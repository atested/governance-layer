#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any


EXPORT_PREFIX = "RECEIPT_ATTESTATION_BUNDLE_EXPORT"
RECEIPT_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
RECEIPT_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class ExportError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"


def load_index(repo_root: Path) -> list[dict[str, str]]:
    p = repo_root / "out" / "mcp_exec" / "index.v1.json"
    if not p.is_file():
        raise ExportError("RECEIPT_INDEX_MISSING")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        raise ExportError("RECEIPT_INDEX_INVALID")
    rows = doc.get("receipts", [])
    if not isinstance(rows, list):
        raise ExportError("RECEIPT_INDEX_INVALID")
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        run_id = str(row.get("run_id", ""))
        digest = str(row.get("digest", ""))
        action_name = str(row.get("action_name", ""))
        outcome = str(row.get("outcome", ""))
        if run_id and digest and RECEIPT_RUN_ID_RE.fullmatch(run_id) and RECEIPT_DIGEST_RE.fullmatch(digest):
            out.append(
                {
                    "run_id": run_id,
                    "digest": digest,
                    "action_name": action_name,
                    "outcome": outcome,
                }
            )
    out.sort(key=lambda r: r["run_id"])
    return out


def select_receipt(repo_root: Path, run_id: str, digest: str) -> dict[str, str]:
    rows = load_index(repo_root)
    if bool(run_id) == bool(digest):
        raise ExportError("RECEIPT_SELECTOR_INVALID")
    if run_id and not RECEIPT_RUN_ID_RE.fullmatch(run_id):
        raise ExportError("RECEIPT_RUN_ID_INVALID")
    if digest and not RECEIPT_DIGEST_RE.fullmatch(digest):
        raise ExportError("RECEIPT_DIGEST_INVALID")
    if run_id:
        row = next((r for r in rows if r["run_id"] == run_id), None)
        if row is None:
            raise ExportError("RECEIPT_NOT_FOUND")
        return row

    matches = [r for r in rows if r["digest"] == digest]
    if not matches:
        raise ExportError("RECEIPT_NOT_FOUND")
    matches.sort(key=lambda r: r["run_id"])
    return matches[0]


def must_read(path: Path, token: str) -> bytes:
    if not path.is_file():
        raise ExportError(token)
    return path.read_bytes()


def _out_dir_token(repo_root: Path, out_dir: Path) -> str:
    try:
        return out_dir.relative_to(repo_root).as_posix()
    except ValueError:
        return out_dir.as_posix()


def _final(
    ok: bool,
    reason: str,
    bundle_version: str = "NONE",
    receipt_bundle_version: str = "NONE",
    bundle_id: str = "NONE",
    manifest_sha256: str = "NONE",
    files_count: int = 0,
    bundle_dir: str = "NONE",
    receipt_run_id: str = "NONE",
    receipt_digest: str = "NONE",
    signature_present: bool = False,
    replay_check_present: bool = False,
) -> int:
    print(
        f"{EXPORT_PREFIX} "
        f"ok={'yes' if ok else 'no'} "
        f"reason={reason} "
        f"bundle_version={bundle_version} "
        f"receipt_bundle_version={receipt_bundle_version} "
        f"bundle_id={bundle_id} "
        f"manifest_sha256={manifest_sha256} "
        f"files_count={files_count} "
        f"bundle_dir={bundle_dir} "
        f"receipt_run_id={receipt_run_id} "
        f"receipt_digest={receipt_digest} "
        f"signature_present={'yes' if signature_present else 'no'} "
        f"replay_check_present={'yes' if replay_check_present else 'no'}"
    )
    return 0 if ok else 1


