#!/usr/bin/env python3
import argparse
import hashlib
import json
import sys
import tarfile
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "mcp"))
from receipt_signing import verify_digest_signature_with_key_input  # noqa: E402

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR / "attest"))
import ed25519_bundle_signing as edsig

HASH_ALGO = "sha256"
MANIFEST_NAME = "manifest.json"
PAYLOAD_PREFIX = "payload/"
VERIFY_PREFIX = "ATTESTATION_BUNDLE_VERIFY"


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def fail(msg: str, code: int = 1) -> int:
    print(f"FAIL: {msg}")
    return code


def _final(
    ok: bool,
    reason: str,
    human_lines: Optional[list[str]] = None,
    code: int = 0,
    bundle_version: str = "NONE",
    receipt_bundle_version: str = "NONE",
    bundle_id: str = "NONE",
    manifest_sha256: str = "NONE",
    files_checked: int = 0,
    signature_verified: str = "not_required",
) -> int:
    print(
        f"{VERIFY_PREFIX} "
        f"ok={'yes' if ok else 'no'} "
        f"reason={reason} "
        f"bundle_version={bundle_version} "
        f"receipt_bundle_version={receipt_bundle_version} "
        f"bundle_id={bundle_id} "
        f"manifest_sha256={manifest_sha256} "
        f"files_checked={files_checked} "
        f"signature_verified={signature_verified}"
    )
    for line in human_lines or []:
        print(line)
    return code


def _load_bundle(path: Path) -> tuple[bytes, dict[str, bytes]]:
    if path.is_file():
        try:
            tf = tarfile.open(path, "r:")
        except tarfile.TarError as e:
            raise ValueError(f"cannot read bundle tar: {e}")
        with tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            names = [m.name for m in members]
            if MANIFEST_NAME not in names:
                raise ValueError("missing manifest.json")
            if len(names) != len(set(names)):
                raise ValueError("duplicate tar member names")
            mf = tf.extractfile(MANIFEST_NAME)
            if mf is None:
                raise ValueError("cannot read manifest.json")
            manifest_raw = mf.read()
            payload_files: dict[str, bytes] = {}
            for m in members:
                if m.name == MANIFEST_NAME:
                    continue
                if m.name.startswith(PAYLOAD_PREFIX):
                    rel = m.name[len(PAYLOAD_PREFIX) :]
                elif m.name.startswith("sig/"):
                    rel = m.name
                else:
                    raise ValueError(f"unexpected bundle member outside payload/: {m.name}")
                f = tf.extractfile(m)
                if f is None:
                    raise ValueError(f"cannot read payload member: {rel}")
                payload_files[rel] = f.read()
            return manifest_raw, payload_files
    if path.is_dir():
        manifest_path = path / MANIFEST_NAME
        if not manifest_path.is_file():
            raise ValueError("missing manifest.json")
        manifest_raw = manifest_path.read_bytes()
        payload_files: dict[str, bytes] = {}
        payload_root = path / "payload"
        if payload_root.is_dir():
            for p in sorted(payload_root.rglob("*")):
                if p.is_file():
                    rel = str(p.relative_to(payload_root)).replace("\\", "/")
                    payload_files[rel] = p.read_bytes()
        sig_root = path / "sig"
        if sig_root.is_dir():
            for p in sorted(sig_root.rglob("*")):
                if p.is_file():
                    rel = "sig/" + str(p.relative_to(sig_root)).replace("\\", "/")
                    payload_files[rel] = p.read_bytes()
        return manifest_raw, payload_files
    raise ValueError(f"bundle not found: {path}")


def _validate_receipt_extension(
    manifest: dict[str, Any], payload_map: dict[str, bytes], receipt_pubkey: str, require_signature: bool
) -> int:
    if manifest.get("receipt_bundle_version") != "receipt_attestation_bundle_v0":
        return 0
    receipt_digest = manifest.get("receipt_digest")
    if not isinstance(receipt_digest, str) or not receipt_digest.startswith("sha256:"):
        return fail("receipt_digest missing or invalid")
    if "record.json" not in payload_map:
        return fail("manifest missing record.json")
    got = sha256_bytes(payload_map["record.json"])
    if got != receipt_digest:
        return fail("receipt_digest mismatch vs record.json hash")

    signature_present = bool(manifest.get("signature_present", False))
    if require_signature and not signature_present:
        return fail("SIGNATURE_MISSING")
    if not signature_present:
        return 0
    if "artifacts/action_record.sig" not in payload_map:
        return fail("signature_present but artifacts/action_record.sig missing")
    if "artifacts/action_record.sigmeta.json" not in payload_map:
        return fail("signature_present but artifacts/action_record.sigmeta.json missing")
    if not receipt_pubkey:
        if require_signature:
            return fail("PUBKEY_MISSING")
        return 0
    try:
        sigmeta = json.loads(payload_map["artifacts/action_record.sigmeta.json"].decode("utf-8"))
    except Exception as e:
        return fail(f"malformed sigmeta json: {e}")
    if sigmeta.get("digest") != receipt_digest:
        return fail("sigmeta digest mismatch")
    sig = payload_map["artifacts/action_record.sig"].decode("utf-8").strip()
    ok = verify_digest_signature_with_key_input(receipt_digest, sig, receipt_pubkey)
    if not ok:
        return fail("SIGNATURE_INVALID")
    return 0


