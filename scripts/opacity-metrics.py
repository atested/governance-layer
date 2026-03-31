#!/usr/bin/env python3
import argparse
import json
from pathlib import Path


OPAQUE_RESOLUTIONS = (
    "approved_lookup",
    "transparent_restatement",
    "operator_intervention",
    "denied",
)


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_chain(path: Path) -> list[dict]:
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def derive_metrics(rows: list[dict]) -> dict:
    transparent_actions = 0
    opaque_encounters = 0
    resolution_distribution = {resolution: 0 for resolution in OPAQUE_RESOLUTIONS}

    for row in rows:
        if row.get("event_type") == "opaque_invocation_decision":
            opaque_encounters += 1
            resolution = str(row.get("resolution", ""))
            if resolution in resolution_distribution:
                resolution_distribution[resolution] += 1
        elif "event_type" not in row:
            transparent_actions += 1

    total_governed_actions = transparent_actions + opaque_encounters
    if total_governed_actions == 0:
        transparent_proportion = 0.0
        opaque_proportion = 0.0
    else:
        transparent_proportion = transparent_actions / total_governed_actions
        opaque_proportion = opaque_encounters / total_governed_actions

    return {
        "opaque_path_encounter_frequency": opaque_encounters,
        "resolution_distribution": resolution_distribution,
        "transparent_vs_opaque_proportion": {
            "opaque_encounters": opaque_encounters,
            "opaque_proportion": round(opaque_proportion, 6),
            "total_governed_actions": total_governed_actions,
            "transparent_actions": transparent_actions,
            "transparent_proportion": round(transparent_proportion, 6),
        },
    }


def render_text(report: dict) -> str:
    proportion = report["transparent_vs_opaque_proportion"]
    lines = [
        f"transparent_actions={proportion['transparent_actions']}",
        f"opaque_encounters={proportion['opaque_encounters']}",
        f"total_governed_actions={proportion['total_governed_actions']}",
        f"transparent_proportion={proportion['transparent_proportion']:.6f}",
        f"opaque_proportion={proportion['opaque_proportion']:.6f}",
        f"opaque_path_encounter_frequency={report['opaque_path_encounter_frequency']}",
    ]
    for resolution in OPAQUE_RESOLUTIONS:
        lines.append(
            f"resolution_{resolution}={report['resolution_distribution'][resolution]}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Derive baseline opacity metrics from a JSONL chain.")
    ap.add_argument("chain_path")
    ap.add_argument("--format", choices=("json", "text"), default="json")
    args = ap.parse_args()

    chain_path = Path(args.chain_path)
    rows = load_chain(chain_path)
    report = derive_metrics(rows)

    if args.format == "text":
        print(render_text(report), end="")
    else:
        print(canonical_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
