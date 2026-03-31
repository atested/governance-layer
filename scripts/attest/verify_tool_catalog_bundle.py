#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(REPO_ROOT / "mcp"))
from receipt_signing import verify_digest_signature_with_key_input  # noqa: E402

_TOOL_ID_RE = re.compile(r"tool_[0-9a-f]{16}$")
DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def verify(bundle_dir: Path, require_signature: bool = False, pubkey: str = "") -> tuple[bool, str, str, str, str]:
    manifest_path = bundle_dir / "manifest.json"
    if not manifest_path.is_file():
        return False, "MANIFEST_MISSING", "NONE", "NONE", "no" if require_signature else "not_required"
    try:
        manifest_raw = manifest_path.read_bytes()
    except Exception:
        return False, "MANIFEST_INVALID", "NONE", "NONE", "no" if require_signature else "not_required"
    manifest_sha = _sha256_bytes(manifest_raw)
    bundle_id = "tcb_" + manifest_sha.split(":", 1)[1]
    try:
        manifest_obj = json.loads(manifest_raw.decode("utf-8"))
    except Exception:
        return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
    if not isinstance(manifest_obj, dict):
        return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
    if manifest_obj.get("bundle_version") != "tool_catalog_bundle_v1":
        return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
    tool_ids = manifest_obj.get("tool_ids", [])
    files = manifest_obj.get("files", [])
    if not isinstance(tool_ids, list) or not isinstance(files, list):
        return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
    clean_tool_ids = [str(t) for t in tool_ids if isinstance(t, str)]
    if not all(_TOOL_ID_RE.fullmatch(t) for t in clean_tool_ids):
        return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
    if clean_tool_ids != sorted(set(clean_tool_ids)):
        return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
    paths = [row.get("path") for row in files if isinstance(row, dict)]
    if not all(isinstance(p, str) for p in paths):
        return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"

    seen_tool_ids: list[str] = []
    for file_row in files:
        if not isinstance(file_row, dict):
            return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
        rel = file_row.get("path")
        expected_sha = file_row.get("sha256")
        expected_size = file_row.get("size_bytes")
        if not isinstance(rel, str) or not isinstance(expected_sha, str) or not isinstance(expected_size, int):
            return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
        if not DIGEST_RE.fullmatch(expected_sha):
            return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
        if rel.startswith("/") or ".." in rel.split("/"):
            return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
        p = bundle_dir / rel
        if not p.is_file():
            return False, "MISSING_FILE", bundle_id, manifest_sha, "no" if require_signature else "not_required"
        raw = p.read_bytes()
        if len(raw) != expected_size:
            return False, "SIZE_MISMATCH", bundle_id, manifest_sha, "no" if require_signature else "not_required"
        if _sha256_bytes(raw) != expected_sha:
            return False, "HASH_MISMATCH", bundle_id, manifest_sha, "no" if require_signature else "not_required"
        if rel.startswith("payload/tools/"):
            try:
                doc = json.loads(raw.decode("utf-8"))
            except Exception:
                return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
            if not isinstance(doc, dict):
                return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
            schema = doc.get("schema_json")
            schema_sha = doc.get("schema_sha256")
            if not isinstance(schema, dict) or not isinstance(schema_sha, str):
                return False, "SCHEMA_HASH_MISMATCH", bundle_id, manifest_sha, "no" if require_signature else "not_required"
            computed = hashlib.sha256(_canonical_json(schema).encode("utf-8")).hexdigest()
            if computed != schema_sha:
                return False, "SCHEMA_HASH_MISMATCH", bundle_id, manifest_sha, "no" if require_signature else "not_required"
            tool_id = str(doc.get("tool_id", "")).strip()
            file_tool_id = rel.split("/")[-1].removesuffix(".json")
            if not _TOOL_ID_RE.fullmatch(tool_id):
                return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
            if file_tool_id != tool_id:
                return False, "MANIFEST_INVALID", bundle_id, manifest_sha, "no" if require_signature else "not_required"
            seen_tool_ids.append(tool_id)

    if sorted(set(seen_tool_ids)) != clean_tool_ids:
        return False, "TOOL_ID_SET_MISMATCH", bundle_id, manifest_sha, "no" if require_signature else "not_required"

    if require_signature:
        sig_path = bundle_dir / "manifest.json.sig"
        sigmeta_path = bundle_dir / "manifest.json.sigmeta.json"
        if not sig_path.is_file() or not sigmeta_path.is_file():
            return False, "SIG_MISSING", bundle_id, manifest_sha, "no"
        try:
            sigmeta = json.loads(sigmeta_path.read_text(encoding="utf-8"))
        except Exception:
            return False, "SIGMETA_MISMATCH", bundle_id, manifest_sha, "no"
        digest = manifest_sha
        if not isinstance(sigmeta, dict) or str(sigmeta.get("manifest_sha256", "")) != digest:
            return False, "SIGMETA_MISMATCH", bundle_id, manifest_sha, "no"
        signature = sig_path.read_text(encoding="utf-8").strip()
        if not pubkey.strip():
            return False, "SIG_INVALID", bundle_id, manifest_sha, "no"
        if not verify_digest_signature_with_key_input(digest, signature, pubkey):
            return False, "SIG_INVALID", bundle_id, manifest_sha, "no"
        return True, "OK", bundle_id, manifest_sha, "yes"

    return True, "OK", bundle_id, manifest_sha, "not_required"


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify deterministic tool catalog bundle")
    ap.add_argument("--bundle-dir", required=True)
    ap.add_argument("--require-signature", default="0")
    ap.add_argument("--pubkey", default="")
    args = ap.parse_args()

    req = str(args.require_signature).strip()
    if req not in ("0", "1"):
        print(
            "TOOL_CATALOG_BUNDLE_VERIFY "
            "ok=no reason=REQUIRE_SIGNATURE_FLAG_INVALID "
            "bundle_id=NONE manifest_sha256=NONE signature_verified=not_required"
        )
        return 1
    bundle_dir_raw = str(args.bundle_dir or "").strip().replace("\\", "/")
    if not bundle_dir_raw or ".." in bundle_dir_raw.split("/"):
        print(
            "TOOL_CATALOG_BUNDLE_VERIFY "
            "ok=no reason=BUNDLE_DIR_INVALID "
            "bundle_id=NONE manifest_sha256=NONE signature_verified=not_required"
        )
        return 1
    bundle_dir = Path(bundle_dir_raw)
    if not bundle_dir.is_absolute():
        bundle_dir = REPO_ROOT / bundle_dir
    if not bundle_dir.is_dir():
        print(
            "TOOL_CATALOG_BUNDLE_VERIFY "
            "ok=no reason=BUNDLE_DIR_INVALID "
            "bundle_id=NONE manifest_sha256=NONE signature_verified=not_required"
        )
        return 1
    ok, reason, bundle_id, manifest_sha, signature_verified = verify(
        bundle_dir, require_signature=(req == "1"), pubkey=str(args.pubkey or "")
    )
    print(
        "TOOL_CATALOG_BUNDLE_VERIFY "
        f"ok={'yes' if ok else 'no'} "
        f"reason={reason} "
        f"bundle_id={bundle_id} "
        f"manifest_sha256={manifest_sha} "
        f"signature_verified={signature_verified}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
