#!/usr/bin/env python3
import argparse
import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from coverage_stamp import validate_coverage_stamp

VERIFY_RECORD_PATH = Path(__file__).resolve().with_name("verify-record.py")


def load_verify_record_module():
    spec = importlib.util.spec_from_file_location("verify_record_impl", VERIFY_RECORD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load verifier module from {VERIFY_RECORD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    ap = argparse.ArgumentParser(description="Verify chain of governance records")
    ap.add_argument("--require-coverage-stamp", action="store_true")
    ap.add_argument("chain_path")
    args = ap.parse_args()

    path = args.chain_path
    prev_hash = None
    i = 0
    coverage_missing = 0
    coverage_partial = 0
    coverage_ok = 0
    coverage_rows = []
    process_states = {}
    pass_hash_index = {}
    try:
        verify_record_mod = load_verify_record_module()
    except Exception as e:
        print(f"FAIL: unable to initialize record verifier: {e}")
        sys.exit(2)

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            i += 1
            try:
                rec = json.loads(line)
            except Exception:
                print(f"FAIL: line {i}: invalid JSON")
                sys.exit(1)

            rc, lines = verify_record_mod.verify_record_dict(
                rec, require_coverage_stamp=args.require_coverage_stamp
            )
            if rc != 0:
                if lines:
                    first = lines[0]
                    if first.startswith("FAIL: "):
                        first = first[len("FAIL: "):]
                    print(f"FAIL: line {i}: {first}")
                    for extra in lines[1:]:
                        print(extra)
                else:
                    print(f"FAIL: line {i}: record verification failed")
                sys.exit(rc)

            link = rec.get("prev_record_hash")
            if i == 1:
                # first record may have null/None prev
                pass
            else:
                if link != prev_hash:
                    print(f"FAIL: line {i}: prev_record_hash mismatch")
                    print(f" expected: {prev_hash}")
                    print(f" actual:   {link}")
                    sys.exit(1)

            prev_hash = rec.get("record_hash")
            record_type = rec.get("record_type")
            process_id = rec.get("process_id")

            if record_type in ("pass_decision", "triage_decision", "terminal_judgment"):
                if not isinstance(process_id, str) or not process_id:
                    print(f"FAIL: line {i}: record_type {record_type} missing process_id")
                    sys.exit(1)
                state = process_states.setdefault(
                    process_id,
                    {"seen_pass": 0, "seen_triage": 0, "seen_terminal": 0},
                )

                if record_type == "pass_decision":
                    if "originating_triage_hash" in rec or "originating_terminal_hash" in rec:
                        print(f"FAIL: line {i}: pass_decision contains forbidden backward-link field")
                        sys.exit(1)
                    state["seen_pass"] += 1
                    if state["seen_pass"] > 1:
                        print(f"FAIL: line {i}: duplicate pass_decision for process_id {process_id}")
                        sys.exit(1)
                    if not isinstance(rec.get("record_hash"), str) or not rec.get("record_hash"):
                        print(f"FAIL: line {i}: pass_decision missing record_hash")
                        sys.exit(1)
                    pass_hash_index[rec["record_hash"]] = rec
                elif record_type == "triage_decision":
                    if state["seen_pass"] == 0:
                        print(f"FAIL: line {i}: triage_decision appears before pass_decision for process_id {process_id}")
                        sys.exit(1)
                    if state["seen_terminal"] > 0:
                        print(f"FAIL: line {i}: triage_decision appears after terminal_judgment for process_id {process_id}")
                        sys.exit(1)
                    state["seen_triage"] += 1
                    if state["seen_triage"] > 1:
                        print(f"FAIL: line {i}: duplicate triage_decision for process_id {process_id}")
                        sys.exit(1)
                    originating_pass_hash = rec.get("originating_pass_hash")
                    if not isinstance(originating_pass_hash, str) or not originating_pass_hash:
                        print(f"FAIL: line {i}: triage_decision missing originating_pass_hash")
                        sys.exit(1)
                    pass_rec = pass_hash_index.get(originating_pass_hash)
                    if pass_rec is None:
                        print(f"FAIL: line {i}: triage_decision references missing originating_pass_hash")
                        sys.exit(1)
                    if pass_rec.get("policy_decision") != "UNDECIDED":
                        print(f"FAIL: line {i}: triage_decision references non-UNDECIDED pass record")
                        sys.exit(1)
                elif record_type == "terminal_judgment":
                    if state["seen_triage"] == 0:
                        print(f"FAIL: line {i}: terminal_judgment appears before triage_decision for process_id {process_id}")
                        sys.exit(1)
                    state["seen_terminal"] += 1
                    if state["seen_terminal"] > 1:
                        print(f"FAIL: line {i}: duplicate terminal_judgment for process_id {process_id}")
                        sys.exit(1)

            coverage = validate_coverage_stamp(
                rec.get("coverage_stamp"), required=args.require_coverage_stamp
            )
            coverage_rows.append(
                {
                    "line": i,
                    "overall_status": coverage.overall_status,
                    "reason_code": coverage.reason_code,
                }
            )
            if coverage.reason_code == "COVERAGE_STAMP_OK":
                coverage_ok += 1
            elif coverage.reason_code == "COVERAGE_STAMP_PARTIAL":
                coverage_partial += 1
            else:
                coverage_missing += 1

    print(f"PASS: chain verified ({i} records)")
    for row in sorted(coverage_rows, key=lambda r: r["line"]):
        print(
            "coverage_record line={line} overall_status={status} reason_code={reason}".format(
                line=row["line"],
                status=row["overall_status"],
                reason=row["reason_code"],
            )
        )
    print(
        "Coverage Summary: ok={ok} partial={partial} missing_or_absent={missing}".format(
            ok=coverage_ok, partial=coverage_partial, missing=coverage_missing
        )
    )
    sys.exit(0)

if __name__ == "__main__":
    main()
