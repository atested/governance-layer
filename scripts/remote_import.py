#!/usr/bin/env python3
"""Remote chain segment import verification and sidecar storage."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import threading
import time as _time_mod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    from storage_contract import runtime_root
    from event_model import (
        NON_ACTION_EVENT_TYPES,
        _compute_event_record_hash,
        build_non_action_event,
        canonical_json,
        sign_non_action_event,
    )
    from machine_identity import authorized_machine_lookup, canonical_json as registry_canonical_json
    from policy_eval_v2 import _compute_record_hash as compute_decision_record_hash
except ImportError:  # pragma: no cover - package import path
    from scripts.storage_contract import runtime_root
    from scripts.event_model import (
        NON_ACTION_EVENT_TYPES,
        _compute_event_record_hash,
        build_non_action_event,
        canonical_json,
        sign_non_action_event,
    )
    from scripts.machine_identity import authorized_machine_lookup, canonical_json as registry_canonical_json
    from scripts.policy_eval_v2 import _compute_record_hash as compute_decision_record_hash


IMPORT_ENVELOPE_VERSION = "multi_machine_import_v1"
CURRENT_CHAIN_SEGMENT = "current_chain"
ARCHIVE_SEGMENT = "archive"
JSONL_SEGMENT_FORMAT = "jsonl_segment_v1"
ARCHIVE_MANIFEST_FORMAT = "archive_manifest_v1"

_chain_lock = threading.Lock()


@dataclass(frozen=True)
class SegmentVerification:
    ok: bool
    errors: tuple[str, ...]
    records: tuple[dict, ...]
    first_record_hash: Optional[str]
    last_record_hash: Optional[str]
    record_count: int
    source_machine_key_id: Optional[str]


@dataclass(frozen=True)
class ImportResult:
    accepted: bool
    duplicate: bool
    segment_id: str
    import_envelope_hash: Optional[str]
    envelope: Optional[dict]
    manifest: Optional[dict]
    errors: tuple[str, ...]


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_bytes(registry_canonical_json(obj).encode("utf-8"))


def imports_root(repo_root: Path) -> Path:
    return runtime_root(repo_root) / "imports"


def import_sequence_path(repo_root: Path) -> Path:
    return imports_root(repo_root) / "import-sequence.txt"


def next_import_sequence(repo_root: Path) -> int:
    path = import_sequence_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        current = int(path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        current = 0
    value = current + 1
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(f"{value}\n", encoding="utf-8")
    tmp.replace(path)
    return value


def compute_segment_id(
    source_machine_id: str,
    segment_kind: str,
    remote_first_record_hash: str,
    remote_last_record_hash: str,
    remote_record_count: int,
    stored_segment_sha256: str,
) -> str:
    parts = [
        source_machine_id,
        segment_kind,
        remote_first_record_hash,
        remote_last_record_hash,
        str(remote_record_count),
        stored_segment_sha256,
    ]
    return sha256_bytes("\0".join(parts).encode("utf-8"))


def segment_paths(repo_root: Path, source_machine_id: str, segment_id: str) -> tuple[Path, Path]:
    safe_machine = _safe_path_component(source_machine_id)
    safe_segment = _safe_path_component(segment_id.replace("sha256:", "sha256-"))
    base = imports_root(repo_root) / safe_machine
    return base / f"{safe_segment}.jsonl", base / f"{safe_segment}.manifest.json"


def previous_imported_tail_hash(repo_root: Path, source_machine_id: str) -> Optional[str]:
    chain = runtime_root(repo_root) / "LOGS" / "decision-chain.jsonl"
    tail = None
    try:
        lines = chain.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (
            record.get("event_type") == "remote_chain_import"
            and record.get("source_machine_id") == source_machine_id
            and record.get("verification_result") == "PASS"
        ):
            tail = record.get("remote_last_record_hash")
    return tail if isinstance(tail, str) else None


def verify_remote_segment(
    repo_root: Path,
    *,
    source_machine_id: str,
    records_jsonl: bytes | str,
    previous_tail_hash: Optional[str] = None,
    source_machine_key_id: Optional[str] = None,
) -> SegmentVerification:
    raw = records_jsonl.encode("utf-8") if isinstance(records_jsonl, str) else records_jsonl
    errors: list[str] = []
    records: list[dict] = []
    for line_no, line in enumerate(raw.decode("utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {line_no}: JSONL_PARSE_FAILED:{exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"line {line_no}: RECORD_NOT_OBJECT")
            continue
        records.append(record)

    if not records:
        errors.append("SEGMENT_EMPTY")
        return SegmentVerification(False, tuple(errors), tuple(), None, None, 0, source_machine_key_id)

    observed_key_id = source_machine_key_id
    prior_hash = previous_tail_hash
    for index, record in enumerate(records):
        record_hash = record.get("record_hash")
        if not isinstance(record_hash, str) or not record_hash.startswith("sha256:"):
            errors.append(f"record {index + 1}: RECORD_HASH_MISSING")
            continue

        if record.get("machine_id") != source_machine_id:
            errors.append(f"record {index + 1}: MACHINE_ID_MISMATCH")

        expected_prev = prior_hash
        if index > 0 or expected_prev is not None:
            if record.get("prev_record_hash") != expected_prev:
                errors.append(f"record {index + 1}: PREV_RECORD_HASH_MISMATCH")

        recomputed = _compute_remote_record_hash(record)
        if recomputed != record_hash:
            errors.append(f"record {index + 1}: RECORD_HASH_MISMATCH")

        key_id = record.get("signing_key_id")
        if not isinstance(key_id, str) or not key_id:
            errors.append(f"record {index + 1}: SIGNING_KEY_ID_MISSING")
        else:
            observed_key_id = observed_key_id or key_id
            if source_machine_key_id is not None and key_id != source_machine_key_id:
                errors.append(f"record {index + 1}: SIGNING_KEY_ID_MISMATCH")

        if key_id:
            machine = authorized_machine_lookup(
                repo_root,
                source_machine_id,
                key_id,
                at_utc=record.get("event_timestamp_utc") or record.get("timestamp_utc"),
            )
            if machine is None:
                errors.append(f"record {index + 1}: MACHINE_NOT_AUTHORIZED")
            else:
                public_key_pem = _public_key_pem_for(machine, key_id)
                if not public_key_pem:
                    errors.append(f"record {index + 1}: PUBLIC_KEY_MISSING")
                elif not _verify_record_signature(record, public_key_pem):
                    errors.append(f"record {index + 1}: SIGNATURE_INVALID")

        prior_hash = record_hash

    return SegmentVerification(
        ok=not errors,
        errors=tuple(errors),
        records=tuple(records),
        first_record_hash=records[0].get("record_hash"),
        last_record_hash=records[-1].get("record_hash"),
        record_count=len(records),
        source_machine_key_id=observed_key_id,
    )


def import_remote_segment(
    repo_root: Path,
    *,
    source_machine_id: str,
    segment_kind: str,
    records_jsonl: bytes | str,
    sync_session_id: str,
    segment_id: Optional[str] = None,
    archive_manifest: Optional[dict] = None,
    signing_key=None,
    signing_key_id: Optional[str] = None,
) -> ImportResult:
    raw = records_jsonl.encode("utf-8") if isinstance(records_jsonl, str) else records_jsonl
    stored_segment_sha256 = sha256_bytes(raw)
    if segment_id is not None:
        sidecar_path, manifest_path = segment_paths(repo_root, source_machine_id, segment_id)
        if sidecar_path.exists():
            existing = sidecar_path.read_bytes()
            if sha256_bytes(existing) != stored_segment_sha256:
                return ImportResult(
                    False,
                    False,
                    segment_id,
                    None,
                    None,
                    None,
                    ("SEGMENT_ID_BODY_CONFLICT",),
                )
            manifest = _read_json(manifest_path)
            envelope_hash = manifest.get("import_envelope_hash") if isinstance(manifest, dict) else None
            return ImportResult(True, True, segment_id, envelope_hash, None, manifest, tuple())

    previous_tail = previous_imported_tail_hash(repo_root, source_machine_id)
    verification = verify_remote_segment(
        repo_root,
        source_machine_id=source_machine_id,
        records_jsonl=raw,
        previous_tail_hash=previous_tail,
    )
    if not verification.ok:
        return ImportResult(False, False, segment_id or "", None, None, None, verification.errors)

    computed_segment_id = compute_segment_id(
        source_machine_id,
        segment_kind,
        verification.first_record_hash or "",
        verification.last_record_hash or "",
        verification.record_count,
        stored_segment_sha256,
    )
    final_segment_id = segment_id or computed_segment_id
    if segment_id is not None and segment_id != computed_segment_id:
        return ImportResult(
            False,
            False,
            final_segment_id,
            None,
            None,
            None,
            ("SEGMENT_ID_MISMATCH",),
        )

    sidecar_path, manifest_path = segment_paths(repo_root, source_machine_id, final_segment_id)
    if sidecar_path.exists():
        existing = sidecar_path.read_bytes()
        if sha256_bytes(existing) != stored_segment_sha256:
            return ImportResult(
                False,
                False,
                final_segment_id,
                None,
                None,
                None,
                ("SEGMENT_ID_BODY_CONFLICT",),
            )
        manifest = _read_json(manifest_path)
        envelope_hash = manifest.get("import_envelope_hash") if isinstance(manifest, dict) else None
        return ImportResult(True, True, final_segment_id, envelope_hash, None, manifest, tuple())

    import_sequence = next_import_sequence(repo_root)
    primary_import_timestamp_utc = _now_utc_z()
    remote_manifest_hash = sha256_json(archive_manifest) if archive_manifest is not None else None
    segment_format = ARCHIVE_MANIFEST_FORMAT if segment_kind == ARCHIVE_SEGMENT else JSONL_SEGMENT_FORMAT
    stored_rel = str(sidecar_path.relative_to(runtime_root(repo_root)))
    envelope = build_non_action_event(
        "remote_chain_import",
        {
            "record_version": IMPORT_ENVELOPE_VERSION,
            "record_type": "non_action_event",
            "source_machine_id": source_machine_id,
            "source_machine_key_id": verification.source_machine_key_id,
            "source_machine_role": "remote",
            "segment_id": final_segment_id,
            "segment_kind": segment_kind,
            "segment_format": segment_format,
            "remote_first_record_hash": verification.first_record_hash,
            "remote_last_record_hash": verification.last_record_hash,
            "remote_record_count": verification.record_count,
            "previous_imported_remote_tail_hash": previous_tail,
            "remote_manifest_hash": remote_manifest_hash,
            "stored_segment_path": stored_rel,
            "stored_segment_sha256": stored_segment_sha256,
            "import_sequence": import_sequence,
            "sync_session_id": sync_session_id,
            "primary_import_timestamp_utc": primary_import_timestamp_utc,
            "verification_result": "PASS",
            "verification_errors": [],
        },
    )
    _write_bytes_atomic(sidecar_path, raw)
    envelope = append_import_envelope(repo_root, envelope, signing_key=signing_key, signing_key_id=signing_key_id)
    manifest = {
        "manifest_version": 1,
        "source_machine_id": source_machine_id,
        "segment_id": final_segment_id,
        "segment_kind": segment_kind,
        "segment_format": segment_format,
        "stored_segment_path": stored_rel,
        "stored_segment_sha256": stored_segment_sha256,
        "remote_first_record_hash": verification.first_record_hash,
        "remote_last_record_hash": verification.last_record_hash,
        "remote_record_count": verification.record_count,
        "previous_imported_remote_tail_hash": previous_tail,
        "remote_manifest_hash": remote_manifest_hash,
        "import_sequence": import_sequence,
        "sync_session_id": sync_session_id,
        "primary_import_timestamp_utc": primary_import_timestamp_utc,
        "verification_result": "PASS",
        "verification_errors": [],
        "import_envelope_hash": envelope.get("record_hash"),
    }
    _write_json(manifest_path, manifest)
    return ImportResult(True, False, final_segment_id, envelope.get("record_hash"), envelope, manifest, tuple())


def append_import_envelope(
    repo_root: Path,
    envelope: dict,
    *,
    signing_key=None,
    signing_key_id: Optional[str] = None,
) -> dict:
    chain = runtime_root(repo_root) / "LOGS" / "decision-chain.jsonl"
    chain.parent.mkdir(parents=True, exist_ok=True)
    with _chain_lock:
        lockdir = _acquire_chain_file_lock(chain)
        try:
            envelope["prev_record_hash"] = _last_chain_hash(chain)
            envelope["record_hash"] = _compute_event_record_hash(envelope)
            if signing_key is not None:
                sign_non_action_event(envelope, signing_key, signing_key_id)
            line = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            fd = os.open(str(chain), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, (line + "\n").encode("utf-8"))
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            _release_chain_file_lock(lockdir)
    return envelope


def verify_stored_segment_binding(repo_root: Path, envelope: dict) -> tuple[bool, Optional[str]]:
    rel = envelope.get("stored_segment_path")
    expected = envelope.get("stored_segment_sha256")
    if not isinstance(rel, str) or not isinstance(expected, str):
        return False, "ENVELOPE_STORAGE_FIELDS_MISSING"
    path = runtime_root(repo_root) / rel
    try:
        actual = sha256_bytes(path.read_bytes())
    except OSError as exc:
        return False, f"SIDECAR_UNREADABLE:{exc}"
    if actual != expected:
        return False, f"STORED_SEGMENT_SHA256_MISMATCH expected={expected} actual={actual}"
    return True, None


def _compute_remote_record_hash(record: dict) -> str:
    if record.get("record_type") == "mediated_decision" or record.get("record_version") == "2.0":
        return compute_decision_record_hash(record)
    if record.get("event_type") in NON_ACTION_EVENT_TYPES:
        return _compute_event_record_hash(record)
    body = dict(record)
    body["record_hash"] = None
    if "signature" in body:
        body["signature"] = None
    if "signing_key_id" in body:
        body["signing_key_id"] = None
    return sha256_bytes(canonical_json(body).encode("utf-8"))


def _verify_record_signature(record: dict, public_key_pem: str) -> bool:
    sig = record.get("signature")
    if not isinstance(sig, str) or not sig:
        return False
    try:
        from receipt_signing import _b64url_decode_nopad, _load_crypto
    except ImportError:  # pragma: no cover - package import path
        from scripts.receipt_signing import _b64url_decode_nopad, _load_crypto

    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, crypto_err = _load_crypto()
    if crypto_err:
        return False
    try:
        pub = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
    except Exception:
        return False
    if not isinstance(pub, Ed25519PublicKey):
        return False
    try:
        pub.verify(_b64url_decode_nopad(sig), _signature_preimage(record).encode("utf-8"))
        return True
    except (InvalidSignature, Exception):
        return False


def _signature_preimage(record: dict) -> str:
    if record.get("event_type") in NON_ACTION_EVENT_TYPES:
        body = dict(record)
        body["record_hash"] = None
        body["signature"] = None
        body["signing_key_id"] = None
        return canonical_json(body)
    return _verify_record_module().signing_preimage_payload(record)


def _verify_record_module():
    path = Path(__file__).resolve().parent / "verify-record.py"
    spec = importlib.util.spec_from_file_location("_atested_verify_record", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _public_key_pem_for(machine: dict, key_id: str) -> Optional[str]:
    for key in machine.get("keys", []):
        if key.get("public_key_fingerprint") == key_id:
            value = key.get("public_key_pem")
            return value if isinstance(value, str) and value else None
    return None


def _safe_path_component(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(value))


def _last_chain_hash(path: Path) -> Optional[str]:
    last = ""
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = line
    except OSError:
        return None
    if not last:
        return None
    try:
        record = json.loads(last)
    except json.JSONDecodeError:
        return None
    value = record.get("record_hash")
    return value if isinstance(value, str) else None


def _acquire_chain_file_lock(chain_path: Path) -> Path:
    lockdir = Path(str(chain_path) + ".lock.d")
    lock_meta = lockdir / "lock_owner.json"
    max_wait = 50

    def _try_acquire() -> bool:
        try:
            lockdir.mkdir(exist_ok=False)
            try:
                lock_meta.write_text(json.dumps({"pid": os.getpid(), "ts": _time_mod.time()}), encoding="utf-8")
            except OSError:
                pass
            return True
        except FileExistsError:
            return False

    def _holder_is_alive() -> bool:
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


def _release_chain_file_lock(lockdir: Path) -> None:
    try:
        (lockdir / "lock_owner.json").unlink(missing_ok=True)
        lockdir.rmdir()
    except OSError:
        pass


def _read_json(path: Path) -> Optional[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _now_utc_z() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
