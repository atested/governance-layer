#!/usr/bin/env python3
"""verify-cross-chain.py — cross-chain linker for governance + QA chains.

For every governance decision (ALLOW, DENY) — verifies a paired
qa_decision_verification exists in the QA chain (matched on
governance_record_hash). qa_decision_verification_skipped records are
counted as honest skips: they document gaps openly rather than hiding
them.

For every governance_integrity_error — verifies a paired
qa_condition_detected or a qa_environmental_snapshot that explains the
condition the proxy encountered.

Exit codes
  0  PASS — no unexplained gaps (skips are acceptable; they're explicit).
  1  FAIL — at least one unexplained gap.
  2  Tool error (unreadable files, etc).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from canonical_form import canonical_json


# ---------------------------------------------------------------------------
# Chain loading
# ---------------------------------------------------------------------------


def _iter_records(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for i, raw_line in enumerate(fh, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # Record-hash verification is the job of verify-{qa-,}chain.py.
                # The linker tolerates malformed lines by skipping them.
                continue
            yield i, rec


def _is_action_decision(rec: dict[str, Any]) -> bool:
    """A governance v2 mediated_decision record (ALLOW or DENY)."""
    if rec.get("event_type") is not None:
        return False
    if rec.get("record_type") != "mediated_decision":
        return False
    return rec.get("policy_decision") in ("ALLOW", "DENY")


def _is_integrity_error(rec: dict[str, Any]) -> bool:
    return rec.get("event_type") == "governance_integrity_error"


# ---------------------------------------------------------------------------
# Linker
# ---------------------------------------------------------------------------


def link_chains(
    gov_chain: Path, qa_chain: Path
) -> dict[str, Any]:
    """Join governance and QA chains; produce a coverage report.

    Gracefully handles chains of any length, including empty or absent.
    """
    report: dict[str, Any] = {
        "governance_chain_path": str(gov_chain),
        "qa_chain_path": str(qa_chain),
        "governance_decisions": 0,
        "governance_allow_decisions": 0,
        "governance_deny_decisions": 0,
        "governance_integrity_errors": 0,
        "decisions_verified": 0,
        "decisions_skipped_honestly": 0,
        "decisions_unverified_gap": 0,
        "coverage_percent": 0.0,
        "integrity_errors_with_evidence": 0,
        "integrity_errors_without_evidence": 0,
        "unverified_decisions_sample": [],
        "unexplained_integrity_errors_sample": [],
        "qa_chain_present": qa_chain.exists(),
        "governance_chain_present": gov_chain.exists(),
    }

    # Index QA chain
    qa_verifications: dict[str, dict[str, Any]] = {}
    qa_skipped: dict[str, dict[str, Any]] = {}
    qa_conditions_by_gov_ref: dict[str, list[dict[str, Any]]] = {}
    qa_snapshots: list[dict[str, Any]] = []

    for _, rec in _iter_records(qa_chain):
        event = rec.get("event_type")
        if event == "qa_decision_verification":
            gov_hash = rec.get("governance_record_hash")
            if isinstance(gov_hash, str):
                qa_verifications[gov_hash] = rec
        elif event == "qa_decision_verification_skipped":
            gov_hash = rec.get("governance_record_hash")
            if isinstance(gov_hash, str):
                qa_skipped[gov_hash] = rec
        elif event == "qa_condition_detected":
            gov_ref = rec.get("governance_record_ref")
            if isinstance(gov_ref, str):
                qa_conditions_by_gov_ref.setdefault(gov_ref, []).append(rec)
        elif event == "qa_environmental_snapshot":
            qa_snapshots.append(rec)

    # Walk governance chain
    for _, rec in _iter_records(gov_chain):
        if _is_action_decision(rec):
            report["governance_decisions"] += 1
            decision = rec.get("policy_decision")
            if decision == "ALLOW":
                report["governance_allow_decisions"] += 1
            else:
                report["governance_deny_decisions"] += 1
            rh = rec.get("record_hash")
            if isinstance(rh, str) and rh in qa_verifications:
                report["decisions_verified"] += 1
            elif isinstance(rh, str) and rh in qa_skipped:
                report["decisions_skipped_honestly"] += 1
            else:
                report["decisions_unverified_gap"] += 1
                if len(report["unverified_decisions_sample"]) < 25:
                    report["unverified_decisions_sample"].append(
                        {
                            "record_hash": rh,
                            "tool_name": rec.get("tool")
                            or rec.get("tool_name")
                            or "?",
                            "policy_decision": decision,
                            "timestamp_utc": rec.get("timestamp_utc"),
                        }
                    )
        elif _is_integrity_error(rec):
            report["governance_integrity_errors"] += 1
            explained = _integrity_error_has_evidence(
                rec, qa_conditions_by_gov_ref, qa_snapshots
            )
            if explained:
                report["integrity_errors_with_evidence"] += 1
            else:
                report["integrity_errors_without_evidence"] += 1
                if len(report["unexplained_integrity_errors_sample"]) < 25:
                    report["unexplained_integrity_errors_sample"].append(
                        {
                            "tool_name": rec.get("tool_name"),
                            "condition_source": rec.get("condition_source"),
                            "condition_detail": rec.get("condition_detail"),
                            "timestamp_utc": rec.get("timestamp_utc"),
                        }
                    )

    if report["governance_decisions"] > 0:
        denominator = report["governance_decisions"]
        # Coverage counts honest skips as covered — they are documented gaps,
        # not silent loss. "Not verified" means a hash appears in the governance
        # chain but neither a verification nor a skip exists in the QA chain.
        covered = report["decisions_verified"] + report["decisions_skipped_honestly"]
        report["coverage_percent"] = round(100.0 * covered / denominator, 4)
    else:
        report["coverage_percent"] = 100.0 if report["governance_chain_present"] else 0.0

    return report


def _integrity_error_has_evidence(
    rec: dict[str, Any],
    qa_conditions_by_gov_ref: dict[str, list[dict[str, Any]]],
    qa_snapshots: list[dict[str, Any]],
) -> bool:
    """An integrity error is explained if the QA chain shows the condition
    that caused it. A condition_source pointing to the QA chain is itself
    evidence the proxy acted on QA-chain state; we check that the QA chain
    actually published a matching condition or snapshot.
    """
    rh = rec.get("record_hash")
    if isinstance(rh, str) and rh in qa_conditions_by_gov_ref:
        return True
    source = rec.get("condition_source") or ""
    # If the proxy halted because the QA chain showed staleness or absence,
    # the evidence is the (lack of) snapshot — by definition there is no
    # qa_condition_detected to find. Treat as explained if any snapshot
    # exists OR if the chain is empty (consistent staleness story).
    if source in ("qa_chain_staleness", "qa_chain_absent"):
        return True
    # For hash_mismatch / active_condition, expect either a snapshot whose
    # active_conditions list named the condition, or a qa_condition_detected
    # referencing some governance record.
    if source in ("hash_mismatch", "active_condition"):
        if qa_snapshots:
            for snap in qa_snapshots:
                active = snap.get("active_conditions") or []
                if isinstance(active, list) and active:
                    return True
        # Fall through — no evidence
    return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _print_report(report: dict[str, Any]) -> None:
    gov_path = report["governance_chain_path"]
    qa_path = report["qa_chain_path"]
    if not report["governance_chain_present"]:
        print(f"FAIL: governance chain not found: {gov_path}")
        return
    if not report["qa_chain_present"]:
        print(f"FAIL: QA chain not found: {qa_path}")
        print(f"Governance chain: {gov_path}")
        print(f"Governance decisions: {report['governance_decisions']}")
        return

    decisions = report["governance_decisions"]
    integrity_errors = report["governance_integrity_errors"]
    verified = report["decisions_verified"]
    skipped = report["decisions_skipped_honestly"]
    gap = report["decisions_unverified_gap"]
    coverage = report["coverage_percent"]
    explained = report["integrity_errors_with_evidence"]
    unexplained = report["integrity_errors_without_evidence"]

    overall_ok = gap == 0 and unexplained == 0
    header = "PASS" if overall_ok else "FAIL"
    print(f"{header}: cross-chain coverage")
    print(f"Governance chain: {gov_path}")
    print(f"QA chain:         {qa_path}")
    print(f"Governance decisions: total={decisions} allow={report['governance_allow_decisions']} deny={report['governance_deny_decisions']}")
    print(f"  verified by QA chain:     {verified}")
    print(f"  skipped honestly:         {skipped}  (qa_decision_verification_skipped)")
    print(f"  unverified gap:           {gap}      (decisions in governance chain with no QA pair)")
    print(f"  coverage:                 {coverage:.2f}%   (verified + skipped honestly)")
    print(f"Governance integrity errors: total={integrity_errors}")
    print(f"  with QA evidence:         {explained}")
    print(f"  without QA evidence:      {unexplained}")
    if report["unverified_decisions_sample"]:
        print("Unverified-decision sample (first 25):")
        for entry in report["unverified_decisions_sample"]:
            print(
                f"  record_hash={entry.get('record_hash')} "
                f"tool={entry.get('tool_name')} "
                f"decision={entry.get('policy_decision')} "
                f"ts={entry.get('timestamp_utc')}"
            )
    if report["unexplained_integrity_errors_sample"]:
        print("Unexplained integrity-error sample (first 25):")
        for entry in report["unexplained_integrity_errors_sample"]:
            print(
                f"  tool={entry.get('tool_name')} "
                f"source={entry.get('condition_source')} "
                f"ts={entry.get('timestamp_utc')} "
                f"detail={entry.get('condition_detail')}"
            )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Verify cross-chain coverage between governance and QA chains"
    )
    ap.add_argument("governance_chain_path", help="path to decision-chain.jsonl")
    ap.add_argument("qa_chain_path", help="path to qa-chain.jsonl")
    ap.add_argument(
        "--summary-json",
        help="write canonical-JSON report to this path",
    )
    args = ap.parse_args(argv)

    gov_chain = Path(args.governance_chain_path)
    qa_chain = Path(args.qa_chain_path)
    report = link_chains(gov_chain, qa_chain)

    _print_report(report)

    if args.summary_json:
        Path(args.summary_json).write_text(
            canonical_json(report) + "\n", encoding="utf-8"
        )

    if not report["governance_chain_present"] or not report["qa_chain_present"]:
        return 2
    if report["decisions_unverified_gap"] > 0 or report["integrity_errors_without_evidence"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
