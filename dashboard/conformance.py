"""Dashboard conformance state reader.

The dashboard reads the QA chain for operator visibility only. It does not
write to the QA chain and does not gate governance decisions.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


QA_EVENT_TYPES = {
    "qa_environmental_snapshot",
    "qa_condition_detected",
    "qa_spc_finding",
    "qa_decision_verification",
    "qa_decision_verification_skipped",
    "qa_verification_backlog_warning",
    "qa_behavioral_analysis",
    "qa_element_verification",
}

GUIDANCE = {
    "stale_rules": "Policy rules were updated on disk but the proxy is using a previous version. Restart the proxy to load current rules.",
    "CR-CRIT-001": "Policy rules were updated on disk but the proxy is using a previous version. Restart the proxy to load current rules.",
    "stale_capability_registry": "Capability registry was updated on disk. Restart the proxy to load the current registry.",
    "CR-CRIT-004": "Capability registry was updated on disk. Restart the proxy to load the current registry.",
    "signing_key_fingerprint_change": "The governance signing key has changed without a recorded rotation event. Verify key integrity.",
    "CR-CRIT-006": "The governance signing key has changed without a recorded rotation event. Verify key integrity.",
    "operator_session_expiry": "An approval references an operator session that may have exceeded the maximum age. Review and reissue if needed.",
    "CR-CRIT-007": "An approval references an operator session that may have exceeded the maximum age. Review and reissue if needed.",
}


@dataclass(frozen=True)
class QARead:
    status: str
    records: list[dict]
    latest_snapshot: Optional[dict] = None
    detail: str = ""


class DashboardQAChainReader:
    """Position-cached, mtime-invalidated reader for recent QA chain records."""

    def __init__(self, chain_path: Path, *, chunk_size: int = 64 * 1024, max_records: int = 250):
        self.chain_path = Path(chain_path)
        self.chunk_size = chunk_size
        self.max_records = max_records
        self._cached_mtime_ns: Optional[int] = None
        self._cached_size = 0
        self._cached_offset = 0
        self._cached_records: list[dict] = []
        self._last_sequence: Optional[int] = None
        self._last_advance_at: Optional[float] = None

    def read_recent(self) -> QARead:
        try:
            stat = self.chain_path.stat()
        except FileNotFoundError:
            self._reset()
            return QARead("absent", [], detail="QA chain file does not exist")
        except OSError as exc:
            return QARead("error", [], detail=f"QA chain unreadable: {exc}")

        if stat.st_size == 0:
            self._reset(mtime_ns=stat.st_mtime_ns)
            return QARead("absent", [], detail="QA chain is empty")

        if (
            self._cached_records
            and self._cached_mtime_ns == stat.st_mtime_ns
            and self._cached_size == stat.st_size
        ):
            self._update_liveness(self._latest_snapshot(self._cached_records))
            return QARead("ok", list(self._cached_records), self._latest_snapshot(self._cached_records))

        if stat.st_size < self._cached_offset:
            self._reset()

        if not self._cached_records or self._cached_offset == 0:
            records = self._read_recent_from_end(stat.st_size)
        else:
            records = list(self._cached_records)
            records.extend(self._read_forward())
            records = records[-self.max_records:]

        self._cached_records = records
        self._cached_mtime_ns = stat.st_mtime_ns
        self._cached_size = stat.st_size
        self._cached_offset = stat.st_size
        latest = self._latest_snapshot(records)
        self._update_liveness(latest)
        if latest is None:
            return QARead("absent", records, detail="QA chain contains no qa_environmental_snapshot")
        return QARead("ok", records, latest)

    def sequence_stale(self, *, stale_seconds: float, now=None) -> bool:
        if self._last_sequence is None or self._last_advance_at is None:
            return False
        clock = now or time.monotonic
        return clock() - self._last_advance_at >= stale_seconds

    def _reset(self, *, mtime_ns: Optional[int] = None) -> None:
        self._cached_mtime_ns = mtime_ns
        self._cached_size = 0
        self._cached_offset = 0
        self._cached_records = []
        self._last_sequence = None
        self._last_advance_at = None

    def _read_forward(self) -> list[dict]:
        try:
            with self.chain_path.open("r", encoding="utf-8") as fh:
                fh.seek(self._cached_offset)
                return self._parse_lines(fh.read().splitlines())
        except OSError:
            return []

    def _read_recent_from_end(self, file_size: int) -> list[dict]:
        try:
            with self.chain_path.open("rb") as fh:
                end = file_size
                buffer = b""
                while end > 0:
                    start = max(0, end - self.chunk_size)
                    fh.seek(start)
                    buffer = fh.read(end - start) + buffer
                    records = self._parse_lines(buffer.decode("utf-8", errors="replace").splitlines())
                    if len(records) >= self.max_records or start == 0:
                        return records[-self.max_records:]
                    end = start
        except OSError:
            return []
        return []

    @staticmethod
    def _parse_lines(lines: list[str]) -> list[dict]:
        records = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if record.get("event_type") in QA_EVENT_TYPES:
                records.append(record)
        return records

    @staticmethod
    def _latest_snapshot(records: list[dict]) -> Optional[dict]:
        for record in reversed(records):
            if record.get("event_type") == "qa_environmental_snapshot":
                return record
        return None

    def _update_liveness(self, snapshot: Optional[dict]) -> None:
        if not snapshot:
            return
        sequence = snapshot.get("sequence")
        if not isinstance(sequence, int):
            return
        now = time.monotonic()
        if self._last_sequence is None or sequence > self._last_sequence:
            self._last_sequence = sequence
            self._last_advance_at = now


def _quality_service_degraded_reason() -> Optional[dict]:
    """Read the supervisor's quality-service degraded marker if present.

    The supervisor writes {runtime}/supervisor/quality-service.degraded.json
    when the prebuilt quality-service binary is missing, unsupported, or fails
    manifest verification. Surface that reason in the conformance payload so
    the operator sees something more useful than "HALTED".
    """
    runtime = os.environ.get("GOV_RUNTIME_DIR")
    if not runtime:
        return None
    marker = Path(runtime) / "supervisor" / "quality-service.degraded.json"
    if not marker.exists():
        return None
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _degraded_detail_message(degraded: dict) -> str:
    reason = str(degraded.get("reason") or "")
    if reason.startswith("quality_service_binary_missing"):
        return f"Quality service binary is missing. Reinstall Atested or restore the shipped binary. {reason}"
    if reason.startswith("quality_service_binary_hash_mismatch"):
        return f"Quality service binary failed manifest verification. Reinstall Atested from a trusted release. {reason}"
    if reason.startswith("quality_service_platform_unsupported"):
        return f"Quality service is not available for this platform. {reason}"
    if reason.startswith("quality_service_manifest"):
        return f"Quality service manifest is unavailable or invalid. Reinstall Atested from a trusted release. {reason}"
    if reason:
        return f"Quality service unavailable: {reason}"
    return "Quality service is unavailable; check supervisor logs."


def build_conformance_payload(reader: DashboardQAChainReader) -> dict:
    read = reader.read_recent()
    stale_seconds = _stale_seconds()
    degraded = _quality_service_degraded_reason()
    if degraded is not None:
        # The shipped prebuilt binary is missing or failed verification.
        # Operator-actionable message takes precedence over the generic
        # "QA chain unavailable".
        return _halted_payload(
            _degraded_detail_message(degraded),
            qa_chain_present=False,
            degraded=degraded,
        )
    if read.status != "ok" or not read.latest_snapshot:
        return _halted_payload(read.detail or "QA chain unavailable", qa_chain_present=False)
    if reader.sequence_stale(stale_seconds=stale_seconds):
        return _halted_payload("QA chain snapshot sequence not advancing", qa_chain_present=True, snapshot=read.latest_snapshot)

    snapshot = read.latest_snapshot
    records = read.records
    active_conditions = _active_conditions(snapshot, records)
    critical_conditions = [c for c in active_conditions if c.get("severity") == "critical"]
    high_conditions = [c for c in active_conditions if c.get("severity") == "high"]
    spc_findings = [r for r in records if r.get("event_type") == "qa_spc_finding"]
    behavioral = [r for r in records if r.get("event_type") == "qa_behavioral_analysis"]
    element = [r for r in records if r.get("event_type") == "qa_element_verification"]
    decision_verifications = [r for r in records if r.get("event_type") == "qa_decision_verification"]
    skipped = [r for r in records if r.get("event_type") == "qa_decision_verification_skipped"]
    backlog = [r for r in records if r.get("event_type") == "qa_verification_backlog_warning"]
    post_hoc_findings = [r for r in decision_verifications if r.get("all_clear") is False]
    element_findings = [r for r in element if int(r.get("elements_flagged") or 0) > 0]
    behavioral_findings = [r for r in behavioral if int(r.get("anomaly_count") or 0) > 0]
    spc_attention = [
        r for r in spc_findings
        if str(r.get("status") or "").lower() in {"above_ucl", "below_lcl", "outside_limits", "alert"}
    ]

    environmental_status = "healthy"
    if snapshot.get("overall") != "healthy" or active_conditions:
        environmental_status = "condition_detected"

    if critical_conditions:
        state = "intervention"
    elif (
        high_conditions
        or snapshot.get("overall") not in {"healthy", None}
        or post_hoc_findings
        or spc_attention
        or element_findings
        or behavioral_findings
    ):
        state = "attention"
    else:
        state = "verified"

    latest_snapshot = {
        "sequence": snapshot.get("sequence"),
        "timestamp": snapshot.get("timestamp_utc") or snapshot.get("timestamp"),
        "policy_rules_hash": snapshot.get("policy_rules_hash"),
        "capability_registry_hash": snapshot.get("capability_registry_hash"),
        "checks": snapshot.get("checks", {}),
        "overall": snapshot.get("overall"),
    }

    return {
        "state": state,
        "modes": {
            "environmental": {
                "status": environmental_status,
                "checks": snapshot.get("checks", {}),
                "conditions": active_conditions,
            },
            "post_hoc": _post_hoc_status(decision_verifications, skipped, backlog),
            "spc": _spc_status(spc_findings),
            "element": _element_status(element),
            "behavioral": _behavioral_status(behavioral),
        },
        "active_conditions": active_conditions,
        "latest_snapshot": latest_snapshot,
        "qa_chain_present": True,
        "quality_service_alive": True,
        "detail": "",
    }


def _halted_payload(
    detail: str,
    *,
    qa_chain_present: bool,
    snapshot: Optional[dict] = None,
    degraded: Optional[dict] = None,
) -> dict:
    payload = {
        "state": "halted",
        "modes": {
            "environmental": {"status": "unavailable", "checks": {}, "conditions": []},
            "post_hoc": {"status": "not_active", "note": "Mode 2 not yet implemented"},
            "spc": {"status": "not_active", "note": "Mode 3 not yet implemented"},
            "element": {"status": "not_active", "note": "Mode 4 not yet implemented"},
            "behavioral": {"status": "not_active", "note": "Mode 5 not yet implemented"},
        },
        "active_conditions": [],
        "latest_snapshot": _snapshot_summary(snapshot) if snapshot else None,
        "qa_chain_present": qa_chain_present,
        "quality_service_alive": False,
        "detail": detail,
    }
    if degraded is not None:
        payload["quality_service_degraded"] = {
            "reason": degraded.get("reason"),
            "updated_utc": degraded.get("updated_utc"),
        }
    return payload


def _snapshot_summary(snapshot: dict) -> dict:
    return {
        "sequence": snapshot.get("sequence"),
        "timestamp": snapshot.get("timestamp_utc") or snapshot.get("timestamp"),
        "policy_rules_hash": snapshot.get("policy_rules_hash"),
        "capability_registry_hash": snapshot.get("capability_registry_hash"),
        "checks": snapshot.get("checks", {}),
        "overall": snapshot.get("overall"),
    }


def _mode_status(records: list[dict], not_active_note: str) -> dict:
    if not records:
        return {"status": "not_active", "note": not_active_note}
    latest = records[-1]
    return {"status": "active", "latest": latest}


def _post_hoc_status(verifications: list[dict], skipped: list[dict], backlog: list[dict]) -> dict:
    if not verifications and not skipped and not backlog:
        return {"status": "not_active", "note": "Mode 2 not yet implemented"}
    latest_backlog = backlog[-1] if backlog else None
    if latest_backlog and int(latest_backlog.get("queue_depth") or 0) > 0:
        return {
            "status": "behind",
            "queue_depth": latest_backlog.get("queue_depth"),
            "queue_capacity": latest_backlog.get("queue_capacity"),
            "decisions_verified": len(verifications),
            "skipped": len(skipped),
            "detail": f"Verification queue depth {latest_backlog.get('queue_depth')} of {latest_backlog.get('queue_capacity')}",
        }
    failed = [record for record in verifications if record.get("all_clear") is False]
    if failed:
        latest = failed[-1]
        return {
            "status": "finding",
            "decisions_verified": len(verifications),
            "last_verified_record_hash": latest.get("governance_record_hash"),
            "findings": latest.get("findings", []),
            "detail": f"{len(failed)} decision verification finding(s)",
        }
    latest = verifications[-1] if verifications else skipped[-1]
    return {
        "status": "active",
        "decisions_verified": len(verifications),
        "last_verified_record_hash": latest.get("governance_record_hash"),
        "skipped": len(skipped),
        "detail": f"{len(verifications)} decision(s) verified",
    }


def _spc_status(findings: list[dict]) -> dict:
    if not findings:
        return {"status": "not_active", "note": "Mode 3 not yet implemented"}
    latest = findings[-1]
    status = str(latest.get("status") or "").lower()
    if status == "learning":
        collected = latest.get("decisions_collected")
        minimum = latest.get("minimum_required")
        return {
            "status": "learning",
            "decisions_collected": collected,
            "minimum_required": minimum,
            "latest": latest,
            "detail": f"Baseline learning: {collected}/{minimum} decisions",
        }
    if status in {"above_ucl", "below_lcl", "outside_limits", "alert"}:
        return {
            "status": "attention",
            "metric_id": latest.get("metric_id"),
            "metric_name": latest.get("metric_name"),
            "current_value": latest.get("current_value"),
            "ucl": latest.get("ucl"),
            "lcl": latest.get("lcl"),
            "latest": latest,
            "detail": f"{latest.get('metric_id')} {status}",
        }
    return {
        "status": "active",
        "latest": latest,
        "detail": latest.get("detail") or "SPC monitoring active",
    }


def _element_status(records: list[dict]) -> dict:
    if not records:
        return {"status": "not_active", "note": "Mode 4 not yet implemented"}
    latest = records[-1]
    flagged = int(latest.get("elements_flagged") or 0)
    payload = {
        "status": "finding" if flagged else "active",
        "last_run": latest.get("timestamp_utc") or latest.get("timestamp"),
        "elements_checked": latest.get("elements_checked"),
        "elements_passed": latest.get("elements_passed"),
        "elements_flagged": latest.get("elements_flagged"),
        "elements_skipped": latest.get("elements_skipped"),
        "findings": latest.get("findings", []),
        "latest": latest,
    }
    payload["detail"] = (
        f"{payload['elements_checked']} checked, {payload['elements_flagged']} flagged"
        if payload["elements_checked"] is not None
        else "Element verification active"
    )
    return payload


def _behavioral_status(records: list[dict]) -> dict:
    if not records:
        return {"status": "not_active", "note": "Mode 5 not yet implemented"}
    latest = records[-1]
    # QS-039 #18: warm-up window. Below the configured minimum decision
    # count the quality service emits a warm-up record rather than flagging
    # anomalies that are artifacts of thin data. Render it as a distinct
    # state so the operator sees "warming up (N/M)" instead of an alarm.
    if latest.get("warm_up"):
        analyzed = int(latest.get("decisions_analyzed") or 0)
        minimum = int(latest.get("minimum_required") or 0)
        return {
            "status": "warming_up",
            "last_run": latest.get("timestamp_utc") or latest.get("timestamp"),
            "decisions_analyzed": analyzed,
            "minimum_required": minimum,
            "anomaly_count": 0,
            "latest": latest,
            "detail": f"warming up ({analyzed}/{minimum} decisions)",
        }
    anomaly_count = int(latest.get("anomaly_count") or 0)
    return {
        "status": "finding" if anomaly_count else "active",
        "last_run": latest.get("timestamp_utc") or latest.get("timestamp"),
        "anomaly_count": anomaly_count,
        "findings": latest.get("findings", []),
        "latest": latest,
        "detail": f"{anomaly_count} behavioral anomal{'y' if anomaly_count == 1 else 'ies'}",
    }


def _active_conditions(snapshot: dict, records: list[dict]) -> list[dict]:
    explicit = {
        record.get("condition_id"): record
        for record in records
        if record.get("event_type") == "qa_condition_detected" and record.get("condition_id")
    }
    conditions = []
    for raw in snapshot.get("active_conditions", []) or []:
        if isinstance(raw, dict):
            condition_id = raw.get("condition_id") or raw.get("id") or raw.get("condition_type") or "condition"
            condition = dict(raw)
        else:
            condition_id = str(raw)
            condition = dict(explicit.get(condition_id, {}))
        condition.setdefault("condition_id", condition_id)
        condition.setdefault("condition_type", _condition_type(condition_id))
        condition.setdefault("severity", _condition_severity(condition_id, condition))
        condition.setdefault("detail", condition_id)
        condition.setdefault("detected_at", condition.get("timestamp_utc") or condition.get("timestamp") or snapshot.get("timestamp_utc"))
        condition["guidance"] = _guidance_for(condition)
        conditions.append(condition)

    if not conditions and snapshot.get("overall") not in {"healthy", None}:
        checks = snapshot.get("checks", {}) if isinstance(snapshot.get("checks"), dict) else {}
        for check_id, check in checks.items():
            if not isinstance(check, dict) or check.get("status") != "fail":
                continue
            severity = str(check.get("severity") or "high").lower()
            condition_type = "environment_critical" if severity == "critical" else "environmental_warning"
            detail = f"{check_id}: {check.get('detail') or 'environmental check failed'}"
            conditions.append({
                "condition_id": f"{condition_type}:{check_id}",
                "condition_type": condition_type,
                "severity": severity,
                "detail": detail,
                "detected_at": snapshot.get("timestamp_utc") or snapshot.get("timestamp"),
                "guidance": _guidance_for({"condition_type": condition_type, "detail": detail}),
            })
        if not conditions:
            conditions.append({
                "condition_id": "environment_critical",
                "condition_type": "environment_critical",
                "severity": "critical",
                "detail": f"Environmental snapshot overall status is {snapshot.get('overall')}",
                "detected_at": snapshot.get("timestamp_utc") or snapshot.get("timestamp"),
                "guidance": "Review the failing environmental checks below and correct the reported condition.",
            })
    return conditions


def _condition_type(condition_id: str) -> str:
    mapping = {
        "CR-CRIT-001": "stale_rules",
        "CR-CRIT-004": "stale_capability_registry",
        "CR-CRIT-006": "signing_key_fingerprint_change",
        "CR-CRIT-007": "operator_session_expiry",
    }
    if condition_id.startswith("CR-CRIT-005"):
        return "environment_critical"
    return mapping.get(condition_id, condition_id)


def _condition_severity(condition_id: str, condition: dict) -> str:
    if condition.get("severity"):
        return str(condition["severity"]).lower()
    if condition_id.startswith("CR-CRIT-") or "critical" in condition_id.lower():
        return "critical"
    if condition_id.startswith("CR-HIGH-"):
        return "high"
    return "medium"


def _guidance_for(condition: dict) -> str:
    condition_type = str(condition.get("condition_type") or "")
    condition_id = str(condition.get("condition_id") or "")
    if condition_type == "environment_critical":
        return f"Review and resolve the failing environmental check: {condition.get('detail', condition_id)}"
    return GUIDANCE.get(condition_type) or GUIDANCE.get(condition_id) or "Review the quality service detail and resolve the reported condition."


def _stale_seconds() -> float:
    explicit = os.environ.get("ATESTED_CONFORMANCE_STALE_SECONDS")
    if explicit:
        try:
            return max(0.0, float(explicit))
        except ValueError:
            pass
    cycles = int(os.environ.get("GOV_QA_STALE_CYCLES", "3") or "3")
    heartbeat = float(os.environ.get("GOV_QA_HEARTBEAT_SECONDS", os.environ.get("ATESTED_QS_HEARTBEAT_SECONDS", "30")) or "30")
    return max(0.0, cycles * heartbeat)
