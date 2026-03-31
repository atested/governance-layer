#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REQUIRED_FILES = [
    "action_record.json",
    "assumptions_unknowns_register.json",
    "claims_evidence_map.json",
    "constraint_acknowledgment_map.json",
    "constraint_set_digest.json",
    "coverage_stamp.json",
    "decision_record.json",
    "input_manifest.json",
    "method_binding.json",
    "proof_manifest.json",
    "rules.json",
]

PHANTOM_CLAIM_TYPES = {"verification_completed", "test_passed", "test_failed"}


def emit_fail(msg: str, code: int = 1) -> int:
    print("AAT_STAGE=FAIL")
    print("COPIED_FILES=0")
    print("DEST=aat/")
    print(f"REASON={msg}")
    return code


def emit_blocked(token: str, code: int = 2) -> int:
    print(f"AAT_STAGE_BLOCKED={token}")
    return code


def bundle_tool_event_digests(bundle_dir: Path) -> set[str]:
    manifest_path = bundle_dir / "input_manifest.json"
    if not manifest_path.is_file():
        return set()
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    digests: set[str] = set()
    for item in doc.get("inputs", []):
        if isinstance(item, dict) and item.get("ref_type") == "tool_event":
            digest = item.get("digest")
            if isinstance(digest, str) and digest:
                digests.add(digest)
    return digests


def k1_safe_claims(cem_doc: dict, allowed_tool_event_digests: set[str]) -> list[dict]:
    claims = cem_doc.get("claims", [])
    if not isinstance(claims, list):
        return []

    filtered: list[dict] = []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_type = claim.get("claim_type", "")
        if claim_type not in PHANTOM_CLAIM_TYPES:
            filtered.append(claim)
            continue
        refs = claim.get("evidence_refs", [])
        if not isinstance(refs, list):
            continue
        claim_tool_digests = {
            ref.get("digest")
            for ref in refs
            if isinstance(ref, dict) and ref.get("ref_type") == "tool_event" and isinstance(ref.get("digest"), str)
        }
        if claim_tool_digests.intersection(allowed_tool_event_digests):
            filtered.append(claim)
    return filtered


def aligned_input_manifest(src_doc: dict, tool_event_digests: set[str]) -> dict:
    version = src_doc.get("input_manifest_version", "v0")
    if not isinstance(version, str) or not version:
        version = "v0"
    inputs = [{"digest": digest, "ref_type": "tool_event"} for digest in sorted(tool_event_digests)]
    return {"input_manifest_version": version, "inputs": inputs}


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage AAT kernel objects into a proof bundle")
    parser.add_argument("--bundle-dir", required=True)
    parser.add_argument("--aat-dir", required=True)
    args = parser.parse_args()

    bundle_dir = Path(args.bundle_dir)
    aat_dir = Path(args.aat_dir)

    if not bundle_dir.is_dir():
        return emit_fail("BUNDLE_DIR_MISSING")
    if not aat_dir.is_dir():
        return emit_fail("AAT_DIR_MISSING")

    missing = [name for name in REQUIRED_FILES if not (aat_dir / name).is_file()]
    if missing:
        return emit_fail(f"AAT_REQUIRED_MISSING:{missing[0]}")

    tool_event_digests = bundle_tool_event_digests(bundle_dir)
    if not tool_event_digests:
        return emit_blocked("AAT_STAGE_NO_TOOL_EVENTS")

    dest_dir = bundle_dir / "aat"
    dest_dir.mkdir(parents=True, exist_ok=True)

    copied = 0
    for name in sorted(REQUIRED_FILES):
        src = aat_dir / name
        dst = dest_dir / name
        if name == "claims_evidence_map.json":
            try:
                cem_doc = json.loads(src.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return emit_fail("AAT_CEM_JSON_INVALID")
            cem_doc["claims"] = k1_safe_claims(cem_doc, tool_event_digests)
            dst.write_text(json.dumps(cem_doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        elif name == "input_manifest.json":
            try:
                im_doc = json.loads(src.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return emit_fail("AAT_IM_JSON_INVALID")
            aligned = aligned_input_manifest(im_doc if isinstance(im_doc, dict) else {}, tool_event_digests)
            dst.write_text(json.dumps(aligned, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        else:
            shutil.copyfile(src, dst)
        copied += 1

    print("AAT_STAGE=PASS")
    print(f"COPIED_FILES={copied}")
    print("DEST=aat/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
