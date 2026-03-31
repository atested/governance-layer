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
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("MANIFEST_INVALID")
    if not isinstance(data, dict):
        raise ValueError("MANIFEST_INVALID")
    files = data.get("files")
    if not isinstance(files, list):
        raise ValueError("MANIFEST_INVALID")
    return data


def _file_map(manifest: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in manifest.get("files", []):
        if not isinstance(row, dict):
            raise ValueError("MANIFEST_INVALID")
        p = row.get("path")
        d = row.get("sha256")
        if not isinstance(p, str) or not p:
            raise ValueError("MANIFEST_INVALID")
        if not isinstance(d, str) or not d.startswith("sha256:"):
            raise ValueError("MANIFEST_INVALID")
        if p in out:
            raise ValueError("MANIFEST_INVALID")
        out[p] = d
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Assess deterministic proof-bundle mergeability")
    ap.add_argument("--left", required=True)
    ap.add_argument("--right", required=True)
    args = ap.parse_args()

    try:
        left_manifest = _load_manifest(_resolve_manifest(args.left))
        right_manifest = _load_manifest(_resolve_manifest(args.right))
        left_map = _file_map(left_manifest)
        right_map = _file_map(right_manifest)
    except ValueError as exc:
        print(
            _canonical_json(
                {
                    "ok": False,
                    "kind": "proof_bundle_mergeability_v1",
                    "mergeability": "malformed",
                    "reason": str(exc),
                }
            ),
            end="",
        )
        return 1

    left_version = left_manifest.get("bundle_version")
    right_version = right_manifest.get("bundle_version")
    left_algo = left_manifest.get("hash_algo")
    right_algo = right_manifest.get("hash_algo")

    if not isinstance(left_version, str) or not isinstance(right_version, str):
        print(_canonical_json({"ok": True, "kind": "proof_bundle_mergeability_v1", "mergeability": "ambiguous", "reason": "BUNDLE_VERSION_MISSING"}), end="")
        return 0
    if not isinstance(left_algo, str) or not isinstance(right_algo, str):
        print(_canonical_json({"ok": True, "kind": "proof_bundle_mergeability_v1", "mergeability": "ambiguous", "reason": "HASH_ALGO_MISSING"}), end="")
        return 0

    if left_version != right_version:
        print(_canonical_json({"ok": True, "kind": "proof_bundle_mergeability_v1", "mergeability": "incompatible", "reason": "BUNDLE_VERSION_MISMATCH"}), end="")
        return 0
    if left_algo != right_algo:
        print(_canonical_json({"ok": True, "kind": "proof_bundle_mergeability_v1", "mergeability": "incompatible", "reason": "HASH_ALGO_MISMATCH"}), end="")
        return 0

    shared = sorted(set(left_map) & set(right_map))
    conflicts = sorted([p for p in shared if left_map[p] != right_map[p]])

    if conflicts:
        out = {
            "ok": True,
            "kind": "proof_bundle_mergeability_v1",
            "mergeability": "incompatible",
            "reason": "CONFLICTING_DIGESTS",
            "shared_paths": shared,
            "conflicting_paths": conflicts,
        }
    else:
        out = {
            "ok": True,
            "kind": "proof_bundle_mergeability_v1",
            "mergeability": "compatible",
            "reason": "NO_CONFLICTING_DIGESTS",
            "shared_paths": shared,
            "conflicting_paths": [],
        }

    print(_canonical_json(out), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
