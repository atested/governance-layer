#!/usr/bin/env bash
set -euo pipefail

QT_USAGE_LEDGER_PATH="${QT_USAGE_LEDGER_PATH:-system/logs/qt-usage.jsonl}"

python3 - "$QT_USAGE_LEDGER_PATH" <<'PY'
import json
import sys
from pathlib import Path

ledger_path = Path(sys.argv[1])
if not ledger_path.exists():
    print("QT: 0 | P:0 F:0 | Last:none | 0s")
    raise SystemExit(0)

events = []
for raw in ledger_path.read_text(encoding="utf-8", errors="replace").splitlines():
    raw = raw.strip()
    if not raw:
        continue
    try:
        events.append(json.loads(raw))
    except json.JSONDecodeError:
        continue

if not events:
    print("QT: 0 | P:0 F:0 | Last:none | 0s")
    raise SystemExit(0)

total = len(events)
passes = sum(1 for e in events if e.get("status") == "PASS")
fails = sum(1 for e in events if e.get("status") == "FAIL")
last = events[-1]
task_id = last.get("task_id") or "unknown"
job_type = last.get("qt_job_type") or ""
seconds = last.get("wall_clock_seconds")

if task_id == "unknown" and not job_type:
    last_part = "none"
else:
    last_part = " ".join(part for part in (task_id, job_type) if part).strip() or "none"

try:
    seconds_value = int(seconds)
except (TypeError, ValueError):
    seconds_value = 0

print(f"QT: {total} | P:{passes} F:{fails} | Last:{last_part} | {seconds_value}s")
PY
