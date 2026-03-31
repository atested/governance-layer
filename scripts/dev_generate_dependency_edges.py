#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


def parse_queue_tokens(text: str):
    ordered = []
    for line in text.splitlines():
        s = line.strip().lower()
        if not re.match(r"^\d+\)", s):
            continue
        token = None
        if "obj2" in s:
            token = "OBJ2"
        elif "obj3" in s:
            token = "OBJ3"
        elif "one-command regression" in s or "deliverable" in s and "regression" in s:
            token = "REGRESSION"
        if token and token not in ordered:
            ordered.append(token)
    return ordered


def id_token(idv: str) -> str:
    low = idv.lower()
    if "_obj2_" in low:
        return "OBJ2"
    if "_obj3_" in low:
        return "OBJ3"
    if "_one_command_regression_" in low:
        return "REGRESSION"
    return ""


def map_token_to_ids(tokens, catalog_entries, report_ids):
    catalog_ids = [e.get("id", "") for e in catalog_entries if isinstance(e, dict)]

    def exact_from_catalog(tok):
        matches = [cid for cid in catalog_ids if id_token(cid) == tok]
        return sorted(set(matches))

    def fallback_from_report(tok):
        matches = [rid for rid in report_ids if id_token(rid) == tok]
        return sorted(set(matches))

    token_to_ids = {}
    for tok in tokens:
        matches = exact_from_catalog(tok)
        if len(matches) == 1:
            token_to_ids[tok] = matches
            continue
        if len(matches) == 0:
            fb = fallback_from_report(tok)
            if len(fb) == 1:
                token_to_ids[tok] = fb
                continue
            raise RuntimeError(f"EDGE_MAP_FAIL token={tok} catalog_matches={len(matches)} fallback_matches={len(fb)}")
        raise RuntimeError(f"EDGE_MAP_AMBIGUOUS token={tok} catalog_matches={len(matches)}")
    return token_to_ids


def build_edges(tokens, token_to_ids):
    edges = []
    idx = {tok: i for i, tok in enumerate(tokens)}
    for tok in tokens:
        if tok not in token_to_ids:
            continue
        my_id = token_to_ids[tok][0]
        deps = []
        # Direct predecessor dependency from queue order.
        my_i = idx[tok]
        if my_i > 0:
            prev_tok = tokens[my_i - 1]
            if prev_tok in token_to_ids:
                deps.append(token_to_ids[prev_tok][0])
        edges.append({"id": my_id, "depends_on": sorted(set(deps))})
    edges.sort(key=lambda x: x["id"])
    return edges


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate canonical dependency edges for spine compiler")
    ap.add_argument("--deps", default="out/progress_spine_proposal/DEPENDENCY_QUEUE.md")
    ap.add_argument("--catalog", default="system/planning/verification_catalog.v1.json")
    ap.add_argument("--report", default="out/phase2_reports/latest/report.v1.json")
    ap.add_argument("--output", default="system/planning/dependency_edges.v1.json")
    args = ap.parse_args()

    deps_path = Path(args.deps)
    cat_path = Path(args.catalog)
    report_path = Path(args.report)
    out_path = Path(args.output)

    for p in (deps_path, cat_path, report_path):
        if not p.is_file():
            print(f"FAIL:MISSING_INPUT:{p}")
            return 2

    tokens = parse_queue_tokens(deps_path.read_text(encoding="utf-8"))
    if not tokens:
        print("FAIL:EMPTY_QUEUE_TOKENS")
        return 2

    catalog = json.loads(cat_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report_ids = [r.get("id", "") for r in report.get("results", []) if isinstance(r, dict)]

    try:
        token_to_ids = map_token_to_ids(tokens, catalog.get("entries", []), report_ids)
    except RuntimeError as exc:
        print(f"FAIL:{exc}")
        return 2

    edges = build_edges(tokens, token_to_ids)
    payload = {
        "version": "dependency_edges_v1",
        "edges": edges,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"EDGE_COUNT={len(edges)}")
    print(f"OUTPUT={out_path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
