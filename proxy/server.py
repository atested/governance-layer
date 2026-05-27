#!/usr/bin/env python3
"""
server.py — Atested API governance proxy.

An HTTP proxy that sits between an AI agent and its model provider.
Intercepts tool_use/tool_calls blocks from streaming and non-streaming
responses, classifies each operation by evidence inference, evaluates
policy, records decisions in the governance chain, and allows or denies
before execution.

Supports multiple providers: Anthropic, OpenAI, Gemini, LiteLLM.

Usage:
    ANTHROPIC_API_KEY=sk-... python -m proxy.server [--port 8080]

Agent configuration:
    ANTHROPIC_BASE_URL=http://localhost:8080/anthropic
    OPENAI_BASE_URL=http://localhost:8080/openai
    GEMINI_BASE_URL=http://localhost:8080/gemini
    OLLAMA_HOST=http://localhost:8080/ollama
    OLLAMA_HOST=http://localhost:8080/ollama

Architecture:
    Agent → Proxy → Provider API
    Proxy intercepts model responses containing tool calls.
    ALLOW: pass tool call through to agent.
    DENY: replace tool call with denial text, agent never sees tool call.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import logging
import os
import platform
import struct
import sys
import time as _time_mod
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any, Optional

import httpx
import websockets

# Add scripts to path for classifier, policy_eval, etc.
REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from classifier import classify
from canonical_form import canonical_json as _canonical_form_json
from env_compat import read_env_preferred  # QS-039 #14: ATESTED_*/GOV_* fallback
from policy_eval_v2 import evaluate, load_policy_rules, _compute_record_hash, compute_policy_rules_hash
# QS-060 replaces load_approval_store_from_chain with the runtime-aware loader
# that also reads sidecar approval-store files; the proxy now goes through
# that loader at line ~493 (_load_approval_store). The legacy
# from_chain helper is still exported by approval_store for callers that
# already have a chain path in hand.
from approval_store import ApprovalStore, approval_store_hash, load_approval_store_from_runtime
from event_model import (
    build_non_action_event,
    is_non_action_event,
    _compute_event_record_hash,
    sign_non_action_event,
)
from integrity_monitor import IntegrityMonitor, IntegrityViolation
from machine_identity import (
    add_machine_identity_fields,
    add_record_freshness_fields,
    ensure_machine_identity,
    ensure_primary_machine_registry,
)

# Storage contract for chain path
from storage_contract import runtime_root
from receipt_signing import _read_private_key, _public_key_fingerprint, _b64url_nopad

# Import signing_preimage_payload from verify-record.py (hyphenated filename)
import importlib.util as _imputil
_vr_spec = _imputil.spec_from_file_location("verify_record_mod", SCRIPTS / "verify-record.py")
_vr_mod = _imputil.module_from_spec(_vr_spec)
_vr_spec.loader.exec_module(_vr_mod)
signing_preimage_payload = _vr_mod.signing_preimage_payload

# Provider registry
from proxy.providers import resolve_provider, PROVIDER_PREFIXES
from proxy.providers.base import BaseProvider, BaseStreamingCollector, ToolCall, StreamAction
from proxy.qa_gate import QAChainTailReader, ProxyQualityGate

logger = logging.getLogger("atested.proxy")

_WEBSOCKET_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# ---------------------------------------------------------------------------
# Ed25519 signing key (loaded once at startup)
# ---------------------------------------------------------------------------

_SIGNING_KEY = None        # Ed25519PrivateKey or None
_SIGNING_KEY_ID = None     # "ed25519:<sha256hex>" or None
_SIGNING_SERIALIZATION = None  # cryptography.hazmat.primitives.serialization

# Hidden signing key filename (dotfile)
SIGNING_KEY_HIDDEN_NAME = ".atested-signing-key.pem"
# Legacy visible key name for migration fallback
SIGNING_KEY_LEGACY_NAME = "governance-signing.pem"


def _resolve_signing_key_path() -> str:
    """Resolve the signing key path with hidden-path preference and migration.

    Priority:
    1. GOV_SIGNING_KEY_PATH env var (explicit override)
    2. Hidden dotfile in runtime directory (.atested-signing-key.pem)
    3. Legacy visible path in keys/ directory (migration fallback with warning)
    """
    _explicit_key = read_env_preferred("ATESTED_SIGNING_KEY_PATH", "GOV_SIGNING_KEY_PATH")
    if _explicit_key is not None:
        return _explicit_key.strip()

    # Check hidden path in runtime directory
    try:
        runtime = runtime_root(REPO)
    except Exception:
        runtime = None
    if runtime:
        hidden_path = runtime / SIGNING_KEY_HIDDEN_NAME
        if hidden_path.exists():
            return str(hidden_path)

    # Check legacy visible path with migration warning
    legacy_path = REPO / "keys" / SIGNING_KEY_LEGACY_NAME
    if legacy_path.exists():
        logger.warning(
            "Signing key found at legacy visible path %s — "
            "recommend moving to %s for security",
            legacy_path,
            (runtime / SIGNING_KEY_HIDDEN_NAME) if runtime else SIGNING_KEY_HIDDEN_NAME,
        )
        return str(legacy_path)

    return ""


def _load_signing_key():
    """Load Ed25519 private key from resolved signing key path."""
    global _SIGNING_KEY, _SIGNING_KEY_ID, _SIGNING_SERIALIZATION
    key_path = _resolve_signing_key_path()
    if not key_path:
        logger.warning("No signing key found — records will be unsigned")
        return
    try:
        priv, serialization = _read_private_key(Path(key_path))
        _SIGNING_KEY = priv
        _SIGNING_SERIALIZATION = serialization
        _SIGNING_KEY_ID = _public_key_fingerprint(priv.public_key(), serialization)
        logger.info("Ed25519 signing key loaded from %s: %s", key_path, _SIGNING_KEY_ID)
    except Exception as exc:
        logger.warning("Failed to load signing key from %s: %s — records will be unsigned", key_path, exc)

_load_signing_key()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8080
DEFAULT_HOST = "127.0.0.1"
ANTHROPIC_API_BASE = "https://api.anthropic.com"
CAP_REGISTRY_PATH = REPO / "capabilities" / "capability-registry.json"

# Maximum request body size (bytes). Protects against unbounded reads.
# 10 MB — large enough for any legitimate model API request.
MAX_REQUEST_BODY_BYTES = int(os.environ.get("ATESTED_MAX_REQUEST_BODY_BYTES", 10 * 1024 * 1024))
_WEBSOCKET_MAX_FRAME_BYTES = MAX_REQUEST_BODY_BYTES

# QS-061: per-provider upstream timeouts. Cloud APIs answer in well under
# the 120s default, but local Ollama inference on a CPU-only host can take
# minutes for the first token (model load + cold cache). A single 120s
# timeout silently failed those requests with no governed record produced.
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 120.0
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 300.0


def provider_timeout_seconds(
    provider_name: Optional[str],
    provider_config: Optional[dict],
) -> float:
    """Return the httpx timeout (seconds) to use for a given provider.

    Falls back to ``DEFAULT_PROVIDER_TIMEOUT_SECONDS`` when no provider is
    given, when the provider has no override, or when the configured value
    is unparseable. Only Ollama currently has a provider-specific default
    because it is the only upstream that routinely exceeds 120 seconds.
    """
    config = provider_config or {}
    if provider_name == "ollama":
        raw = config.get("ollama_timeout_seconds")
        if raw is None:
            return DEFAULT_OLLAMA_TIMEOUT_SECONDS
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return DEFAULT_OLLAMA_TIMEOUT_SECONDS
        return value if value > 0 else DEFAULT_OLLAMA_TIMEOUT_SECONDS
    return DEFAULT_PROVIDER_TIMEOUT_SECONDS

# QS-061: per-provider upstream timeouts. Cloud APIs answer in well under
# the 120s default, but local Ollama inference on a CPU-only host can take
# minutes for the first token (model load + cold cache). A single 120s
# timeout silently failed those requests with no governed record produced.
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 120.0
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 300.0


def provider_timeout_seconds(
    provider_name: Optional[str],
    provider_config: Optional[dict],
) -> float:
    """Return the httpx timeout (seconds) to use for a given provider.

    Falls back to ``DEFAULT_PROVIDER_TIMEOUT_SECONDS`` when no provider is
    given, when the provider has no override, or when the configured value
    is unparseable. Only Ollama currently has a provider-specific default
    because it is the only upstream that routinely exceeds 120 seconds.
    """
    config = provider_config or {}
    if provider_name == "ollama":
        raw = config.get("ollama_timeout_seconds")
        if raw is None:
            return DEFAULT_OLLAMA_TIMEOUT_SECONDS
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return DEFAULT_OLLAMA_TIMEOUT_SECONDS
        return value if value > 0 else DEFAULT_OLLAMA_TIMEOUT_SECONDS
    return DEFAULT_PROVIDER_TIMEOUT_SECONDS


def compute_capability_registry_hash() -> str:
    return "sha256:" + hashlib.sha256(CAP_REGISTRY_PATH.read_bytes()).hexdigest()


def governance_posture() -> str:
    """Return production/developer posture from capability-registry.json.

    The default is production. Any missing, malformed, or unrecognized value
    fails closed into production posture.
    """
    try:
        registry = json.loads(CAP_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "production"
    posture = registry.get("governance_posture", {})
    if isinstance(posture, dict):
        mode = str(posture.get("mode", "production")).strip().lower()
    else:
        mode = str(posture or "production").strip().lower()
    return "developer" if mode == "developer" else "production"


def developer_mode_active() -> bool:
    return governance_posture() == "developer"


def _sha256_body(body: bytes) -> str:
    return "sha256:" + hashlib.sha256(body or b"").hexdigest()

# ---------------------------------------------------------------------------
# Chain recorder (thread-safe, append-only JSONL)
# ---------------------------------------------------------------------------


class ChainRecorder:
    """Appends v2 decision records to the governance chain file.

    Uses the same cross-process mkdir lock as the governance layer and
    dashboard/server.py to prevent concurrent writers from reading
    the same prev_record_hash (D-024 / D-026 fix).
    """

    def __init__(self, chain_path: Path, integrity_monitor: Optional[IntegrityMonitor] = None):
        self._chain_path = chain_path
        self._lock = threading.Lock()
        self._integrity_monitor = integrity_monitor

    def append_atomic(self, record: dict) -> None:
        """Atomically read prev_record_hash, set it, recompute hash, and append.

        This ensures no two processes can read the same head hash.
        """
        import stat as _stat
        logger.info("Chain append: tool=%s decision=%s chain=%s",
                     record.get("original_tool", "?"),
                     record.get("policy_decision", "?"),
                     self._chain_path)
        self._chain_path.parent.mkdir(parents=True, exist_ok=True)
        appended = False
        with self._lock:
            lockdir = self._acquire_file_lock()
            try:
                if self._integrity_monitor is not None:
                    self._integrity_monitor.verify_chain_writable()
                record.setdefault("provider", "unknown")
                if developer_mode_active():
                    record["developer_mode"] = True
                else:
                    record.pop("developer_mode", None)
                add_machine_identity_fields(record, REPO)
                add_record_freshness_fields(record, REPO)
                record["prev_record_hash"] = self._last_hash()
                # Set signature fields to null BEFORE hashing so they're
                # included in the canonical form (stable hash regardless
                # of signing state).
                record["signature"] = None
                record["signing_key_id"] = None
                if is_non_action_event(record):
                    record["record_hash"] = _compute_event_record_hash(record)
                    if _SIGNING_KEY is not None:
                        sign_non_action_event(record, _SIGNING_KEY, _SIGNING_KEY_ID)
                else:
                    record["record_hash"] = _compute_record_hash(record)
                    # Sign the record if a key is loaded.
                    if _SIGNING_KEY is not None:
                        preimage = signing_preimage_payload(record)
                        sig_bytes = _SIGNING_KEY.sign(preimage.encode("utf-8"))
                        record["signature"] = _b64url_nopad(sig_bytes)
                        record["signing_key_id"] = _SIGNING_KEY_ID
                line = _canonical_form_json(record)
                fd = os.open(
                    str(self._chain_path),
                    os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                    _stat.S_IRUSR | _stat.S_IWUSR,
                )
                try:
                    os.write(fd, (line + "\n").encode("utf-8"))
                finally:
                    os.close(fd)
                if self._integrity_monitor is not None:
                    self._integrity_monitor.refresh_after_chain_write()
                appended = True
            finally:
                self._release_file_lock(lockdir)
        if appended:
            try:
                from background_verifier import trigger_after_append
                trigger_after_append(self._chain_path)
            except Exception:
                logger.exception("Background chain verifier trigger failed")

    def append_integrity_event(self, event_type: str, payload: dict) -> dict:
        """Append a non-action integrity event into the governance chain."""
        event = build_non_action_event(event_type, payload)
        self.append_atomic(event)
        return event

    def _last_hash(self) -> Optional[str]:
        """Read and verify the record_hash from the last line.

        Must be called under lock.  Recomputes the tail record's hash
        and compares it to the stored record_hash.  If they disagree,
        logs a chain integrity warning (evidence of tampering or
        corruption) but still returns the stored hash so the chain
        can continue appending.
        """
        if not self._chain_path.exists():
            return None
        try:
            last_line = ""
            with open(self._chain_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        last_line = stripped
            if not last_line:
                return None
            tail_record = json.loads(last_line)
            stored_hash = tail_record.get("record_hash")
            if stored_hash:
                recomputed = _compute_record_hash(tail_record)
                if recomputed != stored_hash:
                    logger.error(
                        "[CHAIN INTEGRITY] Tail record hash mismatch: "
                        "stored=%s recomputed=%s chain=%s",
                        stored_hash, recomputed, self._chain_path,
                    )
            return stored_hash
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _acquire_file_lock(self) -> Path:
        """Acquire cross-process mkdir lock (same protocol as the governance layer)."""
        lockdir = Path(str(self._chain_path) + ".lock.d")
        lock_meta = lockdir / "lock_owner.json"
        max_wait = 50

        def _try_acquire():
            try:
                lockdir.mkdir(exist_ok=False)
                try:
                    meta = json.dumps({"pid": os.getpid(), "ts": _time_mod.time()})
                    lock_meta.write_text(meta, encoding="utf-8")
                except OSError:
                    pass
                return True
            except FileExistsError:
                return False

        def _holder_is_alive():
            try:
                data = json.loads(lock_meta.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if not isinstance(pid, int):
                    return True
                os.kill(pid, 0)
                return True
            except (OSError, json.JSONDecodeError, KeyError):
                return False

        waited = 0
        while True:
            if _try_acquire():
                return lockdir
            waited += 1
            if waited >= max_wait:
                if not _holder_is_alive():
                    try:
                        lock_meta.unlink(missing_ok=True)
                        lockdir.rmdir()
                    except OSError:
                        pass
                    if _try_acquire():
                        return lockdir
                raise TimeoutError(f"timed out waiting for chain lock ({lockdir})")
            _time_mod.sleep(0.1)

    @staticmethod
    def _release_file_lock(lockdir: Path) -> None:
        try:
            (lockdir / "lock_owner.json").unlink(missing_ok=True)
            lockdir.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Backward-compatible Anthropic-specific helpers (used by existing tests)
# ---------------------------------------------------------------------------


def extract_tool_use_blocks(content: list) -> list[dict]:
    """Extract tool_use blocks from a Messages API response content array."""
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]


def replace_tool_use_with_denial(
    content: list, tool_use_id: str, tool_name: str, reason: str, matched_rule: str,
) -> list:
    """Replace a tool_use block with a text block containing the denial message."""
    result = []
    for block in content:
        if (
            isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("id") == tool_use_id
        ):
            result.append({
                "type": "text",
                "text": (
                    f"[Governance] Operation denied: {tool_name}\n"
                    f"Reason: {reason}\n"
                    f"Rule: {matched_rule}\n"
                    f"The operation was classified and denied by policy before execution."
                ),
            })
        else:
            result.append(block)
    return result


# ---------------------------------------------------------------------------
# Governance mediation (decision-only, no execution)
# ---------------------------------------------------------------------------


def _load_approval_store(chain_path: Path) -> ApprovalStore:
    """Load the approval store from the governance chain and runtime sidecars."""
    return load_approval_store_from_runtime(str(chain_path))


def _governed_family() -> str:
    return str(os.environ.get("GOV_GOVERNED_FAMILY", "mcp_tools_v1")).strip() or "mcp_tools_v1"


def _deployment_context() -> str:
    return str(os.environ.get("GOV_DEPLOYMENT_CONTEXT", "default")).strip() or "default"


def _policy_version() -> str:
    return str(os.environ.get("GOV_POLICY_VERSION", "baseline-v1")).strip() or "baseline-v1"


def _check_approval(
    approval_store: ApprovalStore,
    tool_name: str,
    targets: list[str],
    args: Optional[dict] = None,
    *,
    operation_description: str = "",
) -> Optional[dict]:
    """Check if an operation is approved by description, tool, or target."""
    family = _governed_family()
    context = _deployment_context()
    version = _policy_version()

    return approval_store.lookup_operation(
        tool_name,
        args or {},
        targets,
        family,
        context,
        version,
        repo_path=str(REPO),
        # QS-062: prefer matching on the operation_description so an
        # approval for "Push commits to origin/main" doesn't accidentally
        # authorise every Bash call.
        operation_description=operation_description,
    )


def mediate_decision(
    tool_name: str,
    args: dict,
    *,
    policy: dict,
    chain_recorder: Optional[ChainRecorder] = None,
    approval_store: Optional[ApprovalStore] = None,
    session_id: str = "",
    user_identity: str = "",
    provider_name: str = "unknown",
    integrity_monitor: Optional[IntegrityMonitor] = None,
    qa_gate: Optional[ProxyQualityGate] = None,
) -> dict:
    """Classify, evaluate, and record a governance decision.

    Returns the decision record. Does NOT execute the tool — in the API proxy
    model, the agent executes its own tools. The proxy only decides.

    If approval_store is provided and the policy decision is DENY, checks
    whether the operation has been approved. Approved operations are overridden
    to ALLOW with resolution "approved_lookup".
    """
    provider_name = provider_name or "unknown"
    qa_relaxation: Optional[dict] = None
    if qa_gate is not None:
        qa_result = qa_gate.check()
        if not qa_result.ok:
            # Developer mode relaxes two classes of QA integrity failure so a
            # build agent can keep working while it repairs the governance
            # system itself: active conditions (the quality service reporting
            # unhealthy / critical conditions) and QA chain staleness. When
            # relaxed, the operation forwards and EVERY resulting record is
            # annotated with developer_mode_qa_relaxation naming the bypassed
            # condition — the audit trail still shows what was wrong.
            #
            # A hash mismatch or an absent QA chain still block, even in
            # developer mode: those mean the governance configuration or the
            # QA chain itself cannot be trusted, so relaxing them would be
            # silently governing against the wrong rules. In production mode,
            # nothing is relaxed — all integrity failures block as before.
            relaxable = qa_result.condition_source in (
                "active_condition",
                "qa_chain_staleness",
            )
            if developer_mode_active() and relaxable:
                qa_relaxation = {
                    "condition_source": qa_result.condition_source,
                    "condition_id": qa_result.condition_id
                    or f"QA-GATE:{qa_result.condition_source}",
                    "condition_detail": qa_result.condition_detail,
                }
                logger.warning(
                    "Developer mode: forwarding despite QA gate failure "
                    "(%s): %s",
                    qa_result.condition_source,
                    qa_result.condition_detail,
                )
            else:
                record = _build_governance_integrity_error_record(
                    tool_name,
                    condition_source=qa_result.condition_source or "qa_chain_absent",
                    condition_detail=qa_result.condition_detail,
                    user_identity=user_identity,
                    session_id=session_id,
                    provider_name=provider_name,
                    condition_id=qa_result.condition_id or "",
                )
                if chain_recorder is not None:
                    chain_recorder.append_atomic(record)
                return record

    classification = classify(tool_name, args)

    record = evaluate(
        classification,
        policy=policy,
        prev_record_hash=None,
        user_identity=user_identity,
        session_id=session_id,
        approval_store_hash=approval_store_hash(approval_store),
    )

    record["provider"] = provider_name
    if developer_mode_active():
        record["developer_mode"] = True
    if qa_relaxation is not None:
        record["developer_mode_qa_relaxation"] = qa_relaxation
    record["record_hash"] = _compute_record_hash(record)

    # Check approval store for denied operations
    if record["policy_decision"] == "DENY" and approval_store is not None:
        targets = classification.get("targets", [])
        approval = _check_approval(
            approval_store,
            tool_name,
            targets,
            args,
            # QS-062: pass the description so an operator-issued approval
            # keyed on the exact operation phrase ("Push commits to
            # origin/main") wins before falling back to tool-name scope.
            operation_description=classification.get("operation_description", ""),
        )
        if approval:
            logger.info(
                "Approval override: %s approved by %s (event %s)",
                tool_name,
                approval.get("approving_operator", "?"),
                approval.get("event_id", "?"),
            )
            record["policy_decision"] = "ALLOW"
            record["policy_reasons"] = []
            record["matched_rule"] = "approved_lookup"
            record["approval_event_id"] = approval.get("event_id")
            record["record_hash"] = _compute_record_hash(record)

    if chain_recorder is not None:
        chain_recorder.append_atomic(record)

    return record


def _build_governance_integrity_error_record(
    tool_name: str,
    *,
    condition_source: str,
    condition_detail: str,
    user_identity: str,
    session_id: str,
    provider_name: str = "unknown",
    condition_id: str = "",
) -> dict:
    reason = f"Integrity error: {condition_detail}"
    payload = {
        "tool_name": tool_name,
        "original_tool": tool_name,
        "condition_source": condition_source,
        # QS-039 Adv #3: stable id correlating this error to a specific
        # condition (registry CR-* for known conditions, QA-GATE:<source>
        # for gate-internal staleness/absence). Falls back to the source
        # name so the field is always present and non-empty.
        "condition_id": condition_id or f"QA-GATE:{condition_source}",
        "condition_detail": condition_detail,
        "action_taken": "integrity_error_returned",
        "policy_decision": "INTEGRITY_ERROR",
        "matched_rule": f"integrity_{condition_source}",
        "policy_reasons": [{
            "code": "GOVERNANCE_INTEGRITY_ERROR",
            "detail": reason,
            "condition_source": condition_source,
        }],
        "user_identity": user_identity,
        "session_id": session_id,
    }
    payload["provider"] = provider_name or "unknown"
    if developer_mode_active():
        payload["developer_mode"] = True
    return build_non_action_event(
        "governance_integrity_error",
        payload,
    )


def _build_proxy_request_observed_record(
    *,
    provider_name: str,
    method: str,
    path: str,
    status_code: int,
    tool_endpoint: bool,
    examined: bool,
    forwarded: bool,
    request_body: bytes,
    detail: str = "",
) -> dict:
    payload = {
        "provider": provider_name or "unknown",
        "method": method,
        "path": path,
        "status_code": status_code,
        "tool_endpoint": bool(tool_endpoint),
        "examined": bool(examined),
        "forwarded": bool(forwarded),
        "request_body_hash": _sha256_body(request_body),
    }
    if detail:
        payload["detail"] = detail
    if developer_mode_active():
        payload["developer_mode"] = True
    return build_non_action_event("proxy_request_observed", payload)


def _integrity_error_response(record: dict, status_code: int = 502) -> tuple[int, dict, bytes]:
    body = json.dumps({
        "error": "governance_integrity_error",
        "condition_source": record.get("condition_source"),
        "condition_detail": record.get("condition_detail"),
        "record_hash": record.get("record_hash"),
    }).encode("utf-8")
    return status_code, {"content-type": "application/json", "content-length": str(len(body))}, body


def _is_blocking_record(record: dict) -> bool:
    return record.get("policy_decision") in {"DENY", "INTEGRITY_ERROR"}


def _is_websocket_upgrade(headers: dict) -> bool:
    return (
        headers.get("upgrade", "").lower() == "websocket"
        and "upgrade" in headers.get("connection", "").lower()
        and bool(headers.get("sec-websocket-key"))
    )


def _websocket_accept_value(client_key: str) -> str:
    digest = hashlib.sha1((client_key + _WEBSOCKET_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


async def _read_websocket_frame(reader: asyncio.StreamReader) -> tuple[int, bytes]:
    header = await asyncio.wait_for(reader.readexactly(2), timeout=120.0)
    opcode = header[0] & 0x0F
    masked = bool(header[1] & 0x80)
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", await reader.readexactly(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", await reader.readexactly(8))[0]
    if length > _WEBSOCKET_MAX_FRAME_BYTES:
        raise ValueError(f"websocket frame too large: {length} bytes")
    mask = await reader.readexactly(4) if masked else b""
    payload = await reader.readexactly(length) if length else b""
    if masked:
        payload = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
    return opcode, payload


def _encode_websocket_frame(payload: Any, opcode: int = 1) -> bytes:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    length = len(payload)
    head = bytearray([0x80 | opcode])
    if length < 126:
        head.append(length)
    elif length < (1 << 16):
        head.append(126)
        head.extend(struct.pack("!H", length))
    else:
        head.append(127)
        head.extend(struct.pack("!Q", length))
    return bytes(head) + payload


def _websocket_denial_message(tool_call: ToolCall, reason: str, matched_rule: str) -> str:
    denial_text = (
        f"[Governance] Operation denied: {tool_call.tool_name}\n"
        f"Reason: {reason}\n"
        f"Rule: {matched_rule}\n"
        f"The operation was classified and denied by policy before execution."
    )
    return json.dumps({
        "type": "response.output_text.delta",
        "delta": denial_text,
    })


# ---------------------------------------------------------------------------
# Backward-compatible StreamingToolCollector (wraps Anthropic provider)
# ---------------------------------------------------------------------------


class StreamingToolCollector:
    """Backward-compatible wrapper for Anthropic streaming collection.

    Maintains the same interface as the original for existing tests,
    but delegates to the provider-based streaming collector internally.
    """

    def __init__(self, policy: dict, chain_recorder: Optional[ChainRecorder],
                 session_id: str = "", user_identity: str = "",
                 approval_store: Optional[ApprovalStore] = None,
                 integrity_monitor: Optional[IntegrityMonitor] = None,
                 qa_gate: Optional[ProxyQualityGate] = None):
        self._policy = policy
        self._chain_recorder = chain_recorder
        self._session_id = session_id
        self._user_identity = user_identity
        self._approval_store = approval_store
        self._integrity_monitor = integrity_monitor
        self._qa_gate = qa_gate

        # Active tool_use blocks being collected, keyed by index
        self._active_blocks: dict[int, dict] = {}
        # JSON fragments for each block index
        self._json_fragments: dict[int, list[str]] = {}
        # Governance decisions, keyed by block index
        self._decisions: dict[int, dict] = {}
        # Denied block indices
        self._denied_indices: set[int] = set()
        # Replacement events for denied blocks
        self._replacements: dict[int, list[bytes]] = {}

    def process_event(self, event_type: str, data: dict) -> Optional[str]:
        """Process an SSE event. Returns action: 'pass', 'buffer', or 'replace'."""
        msg_type = data.get("type", "")

        if msg_type == "content_block_start":
            block = data.get("content_block", {})
            if block.get("type") == "tool_use":
                idx = data.get("index", 0)
                self._active_blocks[idx] = {
                    "type": "tool_use",
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input": {},
                }
                self._json_fragments[idx] = []
                return "buffer"
            return "pass"

        if msg_type == "content_block_delta":
            idx = data.get("index", 0)
            if idx in self._active_blocks:
                delta = data.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    self._json_fragments.setdefault(idx, []).append(
                        delta.get("partial_json", "")
                    )
                return "buffer"
            return "pass"

        if msg_type == "content_block_stop":
            idx = data.get("index", 0)
            if idx in self._active_blocks:
                block = self._active_blocks.pop(idx)
                fragments = self._json_fragments.pop(idx, [])

                full_json = "".join(fragments)
                if full_json:
                    try:
                        block["input"] = json.loads(full_json)
                    except json.JSONDecodeError:
                        block["input"] = {"_raw": full_json}

                record = mediate_decision(
                    block["name"],
                    block.get("input", {}),
                    policy=self._policy,
                    chain_recorder=self._chain_recorder,
                    approval_store=self._approval_store,
                    session_id=self._session_id,
                    user_identity=self._user_identity,
                    provider_name="anthropic",
                    integrity_monitor=self._integrity_monitor,
                    qa_gate=self._qa_gate,
                )
                self._decisions[idx] = record

                if _is_blocking_record(record):
                    self._denied_indices.add(idx)
                    reasons = record.get("policy_reasons", [])
                    reason_text = reasons[0].get("detail", "policy denied") if reasons else "policy denied"
                    self._replacements[idx] = _build_denial_sse_events(
                        idx, block["id"], block["name"],
                        reason_text, record.get("matched_rule", ""),
                    )
                    return "replace"
                else:
                    return "pass"
            return "pass"

        return "pass"

    def get_buffered_events(self, idx: int) -> list[bytes]:
        return []

    def get_replacement_events(self, idx: int) -> list[bytes]:
        return self._replacements.get(idx, [])

    def is_denied(self, idx: int) -> bool:
        return idx in self._denied_indices

    def get_decision(self, idx: int) -> Optional[dict]:
        return self._decisions.get(idx)


def _build_denial_sse_events(
    index: int, tool_use_id: str, tool_name: str,
    reason: str, matched_rule: str,
) -> list[bytes]:
    """Build SSE events that replace a denied tool_use with a text block."""
    denial_text = (
        f"[Governance] Operation denied: {tool_name}\n"
        f"Reason: {reason}\n"
        f"Rule: {matched_rule}\n"
        f"The operation was classified and denied by policy before execution."
    )
    events = []

    start_data = json.dumps({
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": "text", "text": ""},
    })
    events.append(f"event: content_block_start\ndata: {start_data}\n\n".encode())

    delta_data = json.dumps({
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "text_delta", "text": denial_text},
    })
    events.append(f"event: content_block_delta\ndata: {delta_data}\n\n".encode())

    stop_data = json.dumps({
        "type": "content_block_stop",
        "index": index,
    })
    events.append(f"event: content_block_stop\ndata: {stop_data}\n\n".encode())

    return events


# ---------------------------------------------------------------------------
# Base-dirs placeholder substitution
# ---------------------------------------------------------------------------

import re as _re
_UNKNOWN_PLACEHOLDER_PAT = _re.compile(r"^__GOV_[A-Z0-9_]+__$")


def resolve_policy_base_dirs(
    raw_dirs: list,
    *,
    repo_path: str,
    runtime_path: str,
) -> list[str]:
    """Substitute placeholder tokens in base_dirs and ensure safety invariants."""
    placeholder_map = {
        "__GOV_CANONICAL_REPO_PATH__": repo_path,
        "__GOV_RUNTIME_PATH__": runtime_path,
    }

    substituted: list[str] = []
    for entry in raw_dirs:
        entry_s = str(entry)
        if entry_s in placeholder_map:
            substituted.append(placeholder_map[entry_s])
        elif _UNKNOWN_PLACEHOLDER_PAT.match(entry_s):
            logger.warning(
                "Dropping unknown base_dirs placeholder: %s", entry_s
            )
        else:
            substituted.append(entry_s)

    if repo_path not in substituted:
        logger.warning(
            "base_dirs missing repo path; adding safety fallback: %s",
            repo_path,
        )
        substituted.append(repo_path)
    if runtime_path not in substituted:
        logger.warning(
            "base_dirs missing runtime path; adding safety fallback: %s",
            runtime_path,
        )
        substituted.append(runtime_path)

    seen: set[str] = set()
    deduped: list[str] = []
    for d in substituted:
        if d not in seen:
            seen.add(d)
            deduped.append(d)

    return deduped


# ---------------------------------------------------------------------------
# HTTP proxy handler (provider-agnostic)
# ---------------------------------------------------------------------------


class GovernanceProxy:
    """HTTP proxy that governs AI provider tool calls.

    Routes requests to the appropriate provider based on URL prefix.
    Governance mediation (classify → evaluate → record) is provider-agnostic.
    """

    def __init__(
        self,
        *,
        upstream_base: str = ANTHROPIC_API_BASE,
        policy: Optional[dict] = None,
        chain_recorder: Optional[ChainRecorder] = None,
        chain_path: Optional[Path] = None,
        session_id: str = "",
        user_identity: str = "",
        provider_config: Optional[dict] = None,
        integrity_monitor: Optional[IntegrityMonitor] = None,
        qa_gate: Optional[ProxyQualityGate] = None,
    ):
        self._upstream_base = upstream_base.rstrip("/")
        self._policy = policy or self._load_default_policy()
        self._chain_recorder = chain_recorder
        self._chain_path = chain_path
        self._session_id = session_id
        self._user_identity = user_identity
        self._approval_store: Optional[ApprovalStore] = None
        self._approval_store_mtime: float = 0.0
        self._approval_lock = threading.Lock()
        self._integrity_monitor = integrity_monitor
        self._qa_gate = qa_gate
        # Provider-specific config (upstream URLs, etc.)
        self._provider_config = provider_config or {}
        # Default: put the legacy upstream_base as the anthropic upstream
        if "anthropic_upstream" not in self._provider_config:
            self._provider_config["anthropic_upstream"] = self._upstream_base

    def _get_approval_store(self) -> Optional[ApprovalStore]:
        """Return a cached approval store, reloading when the chain file changes."""
        if self._chain_path is None:
            return None
        with self._approval_lock:
            try:
                mtime = self._chain_path.stat().st_mtime if self._chain_path.exists() else 0.0
            except OSError:
                return self._approval_store
            if mtime != self._approval_store_mtime or self._approval_store is None:
                self._approval_store = _load_approval_store(self._chain_path)
                self._approval_store_mtime = mtime
                logger.info("Approval store reloaded: %d active approvals",
                            len(self._approval_store.all_approvals()))
        return self._approval_store

    def _append_request_observed(
        self,
        *,
        provider_name: str,
        method: str,
        path: str,
        status_code: int,
        tool_endpoint: bool,
        examined: bool,
        forwarded: bool,
        request_body: bytes,
        detail: str = "",
    ) -> None:
        if self._chain_recorder is None:
            return
        record = _build_proxy_request_observed_record(
            provider_name=provider_name,
            method=method,
            path=path,
            status_code=status_code,
            tool_endpoint=tool_endpoint,
            examined=examined,
            forwarded=forwarded,
            request_body=request_body,
            detail=detail,
        )
        self._chain_recorder.append_atomic(record)

    def _append_unexaminable_error(
        self,
        *,
        provider_name: str,
        method: str,
        path: str,
        detail: str,
    ) -> dict:
        record = _build_governance_integrity_error_record(
            "__request__",
            condition_source="unsupported_provider_format",
            condition_detail=f"{method} {path}: {detail}",
            user_identity=self._user_identity,
            session_id=self._session_id,
            provider_name=provider_name,
            condition_id="QA-GATE:unsupported_provider_format",
        )
        if self._chain_recorder is not None:
            self._chain_recorder.append_atomic(record)
        return record

    @staticmethod
    def _load_default_policy() -> dict:
        policy_path = os.environ.get("GOV_POLICY_RULES_PATH", "").strip()
        policy = load_policy_rules(Path(policy_path) if policy_path else None)
        runtime = runtime_root(REPO)
        policy = dict(policy)
        policy["base_dirs"] = resolve_policy_base_dirs(
            policy.get("base_dirs", []),
            repo_path=str(REPO),
            runtime_path=str(runtime),
        )
        logger.info("base_dirs loaded: %s", policy["base_dirs"])
        return policy

    def _prepare_request_with_provider(
        self, method: str, path: str, headers: dict, body: bytes,
        provider: BaseProvider,
    ) -> tuple[str, dict, bool, bool]:
        """Parse request using provider interface. Returns (url, headers, is_tool_ep, is_streaming)."""
        upstream_url = provider.get_upstream_url(path, self._provider_config)
        forward_headers = provider.forward_headers(headers)
        is_tool_ep = provider.is_tool_endpoint(path)
        is_streaming = False
        if is_tool_ep and body:
            is_streaming = provider.is_streaming(body)
        # Check for streaming in URL path (Gemini)
        if hasattr(provider, 'is_streaming_path') and provider.is_streaming_path(path):
            is_streaming = True
        return upstream_url, forward_headers, is_tool_ep, is_streaming

    # Legacy method for backward compatibility
    def _prepare_request(self, method: str, path: str, headers: dict,
                         body: bytes) -> tuple[str, dict, bool, bool]:
        """Parse request (Anthropic-only, for backward compat)."""
        path_base = path.split("?")[0]
        is_messages = path_base.rstrip("/").endswith("/v1/messages")
        upstream_url = f"{self._upstream_base}{path}"
        forward_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in ("host", "transfer-encoding", "connection")
        }
        is_streaming = False
        if is_messages and body:
            try:
                req_body = json.loads(body)
                is_streaming = req_body.get("stream", False)
            except (json.JSONDecodeError, AttributeError):
                pass
        return upstream_url, forward_headers, is_messages, is_streaming

    @staticmethod
    def _forward_response_headers(headers, body: bytes) -> dict:
        forwarded = {
            k: v for k, v in dict(headers).items()
            if k.lower() not in {
                "content-encoding",
                "content-length",
                "transfer-encoding",
                "connection",
            }
        }
        forwarded["content-length"] = str(len(body))
        return forwarded

    def _websocket_upstream_url(self, path: str, provider: BaseProvider) -> str:
        url = provider.get_upstream_url(path, self._provider_config)
        if url.startswith("https://"):
            return "wss://" + url[len("https://"):]
        if url.startswith("http://"):
            return "ws://" + url[len("http://"):]
        return url

    def _websocket_forward_headers(self, headers: dict, provider: BaseProvider) -> dict:
        forwarded = provider.forward_headers(headers)
        for key in list(forwarded):
            if key.lower() in {"content-type", "content-length", "accept"}:
                forwarded.pop(key, None)
        return forwarded

    async def _process_websocket_upstream_message(
        self,
        *,
        provider: BaseProvider,
        collector: BaseStreamingCollector,
        message: Any,
        approval_store: Optional[ApprovalStore],
    ) -> tuple[list[Any], int]:
        if isinstance(message, bytes):
            return [message], 0
        if not isinstance(message, str):
            return [str(message)], 0

        try:
            data = json.loads(message)
        except json.JSONDecodeError as exc:
            if not developer_mode_active():
                record = self._append_unexaminable_error(
                    provider_name=provider.name,
                    method="WS",
                    path="websocket",
                    detail=f"websocket JSON parse failed: {exc}",
                )
                return [json.dumps({
                    "type": "error",
                    "error": {
                        "type": "governance_integrity_error",
                        "condition_source": record.get("condition_source"),
                        "condition_detail": record.get("condition_detail"),
                    },
                })], 1
            return [message], 0

        event_type = str(data.get("type") or "")
        stream_action = collector.process_event(event_type, data)
        if stream_action.action == "buffer":
            collector.add_buffered_event(stream_action.index, message)
            if not stream_action.completed_tool_call:
                return [], 0

            tc = stream_action.completed_tool_call
            record = mediate_decision(
                tc.tool_name, tc.args,
                policy=self._policy,
                chain_recorder=self._chain_recorder,
                approval_store=approval_store,
                session_id=self._session_id,
                user_identity=self._user_identity,
                provider_name=provider.name,
                integrity_monitor=self._integrity_monitor,
                qa_gate=self._qa_gate,
            )
            if _is_blocking_record(record):
                reasons = record.get("policy_reasons", [])
                reason_text = reasons[0].get("detail", "policy denied") if reasons else "policy denied"
                return [_websocket_denial_message(
                    tc, reason_text, record.get("matched_rule", ""),
                )], 1
            return collector.get_buffered_events(stream_action.index) + [message], 1

        if stream_action.action == "pass":
            return [message], 0
        return [], 0

    async def handle_websocket(
        self,
        path: str,
        headers: dict,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        provider: BaseProvider,
    ) -> None:
        """Proxy and govern an OpenAI Responses WebSocket session."""
        upstream_url = self._websocket_upstream_url(path, provider)
        fwd_headers = self._websocket_forward_headers(headers, provider)
        request_marker = f"WS {path}".encode("utf-8")
        governed_record_count = 0
        handshake_complete = False

        try:
            async with websockets.connect(
                upstream_url,
                additional_headers=fwd_headers,
                open_timeout=10,
                ping_interval=20,
                ping_timeout=20,
                max_size=_WEBSOCKET_MAX_FRAME_BYTES,
            ) as upstream:
                accept = _websocket_accept_value(headers["sec-websocket-key"])
                writer.write(b"HTTP/1.1 101 Switching Protocols\r\n")
                writer.write(b"upgrade: websocket\r\n")
                writer.write(b"connection: Upgrade\r\n")
                writer.write(f"sec-websocket-accept: {accept}\r\n".encode("ascii"))
                writer.write(b"\r\n")
                await writer.drain()
                handshake_complete = True

                collector = provider.create_streaming_collector()
                approval_store = self._get_approval_store()
                closed = asyncio.Event()

                async def client_to_upstream() -> None:
                    while not closed.is_set():
                        opcode, payload = await _read_websocket_frame(reader)
                        if opcode == 0x8:
                            closed.set()
                            await upstream.close()
                            writer.write(_encode_websocket_frame(payload, opcode=0x8))
                            await writer.drain()
                            return
                        if opcode == 0x9:
                            writer.write(_encode_websocket_frame(payload, opcode=0xA))
                            await writer.drain()
                            continue
                        if opcode == 0xA:
                            continue
                        if opcode == 0x1:
                            await upstream.send(payload.decode("utf-8", errors="replace"))
                        elif opcode == 0x2:
                            await upstream.send(payload)

                async def upstream_to_client() -> None:
                    nonlocal governed_record_count
                    async for message in upstream:
                        outputs, records_written = await self._process_websocket_upstream_message(
                            provider=provider,
                            collector=collector,
                            message=message,
                            approval_store=approval_store,
                        )
                        governed_record_count += records_written
                        for output in outputs:
                            opcode = 0x2 if isinstance(output, bytes) else 0x1
                            writer.write(_encode_websocket_frame(output, opcode=opcode))
                            await writer.drain()
                    closed.set()

                tasks = {
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                }
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    task.result()

        except Exception as exc:
            logger.warning("WebSocket proxy error (%s %s): %s", provider.name, path, exc)
            if not handshake_complete:
                self._append_request_observed(
                    provider_name=provider.name, method="WS", path=upstream_url,
                    status_code=502, tool_endpoint=provider.is_tool_endpoint(path),
                    examined=False, forwarded=False, request_body=request_marker,
                    detail=f"websocket upstream connection failed: {exc}",
                )
                err_body = json.dumps({"error": "websocket upstream connection failed"}).encode()
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n")
                writer.write(b"content-type: application/json\r\n")
                writer.write(f"content-length: {len(err_body)}\r\n".encode())
                writer.write(b"\r\n")
                writer.write(err_body)
                await writer.drain()
                return
        finally:
            if handshake_complete and governed_record_count == 0:
                self._append_request_observed(
                    provider_name=provider.name, method="WS", path=upstream_url,
                    status_code=101, tool_endpoint=provider.is_tool_endpoint(path),
                    examined=True, forwarded=True, request_body=request_marker,
                    detail="websocket session contained no tool calls",
                )

    async def handle_request(self, method: str, path: str, headers: dict,
                             body: bytes,
                             provider: Optional[BaseProvider] = None,
                             ) -> tuple[int, dict, bytes]:
        """Handle a proxied HTTP request (non-streaming or buffered fallback).

        If provider is given, uses the provider interface for parsing/rewriting.
        Otherwise falls back to legacy Anthropic-only behavior.
        """
        if provider is not None:
            return await self._handle_request_with_provider(
                method, path, headers, body, provider
            )

        # Legacy path (backward compat)
        url, fwd_headers, is_messages, is_streaming = self._prepare_request(
            method, path, headers, body
        )
        if is_messages and body:
            try:
                json.loads(body)
            except json.JSONDecodeError as exc:
                if not developer_mode_active():
                    record = self._append_unexaminable_error(
                        provider_name="anthropic",
                        method=method,
                        path=path,
                        detail=f"request JSON parse failed: {exc}",
                    )
                    return _integrity_error_response(record)
                logger.warning("Developer mode forwarding unparseable legacy Anthropic request: %s", path)
        if is_messages and is_streaming:
            return await self._handle_streaming_buffered(
                url, fwd_headers, body
            )
        else:
            return await self._handle_non_streaming(
                url, method, fwd_headers, body, is_messages
            )

    async def _handle_request_with_provider(
        self, method: str, path: str, headers: dict, body: bytes,
        provider: BaseProvider,
    ) -> tuple[int, dict, bytes]:
        """Handle a request using the provider interface."""
        url, fwd_headers, is_tool_ep, is_streaming = self._prepare_request_with_provider(
            method, path, headers, body, provider
        )
        if is_tool_ep and body:
            try:
                json.loads(body)
            except json.JSONDecodeError as exc:
                if not developer_mode_active():
                    record = self._append_unexaminable_error(
                        provider_name=provider.name,
                        method=method,
                        path=path,
                        detail=f"request JSON parse failed: {exc}",
                    )
                    return _integrity_error_response(record)
                logger.warning("Developer mode forwarding unparseable request body: %s %s", provider.name, path)
        if is_tool_ep and is_streaming:
            return await self._handle_streaming_buffered_provider(
                url, fwd_headers, body, provider
            )
        else:
            return await self._handle_non_streaming_provider(
                url, method, fwd_headers, body, is_tool_ep, provider
            )

    async def handle_streaming_to_writer(
        self, path: str, headers: dict, body: bytes,
        writer: asyncio.StreamWriter,
        provider: Optional[BaseProvider] = None,
    ) -> None:
        """Handle a streaming request, forwarding text events in real time.

        Text blocks are written to the client immediately as they arrive.
        Tool calls are buffered until complete, governed, then flushed
        (ALLOW) or replaced with denial text (DENY).
        """
        if provider is not None:
            return await self._handle_streaming_to_writer_provider(
                path, headers, body, writer, provider
            )

        # Legacy Anthropic path
        url, fwd_headers, is_messages, _ = self._prepare_request(
            "POST", path, headers, body
        )
        collector = StreamingToolCollector(
            self._policy, self._chain_recorder,
            self._session_id, self._user_identity,
            approval_store=self._get_approval_store(),
            integrity_monitor=self._integrity_monitor,
            qa_gate=self._qa_gate,
        )
        buffered_events: dict[int, list[bytes]] = {}
        _tool_use_count = 0

        logger.info("Streaming handler entered for path=%s", path)

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", url, headers=fwd_headers, content=body,
            ) as resp:
                if resp.status_code != 200:
                    content = await resp.aread()
                    # QS-053: every request through the proxy produces a chain
                    # record, including streaming non-200s.
                    self._append_request_observed(
                        provider_name="anthropic", method="POST", path=url,
                        status_code=resp.status_code, tool_endpoint=is_messages,
                        examined=False, forwarded=True, request_body=body,
                        detail="streaming upstream non-200 response",
                    )
                    writer.write(f"HTTP/1.1 {resp.status_code} Error\r\n".encode())
                    writer.write(b"content-type: application/json\r\n")
                    writer.write(f"content-length: {len(content)}\r\n".encode())
                    writer.write(b"\r\n")
                    writer.write(content)
                    await writer.drain()
                    return

                writer.write(b"HTTP/1.1 200 OK\r\n")
                writer.write(b"content-type: text/event-stream\r\n")
                writer.write(b"cache-control: no-cache\r\n")
                writer.write(b"connection: keep-alive\r\n")
                for key in ("x-request-id", "request-id"):
                    val = resp.headers.get(key)
                    if val:
                        writer.write(f"{key}: {val}\r\n".encode())
                writer.write(b"\r\n")
                await writer.drain()

                current_event_type = ""
                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue

                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()

                    if data_str == "[DONE]":
                        logger.info("Stream complete: %d tool_use blocks mediated", _tool_use_count)
                        writer.write(b"event: done\ndata: [DONE]\n\n")
                        await writer.drain()
                        continue

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError as exc:
                        if not developer_mode_active():
                            record = self._append_unexaminable_error(
                                provider_name=provider.name,
                                method="POST",
                                path=url,
                                detail=f"stream JSON parse failed: {exc}",
                            )
                            err = json.dumps({
                                "error": "governance_integrity_error",
                                "condition_source": record.get("condition_source"),
                                "condition_detail": record.get("condition_detail"),
                            })
                            writer.write(f"event: error\ndata: {err}\n\n".encode())
                            await writer.drain()
                            return
                        chunk = f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                        writer.write(chunk)
                        await writer.drain()
                        continue

                    action = collector.process_event(current_event_type, data)

                    if action == "buffer":
                        idx = data.get("index", 0)
                        msg_type = data.get("type", "")
                        if msg_type == "content_block_start":
                            _tool_use_count += 1
                            block_name = data.get("content_block", {}).get("name", "?")
                            logger.info("Tool use #%d detected: %s (idx=%d)", _tool_use_count, block_name, idx)
                        buffered_events.setdefault(idx, []).append(
                            f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                        )

                    elif action == "replace":
                        idx = data.get("index", 0)
                        decision = collector.get_decision(idx)
                        logger.info("Tool DENIED (idx=%d): %s", idx, decision.get("matched_rule", "") if decision else "?")
                        for event_bytes in collector.get_replacement_events(idx):
                            writer.write(event_bytes)
                        await writer.drain()
                        buffered_events.pop(idx, None)

                    elif action == "pass":
                        msg_type = data.get("type", "")
                        idx = data.get("index", 0)

                        if msg_type == "content_block_stop" and idx in buffered_events:
                            decision = collector.get_decision(idx)
                            if decision:
                                logger.info("Tool ALLOWED (idx=%d): %s → %s",
                                            idx, decision.get("original_tool", "?"),
                                            decision.get("policy_decision", "?"))
                            for event_bytes in buffered_events.pop(idx):
                                writer.write(event_bytes)
                            writer.write(
                                f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                            )
                            await writer.drain()
                        else:
                            writer.write(
                                f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                            )
                            await writer.drain()

        # QS-053: a streaming response with no tool_use blocks still produces
        # a chain record (mirrors the non-streaming no-tool-blocks path), so
        # every request through the proxy is recorded — not just those that
        # carry a governed tool call. Fires on normal stream end regardless of
        # whether the upstream emitted a [DONE] sentinel.
        if _tool_use_count == 0:
            self._append_request_observed(
                provider_name="anthropic", method="POST", path=url,
                status_code=200, tool_endpoint=is_messages,
                examined=True, forwarded=True, request_body=body,
                detail="recognized streaming response contained no tool_use blocks",
            )

    async def _handle_streaming_to_writer_provider(
        self, path: str, headers: dict, body: bytes,
        writer: asyncio.StreamWriter,
        provider: BaseProvider,
    ) -> None:
        """Handle streaming with provider interface."""
        url, fwd_headers, is_tool_ep, _ = self._prepare_request_with_provider(
            "POST", path, headers, body, provider
        )
        collector = provider.create_streaming_collector()
        _tool_call_count = 0
        approval_store = self._get_approval_store()

        logger.info("Streaming handler (%s) entered for path=%s", provider.name, path)

        # QS-061: pick a timeout that fits the provider. Cloud APIs answer
        # well under 120s, but local Ollama can take minutes per token.
        async with httpx.AsyncClient(
            timeout=provider_timeout_seconds(provider.name, self._provider_config)
        ) as client:
            async with client.stream(
                "POST", url, headers=fwd_headers, content=body,
            ) as resp:
                if resp.status_code != 200:
                    content = await resp.aread()
                    # QS-053: record every request, including streaming non-200s.
                    self._append_request_observed(
                        provider_name=provider.name, method="POST", path=url,
                        status_code=resp.status_code, tool_endpoint=is_tool_ep,
                        examined=False, forwarded=True, request_body=body,
                        detail="streaming upstream non-200 response",
                    )
                    writer.write(f"HTTP/1.1 {resp.status_code} Error\r\n".encode())
                    writer.write(b"content-type: application/json\r\n")
                    writer.write(f"content-length: {len(content)}\r\n".encode())
                    writer.write(b"\r\n")
                    writer.write(content)
                    await writer.drain()
                    return

                writer.write(b"HTTP/1.1 200 OK\r\n")
                writer.write(b"content-type: text/event-stream\r\n")
                writer.write(b"cache-control: no-cache\r\n")
                writer.write(b"connection: keep-alive\r\n")
                for key in ("x-request-id", "request-id"):
                    val = resp.headers.get(key)
                    if val:
                        writer.write(f"{key}: {val}\r\n".encode())
                writer.write(b"\r\n")
                await writer.drain()

                current_event_type = ""
                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue

                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()

                    if data_str == "[DONE]":
                        logger.info("Stream complete (%s): %d tool calls mediated",
                                    provider.name, _tool_call_count)
                        writer.write(b"event: done\ndata: [DONE]\n\n")
                        await writer.drain()
                        continue

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        chunk = f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                        writer.write(chunk)
                        await writer.drain()
                        continue

                    event_bytes = f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                    stream_action = collector.process_event(current_event_type, data)

                    if stream_action.action == "buffer":
                        collector.add_buffered_event(stream_action.index, event_bytes)
                        if stream_action.completed_tool_call:
                            _tool_call_count += 1
                            tc = stream_action.completed_tool_call
                            logger.info("Tool call #%d (%s) detected: %s",
                                        _tool_call_count, provider.name, tc.tool_name)

                            # Mediate the completed tool call
                            record = mediate_decision(
                                tc.tool_name, tc.args,
                                policy=self._policy,
                                chain_recorder=self._chain_recorder,
                                approval_store=approval_store,
                                session_id=self._session_id,
                                user_identity=self._user_identity,
                                provider_name=provider.name,
                                integrity_monitor=self._integrity_monitor,
                                qa_gate=self._qa_gate,
                            )

                            if _is_blocking_record(record):
                                reasons = record.get("policy_reasons", [])
                                reason_text = reasons[0].get("detail", "policy denied") if reasons else "policy denied"
                                logger.info("Tool DENIED (%s): %s — %s",
                                            provider.name, tc.tool_name,
                                            record.get("matched_rule", ""))
                                for denial_event in collector.build_denial_events(
                                    stream_action.index, tc,
                                    reason_text, record.get("matched_rule", ""),
                                ):
                                    writer.write(denial_event)
                                await writer.drain()
                            else:
                                logger.info("Tool ALLOWED (%s): %s",
                                            provider.name, tc.tool_name)
                                for buf_event in collector.get_buffered_events(stream_action.index):
                                    writer.write(buf_event)
                                # Also write the current stop event
                                writer.write(event_bytes)
                                await writer.drain()

                    elif stream_action.action == "pass":
                        writer.write(event_bytes)
                        await writer.drain()

        # QS-053: record the request even when the stream carried no tool call.
        if _tool_call_count == 0:
            self._append_request_observed(
                provider_name=provider.name, method="POST", path=url,
                status_code=200, tool_endpoint=is_tool_ep,
                examined=True, forwarded=True, request_body=body,
                detail="recognized streaming response contained no tool calls",
            )

    async def _handle_non_streaming(
        self, url: str, method: str, headers: dict, body: bytes,
        is_messages: bool,
    ) -> tuple[int, dict, bytes]:
        """Forward a non-streaming request and govern the response (legacy Anthropic)."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method, url, headers=headers, content=body,
            )

        resp_body = resp.content
        resp_headers = self._forward_response_headers(resp.headers, resp_body)

        logger.info("Non-streaming response: status=%d is_messages=%s", resp.status_code, is_messages)
        if not is_messages or resp.status_code != 200:
            self._append_request_observed(
                provider_name="anthropic",
                method=method,
                path=url,
                status_code=resp.status_code,
                tool_endpoint=is_messages,
                examined=not is_messages,
                forwarded=True,
                request_body=body,
                detail="legacy non-messages endpoint" if not is_messages else "upstream non-200 response",
            )
            return resp.status_code, resp_headers, resp_body

        try:
            data = json.loads(resp_body)
        except json.JSONDecodeError as exc:
            if not developer_mode_active():
                record = self._append_unexaminable_error(
                    provider_name="anthropic",
                    method=method,
                    path=url,
                    detail=f"response JSON parse failed: {exc}",
                )
                return _integrity_error_response(record)
            self._append_request_observed(
                provider_name="anthropic",
                method=method,
                path=url,
                status_code=resp.status_code,
                tool_endpoint=True,
                examined=False,
                forwarded=True,
                request_body=body,
                detail=f"developer mode forwarded response JSON parse failure: {exc}",
            )
            return resp.status_code, resp_headers, resp_body

        content = data.get("content", [])
        tool_blocks = extract_tool_use_blocks(content)

        if not tool_blocks:
            self._append_request_observed(
                provider_name="anthropic",
                method=method,
                path=url,
                status_code=resp.status_code,
                tool_endpoint=True,
                examined=True,
                forwarded=True,
                request_body=body,
                detail="recognized response contained no tool_use blocks",
            )
            return resp.status_code, resp_headers, resp_body

        modified = False
        approval_store = self._get_approval_store()
        for block in tool_blocks:
            record = mediate_decision(
                block["name"],
                block.get("input", {}),
                policy=self._policy,
                chain_recorder=self._chain_recorder,
                approval_store=approval_store,
                session_id=self._session_id,
                user_identity=self._user_identity,
                provider_name="anthropic",
                integrity_monitor=self._integrity_monitor,
                qa_gate=self._qa_gate,
            )

            if _is_blocking_record(record):
                reasons = record.get("policy_reasons", [])
                reason_text = reasons[0].get("detail", "policy denied") if reasons else "policy denied"
                data["content"] = replace_tool_use_with_denial(
                    data["content"],
                    block["id"],
                    block["name"],
                    reason_text,
                    record.get("matched_rule", ""),
                )
                modified = True

        if modified:
            remaining_tool_use = [
                b for b in data["content"]
                if isinstance(b, dict) and b.get("type") == "tool_use"
            ]
            if not remaining_tool_use and data.get("stop_reason") == "tool_use":
                data["stop_reason"] = "end_turn"
            resp_body = json.dumps(data).encode()
            resp_headers = self._forward_response_headers(resp_headers, resp_body)

        return resp.status_code, resp_headers, resp_body

    async def _handle_non_streaming_provider(
        self, url: str, method: str, headers: dict, body: bytes,
        is_tool_ep: bool, provider: BaseProvider,
    ) -> tuple[int, dict, bytes]:
        """Forward a non-streaming request and govern via provider interface."""
        # QS-061: per-provider timeout — Ollama defaults to 300s.
        async with httpx.AsyncClient(
            timeout=provider_timeout_seconds(provider.name, self._provider_config)
        ) as client:
            resp = await client.request(
                method, url, headers=headers, content=body,
            )

        resp_body = resp.content
        resp_headers = self._forward_response_headers(resp.headers, resp_body)

        logger.info("Non-streaming response (%s): status=%d is_tool_ep=%s",
                     provider.name, resp.status_code, is_tool_ep)
        if not is_tool_ep or resp.status_code != 200:
            self._append_request_observed(
                provider_name=provider.name,
                method=method,
                path=url,
                status_code=resp.status_code,
                tool_endpoint=is_tool_ep,
                examined=not is_tool_ep,
                forwarded=True,
                request_body=body,
                detail="non-tool endpoint" if not is_tool_ep else "upstream non-200 response",
            )
            return resp.status_code, resp_headers, resp_body

        try:
            data = json.loads(resp_body)
        except json.JSONDecodeError as exc:
            if not developer_mode_active():
                record = self._append_unexaminable_error(
                    provider_name=provider.name,
                    method=method,
                    path=url,
                    detail=f"response JSON parse failed: {exc}",
                )
                return _integrity_error_response(record)
            self._append_request_observed(
                provider_name=provider.name,
                method=method,
                path=url,
                status_code=resp.status_code,
                tool_endpoint=True,
                examined=False,
                forwarded=True,
                request_body=body,
                detail=f"developer mode forwarded response JSON parse failure: {exc}",
            )
            return resp.status_code, resp_headers, resp_body

        if not provider.response_format_known(data):
            detail = "provider response format is not recognized"
            if not developer_mode_active():
                record = self._append_unexaminable_error(
                    provider_name=provider.name,
                    method=method,
                    path=url,
                    detail=detail,
                )
                return _integrity_error_response(record)
            self._append_request_observed(
                provider_name=provider.name,
                method=method,
                path=url,
                status_code=resp.status_code,
                tool_endpoint=True,
                examined=False,
                forwarded=True,
                request_body=body,
                detail=f"developer mode forwarded: {detail}",
            )
            return resp.status_code, resp_headers, resp_body

        tool_calls = provider.extract_tool_calls(data)
        if not tool_calls:
            self._append_request_observed(
                provider_name=provider.name,
                method=method,
                path=url,
                status_code=resp.status_code,
                tool_endpoint=True,
                examined=True,
                forwarded=True,
                request_body=body,
                detail="recognized response contained no tool calls",
            )
            return resp.status_code, resp_headers, resp_body

        denials: list[tuple[ToolCall, str, str]] = []
        approval_store = self._get_approval_store()
        for tc in tool_calls:
            record = mediate_decision(
                tc.tool_name,
                tc.args,
                policy=self._policy,
                chain_recorder=self._chain_recorder,
                approval_store=approval_store,
                session_id=self._session_id,
                user_identity=self._user_identity,
                provider_name=provider.name,
                integrity_monitor=self._integrity_monitor,
                qa_gate=self._qa_gate,
            )

            if _is_blocking_record(record):
                reasons = record.get("policy_reasons", [])
                reason_text = reasons[0].get("detail", "policy denied") if reasons else "policy denied"
                denials.append((tc, reason_text, record.get("matched_rule", "")))

        if denials:
            data = provider.apply_denials(data, denials)
            resp_body = json.dumps(data).encode()
            resp_headers = self._forward_response_headers(resp_headers, resp_body)

        return resp.status_code, resp_headers, resp_body

    async def _handle_streaming_buffered(
        self, url: str, headers: dict, body: bytes,
    ) -> tuple[int, dict, bytes]:
        """Handle a streaming request with full buffering (legacy Anthropic)."""
        collector = StreamingToolCollector(
            self._policy, self._chain_recorder,
            self._session_id, self._user_identity,
            approval_store=self._get_approval_store(),
            integrity_monitor=self._integrity_monitor,
            qa_gate=self._qa_gate,
        )

        output_chunks: list[bytes] = []
        buffered_events: dict[int, list[bytes]] = {}
        resp_status = 200
        resp_headers: dict = {}
        tool_block_count = 0

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", url, headers=headers, content=body,
            ) as resp:
                resp_status = resp.status_code
                resp_headers = dict(resp.headers)

                if resp_status != 200:
                    content = await resp.aread()
                    # QS-053: record every request, including buffered-streaming non-200s.
                    self._append_request_observed(
                        provider_name="anthropic", method="POST", path=url,
                        status_code=resp_status, tool_endpoint=True,
                        examined=False, forwarded=True, request_body=body,
                        detail="buffered streaming upstream non-200 response",
                    )
                    return resp_status, self._forward_response_headers(resp_headers, content), content

                current_event_type = ""
                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()

                    if not line:
                        continue

                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                        continue

                    if line.startswith("data:"):
                        data_str = line[5:].strip()

                        if data_str == "[DONE]":
                            output_chunks.append(b"event: done\ndata: [DONE]\n\n")
                            continue

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            output_chunks.append(
                                f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                            )
                            continue

                        action = collector.process_event(current_event_type, data)

                        if action == "buffer":
                            idx = data.get("index", 0)
                            if data.get("type") == "content_block_start":
                                tool_block_count += 1
                            buffered_events.setdefault(idx, []).append(
                                f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                            )

                        elif action == "replace":
                            idx = data.get("index", 0)
                            for event_bytes in collector.get_replacement_events(idx):
                                output_chunks.append(event_bytes)
                            buffered_events.pop(idx, None)

                        elif action == "pass":
                            msg_type = data.get("type", "")
                            idx = data.get("index", 0)

                            if msg_type == "content_block_stop" and idx in buffered_events:
                                for event_bytes in buffered_events.pop(idx):
                                    output_chunks.append(event_bytes)
                                output_chunks.append(
                                    f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                                )
                            else:
                                output_chunks.append(
                                    f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                                )

        full_body = b"".join(output_chunks)

        # QS-053: record the request even when the buffered stream carried no tool call.
        if tool_block_count == 0:
            self._append_request_observed(
                provider_name="anthropic", method="POST", path=url,
                status_code=resp_status, tool_endpoint=True,
                examined=True, forwarded=True, request_body=body,
                detail="recognized buffered streaming response contained no tool_use blocks",
            )

        stream_headers = {
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
            "connection": "keep-alive",
        }
        for key in ("x-request-id", "request-id"):
            if key in resp_headers:
                stream_headers[key] = resp_headers[key]

        return resp_status, stream_headers, full_body

    async def _handle_streaming_buffered_provider(
        self, url: str, headers: dict, body: bytes,
        provider: BaseProvider,
    ) -> tuple[int, dict, bytes]:
        """Handle streaming with full buffering via provider interface."""
        collector = provider.create_streaming_collector()
        output_chunks: list[bytes] = []
        resp_status = 200
        resp_headers: dict = {}
        approval_store = self._get_approval_store()
        tool_call_count = 0

        # QS-061: per-provider timeout — Ollama defaults to 300s.
        async with httpx.AsyncClient(
            timeout=provider_timeout_seconds(provider.name, self._provider_config)
        ) as client:
            async with client.stream(
                "POST", url, headers=headers, content=body,
            ) as resp:
                resp_status = resp.status_code
                resp_headers = dict(resp.headers)

                if resp_status != 200:
                    content = await resp.aread()
                    # QS-053: record every request, including buffered-streaming non-200s.
                    self._append_request_observed(
                        provider_name=provider.name, method="POST", path=url,
                        status_code=resp_status, tool_endpoint=True,
                        examined=False, forwarded=True, request_body=body,
                        detail="buffered streaming upstream non-200 response",
                    )
                    return resp_status, self._forward_response_headers(resp_headers, content), content

                current_event_type = ""
                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue

                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()

                    if data_str == "[DONE]":
                        output_chunks.append(b"event: done\ndata: [DONE]\n\n")
                        continue

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError as exc:
                        if not developer_mode_active():
                            record = self._append_unexaminable_error(
                                provider_name=provider.name,
                                method="POST",
                                path=url,
                                detail=f"stream JSON parse failed: {exc}",
                            )
                            return _integrity_error_response(record)
                        output_chunks.append(
                            f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                        )
                        continue

                    event_bytes = f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                    stream_action = collector.process_event(current_event_type, data)

                    if stream_action.action == "buffer":
                        collector.add_buffered_event(stream_action.index, event_bytes)
                        if stream_action.completed_tool_call:
                            tool_call_count += 1
                            tc = stream_action.completed_tool_call
                            record = mediate_decision(
                                tc.tool_name, tc.args,
                                policy=self._policy,
                                chain_recorder=self._chain_recorder,
                                approval_store=approval_store,
                                session_id=self._session_id,
                                user_identity=self._user_identity,
                                provider_name=provider.name,
                                integrity_monitor=self._integrity_monitor,
                                qa_gate=self._qa_gate,
                            )

                            if _is_blocking_record(record):
                                reasons = record.get("policy_reasons", [])
                                reason_text = reasons[0].get("detail", "policy denied") if reasons else "policy denied"
                                for denial_event in collector.build_denial_events(
                                    stream_action.index, tc,
                                    reason_text, record.get("matched_rule", ""),
                                ):
                                    output_chunks.append(denial_event)
                            else:
                                for buf_event in collector.get_buffered_events(stream_action.index):
                                    output_chunks.append(buf_event)
                                output_chunks.append(event_bytes)

                    elif stream_action.action == "pass":
                        output_chunks.append(event_bytes)

        full_body = b"".join(output_chunks)

        # QS-053: record the request even when the buffered stream carried no tool call.
        if tool_call_count == 0:
            self._append_request_observed(
                provider_name=provider.name, method="POST", path=url,
                status_code=resp_status, tool_endpoint=True,
                examined=True, forwarded=True, request_body=body,
                detail="recognized buffered streaming response contained no tool calls",
            )

        stream_headers = {
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
            "connection": "keep-alive",
        }
        for key in ("x-request-id", "request-id"):
            if key in resp_headers:
                stream_headers[key] = resp_headers[key]

        return resp_status, stream_headers, full_body


