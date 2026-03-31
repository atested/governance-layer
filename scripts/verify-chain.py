#!/usr/bin/env python3
import argparse
import json
import importlib.util
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from coverage_stamp import validate_coverage_stamp
from event_model import is_non_action_event

VERIFY_RECORD_PATH = Path(__file__).resolve().with_name("verify-record.py")


def load_verify_record_module():
    spec = importlib.util.spec_from_file_location("verify_record_impl", VERIFY_RECORD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load verifier module from {VERIFY_RECORD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def canonical_summary_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def build_summary(
    chain_path: str,
    total_records: int,
    action_count: int,
    non_action_count: int,
    record_type_counts: dict,
    coverage_ok: int,
    coverage_partial: int,
    coverage_missing: int,
    process_states: dict,
):
    completed_rdd_processes = []
    allow_terminal_processes = []
    for process_id in sorted(process_states):
        state = process_states[process_id]
        if (
            state["seen_pass"] == 1
            and state["seen_triage"] == 1
            and state["seen_terminal"] == 1
        ):
            row = {
                "process_id": process_id,
                "pass_policy_decision": state.get("pass_policy_decision"),
                "triage_disposition_type": state.get("triage_disposition_type"),
                "terminal_outcome": state.get("terminal_outcome"),
                "terminal_method": state.get("terminal_method"),
            }
            completed_rdd_processes.append(row)
            if state.get("terminal_outcome") == "ALLOW":
                allow_terminal_processes.append(row)

    return {
        "report_version": "chain_verification_summary_v1",
        "result": "PASS",
        "chain_path_basename": Path(chain_path).name,
        "counts": {
            "records_total": total_records,
            "action_records": action_count,
            "non_action_records": non_action_count,
            "pass_decision": record_type_counts.get("pass_decision", 0),
            "triage_decision": record_type_counts.get("triage_decision", 0),
            "terminal_judgment": record_type_counts.get("terminal_judgment", 0),
        },
        "coverage_summary": {
            "ok": coverage_ok,
            "partial": coverage_partial,
            "missing_or_absent": coverage_missing,
        },
        "rdd_terminal_process_summary": {
            "process_count": len(process_states),
            "completed_rdd_process_count": len(completed_rdd_processes),
            "allow_terminal_process_count": len(allow_terminal_processes),
            "completed_rdd_processes": completed_rdd_processes,
        },
    }

def main():
    ap = argparse.ArgumentParser(description="Verify chain of governance records")
    ap.add_argument("--require-coverage-stamp", action="store_true")
    ap.add_argument("--summary-json")
    ap.add_argument("chain_path")
    args = ap.parse_args()

    path = args.chain_path
    prev_hash = None
    i = 0
    non_action_count = 0
    coverage_missing = 0
    coverage_partial = 0
    coverage_ok = 0
    coverage_rows = []
    process_states = {}
    pass_hash_index = {}
    record_type_counts = {}
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

            # Non-action governance events participate in the hash chain
            # but skip the record_type state machine and coverage stamp
            # logic — they have their own validation in verify-record.
            if is_non_action_event(rec):
                non_action_count += 1
                continue

            record_type = rec.get("record_type")
            if isinstance(record_type, str) and record_type:
                record_type_counts[record_type] = record_type_counts.get(record_type, 0) + 1
            process_id = rec.get("process_id")

            if record_type in ("pass_decision", "triage_decision", "terminal_judgment"):
                if not isinstance(process_id, str) or not process_id:
                    print(f"FAIL: line {i}: record_type {record_type} missing process_id")
                    sys.exit(1)
                state = process_states.setdefault(
                    process_id,
                    {
                        "seen_pass": 0,
                        "seen_triage": 0,
                        "seen_terminal": 0,
                        "pass_policy_decision": None,
                        "triage_disposition_type": None,
                        "terminal_outcome": None,
                        "terminal_method": None,
                    },
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
                    state["pass_policy_decision"] = rec.get("policy_decision")
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
                    disposition = rec.get("disposition")
                    if isinstance(disposition, dict):
                        state["triage_disposition_type"] = disposition.get("type")
                elif record_type == "terminal_judgment":
                    if state["seen_triage"] == 0:
                        print(f"FAIL: line {i}: terminal_judgment appears before triage_decision for process_id {process_id}")
                        sys.exit(1)
                    state["seen_terminal"] += 1
                    if state["seen_terminal"] > 1:
                        print(f"FAIL: line {i}: duplicate terminal_judgment for process_id {process_id}")
                        sys.exit(1)
                    state["terminal_outcome"] = rec.get("outcome")
                    state["terminal_method"] = rec.get("method")

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

    action_count = i - non_action_count
    print(f"PASS: chain verified ({i} records)")
    print(f"Chain Detail: action={action_count} non_action={non_action_count}")
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
    if args.summary_json:
        summary = build_summary(
            chain_path=path,
            total_records=i,
            action_count=action_count,
            non_action_count=non_action_count,
            record_type_counts=record_type_counts,
            coverage_ok=coverage_ok,
            coverage_partial=coverage_partial,
            coverage_missing=coverage_missing,
            process_states=process_states,
        )
        Path(args.summary_json).write_text(canonical_summary_json(summary), encoding="utf-8")
    sys.exit(0)

if __name__ == "__main__":
    main()
