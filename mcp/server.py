#!/usr/bin/env python3
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
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
from tool_event_store import (
    get_tool_event_bundle,
    get_tool_event_by_digest,
    list_all_tool_events,
    tool_event_bundle_store_root,
    upsert_tool_event_bundle,
    list_tool_events_for_receipt,
    list_tool_events_recent,
)
from tool_event_link_store import upsert_receipt_tool_event_links
from tool_event_link_store import get_receipts_for_tool_event, get_tool_events_for_receipt
from capabilities import build_registry

REPO = Path(__file__).resolve().parents[1]
APPEND = REPO / "scripts" / "append-record-runtime.sh"
CAP_REGISTRY_PATH = REPO / "capabilities" / "capability-registry.json"

VERIFY_CHAIN = REPO / "scripts" / "verify-chain.py"
RUNTIME = Path(os.environ.get("GOV_RUNTIME_DIR", "/Volumes/SSD/archive/gov/runtime")).resolve()
INTENTS_DIR = RUNTIME / "LOGS" / "intents"
RECORDS_DIR = RUNTIME / "LOGS" / "records"
CHAIN = RUNTIME / "LOGS" / "decision-chain.jsonl"

if FastMCP is None:
    class _FallbackMCP:
        def __init__(self, _name: str) -> None:
            pass

        def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
                return fn
            return _decorator

        def run(self) -> None:
            print("MCP_RUNTIME_UNAVAILABLE=YES")
            raise SystemExit(2)

    mcp = _FallbackMCP("governance-broker")
else:
    mcp = FastMCP("governance-broker")


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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")



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
    return str(dst)

def _verify_chain() -> None:
    # Fail closed if the runtime chain is broken.
    if not CHAIN.exists():
        return
    proc = subprocess.run(
        ["python3", str(VERIFY_CHAIN), str(CHAIN)],
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
    req_id = str(uuid.uuid4())

    # Normalize args from capability spec
    norm_args, norm_constraints = normalize_args(tool_name, args)
    if isinstance(norm_constraints, dict) and norm_constraints.get("_missing"):
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-MISSING-INTENT-FIELDS", "detail": {"missing": norm_constraints.get("_missing")}}],
            "decision_record": None,
        }

    intent_obj = {
        "tool": tool_name,
        "args": norm_args,
        "intent": intent,
    }

    INTENTS_DIR.mkdir(parents=True, exist_ok=True)
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    intent_path = INTENTS_DIR / f"{req_id}.intent.json"
    _write_json(intent_path, intent_obj)

    # Verify chain integrity BEFORE appending (fail closed)
    _verify_chain()

    # Append decision record to runtime chain (tamper-evident sequence)
    rec = _append_decision(intent_path)

    # Verify chain integrity AFTER appending (fail closed)
    _verify_chain()

    # Persist a pretty record copy (optional convenience, not part of the chain)
    record_path = RECORDS_DIR / f"{req_id}.record.json"
    _write_json(record_path, rec)

    decision = rec.get("policy_decision")
    if decision != "ALLOW":
        return {
            "policy_decision": decision,
            "policy_reasons": rec.get("policy_reasons", []),
            "decision_record": rec,
        }

    # Execute the action
    action_result = action(rec, norm_args)

    return {
        "policy_decision": "ALLOW",
        "policy_reasons": rec.get("policy_reasons", []),
        "decision_record": rec,
        **action_result
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
            # Phase 1: absolute paths only
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
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
        src_canon = src.resolve()
        dst_canon = dst.resolve()

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
        canon = target.resolve()

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
            "digest_valid": False,
            "reason_token": "RECEIPT_NOT_FOUND",
            "signature_present": False,
            "signature_valid": False,
            "signature_reason_token": "NONE",
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
            "policy_context_used": str(policy_context or "DEFAULT").strip().upper() or "DEFAULT",
        }


def _tool_event_row_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    ref = str(row.get("tool_event_ref", ""))
    payload_digest = str(row.get("tool_event_digest", ""))
    return {
        "tool_event_digest": payload_digest,
        "tool_event_payload_sha256": payload_digest,
        "tool_event_ref": ref,
        "receipt_id": str(row.get("receipt_id", "")),
        "stored_at": int(row.get("stored_seq", 0)),
    }


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
        **_tool_event_row_payload(row),
    }


@mcp.tool()
def capabilities_tool_event_list_recent(limit: int = 10, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    rows = list_tool_events_recent(REPO, int(limit))
    events = [_tool_event_row_payload(r) for r in rows]
    return {
        "tool_event_version": "v0",
        "events": events,
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


@mcp.tool()
def capabilities_tool_event_list_for_receipt(receipt_id: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    rows = list_tool_events_for_receipt(REPO, str(receipt_id))
    events = [_tool_event_row_payload(r) for r in rows]
    return {
        "tool_event_version": "v0",
        "receipt_id": str(receipt_id),
        "events": events,
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


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
    return {
        "tool_event_link_version": "v0",
        "receipt_id": rid,
        "tool_event_digests": digests,
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


@mcp.tool()
def capabilities_tool_event_receipts(digest: str, policy_context: str = "DEFAULT") -> Dict[str, Any]:
    used_context = str(policy_context or "DEFAULT").strip().upper() or "DEFAULT"
    token = str(digest or "").strip()
    receipt_ids = get_receipts_for_tool_event(REPO, token)
    return {
        "tool_event_link_version": "v0",
        "tool_event_digest": token,
        "receipt_ids": receipt_ids,
        "policy_context_used": used_context,
        "POLICY_BYPASS": "READ_ONLY_QUERY",
    }


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


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--stdio-test-capabilities-execute":
        raise SystemExit(_run_stdio_capabilities_execute())
    mcp.run()
