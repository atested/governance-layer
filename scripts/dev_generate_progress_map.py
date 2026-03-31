#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Dict, List


def stable_id(prefix: str, canonical: str) -> str:
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "_", canonical.lower()).strip("_")
    return f"{prefix}_{slug}_{digest}"


def extract_phase2_rows(progress_map_md: str) -> List[Dict[str, str]]:
    m = re.search(
        r"## Phase 2 deliverables/objectives map \(initial\)\n\n\| Item \|.*?\n\|---\|.*?\n(?P<body>(?:\|.*\n)+)",
        progress_map_md,
        flags=re.MULTILINE,
    )
    if not m:
        raise ValueError("PROGRESS_MAP_PARSE_FAIL=PHASE2_TABLE_MISSING")

    rows = []
    for raw in m.group("body").splitlines():
        if not raw.strip().startswith("|"):
            continue
        parts = [p.strip() for p in raw.strip().strip("|").split("|")]
        if len(parts) < 5:
            continue
        rows.append({
            "title": parts[0],
            "status": parts[4],
        })
    if not rows:
        raise ValueError("PROGRESS_MAP_PARSE_FAIL=PHASE2_ROWS_EMPTY")
    return rows


def extract_phase_objectives(snapshot_md: str, phase_label: str) -> List[str]:
    lines = snapshot_md.splitlines()
    out: List[str] = []
    in_phase = False
    for line in lines:
        if re.search(rf"###\s+{re.escape(phase_label)}\s+objectives", line):
            in_phase = True
            continue
        if in_phase and re.search(r"###\s+Phase\s+\d+\s+objectives", line):
            break
        if in_phase and re.search(r"##\s+Current status", line):
            break
        if in_phase:
            m = re.search(r"\b\d+\.?\s+(.+)$", line)
            if m:
                text = m.group(1).strip()
                if text and not text.lower().startswith("1."):
                    if text not in out:
                        out.append(text)
    return out


def load_catalog_by_cmd(catalog_path: Path) -> Dict[str, str]:
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    out = {}
    for e in data.get("entries", []):
        cmd = e.get("verification_cmd", "")
        eid = e.get("id", "")
        if cmd and eid:
            out[cmd] = eid
    return out


def map_verification_id(title: str, catalog_cmd_to_id: Dict[str, str]) -> str:
    t = title.lower()
    pref = [
        ("obj1", "bash system/tests/test_phase2_merge_prep_queue_helper.sh"),
        ("obj2", "bash system/tests/test_phase2_obj2_registry_source_parity.sh"),
        ("obj3", "bash system/tests/test_phase2_obj3_reason_precedence_dedup.sh"),
        ("one-command regression", "bash system/tests/test_phase2_one_command_regression.sh"),
        ("reference client", "bash system/tests/test_p3_stdio_mcp_reference_client.sh"),
        ("attribution via signatures", "python3 scripts/verify-attestation-bundle.py"),
    ]
    for needle, cmd in pref:
        if needle in t and cmd in catalog_cmd_to_id:
            return catalog_cmd_to_id[cmd]
    return ""


def normalize_status(raw: str) -> str:
    s = raw.lower()
    if "not_evaluated" in s or "not evaluated" in s:
        return "NOT_EVALUATED"
    if "evidence_present" in s or "evidence present" in s:
        return "EVIDENCE_PRESENT"
    if "verified_on_main" in s or "verified on main" in s:
        return "VERIFIED_ON_MAIN"
    if "gap" in s:
        return "GAP"
    return "NOT_EVALUATED"


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate canonical deterministic progress map JSON")
    ap.add_argument("--progress-map-draft", default="out/progress_spine_proposal/PROGRESS_MAP__DRAFT.md")
    ap.add_argument("--completeness-snapshot", default="out/progress_spine_proposal/COMPLETENESS_SNAPSHOT.md")
    ap.add_argument("--catalog", default="system/planning/verification_catalog.v1.json")
    ap.add_argument("--output", default="system/planning/progress_map.v1.json")
    args = ap.parse_args()

    progress_path = Path(args.progress_map_draft)
    snapshot_path = Path(args.completeness_snapshot)
    catalog_path = Path(args.catalog)
    out_path = Path(args.output)

    for p, token in [
        (progress_path, "PROGRESS_MAP_PARSE_FAIL=MISSING_PROGRESS_MAP_DRAFT"),
        (snapshot_path, "PROGRESS_MAP_PARSE_FAIL=MISSING_COMPLETENESS_SNAPSHOT"),
        (catalog_path, "PROGRESS_MAP_PARSE_FAIL=MISSING_CATALOG"),
    ]:
        if not p.is_file():
            print(token)
            return 2

    progress_text = progress_path.read_text(encoding="utf-8")
    snapshot_text = snapshot_path.read_text(encoding="utf-8")

    try:
        phase2 = extract_phase2_rows(progress_text)
    except ValueError as e:
        print(str(e))
        return 2

    phase3 = extract_phase_objectives(snapshot_text, "Phase 3")
    phase4 = extract_phase_objectives(snapshot_text, "Phase 4")
    if not phase3:
        print("PROGRESS_MAP_PARSE_FAIL=PHASE3_OBJECTIVES_MISSING")
        return 2
    if not phase4:
        print("PROGRESS_MAP_PARSE_FAIL=PHASE4_OBJECTIVES_MISSING")
        return 2

    cmd_to_id = load_catalog_by_cmd(catalog_path)

    items = []
    for row in phase2:
        title = row["title"]
        item_id = stable_id("PMAP", f"PHASE2|{title}")
        vid = map_verification_id(title, cmd_to_id)
        items.append(
            {
                "depends_on": [],
                "id": item_id,
                "phase": "PHASE2",
                "status": normalize_status(row["status"]),
                "title": title,
                "verification_id": vid,
            }
        )

    for title in phase3:
        item_id = stable_id("PMAP", f"PHASE3|{title}")
        vid = map_verification_id(title, cmd_to_id)
        items.append(
            {
                "depends_on": [],
                "id": item_id,
                "phase": "PHASE3",
                "status": "NOT_EVALUATED",
                "title": title,
                "verification_id": vid,
            }
        )

    for title in phase4:
        item_id = stable_id("PMAP", f"PHASE4|{title}")
        vid = map_verification_id(title, cmd_to_id)
        items.append(
            {
                "depends_on": [],
                "id": item_id,
                "phase": "PHASE4",
                "status": "NOT_EVALUATED",
                "title": title,
                "verification_id": vid,
            }
        )

    items.sort(key=lambda x: x["id"])

    payload = {
        "items": items,
        "source_digest": "sha256:" + hashlib.sha256((progress_text + "\n" + snapshot_text).encode("utf-8")).hexdigest(),
        "version": "progress_map_v1",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"PROGRESS_MAP_ITEMS={len(items)}")
    print(f"PROGRESS_MAP_OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
