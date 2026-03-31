#!/usr/bin/env python3
"""
replay-record.py — Deterministic replay verifier for governance decision records.

Replays the original request embedded in a decision record and asserts that the
replay output matches the original on all deterministic invariants:
  1. policy_decision  (ALLOW / DENY)
  2. reason_codes     (ordered list of policy_reasons[*].code)
  3. tool             (registered tool name)
  4. cap_registry_hash (internal on-disk registry hash at replay time)
  5. normalized_args  (strict deep-equal)

Non-deterministic fields (timestamp_utc, session_id, request_id, record_hash,
prev_record_hash) are intentionally excluded from comparison.

Requires records produced at Phase 2B.3 or later (request_bytes_b64 + request_hash
must be present). Pre-2B.3 records are rejected with a clear error.

Usage:
    replay-record.py <decision-record.json> [more-records.json ...]

Exit codes:
    0 — all invariants match
    1 — invariant mismatch (diff printed to stdout)
    2 — fatal error (missing fields, hash mismatch, subprocess failure)
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from coverage_stamp import validate_coverage_stamp, canonical_json

SCRIPTS = Path(__file__).resolve().parent
POLICY_EVAL = SCRIPTS / "policy-eval.py"
VERIFY_RECORD = SCRIPTS / "verify-record.py"

NON_DETERMINISTIC = frozenset([
    "timestamp_utc",
    "session_id",
    "request_id",
    "record_hash",
    "prev_record_hash",
    "signature",
    "signing_key_id",
    # request_bytes_b64 and request_hash are identical by construction (same bytes),
    # so they would always match — but we verify them separately via sha256 check.
])
TEST_MUTATION_ENV = "GOV_REPLAY_TEST_MUTATION"
INVARIANT_FIELDS = (
    "policy_decision",
    "tool",
    "cap_registry_hash",
    "normalized_args",
    "reason_codes",
    "coverage_stamp",
)
STRICTNESS_CHOICES = ("error", "mismatch", "ignore")
RDD_REPLAYABLE_TYPES = frozenset(("triage_decision", "terminal_judgment"))


def sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load_verify_record_module():
    spec = importlib.util.spec_from_file_location("verify_record_impl", VERIFY_RECORD)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load verifier module from {VERIFY_RECORD}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_reason_codes(record: dict) -> list:
    return [r["code"] for r in record.get("policy_reasons", [])]


def compare_invariants(orig: dict, replay: dict) -> list:
    """Return list of mismatch dicts for deterministic invariants."""
    mismatches = []
    checks = [
        ("policy_decision",  "raw", orig.get("policy_decision"),   replay.get("policy_decision"),
         "policy_decision" in orig, "policy_decision" in replay),
        ("tool",             "raw", orig.get("tool"),               replay.get("tool"),
         "tool" in orig, "tool" in replay),
        ("cap_registry_hash", "raw", orig.get("cap_registry_hash"), replay.get("cap_registry_hash"),
         "cap_registry_hash" in orig, "cap_registry_hash" in replay),
        ("normalized_args",  "raw", orig.get("normalized_args"),   replay.get("normalized_args"),
         "normalized_args" in orig, "normalized_args" in replay),
        ("reason_codes",     "derived", extract_reason_codes(orig), extract_reason_codes(replay), True, True),
        (
            "coverage_stamp",
            "derived",
            orig.get("__coverage_stamp_canonical"),
            replay.get("__coverage_stamp_canonical"),
            True,
            True,
        ),
    ]
    for field, source_kind, old_val, new_val, old_present, new_present in checks:
        if old_val != new_val:
            kind = "value"
            if source_kind == "raw" and old_present and not new_present:
                kind = "missing"
            elif source_kind == "raw" and (type(old_val) is not type(new_val)):
                kind = "type"
            mismatches.append({"field": field, "kind": kind, "original": old_val, "replay": new_val})
    if "__replay_test_extra_invariant__" in replay:
        mismatches.append({
            "field": "__replay_test_extra_invariant__",
            "kind": "extra",
            "original": None,
            "replay": replay["__replay_test_extra_invariant__"],
        })
    return mismatches


def apply_strictness(mismatches: list, strict_missing: str, strict_extra: str) -> dict:
    kept = []
    ignored = []
    fatals = []
    for m in mismatches:
        kind = m.get("kind")
        if kind == "missing":
            mode = strict_missing
        elif kind == "extra":
            mode = strict_extra
        else:
            mode = "mismatch"
        if mode == "ignore":
            ignored.append(dict(m))
            continue
        if mode == "error":
            fatals.append(dict(m))
            continue
        kept.append(dict(m))
    fatal_reason = None
    if fatals:
        first = fatals[0]
        if first.get("kind") == "missing":
            fatal_reason = f"strict_missing=error triggered for field {first['field']}"
        elif first.get("kind") == "extra":
            fatal_reason = f"strict_extra=error triggered for field {first['field']}"
        else:
            fatal_reason = f"strictness error triggered for field {first['field']}"
    return {
        "mismatches": sorted_mismatches(kept),
        "ignored_findings": sorted_mismatches(ignored),
        "fatal_findings": sorted_mismatches(fatals),
        "fatal_reason": fatal_reason,
    }


def sorted_mismatches(mismatches: list) -> list:
    return sorted(
        mismatches,
        key=lambda m: (
            m.get("field", ""),
            m.get("kind", ""),
            json.dumps(m.get("original"), sort_keys=True, separators=(",", ":")),
            json.dumps(m.get("replay"), sort_keys=True, separators=(",", ":")),
        ),
    )


def apply_test_mutation(replay: dict) -> dict:
    mode = os.environ.get(TEST_MUTATION_ENV, "").strip()
    if not mode:
        return replay
    mutated = json.loads(json.dumps(replay))
    if mode == "drop_normalized_args":
        mutated.pop("normalized_args", None)
        return mutated
    if mode == "add_extra_invariant":
        mutated["__replay_test_extra_invariant__"] = {"probe": True}
        return mutated
    if mode == "mismatch_tool_value":
        mutated["tool"] = "FS_WRITE" if mutated.get("tool") != "FS_WRITE" else "FS_READ"
        return mutated
    if mode == "type_mismatch_cap_registry_hash":
        mutated["cap_registry_hash"] = 12345
        return mutated
    if mode == "mismatch_reason_codes_order":
        reasons = mutated.get("policy_reasons")
        if isinstance(reasons, list) and len(reasons) >= 2:
            mutated["policy_reasons"] = list(reversed(reasons))
            return mutated
        # Ensure deterministic mismatch even if fixture only has one reason.
        mutated["policy_reasons"] = [{"code": "RC-REPLAY-TEST-MISMATCH"}]
        return mutated
    raise ValueError(f"unsupported {TEST_MUTATION_ENV} mode: {mode}")


def record_hash_digest_bytes(record: dict) -> bytes:
    record_hash = record.get("record_hash")
    if not isinstance(record_hash, str) or not record_hash.startswith("sha256:"):
        raise ValueError("record_hash missing or invalid")
    digest_hex = record_hash.split(":", 1)[1]
    if len(digest_hex) != 64:
        raise ValueError("record_hash has unexpected digest length")
    try:
        return bytes.fromhex(digest_hex)
    except ValueError as e:
        raise ValueError(f"record_hash is not valid hex: {e}") from e


def compute_records_sha(records: list) -> str:
    # Order-independent aggregate over stable per-record identifiers only.
    digests = sorted(record_hash_digest_bytes(rec) for rec in records)
    return sha256_hex(b"".join(digests))


def fail_fatal(msg: str, rc: int = 2) -> dict:
    return {"kind": "fatal", "exit_code": rc, "message": msg}


def _verify_replay_candidate(
    verify_mod,
    record: dict,
    *,
    require_coverage_stamp: bool,
    context: str,
    check_cap_registry_hash: bool = True,
) -> Optional[dict]:
    rc, lines = verify_mod.verify_record_dict(
        record,
        require_coverage_stamp=require_coverage_stamp,
        check_cap_registry_hash=check_cap_registry_hash,
    )
    if rc == 0:
        return None
    first_line = lines[0] if lines else f"FAIL: {context} verification failed"
    return fail_fatal(first_line.replace("FAIL: ", ""), rc=rc)


def _required_originating_field(record_type: str) -> str:
    if record_type == "triage_decision":
        return "originating_pass_hash"
    if record_type == "terminal_judgment":
        return "originating_triage_hash"
    return ""


def _validate_rdd_replay_record_shape(rec: dict) -> tuple[int, list]:
    record_type = rec.get("record_type")
    if record_type not in RDD_REPLAYABLE_TYPES:
        return 2, [f"FAIL: unsupported record_type for replay extension: {record_type}"]
    process_id = rec.get("process_id")
    if not isinstance(process_id, str) or not process_id:
        return 1, [f"FAIL: {record_type} missing process_id"]
    origin_field = _required_originating_field(record_type)
    origin_value = rec.get(origin_field)
    if not isinstance(origin_value, str) or not origin_value:
        return 1, [f"FAIL: {record_type} missing required field {origin_field}"]
    return 0, []


def _rdd_replay_projection(rec: dict) -> dict:
    record_type = rec.get("record_type")
    proj = {
        "record_type": record_type,
        "process_id": rec.get("process_id"),
        "coverage_stamp": rec.get("__coverage_stamp_canonical"),
    }
    origin_field = _required_originating_field(record_type)
    if origin_field:
        proj[origin_field] = rec.get(origin_field)
    return proj


def compare_rdd_replay_invariants(orig: dict, replay: dict) -> list:
    mismatches = []
    fields = ("record_type", "process_id", "coverage_stamp")
    origin_field = _required_originating_field(orig.get("record_type"))
    if origin_field:
        fields = fields + (origin_field,)
    for field in fields:
        old_val = orig.get(field)
        new_val = replay.get(field)
        if old_val != new_val:
            kind = "value"
            if old_val is not None and new_val is None:
                kind = "missing"
            elif (old_val is not None and new_val is not None) and (type(old_val) is not type(new_val)):
                kind = "type"
            mismatches.append({"field": field, "kind": kind, "original": old_val, "replay": new_val})
    if "__replay_test_extra_invariant__" in replay:
        mismatches.append({
            "field": "__replay_test_extra_invariant__",
            "kind": "extra",
            "original": None,
            "replay": replay["__replay_test_extra_invariant__"],
        })
    return mismatches


def replay_record(
    record_path: str,
    strict_missing: str = "mismatch",
    strict_extra: str = "mismatch",
    require_coverage_stamp: bool = False,
) -> dict:
    try:
        with open(record_path, "r", encoding="utf-8") as f:
            orig = json.load(f)
    except Exception as e:
        return fail_fatal(f"cannot load record '{record_path}': {e}")

    try:
        verify_mod = load_verify_record_module()
    except Exception as e:
        return fail_fatal(f"unable to initialize verify-record module: {e}")

    record_type = orig.get("record_type")
    if record_type in RDD_REPLAYABLE_TYPES:
        shape_rc, shape_lines = _validate_rdd_replay_record_shape(orig)
        if shape_rc != 0:
            return fail_fatal(shape_lines[0].replace("FAIL: ", ""), rc=shape_rc)
        verify_failure = _verify_replay_candidate(
            verify_mod,
            orig,
            require_coverage_stamp=require_coverage_stamp,
            context="original record",
            check_cap_registry_hash=False,
        )
        if verify_failure is not None:
            return verify_failure
        orig_cov = validate_coverage_stamp(orig.get("coverage_stamp"), required=require_coverage_stamp)
        if not orig_cov.ok:
            return fail_fatal(f"{orig_cov.reason_code}: {orig_cov.message}", rc=1)
        orig_proj = _rdd_replay_projection({
            **orig,
            "__coverage_stamp_canonical": canonical_json(orig_cov.normalized) if orig_cov.normalized else "",
        })
        replay_proj = apply_test_mutation(dict(orig_proj))
        strict_eval = apply_strictness(
            compare_rdd_replay_invariants(orig_proj, replay_proj),
            strict_missing,
            strict_extra,
        )
        mismatches = strict_eval["mismatches"]
        ignored_findings = strict_eval["ignored_findings"]
        fatal_findings = strict_eval["fatal_findings"]
        fatal_reason = strict_eval["fatal_reason"]
        if fatal_reason is not None:
            kind = "fatal"
            exit_code = 2
        elif mismatches:
            kind = "mismatch"
            exit_code = 1
        else:
            kind = "pass"
            exit_code = 0
        return {
            "kind": kind,
            "exit_code": exit_code,
            "record": orig,
            "record_path": record_path,
            "record_hash": orig.get("record_hash"),
            "tool": orig.get("tool"),
            "decision": orig.get("policy_decision"),
            "reason_codes": extract_reason_codes(orig),
            "mismatches": mismatches,
            "ignored_findings": ignored_findings,
            "fatal_findings": fatal_findings,
            "fatal_reason": fatal_reason,
            "coverage_reason_code": orig_cov.reason_code,
            "coverage_overall_status": orig_cov.overall_status,
        }

    if record_type and record_type != "pass_decision":
        return fail_fatal(
            f"unsupported record_type for replay path: {record_type}. supported: pass_decision, triage_decision, terminal_judgment",
            rc=2,
        )

    verify_failure = _verify_replay_candidate(
        verify_mod,
        orig,
        require_coverage_stamp=require_coverage_stamp,
        context="original record",
        check_cap_registry_hash=False,
    )
    if verify_failure is not None:
        return verify_failure

    # Require embedded request bytes (Phase 2B.3+ records only).
    b64 = orig.get("request_bytes_b64")
    stored_hash = orig.get("request_hash")
    if not b64 or not stored_hash:
        return fail_fatal(
            "record missing request_bytes_b64 or request_hash.\n"
            "  Only records produced at Phase 2B.3 or later are replayable."
        )

    # Decode and verify request bytes hash before any evaluation.
    try:
        raw = base64.b64decode(b64)
    except Exception as e:
        return fail_fatal(f"request_bytes_b64 is not valid base64: {e}")

    recomputed_hash = sha256_hex(raw)
    if recomputed_hash != stored_hash:
        return fail_fatal(
            f"request_hash mismatch (record tampered or corrupted)\n"
            f"  stored:     {stored_hash}\n"
            f"  recomputed: {recomputed_hash}"
        )

    # Write raw bytes to an isolated temp file; no path injection possible.
    with tempfile.TemporaryDirectory(prefix="gov_replay_") as tdir:
        tmp_intent = Path(tdir) / "replay_intent.json"
        tmp_intent.write_bytes(raw)

        # Invoke policy-eval with no external registry arg (internal path only).
        result = subprocess.run(
            [sys.executable, str(POLICY_EVAL), str(tmp_intent)],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return fail_fatal(
                f"policy-eval exited {result.returncode} during replay.\n"
                f"  stderr: {result.stderr.strip()}"
            )

        replay_out = result.stdout.strip()
        if not replay_out:
            return fail_fatal(
                f"policy-eval produced no output during replay.\n"
                f"  stderr: {result.stderr.strip()}"
            )

        try:
            replay = json.loads(replay_out)
        except Exception as e:
            return fail_fatal(f"policy-eval replay output is not valid JSON: {e}")

    verify_failure = _verify_replay_candidate(
        verify_mod,
        replay,
        require_coverage_stamp=require_coverage_stamp,
        context="replay output",
    )
    if verify_failure is not None:
        return verify_failure

    try:
        replay = apply_test_mutation(replay)
    except Exception as e:
        return fail_fatal(f"{TEST_MUTATION_ENV} failed: {e}")

    # Compare deterministic invariants.
    orig_cov = validate_coverage_stamp(orig.get("coverage_stamp"), required=require_coverage_stamp)
    if not orig_cov.ok:
        return fail_fatal(f"{orig_cov.reason_code}: {orig_cov.message}", rc=1)
    replay_cov = validate_coverage_stamp(replay.get("coverage_stamp"), required=require_coverage_stamp)
    if not replay_cov.ok:
        return fail_fatal(f"{replay_cov.reason_code}: {replay_cov.message}", rc=1)
    orig["__coverage_stamp_canonical"] = canonical_json(orig_cov.normalized) if orig_cov.normalized else ""
    replay["__coverage_stamp_canonical"] = canonical_json(replay_cov.normalized) if replay_cov.normalized else ""

    strict_eval = apply_strictness(compare_invariants(orig, replay), strict_missing, strict_extra)
    mismatches = strict_eval["mismatches"]
    ignored_findings = strict_eval["ignored_findings"]
    fatal_findings = strict_eval["fatal_findings"]
    fatal_reason = strict_eval["fatal_reason"]
    if fatal_reason is not None:
        kind = "fatal"
        exit_code = 2
    elif mismatches:
        kind = "mismatch"
        exit_code = 1
    else:
        kind = "pass"
        exit_code = 0
    result = {
        "kind": kind,
        "exit_code": exit_code,
        "record": orig,
        "record_path": record_path,
        "record_hash": orig.get("record_hash"),
        "tool": orig.get("tool"),
        "decision": orig.get("policy_decision"),
        "reason_codes": extract_reason_codes(orig),
        "mismatches": mismatches,
        "ignored_findings": ignored_findings,
        "fatal_findings": fatal_findings,
        "fatal_reason": fatal_reason,
        "coverage_reason_code": orig_cov.reason_code,
        "coverage_overall_status": orig_cov.overall_status,
    }
    return result


def print_replay_result(result: dict) -> None:
    def _print_ignored():
        for m in result.get("ignored_findings", []):
            print(f"  ignored_field: {m['field']}")
            if "kind" in m:
                print(f"  ignored_kind:  {m['kind']}")

    if result["kind"] == "fatal":
        if "message" in result:
            print(f"FAIL: {result['message']}", file=sys.stderr)
            return
        print(f"FAIL: {result['fatal_reason']}")
        for m in result.get("fatal_findings", []):
            print(f"  field:    {m['field']}")
            if "kind" in m:
                print(f"  kind:     {m['kind']}")
            print(f"  original: {m['original']}")
            print(f"  replay:   {m['replay']}")
        _print_ignored()
        return
    if result["kind"] == "pass":
        record_label = Path(result["record_path"]).name
        print(
            f"PASS: replay matches original "
            f"(record={record_label}, decision={result['decision']}, "
            f"tool={result['tool']}, reason_codes={result['reason_codes']})"
        )
        print(
            "Coverage Summary: overall_status={status} reason_code={reason}".format(
                status=result.get("coverage_overall_status", "missing"),
                reason=result.get("coverage_reason_code", "COVERAGE_STAMP_MISSING"),
            )
        )
        _print_ignored()
        return
    mismatches = result["mismatches"]
    print(f"FAIL: replay mismatch on {len(mismatches)} invariant(s):")
    for m in mismatches:
        print(f"  field:    {m['field']}")
        if "kind" in m:
            print(f"  kind:     {m['kind']}")
        print(f"  original: {m['original']}")
        print(f"  replay:   {m['replay']}")
    _print_ignored()


def build_audit_report(results: list) -> dict:
    records = []
    checked = 0
    mismatched = 0
    matched = 0
    missing = 0
    extra = 0
    for r in results:
        if r["kind"] == "fatal":
            records.append({
                "kind": "fatal",
                "record_path": r.get("record_path"),
                "message": r.get("message"),
                "fatal_reason": r.get("fatal_reason"),
                "fatal_findings": r.get("fatal_findings", []),
                "ignored_findings": r.get("ignored_findings", []),
            })
            continue
        rec_mismatches = r["mismatches"]
        ignored_findings = r.get("ignored_findings", [])
        checked += len(INVARIANT_FIELDS)
        mismatched += len(rec_mismatches)
        matched += len(INVARIANT_FIELDS) - sum(1 for m in rec_mismatches if m.get("kind") != "extra")
        missing += sum(1 for m in rec_mismatches if m.get("kind") == "missing")
        extra += sum(1 for m in rec_mismatches if m.get("kind") == "extra")
        records.append({
            "kind": r["kind"],
            "record_path": r["record_path"],
            "record_hash": r["record_hash"],
            "tool": r["tool"],
            "decision": r["decision"],
            "coverage_overall_status": r.get("coverage_overall_status"),
            "coverage_reason_code": r.get("coverage_reason_code"),
            "reason_codes": r["reason_codes"],
            "mismatches": rec_mismatches,
            "ignored_findings": ignored_findings,
            "fatal_reason": r.get("fatal_reason"),
        })
    records = sorted(records, key=lambda r: (r.get("record_hash") or "", r.get("record_path") or ""))
    return {
        "report_version": "replay_audit_summary_v1",
        "generator": {
            "script": Path(__file__).name,
            "hash_algo": "sha256",
        },
        "record_counts": {
            "total": len(results),
            "matched": sum(1 for r in results if r.get("kind") == "pass"),
            "mismatched": sum(1 for r in results if r.get("kind") == "mismatch"),
            "fatal": sum(1 for r in results if r.get("kind") == "fatal"),
        },
        "invariant_counts": {
            "total_checked": checked,
            "matched": matched,
            "mismatched": mismatched,
            "missing": missing,
            "extra": extra,
        },
        "strictness": {
            "missing": results[0].get("strict_missing", "mismatch") if results else "mismatch",
            "extra": results[0].get("strict_extra", "mismatch") if results else "mismatch",
        },
        "records": records,
    }


def write_audit_report(path_value: str, report: dict) -> None:
    payload = (json.dumps(report, sort_keys=True, separators=(",", ":")) + "\n")
    if path_value == "-":
        sys.stdout.write(payload)
        return
    Path(path_value).write_text(payload, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(
        description="Deterministic replay verifier for governance decision records."
    )
    ap.add_argument("--audit-report-json", dest="audit_report_json", default=None,
                    help="Write deterministic mismatch summary JSON to path (use '-' for stdout)")
    ap.add_argument("--strict-missing", choices=STRICTNESS_CHOICES, default="mismatch")
    ap.add_argument("--strict-extra", choices=STRICTNESS_CHOICES, default="mismatch")
    ap.add_argument("--require-coverage-stamp", action="store_true")
    ap.add_argument("record_paths", nargs="+")
    args = ap.parse_args()

    results = []
    ok_records = []
    final_rc = 0
    for p in args.record_paths:
        res = replay_record(
            p,
            strict_missing=args.strict_missing,
            strict_extra=args.strict_extra,
            require_coverage_stamp=args.require_coverage_stamp,
        )
        res.setdefault("record_path", p)
        res["strict_missing"] = args.strict_missing
        res["strict_extra"] = args.strict_extra
        results.append(res)
        print_replay_result(res)
        if res["kind"] == "pass":
            ok_records.append(res["record"])
            continue
        final_rc = res["exit_code"]
        break

    if args.audit_report_json:
        write_audit_report(args.audit_report_json, build_audit_report(results))

    if final_rc == 0:
        print(f"RECORDS_SHA={compute_records_sha(ok_records)}")
    sys.exit(final_rc)


if __name__ == "__main__":
    main()
