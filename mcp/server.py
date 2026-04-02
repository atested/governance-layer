#!/usr/bin/env python3
import base64
import contextvars
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from mcp.server.fastmcp import FastMCP  # type: ignore
except ModuleNotFoundError:
    FastMCP = None  # type: ignore
from capability_introspection import (
    emit_action_record,
    list_recent_receipts,
    load_receipt,
    replay_check,
)
from inspectability_contract import (
    describe_inspectability_contract,
    build_receipt_tool_events_payload,
    build_tool_event_list_for_receipt_payload,
    build_tool_event_list_recent_payload,
    build_tool_event_row_payload,
    build_tool_event_receipts_payload,
)
from tool_event_store import (
    get_tool_event_bundle,
    get_tool_event_by_digest,
    list_all_tool_events,
    tool_event_bundle_store_root,
    upsert_tool_event_bundle,
    list_tool_events_recent,
)
from tool_event_link_store import upsert_receipt_tool_event_links
from tool_event_link_store import get_receipts_for_tool_event, get_tool_events_for_receipt
from capabilities import build_registry
from licensing import resolve_posture, activate_license, trial_days_remaining, load_license
from registry_integrity import RegistryIntegrity, ConfigFileIntegrity, validate_messaging_map_schema
from storage_contract import describe_storage_contract, runtime_root

REPO = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
from messaging_surface import (
    FORWARD_RECEIPT_FILENAME,
    FORWARD_RECEIPT_VERSION,
    find_mapping_entry,
    load_messaging_map,
    resolve_repo_relative_payload_handle,
    sha256_prefixed_bytes,
)
from approval_store import ApprovalStore, load_approval_store_from_chain
from event_model import build_non_action_event
from transparency import classify_action_transparency, handle_opaque_action
from verification import (
    VerificationStateTracker,
    check_verification_state,
    evaluate_probe_result,
    load_verification_state_from_chain,
)
from readout import (
    assemble_governance_status_record,
    audit_query as _audit_query,
    audit_record_detail as _audit_record_detail,
    audit_report as _audit_report,
    governance_activity_view,
    governance_approvals_view,
    governance_verification_view,
)

APPEND = REPO / "scripts" / "append-record-runtime.sh"
CAP_REGISTRY_PATH = REPO / "capabilities" / "capability-registry.json"

VERIFY_CHAIN = REPO / "scripts" / "verify-chain.py"
RUNTIME = runtime_root(REPO)
INTENTS_DIR = RUNTIME / "LOGS" / "intents"
RECORDS_DIR = RUNTIME / "LOGS" / "records"
CHAIN = RUNTIME / "LOGS" / "decision-chain.jsonl"
_VERIFICATION_TRACKER: Optional[VerificationStateTracker] = None
_APPROVAL_STORE: Optional[ApprovalStore] = None
_REMOTE_TRANSPORT = "streamable-http"
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Chain-append lock: prevents concurrent verify-append-verify sequences from
# interleaving when multiple clients share one server process (HTTP transport).
# threading.Lock is correct here because FastMCP runs sync @mcp.tool() handlers
# in a thread pool — asyncio.Lock cannot be acquired from sync thread context.
_CHAIN_LOCK = threading.Lock()

# Registry reload lock: prevents concurrent reads and writes of the in-memory
# capability registry (_CAP_REG, _CAPS) from racing during a governed reload.
_REGISTRY_LOCK = threading.Lock()

# Per-request user identity, set by remote_server.py middleware for HTTP
# transport.  Defaults to None for stdio (single-user) transport.
_current_user_identity: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "_current_user_identity", default=None
)


def _ensure_runtime_permissions() -> None:
    """H8: Ensure runtime directories have restrictive permissions (0700)."""
    import stat
    for d in (RUNTIME, RUNTIME / "LOGS", RUNTIME / "LOGS" / "records",
              RUNTIME / "LOGS" / "intents", RUNTIME / "LOGS" / "attestations"):
        if d.exists() and d.is_dir():
            try:
                current = d.stat().st_mode & 0o777
                if current != 0o700:
                    d.chmod(0o700)
            except OSError:
                pass


def _check_signing_key_permissions() -> None:
    """M2: Warn if signing key file has permissions broader than 0600."""
    import stat
    key_path = os.environ.get("GOV_SIGNING_KEY_PATH", "")
    if not key_path:
        return
    p = Path(key_path)
    if not p.exists():
        return
    try:
        mode = p.stat().st_mode & 0o777
        if mode & (stat.S_IRGRP | stat.S_IWGRP | stat.S_IROTH | stat.S_IWOTH):
            import sys as _sys
            print(
                f"WARNING: signing key {key_path} has permissions {oct(mode)} "
                f"(should be 0600). Other users may read the private key.",
                file=_sys.stderr, flush=True,
            )
    except OSError:
        pass


# H8: Set permissions on startup
if RUNTIME.exists():
    _ensure_runtime_permissions()
# M2: Check signing key permissions on startup
_check_signing_key_permissions()


def _tool_catalog_bundle_store_root() -> Path:
    return REPO / "out" / "mcp_tool_catalog_bundles"


def _tool_catalog_module():
    mod = _cap_registry().get("TOOL_REGISTER")
    if mod is None:
        raise RuntimeError("TOOL_REGISTER_CAPABILITY_MISSING")
    return mod


def _parse_machine_line(prefix: str, text: str) -> Dict[str, str]:
    for line in text.splitlines():
        if not line.startswith(prefix):
            continue
        out: Dict[str, str] = {}
        for part in line.split()[1:]:
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            out[key] = value
        return out
    return {}


def _env_host() -> str:
    return str(os.environ.get("GOVMCP_HOST", "127.0.0.1")).strip() or "127.0.0.1"


def _env_port() -> int:
    raw = str(os.environ.get("GOVMCP_PORT", "8000")).strip() or "8000"
    try:
        port = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"GOVMCP_PORT_INVALID:{raw}") from exc
    if port <= 0 or port > 65535:
        raise RuntimeError(f"GOVMCP_PORT_INVALID:{raw}")
    return port


def _env_log_level() -> str:
    level = str(os.environ.get("GOVMCP_LOG_LEVEL", "INFO")).strip().upper() or "INFO"
    if level not in _VALID_LOG_LEVELS:
        raise RuntimeError(f"GOVMCP_LOG_LEVEL_INVALID:{level}")
    return level


def _env_streamable_http_path() -> str:
    path = str(os.environ.get("GOVMCP_STREAMABLE_HTTP_PATH", "/mcp")).strip() or "/mcp"
    if not path.startswith("/"):
        path = "/" + path
    return path


def remote_runtime_contract() -> Dict[str, Any]:
    return {
        "transport": _REMOTE_TRANSPORT,
        "host": _env_host(),
        "port": _env_port(),
        "streamable_http_path": _env_streamable_http_path(),
        "runtime_root": str(RUNTIME).replace("\\", "/"),
        "runtime_root_source": "env:GOV_RUNTIME_DIR" if os.environ.get("GOV_RUNTIME_DIR") else "repo_default:gov_runtime",
        "auth_state": "not_configured_in_remote_foundation",
        "deployment_state": "not_packaged_in_remote_foundation",
    }


def _mcp_settings_kwargs() -> Dict[str, Any]:
    return {
        "host": _env_host(),
        "port": _env_port(),
        "log_level": _env_log_level(),
        "streamable_http_path": _env_streamable_http_path(),
    }

if FastMCP is None:
    class _FallbackMCP:
        def __init__(self, _name: str) -> None:
            pass

        def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
                return fn
            return _decorator

        def run(self, _transport: str = "stdio") -> None:
            print("MCP_RUNTIME_UNAVAILABLE=YES")
            raise SystemExit(2)

    mcp = _FallbackMCP("governance-broker")
else:
    mcp = FastMCP("governance-broker", **_mcp_settings_kwargs())


def run_local_stdio() -> None:
    mcp.run("stdio")


def run_remote_streamable_http() -> None:
    mcp.run(_REMOTE_TRANSPORT)


