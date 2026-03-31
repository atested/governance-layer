#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

KIND = "proof_bundle_summary_v1"


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


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("MANIFEST_INVALID")
    if not isinstance(obj, dict):
        raise ValueError("MANIFEST_INVALID")
    files = obj.get("files")
    if not isinstance(files, list):
        raise ValueError("MANIFEST_INVALID")
    return obj


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic proof-bundle summary")
    ap.add_argument("--input", required=True)
    args = ap.parse_args()

    try:
        manifest_path = _resolve_manifest(args.input)
        manifest = _load_manifest(manifest_path)
    except ValueError as exc:
        print(_canonical_json({"ok": False, "kind": KIND, "reason": str(exc)}), end="")
        return 1

    files = manifest.get("files", [])
    rows: list[dict[str, Any]] = []
    total_size = 0
    for row in files:
        if not isinstance(row, dict):
            print(_canonical_json({"ok": False, "kind": KIND, "reason": "MANIFEST_INVALID"}), end="")
            return 1
        p = row.get("path")
        d = row.get("sha256")
        size = row.get("size")
        if size is None:
            size = row.get("size_bytes")
        if not isinstance(p, str) or not isinstance(d, str) or not d.startswith("sha256:"):
            print(_canonical_json({"ok": False, "kind": KIND, "reason": "MANIFEST_INVALID"}), end="")
            return 1
        if not isinstance(size, int) or size < 0:
            print(_canonical_json({"ok": False, "kind": KIND, "reason": "MANIFEST_INVALID"}), end="")
            return 1
        total_size += size
        rows.append({"path": p, "sha256": d, "size_bytes": size})
    rows.sort(key=lambda x: x["path"])

    out = {
        "ok": True,
        "kind": KIND,
        "manifest_sha256": _sha256_bytes(manifest_path.read_bytes()),
        "bundle_version": manifest.get("bundle_version", ""),
        "hash_algo": manifest.get("hash_algo", ""),
        "file_count": len(rows),
        "total_size_bytes": total_size,
        "files": rows,
    }
    print(_canonical_json(out), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
