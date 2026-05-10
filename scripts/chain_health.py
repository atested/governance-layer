#!/usr/bin/env python3
"""
chain_health.py — Chain stability, break classification, self-healing,
rolling retention, and system health monitoring.

This module provides:
  1. Chain stability log — append-only JSONL for health events (not governance data).
  2. Break classification — known/suspicious/pattern detection.
  3. Self-healing — conservative auto-repair for known break types only.
  4. Rolling retention — archive old chain segments with stability checkpoints.
  5. Health signal collection — aggregated system health for dashboard and MCP tool.

Design principles:
  - Unclassifiable breaks default to suspicious (never auto-repaired).
  - Evidence of suspicious breaks is never destroyed.
  - Stability events are separate from the governance chain.
  - Retention uses time-based windows, not size-based.
"""

import json
import os
import shutil
import stat as _stat
import uuid
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


def _load_chain_rows_raw(chain_path: Path) -> list:
    """Load chain rows with minimal overhead (fallback when no rows passed)."""
    rows = []
    with open(chain_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return rows


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STABILITY_EVENT_TYPES = frozenset([
    "checkpoint",
    "auto_repair",
    "break_detected",
    "suspicious_event",
    "archive_created",
    "health_check",
    "server_start",
    "alert_acknowledged",
])

# Known break patterns that can be auto-repaired
KNOWN_BREAK_PATTERNS = {
    "unsigned_legacy": "Records created before signing enforcement (H3). Structurally valid but unsigned.",
    "chain_reset": "Chain was intentionally reset. First record has prev_record_hash=None after prior records.",
    "truncation_recovery": "Chain was truncated and restarted. chain_meta shows higher count than actual.",
    "partial_write": "Trailing record is incomplete JSON (crash/interrupt during write).",
}

# Default retention: 90 days active, 90 days archive
DEFAULT_ACTIVE_RETENTION_DAYS = 90
DEFAULT_ARCHIVE_RETENTION_DAYS = 90

# Break pattern thresholds
PATTERN_BREAK_THRESHOLD = 3
PATTERN_BREAK_WINDOW_HOURS = 24

# Health status levels
HEALTH_HEALTHY = "healthy"
HEALTH_HEALTHY_REPAIRED = "healthy_auto_repaired"
HEALTH_ATTENTION = "attention"
HEALTH_CRITICAL = "critical"

# DENY rate anomaly: flag if > 3x average
DENY_RATE_ANOMALY_MULTIPLIER = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(ts: str) -> Optional[datetime]:
    """Parse a UTC timestamp string to datetime."""
    if not ts:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _file_size(p: Path) -> int:
    try:
        return p.stat().st_size if p.exists() else 0
    except OSError:
        return 0


def _dir_size(p: Path) -> int:
    total = 0
    if not p.exists():
        return 0
    try:
        for f in p.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except OSError:
        pass
    return total


# ---------------------------------------------------------------------------
# Stability log
# ---------------------------------------------------------------------------

def append_stability_event(
    stability_log_path: Path,
    event_type: str,
    detail: Dict[str, Any],
) -> Dict[str, Any]:
    """Append a health event to the stability log. Returns the event."""
    if event_type not in STABILITY_EVENT_TYPES:
        raise ValueError(f"unknown stability event type: {event_type}")

    event = {
        "stability_event_id": str(uuid.uuid4()),
        "timestamp_utc": _now_utc_z(),
        "event_type": event_type,
        "detail": detail,
    }

    stability_log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    fd = os.open(str(stability_log_path), os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                 _stat.S_IRUSR | _stat.S_IWUSR)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)

    return event


