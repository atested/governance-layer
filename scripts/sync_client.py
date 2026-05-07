#!/usr/bin/env python3
"""Remote-side sync client for multi-machine governance."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

try:
    from machine_identity import ensure_machine_identity
    from remote_import import CURRENT_CHAIN_SEGMENT, compute_segment_id
    from storage_contract import runtime_root
    from sync_protocol import (
        SYNC_PROTOCOL_VERSION,
        b64encode,
        canonical_json,
        now_utc_z,
        private_key_fingerprint,
        private_key_public_pem,
        sha256_bytes,
        sign_segment_request,
        verify_response_signature,
    )
except ImportError:  # pragma: no cover - package import path
    from scripts.machine_identity import ensure_machine_identity
    from scripts.remote_import import CURRENT_CHAIN_SEGMENT, compute_segment_id
    from scripts.storage_contract import runtime_root
    from scripts.sync_protocol import (
        SYNC_PROTOCOL_VERSION,
        b64encode,
        canonical_json,
        now_utc_z,
        private_key_fingerprint,
        private_key_public_pem,
        sha256_bytes,
        sign_segment_request,
        verify_response_signature,
    )


class SyncClientError(RuntimeError):
    pass


class SyncClient:
    def __init__(
        self,
        repo_root: Path,
        primary_base_url: str,
        *,
        remote_private_key,
        source_machine_id: Optional[str] = None,
        primary_public_key_pem: Optional[str] = None,
        timeout_seconds: int = 10,
    ):
        self.repo_root = Path(repo_root)
        self.primary_base_url = primary_base_url.rstrip("/")
        self.remote_private_key = remote_private_key
        self.source_machine_id = source_machine_id
        self.primary_public_key_pem = primary_public_key_pem
        self.timeout_seconds = timeout_seconds
        self.request_number = 0
        self.session: Optional[dict] = None

    def start_session(self) -> dict:
        key_id = private_key_fingerprint(self.remote_private_key)
        source_machine_id = self._source_machine_id(key_id)
        payload = {
            "source_machine_id": source_machine_id,
            "source_machine_key_id": key_id,
            "source_machine_public_key_pem": private_key_public_pem(self.remote_private_key),
            "protocol_version": SYNC_PROTOCOL_VERSION,
            "product_version": _current_version(self.repo_root),
            "timestamp_utc": now_utc_z(),
        }
        response = self._post("/sync/v1/session/start", payload)
        if not response.get("accepted"):
            raise SyncClientError(str(response.get("error") or "SESSION_REJECTED"))
        self._verify_response("/sync/v1/session/start", response)
        self.session = response
        self.request_number = 0
        return response

    def sync_current_segment(self, records_jsonl: bytes, *, segment_kind: str = CURRENT_CHAIN_SEGMENT) -> dict:
        if self.session is None:
            self.start_session()
        assert self.session is not None
        raw = records_jsonl
        stored_sha = sha256_bytes(raw)
        first_hash, last_hash, count = _segment_hash_bounds(raw)
        key_id = private_key_fingerprint(self.remote_private_key)
        source_machine_id = self._source_machine_id(key_id)
        segment_id = compute_segment_id(
            source_machine_id,
            segment_kind,
            first_hash,
            last_hash,
            count,
            stored_sha,
        )
        self.request_number += 1
        payload = {
            "sync_session_id": self.session["sync_session_id"],
            "request_number": self.request_number,
            "timestamp_utc": now_utc_z(),
            "source_machine_id": source_machine_id,
            "segment_id": segment_id,
            "segment_kind": segment_kind,
            "segment_sha256": stored_sha,
            "records_jsonl_b64": b64encode(raw),
            "archive_manifest": None,
        }
        signed = sign_segment_request(
            "POST",
            "/sync/v1/segment",
            payload,
            self.session["nonce"],
            self.remote_private_key,
        )
        response = self._post("/sync/v1/segment", signed)
        if not response.get("accepted"):
            raise SyncClientError(str(response.get("error") or response.get("errors") or "SEGMENT_REJECTED"))
        self._verify_response("/sync/v1/segment", response)
        store_state_bundle(self.repo_root, response)
        return response

    def finish_session(self) -> dict:
        if self.session is None:
            return {"accepted": False}
        response = self._post("/sync/v1/session/finish", {"sync_session_id": self.session["sync_session_id"]})
        self._verify_response("/sync/v1/session/finish", response)
        self.session = None
        return response

    def _post(self, path: str, payload: dict) -> dict:
        body = canonical_json(payload).encode("utf-8")
        request = urllib.request.Request(
            self.primary_base_url + path,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            raw = exc.read()
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SyncClientError(f"INVALID_RESPONSE:{exc}") from exc
        if not isinstance(parsed, dict):
            raise SyncClientError("INVALID_RESPONSE_OBJECT")
        return parsed

    def _verify_response(self, path: str, response: dict) -> None:
        if self.primary_public_key_pem and not verify_response_signature(path, response, self.primary_public_key_pem):
            raise SyncClientError("PRIMARY_SIGNATURE_INVALID")

    def _source_machine_id(self, key_id: str) -> str:
        if self.source_machine_id:
            return self.source_machine_id
        return ensure_machine_identity(self.repo_root, role="remote", signing_key_id=key_id)["machine_id"]


def store_state_bundle(repo_root: Path, bundle: dict) -> None:
    sync_dir = runtime_root(repo_root) / "sync"
    sync_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "received_at_utc": now_utc_z(),
        "approval_store": bundle.get("approval_store"),
        "approval_store_hash": bundle.get("approval_store_hash"),
        "policy_rules": bundle.get("policy_rules"),
        "policy_rules_hash": bundle.get("policy_rules_hash"),
        "communications": bundle.get("communications", []),
        "version_info": bundle.get("version_info", {}),
        "machine_registry_hash": bundle.get("machine_registry_hash"),
        "machine_registry": bundle.get("machine_registry", {}),
    }
    _write_json(sync_dir / "state_bundle.json", state)
    _write_json(sync_dir / "approval_store_snapshot.json", {
        "approval_store": state["approval_store"],
        "approval_store_hash": state["approval_store_hash"],
        "received_at_utc": state["received_at_utc"],
    })
    _write_json(sync_dir / "policy_rules_snapshot.json", {
        "policy_rules": state["policy_rules"],
        "policy_rules_hash": state["policy_rules_hash"],
        "received_at_utc": state["received_at_utc"],
    })


def _segment_hash_bounds(records_jsonl: bytes) -> tuple[str, str, int]:
    records = []
    for line in records_jsonl.decode("utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            if not isinstance(record, dict):
                raise SyncClientError("SEGMENT_RECORD_NOT_OBJECT")
            records.append(record)
    if not records:
        raise SyncClientError("SEGMENT_EMPTY")
    first_hash = records[0].get("record_hash")
    last_hash = records[-1].get("record_hash")
    if not isinstance(first_hash, str) or not isinstance(last_hash, str):
        raise SyncClientError("SEGMENT_HASH_BOUNDS_MISSING")
    return first_hash, last_hash, len(records)


def _current_version(repo_root: Path) -> str:
    path = repo_root / "VERSION"
    return path.read_text(encoding="utf-8").strip() if path.exists() else "0.0.0"


def _write_json(path: Path, payload: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
