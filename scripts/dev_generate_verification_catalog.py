#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "entry"


def canonical_id(canonical: str) -> str:
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    return f"VCAT_{slugify(canonical)}_{digest}"


def classify_objective(path: str) -> str:
    p = path.lower()
    if "phase2" in p or "aat" in p:
        return "PHASE2"
    if "no_" in p or "hygiene" in p or "strict_mode" in p or "conflict" in p:
        return "HYGIENE"
    return "GENERAL"


def command_for(path: str) -> str:
    if path.endswith(".sh"):
        return f"bash {path}"
    if path.endswith(".py"):
        return f"python3 {path}"
    return path


def title_for(path: str) -> str:
    name = Path(path).name
    name = re.sub(r"\.(sh|py)$", "", name)
    return name.replace("_", " ")


def parse_markdown(md_text: str):
    blocks = []
    in_code = False
    current = []
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            if in_code:
                blocks.append(current)
                current = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            current.append(line.strip())

    paths = set()
    for block in blocks:
        for line in block:
            if not line:
                continue
            if line.startswith("system/tests/") or line.startswith("scripts/"):
                paths.add(line)

    supplemental_paths = [
        "system/tests/test_mcp_capabilities_execute_fs_move.sh",
        "system/tests/test_mcp_capabilities_execute_blocked.sh",
        "system/tests/test_mcp_capabilities_execute_delete_exec.sh",
        "system/tests/test_mcp_capabilities_execute_fs_copy.sh",
        "system/tests/test_mcp_capabilities_execute_delete_nonexec.sh",
        "system/tests/test_mcp_receipt_store_index.sh",
        "system/tests/test_mcp_receipt_and_list_recent.sh",
        "system/tests/test_mcp_replay_check.sh",
        "system/tests/test_mcp_replay_check_emits_artifact.sh",
        "system/tests/test_export_receipt_bundle_includes_replay_check.sh",
        "system/tests/test_verify_receipt_bundle_replay_check_artifact.sh",
        "system/tests/test_mcp_admissibility_policy_context_drift.sh",
        "system/tests/test_mcp_replay_check_policy_context_drift.sh",
        "system/tests/test_mcp_receipt_signature_primitives.sh",
        "system/tests/test_mcp_receipt_signature_verification.sh",
        "system/tests/test_export_receipt_attestation_bundle.sh",
        "system/tests/test_verify_receipt_attestation_bundle.sh",
        "system/tests/test_mcp_export_receipt_attestation.sh",
        "system/tests/test_export_receipt_bundle_signature_parity.sh",
        "system/tests/test_verify_receipt_bundle_require_signature.sh",
        "system/tests/test_mcp_attested_execute_fs_move.sh",
        "system/tests/test_mcp_attested_execute_fail_closed.sh",
        "system/tests/test_mcp_attested_execute_includes_replay_artifact.sh",
        "system/tests/test_mcp_attested_execute_replay_context_unknown.sh",
        "system/tests/test_mcp_reference_workflow_e2e.sh",
        "system/tests/test_mcp_noop_echo_capability.sh",
        "system/tests/test_mcp_ingest_artifact_attested_small_payload.sh",
        "system/tests/test_mcp_ingest_artifact_rejects_large_payload.sh",
        "system/tests/test_mcp_ingest_tool_event_attested_ok.sh",
        "system/tests/test_mcp_ingest_tool_event_rejects_invalid.sh",
        "system/tests/test_mcp_tool_catalog_register_and_get.sh",
        "system/tests/test_mcp_tool_catalog_list_recent.sh",
        "system/tests/test_export_tool_catalog_bundle.sh",
        "system/tests/test_verify_tool_catalog_bundle.sh",
        "system/tests/test_mcp_tool_catalog_export_bundle.sh",
        "system/tests/test_mcp_tool_catalog_verify_bundle.sh",
    ]
    for path in supplemental_paths:
        if Path(path).is_file():
            paths.add(path)

    entries = []
    for path in sorted(paths):
        cmd = command_for(path)
        objective = classify_objective(path)
        title = title_for(path)
        canonical = f"{path}|{cmd}|{objective}"
        entries.append(
            {
                "id": canonical_id(canonical),
                "title": title,
                "objective": objective,
                "verification_cmd": cmd,
                "description": f"Catalog entry derived from {path}",
                "source_path": path,
            }
        )

    # Compatibility surfaces that must remain present even when not listed
    # in the snapshot markdown code blocks.
    compatibility_cmds = [
        "bash system/tests/test_phase2_obj2_registry_source_parity.sh",
        "bash system/tests/test_phase2_obj3_reason_precedence_dedup.sh",
        "bash system/tests/test_phase2_one_command_regression.sh",
        "bash system/tests/test_phase2_merge_prep_queue_helper.sh",
        "bash system/tests/test_progress_map_canon_generation.sh",
        "bash system/tests/test_verify_attestation_bundle_signature_mode.sh",
        "bash system/tests/test_attestation_sign_verify_e2e.sh",
        "bash system/tests/test_ed25519_attestation_primitives.sh",
        "bash system/tests/test_phase2_report_includes_p3_signature_row.sh",
        "bash system/tests/test_phase2_report_status_invariants.sh",
    ]
    existing_cmds = {e["verification_cmd"] for e in entries}
    for cmd in compatibility_cmds:
        if cmd in existing_cmds:
            continue
        parts = cmd.split(" ", 1)
        path = parts[1] if len(parts) == 2 else cmd
        objective = classify_objective(path)
        canonical = f"{path}|{cmd}|{objective}"
        entries.append(
            {
                "id": canonical_id(canonical),
                "title": title_for(path),
                "objective": objective,
                "verification_cmd": cmd,
                "description": f"Catalog compatibility entry derived from {Path(path).name}",
                "source_path": path,
            }
        )
    entries.sort(key=lambda x: x["id"])
    return entries


def add_compatibility_entries(entries):
    known = {e.get("verification_cmd", "") for e in entries}
    cmds = [
        "bash system/tests/test_p4_fs_delete_nonexec_admissibility.sh",
        "bash system/tests/test_p4_fs_copy_admissibility.sh",
        "bash system/tests/test_p4_fs_move_dir_semantics.sh",
    ]
    for cmd in cmds:
        if cmd in known:
            continue
        source = cmd.split(" ", 1)[1]
        objective = classify_objective(source)
        canonical = f"{source}|{cmd}|{objective}"
        entries.append(
            {
                "id": canonical_id(canonical),
                "title": f"Verify: {Path(source).name}",
                "objective": objective,
                "verification_cmd": cmd,
                "description": f"Compatibility entry for {source}",
                "source_path": source,
            }
        )
    entries.sort(key=lambda x: x["id"])
    return entries


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate deterministic machine verification catalog")
    ap.add_argument(
        "--input",
        default="out/progress_spine_proposal/VERIFICATION_CATALOG.md",
        help="Source markdown catalog",
    )
    ap.add_argument(
        "--output",
        default="system/planning/verification_catalog.v1.json",
        help="Output JSON path",
    )
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(f"FAIL: missing input catalog: {args.input}")
        return 2

    entries = parse_markdown(src.read_text(encoding="utf-8"))
    entries = add_compatibility_entries(entries)
    if not entries:
        print("FAIL: ambiguous or empty catalog parse")
        return 2

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "catalog_version": "verification_catalog_v1",
        "source": str(src).replace("\\", "/"),
        "entry_count": len(entries),
        "entries": entries,
    }
    out.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"CATALOG_ENTRIES={len(entries)}")
    print(f"CATALOG_OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
