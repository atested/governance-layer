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
from tool_event_store import list_all_tool_events  # noqa: E402


EXPORT_PREFIX = "TOOL_EVENT_BUNDLE_EXPORT"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RECEIPT_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
BUNDLE_VERSION = "tool_event_bundle_v0"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _is_repo_relative_path(ref: str) -> bool:
    path = Path(ref)
    if path.is_absolute():
        return False
    parts = [part for part in ref.replace("\\", "/").split("/") if part not in ("", ".")]
    return ".." not in parts


def _final(
    ok: bool,
    reason: str,
    bundle_id: str = "NONE",
    manifest_sha256: str = "NONE",
    digests_count: int = 0,
    bundle_version: str = "NONE",
) -> int:
    flag = "yes" if ok else "no"
    print(
        f"{EXPORT_PREFIX} ok={flag} reason={reason} "
        f"bundle_version={bundle_version} bundle_id={bundle_id} "
        f"manifest_sha256={manifest_sha256} tool_event_digests_count={digests_count}"
    )
    return 0 if ok else 1


def _select_rows(rows: list[dict[str, Any]], digest: str, receipt_id: str) -> list[dict[str, Any]]:
    if digest:
        return [r for r in rows if r.get("tool_event_digest") == digest]
    if receipt_id:
        return [r for r in rows if r.get("receipt_id") == receipt_id]
    return []


def export_bundle(repo_root: Path, rows: list[dict[str, Any]], out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload_dir = out_dir / "payload"
    payload_dir.mkdir(parents=True, exist_ok=True)

    selected = sorted(rows, key=lambda r: (str(r.get("tool_event_digest", "")), str(r.get("run_id", ""))))
    if not selected:
        return _final(False, "TOOL_EVENT_NOT_FOUND")

    files_map: dict[str, dict[str, Any]] = {}
    digests: list[str] = []
    for row in selected:
        digest = str(row.get("tool_event_digest", ""))
        if not DIGEST_RE.fullmatch(digest):
            return _final(False, "TOOL_EVENT_DIGEST_INVALID")
        event_ref = str(row.get("tool_event_ref", ""))
        if not _is_repo_relative_path(event_ref):
            return _final(False, "TOOL_EVENT_REF_INVALID")
        src = repo_root / event_ref
        if not src.is_file():
            return _final(False, "TOOL_EVENT_PAYLOAD_MISSING")
        body = src.read_bytes()
        if _sha256_bytes(body) != digest:
            return _final(False, "TOOL_EVENT_DIGEST_MISMATCH")
        rel_name = digest.replace(":", "_") + ".json"
        rel_path = f"payload/{rel_name}"
        dst = payload_dir / rel_name
        dst.write_bytes(body)
        files_map[rel_path] = {"sha256": _sha256_bytes(body), "size_bytes": len(body)}
        digests.append(digest)

    manifest = {
        "bundle_version": BUNDLE_VERSION,
        "tool_event_digests": sorted(digests),
        "files": {k: files_map[k] for k in sorted(files_map)},
    }
    (out_dir / "tool_event_bundle.manifest.json").write_text(
        _canonical_json(manifest) + "\n",
        encoding="utf-8",
    )
    manifest_sha = _sha256_bytes((out_dir / "tool_event_bundle.manifest.json").read_bytes())
    bundle_id = "teb_" + manifest_sha.split(":", 1)[1]
    return _final(
        True,
        "OK",
        bundle_id=bundle_id,
        manifest_sha256=manifest_sha,
        digests_count=len(digests),
        bundle_version=BUNDLE_VERSION,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Export deterministic tool event bundle")
    ap.add_argument("--digest", default="")
    ap.add_argument("--receipt-id", default="")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    digest = args.digest.strip()
    receipt_id = args.receipt_id.strip()
    if bool(digest) == bool(receipt_id):
        return _final(False, "PROVIDE_DIGEST_OR_RECEIPT_ID")
    if digest and not DIGEST_RE.fullmatch(digest):
        return _final(False, "DIGEST_INVALID")
    if receipt_id and not RECEIPT_RE.fullmatch(receipt_id):
        return _final(False, "RECEIPT_ID_INVALID")

    out_rel = args.out_dir.strip().replace("\\", "/")
    if not out_rel.startswith("out/") or ".." in out_rel.split("/"):
        return _final(False, "OUT_DIR_INVALID")

    repo_root = Path(__file__).resolve().parents[2]
    rows = list_all_tool_events(repo_root)
    selected = _select_rows(rows, digest, receipt_id)
    return export_bundle(repo_root, selected, repo_root / out_rel)


if __name__ == "__main__":
    raise SystemExit(main())