def read_stability_log(
    stability_log_path: Path,
    limit: int = 50,
    event_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Read recent stability events, newest first."""
    if not stability_log_path.exists():
        return []
    events = []
    with open(stability_log_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                evt = json.loads(stripped)
            except json.JSONDecodeError:
                continue
            if event_type and evt.get("event_type") != event_type:
                continue
            events.append(evt)
    # Return newest first, limited
    events.reverse()
    return events[:limit]


# ---------------------------------------------------------------------------
# Break classification
# ---------------------------------------------------------------------------

def classify_chain_break(
    chain_path: Path,
    break_at_line: int,
    break_reason: str,
    chain_meta_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Classify a chain break.

    Returns dict with: classification, pattern, description, auto_repairable, repair_strategy.
    Conservative: unclassifiable defaults to suspicious.
    """
    result = {
        "classification": "suspicious",
        "pattern": None,
        "description": f"Unclassified break at line {break_at_line}: {break_reason}",
        "confidence": "low",
        "auto_repairable": False,
        "repair_strategy": None,
    }

    # Pattern: unsigned records rejected by signing enforcement
    if "unsigned record rejected" in break_reason.lower():
        result.update({
            "classification": "known",
            "pattern": "unsigned_legacy",
            "description": KNOWN_BREAK_PATTERNS["unsigned_legacy"],
            "confidence": "high",
            "auto_repairable": True,
            "repair_strategy": "skip_unsigned_verification",
        })
        return result

    # Pattern: hash mismatch on first record (chain was reset)
    if break_at_line == 1 and "prev_record_hash" in break_reason.lower():
        result.update({
            "classification": "known",
            "pattern": "chain_reset",
            "description": KNOWN_BREAK_PATTERNS["chain_reset"],
            "confidence": "medium",
            "auto_repairable": False,
            "repair_strategy": None,
        })
        return result

    # Pattern: chain_meta shows higher length (truncation)
    if chain_meta_path and chain_meta_path.exists():
        try:
            meta = json.loads(chain_meta_path.read_text(encoding="utf-8"))
            recorded = meta.get("chain_length", 0)
            actual = 0
            if chain_path.exists():
                with open(chain_path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            actual += 1
            if recorded > actual and break_reason == "truncation_detected":
                result.update({
                    "classification": "known",
                    "pattern": "truncation_recovery",
                    "description": KNOWN_BREAK_PATTERNS["truncation_recovery"],
                    "confidence": "medium",
                    "auto_repairable": True,
                    "repair_strategy": "reset_chain_meta",
                })
                return result
        except (json.JSONDecodeError, OSError):
            pass

    # Pattern: trailing incomplete JSON
    if "invalid_json" in break_reason.lower():
        # Check if it's the last line
        if chain_path.exists():
            line_count = 0
            with open(chain_path, "r", encoding="utf-8") as fh:
                for _ in fh:
                    line_count += 1
            if break_at_line == line_count:
                result.update({
                    "classification": "known",
                    "pattern": "partial_write",
                    "description": KNOWN_BREAK_PATTERNS["partial_write"],
                    "confidence": "medium",
                    "auto_repairable": True,
                    "repair_strategy": "truncate_last_line",
                })
                return result

    # Default: suspicious
    return result


def detect_break_pattern(
    stability_log_path: Path,
    window_hours: int = PATTERN_BREAK_WINDOW_HOURS,
    threshold: int = PATTERN_BREAK_THRESHOLD,
) -> Optional[Dict[str, Any]]:
    """Detect repeated breaks (pattern) that might indicate ongoing attack."""
    events = read_stability_log(stability_log_path, limit=100, event_type="break_detected")
    if len(events) < threshold:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
    recent = []
    for evt in events:
        ts = _parse_utc(evt.get("timestamp_utc", ""))
        if ts and ts >= cutoff:
            recent.append(evt)

    if len(recent) >= threshold:
        return {
            "pattern_detected": True,
            "break_count": len(recent),
            "window_hours": window_hours,
            "threshold": threshold,
            "severity": "critical",
            "description": f"{len(recent)} chain breaks detected in the last {window_hours} hours. "
                           f"This may indicate an ongoing attack or serious system failure.",
        }
    return None


# ---------------------------------------------------------------------------
# Self-healing (conservative)
# ---------------------------------------------------------------------------

def auto_repair_chain(
    chain_path: Path,
    break_info: Dict[str, Any],
    stability_log_path: Path,
) -> Dict[str, Any]:
    """Attempt conservative auto-repair of a known break.

    Only repairs breaks classified as 'known' with auto_repairable=True.
    Logs all actions to stability log.
    Returns: {"repaired": bool, "strategy": str, "stability_event_id": str}
    """
    if break_info.get("classification") != "known":
        return {"repaired": False, "reason": "break not classified as known"}
    if not break_info.get("auto_repairable"):
        return {"repaired": False, "reason": "break not auto-repairable"}

    strategy = break_info.get("repair_strategy")

    if strategy == "truncate_last_line":
        # Remove the last (corrupt) line
        lines = []
        with open(chain_path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
        if lines:
            # Write all but last to temp, then rename
            tmp = chain_path.with_suffix(".repair.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                for line in lines[:-1]:
                    fh.write(line)
            tmp.rename(chain_path)
        evt = append_stability_event(stability_log_path, "auto_repair", {
            "strategy": strategy,
            "pattern": break_info.get("pattern"),
            "description": f"Removed corrupt trailing line from chain.",
            "lines_before": len(lines),
            "lines_after": len(lines) - 1,
        })
        return {"repaired": True, "strategy": strategy, "stability_event_id": evt["stability_event_id"]}

    if strategy == "reset_chain_meta":
        meta_path = chain_path.parent / "chain_meta.json"
        actual = 0
        if chain_path.exists():
            with open(chain_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        actual += 1
        meta_path.write_text(json.dumps({"chain_length": actual}), encoding="utf-8")
        evt = append_stability_event(stability_log_path, "auto_repair", {
            "strategy": strategy,
            "pattern": break_info.get("pattern"),
            "description": f"Reset chain_meta.json chain_length to {actual}.",
        })
        return {"repaired": True, "strategy": strategy, "stability_event_id": evt["stability_event_id"]}

    if strategy == "skip_unsigned_verification":
        # This isn't a chain file repair — it's handled by check_chain_integrity
        # already using GOV_SIGNING_DEV_MODE=1. Log it as a known condition.
        evt = append_stability_event(stability_log_path, "auto_repair", {
            "strategy": strategy,
            "pattern": break_info.get("pattern"),
            "description": "Chain contains unsigned legacy records. Integrity verified with signing bypass.",
        })
        return {"repaired": True, "strategy": strategy, "stability_event_id": evt["stability_event_id"]}

    return {"repaired": False, "reason": f"unknown repair strategy: {strategy}"}


# ---------------------------------------------------------------------------
# Rolling retention
# ---------------------------------------------------------------------------

def archive_chain_segment(
    chain_path: Path,
    archive_dir: Path,
    active_retention_days: int = DEFAULT_ACTIVE_RETENTION_DAYS,
    stability_log_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """Archive records older than the active retention window.

    Returns archive info or None if nothing to archive.
    """
    if not chain_path.exists():
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=active_retention_days)
    rows = []
    with open(chain_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                rows.append(stripped)

    if not rows:
        return None

    # Find the split point: first record newer than cutoff stays
    archive_lines = []
    keep_lines = []
    for raw_line in rows:
        try:
            rec = json.loads(raw_line)
        except json.JSONDecodeError:
            keep_lines.append(raw_line)
            continue
        ts = _parse_utc(rec.get("timestamp_utc", ""))
        if ts and ts < cutoff:
            archive_lines.append(raw_line)
        else:
            keep_lines.append(raw_line)

    if not archive_lines:
        return None

    # Write archive file
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_file = archive_dir / f"decision-chain.archive.{ts_str}.jsonl"
    with open(archive_file, "w", encoding="utf-8") as fh:
        for line in archive_lines:
            fh.write(line + "\n")

    # Get terminal hash of archived segment
    try:
        last_archived = json.loads(archive_lines[-1])
        terminal_hash = last_archived.get("record_hash")
    except (json.JSONDecodeError, IndexError):
        terminal_hash = None

    # Rewrite chain with kept records (atomic via temp file)
    tmp = chain_path.with_suffix(".retention.tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        for line in keep_lines:
            fh.write(line + "\n")
    tmp.rename(chain_path)

    # Update chain_meta
    meta_path = chain_path.parent / "chain_meta.json"
    meta_path.write_text(json.dumps({"chain_length": len(keep_lines)}), encoding="utf-8")

    # Log checkpoint
    archive_info = {
        "archived_count": len(archive_lines),
        "kept_count": len(keep_lines),
        "archive_path": str(archive_file),
        "terminal_hash": terminal_hash,
    }

    if stability_log_path:
        append_stability_event(stability_log_path, "archive_created", archive_info)

    return archive_info


def purge_expired_archives(
    archive_dir: Path,
    archive_retention_days: int = DEFAULT_ARCHIVE_RETENTION_DAYS,
) -> int:
    """Delete archive files older than the archive retention window. Returns count deleted."""
    if not archive_dir.exists():
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=archive_retention_days)
    deleted = 0
    for f in sorted(archive_dir.glob("decision-chain.archive.*.jsonl")):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError:
            continue
    return deleted


# ---------------------------------------------------------------------------
# Enhanced chain integrity check with classification
# ---------------------------------------------------------------------------

_chain_health_cache: Dict[str, Any] = {"mtime": 0.0, "size": 0, "result": None}


def check_chain_health(
    chain_path: Path,
    stability_log_path: Optional[Path] = None,
    chain_meta_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Enhanced chain integrity check with break classification.

    Results are cached by file mtime + size when the chain is healthy.
    Unhealthy states are never cached (side effects may apply).

    Returns:
        {
            "status": "healthy" | "healthy_auto_repaired" | "attention" | "critical",
            "chain_event_count": int,
            "checked": bool,
            "break_info": {...} | None,
            "repair_info": {...} | None,
            "pattern_alert": {...} | None,
            "recent_stability_events": [...],
        }
    """
    if not chain_path.exists() or _file_size(chain_path) == 0:
        return {
            "status": HEALTH_HEALTHY,
            "chain_event_count": 0,
            "checked": True,
            "break_info": None,
            "repair_info": None,
            "pattern_alert": None,
            "recent_stability_events": [],
        }

    # Cache check: reuse healthy result if file unchanged
    try:
        st = chain_path.stat()
        c_mtime, c_size = st.st_mtime, st.st_size
    except OSError:
        c_mtime, c_size = 0.0, 0

    if (
        _chain_health_cache["result"] is not None
        and _chain_health_cache["mtime"] == c_mtime
        and _chain_health_cache["size"] == c_size
    ):
        return _chain_health_cache["result"]

    from integrity_monitor import _record_hash_for_integrity

    # Structural chain health must not depend on a signing key being available
    # to the dashboard process. Signature verification belongs to evidence
    # verification; Health's Critical state is reserved for current hash/linkage
    # integrity failures in the chain file itself.
    prev_hash: Optional[str] = None
    line_no = 0
    break_info = None
    breaks: list[dict] = []

    with open(chain_path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            stripped = raw_line.strip()
            if not stripped:
                continue
            line_no += 1
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                b = {"break_at_line": line_no, "reason": "invalid_json"}
                if break_info is None:
                    break_info = b
                breaks.append(b)
                prev_hash = None
                continue

            record_hash = rec.get("record_hash")
            if not isinstance(record_hash, str) or not record_hash.startswith("sha256:"):
                b = {"break_at_line": line_no, "reason": "record_hash_missing"}
                if break_info is None:
                    break_info = b
                breaks.append(b)
                prev_hash = record_hash
                continue

            recomputed_hash = _record_hash_for_integrity(rec)
            if recomputed_hash is not None and recomputed_hash != record_hash:
                b = {"break_at_line": line_no, "reason": "record_hash_mismatch"}
                if break_info is None:
                    break_info = b
                breaks.append(b)
                prev_hash = record_hash
                continue

            link = rec.get("prev_record_hash")
            if line_no > 1 and "prev_record_hash" in rec and link != prev_hash:
                b = {"break_at_line": line_no, "reason": "prev_record_hash_mismatch"}
                if break_info is None:
                    break_info = b
                breaks.append(b)
                prev_hash = record_hash
                continue

            prev_hash = record_hash

    recent_events = read_stability_log(stability_log_path, limit=10) if stability_log_path else []

    if break_info is None:
        # Chain is healthy — cache the result
        result = {
            "status": HEALTH_HEALTHY,
            "chain_event_count": line_no,
            "checked": True,
            "break_info": None,
            "break_count": 0,
            "breaks": [],
            "repair_info": None,
            "pattern_alert": None,
            "recent_stability_events": recent_events,
        }
        _chain_health_cache["mtime"] = c_mtime
        _chain_health_cache["size"] = c_size
        _chain_health_cache["result"] = result
        return result

    # Break detected — classify it
    classification = classify_chain_break(
        chain_path, break_info["break_at_line"], break_info["reason"], chain_meta_path
    )
    break_info["classification"] = classification
    break_count = len(breaks)

    # Log the break
    if stability_log_path:
        append_stability_event(stability_log_path, "break_detected", {
            **break_info,
            "classification": classification["classification"],
            "pattern": classification.get("pattern"),
        })

    # Check for break pattern (repeated breaks)
    pattern_alert = None
    if stability_log_path:
        pattern_alert = detect_break_pattern(stability_log_path)

    if pattern_alert:
        return {
            "status": HEALTH_CRITICAL,
            "chain_event_count": line_no,
            "checked": True,
            "break_info": break_info,
            "break_count": break_count,
            "breaks": breaks,
            "repair_info": None,
            "pattern_alert": pattern_alert,
            "recent_stability_events": recent_events,
        }

    # Attempt auto-repair if known
    repair_info = None
    if classification["auto_repairable"] and stability_log_path:
        repair_info = auto_repair_chain(chain_path, classification, stability_log_path)

    if repair_info and repair_info.get("repaired"):
        return {
            "status": HEALTH_HEALTHY_REPAIRED,
            "chain_event_count": line_no,
            "checked": True,
            "break_info": break_info,
            "break_count": break_count,
            "breaks": breaks,
            "repair_info": repair_info,
            "pattern_alert": None,
            "recent_stability_events": read_stability_log(stability_log_path, limit=10),
        }

    if classification["classification"] == "suspicious":
        if stability_log_path:
            append_stability_event(stability_log_path, "suspicious_event", {
                "break_at_line": break_info["break_at_line"],
                "reason": break_info["reason"],
                "guidance": "Investigate the chain file manually. Do not auto-repair. "
                            "The break may indicate tampering or unauthorized access.",
            })
        return {
            "status": HEALTH_ATTENTION,
            "chain_event_count": line_no,
            "checked": True,
            "break_info": break_info,
            "break_count": break_count,
            "breaks": breaks,
            "repair_info": None,
            "pattern_alert": None,
            "recent_stability_events": read_stability_log(stability_log_path, limit=10),
        }

    return {
        "status": HEALTH_ATTENTION,
        "chain_event_count": line_no,
        "checked": True,
        "break_info": break_info,
        "repair_info": repair_info,
        "pattern_alert": None,
        "recent_stability_events": recent_events,
    }


# ---------------------------------------------------------------------------
# Health signal collection
# ---------------------------------------------------------------------------

def _compute_deny_rate(chain_path: Path, window: int = 100, _rows: list = None) -> Dict[str, Any]:
    """Compute DENY rate from recent chain records."""
    if _rows is None:
        if not chain_path.exists():
            return {"deny_count": 0, "allow_count": 0, "total": 0, "deny_rate": 0.0, "anomaly": False}
        _rows = _load_chain_rows_raw(chain_path)

    decisions = []
    for rec in _rows:
        decision = rec.get("policy_decision")
        if decision in ("ALLOW", "DENY"):
            decisions.append(decision)

    recent = decisions[-window:] if len(decisions) > window else decisions
    if not recent:
        return {"deny_count": 0, "allow_count": 0, "total": 0, "deny_rate": 0.0, "anomaly": False}

    deny_count = sum(1 for d in recent if d == "DENY")
    allow_count = sum(1 for d in recent if d == "ALLOW")
    total = len(recent)
    deny_rate = deny_count / total if total > 0 else 0.0

    # Anomaly: compare recent 10 to overall rate
    anomaly = False
    historical_average = deny_rate  # default to same as recent if not enough data
    if len(decisions) > 20:
        overall_deny_rate = sum(1 for d in decisions if d == "DENY") / len(decisions)
        historical_average = overall_deny_rate
        recent_10 = decisions[-10:]
        recent_deny_rate = sum(1 for d in recent_10 if d == "DENY") / len(recent_10)
        if overall_deny_rate > 0 and recent_deny_rate > overall_deny_rate * DENY_RATE_ANOMALY_MULTIPLIER:
            anomaly = True

    return {
        "deny_count": deny_count,
        "allow_count": allow_count,
        "total": total,
        "deny_rate": round(deny_rate, 4),
        "historical_average": round(historical_average, 4),
        "anomaly": anomaly,
    }


def _observation_gap(chain_path: Path, _rows: list = None) -> Dict[str, Any]:
    """Detect gaps in observation data (transparency metric drop)."""
    if _rows is None:
        if not chain_path.exists():
            return {"has_observations": False, "gap_detected": False}
        _rows = _load_chain_rows_raw(chain_path)

    last_governed_ts = None
    last_observation_ts = None
    governed_count = 0
    observation_count = 0

    for rec in _rows:
        ts = rec.get("timestamp_utc")
        if rec.get("event_type") == "ungoverned_operation_observed":
            observation_count += 1
            last_observation_ts = ts
        elif rec.get("policy_decision") in ("ALLOW", "DENY"):
            governed_count += 1
            last_governed_ts = ts

    if observation_count == 0:
        return {"has_observations": False, "gap_detected": False, "governed_count": governed_count}

    # Gap: governed operations happening but no recent observations
    gap_detected = False
    hours_since_last = None
    now_utc = datetime.now(timezone.utc)
    if last_observation_ts:
        obs_dt = _parse_utc(last_observation_ts)
        if obs_dt:
            hours_since_last = round((now_utc - obs_dt).total_seconds() / 3600, 1)
    if last_governed_ts and last_observation_ts:
        gov_dt = _parse_utc(last_governed_ts)
        obs_dt = _parse_utc(last_observation_ts)
        if gov_dt and obs_dt:
            gap_hours = (gov_dt - obs_dt).total_seconds() / 3600
            if gap_hours > 24:
                gap_detected = True

    return {
        "has_observations": True,
        "gap_detected": gap_detected,
        "governed_count": governed_count,
        "observation_count": observation_count,
        "ungoverned_operation_count": observation_count,
        "hours_since_last": hours_since_last,
        "last_governed": last_governed_ts,
        "last_observation": last_observation_ts,
    }


def _user_activity(chain_path: Path, _rows: list = None) -> Dict[str, Any]:
    """Analyze user activity for anomalies."""
    if _rows is None:
        if not chain_path.exists():
            return {"unique_users": 0, "users": {}, "anomalies": []}
        _rows = _load_chain_rows_raw(chain_path)

    user_counts: Counter = Counter()
    for rec in _rows:
        uid = rec.get("actor") or rec.get("user_identity")
        if uid and uid != "unknown":
            user_counts[uid] += 1

    anomalies = []
    if user_counts:
        avg = sum(user_counts.values()) / len(user_counts)
        for uid, count in user_counts.items():
            if avg > 0 and count > avg * 10:
                anomalies.append({
                    "user": uid,
                    "action_count": count,
                    "average": round(avg, 1),
                    "description": f"User '{uid}' has {count} actions ({round(count/avg, 1)}x average).",
                })

    return {
        "unique_users": len(user_counts),
        "users": dict(user_counts.most_common(10)),
        "anomalies": anomalies,
    }


def _license_health(runtime_root: Path) -> Dict[str, Any]:
    """Check license status."""
    try:
        import importlib.util
        license_path = Path(__file__).resolve().parent / "licensing.py"
        if not license_path.exists():
            return {"status": "unknown", "detail": "licensing module not found"}
        spec = importlib.util.spec_from_file_location("licensing_mod", license_path)
        if spec is None or spec.loader is None:
            return {"status": "unknown"}
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "get_license_status"):
            return mod.get_license_status(runtime_root)
        return {"status": "unknown", "detail": "no get_license_status function"}
    except Exception as e:
        return {"status": "unknown", "detail": str(e)}


def _integrity_status(chain_path: Path) -> Dict[str, Any]:
    """Read D-139 integrity metadata for dashboard health display.

    This is intentionally read-only. IntegrityMonitor remains the authority for
    creating and validating the sidecar metadata.
    """
    try:
        from integrity_monitor import IntegrityMonitor, IntegrityViolation

        monitor = IntegrityMonitor(chain_path)
        metadata = monitor.load_metadata()
    except IntegrityViolation as exc:
        return {
            "available": False,
            "status": "metadata_invalid",
            "message": str(exc),
            "proxy_code_hash": None,
            "policy_rules_hash": None,
            "policy_rules_status": "not_available",
            "chain_file_status": "not_available",
        }
    except Exception as exc:
        return {
            "available": False,
            "status": "not_available",
            "message": str(exc),
            "proxy_code_hash": None,
            "policy_rules_hash": None,
            "policy_rules_status": "not_available",
            "chain_file_status": "not_available",
        }

    if not metadata:
        return {
            "available": False,
            "status": "not_available",
            "message": "Integrity metadata has not been created yet.",
            "proxy_code_hash": None,
            "policy_rules_hash": None,
            "policy_rules_status": "not_available",
            "chain_file_status": "not_available",
        }

    blocked_reason = metadata.get("blocked_reason")
    blocked_policy_hash = metadata.get("policy_rules_blocked_hash")
    chain_file_status = "intact"
    if blocked_reason == "chain_file_missing":
        chain_file_status = "missing"
    elif blocked_reason == "chain_file_truncated":
        chain_file_status = "truncated"
    elif blocked_reason in {"chain_record_count_mismatch", "chain_tail_hash_mismatch"}:
        chain_file_status = "changed"

    policy_rules_status = "changed" if blocked_policy_hash else "verified"

    return {
        "available": True,
        "status": "attention" if blocked_reason else "ok",
        "metadata_path": str(monitor.metadata_path),
        "last_updated_utc": metadata.get("last_updated_utc"),
        "proxy_code_hash": metadata.get("proxy_code_hash"),
        "policy_rules_hash": blocked_policy_hash or metadata.get("policy_rules_hash"),
        "policy_rules_status": policy_rules_status,
        "chain_file_status": chain_file_status,
        "blocked_reason": blocked_reason,
    }


def collect_health_signals(
    chain_path: Path,
    stability_log_path: Path,
    chain_meta_path: Path,
    runtime_root: Path,
) -> Dict[str, Any]:
    """Collect all health signals into a unified structure."""
    # Chain health
    chain_health = check_chain_health(chain_path, stability_log_path, chain_meta_path)

    # Storage
    archive_dir = chain_path.parent / "archive"
    records_dir = chain_path.parent / "records"
    storage = {
        "chain_size_bytes": _file_size(chain_path),
        "stability_log_size_bytes": _file_size(stability_log_path),
        "archive_size_bytes": _dir_size(archive_dir),
        "records_dir_size_bytes": _dir_size(records_dir),
        "archive_count": len(list(archive_dir.glob("*.jsonl"))) if archive_dir.exists() else 0,
    }

    # Load chain rows once via the shared incremental cache and pass to sub-signals
    try:
        from readout import load_chain_rows as _readout_load
        _shared_rows = _readout_load(chain_path) if chain_path.exists() else []
    except ImportError:
        _shared_rows = _load_chain_rows_raw(chain_path) if chain_path.exists() else []

    # Policy / DENY rate
    deny_rate = _compute_deny_rate(chain_path, _rows=_shared_rows)

    # User activity
    users = _user_activity(chain_path, _rows=_shared_rows)

    # Legacy health contract retained for CLI/tests; the v3 dashboard no longer
    # renders this as a Transparency card.
    observations = _observation_gap(chain_path, _rows=_shared_rows)

    # License
    license_info = _license_health(runtime_root)

    # D-139 integrity metadata
    integrity = _integrity_status(chain_path)

    # D-153 usage-triggered background verification
    try:
        from background_verifier import read_verification_status
        background_verification = read_verification_status(chain_path)
    except Exception:
        background_verification = {"status": "not_available", "checked": False}

    # Stability events
    recent_events = read_stability_log(stability_log_path, limit=20)

    # Determine overall health status
    overall = HEALTH_HEALTHY
    alerts: List[Dict[str, Any]] = []

    if chain_health["status"] == HEALTH_CRITICAL:
        overall = HEALTH_CRITICAL
        alerts.append({
            "severity": "critical",
            "source": "chain",
            "message": "Repeated chain breaks detected. Possible attack or system failure.",
            "guidance": "Investigate immediately. Check chain file for tampering. Review server access logs.",
        })
    elif chain_health["status"] == HEALTH_ATTENTION:
        overall = HEALTH_ATTENTION
        alerts.append({
            "severity": "attention",
            "source": "chain",
            "message": "Chain integrity issue detected.",
            "guidance": "Review the break details below. Suspicious breaks should be investigated.",
        })
    elif chain_health["status"] == HEALTH_HEALTHY_REPAIRED:
        if overall == HEALTH_HEALTHY:
            overall = HEALTH_HEALTHY_REPAIRED

    if deny_rate.get("anomaly"):
        if overall == HEALTH_HEALTHY or overall == HEALTH_HEALTHY_REPAIRED:
            overall = HEALTH_ATTENTION
        alerts.append({
            "severity": "attention",
            "source": "deny_rate",
            "message": f"DENY rate anomaly: recent DENY rate is significantly above average.",
            "guidance": "Check if policy was recently changed or if an agent is misconfigured.",
        })

    if users.get("anomalies"):
        alerts.append({
            "severity": "info",
            "source": "users",
            "message": f"{len(users['anomalies'])} user activity anomalies detected.",
            "guidance": "Review user activity for unusual patterns.",
        })

    if integrity.get("policy_rules_status") == "changed":
        if overall == HEALTH_HEALTHY or overall == HEALTH_HEALTHY_REPAIRED:
            overall = HEALTH_ATTENTION
        alerts.append({
            "severity": "attention",
            "source": "policy_rules_changed",
            "message": "Policy rules changed while the proxy was running. Atested is denying all governed operations until this is acknowledged.",
            "guidance": "Review the policy change, then acknowledge it to resume normal policy evaluation.",
        })

    if background_verification.get("status") in {"broken", "error"}:
        if overall == HEALTH_HEALTHY or overall == HEALTH_HEALTHY_REPAIRED:
            overall = HEALTH_ATTENTION
        alerts.append({
            "severity": "attention",
            "source": "background_verification",
            "message": "Background chain verification found a problem.",
            "guidance": "Open Chain Integrity details and jump to the break point in the Chain Walker.",
        })

    # Product version
    version = ""
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    if version_file.exists():
        version = version_file.read_text(encoding="utf-8").strip()

    return {
        "timestamp_utc": _now_utc_z(),
        "overall_status": overall,
        "version": version,
        "alerts": alerts,
        "chain": chain_health,
        "deny_rate": deny_rate,
        "storage": storage,
        "integrity": integrity,
        "background_verification": background_verification,
        "observations": observations,
        "users": users,
        "license": license_info,
        "recent_stability_events": recent_events,
        "retention": {
            "active_window_days": DEFAULT_ACTIVE_RETENTION_DAYS,
            "archive_window_days": DEFAULT_ARCHIVE_RETENTION_DAYS,
        },
    }
