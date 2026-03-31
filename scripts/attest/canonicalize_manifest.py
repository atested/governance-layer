#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

KIND = "manifest_canonical_v1"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256_json(obj: Any) -> str:
    data = _canonical_json(obj).encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _normalize(value[k]) for k in sorted(value.keys())}
    if isinstance(value, list):
        norm = [_normalize(v) for v in value]
        return sorted(norm, key=lambda v: _canonical_json(v))
    return value


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("MANIFEST_INVALID")


def main() -> int:
    ap = argparse.ArgumentParser(description="Canonicalize manifest-like JSON deterministically")
    ap.add_argument("--input", required=True)
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.is_file():
        print(_canonical_json({"ok": False, "kind": KIND, "reason": "MANIFEST_MISSING"}), end="")
        return 1

    try:
        raw = _load_json(inp)
    except ValueError as exc:
        print(_canonical_json({"ok": False, "kind": KIND, "reason": str(exc)}), end="")
        return 1

    canonical = _normalize(raw)
    out = {
        "ok": True,
        "kind": KIND,
        "canonical_sha256": _sha256_json(canonical),
        "canonical": canonical,
    }
    print(_canonical_json(out), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
