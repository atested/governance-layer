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
from receipt_signing import sign_digest_with_key_input  # noqa: E402
from tool_catalog_store import get as get_tool_doc  # noqa: E402
from tool_catalog_store import store_root as tool_store_root  # noqa: E402

_TOOL_ID_RE = re.compile(r"tool_[0-9a-f]{16}$")
SCHEMA_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _list_tool_ids(repo_root: Path) -> list[str]:
    tools_dir = tool_store_root(repo_root) / "tools"
    if not tools_dir.is_dir():
        return []
    out = []
    for p in sorted(tools_dir.glob("*.json")):
        token = p.stem.strip()
        if token:
            out.append(token)
    return sorted(set(out))


def export_bundle(
    repo_root: Path,
    out_dir: Path,
    tool_ids: list[str],
    sign: bool = False,
    private_key: str = "",
) -> tuple[bool, str, str, str, bool, int]:
    resolved_ids = sorted({str(t).strip() for t in tool_ids if str(t).strip()})
    for tool_id in resolved_ids:
        if not _TOOL_ID_RE.fullmatch(tool_id):
            return False, "TOOL_ID_INVALID", "NONE", "NONE", False, 0
    if not resolved_ids:
        resolved_ids = _list_tool_ids(repo_root)
    for tool_id in resolved_ids:
        if not _TOOL_ID_RE.fullmatch(tool_id):
            return False, "TOOL_ID_INVALID", "NONE", "NONE", False, 0
    if not resolved_ids:
        return False, "TOOL_CATALOG_EMPTY", "NONE", "NONE", False, 0

    payload_dir = out_dir / "payload" / "tools"
    if out_dir.exists():
        import shutil

        shutil.rmtree(out_dir)
    payload_dir.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, Any]] = []
    for tool_id in resolved_ids:
        try:
            doc = get_tool_doc(repo_root, tool_id)
        except Exception:
            return False, "TOOL_DOC_INVALID", "NONE", "NONE", False, 0
        if doc is None:
            return False, "TOOL_NOT_FOUND", "NONE", "NONE", False, 0
        if str(doc.get("tool_id", "")).strip() != tool_id:
            return False, "TOOL_DOC_INVALID", "NONE", "NONE", False, 0
        schema_sha = str(doc.get("schema_sha256", "")).strip()
        if not SCHEMA_SHA_RE.fullmatch(schema_sha):
            return False, "TOOL_DOC_INVALID", "NONE", "NONE", False, 0
        raw = _canonical_json(doc).encode("utf-8")
        dst = payload_dir / f"{tool_id}.json"
        dst.write_bytes(raw)
        files.append(
            {
                "path": f"payload/tools/{tool_id}.json",
                "sha256": _sha256_bytes(raw),
                "size_bytes": len(raw),
            }
        )

    files.sort(key=lambda x: x["path"])
    manifest = {
        "bundle_version": "tool_catalog_bundle_v1",
        "hash_algo": "sha256",
        "tool_ids": resolved_ids,
        "files": files,
    }
    manifest_raw = _canonical_json(manifest).encode("utf-8")
    (out_dir / "manifest.json").write_bytes(manifest_raw)
    manifest_sha = _sha256_bytes(manifest_raw)
    bundle_id = "tcb_" + manifest_sha.split(":", 1)[1]

    signature_present = False
    if sign:
        if not private_key.strip():
            return False, "SIGNING_KEY_MISSING", "NONE", "NONE", False, len(resolved_ids)
        try:
            signed = sign_digest_with_key_input(manifest_sha, private_key)
        except Exception:
            return False, "SIGNING_FAILED", "NONE", "NONE", False, len(resolved_ids)
        (out_dir / "manifest.json.sig").write_text(signed["signature"] + "\n", encoding="utf-8")
        sigmeta = {
            "sigmeta_version": "v0",
            "algo": "ed25519",
            "manifest_sha256": manifest_sha,
            "pubkey_fingerprint": signed["pubkey_fingerprint"],
            "created_by": "export_tool_catalog_bundle_v1",
        }
        (out_dir / "manifest.json.sigmeta.json").write_text(_canonical_json(sigmeta), encoding="utf-8")
        signature_present = True
    return True, "OK", bundle_id, manifest_sha, signature_present, len(resolved_ids)


def main() -> int:
    ap = argparse.ArgumentParser(description="Export deterministic tool catalog bundle")
    ap.add_argument("--tool-id", action="append", default=[])
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sign", default="0")
    ap.add_argument("--private-key", default="")
    args = ap.parse_args()

    sign_raw = str(args.sign).strip()
    if sign_raw not in ("0", "1"):
        print(
            "TOOL_CATALOG_BUNDLE_EXPORT "
            "ok=no reason=SIGN_FLAG_INVALID bundle_id=NONE manifest_sha256=NONE "
            "tool_count=0 signature_present=no"
        )
        return 1

    out_raw = str(args.out_dir or "").strip().replace("\\", "/")
    out_parts = [p for p in out_raw.split("/") if p not in ("", ".")]
    if not out_raw or ".." in out_parts:
        print(
            "TOOL_CATALOG_BUNDLE_EXPORT "
            "ok=no reason=OUT_DIR_INVALID bundle_id=NONE manifest_sha256=NONE "
            "tool_count=0 signature_present=no"
        )
        return 1
    out_dir = Path(out_raw)
    if not out_dir.is_absolute():
        if not out_raw.startswith("out/"):
            print(
                "TOOL_CATALOG_BUNDLE_EXPORT "
                "ok=no reason=OUT_DIR_INVALID bundle_id=NONE manifest_sha256=NONE "
                "tool_count=0 signature_present=no"
            )
            return 1
        out_dir = REPO_ROOT / out_dir
    else:
        try:
            out_dir.relative_to(REPO_ROOT / "out")
        except ValueError:
            print(
                "TOOL_CATALOG_BUNDLE_EXPORT "
                "ok=no reason=OUT_DIR_INVALID bundle_id=NONE manifest_sha256=NONE "
                "tool_count=0 signature_present=no"
            )
            return 1

    ok, reason, bundle_id, manifest_sha, signature_present, tool_count = export_bundle(
        REPO_ROOT,
        out_dir,
        list(args.tool_id),
        sign=(sign_raw == "1"),
        private_key=str(args.private_key or ""),
    )
    print(
        "TOOL_CATALOG_BUNDLE_EXPORT "
        f"ok={'yes' if ok else 'no'} "
        f"reason={reason} "
        f"bundle_id={bundle_id} "
        f"manifest_sha256={manifest_sha} "
        f"tool_count={tool_count} "
        f"signature_present={'yes' if signature_present else 'no'}"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
