"""Archive-derived artifacts: pre-computed summaries and SQLite databases.

After a chain is archived, this module generates:
  1. A summary JSON with aggregated counts (by tool, decision, user, category).
  2. A SQLite database with full records for audit query access.

The SQLite database includes a metadata table with a SHA-256 hash of the
source archive JSONL for integrity verification.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ARCHIVE_SQLITE_SCHEMA_VERSION = 2


def _sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _parse_archive_rows(archive_path: Path) -> list[dict]:
    """Parse an archive JSONL file into a list of dicts."""
    rows: list[dict] = []
    with open(archive_path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError:
                continue
    return rows


def _first_target(record: dict) -> str:
    classification = record.get("classification")
    if isinstance(classification, dict):
        targets = classification.get("targets")
        if isinstance(targets, list) and targets:
            return str(targets[0])
    for key in ("target", "artifact_identity"):
        value = record.get(key)
        if isinstance(value, str) and value:
            return value
    return ""


def _archive_record_fields(record: dict) -> dict:
    """Return normalized columns for both legacy and v2 archive records."""
    classification = record.get("classification")
    if not isinstance(classification, dict):
        classification = {}
    return {
        "timestamp_utc": (
            record.get("event_timestamp_utc")
            or record.get("timestamp_utc")
            or record.get("primary_import_timestamp_utc")
            or ""
        ),
        "event_type": record.get("event_type") or (
            "action_decision" if record.get("record_type") == "mediated_decision" else ""
        ),
        "user_identity": record.get("user_identity") or record.get("actor") or "",
        "tool_name": (
            record.get("tool_name")
            or record.get("original_tool")
            or record.get("tool")
            or record.get("capability_class")
            or ""
        ),
        "policy_decision": record.get("policy_decision") or "",
        "action_type": record.get("action_type") or classification.get("action_type") or "",
        "confidence_tier": str(record.get("confidence_tier") or classification.get("confidence_tier") or ""),
        "matched_rule": record.get("matched_rule") or "",
        "record_hash": record.get("record_hash") or "",
        "target": _first_target(record),
    }


def generate_summary(archive_jsonl_path: Path, output_path: Path) -> dict:
    """Parse archive JSONL and write a pre-computed summary JSON.

    Returns the summary dict.
    """
    rows = _parse_archive_rows(archive_jsonl_path)

    by_decision: Counter = Counter()
    by_tool: Counter = Counter()
    by_user: Counter = Counter()
    by_category: Counter = Counter()
    timestamps: list[str] = []

    for rec in rows:
        decision = rec.get("policy_decision", "")
        if decision:
            by_decision[decision] += 1
        fields = _archive_record_fields(rec)
        tool = fields.get("tool_name", "")
        if tool:
            by_tool[tool] += 1
        user = rec.get("user_identity") or rec.get("actor", "")
        if user:
            by_user[user] += 1
        cat = rec.get("event_category") or rec.get("event_type", "")
        if not cat and rec.get("record_type") == "mediated_decision":
            cat = "action_decision"
        if cat:
            by_category[cat] += 1
        ts = fields.get("timestamp_utc", "")
        if ts:
            timestamps.append(ts)

    timestamps.sort()
    time_range = {
        "first": timestamps[0] if timestamps else "",
        "last": timestamps[-1] if timestamps else "",
    }

    summary = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_file": str(archive_jsonl_path),
        "source_sha256": _sha256_file(archive_jsonl_path),
        "record_count": len(rows),
        "time_range": time_range,
        "by_decision": dict(by_decision),
        "by_tool": dict(by_tool.most_common(50)),
        "by_user": dict(by_user.most_common(50)),
        "by_category": dict(by_category.most_common(50)),
    }

    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(output_path)
    return summary


_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY,
    timestamp_utc TEXT,
    event_type TEXT,
    user_identity TEXT,
    tool_name TEXT,
    policy_decision TEXT,
    action_type TEXT,
    confidence_tier TEXT,
    matched_rule TEXT,
    target TEXT,
    record_hash TEXT,
    raw_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_timestamp ON records(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_decision ON records(policy_decision);
CREATE INDEX IF NOT EXISTS idx_tool ON records(tool_name);
CREATE INDEX IF NOT EXISTS idx_user ON records(user_identity);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def generate_sqlite(archive_jsonl_path: Path, output_path: Path) -> Path:
    """Parse archive JSONL and write a SQLite database with records + metadata.

    Returns the output path.
    """
    rows = _parse_archive_rows(archive_jsonl_path)
    source_hash = _sha256_file(archive_jsonl_path)

    tmp = output_path.with_suffix(output_path.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()

    conn = sqlite3.connect(str(tmp))
    try:
        conn.executescript(_SQLITE_SCHEMA)

        insert_sql = """
            INSERT INTO records
                (id, timestamp_utc, event_type, user_identity, tool_name,
                 policy_decision, action_type, confidence_tier, matched_rule,
                 target, record_hash, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        batch: list[tuple] = []
        for i, rec in enumerate(rows):
            fields = _archive_record_fields(rec)
            batch.append((
                i + 1,
                fields["timestamp_utc"],
                fields["event_type"],
                fields["user_identity"],
                fields["tool_name"],
                fields["policy_decision"],
                fields["action_type"],
                fields["confidence_tier"],
                fields["matched_rule"],
                fields["target"],
                fields["record_hash"],
                json.dumps(rec, sort_keys=True, separators=(",", ":")),
            ))
            if len(batch) >= 1000:
                conn.executemany(insert_sql, batch)
                batch.clear()

        if batch:
            conn.executemany(insert_sql, batch)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("source_sha256", source_hash),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("schema_version", str(ARCHIVE_SQLITE_SCHEMA_VERSION)),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("archive_id", archive_jsonl_path.stem),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("generated_at", now),
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("record_count", str(len(rows))),
        )
        conn.commit()
    finally:
        conn.close()

    tmp.replace(output_path)
    return output_path