def _load_expected_pubkey_hex(pubkey_arg: str) -> str:
    if not pubkey_arg:
        return ""
    p = Path(pubkey_arg)
    if p.is_file():
        pub = edsig.load_public_key_pem(p)
        return edsig.raw_public_bytes_hex(pub)
    inline = pubkey_arg
    if inline.startswith("ed25519-pubhex:"):
        inline = inline.split(":", 1)[1]
    if len(inline) != 64:
        raise ValueError("expected 32-byte ed25519 pubkey hex")
    int(inline, 16)
    return inline.lower()


def _verify_signature_sidecars(
    bundle_path: Path,
    bundle_digest: str,
    require_signature: bool,
    pubkey_arg: str,
    sig_path_arg: str,
    sigmeta_path_arg: str,
) -> int:
    sig_path = Path(sig_path_arg) if sig_path_arg else Path(str(bundle_path) + ".sig")
    sigmeta_path = Path(sigmeta_path_arg) if sigmeta_path_arg else Path(str(bundle_path) + ".sigmeta.json")
    has_sig = sig_path.is_file()
    has_sigmeta = sigmeta_path.is_file()

    if not has_sig and not has_sigmeta:
        if require_signature:
            return fail("SIGNATURE_REQUIRED_MISSING", 1)
        return 0
    if not has_sig or not has_sigmeta:
        return fail("SIGNATURE_ARTIFACT_INCOMPLETE", 1)

    if require_signature and not pubkey_arg:
        return fail("SIGNATURE_REQUIRED_PUBKEY_MISSING", 1)

    try:
        expected_pubkey_hex = _load_expected_pubkey_hex(pubkey_arg) if pubkey_arg else ""
    except Exception:
        return fail("INVALID_EXPECTED_PUBKEY", 1)

    signature = sig_path.read_text(encoding="utf-8").strip()
    if not signature:
        return fail("SIGNATURE_EMPTY", 1)

    try:
        meta = json.loads(sigmeta_path.read_text(encoding="utf-8"))
    except Exception:
        return fail("SIGNATURE_META_MALFORMED", 1)
    if not isinstance(meta, dict):
        return fail("SIGNATURE_META_INVALID", 1)

    scheme = meta.get("signature_scheme")
    if scheme != "ed25519_attestation_bundle_v0":
        return fail("SIGNATURE_SCHEME_MISMATCH", 1)

    signer_pubkey = meta.get("signer_pubkey")
    if not isinstance(signer_pubkey, str) or len(signer_pubkey) != 64:
        return fail("SIGNER_PUBKEY_INVALID", 1)
    try:
        int(signer_pubkey, 16)
    except Exception:
        return fail("SIGNER_PUBKEY_INVALID", 1)

    if expected_pubkey_hex and signer_pubkey.lower() != expected_pubkey_hex:
        return fail("SIGNER_PUBKEY_MISMATCH", 1)

    if meta.get("bundle_digest") != bundle_digest:
        return fail("SIGNATURE_DIGEST_MISMATCH", 1)

    try:
        edsig.verify_signature(bundle_digest, signature, signer_pubkey.lower())
    except Exception:
        return fail("SIGNATURE_VERIFICATION_FAILED", 1)

    return 0


