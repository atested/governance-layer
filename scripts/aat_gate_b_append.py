#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER_CLI = ROOT / "scripts" / "foundation_v0_process_ledger.py"
DEFAULT_TYPED_REF_CATALOG = ROOT / "system" / "schemas" / "typed_ref_catalog.json"
DEFAULT_SURFACE_CATALOG = ROOT / "system" / "schemas" / "foundation_v0_surface_catalog.json"

DECISION_PASS = "PASS"
DECISION_NON_ADMISSIBLE = "FAIL_NON_ADMISSIBLE"
DECISION_HARD_STOP = "FAIL_HARD_STOP"

APPEND_RE = re.compile(r"append_seq=([0-9]+)\s+entry_hash=(sha256:[0-9a-f]{64})")


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def emit(admissible: str, stop_required: str, reason: str, rc: int, details: dict[str, str] | None = None) -> int:
    print(f"ADMISSIBLE={admissible}")
    print(f"STOP_REQUIRED={stop_required}")
    print(f"REASON_CODE={reason}")
    if details:
        for key in sorted(details):
            print(f"{key}={details[key]}")
    return rc


def ensure_catalogs(typed_ref_catalog: Path, surface_catalog: Path) -> tuple[set[str], set[str]]:
    typed = load_json(typed_ref_catalog)
    surfaces = load_json(surface_catalog)

    type_map = typed.get("types", {}) if isinstance(typed, dict) else {}
    if not isinstance(type_map, dict):
        raise ValueError("AAT_GATE_B_TYPED_REF_CATALOG_INVALID")

    required_types = {
        "decision_record",
        "proof_bundle",
        "rules_version",
        "input_file",
        "action_decision_record",
    }
    missing_types = sorted(required_types - set(type_map.keys()))
    if missing_types:
        raise ValueError(f"AAT_GATE_B_TYPED_REF_TYPE_MISSING:{missing_types[0]}")

    surface_list = surfaces.get("surfaces", []) if isinstance(surfaces, dict) else []
    if not isinstance(surface_list, list):
        raise ValueError("AAT_GATE_B_SURFACE_CATALOG_INVALID")

    return set(type_map.keys()), set(surface_list)


def map_action_kind_to_surfaces(action_kind: str) -> list[str]:
    mapping = {
        "CORE_GENERIC": ["toolchain"],
        "TOOL_EXEC": ["shell"],
    }
    return mapping.get(action_kind, ["toolchain"])


def derive_surfaces(action_record: dict[str, Any], allowed_surfaces: set[str], explicit: list[str]) -> list[str]:
    vals: list[str] = []
    if explicit:
        vals.extend(explicit)
    elif isinstance(action_record.get("capability_surfaces"), list):
        vals.extend([str(x) for x in action_record["capability_surfaces"]])
    elif isinstance(action_record.get("capability_surface"), str):
        vals.append(action_record["capability_surface"])
    else:
        vals.extend(map_action_kind_to_surfaces(str(action_record.get("action_kind", "CORE_GENERIC"))))

    norm = sorted(set(vals))
    for s in norm:
        if s not in allowed_surfaces:
            raise ValueError(f"AAT_GATE_B_SURFACE_UNKNOWN:{s}")
    return norm


def parse_append_output(output: str) -> tuple[str, str]:
    m = APPEND_RE.search(output)
    if not m:
        raise ValueError("AAT_GATE_B_APPEND_OUTPUT_INVALID")
    return m.group(1), m.group(2)


