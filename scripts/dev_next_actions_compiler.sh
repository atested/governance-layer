#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: dev_next_actions_compiler.sh [--status-file PATH] [--catalog-file PATH] [--deps-file PATH] [--edges-file PATH] [--out-file PATH]

Compiles next actions from progress status + catalog + dependency queue.
USAGE
}

status_file="out/progress_status/latest/status.v1.json"
catalog_file="system/planning/verification_catalog.v1.json"
deps_file="out/progress_spine_proposal/DEPENDENCY_QUEUE.md"
edges_file="system/planning/dependency_edges.v1.json"
out_file="out/next_actions/latest/next_actions.v1.json"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --status-file)
      status_file="$2"; shift 2 ;;
    --catalog-file)
      catalog_file="$2"; shift 2 ;;
    --deps-file)
      deps_file="$2"; shift 2 ;;
    --edges-file)
      edges_file="$2"; shift 2 ;;
    --out-file)
      out_file="$2"; shift 2 ;;
    -h|--help)
      usage
      exit 0 ;;
    *)
      usage
      exit 1 ;;
  esac
done

python3 - "$status_file" "$catalog_file" "$deps_file" "$edges_file" "$out_file" <<'PY'
import json
import re
import sys
from pathlib import Path

status_path = Path(sys.argv[1])
catalog_path = Path(sys.argv[2])
deps_path = Path(sys.argv[3])
edges_path = Path(sys.argv[4])
out_path = Path(sys.argv[5])

for p in (status_path, catalog_path, deps_path):
    if not p.exists():
        print("NEXT_ACTIONS_ERROR=MISSING_INPUT")
        sys.exit(1)

status_data = json.loads(status_path.read_text(encoding="utf-8"))
catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
deps_text = deps_path.read_text(encoding="utf-8")

catalog_entries = catalog_data.get("entries", [])
catalog_by_id = {}
for e in catalog_entries:
    if isinstance(e, dict) and e.get("id"):
        catalog_by_id[e["id"]] = e

obj_order = []
for m in re.finditer(r"\b(Obj[0-9]+)\b", deps_text, flags=re.IGNORECASE):
    token = m.group(1).upper()
    if token not in obj_order:
        obj_order.append(token)
if "deliverable" in deps_text.lower() and "REGRESSION" not in obj_order:
    obj_order.append("REGRESSION")

blocked_map = {}
for item in status_data.get("blocked_by_dependencies", []):
    if isinstance(item, dict):
        vid = item.get("id")
        dep = item.get("dependency_token") or item.get("token")
        if isinstance(vid, str) and isinstance(dep, str):
            blocked_map[vid] = dep

edges_map = {}
if edges_path.exists():
    edges_data = json.loads(edges_path.read_text(encoding="utf-8"))
    for item in edges_data.get("edges", []):
        if isinstance(item, dict):
            vid = item.get("id")
            deps = item.get("depends_on", [])
            if isinstance(vid, str) and isinstance(deps, list):
                edges_map[vid] = sorted([d for d in deps if isinstance(d, str) and d])

open_raw = status_data.get("open_verifications", [])
normalized = []
for item in open_raw:
    if isinstance(item, str):
        vid = item
        st = "SKIP"
    elif isinstance(item, dict):
        vid = item.get("id", "")
        st = str(item.get("status", "SKIP")).upper()
    else:
        continue

    if not vid:
        continue
    status = "FAIL" if st == "FAIL" else "SKIP"

    cat = catalog_by_id.get(vid, {})
    cmd = ""
    for k in ("verification_cmd", "cmd_ref", "cmd"):
        v = cat.get(k)
        if isinstance(v, str) and v.strip():
            cmd = v.strip()
            break

    reason = "UNKNOWN"
    action = "DEFINE"
    depends_on = []
    depth = 0

    if status == "FAIL":
        reason = "FAILED_CHECK"
        action = "FIX"
    elif status == "SKIP":
        if not cmd:
            reason = "MISSING_VERIFICATION"
            action = "DEFINE"
        else:
            reason = "SKIPPED_REQUIREMENT"
            action = "RUN"

    dep_token = blocked_map.get(vid, "")
    dep_token_upper = dep_token.upper() if dep_token else ""
    dep_token_key = dep_token_upper[:-4] if dep_token_upper.endswith("_DEP") else dep_token_upper

    if vid in edges_map:
        depends_on = edges_map.get(vid, [])

    if not depends_on and dep_token and dep_token_key in obj_order:
        matches = [
            eid for eid, ent in catalog_by_id.items()
            if isinstance(ent.get("objective"), str)
            and ent.get("objective", "").upper() in {dep_token_upper, dep_token_key}
            and eid != vid
        ]
        if matches:
            depends_on = sorted(matches)

    if vid in blocked_map:
        if depends_on:
            reason = "DEP_BLOCKED"
            action = "UNBLOCK"
            depth = 1
        else:
            reason = "MISSING_DEPENDENCY_EDGE"
            action = "DEFINE"
            depth = 0

    normalized.append({
        "id": vid,
        "status": status,
        "action": action,
        "reason_token": reason,
        "depends_on": depends_on,
        "cmd": cmd,
        "_depth": depth,
    })

status_rank = {"FAIL": 0, "SKIP": 1}
normalized.sort(key=lambda x: (status_rank.get(x["status"], 9), x["_depth"], x["id"]))

open_items = []
for row in normalized:
    open_items.append({
        "id": row["id"],
        "status": row["status"],
        "action": row["action"],
        "reason_token": row["reason_token"],
        "depends_on": row["depends_on"],
        "cmd": row["cmd"],
    })

result = {
    "version": "next_actions_v1",
    "open": open_items,
}

out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result, separators=(",", ":"), ensure_ascii=True))
PY
