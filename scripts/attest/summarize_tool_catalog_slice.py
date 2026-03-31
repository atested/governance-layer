#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(REPO_ROOT / "mcp"))
from tool_catalog_store import list_slice  # noqa: E402

PREFIX = "TOOL_CATALOG_SLICE_SUMMARY"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _fail(reason: str) -> int:
    print(
        f"{PREFIX} ok=no reason={reason} "
        "selected_count=0 summary_sha256=NONE report_path=NONE"
    )
    return 1


def _normalize_out_path(out_json: str) -> Path | None:
    raw = str(out_json or "").strip().replace("\\", "/")
    if not raw:
        return None
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if ".." in parts:
        raise ValueError("OUT_PATH_INVALID")
    out_path = Path(raw)
    if not out_path.is_absolute():
        if not raw.startswith("out/"):
            raise ValueError("OUT_PATH_INVALID")
        out_path = REPO_ROOT / out_path
    else:
        try:
            out_path.relative_to(REPO_ROOT / "out")
        except ValueError as exc:
            raise ValueError("OUT_PATH_INVALID") from exc
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate deterministic filtered tool-catalog summary")
    ap.add_argument("--created-from", default="any")
    ap.add_argument("--capability", default="")
    ap.add_argument("--limit", default="25")
    ap.add_argument("--out-json", default="")
    args = ap.parse_args()

    try:
        out_path = _normalize_out_path(str(args.out_json or ""))
    except ValueError as exc:
        return _fail(str(exc))

    try:
        rows = list_slice(
            REPO_ROOT,
            created_from=str(args.created_from or "any"),
            capability=str(args.capability or ""),
            limit=str(args.limit or "25"),
        )
    except ValueError:
        return _fail("FILTER_INVALID")

    by_created_from: dict[str, int] = {}
    by_capability: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    for row in rows:
        created_from = str(row.get("created_from", "")).strip()
        by_created_from[created_from] = by_created_from.get(created_from, 0) + 1
        caps = row.get("declared_capabilities", [])
        if isinstance(caps, list):
            for cap in caps:
                token = str(cap).strip()
                if token:
                    by_capability[token] = by_capability.get(token, 0) + 1
        items.append(
            {
                "tool_id": str(row.get("tool_id", "")),
                "tool_name": str(row.get("tool_name", "")),
                "tool_version": str(row.get("tool_version", "")),
                "created_from": created_from,
                "schema_sha256": str(row.get("schema_sha256", "")),
                "declared_capabilities": list(row.get("declared_capabilities", [])) if isinstance(row.get("declared_capabilities", []), list) else [],
                "index_seq": int(row.get("index_seq", 0)),
            }
        )

    summary = {
        "summary_version": "tool_catalog_slice_summary_v1",
        "filters": {
            "created_from": str(args.created_from or "any").strip().lower() or "any",
            "capability": str(args.capability or "").strip().upper(),
            "limit": max(1, min(int(args.limit), 500)),
        },
        "selected_count": len(items),
        "selected_tool_ids": [item["tool_id"] for item in items],
        "counts": {
            "by_created_from": {k: by_created_from[k] for k in sorted(by_created_from)},
            "by_declared_capability": {k: by_capability[k] for k in sorted(by_capability)},
        },
        "items": items,
    }

    summary_raw = _canonical_json(summary).encode("utf-8")
    summary_sha = _sha256_bytes(summary_raw)

    report_path = "NONE"
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(summary_raw)
        report_path = str(out_path.relative_to(REPO_ROOT)).replace("\\", "/")

    print(
        f"{PREFIX} ok=yes reason=OK "
        f"selected_count={len(items)} "
        f"summary_sha256={summary_sha} "
        f"report_path={report_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
