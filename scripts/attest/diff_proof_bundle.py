#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

KIND = "proof_bundle_diff_v1"


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


def _file_map(manifest: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    files = manifest.get("files", [])
    for row in files:
        if not isinstance(row, dict):
            raise ValueError("MANIFEST_INVALID")
        p = row.get("path")
        d = row.get("sha256")
        if not isinstance(p, str) or not p.strip():
            raise ValueError("MANIFEST_INVALID")
        if not isinstance(d, str) or not d.startswith("sha256:"):
            raise ValueError("MANIFEST_INVALID")
        if p in out:
            raise ValueError("SCHEMA_MISMATCH")
        out[p] = d
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic proof-bundle manifest diff")
    ap.add_argument("--left", required=True)
    ap.add_argument("--right", required=True)
    args = ap.parse_args()

    try:
        left_manifest_path = _resolve_manifest(args.left)
        right_manifest_path = _resolve_manifest(args.right)
        left_manifest = _load_manifest(left_manifest_path)
        right_manifest = _load_manifest(right_manifest_path)
        left_map = _file_map(left_manifest)
        right_map = _file_map(right_manifest)
    except ValueError as exc:
        print(_canonical_json({"ok": False, "kind": KIND, "reason": str(exc)}), end="")
        return 1

    left_keys = set(left_map.keys())
    right_keys = set(right_map.keys())
    added = sorted(right_keys - left_keys)
    removed = sorted(left_keys - right_keys)
    shared = sorted(left_keys & right_keys)
    changed_digests = [p for p in shared if left_map[p] != right_map[p]]
    unchanged = [p for p in shared if left_map[p] == right_map[p]]

    schema_mismatch: list[str] = []
    if left_manifest.get("bundle_version") != right_manifest.get("bundle_version"):
        schema_mismatch.append("bundle_version")
    if left_manifest.get("hash_algo") != right_manifest.get("hash_algo"):
        schema_mismatch.append("hash_algo")

    out = {
        "ok": True,
        "kind": KIND,
        "left_manifest_sha256": _sha256_bytes(left_manifest_path.read_bytes()),
        "right_manifest_sha256": _sha256_bytes(right_manifest_path.read_bytes()),
        "added": added,
        "removed": removed,
        "changed_digests": sorted(changed_digests),
        "unchanged": sorted(unchanged),
        "schema_mismatch": sorted(schema_mismatch),
    }
    print(_canonical_json(out), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