def verify_sqlite_integrity(archive_jsonl_path: Path, sqlite_path: Path) -> bool:
    """Verify that the SQLite database matches the source archive JSONL.

    Compares the stored source_sha256 in the metadata table against the
    current SHA-256 of the archive JSONL file.
    """
    if not sqlite_path.exists() or not archive_jsonl_path.exists():
        return False

    try:
        conn = sqlite3.connect(str(sqlite_path))
        try:
            source_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'source_sha256'"
            ).fetchone()
            schema_row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
        finally:
            conn.close()
    except (sqlite3.Error, OSError):
        return False

    if source_row is None or schema_row is None:
        return False
    if str(schema_row[0]) != str(ARCHIVE_SQLITE_SCHEMA_VERSION):
        return False

    stored_hash = source_row[0]
    actual_hash = _sha256_file(archive_jsonl_path)
    return stored_hash == actual_hash


def get_or_regenerate_sqlite(archive_jsonl_path: Path, sqlite_path: Path) -> Optional[Path]:
    """Return a verified SQLite path, regenerating on integrity failure.

    Returns None if the archive JSONL does not exist.
    """
    if not archive_jsonl_path.exists():
        return None

    if sqlite_path.exists() and verify_sqlite_integrity(archive_jsonl_path, sqlite_path):
        return sqlite_path

    # Regenerate
    return generate_sqlite(archive_jsonl_path, sqlite_path)


def generate_artifacts(archive_jsonl_path: Path, archive_id: str) -> dict:
    """Generate both summary and SQLite artifacts for an archive.

    Files are placed alongside the archive JSONL in the same directory.
    Returns a status dict.
    """
    parent = archive_jsonl_path.parent
    summary_path = parent / f"{archive_id}.summary.json"
    sqlite_path = parent / f"{archive_id}.sqlite"

    result: dict[str, Any] = {
        "archive_id": archive_id,
        "summary_path": str(summary_path),
        "sqlite_path": str(sqlite_path),
        "summary_ok": False,
        "sqlite_ok": False,
    }

    try:
        generate_summary(archive_jsonl_path, summary_path)
        result["summary_ok"] = True
    except Exception as e:
        result["summary_error"] = str(e)

    try:
        generate_sqlite(archive_jsonl_path, sqlite_path)
        result["sqlite_ok"] = True
    except Exception as e:
        result["sqlite_error"] = str(e)

    return result