# ---------------------------------------------------------------------------
# ASGI-like HTTP server using asyncio
# ---------------------------------------------------------------------------


class ProxyServer:
    """Minimal async HTTP server wrapping GovernanceProxy."""

    def __init__(self, proxy: GovernanceProxy, host: str, port: int):
        self._proxy = proxy
        self._host = host
        self._port = port

    async def _handle_client(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter):
        try:
            request_line = await asyncio.wait_for(
                reader.readline(), timeout=30.0
            )
            if not request_line:
                writer.close()
                return

            parts = request_line.decode("utf-8", errors="replace").strip().split(" ")
            if len(parts) < 3:
                writer.close()
                return

            method = parts[0]
            raw_path = parts[1]

            # Route to provider by URL prefix
            provider = None
            path = raw_path
            try:
                provider, path = resolve_provider(raw_path)
            except ValueError:
                # No provider prefix matched — try legacy /anthropic fallback
                if raw_path.startswith("/anthropic"):
                    path = raw_path[len("/anthropic"):]
                    if not path:
                        path = "/"
                # else: pass raw_path through as-is (non-provider endpoint)

            # Read headers
            headers: dict[str, str] = {}
            while True:
                header_line = await asyncio.wait_for(
                    reader.readline(), timeout=10.0
                )
                line_str = header_line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    break
                if ":" in line_str:
                    key, value = line_str.split(":", 1)
                    headers[key.strip().lower()] = value.strip()

            if _is_websocket_upgrade(headers):
                if provider is None:
                    err_body = json.dumps({"error": "unsupported websocket provider path"}).encode()
                    writer.write(b"HTTP/1.1 404 Not Found\r\n")
                    writer.write(b"content-type: application/json\r\n")
                    writer.write(f"content-length: {len(err_body)}\r\n".encode())
                    writer.write(b"\r\n")
                    writer.write(err_body)
                    await writer.drain()
                    return
                if provider.name != "openai" or not provider.is_tool_endpoint(path):
                    err_body = json.dumps({"error": "unsupported websocket endpoint"}).encode()
                    self._proxy._append_request_observed(
                        provider_name=provider.name, method="WS", path=path,
                        status_code=404, tool_endpoint=provider.is_tool_endpoint(path),
                        examined=False, forwarded=False, request_body=b"",
                        detail="unsupported websocket endpoint",
                    )
                    writer.write(b"HTTP/1.1 404 Not Found\r\n")
                    writer.write(b"content-type: application/json\r\n")
                    writer.write(f"content-length: {len(err_body)}\r\n".encode())
                    writer.write(b"\r\n")
                    writer.write(err_body)
                    await writer.drain()
                    return
                logger.info("WebSocket request (%s): %s %s", provider.name, method, path)
                await self._proxy.handle_websocket(path, headers, reader, writer, provider)
                return

            # Read body (with size limit)
            body = b""
            content_length = int(headers.get("content-length", "0"))
            if content_length > MAX_REQUEST_BODY_BYTES:
                logger.warning("Request body too large: %d bytes (limit %d)",
                               content_length, MAX_REQUEST_BODY_BYTES)
                err_body = json.dumps({"error": "request body too large"}).encode()
                writer.write(b"HTTP/1.1 413 Content Too Large\r\n")
                writer.write(b"content-type: application/json\r\n")
                writer.write(f"content-length: {len(err_body)}\r\n".encode())
                writer.write(b"\r\n")
                writer.write(err_body)
                await writer.drain()
                return
            if content_length > 0:
                body = await asyncio.wait_for(
                    reader.readexactly(content_length), timeout=60.0
                )
            elif headers.get("transfer-encoding", "").lower() == "chunked":
                chunks = []
                total_chunked = 0
                while True:
                    size_line = await asyncio.wait_for(
                        reader.readline(), timeout=30.0
                    )
                    chunk_size = int(size_line.strip(), 16)
                    if chunk_size == 0:
                        await reader.readline()
                        break
                    total_chunked += chunk_size
                    if total_chunked > MAX_REQUEST_BODY_BYTES:
                        logger.warning("Chunked request body too large: %d+ bytes (limit %d)",
                                       total_chunked, MAX_REQUEST_BODY_BYTES)
                        err_body = json.dumps({"error": "request body too large"}).encode()
                        writer.write(b"HTTP/1.1 413 Content Too Large\r\n")
                        writer.write(b"content-type: application/json\r\n")
                        writer.write(f"content-length: {len(err_body)}\r\n".encode())
                        writer.write(b"\r\n")
                        writer.write(err_body)
                        await writer.drain()
                        return
                    chunk_data = await asyncio.wait_for(
                        reader.readexactly(chunk_size), timeout=30.0
                    )
                    await reader.readline()
                    chunks.append(chunk_data)
                body = b"".join(chunks)

            if provider is not None:
                # Provider-aware path
                forward_headers = provider.forward_headers(headers)
                is_tool_ep = provider.is_tool_endpoint(path)
                is_streaming = False
                if is_tool_ep and body:
                    is_streaming = provider.is_streaming(body)
                if hasattr(provider, 'is_streaming_path') and provider.is_streaming_path(path):
                    is_streaming = True

                logger.info("Request (%s): %s %s tool_ep=%s streaming=%s body_len=%d",
                            provider.name, method, path[:60], is_tool_ep, is_streaming, len(body))

                if is_streaming:
                    await self._proxy.handle_streaming_to_writer(
                        path, headers, body, writer, provider=provider
                    )
                else:
                    status, resp_headers, resp_body = await self._proxy.handle_request(
                        method, path, headers, body, provider=provider
                    )
                    status_text = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "OK"
                    writer.write(f"HTTP/1.1 {status} {status_text}\r\n".encode())
                    for k, v in resp_headers.items():
                        if k.lower() not in ("transfer-encoding",):
                            writer.write(f"{k}: {v}\r\n".encode())
                    if "content-length" not in {k.lower() for k in resp_headers}:
                        writer.write(f"content-length: {len(resp_body)}\r\n".encode())
                    writer.write(b"\r\n")
                    writer.write(resp_body)
                    await writer.drain()
            else:
                # Legacy Anthropic-only path (no provider prefix matched)
                forward_headers = {}
                for k, v in headers.items():
                    if k == "x-api-key":
                        forward_headers["x-api-key"] = v
                    elif k == "anthropic-version":
                        forward_headers["anthropic-version"] = v
                    elif k == "anthropic-beta":
                        forward_headers["anthropic-beta"] = v
                    elif k == "content-type":
                        forward_headers["content-type"] = v
                    elif k == "authorization":
                        forward_headers["authorization"] = v
                    elif k == "accept":
                        forward_headers["accept"] = v

                is_streaming = False
                path_base = path.split("?")[0]
                is_messages = path_base.rstrip("/").endswith("/v1/messages")
                if is_messages and body:
                    try:
                        is_streaming = json.loads(body).get("stream", False)
                    except (json.JSONDecodeError, AttributeError) as e:
                        logger.warning("Failed to parse request body for streaming detection: %s (body_len=%d)", e, len(body))

                logger.info("Request: %s %s messages=%s streaming=%s body_len=%d",
                            method, path[:60], is_messages, is_streaming, len(body))

                if is_streaming:
                    await self._proxy.handle_streaming_to_writer(
                        path, forward_headers, body, writer
                    )
                else:
                    status, resp_headers, resp_body = await self._proxy.handle_request(
                        method, path, forward_headers, body
                    )
                    status_text = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "OK"
                    writer.write(f"HTTP/1.1 {status} {status_text}\r\n".encode())
                    for k, v in resp_headers.items():
                        if k.lower() not in ("transfer-encoding",):
                            writer.write(f"{k}: {v}\r\n".encode())
                    if "content-length" not in {k.lower() for k in resp_headers}:
                        writer.write(f"content-length: {len(resp_body)}\r\n".encode())
                    writer.write(b"\r\n")
                    writer.write(resp_body)
                    await writer.drain()

        except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as exc:
            logger.error("Request handling error: %s", exc, exc_info=True)
            try:
                err_body = json.dumps({"error": "internal proxy error"}).encode()
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n")
                writer.write(b"content-type: application/json\r\n")
                writer.write(f"content-length: {len(err_body)}\r\n".encode())
                writer.write(b"\r\n")
                writer.write(err_body)
                await writer.drain()
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self):
        server = await asyncio.start_server(
            self._handle_client, self._host, self._port
        )
        logger.info(
            "Atested governance proxy listening on http://%s:%d",
            self._host, self._port,
        )
        logger.info(
            "Providers: /anthropic /openai /gemini /litellm"
        )
        logger.info(
            "Configure your agent: ANTHROPIC_BASE_URL=http://%s:%d/anthropic",
            self._host, self._port,
        )
        async with server:
            await server.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Atested API governance proxy")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    parser.add_argument("--upstream", default=ANTHROPIC_API_BASE,
                        help="Upstream API base URL (alias for --anthropic-upstream, kept for backward compat)")
    parser.add_argument("--anthropic-upstream", default=None,
                        help="Anthropic upstream base URL (default: https://api.anthropic.com)")
    parser.add_argument("--openai-upstream",
                        default=os.environ.get("OPENAI_UPSTREAM", "https://api.openai.com"),
                        help="OpenAI upstream base URL")
    parser.add_argument("--gemini-upstream",
                        default=os.environ.get("GEMINI_UPSTREAM", "https://generativelanguage.googleapis.com"),
                        help="Gemini upstream base URL")
    parser.add_argument("--litellm-upstream",
                        default=os.environ.get("LITELLM_UPSTREAM", ""),
                        help="LiteLLM upstream base URL (required for /litellm route)")
    parser.add_argument("--ollama-upstream",
                        default=os.environ.get("OLLAMA_UPSTREAM", "http://localhost:11434"),
                        help="Ollama upstream base URL (default: http://localhost:11434)")
    parser.add_argument("--ollama-timeout",
                        type=float,
                        default=float(os.environ.get("OLLAMA_TIMEOUT", DEFAULT_OLLAMA_TIMEOUT_SECONDS)),
                        help=(
                            "Per-request timeout in seconds for the Ollama provider "
                            f"(default: {int(DEFAULT_OLLAMA_TIMEOUT_SECONDS)}s, env: OLLAMA_TIMEOUT). "
                            "Set higher than the 120s cloud default because local "
                            "Ollama inference is slower, especially for the first token."
                        ))
    parser.add_argument("--user-identity", default="",
                        help="User identity for chain records (default: system hostname)")
    parser.add_argument("--session-id", default="", help="Session ID for chain records")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # INV-005: Proxy records are trust-grade and MUST be signed.
    # Refuse to start without a valid signing key — no silent degradation.
    if _SIGNING_KEY is None:
        key_path = (read_env_preferred("ATESTED_SIGNING_KEY_PATH", "GOV_SIGNING_KEY_PATH") or "").strip()
        if not key_path:
            logger.error(
                "No signing key found — proxy requires a signing key (INV-005). "
                "Run 'python3 scripts/atested_cli.py init' to generate one, "
                "or set GOV_SIGNING_KEY_PATH to an existing Ed25519 PEM file."
            )
        else:
            logger.error("Failed to load signing key from %s — proxy requires a valid key (INV-005)", key_path)
        sys.exit(1)

    # Verify API key is available
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — proxy will forward requests without adding auth")

    # Setup chain recorder
    runtime = runtime_root(REPO)
    identity = ensure_machine_identity(REPO, role="primary", signing_key_id=_SIGNING_KEY_ID)
    ensure_primary_machine_registry(REPO, identity=identity, public_key_fingerprint=_SIGNING_KEY_ID)
    chain_path = runtime / "LOGS" / "decision-chain.jsonl"
    integrity_monitor = IntegrityMonitor(chain_path)
    startup_archive_manifest = None
    try:
        integrity_monitor.verify_startup_chain()
    except IntegrityViolation as exc:
        logger.error("Startup chain integrity violation; archiving and starting fresh: %s", exc)
        try:
            from chain_archive import archive_chain
            # write_genesis=False: the proxy appends its own signed
            # chain_started_after_archive below (lines that follow), with the
            # decision signing key and full request context. archive_chain
            # must not also write an unsigned genesis or the decision chain
            # would carry two genesis records.
            startup_archive_manifest = archive_chain(
                chain_path,
                reason="startup_integrity_violation",
                payload={"error": str(exc)},
                sidecar_events_path=integrity_monitor.events_path,
                write_genesis=False,
            )
            integrity_monitor = IntegrityMonitor(chain_path)
            integrity_monitor.save_chain_summary(integrity_monitor.summarize_chain())
        except Exception as archive_exc:
            logger.error("Unable to archive compromised chain: %s", archive_exc)
            sys.exit(1)
    chain_recorder = ChainRecorder(chain_path, integrity_monitor=integrity_monitor)

    # Resolve user identity: explicit flag > env var > hostname
    user_identity = (
        args.user_identity
        or os.environ.get("ATESTED_USER_LABEL", "")
        or platform.node()
    )
    logger.info("User identity: %s", user_identity)

    # Resolve Anthropic upstream: explicit --anthropic-upstream > --upstream
    anthropic_upstream = args.anthropic_upstream or args.upstream

    # Build provider config
    provider_config = {
        "anthropic_upstream": anthropic_upstream,
        "openai_upstream": args.openai_upstream,
        "gemini_upstream": args.gemini_upstream,
        "litellm_upstream": args.litellm_upstream,
        "ollama_upstream": args.ollama_upstream,
        # QS-061: per-provider timeout. Read by provider_timeout_seconds()
        # when each upstream call constructs an httpx client.
        "ollama_timeout_seconds": args.ollama_timeout,
    }

    logger.info(
        "Provider upstreams: anthropic=%s openai=%s gemini=%s litellm=%s ollama=%s (timeout=%.0fs)",
        anthropic_upstream, args.openai_upstream, args.gemini_upstream,
        args.litellm_upstream or "(not configured)",
        args.ollama_upstream, args.ollama_timeout,
    )

    # Warn about non-HTTPS upstreams (informational — proxy starts regardless).
    # Ollama is special-cased: it runs locally and ships without TLS, so an
    # http://localhost:11434 default is expected and not a deployment risk.
    for provider_label, upstream_url in [
        ("anthropic", anthropic_upstream),
        ("openai", args.openai_upstream),
        ("gemini", args.gemini_upstream),
        ("litellm", args.litellm_upstream),
        ("ollama", args.ollama_upstream),
    ]:
        if not upstream_url or not upstream_url.startswith("http://"):
            continue
        if provider_label == "ollama":
            from urllib.parse import urlsplit
            host = (urlsplit(upstream_url).hostname or "").lower()
            if host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}:
                continue
        logger.warning(
            "WARNING: upstream for %s is not using HTTPS — "
            "traffic to this provider will be unencrypted: %s",
            provider_label, upstream_url,
        )

    try:
        if startup_archive_manifest is not None:
            chain_recorder.append_integrity_event(
                "chain_started_after_archive",
                {
                    "archive_id": startup_archive_manifest.get("archive_id", ""),
                    "archive_manifest_path": startup_archive_manifest.get("manifest_path", ""),
                    "archive_chain_path": startup_archive_manifest.get("archive_chain_path", ""),
                    "archive_reason": startup_archive_manifest.get("reason", ""),
                    "archived_record_count": startup_archive_manifest.get("record_count", 0),
                    "user_identity": user_identity,
                    "session_id": args.session_id,
                },
            )
        startup_hashes = record_startup_integrity_events(
            chain_recorder,
            integrity_monitor,
            user_identity=user_identity,
            session_id=args.session_id,
        )
        logger.info(
            "Integrity startup hashes: proxy=%s policy=%s",
            startup_hashes["current_proxy_code_hash"],
            startup_hashes["current_policy_rules_hash"],
        )
    except IntegrityViolation as exc:
        logger.error("Refusing to start: %s", exc)
        sys.exit(1)

    # QS-033 A2: signal proxy readiness AFTER startup events are written so
    # the supervisor (and the quality service it starts next) sees a chain
    # tail that already reflects the current policy_rules_hash. Failure to
    # write the marker is non-fatal — when the proxy is launched outside the
    # supervisor, the env var is unset and this is a no-op.
    proxy_ready_path = os.environ.get("ATESTED_PROXY_READY_FILE", "").strip()
    if proxy_ready_path:
        try:
            ready_path = Path(proxy_ready_path)
            ready_path.parent.mkdir(parents=True, exist_ok=True)
            ready_path.write_text("ready\n", encoding="utf-8")
        except OSError as exc:
            logger.warning(
                "Failed to write proxy ready file %s: %s", proxy_ready_path, exc
            )

    policy = GovernanceProxy._load_default_policy()
    qa_chain_path = Path(
        (read_env_preferred("ATESTED_QA_CHAIN_PATH", "GOV_QA_CHAIN_PATH") or "").strip()
        or runtime / "LOGS" / "qa-chain.jsonl"
    )
    qa_gate = ProxyQualityGate(
        QAChainTailReader(qa_chain_path),
        expected_policy_rules_hash=compute_policy_rules_hash(load_policy_rules(None)),
        expected_capability_registry_hash=compute_capability_registry_hash(),
        stale_cycles=int(os.environ.get("GOV_QA_STALE_CYCLES", "3")),
        heartbeat_seconds=float(os.environ.get("GOV_QA_HEARTBEAT_SECONDS", "30")),
    )

    proxy = GovernanceProxy(
        upstream_base=anthropic_upstream,
        policy=policy,
        chain_recorder=chain_recorder,
        chain_path=chain_path,
        session_id=args.session_id,
        user_identity=user_identity,
        provider_config=provider_config,
        integrity_monitor=integrity_monitor,
        qa_gate=qa_gate,
    )

    server = ProxyServer(proxy, args.host, args.port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Proxy shutting down")


def record_startup_integrity_events(
    chain_recorder: ChainRecorder,
    integrity_monitor: IntegrityMonitor,
    *,
    user_identity: str = "",
    session_id: str = "",
) -> dict:
    """Record startup code and policy hashes, including visible code changes."""
    hashes = integrity_monitor.startup_hashes()
    previous_code_hash = hashes.get("previous_proxy_code_hash")
    current_code_hash = hashes["current_proxy_code_hash"]
    if previous_code_hash and previous_code_hash != current_code_hash:
        chain_recorder.append_integrity_event(
            "proxy_code_hash_changed",
            {
                "previous_proxy_code_hash": previous_code_hash,
                "current_proxy_code_hash": current_code_hash,
                "code_paths": hashes["code_paths"],
                "user_identity": user_identity,
                "session_id": session_id,
            },
        )
    # SEC-2026-002: include metadata_hash so the signed event binds the
    # integrity metadata to the chain, preventing silent replacement.
    current_metadata = integrity_monitor.load_metadata() or {}
    # Product version from VERSION file
    _version_file = REPO / "VERSION"
    _product_version = _version_file.read_text(encoding="utf-8").strip() if _version_file.exists() else ""
    startup_payload = {
        "current_proxy_code_hash": current_code_hash,
        "code_paths": hashes["code_paths"],
        "metadata_hash": current_metadata.get("metadata_hash"),
        "product_version": _product_version,
        "user_identity": user_identity,
        "session_id": session_id,
    }
    if hashes.get("current_data_hash"):
        startup_payload["current_data_hash"] = hashes["current_data_hash"]
        startup_payload["data_paths"] = hashes.get("data_paths", [])
    chain_recorder.append_integrity_event(
        "proxy_startup_code_hash",
        startup_payload,
    )
    # QS-033 A2: include policy_rules_hash + capability_registry_hash so the
    # quality service's env gate (last_governance_chain_hash → policy_rules_hash
    # / capability_registry_hash) finds the current hashes at the chain tail
    # immediately after the proxy starts, even before the first tool call.
    # Two policy-hash semantics live in this record:
    #   - current_policy_rules_hash: raw sha256 of the policy file bytes,
    #     produced by IntegrityMonitor. Kept for downstream readers that
    #     already use that name to detect file-level tampering.
    #   - policy_rules_hash: canonical-form hash of the parsed policy
    #     (compute_policy_rules_hash), which is what the QS env gate (and
    #     proxy QA gate) compute and compare. Without this distinction the
    #     two values never match and ENV-001 fails on every startup.
    current_policy_hash = hashes["current_policy_rules_hash"]
    canonical_policy_hash = compute_policy_rules_hash(load_policy_rules(Path(hashes["policy_path"])))
    current_cap_hash = compute_capability_registry_hash()
    chain_recorder.append_integrity_event(
        "policy_rules_loaded",
        {
            "current_policy_rules_hash": current_policy_hash,
            "policy_rules_hash": canonical_policy_hash,
            "capability_registry_hash": current_cap_hash,
            "policy_path": hashes["policy_path"],
            "user_identity": user_identity,
            "session_id": session_id,
        },
    )
    # Commit startup hashes to metadata AFTER events are written.
    # This ensures expected_record_count in metadata already reflects
    # the startup events (via refresh_after_chain_write in append_atomic),
    # preventing chain_record_count_mismatch on the first tool call.
    integrity_monitor.commit_startup_hashes()
    return hashes


if __name__ == "__main__":
    main()
