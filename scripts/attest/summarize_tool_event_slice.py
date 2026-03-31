#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR.parent.parent / "mcp"))
from tool_event_store import list_slice  # noqa: E402


SUMMARY_PREFIX = "TOOL_EVENT_SLICE_SUMMARY"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
HEX_PREFIX_RE = re.compile(r"^[0-9a-f]{4,64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _final(
    ok: bool,
    reason: str,
    selected_count: int = 0,
    summary_sha256: str = "NONE",
    report_path: str = "NONE",
) -> int:
    flag = "yes" if ok else "no"
    print(
        f"{SUMMARY_PREFIX} ok={flag} reason={reason} selected_count={selected_count} "
        f"summary_sha256={summary_sha256} report_path={report_path}"
    )
    return 0 if ok else 1


def _validate_out_path(token: str) -> bool:
    normalized = str(token or "").strip().replace("\\", "/")
    if not normalized.startswith("out/"):
        return False
    return ".." not in normalized.split("/")


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate deterministic filtered tool-event summary")
    ap.add_argument("--receipt-id", default="any")
    ap.add_argument("--digest-prefix", default="")
    ap.add_argument("--limit", default="25")
    ap.add_argument("--out-json", default="")
    args = ap.parse_args()

    receipt_id = str(args.receipt_id or "any").strip() or "any"
    digest_prefix = str(args.digest_prefix or "").strip().lower()
    try:
        limit = int(str(args.limit))
    except Exception:
        return _final(False, "FILTER_INVALID")
    if receipt_id != "any" and not RUN_ID_RE.fullmatch(receipt_id):
        return _final(False, "FILTER_INVALID")
    if digest_prefix and not HEX_PREFIX_RE.fullmatch(digest_prefix):
        return _final(False, "FILTER_INVALID")
    if limit < 1 or limit > 100:
        return _final(False, "FILTER_INVALID")
    out_json = str(args.out_json or "").strip().replace("\\", "/")
    if out_json and not _validate_out_path(out_json):
        return _final(False, "OUT_PATH_INVALID")

    repo_root = Path(__file__).resolve().parents[2]
    try:
        rows = list_slice(repo_root, receipt_id=receipt_id, digest_prefix=digest_prefix, limit=limit)
    except ValueError:
        return _final(False, "FILTER_INVALID")
    except Exception:
        return _final(False, "OTHER")

    by_receipt: dict[str, int] = {}
    for row in rows:
        rid = str(row.get("receipt_id", ""))
        by_receipt[rid] = by_receipt.get(rid, 0) + 1

    summary = {
        "summary_version": "tool_event_slice_summary_v1",
        "filters": {
            "receipt_id": receipt_id,
            "digest_prefix": digest_prefix,
            "limit": limit,
        },
        "selected_count": len(rows),
        "counts": {
            "by_receipt_id": {k: by_receipt[k] for k in sorted(by_receipt)},
        },
        "items": [
            {
                "receipt_id": str(r.get("receipt_id", "")),
                "run_id": str(r.get("run_id", "")),
                "stored_seq": int(r.get("stored_seq", 0)),
                "tool_event_digest": str(r.get("tool_event_digest", "")),
                "tool_event_ref": str(r.get("tool_event_ref", "")),
                "action_record_ref": str(r.get("action_record_ref", "")),
            }
            for r in rows
        ],
    }
    summary_raw = _canonical_json(summary).encode("utf-8")
    summary_sha = _sha256_bytes(summary_raw)

    report_path = "NONE"
    if out_json:
        out_path = repo_root / out_json
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(summary_raw)
        report_path = out_json

    return _final(True, "OK", selected_count=len(rows), summary_sha256=summary_sha, report_path=report_path)


if __name__ == "__main__":
    raise SystemExit(main())
