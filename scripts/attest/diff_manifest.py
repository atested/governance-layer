#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

KIND = "manifest_diff_v1"


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _type_name(value: Any) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if value is None:
        return "null"
    return "unknown"


def _diff(left: Any, right: Any, path: str, out: dict[str, list[Any]]) -> None:
    left_t = _type_name(left)
    right_t = _type_name(right)
    if left_t != right_t:
        out["schema_mismatch"].append({"path": path, "left_type": left_t, "right_type": right_t})
        return

    if isinstance(left, dict):
        lk = set(left.keys())
        rk = set(right.keys())
        for k in sorted(lk - rk):
            p = f"{path}/{k}"
            out["removed"].append({"path": p, "left": left[k]})
        for k in sorted(rk - lk):
            p = f"{path}/{k}"
            out["added"].append({"path": p, "right": right[k]})
        for k in sorted(lk & rk):
            _diff(left[k], right[k], f"{path}/{k}", out)
        return

    if isinstance(left, list):
        n = min(len(left), len(right))
        for i in range(n):
            _diff(left[i], right[i], f"{path}/{i}", out)
        for i in range(n, len(left)):
            out["removed"].append({"path": f"{path}/{i}", "left": left[i]})
        for i in range(n, len(right)):
            out["added"].append({"path": f"{path}/{i}", "right": right[i]})
        return

    if left == right:
        out["unchanged"].append({"path": path, "value": left})
    else:
        out["changed"].append({"path": path, "left": left, "right": right})


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise ValueError("MANIFEST_INVALID")


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministic manifest diff utility")
    ap.add_argument("--left", required=True)
    ap.add_argument("--right", required=True)
    args = ap.parse_args()

    left_path = Path(args.left)
    right_path = Path(args.right)
    if not left_path.is_file() or not right_path.is_file():
        print(_canonical_json({"ok": False, "kind": KIND, "reason": "MANIFEST_MISSING"}), end="")
        return 1

    try:
        left = _load_json(left_path)
        right = _load_json(right_path)
    except ValueError as exc:
        print(_canonical_json({"ok": False, "kind": KIND, "reason": str(exc)}), end="")
        return 1

    out: dict[str, Any] = {
        "ok": True,
        "kind": KIND,
        "added": [],
        "removed": [],
        "changed": [],
        "unchanged": [],
        "schema_mismatch": [],
    }
    _diff(left, right, "", out)  # type: ignore[arg-type]
    print(_canonical_json(out), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