def _run_stdio_capabilities_execute() -> int:
    line = sys.stdin.readline()
    if not line:
        print("CAPABILITIES_PROTOCOL_ERROR=EMPTY_REQUEST")
        return 2
    try:
        req = json.loads(line)
    except json.JSONDecodeError:
        print("CAPABILITIES_PROTOCOL_ERROR=MALFORMED_JSON")
        return 2
    if not isinstance(req, dict):
        print("CAPABILITIES_PROTOCOL_ERROR=INVALID_REQUEST")
        return 2
    method = req.get("method")
    params = req.get("params", {})
    if not isinstance(params, dict):
        print("CAPABILITIES_PROTOCOL_ERROR=INVALID_PARAMS")
        return 2
    if method not in (
        "capabilities.list",
        "capabilities.describe",
        "capabilities.normalize_action",
        "capabilities.execute",
        "capabilities.admissibility_check",
        "capabilities.tool_register",
        "capabilities.tool_get",
        "capabilities.tool_list_recent",
        "capabilities.tool_catalog_list_slice",
        "capabilities.tool_catalog_summarize_slice",
        "capabilities.tool_catalog_export_bundle",
        "capabilities.tool_catalog_verify_bundle",
        "capabilities.receipt",
        "capabilities.list_recent",
        "capabilities.replay_check",
        "capabilities.tool_event_get",
        "capabilities.tool_event_list_recent",
        "capabilities.tool_event_list_for_receipt",
        "capabilities.tool_event_export",
        "capabilities.tool_event_bundle_verify",
        "capabilities.receipt_tool_events",
        "capabilities.tool_event_receipts",
    ):
        if method != "capabilities.export_attestation":
            print("CAPABILITIES_PROTOCOL_ERROR=METHOD_MISMATCH")
            return 2
    if method == "capabilities.export_attestation":
        run_id = str(params.get("run_id", ""))
        out_dir = str(params.get("out_dir", ""))
        include_signature = bool(params.get("include_signature", True))
        include_replay_check = bool(params.get("include_replay_check", False))
        result = capabilities_export_attestation(
            run_id,
            out_dir,
            include_signature,
            include_replay_check=include_replay_check,
        )
    elif method not in (
        "capabilities.list",
        "capabilities.describe",
        "capabilities.normalize_action",
        "capabilities.execute",
        "capabilities.admissibility_check",
        "capabilities.tool_register",
        "capabilities.tool_get",
        "capabilities.tool_list_recent",
        "capabilities.tool_catalog_list_slice",
        "capabilities.tool_catalog_summarize_slice",
        "capabilities.tool_catalog_export_bundle",
        "capabilities.tool_catalog_verify_bundle",
        "capabilities.receipt",
        "capabilities.list_recent",
        "capabilities.replay_check",
        "capabilities.tool_event_get",
        "capabilities.tool_event_list_recent",
        "capabilities.tool_event_list_for_receipt",
        "capabilities.tool_event_export",
        "capabilities.tool_event_bundle_verify",
        "capabilities.receipt_tool_events",
        "capabilities.tool_event_receipts",
    ):
        print("CAPABILITIES_PROTOCOL_ERROR=METHOD_MISMATCH")
        return 2
    if method == "capabilities.list":
        result = capabilities_list()
    elif method == "capabilities.describe":
        name = str(params.get("name", ""))
        result = capabilities_describe(name)
    elif method == "capabilities.normalize_action":
        action = params.get("action", {})
        if not isinstance(action, dict):
            print("CAPABILITIES_PROTOCOL_ERROR=INVALID_ACTION")
            return 2
        name = str(action.get("name", ""))
        action_params = action.get("params", {})
        result = capabilities_normalize_action(name, action_params)
    elif method == "capabilities.execute":
        action = params.get("action", {})
        if not isinstance(action, dict):
            print("CAPABILITIES_PROTOCOL_ERROR=INVALID_ACTION")
            return 2
        mode = params.get("mode", {})
        if not isinstance(mode, dict):
            mode = {}
        name = str(action.get("name", ""))
        action_params = action.get("params", {})
        result = capabilities_execute(name, action_params, mode)
    elif method == "capabilities.admissibility_check":
        action = params.get("action", {})
        if not isinstance(action, dict):
            print("CAPABILITIES_PROTOCOL_ERROR=INVALID_ACTION")
            return 2
        name = str(action.get("name", ""))
        action_params = action.get("params", {})
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_admissibility_check(name, action_params, policy_context=policy_context)
    elif method == "capabilities.tool_register":
        action = params.get("action", {})
        if not isinstance(action, dict):
            print("CAPABILITIES_PROTOCOL_ERROR=INVALID_ACTION")
            return 2
        result = capabilities_tool_register(action)
    elif method == "capabilities.tool_get":
        tool_id = str(params.get("tool_id", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_get(tool_id, policy_context=policy_context)
    elif method == "capabilities.tool_list_recent":
        limit = int(params.get("limit", 10))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_list_recent(limit, policy_context=policy_context)
    elif method == "capabilities.tool_catalog_list_slice":
        created_from = str(params.get("created_from", "any"))
        capability = str(params.get("capability", ""))
        limit = params.get("limit", 25)
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_catalog_list_slice(
            created_from=created_from,
            capability=capability,
            limit=limit,
            policy_context=policy_context,
        )
    elif method == "capabilities.tool_catalog_summarize_slice":
        created_from = str(params.get("created_from", "any"))
        capability = str(params.get("capability", ""))
        limit = params.get("limit", 25)
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_catalog_summarize_slice(
            created_from=created_from,
            capability=capability,
            limit=limit,
            policy_context=policy_context,
        )
    elif method == "capabilities.tool_catalog_export_bundle":
        tool_ids = params.get("tool_ids", [])
        sign = bool(params.get("sign", False))
        private_key_ref = str(params.get("private_key_ref", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_catalog_export_bundle(
            tool_ids=tool_ids,
            sign=sign,
            private_key_ref=private_key_ref,
            policy_context=policy_context,
        )
    elif method == "capabilities.tool_catalog_verify_bundle":
        bundle_id = str(params.get("bundle_id", ""))
        require_signature = bool(params.get("require_signature", False))
        pubkey = str(params.get("pubkey", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_catalog_verify_bundle(
            bundle_id=bundle_id,
            require_signature=require_signature,
            pubkey=pubkey,
            policy_context=policy_context,
        )
    elif method == "capabilities.receipt":
        run_id = str(params.get("run_id", ""))
        verify_signature = bool(params.get("verify_signature", False))
        pubkey = str(params.get("pubkey", ""))
        result = capabilities_receipt(run_id, verify_signature=verify_signature, pubkey=pubkey)
    elif method == "capabilities.list_recent":
        limit = int(params.get("limit", 10))
        result = capabilities_list_recent(limit)
    elif method == "capabilities.replay_check":
        run_id = str(params.get("run_id", ""))
        verify_signature = bool(params.get("verify_signature", False))
        pubkey = str(params.get("pubkey", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        emit_artifact = bool(params.get("emit_artifact", False))
        result = capabilities_replay_check(
            run_id,
            verify_signature=verify_signature,
            pubkey=pubkey,
            policy_context=policy_context,
            emit_artifact=emit_artifact,
        )
    elif method == "capabilities.tool_event_get":
        digest = str(params.get("digest", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_event_get(digest, policy_context=policy_context)
    elif method == "capabilities.tool_event_list_recent":
        limit = int(params.get("limit", 10))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_event_list_recent(limit, policy_context=policy_context)
    elif method == "capabilities.tool_event_list_for_receipt":
        receipt_id = str(params.get("receipt_id", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_event_list_for_receipt(receipt_id, policy_context=policy_context)
    elif method == "capabilities.tool_event_export":
        digest = str(params.get("digest", ""))
        receipt_id = str(params.get("receipt_id", ""))
        limit = int(params.get("limit", 10))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_event_export(
            digest=digest,
            receipt_id=receipt_id,
            limit=limit,
            policy_context=policy_context,
        )
    elif method == "capabilities.tool_event_bundle_verify":
        bundle_id = str(params.get("bundle_id", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_event_bundle_verify(bundle_id=bundle_id, policy_context=policy_context)
    elif method == "capabilities.receipt_tool_events":
        receipt_id = str(params.get("receipt_id", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_receipt_tool_events(receipt_id=receipt_id, policy_context=policy_context)
    elif method == "capabilities.tool_event_receipts":
        digest = str(params.get("digest", ""))
        policy_context = str(params.get("policy_context", "DEFAULT"))
        result = capabilities_tool_event_receipts(digest=digest, policy_context=policy_context)
    print(json.dumps({"id": req.get("id"), "result": result}, sort_keys=True, separators=(",", ":")))
    return 0


def _cap_registry():
    _REGISTRY_INTEGRITY.verify_or_fail()
    with _REGISTRY_LOCK:
        return build_registry(CAP_REGISTRY_PATH)


@mcp.tool()
def capabilities_list() -> Dict[str, Any]:
    """List available governed capabilities with deterministic ordering."""
    caps = []
    reg = _cap_registry()
    for name in reg.names():
        mod = reg.get(name)
        if mod is None:
            continue
        desc = mod.describe()
        caps.append(
            {
                "name": desc.name,
                "params": desc.params,
            }
        )
    return {"capabilities_version": "v0", "capabilities": caps}


@mcp.tool()
def capabilities_describe(name: str) -> Dict[str, Any]:
    """Describe one capability schema deterministically."""
    cap_name = str(name or "").strip()
    mod = _cap_registry().get(cap_name)
    if mod is None:
        return {"capabilities_version": "v0", "ok": False, "reason_token": "CAPABILITY_UNKNOWN", "name": cap_name}
    desc = mod.describe()
    return {
        "capabilities_version": "v0",
        "ok": True,
        "name": desc.name,
        "params": desc.params,
        "reason_tokens": desc.reason_tokens,
    }


@mcp.tool()
def capabilities_normalize_action(name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize action inputs without execution."""
    mod = _cap_registry().get(str(name or "").strip())
    if mod is None:
        norm = {"ok": False, "reason_token": "CAPABILITY_UNKNOWN", "normalized_params": {}}
    else:
        norm = mod.normalize_action(CAP_REGISTRY_PATH, params)
    return {
        "capabilities_version": "v0",
        "action_name": str(name),
        "ok": bool(norm.get("ok", False)),
        "reason_token": str(norm.get("reason_token", "UNKNOWN")),
        "normalized_params": norm.get("normalized_params", {}),
    }

def _load_cap_registry() -> dict:
    with open(CAP_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _cap_container(reg: dict) -> dict:
    # Handle both dict and array structures
    if "tools" in reg and isinstance(reg["tools"], list):
        # Convert array to dict keyed by tool name
        return {t.get("tool") or t.get("capability_class"): t for t in reg["tools"]}
    if "FS_WRITE" in reg:
        return reg
    for k in ("tools", "capabilities"):
        if k in reg and isinstance(reg[k], dict) and "FS_WRITE" in reg[k]:
            return reg[k]
    return reg

_CAP_REG = _load_cap_registry()
_CAPS = _cap_container(_CAP_REG)

# ---------------------------------------------------------------------------
# Registry integrity protection
# ---------------------------------------------------------------------------
_REGISTRY_INTEGRITY = RegistryIntegrity(CAP_REGISTRY_PATH, RUNTIME)
_REGISTRY_INIT_RESULT = _REGISTRY_INTEGRITY.initialize(
    enforce_permissions=True,
)
# Print startup warnings (visible in server logs)
for _w in _REGISTRY_INIT_RESULT.get("warnings", []):
    print(f"[registry-integrity] {_w}", file=sys.stderr)

# Messaging tool map integrity protection (same model as capability registry)
_MSG_MAP_PATH = REPO / "capabilities" / "messaging-tool-map.v1.json"
_MSG_MAP_INTEGRITY = ConfigFileIntegrity(
    _MSG_MAP_PATH, RUNTIME,
    name="messaging_map",
    validate_fn=validate_messaging_map_schema,
    backup_filename="messaging_map_backup.json",
)
try:
    _MSG_MAP_INIT = _MSG_MAP_INTEGRITY.initialize(enforce_permissions=True)
    for _w in _MSG_MAP_INIT.get("warnings", []):
        print(f"[messaging-map-integrity] {_w}", file=sys.stderr)
except RuntimeError as _e:
    print(f"[messaging-map-integrity] WARNING: {_e}", file=sys.stderr)

def get_capability(capability: str) -> dict:
    if capability not in _CAPS:
        raise KeyError(f"Unknown capability: {capability}")
    return _CAPS[capability]

def normalize_args(capability: str, args: dict) -> tuple:
    """Normalize args based on capability spec. Returns (norm_args, constraints_or_error)."""
    cap = get_capability(capability)
    caps = cap.get("caps", {}) or {}
    spec = cap.get("args", {}) or {}
    required = spec.get("required", []) or []

    missing = [k for k in required if k not in args or args.get(k) is None]
    if missing:
        return args, {"_missing": missing}

    out = dict(args)

    if capability == "FS_LIST":
        dflt = int(caps.get("max_entries_default", 100))
        hard = int(caps.get("max_entries_hard", 500))
        try:
            n = int(out.get("max_entries", dflt))
        except Exception:
            n = dflt
        if n < 1:
            n = 1
        if n > hard:
            n = hard
        out["max_entries"] = n

        if not bool(caps.get("include_hidden_allowed", False)):
            out["include_hidden"] = False

    if capability == "FS_READ":
        dflt = int(caps.get("max_bytes_default", cap.get("max_bytes_default", 4096)))
        hard = int(caps.get("max_bytes_hard", cap.get("max_bytes_hard", 65536)))
        try:
            mb = int(out.get("max_bytes", dflt))
        except Exception:
            mb = dflt
        if mb < 1:
            mb = 1
        if mb > hard:
            mb = hard
        out["max_bytes"] = mb

        try:
            off = int(out.get("offset", 0))
        except Exception:
            off = 0
        if off < int(caps.get("offset_min", 0)):
            off = int(caps.get("offset_min", 0))
        out["offset"] = off

        out["as_text"] = bool(out.get("as_text", True))

    if capability == "FS_WRITE":
        out["overwrite"] = bool(out.get("overwrite", False))
        if not bool(caps.get("request_executable_allowed", False)):
            out["request_executable"] = False
        else:
            out["request_executable"] = bool(out.get("request_executable", False))

    if capability == "FS_MKDIR":
        out["parents"] = bool(out.get("parents", False))
        out["exist_ok"] = bool(out.get("exist_ok", False))

    if capability == "FS_MOVE":
        out["overwrite"] = bool(out.get("overwrite", False))

    if capability == "FS_DELETE":
        out["recursive"] = bool(out.get("recursive", False))

    # Build constraints dict (excluding content)
    constraints = {}
    for k, v in out.items():
        if k != "content":
            constraints[k] = v

    return out, constraints

def _write_json(path: Path, obj: Any) -> None:
    """Write JSON to a file with restrictive permissions (0600)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    import stat as _stat
    import tempfile as _tmpmod
    content = json.dumps(obj, indent=2, sort_keys=True) + "\n"
    fd, tmp = _tmpmod.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.fchmod(fd, _stat.S_IRUSR | _stat.S_IWUSR)  # 0600
        os.close(fd)
        os.rename(tmp, str(path))
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_attestation_file(path: Path, obj: Any) -> None:
    """Write attestation JSON with 0600 permissions."""
    _write_json(path, obj)


def _governed_family() -> str:
    return str(os.environ.get("GOV_GOVERNED_FAMILY", "mcp_tools_v1")).strip() or "mcp_tools_v1"


def _deployment_context() -> str:
    return str(os.environ.get("GOV_DEPLOYMENT_CONTEXT", "default")).strip() or "default"


def _policy_version() -> str:
    return str(os.environ.get("GOV_POLICY_VERSION", "baseline-v1")).strip() or "baseline-v1"


def _verification_tracker() -> VerificationStateTracker:
    global _VERIFICATION_TRACKER
    if _VERIFICATION_TRACKER is None:
        if CHAIN.exists():
            _VERIFICATION_TRACKER = load_verification_state_from_chain(str(CHAIN))
        else:
            _VERIFICATION_TRACKER = VerificationStateTracker()
    return _VERIFICATION_TRACKER


def _approval_store() -> ApprovalStore:
    global _APPROVAL_STORE
    if _APPROVAL_STORE is None:
        if CHAIN.exists():
            _APPROVAL_STORE = load_approval_store_from_chain(str(CHAIN))
        else:
            _APPROVAL_STORE = ApprovalStore()
    return _APPROVAL_STORE


def _chain_meta_path() -> Path:
    """Path to chain metadata file (M1: truncation detection)."""
    return CHAIN.parent / "chain_meta.json"


def _read_chain_meta() -> Dict[str, Any]:
    """Read chain metadata. Returns empty dict if not present."""
    p = _chain_meta_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _update_chain_meta_length(new_length: int) -> None:
    """Atomically update chain_meta.json with current chain length."""
    meta = _read_chain_meta()
    meta["chain_length"] = new_length
    _write_json(_chain_meta_path(), meta)


def _chain_line_count() -> int:
    """Count non-empty lines in the chain file."""
    if not CHAIN.exists():
        return 0
    count = 0
    with open(CHAIN, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                count += 1
    return count


def _check_chain_truncation() -> None:
    """M1: Detect chain truncation by comparing actual length to recorded length."""
    meta = _read_chain_meta()
    recorded = meta.get("chain_length")
    if recorded is None:
        return  # No metadata yet — first run or legacy chain.
    actual = _chain_line_count()
    if actual < recorded:
        raise RuntimeError(
            f"CHAIN_TRUNCATION_DETECTED: recorded={recorded} actual={actual}. "
            f"Records may have been removed from the chain."
        )


def _chain_head_record_hash() -> Optional[str]:
    if not CHAIN.exists():
        return None
    last_line = ""
    with open(CHAIN, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if not last_line:
        return None
    try:
        record = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"CHAIN_HEAD_INVALID_JSON: {exc}") from exc
    record_hash = record.get("record_hash")
    if record_hash is None:
        return None
    if not isinstance(record_hash, str) or not record_hash:
        raise RuntimeError("CHAIN_HEAD_MISSING_RECORD_HASH")
    return record_hash


def _acquire_chain_file_lock() -> Path:
    """H6: Acquire the cross-process mkdir lock used by append-record-runtime.sh.

    M6: On timeout, check if the lock holder PID is still alive.
    If the holder is dead, remove the stale lock and retry once.
    """
    lockdir = Path(str(CHAIN) + ".lock.d")
    lock_meta = lockdir / "lock_owner.json"
    max_wait = 50

    def _try_acquire() -> bool:
        try:
            lockdir.mkdir(exist_ok=False)
            # Write PID+timestamp metadata for stale lock detection.
            try:
                import time as _time
                meta = json.dumps({"pid": os.getpid(), "ts": _time.time()})
                lock_meta.write_text(meta, encoding="utf-8")
            except OSError:
                pass
            return True
        except FileExistsError:
            return False

    def _holder_is_alive() -> bool:
        """M6: Check if the PID that holds the lock is still running."""
        try:
            data = json.loads(lock_meta.read_text(encoding="utf-8"))
            pid = data.get("pid")
            if not isinstance(pid, int):
                return True  # Can't determine — assume alive.
            os.kill(pid, 0)  # signal 0 = existence check
            return True
        except (OSError, json.JSONDecodeError, KeyError):
            return False  # PID doesn't exist or metadata unreadable.

    waited = 0
    while True:
        if _try_acquire():
            return lockdir
        waited += 1
        if waited >= max_wait:
            # M6: Before giving up, check if the holder is dead.
            if not _holder_is_alive():
                try:
                    # Remove stale lock metadata then directory.
                    lock_meta.unlink(missing_ok=True)
                    lockdir.rmdir()
                except OSError:
                    pass
                # Retry once.
                if _try_acquire():
                    return lockdir
            raise TimeoutError(f"timed out waiting for chain lock ({lockdir})")
        import time
        time.sleep(0.1)


def _release_chain_file_lock(lockdir: Path) -> None:
    try:
        # Remove metadata file first, then directory.
        (lockdir / "lock_owner.json").unlink(missing_ok=True)
        lockdir.rmdir()
    except OSError:
        pass


def _append_non_action_event(event: Dict[str, Any]) -> Dict[str, Any]:
    # M4 (F-11): Validate non-action event has required fields and recognized
    # event_type before accepting into the chain.
    from event_model import validate_non_action_event
    ok, err = validate_non_action_event(event)
    if not ok:
        raise ValueError(f"NON_ACTION_EVENT_INVALID: {err}")

    # Fix 2 (D-019): Add runtime fields BEFORE hash computation.
    # The event's record_hash must cover ALL fields that are written.
    identity = _current_user_identity.get(None)
    if identity is not None:
        event["user_identity"] = identity
    posture = resolve_posture(RUNTIME)
    event["license_status"] = posture["license_status"]
    event["license_tier"] = posture["license_tier"]
    event["organization_id"] = posture["organization_id"]
    event["license_expiry"] = posture["license_expiry"]
    # Recompute record_hash now that all fields are set.
    from event_model import _compute_event_record_hash
    event["record_hash"] = _compute_event_record_hash(event)
    CHAIN.parent.mkdir(parents=True, exist_ok=True)
    # H6: Acquire cross-process file lock (same lock as append-record-runtime.sh)
    lockdir = _acquire_chain_file_lock()
    try:
        line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
        # H8 (D-019): Ensure chain file is 0600.
        import stat as _stat
        fd = os.open(str(CHAIN), os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                      _stat.S_IRUSR | _stat.S_IWUSR)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    finally:
        _release_chain_file_lock(lockdir)
    # M1: Update chain length metadata after successful append.
    _update_chain_meta_length(_chain_line_count())
    # Incrementally update runtime singletons so they stay consistent
    # with the chain without requiring a full re-parse.
    event_type = event.get("event_type")
    if event_type == "verification_state_transition":
        _verification_tracker().ingest_transition_event(event)
    elif event_type == "opaque_artifact_approval":
        _approval_store().ingest_approval(event)
    elif event_type == "opaque_artifact_revocation":
        _approval_store().ingest_revocation(event)
    return event


def _load_opaque_artifact_bytes(args: Dict[str, Any]) -> bytes:
    artifact_path = str(args.get("opaque_artifact_path", "")).strip()
    if artifact_path:
        candidate = Path(artifact_path)
        if not candidate.is_absolute():
            candidate = (REPO / candidate).resolve()
        return candidate.read_bytes()

    if bool(args.get("opaque_executable")):
        content = args.get("content")
        if isinstance(content, str):
            return content.encode("utf-8")
        if isinstance(content, (bytes, bytearray)):
            return bytes(content)

    raise RuntimeError("OPAQUE_ARTIFACT_UNRESOLVABLE")


def _append_scoped_artifact_event(
    event_type: str,
    artifact_identity: str,
    operator_identity: str,
) -> Dict[str, Any]:
    payload = {
        "artifact_identity": str(artifact_identity),
        "governed_family": _governed_family(),
        "deployment_context": _deployment_context(),
        "policy_version": _policy_version(),
    }
    if event_type == "opaque_artifact_approval":
        payload["approving_operator"] = str(operator_identity)
    elif event_type == "opaque_artifact_revocation":
        payload["revoking_operator"] = str(operator_identity)
    else:
        raise ValueError(f"unsupported event_type: {event_type}")

    with _CHAIN_LOCK:
        _verify_chain()
        event = build_non_action_event(
            event_type,
            payload,
            prev_record_hash=_chain_head_record_hash(),
        )
        rec = _append_non_action_event(event)
        _verify_chain()
    return rec


def _transition_verification_surface(
    governed_family: str,
    to_state: str,
) -> Dict[str, Any]:
    tracker = _verification_tracker()
    with _CHAIN_LOCK:
        _verify_chain()
        event = tracker.transition(
            governed_family,
            to_state,
            prev_record_hash=_chain_head_record_hash(),
        )
        rec = _append_non_action_event(event)
        _verify_chain()
    return rec



def _invalidate_runtime_state() -> None:
    """Reset all chain-derived runtime singletons.

    Called after chain quarantine to ensure stale state from the old
    chain cannot leak into subsequent operations. The next access to
    any singleton will rebuild it from the (now-empty or new) chain.
    """
    global _VERIFICATION_TRACKER, _APPROVAL_STORE
    _VERIFICATION_TRACKER = None
    _APPROVAL_STORE = None


def _quarantine_chain(reason: str) -> str:
    # Move the current chain to a quarantine folder with timestamp.
    # Returns the quarantined file path (string). Does not delete evidence.
    if not CHAIN.exists():
        return ""
    qdir = RUNTIME / "LOGS" / "quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = qdir / f"decision-chain.{ts}.jsonl"
    CHAIN.rename(dst)
    # Write a small marker file alongside for operator context
    (qdir / f"decision-chain.{ts}.reason.txt").write_text(reason + "\n", encoding="utf-8")
    _invalidate_runtime_state()
    return str(dst)

def _verify_chain() -> None:
    # Fail closed if the runtime chain is broken.
    if not CHAIN.exists():
        return
    # M1: Check for truncation before hash verification.
    _check_chain_truncation()
    proc = subprocess.run(
        [sys.executable, str(VERIFY_CHAIN), str(CHAIN)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stdout.strip() or proc.stderr.strip() or "unknown")
        qpath = _quarantine_chain("CHAIN_VERIFY_FAIL: " + msg)
        raise RuntimeError("CHAIN_VERIFY_FAIL: " + msg + (" | quarantined=" + qpath if qpath else ""))

def _append_decision(intent_path: Path) -> Dict[str, Any]:
    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(RUNTIME)

    proc = subprocess.run(
        [str(APPEND), str(intent_path)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    rec = json.loads(proc.stdout.strip().splitlines()[-1])
    return rec

def governed_tool(
    tool_name: str,
    args: Dict[str, Any],
    intent: Dict[str, Any],
    action: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Governed tool wrapper implementing verify→append→verify invariants.

    Args:
        tool_name: Tool identifier (e.g., "FS_WRITE")
        args: Tool arguments to log in decision record
        intent: Intent structure for decision record
        action: Callable that performs the actual tool action if ALLOW.
                Takes the decision record and normalized args, returns action-specific result dict.

    Returns:
        Dict with policy_decision, policy_reasons, decision_record, and optional action results.
    """
    # Registry integrity: verify configuration files haven't been tampered with.
    # Fail closed if modified without a governed reload.
    _REGISTRY_INTEGRITY.verify_or_fail()
    if tool_name in ("MSG_SEND", "MSG_REPLY"):
        _MSG_MAP_INTEGRITY.verify_or_fail()

    req_id = str(uuid.uuid4())
    governed_family = _governed_family()
    verification_state = check_verification_state(governed_family, _verification_tracker())
    request = {
        "tool": tool_name,
        "capability_class": tool_name,
        "args": dict(args),
    }
    transparency = classify_action_transparency(request, _CAP_REG)

    # Classification timing invariant: classify_action_transparency() runs
    # before normalize_args() because unregistered tools (opaque by default)
    # have no capability spec to normalize against. Opaque actions skip
    # normalization entirely — the raw args are sufficient for artifact
    # loading. Transparent actions normalize against the capability spec.
    if transparency == "opaque":
        norm_args = dict(args)
        with _CHAIN_LOCK:
            _verify_chain()
            store = _approval_store()
            rec = _append_non_action_event(
                handle_opaque_action(
                    request=request,
                    artifact_bytes=_load_opaque_artifact_bytes(norm_args),
                    governed_family=governed_family,
                    deployment_context=_deployment_context(),
                    policy_version=_policy_version(),
                    approval_lookup_fn=store.lookup,
                    prev_record_hash=_chain_head_record_hash(),
                )["event"]
            )
            _verify_chain()

        if rec.get("resolution") != "approved_lookup":
            return {
                "policy_decision": "DENY",
                "policy_reasons": [
                    {
                        "code": "OPAQUE_ACTION_DENIED",
                        "detail": {
                            "resolution": rec.get("resolution", "denied"),
                            "artifact_identity": rec.get("artifact_identity", ""),
                        },
                    }
                ],
                "decision_record": {**rec, "verification_state": verification_state},
            }

        action_result = action(rec, norm_args)
        if action_result.get("policy_decision") == "DENY":
            return {
                "policy_decision": "DENY",
                "policy_reasons": action_result.get("policy_reasons", []),
                "decision_record": {**rec, "verification_state": verification_state},
            }

        return {
            "policy_decision": "ALLOW",
            "policy_reasons": [],
            "decision_record": {**rec, "verification_state": verification_state},
            **action_result,
        }

    # Transparent path: normalize args against capability spec.
    norm_args, norm_constraints = normalize_args(tool_name, args)
    if isinstance(norm_constraints, dict) and norm_constraints.get("_missing"):
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-MISSING-INTENT-FIELDS", "detail": {"missing": norm_constraints.get("_missing")}}],
            "decision_record": None,
        }

    identity = _current_user_identity.get(None)
    intent_obj = {
        "tool": tool_name,
        "args": norm_args,
        "intent": intent,
    }
    if identity is not None:
        intent_obj["user_identity"] = identity

    INTENTS_DIR.mkdir(parents=True, exist_ok=True)
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    intent_path = INTENTS_DIR / f"{req_id}.intent.json"
    _write_json(intent_path, intent_obj)

    # Locked verify→append→verify: prevents interleaving under concurrent
    # HTTP clients.  For stdio (single-client) the lock is uncontended.
    with _CHAIN_LOCK:
        _verify_chain()
        rec = _append_decision(intent_path)
        _verify_chain()

    # Enrich record with user identity (additive — included in sidecar
    # record and API response for attribution).
    if identity is not None:
        rec["user_identity"] = identity

    # Enrich record with licensing posture (additive metadata — does not
    # affect policy decisions, only records the truth about license state).
    posture = resolve_posture(RUNTIME)
    rec["license_status"] = posture["license_status"]
    rec["license_tier"] = posture["license_tier"]
    rec["organization_id"] = posture["organization_id"]
    rec["license_expiry"] = posture["license_expiry"]

    # Persist a pretty record copy (optional convenience, not part of the chain)
    record_path = RECORDS_DIR / f"{req_id}.record.json"
    _write_json(record_path, rec)
    rec_with_verification = dict(rec)
    rec_with_verification["verification_state"] = verification_state

    decision = rec.get("policy_decision")
    if decision != "ALLOW":
        return {
            "policy_decision": decision,
            "policy_reasons": rec.get("policy_reasons", []),
            "decision_record": rec_with_verification,
        }

    # Execute the action
    action_result = action(rec, norm_args)

    return {
        "policy_decision": "ALLOW",
        "policy_reasons": rec.get("policy_reasons", []),
        "decision_record": rec_with_verification,
        **action_result
    }


def evaluate_action(
    tool_name: str,
    args: Dict[str, Any],
    intent: Dict[str, Any],
    user_identity: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate an action against governance policy without executing it.

    Routes through the same policy evaluation engine as governed MCP tools,
    producing an identical chain record. No action is executed — this is a
    pre-flight check only.

    Returns a dict with: decision, reason, record_hash, missing.
    """
    _REGISTRY_INTEGRITY.verify_or_fail()

    # Validate tool exists in capability registry
    if tool_name not in _CAPS:
        return {
            "decision": "DENY",
            "reason": f"Unknown tool: {tool_name}",
            "record_hash": None,
            "missing": ["valid_tool_name"],
        }

    req_id = str(uuid.uuid4())

    # Normalize args against capability spec
    norm_args, norm_constraints = normalize_args(tool_name, args)
    if isinstance(norm_constraints, dict) and norm_constraints.get("_missing"):
        return {
            "decision": "DENY",
            "reason": "Missing required fields: " + ", ".join(norm_constraints["_missing"]),
            "record_hash": None,
            "missing": norm_constraints["_missing"],
        }

    intent_obj = {
        "tool": tool_name,
        "args": norm_args,
        "intent": intent,
    }
    if user_identity is not None:
        intent_obj["user_identity"] = user_identity

    INTENTS_DIR.mkdir(parents=True, exist_ok=True)
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    intent_path = INTENTS_DIR / f"{req_id}.intent.json"
    _write_json(intent_path, intent_obj)

    with _CHAIN_LOCK:
        _verify_chain()
        rec = _append_decision(intent_path)
        _verify_chain()

    if user_identity is not None:
        rec["user_identity"] = user_identity

    posture = resolve_posture(RUNTIME)
    rec["license_status"] = posture["license_status"]
    rec["license_tier"] = posture["license_tier"]
    rec["organization_id"] = posture["organization_id"]
    rec["license_expiry"] = posture["license_expiry"]

    record_path = RECORDS_DIR / f"{req_id}.record.json"
    _write_json(record_path, rec)

    decision = rec.get("policy_decision", "UNKNOWN")
    reasons = rec.get("policy_reasons", [])

    # Build human-readable reason string
    if reasons:
        reason_parts = []
        for r in reasons:
            code = r.get("code", "")
            detail = r.get("detail", {})
            if isinstance(detail, dict) and detail:
                reason_parts.append(f"{code}")
            else:
                reason_parts.append(code)
        reason_str = "; ".join(reason_parts)
    elif decision == "ALLOW":
        reason_str = "Action meets all required conditions."
    else:
        reason_str = "Action does not meet required conditions."

    # Build missing conditions list for DENY
    missing = None
    if decision == "DENY":
        missing = [r.get("code", "") for r in reasons if r.get("code")]

    return {
        "decision": decision,
        "reason": reason_str,
        "record_hash": rec.get("record_hash"),
        "missing": missing,
    }


@mcp.tool()
def approve_artifact(artifact_identity: str, operator_identity: str) -> Dict[str, Any]:
    """Record an opaque artifact approval event in the active governance scope."""
    # M5: Use authenticated identity from ContextVar when available,
    # store caller-supplied value as claimed_operator to prevent spoofing.
    authenticated = _current_user_identity.get(None)
    effective = authenticated if authenticated else operator_identity
    rec = _append_scoped_artifact_event(
        "opaque_artifact_approval",
        artifact_identity,
        effective,
    )
    if authenticated and operator_identity != authenticated:
        rec["claimed_operator"] = operator_identity
    return rec


@mcp.tool()
def revoke_artifact(artifact_identity: str, operator_identity: str) -> Dict[str, Any]:
    """Record an opaque artifact revocation event in the active governance scope."""
    # M5: Use authenticated identity from ContextVar when available.
    authenticated = _current_user_identity.get(None)
    effective = authenticated if authenticated else operator_identity
    rec = _append_scoped_artifact_event(
        "opaque_artifact_revocation",
        artifact_identity,
        effective,
    )
    if authenticated and operator_identity != authenticated:
        rec["claimed_operator"] = operator_identity
    return rec


@mcp.tool()
def list_active_approvals() -> Dict[str, Any]:
    """Return currently active approvals for the active governance scope."""
    if not CHAIN.exists():
        approvals = []
    else:
        scope = {
            "governed_family": _governed_family(),
            "deployment_context": _deployment_context(),
            "policy_version": _policy_version(),
        }
        store = _approval_store()
        approvals = [
            approval
            for approval in store.all_approvals()
            if approval.get("governed_family") == scope["governed_family"]
            and approval.get("deployment_context") == scope["deployment_context"]
            and approval.get("policy_version") == scope["policy_version"]
        ]
        approvals.sort(
            key=lambda row: (
                str(row.get("artifact_identity", "")),
                str(row.get("approving_operator", "")),
                str(row.get("timestamp_utc", "")),
            )
        )

    return {
        "governed_family": _governed_family(),
        "deployment_context": _deployment_context(),
        "policy_version": _policy_version(),
        "approvals": approvals,
    }


@mcp.tool()
def certify_surface(governed_family: str) -> Dict[str, Any]:
    """Record an unverified -> verified transition for a governed surface."""
    return _transition_verification_surface(str(governed_family), "verified")


@mcp.tool()
def report_drift(governed_family: str) -> Dict[str, Any]:
    """Record a verified -> drift_detected transition for a governed surface."""
    return _transition_verification_surface(str(governed_family), "drift_detected")


@mcp.tool()
def recertify_surface(governed_family: str) -> Dict[str, Any]:
    """Record a drift_detected -> verified transition for a governed surface."""
    return _transition_verification_surface(str(governed_family), "verified")


@mcp.tool()
def run_probe_and_apply(governed_family: str, probe_definition: str) -> Dict[str, Any]:
    from probe_harness import run_probe

    tracker = _verification_tracker()
    result = run_probe(probe_definition, str(governed_family))
    target_state = evaluate_probe_result(result, tracker)
    transition_event = None
    if target_state is not None:
        transition_event = _transition_verification_surface(str(governed_family), target_state)
    return {
        "probe_result": {
            "probe_id": result.probe_id,
            "governed_family": result.governed_family,
            "property_tested": result.property_tested,
            "evidence": result.evidence,
            "passed": result.passed,
            "nonce": result.nonce,
            "timestamp_utc": result.timestamp_utc,
        },
        "target_state": target_state,
        "transition_event": transition_event,
    }


@mcp.tool()
def governance_status(window: Optional[int] = None) -> Dict[str, Any]:
    """Return the full GASR governance status snapshot."""
    window_value = int(window) if window is not None else None
    if window_value is not None and window_value <= 0:
        window_value = None
    return assemble_governance_status_record(
        CHAIN,
        _verification_tracker(),
        _approval_store(),
        window=window_value,
    )


@mcp.tool()
def system_health() -> Dict[str, Any]:
    """Return system health summary.

    Provides overall health status, chain integrity with break classification,
    DENY rate trends, storage usage, observation gaps, license status, and
    recent stability events. Use this when the operator asks about system health.
    """
    from chain_health import collect_health_signals
    stability_log = RUNTIME / "LOGS" / "chain_stability.jsonl"
    chain_meta = RUNTIME / "LOGS" / "chain_meta.json"
    return collect_health_signals(CHAIN, stability_log, chain_meta, RUNTIME)


@mcp.tool()
def governance_approvals() -> Dict[str, Any]:
    """Return the active-approval GASR view."""
    return governance_approvals_view(CHAIN, _approval_store())


@mcp.tool()
def governance_verification(governed_family: str = "") -> Dict[str, Any]:
    """Return the verification-state GASR view."""
    family = str(governed_family).strip() or None
    return governance_verification_view(
        CHAIN,
        _verification_tracker(),
        governed_family=family,
    )


@mcp.tool()
def governance_activity(
    limit: int = 50,
    offset: int = 0,
    governed_family: str = "",
    event_category: str = "",
    resolution: str = "",
) -> Dict[str, Any]:
    """Return the Governance Activity Projection — bounded recent activity."""
    lim = max(int(limit), 0) if limit is not None else 50
    off = max(int(offset), 0) if offset is not None else 0
    fam = str(governed_family).strip() or None
    cat = str(event_category).strip() or None
    res = str(resolution).strip() or None
    return governance_activity_view(
        CHAIN,
        limit=lim,
        offset=off,
        governed_family=fam,
        event_category=cat,
        resolution=res,
    )


@mcp.tool()
def governance_user_report(window: Optional[int] = None) -> Dict[str, Any]:
    """Return unique user identity statistics from governance records.

    Scans both the decision chain and sidecar record files for user_identity
    fields.  Chain records (non-action events written by server.py) embed
    user_identity directly.  Action records (produced by policy-eval.py) have
    user_identity in the sidecar .record.json files.
    """
    from collections import Counter
    users: Counter[str] = Counter()
    total = 0

    # 1. Scan chain for non-action events with user_identity
    if CHAIN.exists():
        for line in CHAIN.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            total += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            uid = rec.get("user_identity")
            if uid:
                users[uid] += 1

    # 2. Scan sidecar record files for action records with user_identity
    if RECORDS_DIR.exists():
        for rfile in RECORDS_DIR.glob("*.record.json"):
            try:
                rec = json.loads(rfile.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            uid = rec.get("user_identity")
            if uid:
                users[uid] += 1

    return {
        "unique_users": len(users),
        "users": [{"identity": k, "action_count": v} for k, v in users.most_common()],
        "total_records": total,
    }


@mcp.tool()
def license_status() -> Dict[str, Any]:
    """Report current licensing state: status, tier, trial days remaining, unique users."""
    posture = resolve_posture(RUNTIME)
    # H5 (D-021): When clock_anomaly is detected, do not report positive
    # trial_days_remaining — the entire response must be consistent.
    if posture["license_status"] == "clock_anomaly":
        remaining = None
    else:
        remaining = trial_days_remaining(RUNTIME)
    try:
        config = load_license(RUNTIME)
    except ValueError as exc:
        # C2 (D-019): corrupted license.json — return controlled error, not crash.
        return {
            "license_status": "error",
            "license_tier": "personal",
            "organization_id": "",
            "license_expiry": "",
            "trial_days_remaining": None,
            "trial_started": "",
            "unique_users_detected": 0,
            "error": f"license.json is corrupted: {exc}",
        }

    # Count unique users from sidecar records
    unique_users = 0
    if RECORDS_DIR.exists():
        seen: set[str] = set()
        for rfile in RECORDS_DIR.glob("*.record.json"):
            try:
                rec = json.loads(rfile.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            uid = rec.get("user_identity")
            if uid:
                seen.add(uid)
        unique_users = len(seen)

    return {
        "license_status": posture["license_status"],
        "license_tier": posture["license_tier"],
        "organization_id": posture["organization_id"],
        "license_expiry": posture["license_expiry"],
        "trial_days_remaining": remaining,
        "trial_started": config.get("trial_started", ""),
        "unique_users_detected": unique_users,
    }


@mcp.tool()
def license_activate(license_key: str, organization_id: str = "") -> Dict[str, Any]:
    """Activate a license key. Memorializes the activation as a governance record."""
    result = activate_license(RUNTIME, license_key, organization_id)
    return result


# ---------------------------------------------------------------------------
# Registry integrity tools
# ---------------------------------------------------------------------------

@mcp.tool()
def registry_status() -> Dict[str, Any]:
    """Report current capability registry integrity status.

    Returns the registry hash, last verification time, reload count,
    and whether the current file matches the active configuration.
    """
    status = _REGISTRY_INTEGRITY.status()
    # Also check if the file currently matches
    try:
        from registry_integrity import _sha256_file
        file_hash = _sha256_file(CAP_REGISTRY_PATH)
        status["file_matches_active"] = file_hash == status["current_hash"]
        status["file_hash"] = file_hash
    except OSError:
        status["file_matches_active"] = None
        status["file_hash"] = None
    return status


@mcp.tool()
def registry_reload() -> Dict[str, Any]:
    """Reload the capability registry through a governed process.

    Validates the file is well-formed JSON with a valid schema before
    accepting changes. Records the configuration change (old hash → new hash)
    as a governance event. If the file is malformed or fails validation,
    the previous configuration remains in effect — fail closed.
    """
    global _CAP_REG, _CAPS
    result = _REGISTRY_INTEGRITY.reload()

    # Record the configuration change as a governance event
    identity = _current_user_identity.get(None)
    payload = {
        "governed_family": _governed_family(),
        "deployment_context": _deployment_context(),
        "policy_version": _policy_version(),
        "old_registry_hash": result["old_hash"],
        "new_registry_hash": result["new_hash"],
        "changed": result["changed"],
        "tool_count": result["tool_count"],
    }
    if identity:
        payload["operator_identity"] = identity

    with _CHAIN_LOCK:
        _verify_chain()
        event = build_non_action_event(
            "registry_config_change",
            payload,
            prev_record_hash=_chain_head_record_hash(),
        )
        _append_non_action_event(event)
        _verify_chain()

    # Reload the in-memory registry used by server.py
    with _REGISTRY_LOCK:
        _CAP_REG = _load_cap_registry()
        _CAPS = _cap_container(_CAP_REG)

    result["governance_event_id"] = event.get("event_id")
    return result


@mcp.tool()
def registry_check() -> Dict[str, Any]:
    """Validate the current capability registry file without reloading.

    Use this to verify your configuration is valid before calling
    registry_reload. Reports whether the file is well-formed JSON,
    passes schema validation, and what tools it defines.
    """
    return _REGISTRY_INTEGRITY.check()


@mcp.tool()
def usage_attestation() -> Dict[str, Any]:
    """Generate a signed usage attestation artifact.

    Produces a summary of governance usage: unique users, total operations,
    operations by category, licensing posture, and a tier recommendation.
    The attestation is SHA-256 hashed and appended to the decision chain
    as a non-action event.
    """
    from collections import Counter

    # Gather usage statistics
    users: set[str] = set()
    categories: Counter[str] = Counter()
    total_ops = 0
    sessions: set[str] = set()

    # Scan chain
    if CHAIN.exists():
        for line in CHAIN.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            total_ops += 1
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            uid = rec.get("user_identity")
            if uid:
                users.add(uid)
            sid = rec.get("session_id")
            if sid:
                sessions.add(sid)
            # Categorize
            cap_class = rec.get("capability_class", "")
            event_type = rec.get("event_type", "")
            if cap_class:
                categories[cap_class] += 1
            elif event_type:
                categories[event_type] += 1

    # Scan sidecar records
    if RECORDS_DIR.exists():
        for rfile in RECORDS_DIR.glob("*.record.json"):
            try:
                rec = json.loads(rfile.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            uid = rec.get("user_identity")
            if uid:
                users.add(uid)
            sid = rec.get("session_id")
            if sid:
                sessions.add(sid)
            cap_class = rec.get("capability_class", "")
            if cap_class:
                categories[cap_class] += 1

    # Licensing posture
    posture = resolve_posture(RUNTIME, unique_user_count=len(users))
    remaining = trial_days_remaining(RUNTIME)

    # Tier recommendation
    n_users = len(users)
    if n_users <= 1:
        recommended_tier = "personal"
    elif n_users <= 10:
        recommended_tier = "team"
    elif n_users <= 50:
        recommended_tier = "business"
    else:
        recommended_tier = "enterprise"

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    attestation_id = f"att_{uuid.uuid4().hex[:16]}"

    artifact = {
        "attestation_version": "1.0",
        "attestation_id": attestation_id,
        "generated_at": now,
        "unique_users": n_users,
        "unique_sessions": len(sessions),
        "total_operations": total_ops,
        "operations_by_category": dict(categories.most_common()),
        "license_status": posture["license_status"],
        "license_tier": posture["license_tier"],
        "organization_id": posture["organization_id"],
        "license_expiry": posture["license_expiry"],
        "trial_days_remaining": remaining,
        "recommended_tier": recommended_tier,
    }

    # Hash the artifact
    artifact_bytes = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    artifact_hash = f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}"
    artifact["artifact_hash"] = artifact_hash

    # H2 (D-021): Attestation signing is mandatory in production mode.
    # In dev mode (GOV_SIGNING_DEV_MODE=1), unsigned attestation is permitted
    # with an explicit warning.
    dev_mode = os.environ.get("GOV_SIGNING_DEV_MODE", "").strip() == "1"
    signing_key_path = os.environ.get("GOV_SIGNING_KEY_PATH", "")
    signed = False
    artifact["signature"] = None
    artifact["signing_key_id"] = None
    if signing_key_path:
        try:
            from cryptography.hazmat.primitives import serialization as _ser
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as _Ed25519PK
            _pk_bytes = Path(signing_key_path).read_bytes()
            _pk = _ser.load_pem_private_key(_pk_bytes, password=None)
            if isinstance(_pk, _Ed25519PK):
                _raw_pub = _pk.public_key().public_bytes(
                    _ser.Encoding.Raw, _ser.PublicFormat.Raw)
                artifact["signing_key_id"] = "ed25519:" + hashlib.sha256(_raw_pub).hexdigest()
                _sig = _pk.sign(artifact_bytes)
                artifact["signature"] = base64.urlsafe_b64encode(_sig).decode("ascii").rstrip("=")
                signed = True
        except Exception:
            pass
    if not signed:
        if dev_mode:
            artifact["signed"] = False
            artifact["warning"] = "unsigned attestation — dev mode only"
        else:
            return {
                "error": "ATTESTATION_SIGNING_REQUIRED",
                "detail": (
                    "Attestation artifacts must be signed in production mode. "
                    "Set GOV_SIGNING_KEY_PATH to an Ed25519 private key PEM file, "
                    "or set GOV_SIGNING_DEV_MODE=1 for unsigned dev attestations."
                ),
            }

    # Write attestation file to runtime
    att_dir = RUNTIME / "LOGS" / "attestations"
    att_dir.mkdir(parents=True, exist_ok=True)
    att_file = att_dir / f"{attestation_id}.json"
    _write_attestation_file(att_file, artifact)

    # Record in chain (H2: use build_non_action_event for proper hash linkage)
    with _CHAIN_LOCK:
        _verify_chain()
        event = build_non_action_event(
            "usage_attestation",
            {
                "attestation_id": attestation_id,
                "artifact_hash": artifact_hash,
                "unique_users": n_users,
                "recommended_tier": recommended_tier,
            },
            prev_record_hash=_chain_head_record_hash(),
        )
        rec = _append_non_action_event(event)
        _verify_chain()

    return artifact


@mcp.tool()
def observe_ungoverned_operation(
    operation_type: str,
    target: str = "",
    source: str = "",
    observed_at: str = "",
) -> Dict[str, Any]:
    """Record an observation that an ungoverned operation occurred.

    This is NOT a policy evaluation — there is no ALLOW/DENY.  It simply
    records in the governance chain that an operation outside the governed
    tool boundary was observed.  Used to compute the Transparency metric.

    Args:
        operation_type: One of read, write, edit, delete, move, execute,
                        glob, grep, list, other.
        target: Optional path or resource identifier.
        source: Optional identifier for the reporting tool (e.g. "claude_code_hook").
        observed_at: Optional ISO-8601 timestamp of when the operation occurred.
                     Defaults to current time if empty.
    """
    from event_model import UNGOVERNED_OPERATION_TYPES

    op = str(operation_type).strip().lower()
    if op not in UNGOVERNED_OPERATION_TYPES:
        return {"error": "INVALID_OPERATION_TYPE", "valid_types": sorted(UNGOVERNED_OPERATION_TYPES)}

    payload = {
        "operation_type": op,
    }
    if target:
        payload["target"] = str(target).strip()
    if source:
        payload["source"] = str(source).strip()
    if observed_at:
        payload["observed_at"] = str(observed_at).strip()

    with _CHAIN_LOCK:
        _verify_chain()
        event = build_non_action_event(
            "ungoverned_operation_observed",
            payload,
            prev_record_hash=_chain_head_record_hash(),
        )
        rec = _append_non_action_event(event)
        _verify_chain()

    return {
        "recorded": True,
        "event_id": rec.get("event_id"),
        "operation_type": op,
    }


@mcp.tool()
def fs_write(path: str, content: str, overwrite: bool = False, request_executable: bool = False) -> Dict[str, Any]:
    """
    Governed file write. Returns DENY with a full decision record on policy failure.
    On ALLOW, performs the write and returns write_result + decision_record.
    """
    args = {
        "path": path,
        "content": content,
        "overwrite": overwrite,
        "request_executable": request_executable,
    }

    intent = {
        "goal": "Write file via MCP fs_write tool.",
        "constraints": {
            "overwrite": bool(overwrite),
        },
        "requested_action": "FS_WRITE",
        "inputs": [],
        "expected_outputs": [
            {"ref": "file:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual file write if policy allows."""
        # Enforce executable restriction even if caller asks (Phase 1)
        if bool(_args.get("request_executable", False)):
            # If policy allowed but caller asks executable, treat as deny-at-action
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-EXECUTABLE-DISALLOWED", "detail": {"requested": True}}],
            }

        target = Path(path)
        if not target.is_absolute():
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            }

        # H7: Re-resolve and reject symlinks to prevent TOCTOU bypass.
        resolved = target.resolve(strict=False)
        if target.exists() and target.is_symlink():
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-SYMLINK-DENIED", "detail": {"path": str(target), "resolved": str(resolved)}}],
            }
        # Verify resolved path matches what policy approved
        approved_canonical = rec.get("normalized_args", {}).get("canonical_path", "")
        if approved_canonical and str(resolved) != approved_canonical:
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-PATH-CHANGED", "detail": {"expected": approved_canonical, "actual": str(resolved)}}],
            }

        # Perform write
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if isinstance(content, (bytes, bytearray)) else "w"
        if (not bool(_args.get("overwrite", False))) and target.exists():
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-OVERWRITE-DISALLOWED", "detail": {"path": str(target)}}],
            }

        if mode == "w":
            target.write_text(content, encoding="utf-8")
            n = len(content.encode("utf-8"))
        else:
            target.write_bytes(content)
            n = len(content)

        return {
            "write_result": {
                "bytes_written": n,
                "canonical_path": str(target.resolve()),
            }
        }

    return governed_tool("FS_WRITE", args, intent, _action)

@mcp.tool()
def fs_list(path: str, max_entries: int = 100, include_hidden: bool = False) -> Dict[str, Any]:
    """
    Governed directory listing (names/types only).
    Phase 2: include_hidden must be False.
    """
    # Pre-check: absolute path required
    target = Path(path)
    if not target.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            "decision_record": None,
        }

    # Clamp max_entries
    try:
        nmax = int(max_entries)
    except Exception:
        nmax = 100
    if nmax < 1:
        nmax = 1
    if nmax > 500:
        nmax = 500

    args = {
        "path": path,
        "max_entries": nmax,
        "include_hidden": bool(include_hidden),
    }

    intent = {
        "goal": "List directory via MCP fs_list tool.",
        "constraints": {
            "max_entries": nmax,
            "include_hidden": bool(include_hidden),
        },
        "requested_action": "FS_LIST",
        "inputs": [],
        "expected_outputs": [
            {"ref": "directory:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual directory listing if policy allows."""
        # Defense-in-depth: policy-eval should have denied include_hidden
        # This is an operational error if reached (policy should prevent)
        if bool(_args.get("include_hidden", False)):
            return {
                "list_error": {"code": "E-INCLUDE-HIDDEN-NOT-SUPPORTED", "detail": {"include_hidden": True}},
                "list_result": None,
            }

        # Check existence and type (runtime check for races)
        # Policy-eval checks this deterministically; this catches filesystem races
        if not target.exists() or not target.is_dir():
            return {
                "list_error": {"code": "E-NOT-A-DIRECTORY", "detail": {"path": str(target)}},
                "list_result": None,
            }

        # List directory entries
        entries = []
        max_entries = int(_args.get("max_entries", 100))
        with os.scandir(target) as it:
            for ent in it:
                name = ent.name
                # Phase 2: never include hidden entries
                if name.startswith("."):
                    continue
                if ent.is_dir(follow_symlinks=False):
                    typ = "dir"
                elif ent.is_file(follow_symlinks=False):
                    typ = "file"
                else:
                    typ = "other"
                entries.append({"name": name, "type": typ})
                if len(entries) >= max_entries:
                    break

        return {
            "list_result": {
                "canonical_path": str(target.resolve()),
                "entries": entries,
            }
        }

    return governed_tool("FS_LIST", args, intent, _action)

@mcp.tool()
def fs_read(path: str, max_bytes: int = 4096, offset: int = 0, as_text: bool = True) -> Dict[str, Any]:
    """
    Governed file read with strict caps.
    Returns content (capped) plus sha256 hash.
    """
    target = Path(path)
    if not target.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            "decision_record": None,
        }

    # Clamp max_bytes
    try:
        mb = int(max_bytes)
    except Exception:
        mb = 4096
    if mb < 1:
        mb = 1
    if mb > 65536:
        mb = 65536

    # Clamp offset
    try:
        off = int(offset)
    except Exception:
        off = 0
    if off < 0:
        off = 0

    args = {
        "path": path,
        "max_bytes": mb,
        "offset": off,
        "as_text": bool(as_text),
    }

    intent = {
        "goal": "Read file via MCP fs_read tool (capped).",
        "constraints": {
            "max_bytes": mb,
            "offset": off,
            "as_text": bool(as_text),
        },
        "requested_action": "FS_READ",
        "inputs": [],
        "expected_outputs": [
            {"ref": "file:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual file read if policy allows."""
        # Operational (race/perm) errors only; policy reasons come from policy-eval.py
        read_offset = int(_args.get("offset", 0))
        read_max_bytes = int(_args.get("max_bytes", 4096))
        read_as_text = bool(_args.get("as_text", True))

        try:
            data = b""
            with open(target, "rb") as f:
                f.seek(read_offset)
                data = f.read(read_max_bytes)
        except Exception as e:
            return {
                "read_error": {"code": "E-READ-FAILED", "detail": {"error": str(e)}},
                "read_result": None,
            }

        h = hashlib.sha256(data).hexdigest()
        result = {
            "canonical_path": str(target.resolve()),
            "bytes_read": len(data),
            "content_hash_sha256": "sha256:" + h,
            "offset": read_offset,
            "max_bytes": read_max_bytes,
        }

        if read_as_text:
            result["content"] = data.decode("utf-8", errors="replace")
        else:
            result["content_b64"] = base64.b64encode(data).decode("ascii")

        return {"read_result": result}

    return governed_tool("FS_READ", args, intent, _action)

@mcp.tool()
def fs_mkdir(path: str, parents: bool = False, exist_ok: bool = False) -> Dict[str, Any]:
    """
    Governed directory creation.
    parents=True creates intermediate directories (mkdir -p equivalent).
    exist_ok=True silently succeeds if directory already exists.
    Path must be within the registry allowlist; hidden paths are denied.
    """
    target = Path(path)
    if not target.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            "decision_record": None,
        }

    args = {
        "path": path,
        "parents": bool(parents),
        "exist_ok": bool(exist_ok),
    }

    intent = {
        "goal": "Create directory via MCP fs_mkdir tool.",
        "constraints": {
            "parents": bool(parents),
            "exist_ok": bool(exist_ok),
        },
        "requested_action": "FS_MKDIR",
        "inputs": [],
        "expected_outputs": [
            {"ref": "directory:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual directory creation if policy allows."""
        canonical = target.resolve()
        use_parents = bool(_args.get("parents", False))
        use_exist_ok = bool(_args.get("exist_ok", False))
        try:
            canonical.mkdir(parents=use_parents, exist_ok=use_exist_ok)
        except FileExistsError:
            return {
                "mkdir_error": {"code": "E-DIR-EXISTS", "detail": {"canonical_path": str(canonical)}},
                "mkdir_result": None,
            }
        except FileNotFoundError:
            return {
                "mkdir_error": {"code": "E-PARENT-NOT-FOUND", "detail": {"canonical_path": str(canonical)}},
                "mkdir_result": None,
            }
        except Exception as e:
            return {
                "mkdir_error": {"code": "E-MKDIR-FAILED", "detail": {"error": str(e)}},
                "mkdir_result": None,
            }
        return {
            "mkdir_result": {
                "canonical_path": str(canonical),
                "parents": use_parents,
                "exist_ok": use_exist_ok,
            }
        }

    return governed_tool("FS_MKDIR", args, intent, _action)


@mcp.tool()
def fs_move(src_path: str, dst_path: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Governed file/directory move.
    Both src and dst must be within the registry allowlist and within the same root.
    overwrite is denied by default (caps.overwrite_allowed=false).
    """
    src = Path(src_path)
    dst = Path(dst_path)
    if not src.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": src_path}}],
            "decision_record": None,
        }
    if not dst.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": dst_path}}],
            "decision_record": None,
        }

    args = {
        "src_path": src_path,
        "dst_path": dst_path,
        "overwrite": bool(overwrite),
    }

    intent = {
        "goal": "Move file or directory via MCP fs_move tool.",
        "constraints": {
            "overwrite": bool(overwrite),
        },
        "requested_action": "FS_MOVE",
        "inputs": [{"ref": "file:src_path", "value": src_path}],
        "expected_outputs": [
            {"ref": "file:dst_path", "value": dst_path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual move if policy allows."""
        use_overwrite = bool(_args.get("overwrite", False))

        # H7 (D-019): Re-resolve and reject symlinks post-approval (TOCTOU).
        src_resolved = src.resolve(strict=False)
        if src.exists() and src.is_symlink():
            return {
                "move_error": {"code": "RC-FS-SYMLINK-DENIED", "detail": {"path": str(src), "resolved": str(src_resolved)}},
                "move_result": None,
            }
        approved_src = rec.get("normalized_args", {}).get("canonical_src_path", "")
        if approved_src and str(src_resolved) != approved_src:
            return {
                "move_error": {"code": "RC-FS-PATH-CHANGED", "detail": {"expected": approved_src, "actual": str(src_resolved)}},
                "move_result": None,
            }
        dst_resolved = dst.resolve(strict=False)
        if dst.exists() and dst.is_symlink():
            return {
                "move_error": {"code": "RC-FS-SYMLINK-DENIED", "detail": {"path": str(dst), "resolved": str(dst_resolved)}},
                "move_result": None,
            }
        approved_dst = rec.get("normalized_args", {}).get("canonical_dst_path", "")
        if approved_dst and str(dst_resolved) != approved_dst:
            return {
                "move_error": {"code": "RC-FS-PATH-CHANGED", "detail": {"expected": approved_dst, "actual": str(dst_resolved)}},
                "move_result": None,
            }

        src_canon = src_resolved
        dst_canon = dst_resolved

        if not src_canon.exists():
            return {
                "move_error": {"code": "E-SRC-NOT-FOUND", "detail": {"src_path": str(src_canon)}},
                "move_result": None,
            }

        if dst_canon.exists() and not use_overwrite:
            return {
                "move_error": {"code": "E-DST-EXISTS", "detail": {"dst_path": str(dst_canon)}},
                "move_result": None,
            }

        try:
            shutil.move(str(src_canon), str(dst_canon))
        except Exception as e:
            return {
                "move_error": {"code": "E-MOVE-FAILED", "detail": {"error": str(e)}},
                "move_result": None,
            }

        return {
            "move_result": {
                "canonical_src_path": str(src_canon),
                "canonical_dst_path": str(dst_canon),
                "overwrite": use_overwrite,
            }
        }

    return governed_tool("FS_MOVE", args, intent, _action)


@mcp.tool()
def fs_delete(path: str, recursive: bool = False) -> Dict[str, Any]:
    """
    Governed file/directory deletion.
    recursive=True required for directory trees; denied by default (caps.recursive_allowed=false).
    """
    target = Path(path)
    if not target.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            "decision_record": None,
        }

    args = {
        "path": path,
        "recursive": bool(recursive),
    }

    intent = {
        "goal": "Delete file or directory via MCP fs_delete tool.",
        "constraints": {
            "recursive": bool(recursive),
        },
        "requested_action": "FS_DELETE",
        "inputs": [{"ref": "file:path", "value": path}],
        "expected_outputs": [
            {"ref": "file:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual deletion if policy allows."""
        use_recursive = bool(_args.get("recursive", False))

        # H7 (D-019): Re-resolve and reject symlinks post-approval (TOCTOU).
        resolved = target.resolve(strict=False)
        if target.exists() and target.is_symlink():
            return {
                "delete_error": {"code": "RC-FS-SYMLINK-DENIED", "detail": {"path": str(target), "resolved": str(resolved)}},
                "delete_result": None,
            }
        approved_canonical = rec.get("normalized_args", {}).get("canonical_path", "")
        if approved_canonical and str(resolved) != approved_canonical:
            return {
                "delete_error": {"code": "RC-FS-PATH-CHANGED", "detail": {"expected": approved_canonical, "actual": str(resolved)}},
                "delete_result": None,
            }

        canon = resolved
        if not canon.exists():
            return {
                "delete_error": {"code": "E-TARGET-NOT-FOUND", "detail": {"canonical_path": str(canon)}},
                "delete_result": None,
            }

        try:
            if use_recursive:
                shutil.rmtree(str(canon))
            else:
                os.remove(str(canon))
        except Exception as e:
            return {
                "delete_error": {"code": "E-DELETE-FAILED", "detail": {"error": str(e)}},
                "delete_result": None,
            }

        return {
            "delete_result": {
                "canonical_path": str(canon),
                "recursive": use_recursive,
            }
        }

    return governed_tool("FS_DELETE", args, intent, _action)


def _messaging_proxy_root() -> Path:
    return REPO / "out" / "messaging_proxy"


def _load_messaging_binding(surface_binding_id: str) -> Dict[str, Any]:
    _, mapping_doc, _ = load_messaging_map()
    entry = find_mapping_entry(mapping_doc, surface_binding_id)
    if entry is None:
        raise RuntimeError("MSG_SURFACE_BINDING_UNKNOWN")
    return entry


def _write_messaging_forward_receipt(
    out_dir: Path,
    rec: Dict[str, Any],
    args: Dict[str, Any],
    binding: Dict[str, Any],
    payload_sha256: str,
    expected_len: int,
) -> Path:
    receipt_path = out_dir / FORWARD_RECEIPT_FILENAME
    receipt = {
        "receipt_version": FORWARD_RECEIPT_VERSION,
        "artifact_role": "post_allow_forwarding_receipt",
        "record_hash": rec.get("record_hash"),
        "request_id": rec.get("request_id"),
        "tool": rec.get("tool"),
        "surface_binding_id": args["surface_binding_id"],
        "provider": binding.get("provider"),
        "external_operation": binding.get("external_operation"),
        "canonical_destination": args["canonical_destination"],
        "payload_handle": args["opaque_payload"]["payload_handle"],
        "payload_transport": args["opaque_payload"]["transport"],
        "payload_byte_length": expected_len,
        "payload_sha256": payload_sha256,
        "binding_strength_note": (
            "payload digest lives only in post-ALLOW forwarding receipt; "
            "evaluator-facing structures remain payload-blind"
        ),
    }
    _write_json(receipt_path, receipt)
    return receipt_path


def _forward_message(rec: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    binding = _load_messaging_binding(str(args["surface_binding_id"]))
    payload = args["opaque_payload"]
    handle = str(payload["payload_handle"])
    try:
        payload_path = resolve_repo_relative_payload_handle(handle, REPO)
        data = payload_path.read_bytes()
    except Exception as exc:
        return {
            "message_forward_error": {
                "code": "E-MSG-PAYLOAD-HANDLE-UNREADABLE",
                "detail": {"handle": handle, "error": str(exc)},
            }
        }
    expected_len = int(payload["byte_length"])
    if len(data) != expected_len:
        return {
            "message_forward_error": {
                "code": "E-MSG-PAYLOAD-LENGTH-MISMATCH",
                "detail": {
                    "expected_byte_length": expected_len,
                    "actual_byte_length": len(data),
                },
            }
        }

    out_dir = _messaging_proxy_root() / str(rec.get("request_id"))
    out_dir.mkdir(parents=True, exist_ok=True)
    payload_out = out_dir / "payload.bin"
    meta_out = out_dir / "forward_request.json"
    payload_out.write_bytes(data)
    payload_sha256 = sha256_prefixed_bytes(data)
    metadata = {
        "record_hash": rec.get("record_hash"),
        "tool": rec.get("tool"),
        "surface_binding_id": args["surface_binding_id"],
        "provider": binding.get("provider"),
        "external_operation": binding.get("external_operation"),
        "canonical_destination": args["canonical_destination"],
        "payload_handle": handle,
        "payload_transport": payload.get("transport"),
        "payload_byte_length": expected_len,
        "forward_receipt_version": FORWARD_RECEIPT_VERSION,
        "forward_receipt_binding_note": (
            "payload digest is recorded only in the post-ALLOW forwarding receipt; "
            "payload bytes and payload hash do not enter evaluator-facing structures"
        ),
    }
    _write_json(meta_out, metadata)
    receipt_out = _write_messaging_forward_receipt(
        out_dir,
        rec,
        args,
        binding,
        payload_sha256,
        expected_len,
    )
    return {
        "message_forward_result": {
            "provider": binding.get("provider"),
            "external_operation": binding.get("external_operation"),
            "surface_binding_id": args["surface_binding_id"],
            "canonical_destination": args["canonical_destination"],
            "payload_bytes_forwarded": expected_len,
            "forwarded_outbox_path": str(meta_out),
            "forward_receipt_path": str(receipt_out),
            "provider_evidence": {
                "artifact_role": "post_allow_forwarding_receipt",
                "receipt_version": FORWARD_RECEIPT_VERSION,
                "record_hash": rec.get("record_hash"),
                "payload_handle": handle,
                "payload_transport": payload.get("transport"),
                "payload_byte_length": expected_len,
                "payload_sha256": payload_sha256,
                "binding_strength_note": (
                    "provider-evidence remains local post-ALLOW forwarding evidence; "
                    "it is not provider-confirmed delivery"
                ),
            },
        }
    }


@mcp.tool()
def msg_send(
    surface_binding_id: str,
    mapping_version: str,
    canonical_destination_kind: str,
    canonical_destination_id: str,
    raw_destination_kind: str,
    raw_destination_value: str,
    payload_handle: str,
    payload_byte_length: int,
    transport: str = "opaque_file_handle.v1",
    intent_goal: str = "Send governed message via messaging proof surface.",
    intent_label: str = "",
    justification_ref: str = "",
    rate_window_count: int = 0,
) -> Dict[str, Any]:
    args = {
        "surface_binding_id": surface_binding_id,
        "mapping_version": mapping_version,
        "canonical_destination": {
            "kind": canonical_destination_kind,
            "id": canonical_destination_id,
        },
        "raw_destination_input": {
            "kind": raw_destination_kind,
            "value": raw_destination_value,
        },
        "opaque_payload": {
            "payload_handle": payload_handle,
            "byte_length": int(payload_byte_length),
            "transport": transport,
        },
        "audit_scope": {
            "intent_label": intent_label,
            "justification_ref": justification_ref,
            "rate_window_count": int(rate_window_count),
        },
    }
    intent = {
        "goal": intent_goal,
        "constraints": {
            "content_visible_to_evaluator": False,
            "forwarding_evidence_binding": (
                "payload digest captured only in post-ALLOW forwarding receipt"
            ),
        },
        "requested_action": "MSG_SEND",
        "inputs": [
            {"ref": "message:destination", "value": canonical_destination_id},
            {"ref": "message:opaque_payload_handle", "value": payload_handle},
        ],
        "expected_outputs": [
            {"ref": "message:forward_result", "value": canonical_destination_id},
        ],
    }
    return governed_tool("MSG_SEND", args, intent, lambda rec, norm_args: _forward_message(rec, norm_args))


@mcp.tool()
def msg_reply(
    surface_binding_id: str,
    mapping_version: str,
    canonical_destination_kind: str,
    canonical_destination_id: str,
    raw_destination_kind: str,
    raw_destination_value: str,
    reply_target_kind: str,
    reply_target_id: str,
    payload_handle: str,
    payload_byte_length: int,
    transport: str = "opaque_file_handle.v1",
    intent_goal: str = "Reply via governed messaging proof surface.",
    intent_label: str = "",
    justification_ref: str = "",
    rate_window_count: int = 0,
) -> Dict[str, Any]:
    args = {
        "surface_binding_id": surface_binding_id,
        "mapping_version": mapping_version,
        "canonical_destination": {
            "kind": canonical_destination_kind,
            "id": canonical_destination_id,
        },
        "raw_destination_input": {
            "kind": raw_destination_kind,
            "value": raw_destination_value,
        },
        "opaque_payload": {
            "payload_handle": payload_handle,
            "byte_length": int(payload_byte_length),
            "transport": transport,
        },
        "reply_context": {
            "reply_target_kind": reply_target_kind,
            "reply_target_id": reply_target_id,
        },
        "audit_scope": {
            "intent_label": intent_label,
            "justification_ref": justification_ref,
            "rate_window_count": int(rate_window_count),
        },
    }
    intent = {
        "goal": intent_goal,
        "constraints": {
            "content_visible_to_evaluator": False,
            "forwarding_evidence_binding": (
                "payload digest captured only in post-ALLOW forwarding receipt"
            ),
        },
        "requested_action": "MSG_REPLY",
        "inputs": [
            {"ref": "message:reply_target", "value": reply_target_id},
            {"ref": "message:opaque_payload_handle", "value": payload_handle},
        ],
        "expected_outputs": [
            {"ref": "message:forward_result", "value": canonical_destination_id},
        ],
    }
    return governed_tool("MSG_REPLY", args, intent, lambda rec, norm_args: _forward_message(rec, norm_args))


@mcp.tool()
def capabilities_admissibility_check(
    name: str, params: Dict[str, Any], policy_context: str = "DEFAULT"
) -> Dict[str, Any]:
    """Evaluate action admissibility without executing side effects."""
    mod = _cap_registry().get(str(name or "").strip())
    if mod is None:
        result = {
            "action_name": str(name or ""),
            "admissible": False,
            "reason_token": "CAPABILITY_UNKNOWN",
            "normalized_params": {},
            "policy_context_used": str(policy_context or "DEFAULT").strip().upper() or "DEFAULT",
        }
    else:
        result = mod.admissibility_check(
            CAP_REGISTRY_PATH,
            REPO,
            params,
            policy_context=policy_context,
        )
    return {
        "capabilities_version": "v0",
        "action_name": str(result.get("action_name", name)),
        "admissible": bool(result.get("admissible", False)),
        "reason_token": str(result.get("reason_token", "UNKNOWN")),
        "normalized_params": result.get("normalized_params", {}),
        "policy_context_used": str(result.get("policy_context_used", "DEFAULT")),
    }


@mcp.tool()
def capabilities_execute(name: str, params: Dict[str, Any], mode: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Governed execution endpoint for capability actions."""
    mode = mode or {}
    require_admissible = bool(mode.get("require_admissible", True))
    dry_run = bool(mode.get("dry_run", False))
    run_id = str(mode.get("run_id", "default"))
    attested = bool(mode.get("attested", False))
    sign_receipt = bool(mode.get("sign_receipt", False)) or attested
    signing_key = str(mode.get("signing_key", ""))
    emit_replay_artifact = bool(mode.get("emit_replay_artifact", False))
    replay_policy_context = str(mode.get("replay_policy_context", "DEFAULT"))
    attestation_out_dir = str(mode.get("attestation_out_dir", f"out/mcp_attestation/{run_id}"))
    attestation_out_dir = attestation_out_dir.strip().replace("\\", "/")

    if attested and not signing_key:
        return {
            "capabilities_version": "v0",
            "action_name": str(name),
            "executed": False,
            "admissible": False,
            "reason_token": "SIGNING_KEY_MISSING",
            "receipt": {"run_id": run_id, "digest": ""},
            "signature": {"present": False, "valid": False, "reason_token": "SIGNING_KEY_MISSING"},
            "attestation_bundle": {"present": False, "bundle_dir": "", "verified": False, "reason_token": "NONE"},
        }
    if attested and (not attestation_out_dir.startswith("out/") or ".." in attestation_out_dir.split("/")):
        return {
            "capabilities_version": "v0",
            "action_name": str(name),
            "executed": False,
            "admissible": False,
            "reason_token": "EXPORT_FAILED",
            "receipt": {"run_id": run_id, "digest": ""},
            "signature": {"present": False, "valid": False, "reason_token": "NONE"},
            "attestation_bundle": {"present": False, "bundle_dir": "", "verified": False, "reason_token": "EXPORT_FAILED"},
        }
    if emit_replay_artifact:
        # Fail-closed only on policy-context validity; this does not execute.
        replay_probe = capabilities_admissibility_check(str(name), params, policy_context=replay_policy_context)
        if str(replay_probe.get("reason_token", "NONE")) == "POLICY_CONTEXT_UNKNOWN":
            response = {
                "capabilities_version": "v0",
                "action_name": str(name),
                "executed": False,
                "admissible": False,
                "reason_token": "POLICY_CONTEXT_UNKNOWN",
                "replay_artifact": {
                    "present": False,
                    "policy_context_used": str(replay_probe.get("policy_context_used", "DEFAULT")),
                    "reason_token": "POLICY_CONTEXT_UNKNOWN",
                },
            }
            if attested:
                response["receipt"] = {"run_id": run_id, "digest": ""}
                response["signature"] = {"present": False, "valid": False, "reason_token": "NONE"}
                response["attestation_bundle"] = {
                    "present": False,
                    "bundle_dir": "",
                    "verified": False,
                    "reason_token": "NONE",
                }
            return response

    mod = _cap_registry().get(str(name or "").strip())
    if mod is None:
        result = {
            "executed": False,
            "action_name": str(name),
            "admissible": False,
            "reason_token": "CAPABILITY_UNKNOWN",
            "normalized_params": {},
        }
    else:
        result = mod.execute(CAP_REGISTRY_PATH, REPO, params, dry_run=dry_run, run_id=run_id)
    if require_admissible and not bool(result.get("admissible", False)):
        result["executed"] = False
    if bool(result.get("executed", False)):
        outcome = "EXECUTED"
    elif bool(result.get("admissible", False)):
        outcome = "FAILED"
    else:
        outcome = "BLOCKED"
    digest = None
    should_sign_receipt = sign_receipt and bool(result.get("executed", False))
    linked_tool_event_digests: list[str] = []
    ingest_payload = result.get("ingest_result", {})
    if isinstance(ingest_payload, dict):
        one = str(ingest_payload.get("tool_event_sha256", "")).strip()
        if one:
            linked_tool_event_digests.append(one)
        many = ingest_payload.get("tool_event_digests", [])
        if isinstance(many, list):
            linked_tool_event_digests.extend([str(v).strip() for v in many if str(v).strip()])
    try:
        digest_result = emit_action_record(
            REPO,
            run_id,
            str(result.get("action_name", name)),
            result.get("normalized_params", {}),
            outcome,
            str(result.get("reason_token", "UNKNOWN")),
            {"executed": bool(result.get("executed", False)), "admissible": bool(result.get("admissible", False))},
            sign_receipt=should_sign_receipt,
            signing_key_input=signing_key,
            tool_event_digests=linked_tool_event_digests,
        )
        digest = digest_result["digest"]
        upsert_receipt_tool_event_links(REPO, run_id, linked_tool_event_digests)
    except ValueError:
        result["reason_token"] = "SIGNING_KEY_MISSING" if sign_receipt and not signing_key else "INVALID_RUN_ID"
        result["executed"] = False
        result["admissible"] = False
        digest_result = {"signature_present": "false", "signature_valid": "false"}

    bundle_present = False
    bundle_verified = False
    bundle_reason = "NONE"
    bundle_dir = ""
    replay_artifact_present = False
    replay_artifact_reason = "NONE"
    replay_context_used = str(replay_policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    if emit_replay_artifact and digest is not None:
        try:
            replay_result = replay_check(
                CAP_REGISTRY_PATH,
                REPO,
                run_id,
                verify_signature=False,
                pubkey="",
                policy_context=replay_policy_context,
                emit_artifact=True,
            )
            replay_artifact_present = bool(
                (REPO / "out" / "mcp_exec" / run_id / "replay_check.v0.json").is_file()
            )
            replay_artifact_reason = str(replay_result.get("reason_token", "NONE"))
            replay_context_used = str(replay_result.get("policy_context_used", replay_context_used))
        except Exception:
            replay_artifact_present = False
            replay_artifact_reason = "REPLAY_ARTIFACT_WRITE_FAILED"

    if attested and bool(result.get("executed", False)):
        if emit_replay_artifact and not replay_artifact_present:
            bundle_reason = "REPLAY_ARTIFACT_MISSING"
        else:
            export = capabilities_export_attestation(
                run_id,
                attestation_out_dir,
                include_signature=True,
                include_replay_check=emit_replay_artifact,
            )
            if not bool(export.get("ok", False)):
                bundle_reason = str(export.get("reason_token", "EXPORT_FAILED")) or "EXPORT_FAILED"
            else:
                bundle_present = True
                bundle_dir = str(export.get("bundle_dir", ""))
                vproc = subprocess.run(
                    ["python3", str(REPO / "scripts/verify-attestation-bundle.py"), bundle_dir],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if vproc.returncode == 0:
                    bundle_verified = True
                else:
                    bundle_reason = "EXPORT_FAILED"

    response = {
        "capabilities_version": "v0",
        "action_name": str(result.get("action_name", name)),
        "executed": bool(result.get("executed", False)),
        "admissible": bool(result.get("admissible", False)),
        "reason_token": str(result.get("reason_token", "UNKNOWN")),
    }
    if digest is not None:
        response["action_record_digest"] = digest
        response["receipt_ref"] = f"out/mcp_exec/{run_id}/action_record.json"
    if isinstance(result.get("ingest_result"), dict):
        response["ingest_result"] = result.get("ingest_result")
        ingest_action_record_ref = str(result["ingest_result"].get("action_record_ref", ""))
        if ingest_action_record_ref:
            response["receipt_ref"] = ingest_action_record_ref
    if sign_receipt:
        response["signature_present"] = digest_result.get("signature_present", "false") == "true"
        response["signature_valid"] = digest_result.get("signature_valid", "false") == "true"
    if attested:
        sig_reason = "NONE"
        if response["reason_token"] == "SIGNING_KEY_MISSING":
            sig_reason = "SIGNING_KEY_MISSING"
        response["receipt"] = {"run_id": run_id, "digest": digest or ""}
        response["signature"] = {
            "present": bool(response.get("signature_present", False)),
            "valid": bool(response.get("signature_valid", False)),
            "reason_token": sig_reason,
        }
        response["attestation_bundle"] = {
            "present": bundle_present,
            "bundle_dir": bundle_dir,
            "verified": bundle_verified,
            "reason_token": bundle_reason,
        }
        response["bundle_ref"] = bundle_dir if bundle_present else ""
    if emit_replay_artifact:
        response["replay_artifact"] = {
            "present": replay_artifact_present,
            "policy_context_used": replay_context_used,
            "reason_token": replay_artifact_reason,
        }
    return response


@mcp.tool()
def capabilities_receipt(run_id: str, verify_signature: bool = False, pubkey: str = "") -> Dict[str, Any]:
    """Retrieve a deterministic receipt by run_id with digest validation."""
    try:
        return load_receipt(REPO, run_id, verify_signature=verify_signature, pubkey=pubkey)
    except ValueError:
        return {
            "receipt_version": "v0",
            "run_id": run_id,
            "digest": "",
            "action_record": {},
            "tool_event_digests": [],
            "linked_tool_event_count": 0,
            "digest_valid": False,
            "reason_token": "RECEIPT_NOT_FOUND",
            "signature_present": False,
            "signature_valid": False,
            "signature_reason_token": "NONE",
            "storage_contract": describe_storage_contract(REPO),
            "inspectability_contract": describe_inspectability_contract(
                "capabilities.receipt", "constitutive"
            ),
        }


@mcp.tool()
def capabilities_list_recent(limit: int = 10) -> Dict[str, Any]:
    """List recent receipts deterministically by lexical run_id order."""
    return list_recent_receipts(REPO, limit)


@mcp.tool()
def capabilities_replay_check(
    run_id: str,
    verify_signature: bool = False,
    pubkey: str = "",
    policy_context: str = "DEFAULT",
    emit_artifact: bool = False,
) -> Dict[str, Any]:
    """Re-evaluate admissibility from stored receipt without executing."""
    try:
        return replay_check(
            CAP_REGISTRY_PATH,
            REPO,
            run_id,
            verify_signature=verify_signature,
            pubkey=pubkey,
            policy_context=policy_context,
            emit_artifact=emit_artifact,
        )
    except ValueError:
        return {
            "replay_version": "v0",
            "run_id": run_id,
            "digest": "",
            "digest_valid": False,
            "admissible_now": False,
            "reason_token": "RECEIPT_NOT_FOUND",
            "action_name": "",
            "normalized_params": {},
            "signature_present": False,
            "signature_valid": False,
            "signature_reason_token": "NONE",
            "tool_event_digests": [],
            "linked_tool_event_count": 0,
            "policy_context_used": str(policy_context or "DEFAULT").strip().upper() or "DEFAULT",
            "storage_contract": describe_storage_contract(REPO),
            "inspectability_contract": describe_inspectability_contract(
                "capabilities.replay_check", "constitutive"
            ),
        }


@mcp.tool()
def capabilities_tool_register(action: Dict[str, Any]) -> Dict[str, Any]:
    mod = _tool_catalog_module()
    result = mod.execute(CAP_REGISTRY_PATH, REPO, dict(action), dry_run=False)
    payload = dict(result.get("result", {})) if isinstance(result.get("result"), dict) else {}
    return {
        "executed": bool(result.get("executed", False)),
        "admissible": bool(result.get("admissible", False)),
        "reason_token": str(result.get("reason_token", "NONE")),
        "tool_id": str(payload.get("tool_id", "")),
        "schema_sha256": str(payload.get("schema_sha256", "")),
    }


@mcp.tool()
def capabilities_tool_get(tool_id: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    mod = _tool_catalog_module()
    return mod.query_get(REPO, str(tool_id), policy_context=policy_context)


@mcp.tool()
def capabilities_tool_list_recent(limit: int = 10, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    mod = _tool_catalog_module()
    return mod.query_list_recent(REPO, int(limit), policy_context=policy_context)


@mcp.tool()
def capabilities_tool_catalog_list_slice(
    created_from: str = "any",
    capability: str = "",
    limit: Any = 25,
    policy_context: str = "DEFAULT",
) -> Dict[str, Any]:
    mod = _tool_catalog_module()
    return mod.query_list_slice(
        REPO,
        created_from=str(created_from),
        capability=str(capability),
        limit=limit,
        policy_context=policy_context,
    )


@mcp.tool()
def capabilities_tool_catalog_summarize_slice(
    created_from: str = "any",
    capability: str = "",
    limit: Any = 25,
    policy_context: str = "DEFAULT",
) -> Dict[str, Any]:
    mod = _tool_catalog_module()
    return mod.query_summarize_slice(
        REPO,
        created_from=str(created_from),
        capability=str(capability),
        limit=limit,
        policy_context=policy_context,
    )


def _canonical_json_bytes(value: Dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_prefixed(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


@mcp.tool()
def capabilities_tool_event_get(digest: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    row = get_tool_event_by_digest(REPO, str(digest))
    if row is None:
        return {
            "tool_event_version": "v0",
            "ok": False,
            "reason_token": "TOOL_EVENT_NOT_FOUND",
            "tool_event_digest": str(digest),
            "tool_event_payload_sha256": "",
            "stored_at": 0,
            "policy_context_used": used_context,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }
    return {
        "tool_event_version": "v0",
        "ok": True,
        "reason_token": "NONE",
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
        **build_tool_event_row_payload(row),
    }


@mcp.tool()
def capabilities_tool_catalog_export_bundle(
    tool_ids: Optional[list[str]] = None,
    sign: bool = False,
    private_key_ref: str = "",
    policy_context: str = "DEFAULT",
) -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    selected_ids = [str(v).strip() for v in (tool_ids or []) if str(v).strip()]
    bundle_root = _tool_catalog_bundle_store_root()
    pending_dir = bundle_root / f"_pending_{uuid.uuid4().hex}"
    pending_rel = str(pending_dir.relative_to(REPO)).replace("\\", "/")
    cmd = [
        "python3",
        str(REPO / "scripts/attest/export_tool_catalog_bundle.py"),
        "--out-dir",
        pending_rel,
        "--sign",
        "1" if sign else "0",
    ]
    for tool_id in selected_ids:
        cmd.extend(["--tool-id", tool_id])
    if sign:
        cmd.extend(["--private-key", str(private_key_ref or "")])
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    machine = _parse_machine_line("TOOL_CATALOG_BUNDLE_EXPORT ", combined)
    ok = proc.returncode == 0 and machine.get("ok") == "yes" and machine.get("reason") == "OK"
    if not ok:
        shutil.rmtree(pending_dir, ignore_errors=True)
        return {
            "tool_catalog_bundle_version": "v0",
            "ok": False,
            "reason": str(machine.get("reason", "EXPORT_FAILED") or "EXPORT_FAILED"),
            "bundle_id": "",
            "manifest_sha256": "",
            "signature_present": "no",
            "policy_context_used": used_context,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }
    bundle_id = str(machine.get("bundle_id", "")).strip()
    final_dir = bundle_root / bundle_id
    if final_dir.exists():
        shutil.rmtree(final_dir)
    pending_dir.rename(final_dir)
    return {
        "tool_catalog_bundle_version": "v0",
        "ok": True,
        "reason": "OK",
        "bundle_id": bundle_id,
        "manifest_sha256": str(machine.get("manifest_sha256", "")),
        "signature_present": str(machine.get("signature_present", "no")),
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


@mcp.tool()
def capabilities_tool_catalog_verify_bundle(
    bundle_id: str,
    require_signature: bool = False,
    pubkey: str = "",
    policy_context: str = "DEFAULT",
) -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    key = str(bundle_id or "").strip()
    bundle_dir = _tool_catalog_bundle_store_root() / key
    cmd = [
        "python3",
        str(REPO / "scripts/attest/verify_tool_catalog_bundle.py"),
        "--bundle-dir",
        str(bundle_dir),
        "--require-signature",
        "1" if require_signature else "0",
    ]
    if require_signature:
        cmd.extend(["--pubkey", str(pubkey or "")])
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False)
    combined = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    machine = _parse_machine_line("TOOL_CATALOG_BUNDLE_VERIFY ", combined)
    reason = str(machine.get("reason", "VERIFY_FAILED") or "VERIFY_FAILED")
    ok = proc.returncode == 0 and machine.get("ok") == "yes" and reason == "OK"
    return {
        "tool_catalog_bundle_verify_version": "v0",
        "ok": bool(ok),
        "reason": reason,
        "bundle_id": key,
        "manifest_sha256": str(machine.get("manifest_sha256", "")),
        "signature_verified": str(machine.get("signature_verified", "not_required")),
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


@mcp.tool()
def capabilities_tool_event_list_recent(limit: int = 10, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    rows = list_tool_events_recent(REPO, int(limit))
    return build_tool_event_list_recent_payload(REPO, rows, used_context)


@mcp.tool()
def capabilities_tool_event_list_for_receipt(receipt_id: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    return build_tool_event_list_for_receipt_payload(REPO, str(receipt_id), used_context)


@mcp.tool()
def capabilities_tool_event_export(
    digest: str = "",
    receipt_id: str = "",
    limit: int = 10,
    policy_context: str = "DEFAULT",
) -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    digest = str(digest or "").strip()
    receipt_id = str(receipt_id or "").strip()
    if bool(digest) == bool(receipt_id):
        return {
            "tool_event_bundle_version": "v0",
            "ok": False,
            "reason_token": "PROVIDE_DIGEST_OR_RECEIPT_ID",
            "bundle_id": "",
            "manifest_sha256": "",
            "tool_event_digests_count": 0,
            "policy_context_used": used_context,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }

    rows = list_all_tool_events(REPO)
    if digest:
        selected = [r for r in rows if str(r.get("tool_event_digest", "")) == digest]
    else:
        selected = [r for r in rows if str(r.get("receipt_id", "")) == receipt_id]
        selected = selected[: max(1, min(int(limit), 100))]
    selected = sorted(selected, key=lambda r: (str(r.get("tool_event_digest", "")), str(r.get("run_id", ""))))
    if not selected:
        return {
            "tool_event_bundle_version": "v0",
            "ok": False,
            "reason_token": "TOOL_EVENT_NOT_FOUND",
            "bundle_id": "",
            "manifest_sha256": "",
            "tool_event_digests_count": 0,
            "policy_context_used": used_context,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }

    files_map: Dict[str, Dict[str, Any]] = {}
    digests: list[str] = []
    payload_blobs: Dict[str, bytes] = {}
    for row in selected:
        item_digest = str(row.get("tool_event_digest", ""))
        rel_ref = str(row.get("tool_event_ref", ""))
        src = REPO / rel_ref
        if not src.is_file():
            return {
                "tool_event_bundle_version": "v0",
                "ok": False,
                "reason_token": "TOOL_EVENT_PAYLOAD_MISSING",
                "bundle_id": "",
                "manifest_sha256": "",
                "tool_event_digests_count": 0,
                "policy_context_used": used_context,
                "POLICY_BYPASS": "READ_ONLY_QUERY",
            }
        body = src.read_bytes()
        if _sha256_prefixed(body) != item_digest:
            return {
                "tool_event_bundle_version": "v0",
                "ok": False,
                "reason_token": "TOOL_EVENT_DIGEST_MISMATCH",
                "bundle_id": "",
                "manifest_sha256": "",
                "tool_event_digests_count": 0,
                "policy_context_used": used_context,
                "POLICY_BYPASS": "READ_ONLY_QUERY",
            }
        rel_name = item_digest.replace(":", "_") + ".json"
        rel_path = f"payload/{rel_name}"
        payload_blobs[rel_path] = body
        files_map[rel_path] = {"sha256": _sha256_prefixed(body), "size_bytes": len(body)}
        digests.append(item_digest)

    manifest = {
        "bundle_version": "tool_event_bundle_v0",
        "tool_event_digests": sorted(digests),
        "files": {k: files_map[k] for k in sorted(files_map)},
    }
    manifest_bytes = _canonical_json_bytes(manifest)
    manifest_sha = _sha256_prefixed(manifest_bytes)
    bundle_id = "teb_" + manifest_sha.split(":", 1)[1]

    bundle_root = tool_event_bundle_store_root(REPO) / bundle_id
    payload_dir = bundle_root / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)
    for rel_path in sorted(payload_blobs):
        (bundle_root / rel_path).write_bytes(payload_blobs[rel_path])
    (bundle_root / "tool_event_bundle.manifest.json").write_bytes(manifest_bytes)

    bundle_ref = str(Path("runtime") / "TOOL_EVENTS" / "BUNDLES" / bundle_id).replace("\\", "/")
    upsert_tool_event_bundle(
        REPO,
        bundle_id=bundle_id,
        manifest_sha256=manifest_sha,
        tool_event_digests_count=len(manifest["tool_event_digests"]),
        bundle_ref=bundle_ref,
    )
    return {
        "tool_event_bundle_version": "v0",
        "ok": True,
        "reason_token": "NONE",
        "bundle_id": bundle_id,
        "manifest_sha256": manifest_sha,
        "tool_event_digests_count": len(manifest["tool_event_digests"]),
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


@mcp.tool()
def capabilities_tool_event_bundle_verify(bundle_id: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    key = str(bundle_id or "").strip()
    if not key:
        return {
            "tool_event_bundle_verify_version": "v0",
            "ok": False,
            "reason": "MANIFEST_INVALID",
            "manifest_sha256": "",
            "policy_context_used": used_context,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }
    entry = get_tool_event_bundle(REPO, key)
    if entry is None:
        return {
            "tool_event_bundle_verify_version": "v0",
            "ok": False,
            "reason": "MISSING_FILE",
            "manifest_sha256": "",
            "policy_context_used": used_context,
            "POLICY_BYPASS": "READ_ONLY_QUERY",
        }

    bundle_dir = tool_event_bundle_store_root(REPO) / key
    proc = subprocess.run(
        [
            "python3",
            str(REPO / "scripts/attest/verify_tool_event_bundle.py"),
            "--bundle-dir",
            str(bundle_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    reason = "OTHER"
    out = proc.stdout.strip()
    for line in out.splitlines():
        if line.startswith("TOOL_EVENT_BUNDLE_VERIFY "):
            for part in line.split():
                if part.startswith("reason="):
                    reason = part.split("=", 1)[1]
                    break
    ok = proc.returncode == 0 and reason == "OK"
    return {
        "tool_event_bundle_verify_version": "v0",
        "ok": bool(ok),
        "reason": reason,
        "manifest_sha256": str(entry.get("manifest_sha256", "")),
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


@mcp.tool()
def capabilities_receipt_tool_events(receipt_id: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    rid = str(receipt_id or "").strip()
    digests = get_tool_events_for_receipt(REPO, rid)
    return build_receipt_tool_events_payload(REPO, rid, digests, used_context)


@mcp.tool()
def capabilities_tool_event_receipts(digest: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    token = str(digest or "").strip()
    receipt_ids = get_receipts_for_tool_event(REPO, token)
    return build_tool_event_receipts_payload(REPO, token, receipt_ids, used_context)


@mcp.tool()
def capabilities_export_attestation(
    run_id: str,
    out_dir: str,
    include_signature: bool = True,
    include_replay_check: bool = False,
) -> Dict[str, Any]:
    """Export a deterministic receipt attestation bundle under out/."""
    out_rel = out_dir.strip().replace("\\", "/")
    if not out_rel.startswith("out/") or ".." in out_rel.split("/"):
        return {"ok": False, "reason_token": "OUT_DIR_INVALID", "bundle_dir": ""}

    cmd = [
        "python3",
        str(REPO / "scripts/attest/export_receipt_bundle.py"),
        "--receipt-run-id",
        run_id,
        "--out-dir",
        out_rel,
        "--include-signature",
        "1" if include_signature else "0",
        "--include-replay-check",
        "1" if include_replay_check else "0",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        out = (proc.stdout + "\n" + proc.stderr).strip()
        token = "EXPORT_FAILED"
        for line in out.splitlines():
            if line.startswith("FAIL:"):
                token = line.replace("FAIL:", "", 1).strip().replace(" ", "_")
                break
        return {"ok": False, "reason_token": token or "EXPORT_FAILED", "bundle_dir": ""}
    return {"ok": True, "reason_token": "NONE", "bundle_dir": out_rel}


# ---------------------------------------------------------------------------
# Audit Query Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def audit_query(
    start_time: str = "",
    end_time: str = "",
    user_identity: str = "",
    tool_name: str = "",
    policy_decision: str = "",
    event_category: str = "",
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """Query the governance chain for audit purposes.

    Filter by time range (ISO-8601), user identity, tool name,
    policy decision (ALLOW/DENY), or event category.
    Returns matching entries in reverse chronological order.
    """
    return _audit_query(
        CHAIN,
        RECORDS_DIR,
        start_time=str(start_time).strip() or None,
        end_time=str(end_time).strip() or None,
        user_identity=str(user_identity).strip() or None,
        tool_name=str(tool_name).strip() or None,
        policy_decision=str(policy_decision).strip() or None,
        event_category=str(event_category).strip() or None,
        limit=max(int(limit), 1) if limit else 100,
        offset=max(int(offset), 0) if offset else 0,
    )


@mcp.tool()
def audit_record_detail(record_id: str) -> Dict[str, Any]:
    """Retrieve a single governance record in full detail.

    Look up by request_id, event_id, or record_hash. Returns the chain
    record and any matching sidecar record.
    """
    rid = str(record_id).strip()
    if not rid:
        return {"found": False, "record_id": "", "error": "record_id is required"}
    return _audit_record_detail(CHAIN, RECORDS_DIR, record_id=rid)


@mcp.tool()
def audit_report(
    start_time: str = "",
    end_time: str = "",
    group_by: str = "tool",
) -> Dict[str, Any]:
    """Generate an audit summary report over a time period.

    group_by options: "tool", "user", "decision", "category".
    Returns counts grouped by the specified dimension plus a
    decision summary (ALLOW/DENY counts).
    """
    gb = str(group_by).strip() or "tool"
    if gb not in ("tool", "user", "decision", "category"):
        gb = "tool"
    return _audit_report(
        CHAIN,
        RECORDS_DIR,
        start_time=str(start_time).strip() or None,
        end_time=str(end_time).strip() or None,
        group_by=gb,
    )


# ---------------------------------------------------------------------------
# Governance Dashboard Tool
# ---------------------------------------------------------------------------

_DASHBOARD_PROCESS: Optional[subprocess.Popen] = None
_DASHBOARD_PORT: Optional[int] = None
_DASHBOARD_LOCK = threading.Lock()


def _find_free_port(preferred: int = 9700) -> int:
    """Find a free TCP port, preferring the given port."""
    import socket
    for port in (preferred, preferred + 1, preferred + 2):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    # Fallback: let OS assign
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _is_dashboard_alive() -> bool:
    global _DASHBOARD_PROCESS
    if _DASHBOARD_PROCESS is None:
        return False
    return _DASHBOARD_PROCESS.poll() is None


@mcp.tool()
def atested_help(query: str = "", topic: str = "") -> Dict[str, Any]:
    """Return contextual documentation and guidance for Atested governance.

    Accepts a question or topic and returns relevant help content drawn from
    the installed documentation.  Covers: adding directories to scope,
    adjusting constraints, reading the dashboard, activating a license,
    granting scoped approvals, ALLOW/DENY meaning, configuring observation
    hooks, and more.

    Args:
        query: A free-text question (e.g. "how do I add a directory?").
        topic: An optional topic keyword to narrow results.  Valid topics
               include: quickstart, configuration, policy, licensing,
               invariants, threat-model, scope, hooks, approvals,
               governance-overview.
    """
    TOPIC_MAP = {
        "quickstart": "QUICKSTART.md",
        "configuration": "CONFIGURATION.md",
        "config": "CONFIGURATION.md",
        "policy": "POLICY.md",
        "licensing": "LICENSING.md",
        "license": "LICENSING.md",
        "invariants": "INVARIANTS.md",
        "threat-model": "THREAT-MODEL.md",
        "threat": "THREAT-MODEL.md",
        "scope": "SCOPE.md",
        "hooks": "INTEGRATION_HOOKS.md",
        "observation": "INTEGRATION_HOOKS.md",
        "approvals": "RESIDUAL_DISCRETION_DOCTRINE.md",
        "approval": "RESIDUAL_DISCRETION_DOCTRINE.md",
        "governance-overview": "GOVERNANCE_OVERVIEW.md",
        "overview": "GOVERNANCE_OVERVIEW.md",
        "distribution": "DISTRIBUTION.md",
        "introduction": "INTRODUCTION_FOR_EVERYONE.md",
        "intro": "INTRODUCTION_FOR_EVERYONE.md",
    }

    docs_dir = REPO / "docs"
    q = (query or "").strip().lower()
    t = (topic or "").strip().lower()

    # Determine which files to search
    if t and t in TOPIC_MAP:
        target_files = [docs_dir / TOPIC_MAP[t]]
    elif t:
        # Fuzzy match topic
        target_files = [docs_dir / v for k, v in TOPIC_MAP.items() if t in k]
        if not target_files:
            target_files = sorted(docs_dir.glob("*.md"))
    else:
        target_files = sorted(docs_dir.glob("*.md"))

    results = []
    seen = set()
    for fp in target_files:
        if not fp.exists() or fp.name in seen:
            continue
        seen.add(fp.name)
        try:
            text = fp.read_text(encoding="utf-8")
        except OSError:
            continue

        # If there's a query, score relevance by keyword matches
        if q:
            keywords = [w for w in q.split() if len(w) > 2]
            text_lower = text.lower()
            score = sum(1 for kw in keywords if kw in text_lower)
            if score == 0:
                continue
        else:
            score = 1

        # Extract relevant sections (headings + nearby content)
        sections = []
        current_heading = ""
        current_content = []
        for line in text.splitlines():
            if line.startswith("#"):
                if current_heading and current_content:
                    section_text = "\n".join(current_content).strip()
                    if q:
                        if any(kw in section_text.lower() for kw in keywords):
                            sections.append({"heading": current_heading, "content": section_text[:600]})
                    else:
                        sections.append({"heading": current_heading, "content": section_text[:400]})
                current_heading = line.lstrip("#").strip()
                current_content = []
            else:
                current_content.append(line)
        # Last section
        if current_heading and current_content:
            section_text = "\n".join(current_content).strip()
            if q:
                if any(kw in section_text.lower() for kw in keywords):
                    sections.append({"heading": current_heading, "content": section_text[:600]})
            else:
                sections.append({"heading": current_heading, "content": section_text[:400]})

        if sections:
            results.append({
                "file": fp.name,
                "relevance_score": score,
                "sections": sections[:5],
            })

    results.sort(key=lambda x: x["relevance_score"], reverse=True)
    results = results[:5]

    # Record in chain as non-action event
    with _CHAIN_LOCK:
        _verify_chain()
        event = build_non_action_event(
            "help_query",
            {"query": query, "topic": topic, "results_count": len(results)},
            prev_record_hash=_chain_head_record_hash(),
        )
        _append_non_action_event(event)
        _verify_chain()

    return {
        "query": query,
        "topic": topic,
        "results": results,
        "available_topics": sorted(set(TOPIC_MAP.keys())),
    }


@mcp.tool()
def submit_feedback(
    message: str,
    experience_note: str = "",
    permission_to_use: bool = False,
    send_to_remote: bool = False,
) -> Dict[str, Any]:
    """Submit feedback about Atested with a signed artifact.

    Creates a signed feedback artifact and writes it locally.  If
    send_to_remote is True, also transmits the artifact to atested.com
    for the development team.

    Args:
        message: Free-form feedback text.
        experience_note: Optional — "What has Atested helped you avoid or improve?"
        permission_to_use: If True, Atested may use the feedback anonymously in marketing.
        send_to_remote: If True, POST the signed artifact to atested.com/api/feedback.
    """
    from feedback_signing import build_feedback_artifact, write_artifact, send_artifact_to_remote

    artifact = build_feedback_artifact(
        message=message,
        experience_note=experience_note,
        permission_to_use=permission_to_use,
        runtime_root=RUNTIME,
    )

    # Write locally
    feedback_dir = RUNTIME / "LOGS" / "feedback"
    out_path = write_artifact(artifact, feedback_dir)

    # Record in chain
    with _CHAIN_LOCK:
        _verify_chain()
        event = build_non_action_event(
            "feedback_submitted",
            {
                "artifact_id": artifact["artifact_id"],
                "artifact_hash": artifact["artifact_hash"],
                "sent_to_remote": send_to_remote,
            },
            prev_record_hash=_chain_head_record_hash(),
        )
        _append_non_action_event(event)
        _verify_chain()

    result = {
        "artifact_id": artifact["artifact_id"],
        "artifact_hash": artifact["artifact_hash"],
        "signed": artifact.get("signed", False),
        "stored_at": str(out_path),
    }

    if send_to_remote:
        remote_result = send_artifact_to_remote(
            artifact, "https://license.atested.com/api/feedback"
        )
        result["remote"] = remote_result

    return result


@mcp.tool()
def submit_telemetry(send_to_remote: bool = False) -> Dict[str, Any]:
    """Generate and submit a signed telemetry artifact with aggregated usage counts.

    Produces anonymous, aggregated data: total ALLOW/DENY decisions,
    deterministic vs judgment counts.  No user identities, file paths,
    or organization names are included.

    Args:
        send_to_remote: If True, POST the signed artifact to atested.com/api/telemetry.
    """
    from feedback_signing import build_telemetry_artifact, write_artifact, send_artifact_to_remote

    artifact = build_telemetry_artifact(
        chain_path=CHAIN,
        runtime_root=RUNTIME,
    )

    # Write locally
    telemetry_dir = RUNTIME / "LOGS" / "telemetry"
    out_path = write_artifact(artifact, telemetry_dir)

    # Record in chain
    with _CHAIN_LOCK:
        _verify_chain()
        event = build_non_action_event(
            "telemetry_submitted",
            {
                "artifact_id": artifact["artifact_id"],
                "artifact_hash": artifact["artifact_hash"],
                "sent_to_remote": send_to_remote,
                "total_allow": artifact["total_allow"],
                "total_deny": artifact["total_deny"],
            },
            prev_record_hash=_chain_head_record_hash(),
        )
        _append_non_action_event(event)
        _verify_chain()

    result = {
        "artifact_id": artifact["artifact_id"],
        "artifact_hash": artifact["artifact_hash"],
        "signed": artifact.get("signed", False),
        "stored_at": str(out_path),
        "total_allow": artifact["total_allow"],
        "total_deny": artifact["total_deny"],
        "total_deterministic": artifact["total_deterministic"],
        "total_judgment": artifact["total_judgment"],
    }

    if send_to_remote:
        remote_result = send_artifact_to_remote(
            artifact, "https://license.atested.com/api/telemetry"
        )
        result["remote"] = remote_result

    return result


@mcp.tool()
def atested_dashboard() -> Dict[str, Any]:
    """Start the Atested Dashboard and return the URL.

    Launches a local web server serving the dashboard UI. If the
    dashboard is already running, returns the existing URL. The
    operator can open this URL in any browser.
    """
    global _DASHBOARD_PROCESS, _DASHBOARD_PORT

    with _DASHBOARD_LOCK:
        if _is_dashboard_alive() and _DASHBOARD_PORT:
            url = f"http://localhost:{_DASHBOARD_PORT}"
            return {"status": "already_running", "url": url, "port": _DASHBOARD_PORT}

        dashboard_dir = REPO / "dashboard"
        if not dashboard_dir.exists():
            return {"status": "error", "error": "Dashboard directory not found"}

        port = _find_free_port()
        server_script = dashboard_dir / "server.py"
        if not server_script.exists():
            return {"status": "error", "error": "Dashboard server script not found"}

        env = {
            **os.environ,
            "GOV_RUNTIME_DIR": str(RUNTIME),
            "GOV_CANONICAL_REPO_PATH": str(REPO),
            "GOV_RUNTIME_PATH": str(RUNTIME),
            "DASHBOARD_PORT": str(port),
        }

        _DASHBOARD_PROCESS = subprocess.Popen(
            [sys.executable, str(server_script)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _DASHBOARD_PORT = port

        # Brief wait to let the server bind
        import time
        time.sleep(0.5)

        if not _is_dashboard_alive():
            _DASHBOARD_PROCESS = None
            _DASHBOARD_PORT = None
            return {"status": "error", "error": "Dashboard server failed to start"}

        url = f"http://localhost:{port}"
        return {"status": "started", "url": url, "port": port}


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--stdio-test-capabilities-execute":
        raise SystemExit(_run_stdio_capabilities_execute())
    run_local_stdio()
