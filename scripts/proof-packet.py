#!/usr/bin/env python3
import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from coverage_stamp import validate_coverage_stamp

HASH_ALGO = "sha256"
PROOF_PACKET_VERSION = "proof_packet_v1"
MANIFEST_NAME = "manifest.json"
FIXED_MTIME = 0
FILE_MODE = 0o644


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


class DuplicateKeyError(ValueError):
    pass


def _strict_object_pairs_hook(pairs):
    out = {}
    for k, v in pairs:
        if k in out:
            raise DuplicateKeyError(f"duplicate manifest path: {k}")
        out[k] = v
    return out


def _fail(msg: str, rc: int = 1) -> int:
    print(f"FAIL: {msg}")
    return rc


def _load_manifest(raw: bytes):
    try:
        doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_strict_object_pairs_hook)
    except DuplicateKeyError as e:
        raise SystemExit(_fail(str(e)))
    except Exception as e:
        raise SystemExit(_fail(f"malformed manifest json: {e}"))
    return doc


def _validate_sha256_string(value, field_name):
    if not isinstance(value, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", value):
        raise SystemExit(_fail(f"{field_name} invalid sha256 marker"))


def _check_manifest_schema(doc):
    required_types = {
        "proof_packet_version": str,
        "hash_algo": str,
        "files": dict,
        "source_summary": dict,
    }
    for k, t in required_types.items():
        if k not in doc:
            raise SystemExit(_fail(f"manifest missing required key: {k}"))
        if not isinstance(doc[k], t):
            raise SystemExit(_fail(f"manifest key type mismatch: {k}"))

    if doc["proof_packet_version"] != PROOF_PACKET_VERSION:
        raise SystemExit(_fail("manifest proof_packet_version mismatch"))
    if doc["hash_algo"] != HASH_ALGO:
        raise SystemExit(_fail("manifest hash_algo mismatch"))

    allowed_top = set(required_types.keys()) | {"coverage_stamp"}
    extras = sorted(set(doc.keys()) - allowed_top)
    if extras:
        raise SystemExit(_fail(f"unexpected manifest top-level key: {extras[0]}"))

    if "coverage_stamp" in doc:
        cov = validate_coverage_stamp(doc["coverage_stamp"], required=True)
        if not cov.ok:
            raise SystemExit(_fail(f"manifest coverage_stamp invalid: {cov.reason_code}"))

    for rel, meta in sorted(doc["files"].items()):
        if not isinstance(rel, str):
            raise SystemExit(_fail("manifest files key type mismatch"))
        if not isinstance(meta, dict):
            raise SystemExit(_fail(f"manifest file entry type mismatch: {rel}"))
        if set(meta.keys()) != {"sha256", "size_bytes"}:
            raise SystemExit(_fail(f"manifest file entry keys invalid: {rel}"))
        _validate_sha256_string(meta["sha256"], f"manifest file {rel}")
        if not isinstance(meta["size_bytes"], int) or meta["size_bytes"] < 0:
            raise SystemExit(_fail(f"manifest file size_bytes invalid: {rel}"))

    if "replay_audit_report.json" not in doc["files"]:
        raise SystemExit(_fail("manifest missing replay_audit_report.json"))

    src = doc["source_summary"]
    if "replay_report_hash" not in src:
        raise SystemExit(_fail("source_summary missing replay_report_hash"))
    _validate_sha256_string(src["replay_report_hash"], "source_summary replay_report_hash")
    if "record_bytes_sha256" not in src:
        raise SystemExit(_fail("source_summary missing record_bytes_sha256"))
    _validate_sha256_string(src["record_bytes_sha256"], "source_summary record_bytes_sha256")


def read_file(path: Path) -> bytes:
    if not path.is_file():
        raise SystemExit(f"ERROR: file not found: {path}")
    return path.read_bytes()


def collect_payload_entries(record_path: Path, artifacts_dir: Path, replay_report_path: Path):
    if not artifacts_dir.is_dir():
        raise SystemExit(f"ERROR: artifacts-dir is not a directory: {artifacts_dir}")

    entries = []
    entries.append(("record.json", read_file(record_path)))
    entries.append(("replay_audit_report.json", read_file(replay_report_path)))

    for p in sorted(artifacts_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(artifacts_dir).as_posix()
        entries.append((f"artifacts/{rel}", p.read_bytes()))

    if not any(name.startswith("artifacts/") for name, _ in entries):
        raise SystemExit(f"ERROR: no artifact files found under artifacts-dir: {artifacts_dir}")

    # Canonical member order for payload and manifest file map.
    entries.sort(key=lambda x: x[0])
    return entries


def manifest_bytes(payload_entries):
    file_map = {}
    for rel, data in payload_entries:
        file_map[rel] = {
            "sha256": sha256_bytes(data),
            "size_bytes": len(data),
        }

    record_doc = {}
    try:
        record_doc = json.loads(dict(payload_entries)["record.json"].decode("utf-8"))
    except Exception:
        record_doc = {}

    replay_report_hash = file_map["replay_audit_report.json"]["sha256"]
    source_summary = {
        "replay_report_hash": replay_report_hash,
        "record_bytes_sha256": file_map["record.json"]["sha256"],
    }
    if isinstance(record_doc, dict):
        if isinstance(record_doc.get("record_hash"), str):
            source_summary["record_hash"] = record_doc["record_hash"]
        if isinstance(record_doc.get("signing_key_id"), str):
            source_summary["signing_key_id"] = record_doc["signing_key_id"]

    doc = {
        "proof_packet_version": PROOF_PACKET_VERSION,
        "hash_algo": HASH_ALGO,
        "files": file_map,
        "source_summary": source_summary,
    }
    coverage = validate_coverage_stamp(record_doc.get("coverage_stamp"), required=False)
    if not coverage.ok:
        raise SystemExit(_fail(f"record coverage_stamp invalid: {coverage.reason_code}", rc=2))
    if coverage.normalized is not None:
        doc["coverage_stamp"] = coverage.normalized
    return (json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def add_bytes(tf: tarfile.TarFile, arcname: str, data: bytes) -> None:
    ti = tarfile.TarInfo(name=arcname)
    ti.size = len(data)
    ti.mtime = FIXED_MTIME
    ti.uid = 0
    ti.gid = 0
    ti.uname = ""
    ti.gname = ""
    ti.mode = FILE_MODE
    tf.addfile(ti, io.BytesIO(data))


def cmd_pack(args: argparse.Namespace) -> int:
    record_path = Path(args.record)
    artifacts_dir = Path(args.artifacts_dir)
    replay_report_path = Path(args.replay_audit_report)
    out_path = Path(args.out)

    payload_entries = collect_payload_entries(record_path, artifacts_dir, replay_report_path)
    manifest = manifest_bytes(payload_entries)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(out_path, mode="w:", format=tarfile.USTAR_FORMAT) as tf:
        add_bytes(tf, MANIFEST_NAME, manifest)
        for rel, data in payload_entries:
            add_bytes(tf, f"payload/{rel}", data)

    packet = out_path.read_bytes()
    print(f"WROTE={out_path}")
    print(f"PROOF_PACKET_SHA256={sha256_bytes(packet)}")
    print(f"MANIFEST_SHA256={sha256_bytes(manifest)}")
    print("PROOF_PACKET_FILES=" + ",".join(rel for rel, _ in payload_entries))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    bundle_path = Path(args.bundle)
    if not bundle_path.is_file():
        return _fail(f"bundle not found: {bundle_path}", rc=2)
    packet_bytes = bundle_path.read_bytes()
    packet_hash = sha256_bytes(packet_bytes)

    try:
        with tarfile.open(bundle_path, "r:") as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            names = [m.name for m in members]
            if MANIFEST_NAME not in names:
                return _fail("missing manifest.json")

            payload_files = {}
            for m in members:
                if m.name == MANIFEST_NAME:
                    continue
                if not m.name.startswith("payload/"):
                    return _fail(f"unexpected top-level member: {m.name}")
                rel = m.name[len("payload/"):]
                payload_files[rel] = tf.extractfile(m).read()

            manifest_raw = tf.extractfile(MANIFEST_NAME).read()
    except tarfile.TarError as e:
        return _fail(f"tar parse error: {e}", rc=2)
    except OSError as e:
        return _fail(f"bundle read error: {e}", rc=2)

    manifest = _load_manifest(manifest_raw)
    _check_manifest_schema(manifest)

    manifest_files = manifest["files"]
    for rel in sorted(manifest_files.keys()):
        if rel not in payload_files:
            return _fail(f"manifest references missing payload member: {rel}")
        data = payload_files[rel]
        got_sha = sha256_bytes(data)
        exp_sha = manifest_files[rel]["sha256"]
        if got_sha != exp_sha:
            return _fail(f"hash mismatch for {rel} (got={got_sha} expected={exp_sha})")
        got_size = len(data)
        exp_size = manifest_files[rel]["size_bytes"]
        if got_size != exp_size:
            return _fail(f"size mismatch for {rel} (got={got_size} expected={exp_size})")

    extra = sorted(set(payload_files.keys()) - set(manifest_files.keys()))
    if extra:
        return _fail(f"unexpected payload member not in manifest: {extra[0]}")

    if manifest["source_summary"]["replay_report_hash"] != manifest_files["replay_audit_report.json"]["sha256"]:
        return _fail("source_summary replay_report_hash mismatch vs manifest file hash")
    if manifest["source_summary"]["record_bytes_sha256"] != manifest_files["record.json"]["sha256"]:
        return _fail("source_summary record_bytes_sha256 mismatch vs manifest file hash")

    print("PASS: proof packet manifest + payload hashes verified")
    if args.summary_json:
        src = manifest["source_summary"]
        coverage = validate_coverage_stamp(manifest.get("coverage_stamp"), required=False)
        summary = {
            "counts": {
                "matched": len(manifest_files),
                "mismatched": 0,
                "missing": 0,
                "extra": 0,
                "fatal": 0,
            },
            "hash_algo": HASH_ALGO,
            "key_linkage": {
                "record_bytes_sha256": src.get("record_bytes_sha256", manifest_files["record.json"]["sha256"]),
                "record_hash": src.get("record_hash"),
                "replay_report_hash": src.get("replay_report_hash"),
                "signing_key_id": src.get("signing_key_id"),
            },
            "packet_hash": packet_hash,
            "report_version": "proof_packet_verify_summary_v1",
            "result": "pass",
            "strictness": {
                "extra": "error",
                "missing": "error",
            },
            "tool": "proof-packet.verify",
        }
        if coverage.normalized is not None:
            summary["coverage_stamp_summary"] = {
                "coverage_stamp_version": "coverage_stamp_v1",
                "overall_status": coverage.overall_status,
                "reason_code": coverage.reason_code,
            }
        payload = (json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        Path(args.summary_json).write_bytes(payload)
        print(f"SUMMARY_SHA256={sha256_bytes(payload)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Proof-packet tools")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pack = sub.add_parser("pack", help="Build deterministic proof-packet from record + artifacts + replay audit report")
    p_pack.add_argument("--record", required=True)
    p_pack.add_argument("--artifacts-dir", required=True)
    p_pack.add_argument("--replay-audit-report", required=True)
    p_pack.add_argument("--out", required=True)
    p_pack.set_defaults(func=cmd_pack)

    p_verify = sub.add_parser("verify", help="Verify proof-packet manifest schema and payload hashes")
    p_verify.add_argument("--bundle", required=True)
    p_verify.add_argument("--summary-json", default=None)
    p_verify.set_defaults(func=cmd_verify)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
