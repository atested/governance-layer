"""QA chain tail reader and proxy quality gate.

The proxy reads the QA chain; it never writes it.  This module keeps the
runtime dependency small and independent of the future Rust quality service.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class QATailReadResult:
    status: str
    snapshot: Optional[dict] = None
    detail: str = ""
    bytes_read: int = 0


@dataclass(frozen=True)
class QualityGateResult:
    ok: bool
    condition_source: Optional[str] = None
    condition_detail: str = ""
    snapshot: Optional[dict] = None
    # QS-039 Adv #3: stable identifier for the condition that failed the
    # gate, so a governance_integrity_error can be correlated to a specific
    # condition. For active_condition this is the triggering registry id
    # (e.g. CR-CRIT-001); for the gate-internal sources it is a stable
    # QA-GATE:<source> identifier (no fabricated CR-* registry codes).
    condition_id: Optional[str] = None


class QAChainTailReader:
    """Position-cached, mtime-invalidated reader for qa_environmental_snapshot."""

    def __init__(self, chain_path: Path, *, chunk_size: int = 64 * 1024):
        self.chain_path = Path(chain_path)
        self.chunk_size = chunk_size
        self._cached_offset = 0
        self._cached_mtime_ns: Optional[int] = None
        self._cached_size = 0
        self._cached_snapshot: Optional[dict] = None
        self._last_seen_sequence: Optional[int] = None
        self.last_bytes_read = 0

    @property
    def cached_offset(self) -> int:
        return self._cached_offset

    @property
    def last_seen_sequence(self) -> Optional[int]:
        return self._last_seen_sequence

    def latest_snapshot(self) -> QATailReadResult:
        self.last_bytes_read = 0
        try:
            stat = self.chain_path.stat()
        except FileNotFoundError:
            self._reset_cache()
            return QATailReadResult("absent", detail="QA chain file does not exist")
        except OSError as exc:
            return QATailReadResult("error", detail=f"QA chain unreadable: {exc}")

        if stat.st_size == 0:
            self._reset_cache(mtime_ns=stat.st_mtime_ns, size=0)
            return QATailReadResult("absent", detail="QA chain is empty")

        if (
            self._cached_snapshot is not None
            and self._cached_mtime_ns == stat.st_mtime_ns
            and self._cached_size == stat.st_size
        ):
            return QATailReadResult(
                "ok",
                snapshot=self._cached_snapshot,
                bytes_read=0,
            )

        if stat.st_size < self._cached_offset:
            self._reset_cache()

        if self._cached_snapshot is None or self._cached_offset == 0:
            result = self._read_latest_snapshot_from_end(stat.st_size)
        else:
            result = self._read_forward_from_cache(stat.st_size)

        if result.status == "ok":
            self._cached_snapshot = result.snapshot
            self._cached_mtime_ns = stat.st_mtime_ns
            self._cached_size = stat.st_size
            self._cached_offset = stat.st_size
            seq = result.snapshot.get("sequence") if isinstance(result.snapshot, dict) else None
            self._last_seen_sequence = seq if isinstance(seq, int) else self._last_seen_sequence
        return result

    def _reset_cache(self, *, mtime_ns: Optional[int] = None, size: int = 0) -> None:
        self._cached_offset = 0
        self._cached_mtime_ns = mtime_ns
        self._cached_size = size
        self._cached_snapshot = None
        self._last_seen_sequence = None

    def _read_forward_from_cache(self, file_size: int) -> QATailReadResult:
        try:
            with self.chain_path.open("r", encoding="utf-8") as fh:
                fh.seek(self._cached_offset)
                data = fh.read()
        except OSError as exc:
            return QATailReadResult("error", detail=f"QA chain unreadable: {exc}")

        self.last_bytes_read = len(data.encode("utf-8"))
        latest = self._latest_snapshot_from_lines(data.splitlines())
        if latest is None:
            return QATailReadResult(
                "ok",
                snapshot=self._cached_snapshot,
                bytes_read=self.last_bytes_read,
            )
        return QATailReadResult("ok", snapshot=latest, bytes_read=self.last_bytes_read)

    def _read_latest_snapshot_from_end(self, file_size: int) -> QATailReadResult:
        try:
            with self.chain_path.open("rb") as fh:
                end = file_size
                buffer = b""
                while end > 0:
                    start = max(0, end - self.chunk_size)
                    fh.seek(start)
                    chunk = fh.read(end - start)
                    self.last_bytes_read += len(chunk)
                    buffer = chunk + buffer
                    latest = self._latest_snapshot_from_lines(
                        buffer.decode("utf-8", errors="replace").splitlines()
                    )
                    if latest is not None:
                        return QATailReadResult("ok", snapshot=latest, bytes_read=self.last_bytes_read)
                    end = start
        except OSError as exc:
            return QATailReadResult("error", detail=f"QA chain unreadable: {exc}")

        return QATailReadResult("absent", detail="QA chain contains no qa_environmental_snapshot")

    @staticmethod
    def _latest_snapshot_from_lines(lines: list[str]) -> Optional[dict]:
        for line in reversed(lines):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if record.get("event_type") == "qa_environmental_snapshot":
                return record
        return None


class ProxyQualityGate:
    """Evaluates whether proxy mediation may proceed under the latest QA state."""

    def __init__(
        self,
        reader: QAChainTailReader,
        *,
        expected_policy_rules_hash: str,
        expected_capability_registry_hash: str,
        stale_cycles: int = 3,
        heartbeat_seconds: float = 30.0,
        now=time.monotonic,
    ):
        self.reader = reader
        self.expected_policy_rules_hash = expected_policy_rules_hash
        self.expected_capability_registry_hash = expected_capability_registry_hash
        self.stale_cycles = max(1, int(stale_cycles))
        self.heartbeat_seconds = max(0.0, float(heartbeat_seconds))
        self._now = now
        self._last_sequence: Optional[int] = None
        self._last_advance_at: Optional[float] = None

    def check(self) -> QualityGateResult:
        result = self.reader.latest_snapshot()
        if result.status != "ok" or not result.snapshot:
            return QualityGateResult(
                False,
                "qa_chain_absent",
                result.detail or "No QA environmental snapshot available",
                condition_id="QA-GATE:qa_chain_absent",
            )

        snapshot = result.snapshot
        sequence = snapshot.get("sequence")
        if not isinstance(sequence, int):
            return QualityGateResult(
                False,
                "qa_chain_absent",
                "Latest QA environmental snapshot has no integer sequence",
                snapshot,
                condition_id="QA-GATE:qa_chain_absent",
            )

        now = self._now()
        if self._last_sequence is None or sequence > self._last_sequence:
            self._last_sequence = sequence
            self._last_advance_at = now
        elif sequence < self._last_sequence:
            return QualityGateResult(
                False,
                "qa_chain_staleness",
                f"QA sequence moved backwards: previous={self._last_sequence}, current={sequence}",
                snapshot,
                condition_id="QA-GATE:qa_chain_staleness",
            )
        else:
            elapsed = 0.0 if self._last_advance_at is None else now - self._last_advance_at
            stale_after = self.stale_cycles * self.heartbeat_seconds
            if elapsed >= stale_after:
                return QualityGateResult(
                    False,
                    "qa_chain_staleness",
                    (
                        f"QA environmental snapshot sequence has not advanced for "
                        f"{elapsed:.1f}s; threshold is {stale_after:.1f}s"
                    ),
                    snapshot,
                    condition_id="QA-GATE:qa_chain_staleness",
                )

        overall = snapshot.get("overall")
        if overall != "healthy":
            return QualityGateResult(
                False,
                "active_condition",
                f"QA environmental snapshot overall status is {overall!r}, expected 'healthy'",
                snapshot,
                condition_id="QA-GATE:unhealthy_snapshot",
            )

        policy_hash = snapshot.get("policy_rules_hash")
        if policy_hash != self.expected_policy_rules_hash:
            return QualityGateResult(
                False,
                "hash_mismatch",
                (
                    f"policy_rules_hash mismatch: proxy={self.expected_policy_rules_hash}, "
                    f"qa_snapshot={policy_hash}"
                ),
                snapshot,
                condition_id="CR-CRIT-001",
            )

        cap_hash = snapshot.get("capability_registry_hash")
        if cap_hash != self.expected_capability_registry_hash:
            return QualityGateResult(
                False,
                "hash_mismatch",
                (
                    f"capability_registry_hash mismatch: proxy={self.expected_capability_registry_hash}, "
                    f"qa_snapshot={cap_hash}"
                ),
                snapshot,
                condition_id="CR-CRIT-004",
            )

        critical_conditions = self._critical_conditions(snapshot.get("active_conditions", []))
        if critical_conditions:
            return QualityGateResult(
                False,
                "active_condition",
                f"Critical QA conditions active: {', '.join(critical_conditions)}",
                snapshot,
                # Pass through the triggering registry id (e.g. CR-CRIT-001)
                # so the integrity error correlates to the specific condition.
                condition_id=critical_conditions[0],
            )

        return QualityGateResult(True, snapshot=snapshot)

    @staticmethod
    def _critical_conditions(active_conditions) -> list[str]:
        if not isinstance(active_conditions, list):
            return ["active_conditions_not_list"]
        critical: list[str] = []
        for condition in active_conditions:
            if isinstance(condition, str):
                lowered = condition.lower()
                if condition.startswith("CR-CRIT-") or "critical" in lowered:
                    critical.append(condition)
            elif isinstance(condition, dict):
                condition_id = str(condition.get("condition_id") or condition.get("id") or "")
                severity = str(condition.get("severity") or "").lower()
                if condition_id.startswith("CR-CRIT-") or severity == "critical":
                    critical.append(condition_id or str(condition))
        return critical
