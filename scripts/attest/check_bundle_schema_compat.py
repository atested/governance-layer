#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("MANIFEST_INVALID")
    if not isinstance(data, dict):
        raise ValueError("MANIFEST_INVALID")
    return data


def _resolve(inp: str) -> Path:
    p = Path(inp)
    if not p.is_file():
        raise ValueError("MANIFEST_MISSING")
    return p


def main() -> int:
    ap = argparse.ArgumentParser(description="Check deterministic bundle schema/version compatibility")
    ap.add_argument("--left", required=True)
    ap.add_argument("--right", required=True)
    args = ap.parse_args()

    try:
        left = _load(_resolve(args.left))
        right = _load(_resolve(args.right))
    except ValueError as exc:
        print(_canonical_json({"ok": False, "kind": "bundle_schema_compat_v1", "compatibility": "malformed", "reason": str(exc)}), end="")
        return 1

    lv = left.get("bundle_version")
    rv = right.get("bundle_version")
    la = left.get("hash_algo")
    ra = right.get("hash_algo")

    if not isinstance(lv, str) or not isinstance(rv, str):
        print(_canonical_json({"ok": True, "kind": "bundle_schema_compat_v1", "compatibility": "incompatible", "reason": "BUNDLE_VERSION_MISSING"}), end="")
        return 0
    if not isinstance(la, str) or not isinstance(ra, str):
        print(_canonical_json({"ok": True, "kind": "bundle_schema_compat_v1", "compatibility": "incompatible", "reason": "HASH_ALGO_MISSING"}), end="")
        return 0

    if lv != rv:
        print(_canonical_json({"ok": True, "kind": "bundle_schema_compat_v1", "compatibility": "incompatible", "reason": "BUNDLE_VERSION_MISMATCH", "left_bundle_version": lv, "right_bundle_version": rv}), end="")
        return 0
    if la != ra:
        print(_canonical_json({"ok": True, "kind": "bundle_schema_compat_v1", "compatibility": "incompatible", "reason": "HASH_ALGO_MISMATCH", "left_hash_algo": la, "right_hash_algo": ra}), end="")
        return 0

    print(_canonical_json({"ok": True, "kind": "bundle_schema_compat_v1", "compatibility": "compatible", "reason": "SCHEMA_COMPATIBLE", "bundle_version": lv, "hash_algo": la}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
