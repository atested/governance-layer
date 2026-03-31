#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: dev_merge_sim_inputs_from_queue.sh [--queue-file PATH] [--evidence-file PATH] [--out-file PATH]

Builds merge simulator branches.txt from queue/evidence markdown/text.
USAGE
}

queue_file="out/keep_busy_portfolio/D_merge_prep_queue.md"
evidence_file="out/keep_busy_portfolio/_merge_prep_evidence.txt"
out_file="out/merge_sim_inputs/latest/branches.txt"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --queue-file)
      queue_file="$2"; shift 2 ;;
    --evidence-file)
      evidence_file="$2"; shift 2 ;;
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

python3 - "$queue_file" "$evidence_file" "$out_file" <<'PY'
import re
import sys
from pathlib import Path

queue_path = Path(sys.argv[1])
evidence_path = Path(sys.argv[2])
out_path = Path(sys.argv[3])

for p in (queue_path, evidence_path):
    if not p.exists():
        print("MERGE_SIM_INPUTS_EMPTY=YES")
        sys.exit(1)

queue_text = queue_path.read_text(encoding="utf-8")
evidence_text = evidence_path.read_text(encoding="utf-8")

ref_re = re.compile(r"\borigin\/(?:codex|cecil)\/[A-Za-z0-9._\/-]+\b")

# Explicit ordered refs from queue file if present on numbered/bulleted lines.
ordered_from_queue = []
explicit_order = False
for line in queue_text.splitlines():
    if re.match(r"^\s*(?:[0-9]+\)|[0-9]+\.|[-*])\s+", line):
        refs = ref_re.findall(line)
        if refs:
            explicit_order = True
            for r in refs:
                if r not in ordered_from_queue:
                    ordered_from_queue.append(r)

all_queue_refs = ref_re.findall(queue_text)
all_evidence_refs = ref_re.findall(evidence_text)

unique_all = sorted(set(all_queue_refs + all_evidence_refs))

if explicit_order:
    tail = sorted([r for r in unique_all if r not in set(ordered_from_queue)])
    final_refs = ordered_from_queue + tail
else:
    final_refs = unique_all

out_path.parent.mkdir(parents=True, exist_ok=True)
if not final_refs:
    token = "MERGE_SIM_INPUTS_EMPTY=YES\n"
    out_path.write_text(token, encoding="utf-8")
    print(token.strip())
    sys.exit(1)

out_path.write_text("\n".join(final_refs) + "\n", encoding="utf-8")
print("\n".join(final_refs))
PY
