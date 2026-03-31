#!/usr/bin/env python3
"""
Render a deterministic text "time ribbon" from integrated E2E records.

Usage:
    time_ribbon.py <records.json>

Input format:
    A JSON array of objects. Each record must include:
      - timestamp_utc
      - record_id
      - speculation_tag

Output:
    Deterministically sorted text rows:
      <timestamp_utc>\t<record_id>\t<speculation_tag>

Exit codes:
    0 = success
    2 = schema/usage error (fail-closed)
"""
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = ("timestamp_utc", "record_id", "speculation_tag")


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fail(msg: str) -> "None":
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(2)


def load_records(path: Path) -> list[dict]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        fail(f"time ribbon input not found: {path}")
    except json.JSONDecodeError as e:
        fail(f"time ribbon input is not valid JSON: {e}")

    if not isinstance(data, list):
        fail("time ribbon input must be a JSON array")

    for idx, rec in enumerate(data):
        if not isinstance(rec, dict):
            fail(f"time ribbon record[{idx}] must be an object")
        for field in REQUIRED_FIELDS:
            if field not in rec:
                fail(
                    f"time ribbon schema error: record[{idx}] missing required field "
                    f"'{field}'"
                )
            if not isinstance(rec[field], str) or not rec[field]:
                fail(
                    f"time ribbon schema error: record[{idx}] field '{field}' "
                    "must be a non-empty string"
                )
    return data


def render(records: list[dict]) -> str:
    # Canonical full-record tiebreaker prevents accidental input-order dependence.
    ordered = sorted(
        records,
        key=lambda rec: (
            rec["timestamp_utc"],
            rec["record_id"],
            rec["speculation_tag"],
            canonical_json(rec),
        ),
    )
    lines = [
        f"{rec['timestamp_utc']}\t{rec['record_id']}\t{rec['speculation_tag']}"
        for rec in ordered
    ]
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: time_ribbon.py <records.json>", file=sys.stderr)
        raise SystemExit(2)

    records = load_records(Path(sys.argv[1]))
    print(render(records))


if __name__ == "__main__":
    main()
