#!/usr/bin/env python3
"""Primary-side HTTP sync service for multi-machine governance."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

try:
    from approval_store import approval_store_hash, load_approval_store_from_chain
    from machine_identity import authorized_machine_lookup, ensure_machine_identity, load_machine_registry, save_machine_registry
    from policy_eval_v2 import compute_policy_rules_hash
    from remote_import import import_remote_segment, sha256_bytes
    from storage_contract import runtime_root
    from sync_protocol import (
        SYNC_PROTOCOL_VERSION,
        b64decode,
        canonical_json,
        now_utc_z,
        segment_request_preimage,
        sign_response,
        verify_preimage_signature,
    )
except ImportError:  # pragma: no cover - package import path
    from scripts.approval_store import approval_store_hash, load_approval_store_from_chain
    from scripts.machine_identity import authorized_machine_lookup, ensure_machine_identity, load_machine_registry, save_machine_registry
    from scripts.policy_eval_v2 import compute_policy_rules_hash
    from scripts.remote_import import import_remote_segment, sha256_bytes
    from scripts.storage_contract import runtime_root
    from scripts.sync_protocol import (
        SYNC_PROTOCOL_VERSION,
        b64decode,
        canonical_json,
        now_utc_z,
        segment_request_preimage,
        sign_response,
        verify_preimage_signature,
    )


DEFAULT_SYNC_HOST = "127.0.0.1"
DEFAULT_SYNC_PORT = 8765
SESSION_TTL_SECONDS = 600
MAX_SYNC_BODY_BYTES = 64 * 1024 * 1024


@dataclass
class SyncSession:
    sync_session_id: str
    nonce: str
    source_machine_id: str
    source_machine_key_id: str
    created_epoch: float
    last_request_number: int = 0
    segment_hashes: dict[str, str] = field(default_factory=dict)


class SyncService:
    """Stateful primary sync service used by the HTTP handler."""

    def __init__(
        self,
        repo_root: Path,
        *,
        primary_private_key=None,
        primary_signing_key_id: Optional[str] = None,
    ):
        self.repo_root = Path(repo_root)
        self.primary_private_key = primary_private_key
        self.primary_signing_key_id = primary_signing_key_id
        self._lock = threading.Lock()
        self._sessions: dict[str, SyncSession] = {}
        ensure_machine_identity(self.repo_root, role="primary", signing_key_id=primary_signing_key_id)

    def start_session(self, payload: dict) -> tuple[int, dict]:
        source_machine_id = str(payload.get("source_machine_id", "")).strip()
        source_machine_key_id = str(payload.get("source_machine_key_id", "")).strip()
        if not source_machine_id or not source_machine_key_id:
            return 400, {"accepted": False, "error": "MACHINE_ID_AND_KEY_REQUIRED"}

        session = SyncSession(
            sync_session_id=f"sync_{uuid.uuid4()}",
            nonce=uuid.uuid4().hex + uuid.uuid4().hex,
            source_machine_id=source_machine_id,
            source_machine_key_id=source_machine_key_id,
            created_epoch=time.time(),
        )
        with self._lock:
            self._sessions[session.sync_session_id] = session

        registry = load_machine_registry(self.repo_root) or {}
        response = {
            "accepted": True,
            "sync_session_id": session.sync_session_id,
            "nonce": session.nonce,
            "primary_machine_identity": ensure_machine_identity(self.repo_root, role="primary"),
            "supported_protocol_versions": [SYNC_PROTOCOL_VERSION],
            "machine_registry_hash": registry.get("registry_hash"),
        }
        return 200, self._maybe_sign("/sync/v1/session/start", response)

    def receive_segment(self, payload: dict) -> tuple[int, dict]:
        session_id = str(payload.get("sync_session_id", "")).strip()
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None:
            return 401, {"accepted": False, "error": "STALE_OR_UNKNOWN_SESSION"}
        if time.time() - session.created_epoch > SESSION_TTL_SECONDS:
            with self._lock:
                self._sessions.pop(session_id, None)
            return 401, {"accepted": False, "error": "STALE_OR_UNKNOWN_SESSION"}

        source_machine_id = str(payload.get("source_machine_id", "")).strip()
        if source_machine_id != session.source_machine_id:
            return 403, {"accepted": False, "error": "SESSION_MACHINE_MISMATCH"}

        request_number = payload.get("request_number")
        if not isinstance(request_number, int) or request_number <= session.last_request_number:
            return 409, {"accepted": False, "error": "REQUEST_NUMBER_REPLAY"}

        segment_id = str(payload.get("segment_id", "")).strip()
        segment_sha256 = str(payload.get("segment_sha256", "")).strip()
        if not segment_id or not segment_sha256:
            return 400, {"accepted": False, "error": "SEGMENT_ID_AND_HASH_REQUIRED"}
        if session.segment_hashes.get(segment_id) not in (None, segment_sha256):
            return 409, {"accepted": False, "error": "SEGMENT_ID_BODY_CONFLICT"}

        machine = authorized_machine_lookup(
            self.repo_root,
            source_machine_id,
            session.source_machine_key_id,
            at_utc=payload.get("timestamp_utc"),
        )
        if machine is None:
            return 403, {"accepted": False, "error": "MACHINE_NOT_AUTHORIZED"}
        public_key_pem = _public_key_pem_for(machine, session.source_machine_key_id)
        if not public_key_pem:
            return 403, {"accepted": False, "error": "PUBLIC_KEY_MISSING"}

        signature = payload.get("remote_signature")
        if not isinstance(signature, str) or not signature:
            return 401, {"accepted": False, "error": "REMOTE_SIGNATURE_REQUIRED"}
        preimage = segment_request_preimage("POST", "/sync/v1/segment", payload, session.nonce)
        if not verify_preimage_signature(preimage, signature, public_key_pem):
            return 401, {"accepted": False, "error": "REMOTE_SIGNATURE_INVALID"}

        try:
            records_jsonl = b64decode(str(payload.get("records_jsonl_b64", "")))
        except Exception:
            return 400, {"accepted": False, "error": "RECORDS_JSONL_B64_INVALID"}
        if sha256_bytes(records_jsonl) != segment_sha256:
            return 400, {"accepted": False, "error": "SEGMENT_SHA256_MISMATCH"}

        import_result = import_remote_segment(
            self.repo_root,
            source_machine_id=source_machine_id,
            segment_kind=str(payload.get("segment_kind") or "current_chain"),
            records_jsonl=records_jsonl,
            sync_session_id=session_id,
            segment_id=segment_id,
            archive_manifest=payload.get("archive_manifest"),
            signing_key=self.primary_private_key,
            signing_key_id=self.primary_signing_key_id,
        )
        if not import_result.accepted:
            return 422, {
                "accepted": False,
                "segment_id": segment_id,
                "errors": list(import_result.errors),
            }

        with self._lock:
            session.last_request_number = request_number
            session.segment_hashes[segment_id] = segment_sha256
        _mark_machine_synced(self.repo_root, source_machine_id)

        response = {
            "accepted": True,
            "segment_id": import_result.segment_id,
            "import_envelope_hash": import_result.import_envelope_hash,
            "duplicate": import_result.duplicate,
            **build_state_bundle(self.repo_root),
        }
        return 200, self._maybe_sign("/sync/v1/segment", response)

    def finish_session(self, payload: dict) -> tuple[int, dict]:
        session_id = str(payload.get("sync_session_id", "")).strip()
        with self._lock:
            existed = self._sessions.pop(session_id, None) is not None
        return 200, self._maybe_sign("/sync/v1/session/finish", {"accepted": existed})

    def _maybe_sign(self, path: str, response: dict) -> dict:
        if self.primary_private_key is None:
            return response
        return sign_response(path, response, self.primary_private_key, self.primary_signing_key_id)


def build_state_bundle(repo_root: Path) -> dict:
    runtime = runtime_root(repo_root)
    chain = runtime / "LOGS" / "decision-chain.jsonl"
    store = load_approval_store_from_chain(str(chain)) if chain.exists() else None
    policy_path = repo_root / "capabilities" / "policy-rules.json"
    try:
        policy_rules = json.loads(policy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        policy_rules = {}
    registry = load_machine_registry(repo_root) or {}
    return {
        "approval_store": {
            "approval_store_version": "0.1",
            "active_approvals": [] if store is None else store.all_approvals(),
        },
        "approval_store_hash": approval_store_hash(store),
        "policy_rules": policy_rules,
        "policy_rules_hash": compute_policy_rules_hash(policy_rules),
        "communications": _load_communications(runtime),
        "version_info": _load_version_info(repo_root),
        "machine_registry_hash": registry.get("registry_hash"),
        "machine_registry": registry,
    }


def run_sync_server(
    repo_root: Path,
    *,
    host: str = DEFAULT_SYNC_HOST,
    port: int = DEFAULT_SYNC_PORT,
    primary_private_key=None,
    primary_signing_key_id: Optional[str] = None,
):
    service = SyncService(
        repo_root,
        primary_private_key=primary_private_key,
        primary_signing_key_id=primary_signing_key_id,
    )
    server = _SyncHTTPServer((host, port), SyncHTTPRequestHandler, service)
    server.serve_forever()


class _SyncHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, sync_service: SyncService):
        self.sync_service = sync_service
        super().__init__(server_address, RequestHandlerClass)


class SyncHTTPRequestHandler(BaseHTTPRequestHandler):
    server: _SyncHTTPServer

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        payload = self._read_json()
        if payload is None:
            self._send_json({"accepted": False, "error": "INVALID_JSON"}, 400)
            return
        if self.path == "/sync/v1/session/start":
            status, response = self.server.sync_service.start_session(payload)
        elif self.path == "/sync/v1/segment":
            status, response = self.server.sync_service.receive_segment(payload)
        elif self.path == "/sync/v1/session/finish":
            status, response = self.server.sync_service.finish_session(payload)
        else:
            status, response = 404, {"accepted": False, "error": "NOT_FOUND"}
        self._send_json(response, status)

    def _read_json(self) -> Optional[dict]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return None
        if length < 0 or length > MAX_SYNC_BODY_BYTES:
            return None
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _send_json(self, payload: dict, status: int = 200) -> None:
        body = canonical_json(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _load_communications(runtime: Path) -> list[dict]:
    items: list[dict] = []
    for path in (
        runtime / "LOGS" / "communications_requests.jsonl",
        runtime / "LOGS" / "update_notifications.jsonl",
    ):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                items.append(record)
    return items[-100:]


def _load_version_info(repo_root: Path) -> dict:
    version_path = repo_root / "VERSION"
    current = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else "0.0.0"
    return {
        "current_version": current,
        "sync_protocol_version": SYNC_PROTOCOL_VERSION,
        "checked_at_utc": now_utc_z(),
    }


def _public_key_pem_for(machine: dict, key_id: str) -> Optional[str]:
    for key in machine.get("keys", []):
        if key.get("public_key_fingerprint") == key_id:
            value = key.get("public_key_pem")
            return value if isinstance(value, str) and value else None
    return None


def _mark_machine_synced(repo_root: Path, machine_id: str) -> None:
    registry = load_machine_registry(repo_root)
    if not registry:
        return
    for machine in registry.get("machines", []):
        if machine.get("machine_id") == machine_id:
            machine["last_sync_utc"] = now_utc_z()
            save_machine_registry(repo_root, registry)
            return
