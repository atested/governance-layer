#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


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
    for row in manifest["files"]:
        if not isinstance(row, dict):
            raise ValueError("MANIFEST_INVALID")
        path = row.get("path")
        digest = row.get("sha256")
        if not isinstance(path, str) or path == "":
            raise ValueError("MANIFEST_INVALID")
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ValueError("MANIFEST_INVALID")
        if path in out:
            raise ValueError("MANIFEST_INVALID")
        out[path] = digest
    return out


def _result(category: str, reason: str, added: list[str], removed: list[str], changed: list[str]) -> dict[str, Any]:
    return {
        "ok": True,
        "kind": "proof_bundle_drift_v1",
        "category": category,
        "reason": reason,
        "added": sorted(added),
        "removed": sorted(removed),
        "changed_digests": sorted(changed),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Classify drift between two proof bundles/manifests")
    ap.add_argument("--left", required=True)
    ap.add_argument("--right", required=True)
    args = ap.parse_args()

    try:
        left_path = _resolve_manifest(args.left)
        right_path = _resolve_manifest(args.right)
        left = _load_manifest(left_path)
        right = _load_manifest(right_path)
        left_map = _file_map(left)
        right_map = _file_map(right)
    except ValueError as exc:
        print(_canonical_json({"ok": False, "kind": "proof_bundle_drift_v1", "category": "malformed", "reason": str(exc)}), end="")
        return 1

    schema_mismatch = (
        left.get("bundle_version") != right.get("bundle_version")
        or left.get("hash_algo") != right.get("hash_algo")
    )

    left_keys = set(left_map)
    right_keys = set(right_map)
    added = sorted(right_keys - left_keys)
    removed = sorted(left_keys - right_keys)
    shared = sorted(left_keys & right_keys)
    changed = sorted([p for p in shared if left_map[p] != right_map[p]])

    if schema_mismatch:
        out = _result("structural", "SCHEMA_MISMATCH", added, removed, changed)
    elif not added and not removed and not changed:
        out = _result("unchanged", "NO_DRIFT", added, removed, changed)
    elif added and not removed and not changed:
        out = _result("additive", "ADDED_FILES_ONLY", added, removed, changed)
    elif removed and not added and not changed:
        out = _result("subtractive", "REMOVED_FILES_ONLY", added, removed, changed)
    elif changed and not added and not removed:
        out = _result("digest_only", "DIGESTS_CHANGED", added, removed, changed)
    else:
        out = _result("structural", "MIXED_DRIFT", added, removed, changed)

    print(_canonical_json(out), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
