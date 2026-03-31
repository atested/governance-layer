#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _artifact_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in sorted(root.rglob("*"), key=lambda x: x.as_posix()):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        rows.append({"path": rel, "size_bytes": p.stat().st_size, "sha256": _sha256_file(p)})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description="Deterministically index local attestation artifacts")
    ap.add_argument("--input", required=True)
    args = ap.parse_args()

    root = Path(args.input)
    if not root.is_dir():
        print(_canonical_json({"ok": False, "kind": "attestation_artifact_index_v1", "reason": "INPUT_NOT_DIRECTORY"}), end="")
        return 1

    rows = _artifact_rows(root)
    if not rows:
        print(_canonical_json({"ok": False, "kind": "attestation_artifact_index_v1", "reason": "EMPTY_ARTIFACT_SET"}), end="")
        return 1

    manifest = root / "manifest.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            print(_canonical_json({"ok": False, "kind": "attestation_artifact_index_v1", "reason": "MANIFEST_INVALID"}), end="")
            return 1
        if not isinstance(data, dict):
            print(_canonical_json({"ok": False, "kind": "attestation_artifact_index_v1", "reason": "MANIFEST_INVALID"}), end="")
            return 1

    top_level = sorted({row["path"].split("/", 1)[0] for row in rows})
    out = {
        "ok": True,
        "kind": "attestation_artifact_index_v1",
        "artifact_count": len(rows),
        "top_level_nodes": top_level,
        "artifacts": rows,
    }
    print(_canonical_json(out), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