def run_append(
    ledger: Path,
    operation_id: str,
    surfaces: list[str],
    decision_record: Path,
    proof_manifest: Path,
    rules_snapshot: Path,
    input_file: Path,
) -> tuple[str, str]:
    cmd = [
        sys.executable,
        str(LEDGER_CLI),
        "append",
        "--ledger",
        str(ledger),
        "--operation-id",
        operation_id,
    ]
    for s in surfaces:
        cmd += ["--capability-surface", s]
    cmd += [
        "--decision-record",
        str(decision_record),
        "--proof-bundle-manifest",
        str(proof_manifest),
        "--rules-snapshot",
        str(rules_snapshot),
        "--input-file",
        str(input_file),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout + proc.stderr)
    return parse_append_output(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(description="AAT Gate B append adapter")
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--aat-action-record", required=True)
    parser.add_argument("--decision-record", required=True)
    parser.add_argument("--proof-bundle-manifest", required=True)
    parser.add_argument("--rules-snapshot", required=True)
    parser.add_argument("--operation-id", default="aat-gate-b-op")
    parser.add_argument("--capability-surface", action="append", default=[])
    parser.add_argument("--typed-ref-catalog", default=str(DEFAULT_TYPED_REF_CATALOG))
    parser.add_argument("--surface-catalog", default=str(DEFAULT_SURFACE_CATALOG))
    args = parser.parse_args()

    ledger = Path(args.ledger)
    action_record_path = Path(args.aat_action_record)
    decision_record_path = Path(args.decision_record)
    proof_manifest_path = Path(args.proof_bundle_manifest)
    rules_snapshot_path = Path(args.rules_snapshot)
    typed_ref_catalog = Path(args.typed_ref_catalog)
    surface_catalog = Path(args.surface_catalog)

    for p, code in [
        (action_record_path, "AAT_GATE_B_ACTION_RECORD_MISSING"),
        (decision_record_path, "AAT_GATE_B_DECISION_RECORD_MISSING"),
        (proof_manifest_path, "AAT_GATE_B_PROOF_MANIFEST_MISSING"),
        (rules_snapshot_path, "AAT_GATE_B_RULES_SNAPSHOT_MISSING"),
        (typed_ref_catalog, "AAT_GATE_B_TYPED_REF_CATALOG_MISSING"),
        (surface_catalog, "AAT_GATE_B_SURFACE_CATALOG_MISSING"),
    ]:
        if not p.is_file():
            return emit("NO", "YES", code, 2)

    try:
        _, allowed_surfaces = ensure_catalogs(typed_ref_catalog, surface_catalog)
        action_record = load_json(action_record_path)
        decision_record = load_json(decision_record_path)
        decision = str(decision_record.get("decision", "UNKNOWN"))
        reason_codes = decision_record.get("reason_codes", [])
        reason_code = str(reason_codes[0]) if isinstance(reason_codes, list) and reason_codes else "NONE"

        if decision not in {DECISION_PASS, DECISION_NON_ADMISSIBLE, DECISION_HARD_STOP}:
            return emit("NO", "YES", "AAT_GATE_B_DECISION_INVALID", 2)

        surfaces = derive_surfaces(action_record, allowed_surfaces, args.capability_surface)

        action_seq, action_hash = run_append(
            ledger=ledger,
            operation_id=f"{args.operation_id}::action",
            surfaces=surfaces,
            decision_record=decision_record_path,
            proof_manifest=proof_manifest_path,
            rules_snapshot=rules_snapshot_path,
            input_file=action_record_path,
        )

        action_record_hash = sha256_bytes(canonical_json(action_record).encode("utf-8"))
        decision_record_hash = sha256_bytes(canonical_json(decision_record).encode("utf-8"))
        decision_event_obj = {
            "action_record_hash": action_record_hash,
            "decision": decision,
            "decision_record_hash": decision_record_hash,
            "reason_code": reason_code,
            "record_type": "aat_decision_event_v0",
        }

        with tempfile.TemporaryDirectory(prefix="aat_gate_b_") as td:
            decision_event_path = Path(td) / "decision_event_input.json"
            decision_event_path.write_text(canonical_json(decision_event_obj) + "\n", encoding="utf-8")

            decision_seq, decision_hash = run_append(
                ledger=ledger,
                operation_id=f"{args.operation_id}::decision",
                surfaces=surfaces,
                decision_record=decision_record_path,
                proof_manifest=proof_manifest_path,
                rules_snapshot=rules_snapshot_path,
                input_file=decision_event_path,
            )

        details = {
            "ACTION_APPEND_ENTRY_HASH": action_hash,
            "ACTION_APPEND_SEQ": action_seq,
            "DECISION_APPEND_ENTRY_HASH": decision_hash,
            "DECISION_APPEND_SEQ": decision_seq,
            "LEDGER_PATH": str(ledger),
        }

        if decision == DECISION_PASS:
            return emit("YES", "NO", "NONE", 0, details)
        if decision == DECISION_NON_ADMISSIBLE:
            return emit("NO", "NO", reason_code, 1, details)
        return emit("NO", "YES", reason_code, 2, details)
    except ValueError as exc:
        return emit("NO", "YES", str(exc), 2)
    except RuntimeError:
        return emit("NO", "YES", "AAT_GATE_B_APPEND_FAILED", 2)


if __name__ == "__main__":
    raise SystemExit(main())