def verify_bundle(
    path: Path,
    receipt_pubkey: str = "",
    require_signature: bool = False,
    pubkey_arg: str = "",
    sig_path_arg: str = "",
    sigmeta_path_arg: str = "",
) -> int:
    try:
        manifest_raw, payload_member_map = _load_bundle(path)
    except ValueError as e:
        return _final(False, "BUNDLE_INVALID", [f"FAIL: {e}"], code=2)

    try:
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except Exception as e:
        return _final(False, "MANIFEST_INVALID", [f"FAIL: malformed manifest json: {e}"], code=1)

    if not isinstance(manifest, dict):
        return _final(False, "MANIFEST_INVALID", ["FAIL: manifest must be a JSON object"], code=1)
    manifest_sha = sha256_bytes(manifest_raw)
    bundle_id = "rab_" + manifest_sha.split(":", 1)[1]
    bundle_version = str(manifest.get("bundle_version", "NONE"))
    receipt_bundle_version = str(manifest.get("receipt_bundle_version", "NONE"))
    signature_verified_fail = "no" if require_signature else "not_required"
    signature_verified_success = "yes" if require_signature else "not_required"
    if manifest.get("bundle_version") != "attestation_bundle_v1":
        return _final(
            False,
            "MANIFEST_INVALID",
            ["FAIL: manifest bundle_version mismatch"],
            code=1,
            bundle_version=bundle_version,
            receipt_bundle_version=receipt_bundle_version,
            bundle_id=bundle_id,
            manifest_sha256=manifest_sha,
            signature_verified=signature_verified_fail,
        )
    if manifest.get("hash_algo") != HASH_ALGO:
        return _final(
            False,
            "MANIFEST_INVALID",
            ["FAIL: manifest hash_algo mismatch"],
            code=1,
            bundle_version=bundle_version,
            receipt_bundle_version=receipt_bundle_version,
            bundle_id=bundle_id,
            manifest_sha256=manifest_sha,
            signature_verified=signature_verified_fail,
        )
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return _final(
            False,
            "MANIFEST_INVALID",
            ["FAIL: manifest files must be a non-empty list"],
            code=1,
            bundle_version=bundle_version,
            receipt_bundle_version=receipt_bundle_version,
            bundle_id=bundle_id,
            manifest_sha256=manifest_sha,
            signature_verified=signature_verified_fail,
        )

    manifest_map = {}
    for entry in files:
        if not isinstance(entry, dict):
            return _final(
                False,
                "MANIFEST_INVALID",
                ["FAIL: manifest file entry must be object"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                signature_verified=signature_verified_fail,
            )
        p = entry.get("path")
        h = entry.get("sha256")
        sz = entry.get("size")
        if not isinstance(p, str) or not p or p.startswith("/") or ".." in p.split("/"):
            return _final(
                False,
                "MANIFEST_INVALID",
                [f"FAIL: invalid manifest path: {p!r}"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                signature_verified=signature_verified_fail,
            )
        if p in manifest_map:
            return _final(
                False,
                "MANIFEST_INVALID",
                [f"FAIL: duplicate manifest path: {p}"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                signature_verified=signature_verified_fail,
            )
        if not isinstance(h, str) or not h.startswith("sha256:"):
            return _final(
                False,
                "MANIFEST_INVALID",
                [f"FAIL: invalid sha256 for {p}"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                signature_verified=signature_verified_fail,
            )
        if not isinstance(sz, int) or sz < 0:
            return _final(
                False,
                "MANIFEST_INVALID",
                [f"FAIL: invalid size for {p}"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                signature_verified=signature_verified_fail,
            )
        manifest_map[p] = {"sha256": h, "size": sz}

    if "record.json" not in manifest_map:
        return _final(
            False,
            "MANIFEST_INVALID",
            ["FAIL: manifest missing record.json"],
            code=1,
            bundle_version=bundle_version,
            receipt_bundle_version=receipt_bundle_version,
            bundle_id=bundle_id,
            manifest_sha256=manifest_sha,
            signature_verified=signature_verified_fail,
        )
    for p in manifest_map:
        if p == "record.json":
            continue
        if not p.startswith("artifacts/"):
            return _final(
                False,
                "MANIFEST_INVALID",
                [f"FAIL: unexpected manifest path outside artifacts/: {p}"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                signature_verified=signature_verified_fail,
            )

    for rel in sorted(manifest_map):
        if rel in payload_member_map:
            continue
        if rel.startswith("artifacts/"):
            alt = "sig/" + rel[len("artifacts/") :]
            if alt in payload_member_map:
                continue
        return _final(
            False,
            "MISSING_FILE",
            [f"FAIL: manifest references missing bundle member: {rel}"],
            code=1,
            bundle_version=bundle_version,
            receipt_bundle_version=receipt_bundle_version,
            bundle_id=bundle_id,
            manifest_sha256=manifest_sha,
            signature_verified=signature_verified_fail,
        )
    for rel in sorted(payload_member_map):
        if rel.startswith("sig/"):
            rel_manifest = "artifacts/" + rel[len("sig/") :]
        else:
            rel_manifest = rel
        if rel_manifest not in manifest_map:
            return _final(
                False,
                "MANIFEST_INVALID",
                [f"FAIL: unexpected payload member not in manifest: {rel_manifest}"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                signature_verified=signature_verified_fail,
            )

    canonical_payload: dict[str, bytes] = {}
    files_checked = 0
    for rel in sorted(manifest_map):
        entry = manifest_map[rel]
        src_rel = rel
        if src_rel not in payload_member_map and src_rel.startswith("artifacts/"):
            alt = "sig/" + src_rel[len("artifacts/") :]
            if alt in payload_member_map:
                src_rel = alt
        data = payload_member_map[src_rel]
        canonical_payload[rel] = data
        if len(data) != entry["size"]:
            return _final(
                False,
                "SIZE_MISMATCH",
                [f"FAIL: size mismatch for {rel} (got={len(data)} expected={entry['size']})"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                files_checked=files_checked,
                signature_verified=signature_verified_fail,
            )
        got = sha256_bytes(data)
        if got != entry["sha256"]:
            return _final(
                False,
                "HASH_MISMATCH",
                [f"FAIL: hash mismatch for {rel} (got={got} expected={entry['sha256']})"],
                code=1,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                files_checked=files_checked,
                signature_verified=signature_verified_fail,
            )
        files_checked += 1

    rc = _validate_receipt_extension(
        manifest, canonical_payload, receipt_pubkey, require_signature=require_signature
    )
    if rc != 0:
        return _final(
            False,
            "RECEIPT_EXTENSION_INVALID",
            [],
            code=rc,
            bundle_version=bundle_version,
            receipt_bundle_version=receipt_bundle_version,
            bundle_id=bundle_id,
            manifest_sha256=manifest_sha,
            files_checked=files_checked,
            signature_verified=signature_verified_fail,
        )

    is_receipt_bundle = manifest.get("receipt_bundle_version") == "receipt_attestation_bundle_v0"
    should_verify_sidecars = path.is_file() and (
        bool(pubkey_arg)
        or bool(sig_path_arg)
        or bool(sigmeta_path_arg)
        or (require_signature and not is_receipt_bundle and not receipt_pubkey)
    )

    if should_verify_sidecars:
        bundle_digest = sha256_bytes(path.read_bytes())
        sig_rc = _verify_signature_sidecars(
            bundle_path=path,
            bundle_digest=bundle_digest,
            require_signature=require_signature,
            pubkey_arg=pubkey_arg,
            sig_path_arg=sig_path_arg,
            sigmeta_path_arg=sigmeta_path_arg,
        )
        if sig_rc != 0:
            return _final(
                False,
                "SIGNATURE_INVALID",
                [],
                code=sig_rc,
                bundle_version=bundle_version,
                receipt_bundle_version=receipt_bundle_version,
                bundle_id=bundle_id,
                manifest_sha256=manifest_sha,
                files_checked=files_checked,
                signature_verified="no" if require_signature else "not_required",
            )

    pass_lines: list[str] = []
    if path.is_file() and should_verify_sidecars:
        pass_lines.append("PASS: attestation bundle signature verified")
    pass_lines.append("PASS: attestation bundle manifest + payload hashes verified")
    return _final(
        True,
        "OK",
        pass_lines,
        code=0,
        bundle_version=bundle_version,
        receipt_bundle_version=receipt_bundle_version,
        bundle_id=bundle_id,
        manifest_sha256=manifest_sha,
        files_checked=files_checked,
        signature_verified=signature_verified_success,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify attestation bundle v1 manifest + payload hashes")
    ap.add_argument("bundle")
    ap.add_argument(
        "--receipt-pubkey", default="", help="PEM path or inline public key for receipt signature verification"
    )
    ap.add_argument("--require-signature", choices=["0", "1"], default="0")
    ap.add_argument("--pubkey", default="")
    ap.add_argument("--sig", default="")
    ap.add_argument("--sigmeta", default="")
    args = ap.parse_args()
    return verify_bundle(
        path=Path(args.bundle),
        receipt_pubkey=args.receipt_pubkey,
        require_signature=(args.require_signature == "1"),
        pubkey_arg=args.pubkey,
        sig_path_arg=args.sig,
        sigmeta_path_arg=args.sigmeta,
    )


if __name__ == "__main__":
    raise SystemExit(main())
