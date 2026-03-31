#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REASONS = {
    "OK",
    "MANIFEST_MISSING",
    "MANIFEST_INVALID",
    "FIELD_MISSING",
    "FIELD_INVALID",
    "DUPLICATE_PATH",
}


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _resolve_manifest(inp: str) -> Path:
    p = Path(inp)
    if p.is_dir():
        m = p / "manifest.json"
        if not m.is_file():
            raise ValueError("MANIFEST_MISSING")
        return m
    if p.is_file():
        return p
    raise ValueError("MANIFEST_MISSING")


def _fail(reason: str) -> tuple[int, dict[str, Any]]:
    if reason not in REASONS:
        reason = "MANIFEST_INVALID"
    return 1, {"ok": False, "kind": "proof_bundle_lint_v1", "reason": reason}


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("MANIFEST_INVALID")
    if not isinstance(obj, dict):
        raise ValueError("MANIFEST_INVALID")
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description="Lint proof-bundle manifest deterministically")
    ap.add_argument("--input", required=True)
    args = ap.parse_args()

    try:
        manifest_path = _resolve_manifest(args.input)
        manifest = _load_manifest(manifest_path)
    except ValueError as exc:
        rc, out = _fail(str(exc))
        print(_canonical_json(out), end="")
        return rc

    if not isinstance(manifest.get("bundle_version"), str):
        rc, out = _fail("FIELD_MISSING")
        print(_canonical_json(out), end="")
        return rc
    if not isinstance(manifest.get("hash_algo"), str):
        rc, out = _fail("FIELD_MISSING")
        print(_canonical_json(out), end="")
        return rc

    files = manifest.get("files")
    if not isinstance(files, list):
        rc, out = _fail("FIELD_MISSING")
        print(_canonical_json(out), end="")
        return rc

    seen: set[str] = set()
    normalized_files: list[dict[str, Any]] = []
    for row in files:
        if not isinstance(row, dict):
            rc, out = _fail("FIELD_INVALID")
            print(_canonical_json(out), end="")
            return rc

        path = row.get("path")
        digest = row.get("sha256")
        size = row.get("size_bytes", row.get("size"))

        if not isinstance(path, str) or path == "":
            rc, out = _fail("FIELD_INVALID")
            print(_canonical_json(out), end="")
            return rc
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            rc, out = _fail("FIELD_INVALID")
            print(_canonical_json(out), end="")
            return rc
        if not isinstance(size, int) or size < 0:
            rc, out = _fail("FIELD_INVALID")
            print(_canonical_json(out), end="")
            return rc

        if path in seen:
            rc, out = _fail("DUPLICATE_PATH")
            print(_canonical_json(out), end="")
            return rc
        seen.add(path)
        normalized_files.append({"path": path, "sha256": digest, "size_bytes": size})

    normalized_files.sort(key=lambda row: row["path"])

    out = {
        "ok": True,
        "kind": "proof_bundle_lint_v1",
        "reason": "OK",
        "manifest_sha256": _sha256_bytes(manifest_path.read_bytes()),
        "bundle_version": manifest["bundle_version"],
        "hash_algo": manifest["hash_algo"],
        "file_count": len(normalized_files),
        "files": normalized_files,
    }
    print(_canonical_json(out), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
