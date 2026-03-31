#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVAL="$ROOT/scripts/policy-eval.py"
TRIAGE="$ROOT/scripts/triage-eval.py"
CHAIN_PATH="${GOV_DECISION_CHAIN_PATH:-$ROOT/LOGS/decision-chain.jsonl}"
DEFAULT_SELECTOR_MODE="compat_legacy_single_case"

if [[ $# -ne 1 ]]; then
  echo "Usage: rdd-pass-triage.sh <intent.json>" >&2
  exit 2
fi

INTENT="$1"
TMPDIR_LOCAL="$(mktemp -d "${TMPDIR:-/tmp}/rdd-pass-triage.XXXXXX")"
cleanup() {
  rm -rf "$TMPDIR_LOCAL"
}
trap cleanup EXIT

mkdir -p "$(dirname "$CHAIN_PATH")"

PASS_JSON="$TMPDIR_LOCAL/pass.record.json"
python3 "$EVAL" "$INTENT" > "$PASS_JSON"

python3 - <<'PY' "$PASS_JSON" "$CHAIN_PATH"
import json
import pathlib
import sys

record_path = pathlib.Path(sys.argv[1])
chain_path = pathlib.Path(sys.argv[2])
record = json.loads(record_path.read_text(encoding="utf-8"))
chain_path.parent.mkdir(parents=True, exist_ok=True)
with chain_path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
PY

policy_decision="$(python3 - <<'PY' "$PASS_JSON"
import json, sys
obj = json.load(open(sys.argv[1], encoding="utf-8"))
print(obj.get("policy_decision", ""))
PY
)"

if [[ "$policy_decision" == "UNDECIDED" ]]; then
selector_contract="$(
python3 - <<'PY' "$INTENT" "$DEFAULT_SELECTOR_MODE"
import json
import os
import sys

path = sys.argv[1]
default_mode = sys.argv[2]
req = json.load(open(path, encoding="utf-8"))
ambient_mode = os.environ.get("GOV_TRIAGE_SELECTOR_MODE")

intent = req.get("intent")
if not isinstance(intent, dict):
    print(f"mode={default_mode}")
    print("source=default")
    if ambient_mode is not None:
        print(f"ambient={ambient_mode}")
    raise SystemExit(0)

selector_mode = None
source = "default"
constraints = intent.get("constraints")
if isinstance(constraints, dict):
    selector_mode = constraints.get("selector_mode")
    if selector_mode is not None:
        source = "intent.constraints.selector_mode"

rdd = intent.get("rdd")
legacy_rdd_mode = None
if isinstance(rdd, dict):
    legacy_rdd_mode = rdd.get("selector_mode")
legacy_top_mode = intent.get("selector_mode")

if selector_mode is not None:
    if not isinstance(selector_mode, str) or not selector_mode.strip():
        print("FATAL: RDD_TRIAGE_SELECTOR_MODE_INVALID mode=<non_string_or_empty>", file=sys.stderr)
        raise SystemExit(2)

    mode = selector_mode.strip().lower()
    if mode not in ("compat_legacy_single_case", "explicit"):
        print(f"FATAL: RDD_TRIAGE_SELECTOR_MODE_INVALID mode={mode}", file=sys.stderr)
        raise SystemExit(2)

    if legacy_rdd_mode is not None and legacy_top_mode is not None:
        print(
            "FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT "
            "canonical=intent.constraints.selector_mode "
            "legacy=intent.rdd.selector_mode,intent.selector_mode",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if legacy_rdd_mode is not None:
        print(
            "FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT "
            "canonical=intent.constraints.selector_mode "
            "legacy=intent.rdd.selector_mode",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if legacy_top_mode is not None:
        print(
            "FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT "
            "canonical=intent.constraints.selector_mode "
            "legacy=intent.selector_mode",
            file=sys.stderr,
        )
        raise SystemExit(2)

    print(f"mode={mode}")
    print(f"source={source}")
    if ambient_mode is not None:
        print(f"ambient={ambient_mode}")
    raise SystemExit(0)

if selector_mode is None and legacy_rdd_mode is not None and legacy_top_mode is not None:
    legacy_values = (legacy_rdd_mode, legacy_top_mode)
    if any((not isinstance(v, str)) or (not v.strip()) for v in legacy_values):
        print(
            "FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_VALUE_INVALID "
            "canonical=<absent> "
            "legacy=intent.rdd.selector_mode,intent.selector_mode",
            file=sys.stderr,
        )
        raise SystemExit(2)
    normalized_legacy_values = tuple(v.strip() for v in legacy_values)
    case_normalized_legacy_values = tuple(v.lower() for v in normalized_legacy_values)
    allowed_modes = {"compat_legacy_single_case", "explicit"}
    if any(v not in allowed_modes for v in case_normalized_legacy_values):
        print(
            "FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_VALUE_UNSUPPORTED "
            "canonical=<absent> "
            "legacy=intent.rdd.selector_mode,intent.selector_mode",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if case_normalized_legacy_values[0] == case_normalized_legacy_values[1]:
        print(
            "FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_CONFLICT "
            "canonical=<absent> "
            "legacy=intent.rdd.selector_mode,intent.selector_mode",
            file=sys.stderr,
        )
    else:
        print(
            "FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_MISMATCH "
            "canonical=<absent> "
            "legacy=intent.rdd.selector_mode,intent.selector_mode",
            file=sys.stderr,
        )
    raise SystemExit(2)

if selector_mode is None and legacy_rdd_mode is not None:
    print("FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_FORBIDDEN source=intent.rdd.selector_mode", file=sys.stderr)
    raise SystemExit(2)

if selector_mode is None and legacy_top_mode is not None:
    print("FATAL: RDD_TRIAGE_SELECTOR_MODE_SOURCE_FORBIDDEN source=intent.selector_mode", file=sys.stderr)
    raise SystemExit(2)

if selector_mode is None:
    print(f"mode={default_mode}")
    print("source=default")
    if ambient_mode is not None:
        print(f"ambient={ambient_mode}")
    raise SystemExit(0)

raise SystemExit(0)
PY
  )"
  selector_mode="$(printf '%s\n' "$selector_contract" | awk -F= '/^mode=/{print $2}')"
  selector_mode_source="$(printf '%s\n' "$selector_contract" | awk -F= '/^source=/{print $2}')"
  ambient_selector_mode="$(printf '%s\n' "$selector_contract" | awk -F= '/^ambient=/{print $2}')"

  if [[ -n "$ambient_selector_mode" && "$ambient_selector_mode" != "$selector_mode" ]]; then
    echo "INFO: RDD_TRIAGE_SELECTOR_MODE_AMBIENT_IGNORED ambient=$ambient_selector_mode applied=$selector_mode" >&2
  fi
  echo "INFO: RDD_TRIAGE_SELECTOR_MODE_APPLIED mode=$selector_mode source=$selector_mode_source" >&2
  GOV_TRIAGE_SELECTOR_MODE="$selector_mode" GOV_DECISION_CHAIN_PATH="$CHAIN_PATH" python3 "$TRIAGE" "$PASS_JSON"
  exit 0
fi

cat "$PASS_JSON"
