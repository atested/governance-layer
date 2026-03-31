#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from coverage_stamp import validate_coverage_stamp

GENESIS_SENTINEL = "sha256:" + ("0" * 64)
CANONICAL_KEYS = [
    "append_seq",
    "capability_surfaces",
    "decision_record_ref",
    "input_artifact_refs",
    "operation_id",
    "prev_entry_hash",
    "proof_bundle_ref",
    "rules_ref",
]
NON_ADMISSIBLE_CODES = {
    "HASH_NOT_FOUND",
    "ARTIFACT_HASH_MISMATCH",
    "RULES_HASH_MISMATCH",
    "STAMP_MISSING",
    "STAMP_MISMATCH",
    "SILENT_SURFACES",
}
HARD_STOP_CODES = {
    "APPEND_FAILURE",
    "SCHEMA_INVALID",
    "CHAIN_BREAK",
    "ENTRY_HASH_MISMATCH",
    "APPEND_SEQ_BREAK",
    "SERIALIZATION_FAILURE",
}


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def hash_prefixed_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def hash_canonical_json_obj(obj: Any) -> str:
    return hash_prefixed_bytes(canonical_json(obj).encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalogs(repo_root: Path) -> tuple[dict[str, Any], set[str]]:
    typed = load_json(repo_root / "system/schemas/typed_ref_catalog.json")
    surfaces_doc = load_json(repo_root / "system/schemas/foundation_v0_surface_catalog.json")
    if not isinstance(typed, dict) or "types" not in typed or not isinstance(typed["types"], dict):
        raise ValueError("SCHEMA_INVALID: typed_ref_catalog.json invalid")
    if not isinstance(surfaces_doc, dict) or not isinstance(surfaces_doc.get("surfaces"), list):
        raise ValueError("SCHEMA_INVALID: foundation_v0_surface_catalog.json invalid")
    return typed["types"], set(surfaces_doc["surfaces"])


def validate_hash_marker(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.startswith("sha256:"):
        raise ValueError(f"SCHEMA_INVALID: {field_name} must be sha256 marker")
    h = value[len("sha256:") :]
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise ValueError(f"SCHEMA_INVALID: {field_name} invalid hash")


def ref_hash_for_type(ref_type: str, payload_bytes: bytes, payload_json: Any | None) -> str:
    if ref_type == "input_file":
        return hash_prefixed_bytes(payload_bytes)
    if ref_type in {"decision_record", "proof_bundle", "rules_version"}:
        if payload_json is None:
            raise ValueError("SCHEMA_INVALID: typed ref expects JSON payload")
        return hash_canonical_json_obj(payload_json)
    raise ValueError(f"SCHEMA_INVALID: unsupported typed ref type: {ref_type}")


def compute_entry_hash(canonical_domain: dict[str, Any]) -> str:
    for key in CANONICAL_KEYS:
        if key not in canonical_domain:
            raise ValueError(f"SCHEMA_INVALID: missing canonical key {key}")
    canonical_obj = {
        "append_seq": canonical_domain["append_seq"],
        "capability_surfaces": sorted(canonical_domain["capability_surfaces"]),
        "decision_record_ref": canonical_domain["decision_record_ref"],
        "input_artifact_refs": sorted(
            canonical_domain["input_artifact_refs"],
            key=lambda x: (x["type"], x["hash"]),
        ),
        "operation_id": canonical_domain["operation_id"],
        "prev_entry_hash": canonical_domain["prev_entry_hash"],
        "proof_bundle_ref": canonical_domain["proof_bundle_ref"],
        "rules_ref": canonical_domain["rules_ref"],
    }
    j1 = canonical_json(canonical_obj)
    j2 = canonical_json(canonical_obj)
    if j1 != j2:
        raise ValueError("SERIALIZATION_FAILURE: canonical serialization nondeterministic")
    return hash_prefixed_bytes(j1.encode("utf-8"))


def parse_ledger(ledger_path: Path) -> list[dict[str, Any]]:
    if not ledger_path.exists():
        return []
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    out = []
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            raise ValueError(f"SCHEMA_INVALID: malformed ledger line {i}: {e}")
    return out


def append_entry(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    typed_catalog, surface_catalog = load_catalogs(repo_root)

    decision_path = Path(args.decision_record)
    proof_manifest_path = Path(args.proof_bundle_manifest)
    rules_path = Path(args.rules_snapshot)
    input_paths = [Path(p) for p in args.input_file]

    decision_json = load_json(decision_path)
    proof_manifest_json = load_json(proof_manifest_path)
    rules_json = load_json(rules_path)

    coverage_ref = proof_manifest_json.get("coverage_stamp_ref")
    if coverage_ref is None:
        raise ValueError("SCHEMA_INVALID: coverage_stamp_ref missing from proof bundle manifest")
    validate_hash_marker(coverage_ref, "coverage_stamp_ref")

    surfaces = sorted(set(args.capability_surface))
    if not surfaces:
        raise ValueError("SCHEMA_INVALID: capability_surfaces must not be empty")
    unknown_surfaces = sorted(set(surfaces) - surface_catalog)
    if unknown_surfaces:
        raise ValueError(f"SCHEMA_INVALID: unknown capability surface {unknown_surfaces[0]}")

    decision_ref = {
        "type": "decision_record",
        "hash": ref_hash_for_type("decision_record", decision_path.read_bytes(), decision_json),
    }
    proof_ref = {
        "type": "proof_bundle",
        "hash": ref_hash_for_type("proof_bundle", proof_manifest_path.read_bytes(), proof_manifest_json),
    }
    rules_ref = {
        "type": "rules_version",
        "hash": ref_hash_for_type("rules_version", rules_path.read_bytes(), rules_json),
    }
    input_refs = []
    for p in input_paths:
        input_refs.append({"type": "input_file", "hash": ref_hash_for_type("input_file", p.read_bytes(), None)})

    for ref in [decision_ref, proof_ref, rules_ref] + input_refs:
        if ref["type"] not in typed_catalog:
            raise ValueError(f"SCHEMA_INVALID: unknown typed reference type {ref['type']}")
        validate_hash_marker(ref["hash"], f"typed_ref:{ref['type']}")

    ledger_path = Path(args.ledger)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    entries = parse_ledger(ledger_path)
    if not entries:
        append_seq = 1
        prev_hash = GENESIS_SENTINEL
    else:
        append_seq = int(entries[-1]["append_seq"]) + 1
        prev_hash = entries[-1]["entry_hash"]

    canonical_domain = {
        "append_seq": append_seq,
        "capability_surfaces": surfaces,
        "decision_record_ref": decision_ref,
        "input_artifact_refs": input_refs,
        "operation_id": args.operation_id,
        "prev_entry_hash": prev_hash,
        "proof_bundle_ref": proof_ref,
        "rules_ref": rules_ref,
    }
    entry_hash = compute_entry_hash(canonical_domain)

    line_obj = dict(canonical_domain)
    line_obj["entry_hash"] = entry_hash
    if args.wall_clock_ts:
        line_obj["wall_clock_ts"] = args.wall_clock_ts
    if args.host_id:
        line_obj["host_id"] = args.host_id
    line_obj["admissibility_status"] = "ADMISSIBLE"
    line_obj["failure_codes"] = []

    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line_obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")

    print(f"APPEND_OK append_seq={append_seq} entry_hash={entry_hash}")
    return 0


def resolve_local_by_hash(artifact_dirs: list[Path], ref_type: str, expected_hash: str) -> tuple[Path | None, str | None]:
    for d in artifact_dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if not p.is_file():
                continue
            raw = p.read_bytes()
            payload_json = None
            if ref_type in {"decision_record", "proof_bundle", "rules_version"}:
                try:
                    payload_json = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue
            actual = ref_hash_for_type(ref_type, raw, payload_json)
            if actual == expected_hash:
                return p, actual
    return None, None


def verify(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    typed_catalog, surface_catalog = load_catalogs(repo_root)
    ledger_path = Path(args.ledger)
    entries = parse_ledger(ledger_path)
    artifact_dirs = [Path(p) for p in args.artifact_dir]

    report = {"ledger": str(ledger_path), "entries": [], "overall_status": "ADMISSIBLE", "hard_stop": None}

    prev_hash = GENESIS_SENTINEL
    expected_seq = 1
    updated_entries: list[dict[str, Any]] = []

    for entry in entries:
        try:
            canonical_domain = {k: entry[k] for k in CANONICAL_KEYS}
            for s in canonical_domain["capability_surfaces"]:
                if s not in surface_catalog:
                    raise ValueError("SCHEMA_INVALID")
            for ref_key in ["decision_record_ref", "proof_bundle_ref", "rules_ref"]:
                ref = canonical_domain[ref_key]
                if ref["type"] not in typed_catalog:
                    raise ValueError("SCHEMA_INVALID")
                validate_hash_marker(ref["hash"], ref_key)
            for ref in canonical_domain["input_artifact_refs"]:
                if ref["type"] not in typed_catalog:
                    raise ValueError("SCHEMA_INVALID")
                validate_hash_marker(ref["hash"], "input_artifact_ref")

            computed = compute_entry_hash(canonical_domain)
            if computed != entry.get("entry_hash"):
                report["hard_stop"] = "ENTRY_HASH_MISMATCH"
                report["overall_status"] = "STOP"
                print("ENTRY_HASH_MISMATCH")
                return 2
            if canonical_domain["prev_entry_hash"] != prev_hash:
                report["hard_stop"] = "CHAIN_BREAK"
                report["overall_status"] = "STOP"
                print("CHAIN_BREAK")
                return 2
            if canonical_domain["append_seq"] != expected_seq:
                report["hard_stop"] = "APPEND_SEQ_BREAK"
                report["overall_status"] = "STOP"
                print("APPEND_SEQ_BREAK")
                return 2

            failure_codes: list[str] = []

            all_refs = [
                canonical_domain["decision_record_ref"],
                canonical_domain["proof_bundle_ref"],
                canonical_domain["rules_ref"],
                *canonical_domain["input_artifact_refs"],
            ]
            resolved_proof_manifest = None
            for ref in all_refs:
                p, actual = resolve_local_by_hash(artifact_dirs, ref["type"], ref["hash"])
                if p is None:
                    failure_codes.append("HASH_NOT_FOUND")
                    continue
                if actual != ref["hash"]:
                    failure_codes.append("ARTIFACT_HASH_MISMATCH")
                if ref["type"] == "rules_version" and actual != ref["hash"]:
                    failure_codes.append("RULES_HASH_MISMATCH")
                if ref["type"] == "proof_bundle":
                    resolved_proof_manifest = json.loads(p.read_text(encoding="utf-8"))

            if resolved_proof_manifest is None:
                failure_codes.append("STAMP_MISSING")
            else:
                stamp_hash = resolved_proof_manifest.get("coverage_stamp_ref")
                if stamp_hash is None:
                    failure_codes.append("STAMP_MISSING")
                else:
                    validate_hash_marker(stamp_hash, "coverage_stamp_ref")
                    stamp_path, _ = resolve_local_by_hash(artifact_dirs, "proof_bundle", stamp_hash)
                    if stamp_path is None:
                        failure_codes.append("STAMP_MISMATCH")
                    else:
                        try:
                            stamp_obj = json.loads(stamp_path.read_text(encoding="utf-8"))
                        except Exception:
                            failure_codes.append("STAMP_MISMATCH")
                        else:
                            val = validate_coverage_stamp(stamp_obj, required=True)
                            if not val.ok or val.normalized is None:
                                failure_codes.append("STAMP_MISMATCH")
                            else:
                                if hash_canonical_json_obj(val.normalized) != stamp_hash:
                                    failure_codes.append("STAMP_MISMATCH")
                                else:
                                    stamp_surfaces = {s["surface_id"] for s in val.normalized["surfaces"]}
                                    ledger_surfaces = set(canonical_domain["capability_surfaces"])
                                    if not ledger_surfaces.issubset(stamp_surfaces):
                                        failure_codes.append("SILENT_SURFACES")

            failure_codes = sorted(set(failure_codes))
            admissibility = "NON_ADMISSIBLE" if failure_codes else "ADMISSIBLE"
            if admissibility == "NON_ADMISSIBLE":
                report["overall_status"] = "NON_ADMISSIBLE"
            report["entries"].append(
                {
                    "append_seq": canonical_domain["append_seq"],
                    "operation_id": canonical_domain["operation_id"],
                    "admissibility_status": admissibility,
                    "failure_codes": failure_codes,
                }
            )

            mutable = dict(entry)
            mutable["admissibility_status"] = admissibility
            mutable["failure_codes"] = failure_codes
            updated_entries.append(mutable)

            prev_hash = entry["entry_hash"]
            expected_seq += 1
        except ValueError as e:
            print(str(e))
            return 2

    if args.report_out:
        out = Path(args.report_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")

    if args.write_ledger_metadata:
        ledger_path.write_text(
            "".join(json.dumps(e, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n" for e in updated_entries),
            encoding="utf-8",
        )

    print(f"VERIFY_STATUS={report['overall_status']}")
    if report["overall_status"] == "NON_ADMISSIBLE":
        print("NON_ADMISSIBLE_RECORDED=yes")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Foundation v0 process ledger")
    sub = p.add_subparsers(dest="cmd", required=True)

    ap = sub.add_parser("append", help="append ledger entry")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--operation-id", required=True)
    ap.add_argument("--capability-surface", action="append", required=True)
    ap.add_argument("--decision-record", required=True)
    ap.add_argument("--proof-bundle-manifest", required=True)
    ap.add_argument("--rules-snapshot", required=True)
    ap.add_argument("--input-file", action="append", required=True)
    ap.add_argument("--wall-clock-ts")
    ap.add_argument("--host-id")

    vp = sub.add_parser("verify", help="verify ledger")
    vp.add_argument("--ledger", required=True)
    vp.add_argument("--artifact-dir", action="append", required=True)
    vp.add_argument("--report-out")
    vp.add_argument("--write-ledger-metadata", action="store_true")

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "append":
        return append_entry(args)
    if args.cmd == "verify":
        return verify(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