def export_bundle(
    repo_root: Path,
    row: dict[str, str],
    out_dir: Path,
    include_signature: bool,
    include_replay_check: bool,
) -> tuple[bool, bool, str, str, int]:
    run_id = row["run_id"]
    digest = row["digest"]
    src_dir = repo_root / "out" / "mcp_exec" / run_id

    action_record_bytes = must_read(src_dir / "action_record.json", "RECEIPT_RECORD_MISSING")
    # Ensure digest binding to record body is preserved.
    computed = sha256_bytes(action_record_bytes)
    if computed != digest:
        raise ExportError("RECEIPT_DIGEST_MISMATCH")

    payload_dir = out_dir / "payload"
    sig_dir = out_dir / "sig"
    if out_dir.exists():
        shutil.rmtree(out_dir)
    payload_dir.mkdir(parents=True, exist_ok=True)
    sig_dir.mkdir(parents=True, exist_ok=True)

    (payload_dir / "record.json").write_bytes(action_record_bytes)
    (payload_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (payload_dir / "artifacts" / "action_record.sha256").write_text(digest + "\n", encoding="utf-8")

    files: list[dict[str, Any]] = []

    def add_file(rel_path: str, raw: bytes) -> None:
        files.append({"path": rel_path, "sha256": sha256_bytes(raw), "size": len(raw)})

    rec_rel = "record.json"
    rec_bytes = (payload_dir / "record.json").read_bytes()
    add_file(rec_rel, rec_bytes)

    sha_rel = "artifacts/action_record.sha256"
    sha_bytes = (payload_dir / "artifacts" / "action_record.sha256").read_bytes()
    add_file(sha_rel, sha_bytes)

    sig_src = src_dir / "action_record.sig"
    sigmeta_src = src_dir / "action_record.sigmeta.json"
    has_sig = sig_src.is_file() and sigmeta_src.is_file()
    if include_signature and not has_sig:
        raise ExportError("SIGNATURE_MISSING")

    signature_present = False
    if has_sig:
        sig_dst = sig_dir / "action_record.sig"
        sigmeta_dst = sig_dir / "action_record.sigmeta.json"
        sig_dst.write_bytes(sig_src.read_bytes())
        sigmeta_dst.write_bytes(sigmeta_src.read_bytes())
        add_file("artifacts/action_record.sig", sig_dst.read_bytes())
        add_file("artifacts/action_record.sigmeta.json", sigmeta_dst.read_bytes())
        signature_present = True

    replay_src = src_dir / "replay_check.v0.json"
    has_replay = replay_src.is_file()
    if include_replay_check and not has_replay:
        raise ExportError("REPLAY_ARTIFACT_MISSING")
    replay_present = False
    if has_replay:
        replay_dst = payload_dir / "artifacts" / "replay_check.v0.json"
        replay_dst.write_bytes(replay_src.read_bytes())
        add_file("artifacts/replay_check.v0.json", replay_dst.read_bytes())
        replay_present = True

    # Include capability-specific artifacts when deterministically available.
    if row.get("action_name") == "INGEST_TOOL_EVENT":
        tool_event_src = repo_root / "out" / "mcp_ingest_tool_event" / run_id / "tool_event.v0.json"
        if tool_event_src.is_file():
            tool_event_dst = payload_dir / "artifacts" / "tool_event.v0.json"
            tool_event_dst.write_bytes(tool_event_src.read_bytes())
            add_file("artifacts/tool_event.v0.json", tool_event_dst.read_bytes())

    files.sort(key=lambda x: x["path"])
    manifest = {
        "bundle_version": "attestation_bundle_v1",
        "receipt_bundle_version": "receipt_attestation_bundle_v0",
        "hash_algo": "sha256",
        "receipt_digest": digest,
        "receipt_run_id": run_id,
        "signature_present": signature_present,
        "replay_check_present": replay_present,
        "action_name": row.get("action_name", ""),
        "outcome": row.get("outcome", ""),
        "files": files,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(canonical_json(manifest), encoding="utf-8")
    manifest_sha = sha256_bytes(manifest_path.read_bytes())
    bundle_id = "rab_" + manifest_sha.split(":", 1)[1]
    return signature_present, replay_present, bundle_id, manifest_sha, len(files)


def main() -> int:
    ap = argparse.ArgumentParser(description="Export MCP receipt to deterministic attestation bundle directory")
    ap.add_argument("--receipt-run-id", default="")
    ap.add_argument("--receipt-digest", default="")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--include-signature", choices=["0", "1"], default="1")
    ap.add_argument("--include-replay-check", choices=["0", "1"], default="0")
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parents[2]
    out_raw = str(args.out_dir or "").strip().replace("\\", "/")
    out_parts = [p for p in out_raw.split("/") if p not in ("", ".")]
    if not out_raw or ".." in out_parts:
        return _final(False, "OUT_DIR_INVALID")
    out_dir = Path(out_raw)
    if not out_dir.is_absolute():
        if not out_raw.startswith("out/"):
            return _final(False, "OUT_DIR_INVALID")
        out_dir = repo_root / out_dir
    else:
        try:
            out_dir.relative_to(repo_root / "out")
        except ValueError:
            return _final(False, "OUT_DIR_INVALID")
    try:
        row = select_receipt(repo_root, args.receipt_run_id.strip(), args.receipt_digest.strip())
        signature_present, replay_present, bundle_id, manifest_sha, files_count = export_bundle(
            repo_root,
            row,
            out_dir,
            include_signature=args.include_signature == "1",
            include_replay_check=args.include_replay_check == "1",
        )
    except ExportError as exc:
        return _final(False, exc.reason)
    except Exception:
        return _final(False, "OTHER")
    return _final(
        True,
        "OK",
        bundle_version="attestation_bundle_v1",
        receipt_bundle_version="receipt_attestation_bundle_v0",
        bundle_id=bundle_id,
        manifest_sha256=manifest_sha,
        files_count=files_count,
        bundle_dir=_out_dir_token(repo_root, out_dir),
        receipt_run_id=row["run_id"],
        receipt_digest=row["digest"],
        signature_present=signature_present,
        replay_check_present=replay_present,
    )


if __name__ == "__main__":
    raise SystemExit(main())
