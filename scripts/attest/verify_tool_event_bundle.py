#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_PREFIX = "TOOL_EVENT_BUNDLE_VERIFY"
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
BUNDLE_VERSION = "tool_event_bundle_v0"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _final(
    ok: bool,
    reason: str,
    bundle_version: str = "NONE",
    bundle_id: str = "NONE",
    manifest_sha256: str = "NONE",
    files_checked: int = 0,
    digests_count: int = 0,
) -> int:
    flag = "yes" if ok else "no"
    print(
        f"{VERIFY_PREFIX} ok={flag} reason={reason} "
        f"bundle_version={bundle_version} bundle_id={bundle_id} manifest_sha256={manifest_sha256} "
        f"files_checked={files_checked} tool_event_digests_count={digests_count}"
    )
    return 0 if ok else 1


def _load_manifest(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _valid_manifest_shape(manifest: dict[str, Any]) -> bool:
    digests = manifest.get("tool_event_digests")
    files = manifest.get("files")
    if manifest.get("bundle_version") != "tool_event_bundle_v0":
        return False
    if not isinstance(digests, list) or not all(isinstance(d, str) and DIGEST_RE.fullmatch(d) for d in digests):
        return False
    if digests != sorted(digests) or len(set(digests)) != len(digests):
        return False
    if not isinstance(files, dict):
        return False
    for rel, meta in files.items():
        if not isinstance(rel, str) or not rel.startswith("payload/"):
            return False
        if ".." in rel.split("/"):
            return False
        if not isinstance(meta, dict):
            return False
        sha = meta.get("sha256")
        sz = meta.get("size_bytes")
        if not isinstance(sha, str) or not DIGEST_RE.fullmatch(sha):
            return False
        if not isinstance(sz, int) or sz < 0:
            return False
    return True


def _payload_rel_for_digest(digest: str) -> str:
    return f"payload/{digest.replace(':', '_')}.json"


def verify(bundle_dir: Path) -> tuple[bool, str, str, str, int, int]:
    manifest_path = bundle_dir / "tool_event_bundle.manifest.json"
    if not manifest_path.is_file():
        return False, "MANIFEST_INVALID", "NONE", "NONE", 0, 0
    manifest = _load_manifest(manifest_path)
    if manifest is None or not _valid_manifest_shape(manifest):
        return False, "MANIFEST_INVALID", "NONE", "NONE", 0, 0

    manifest_sha = _sha256_bytes(manifest_path.read_bytes())
    bundle_id = "teb_" + manifest_sha.split(":", 1)[1]
    digests_count = len(manifest["tool_event_digests"])

    files = manifest["files"]
    if list(files.keys()) != sorted(files.keys()):
        return False, "MANIFEST_INVALID", "NONE", "NONE", 0, 0
    expected_files = sorted(_payload_rel_for_digest(digest) for digest in manifest["tool_event_digests"])
    if sorted(files.keys()) != expected_files:
        return False, "FILE_DIGEST_MAP_MISMATCH", BUNDLE_VERSION, bundle_id, manifest_sha, 0, digests_count

    files_checked = 0
    for rel_path, meta in files.items():
        payload_path = bundle_dir / rel_path
        if not payload_path.is_file():
            return False, "MISSING_FILE", BUNDLE_VERSION, bundle_id, manifest_sha, files_checked, digests_count
        data = payload_path.read_bytes()
        got_size = len(data)
        if got_size != int(meta["size_bytes"]):
            return False, "SIZE_MISMATCH", BUNDLE_VERSION, bundle_id, manifest_sha, files_checked, digests_count
        got_hash = _sha256_bytes(data)
        if got_hash != str(meta["sha256"]):
            return False, "HASH_MISMATCH", BUNDLE_VERSION, bundle_id, manifest_sha, files_checked, digests_count
        files_checked += 1

    return True, "OK", BUNDLE_VERSION, bundle_id, manifest_sha, files_checked, digests_count


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify deterministic tool-event bundle integrity")
    ap.add_argument("--bundle-dir", required=True)
    args = ap.parse_args()

    bundle_dir_raw = str(args.bundle_dir or "").strip().replace("\\", "/")
    if not bundle_dir_raw or ".." in bundle_dir_raw.split("/"):
        return _final(False, "BUNDLE_DIR_INVALID")
    bundle_dir = Path(bundle_dir_raw)
    if not bundle_dir.is_absolute():
        bundle_dir = REPO_ROOT / bundle_dir
    if not bundle_dir.is_dir():
        return _final(False, "BUNDLE_DIR_INVALID")
    try:
        ok, reason, bundle_version, bundle_id, manifest_sha, files_checked, digests_count = verify(bundle_dir)
    except Exception:
        return _final(False, "OTHER")
    return _final(ok, reason, bundle_version, bundle_id, manifest_sha, files_checked, digests_count)


if __name__ == "__main__":
    raise SystemExit(main())
