#!/usr/bin/env python3
"""Runtime integrity protection for Atested proxy governance material."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from event_model import is_non_action_event


INTEGRITY_SCHEMA_VERSION = 1

INSTALL_SENTINEL_NAME = ".atested-installed"


class IntegrityViolation(RuntimeError):
    """Raised when governance material fails integrity verification."""


class IntegrityBlocked(RuntimeError):
    """Raised when the proxy must deny operations until operator acknowledgement."""


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def sha256_files(paths: Iterable[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted((p.resolve() for p in paths), key=lambda p: str(p)):
        h.update(str(path).encode("utf-8"))
        h.update(b"\0")
        h.update(sha256_file(path).encode("ascii"))
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def _canonical(obj: dict) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _metadata_hash(metadata: dict) -> str:
    body = dict(metadata)
    body["metadata_hash"] = None
    return "sha256:" + hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _record_hash_for_integrity(record: dict) -> Optional[str]:
    if not (
        is_non_action_event(record)
        or (
            record.get("record_version") == "2.0"
            and record.get("record_type") == "mediated_decision"
        )
    ):
        return None
    body = dict(record)
    body["record_hash"] = None
    if "signature" in body:
        body["signature"] = None
    if "signing_key_id" in body:
        body["signing_key_id"] = None
    return "sha256:" + hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainSummary:
    exists: bool
    record_count: int
    last_record_hash: Optional[str]
    size_bytes: int


class IntegrityMonitor:
    """Maintains sidecar integrity metadata and runtime policy/code checks."""

    def __init__(
        self,
        chain_path: Path,
        *,
        metadata_path: Optional[Path] = None,
        policy_path: Optional[Path] = None,
        repo_root: Optional[Path] = None,
        code_paths: Optional[list[Path]] = None,
        data_paths: Optional[list[Path]] = None,
    ):
        self.chain_path = Path(chain_path)
        self.metadata_path = Path(
            metadata_path
            or os.environ.get("GOV_INTEGRITY_METADATA_PATH", "")
            or self.chain_path.with_suffix(self.chain_path.suffix + ".integrity.json")
        )
        self.events_path = self.metadata_path.with_suffix(".events.jsonl")
        self.repo_root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
        self.policy_path = Path(
            policy_path
            or os.environ.get("GOV_POLICY_RULES_PATH", "")
            or self.repo_root / "capabilities" / "policy-rules.json"
        )
        self.code_paths = code_paths or self.default_code_paths(self.repo_root)
        self.data_paths = data_paths or self.default_data_paths(self.chain_path)
        self.sentinel_path = self.chain_path.parent / INSTALL_SENTINEL_NAME
        self._metadata: Optional[dict] = None
        self._startup_policy_hash: Optional[str] = None
        self._policy_change_event_recorded_for: Optional[str] = None
        self._pending_startup_hashes: Optional[dict] = None

    @staticmethod
    def default_code_paths(repo_root: Path) -> list[Path]:
        return [
            repo_root / "proxy" / "server.py",
            repo_root / "scripts" / "classifier.py",
            repo_root / "scripts" / "policy_eval_v2.py",
            repo_root / "scripts" / "policy_eval_shared.py",
            repo_root / "scripts" / "event_model.py",
        ]

    @staticmethod
    def default_data_paths(chain_path: Path) -> list[Path]:
        """Supplemental data files tracked for tamper detection."""
        runtime = chain_path.parent
        return [
            runtime / "LOGS" / "telemetry" / "summary.json",
        ]

    def current_data_hash(self) -> Optional[str]:
        """Compute composite hash of data_paths that exist."""
        existing = [p for p in self.data_paths if p.exists()]
        if not existing:
            return None
        return sha256_files(existing)

    def load_metadata(self) -> Optional[dict]:
        if not self.metadata_path.exists():
            self._metadata = None
            return None
        try:
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IntegrityViolation(f"integrity metadata unreadable: {self.metadata_path}: {exc}") from exc
        expected = metadata.get("metadata_hash")
        if expected != _metadata_hash(metadata):
            raise IntegrityViolation(f"integrity metadata hash mismatch: {self.metadata_path}")
        self._metadata = metadata
        return metadata

    def save_metadata(self, updates: Optional[dict] = None) -> dict:
        metadata = dict(self._metadata or self._empty_metadata())
        if updates:
            metadata.update(updates)
        metadata["last_updated_utc"] = now_utc_z()
        metadata["metadata_hash"] = _metadata_hash(metadata)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.metadata_path.name + ".",
            suffix=".tmp",
            dir=str(self.metadata_path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(_canonical(metadata))
                fh.write("\n")
            os.replace(tmp_name, self.metadata_path)
        finally:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
        self._metadata = metadata
        return metadata

    def _empty_metadata(self) -> dict:
        return {
            "schema_version": INTEGRITY_SCHEMA_VERSION,
            "chain_path": str(self.chain_path),
            "chain_existed": False,
            "expected_record_count": 0,
            "expected_last_record_hash": None,
            "expected_chain_size_bytes": 0,
            "proxy_code_hash": None,
            "policy_rules_hash": None,
            "policy_rules_blocked_hash": None,
            "blocked_reason": None,
            "last_updated_utc": now_utc_z(),
            "metadata_hash": None,
        }

    def summarize_chain(self) -> ChainSummary:
        if not self.chain_path.exists():
            return ChainSummary(False, 0, None, 0)

        count = 0
        prev_hash = None
        last_hash = None
        try:
            with self.chain_path.open("r", encoding="utf-8") as fh:
                for line_no, raw in enumerate(fh, start=1):
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise IntegrityViolation(f"chain invalid JSON at line {line_no}: {exc}") from exc
                    if count > 0 and record.get("prev_record_hash") != prev_hash:
                        raise IntegrityViolation(f"chain prev_record_hash mismatch at line {line_no}")
                    record_hash = record.get("record_hash")
                    if not isinstance(record_hash, str) or not record_hash.startswith("sha256:"):
                        raise IntegrityViolation(f"chain record_hash missing at line {line_no}")
                    recomputed_hash = _record_hash_for_integrity(record)
                    if recomputed_hash is not None and recomputed_hash != record_hash:
                        raise IntegrityViolation(f"chain record_hash mismatch at line {line_no}")
                    count += 1
                    prev_hash = record_hash
                    last_hash = record_hash
            return ChainSummary(True, count, last_hash, self.chain_path.stat().st_size)
        except OSError as exc:
            raise IntegrityViolation(f"chain unreadable: {self.chain_path}: {exc}") from exc

    def _ensure_sentinel(self) -> None:
        """Create the install sentinel on first run."""
        if not self.sentinel_path.exists():
            self.sentinel_path.parent.mkdir(parents=True, exist_ok=True)
            self.sentinel_path.write_text(
                json.dumps({
                    "created_utc": now_utc_z(),
                    "chain_path": str(self.chain_path),
                }, sort_keys=True) + "\n",
                encoding="utf-8",
            )

    def verify_startup_chain(self) -> ChainSummary:
        metadata = self.load_metadata()
        summary = self.summarize_chain()

        if metadata is None:
            if self.sentinel_path.exists():
                # Sentinel exists but metadata is missing — suspicious.
                # Do NOT re-baseline; record a violation.
                self.record_side_event("integrity_metadata_missing", {
                    "sentinel_exists": True,
                    "chain_exists": summary.exists,
                    "chain_record_count": summary.record_count,
                })
                raise IntegrityViolation(
                    "integrity metadata missing but install sentinel exists — "
                    "metadata may have been deleted to bypass integrity checks"
                )
            # True first run: no sentinel, no metadata.
            self._ensure_sentinel()
            self.save_chain_summary(summary)
            return summary

        previous = self._previous_summary(metadata)
        violation = self._checkpoint_violation(previous, summary)
        if violation == "chain_file_missing":
            self.record_side_event("chain_file_missing", {
                "expected_record_count": previous.record_count,
                "expected_last_record_hash": previous.last_record_hash,
            })
            raise IntegrityViolation(
                f"chain file missing after previous existence: {self.chain_path}"
            )
        if violation == "chain_file_truncated":
            self.record_side_event("chain_file_truncated", {
                "expected_record_count": previous.record_count,
                "actual_record_count": summary.record_count,
                "expected_last_record_hash": previous.last_record_hash,
                "actual_last_record_hash": summary.last_record_hash,
            })
            raise IntegrityViolation(
                f"chain truncated: expected at least {previous.record_count} records, got {summary.record_count}"
            )
        if violation == "chain_tail_hash_mismatch":
            self.record_side_event("chain_tail_hash_mismatch", {
                "expected_last_record_hash": previous.last_record_hash,
                "actual_last_record_hash": summary.last_record_hash,
            })
            raise IntegrityViolation("chain last record hash differs from integrity metadata")

        # Ensure sentinel exists (upgrade path for pre-sentinel installs)
        self._ensure_sentinel()
        self.save_chain_summary(summary)
        return summary

    def verify_chain_writable(self) -> ChainSummary:
        metadata = self.load_metadata()
        if metadata is None and self.sentinel_path.exists():
            self._block_chain("integrity_metadata_missing", {
                "sentinel_exists": True,
                "chain_exists": self.chain_path.exists(),
            })
        metadata = metadata or self._empty_metadata()
        try:
            summary = self.summarize_chain()
        except IntegrityViolation as exc:
            self._block_chain("chain_integrity_invalid", {
                "error": str(exc),
            })
        previous = self._previous_summary(metadata)
        violation = self._checkpoint_violation(previous, summary)

        if violation == "chain_file_missing":
            self._block_chain("chain_file_missing", {
                "expected_record_count": previous.record_count,
                "expected_last_record_hash": previous.last_record_hash,
            })
        if violation == "chain_file_truncated":
            self._block_chain("chain_file_truncated", {
                "expected_record_count": previous.record_count,
                "actual_record_count": summary.record_count,
                "expected_last_record_hash": previous.last_record_hash,
                "actual_last_record_hash": summary.last_record_hash,
            })
        if violation == "chain_tail_hash_mismatch":
            self._block_chain("chain_tail_hash_mismatch", {
                "expected_last_record_hash": previous.last_record_hash,
                "actual_last_record_hash": summary.last_record_hash,
            })
        if summary.record_count > previous.record_count:
            self.save_chain_summary(summary)
        return summary

    def _previous_summary(self, metadata: dict) -> ChainSummary:
        count = int(metadata.get("expected_record_count") or 0)
        return ChainSummary(
            exists=bool(metadata.get("chain_existed")) or count > 0,
            record_count=count,
            last_record_hash=metadata.get("expected_last_record_hash"),
            size_bytes=int(metadata.get("expected_chain_size_bytes") or 0),
        )

    def _checkpoint_violation(
        self,
        previous: ChainSummary,
        current: ChainSummary,
    ) -> Optional[str]:
        """Compare current chain to the last trusted checkpoint.

        The sidecar is a high-water tamper checkpoint, not an exact mirror.
        Valid forward progress can happen through another writer before this
        process refreshes metadata, so count increases are accepted after the
        chain's own hashes/linkage validate in summarize_chain().
        """
        if previous.exists and not current.exists:
            return "chain_file_missing"
        if current.record_count < previous.record_count:
            return "chain_file_truncated"
        if (
            current.record_count == previous.record_count
            and previous.last_record_hash != current.last_record_hash
        ):
            return "chain_tail_hash_mismatch"
        return None

    def _block_chain(self, reason: str, payload: dict) -> None:
        self.record_side_event(reason, payload)
        archived = False
        try:
            from chain_archive import archive_chain
            archive_chain(
                self.chain_path,
                reason=reason,
                payload=payload,
                sidecar_events_path=self.events_path,
            )
            archived = True
        except Exception as exc:
            self.record_side_event("chain_archive_failed", {
                "reason": reason,
                "error": str(exc),
            })
        if archived:
            self.save_metadata({
                "chain_path": str(self.chain_path),
                "chain_existed": False,
                "expected_record_count": 0,
                "expected_last_record_hash": None,
                "expected_chain_size_bytes": 0,
                "blocked_reason": reason,
            })
        else:
            self.save_metadata({"blocked_reason": reason})
        raise IntegrityViolation(f"chain integrity violation: {reason}")

    def save_chain_summary(self, summary: ChainSummary) -> dict:
        return self.save_metadata({
            "chain_path": str(self.chain_path),
            "chain_existed": summary.exists and summary.record_count > 0,
            "expected_record_count": summary.record_count,
            "expected_last_record_hash": summary.last_record_hash,
            "expected_chain_size_bytes": summary.size_bytes,
            "blocked_reason": None,
        })

    def refresh_after_chain_write(self) -> ChainSummary:
        summary = self.summarize_chain()
        self.save_chain_summary(summary)
        return summary

    def current_proxy_code_hash(self) -> str:
        return sha256_files(self.code_paths)

    def current_policy_rules_hash(self) -> str:
        return sha256_file(self.policy_path)

    def startup_hashes(self) -> dict:
        """Compute startup code/policy hashes without saving metadata.

        The caller (record_startup_integrity_events) is responsible for
        calling commit_startup_hashes() AFTER startup events are written,
        ensuring the integrity metadata always reflects the post-startup
        chain state.
        """
        metadata = self.load_metadata() or self._empty_metadata()
        previous_code_hash = metadata.get("proxy_code_hash")
        current_code_hash = self.current_proxy_code_hash()
        current_policy_hash = self.current_policy_rules_hash()
        current_data_hash = self.current_data_hash()
        self._startup_policy_hash = current_policy_hash
        self._policy_change_event_recorded_for = metadata.get("policy_rules_blocked_hash")
        # Store pending hashes for commit_startup_hashes()
        self._pending_startup_hashes = {
            "proxy_code_hash": current_code_hash,
            "policy_rules_hash": current_policy_hash,
            "data_hash": current_data_hash,
            "policy_rules_blocked_hash": None,
            "blocked_reason": None,
        }
        return {
            "previous_proxy_code_hash": previous_code_hash,
            "current_proxy_code_hash": current_code_hash,
            "current_policy_rules_hash": current_policy_hash,
            "current_data_hash": current_data_hash,
            "code_paths": [str(p) for p in self.code_paths],
            "data_paths": [str(p) for p in self.data_paths if p.exists()],
            "policy_path": str(self.policy_path),
        }

    def commit_startup_hashes(self) -> None:
        """Save startup hashes to metadata AFTER startup events are written.

        Must be called after all startup chain events have been appended
        so that refresh_after_chain_write has already updated the expected
        record count. This prevents the stale-count window where
        save_metadata could record count=N while the chain already has
        N+K records from startup events.
        """
        if self._pending_startup_hashes is not None:
            self.save_metadata(self._pending_startup_hashes)
            self._pending_startup_hashes = None

    def check_policy_rules_unchanged(self) -> Optional[dict]:
        if self._startup_policy_hash is None:
            self._startup_policy_hash = (
                (self.load_metadata() or {}).get("policy_rules_hash")
                or self.current_policy_rules_hash()
            )
        current_hash = self.current_policy_rules_hash()
        if current_hash == self._startup_policy_hash:
            return None
        self.save_metadata({
            "policy_rules_blocked_hash": current_hash,
            "blocked_reason": "policy_rules_changed",
        })
        return {
            "previous_policy_rules_hash": self._startup_policy_hash,
            "current_policy_rules_hash": current_hash,
            "policy_path": str(self.policy_path),
            "event_already_recorded": self._policy_change_event_recorded_for == current_hash,
        }

    def mark_policy_change_event_recorded(self, current_hash: str) -> None:
        self._policy_change_event_recorded_for = current_hash
        self.save_metadata({"policy_rules_blocked_hash": current_hash})

    def acknowledge_policy_rules_change(self, operator: str = "") -> dict:
        current_hash = self.current_policy_rules_hash()
        self._startup_policy_hash = current_hash
        return self.save_metadata({
            "policy_rules_hash": current_hash,
            "policy_rules_blocked_hash": None,
            "blocked_reason": None,
            "last_policy_ack_operator": operator,
            "last_policy_ack_utc": now_utc_z(),
        })

    def record_side_event(self, event_type: str, payload: dict) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "timestamp_utc": now_utc_z(),
            "event_type": event_type,
            "chain_path": str(self.chain_path),
            **payload,
        }
        with self.events_path.open("a", encoding="utf-8") as fh:
            fh.write(_canonical(event))
            fh.write("\n")
