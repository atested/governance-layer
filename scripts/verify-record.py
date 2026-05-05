#!/usr/bin/env python3
import base64
import copy
import importlib.util
import json
import os
import sys
import hashlib
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from coverage_stamp import (
    SURFACE_ORDER,
    validate_coverage_stamp,
)
from event_model import (
    is_non_action_event,
    validate_compound_metadata,
    validate_non_action_event,
    verify_non_action_event_hash,
)

CAP_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "capabilities" / "capability-registry.json"
POLICY_EVAL_PATH = Path(__file__).resolve().with_name("policy-eval.py")

_REASON_ORDER_CACHE = None


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _signing_dev_mode_enabled() -> bool:
    return _env_flag("GOV_SIGNING_DEV_MODE")


def _signing_required_mode_enabled() -> bool:
    # H3: Signing is required by default.
    if _signing_dev_mode_enabled():
        return False
    explicit = os.environ.get("GOV_SIGNING_REQUIRED", "").strip().lower()
    if explicit in {"0", "false", "no", "off"}:
        return False
    return True


def _validate_signing_mode_flags():
    if _signing_dev_mode_enabled() and _signing_required_mode_enabled():
        return (
            2,
            ["FAIL: GOV_SIGNING_DEV_MODE=1 and GOV_SIGNING_REQUIRED=1 are mutually exclusive"],
        )
    return None

def compute_cap_registry_hash() -> str:
    data = CAP_REGISTRY_PATH.read_bytes()
    return "sha256:" + hashlib.sha256(data).hexdigest()

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

SIGNING_EXCLUDE_TOP_LEVEL = frozenset([
    "timestamp_utc",
    "session_id",
    "request_id",
    "process_id",
    # H1: prev_record_hash is NOW included in the signing preimage.
    "record_hash",
    "signature",
    "signing_key_id",
    "request_bytes_b64",
    "evidence_refs",
    "untrusted_inputs",
])

# Legacy set for verifying pre-H1 records (record_version "0.2").
SIGNING_EXCLUDE_TOP_LEVEL_LEGACY = frozenset([
    "timestamp_utc",
    "session_id",
    "request_id",
    "process_id",
    "prev_record_hash",
    "record_hash",
    "signature",
    "signing_key_id",
    "request_bytes_b64",
    "evidence_refs",
    "untrusted_inputs",
])


def _sanitize_expected_outputs_for_signing(expected_outputs):
    sanitized = []
    for item in expected_outputs or []:
        if not isinstance(item, dict):
            sanitized.append(item)
            continue
        cleaned = dict(item)
        ref = cleaned.get("ref")
        if isinstance(ref, str) and ref.endswith(":path") and "value" in cleaned:
            cleaned["value"] = "<path-redacted>"
        sanitized.append(cleaned)
    return sanitized


def signing_preimage_payload(rec: dict, exclude_set: frozenset = None) -> str:
    if exclude_set is None:
        exclude_set = SIGNING_EXCLUDE_TOP_LEVEL
    unsigned = copy.deepcopy(rec)
    for key in exclude_set:
        unsigned.pop(key, None)

    if isinstance(unsigned.get("policy_reasons"), list):
        unsigned["policy_reasons"] = [
            {"code": r.get("code")} if isinstance(r, dict) else r
            for r in unsigned["policy_reasons"]
        ]

    if isinstance(unsigned.get("tool_args_redacted"), dict):
        unsigned["tool_args_redacted"].pop("path", None)
        unsigned["tool_args_redacted"].pop("canonical_path", None)

    if isinstance(unsigned.get("policy_inputs"), dict):
        unsigned["policy_inputs"].pop("canonical_path", None)
        unsigned["policy_inputs"].pop("allow_base_dirs", None)

    if isinstance(unsigned.get("normalized_args"), dict):
        for key in ("canonical_path", "canonical_src_path", "canonical_dst_path"):
            unsigned["normalized_args"].pop(key, None)

    if isinstance(unsigned.get("intent"), dict):
        unsigned["intent"]["expected_outputs"] = _sanitize_expected_outputs_for_signing(
            unsigned["intent"].get("expected_outputs", [])
        )

    return canonical_json(unsigned)


def legacy_record_hash_payload(rec: dict) -> str:
    unsigned = dict(rec)
    unsigned["record_hash"] = None
    unsigned["signature"] = None
    return canonical_json(unsigned)


def _load_reason_order():
    global _REASON_ORDER_CACHE
    if _REASON_ORDER_CACHE is not None:
        return _REASON_ORDER_CACHE, None
    try:
        spec = importlib.util.spec_from_file_location("policy_eval_impl", POLICY_EVAL_PATH)
        if spec is None or spec.loader is None:
            return None, f"FAIL: unable to load REASON_ORDER from {POLICY_EVAL_PATH}"
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        reason_order = getattr(mod, "REASON_ORDER", None)
    except Exception as e:
        return None, f"FAIL: unable to load REASON_ORDER from {POLICY_EVAL_PATH}: {e}"
    if not isinstance(reason_order, list) or not all(isinstance(c, str) for c in reason_order):
        return None, "FAIL: REASON_ORDER is missing or invalid in policy-eval.py"
    _REASON_ORDER_CACHE = list(reason_order)
    return _REASON_ORDER_CACHE, None


def _verify_reason_code_order(rec: dict):
    reason_order, err = _load_reason_order()
    if err:
        return 2, [err]

    reasons = rec.get("policy_reasons")
    if not isinstance(reasons, list):
        return 1, ["FAIL: policy_reasons missing or invalid (expected list)"]

    rank = {code: i for i, code in enumerate(reason_order)}
    seen = set()
    actual_codes = []
    last_rank = -1

    for i, item in enumerate(reasons):
        if not isinstance(item, dict):
            return 1, [f"FAIL: policy_reasons[{i}] invalid (expected object)"]
        code = item.get("code")
        if not isinstance(code, str) or not code:
            return 1, [f"FAIL: policy_reasons[{i}].code missing or invalid"]
        if code not in rank:
            return 1, [f"FAIL: policy_reasons[{i}].code unknown for REASON_ORDER: {code}"]
        if code in seen:
            return 1, [f"FAIL: duplicate policy reason code: {code}"]
        seen.add(code)
        actual_codes.append(code)
        code_rank = rank[code]
        if code_rank < last_rank:
            expected_codes = [c for c in reason_order if c in seen]
            return 1, [
                "FAIL: policy_reasons reason_code order mismatch (expected REASON_ORDER)",
                f" expected: {expected_codes}",
                f" actual:   {actual_codes}",
            ]
        last_rank = code_rank

    return 0, []


def _coverage_required_from_env() -> bool:
    return os.environ.get("GOV_COVERAGE_STAMP_REQUIRED", "0") == "1"


def _render_coverage_summary(coverage) -> list[str]:
    lines = ["Coverage Summary"]
    lines.append("coverage_stamp_version=coverage_stamp_v1")
    normalized = coverage.normalized
    if normalized is None:
        lines.append(
            f"overall_status={coverage.overall_status} reason_code={coverage.reason_code}"
        )
        return lines

    surface_map = {s["surface_id"]: s for s in normalized["surfaces"]}
    for sid in SURFACE_ORDER:
        if sid not in surface_map:
            continue
        cov = surface_map[sid]["coverage"]
        status = "complete" if (cov["observation"] and cov["enforcement"] and cov["provenance"]) else "partial"
        lines.append(
            "surface_id={sid} observation={obs} enforcement={enf} provenance={prov} status={status}".format(
                sid=sid,
                obs=int(cov["observation"]),
                enf=int(cov["enforcement"]),
                prov=int(cov["provenance"]),
                status=status,
            )
        )
    lines.append(
        f"overall_status={normalized['overall_status']} reason_code={coverage.reason_code}"
    )
    return lines


def _b64url_decode_nopad(s: str) -> bytes:
    if any(ch.isspace() for ch in s):
        raise ValueError("whitespace not allowed")
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def _load_crypto():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (
            Ed25519PrivateKey,
            Ed25519PublicKey,
        )
    except Exception as e:
        return None, None, None, None, f"cryptography unavailable: {e}"
    return InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, None


def _load_verify_public_key():
    InvalidSignature, serialization, Ed25519PrivateKey, Ed25519PublicKey, crypto_err = _load_crypto()
    if crypto_err:
        return None, None, None, f"FAIL: {crypto_err}"

    verify_path = os.environ.get("GOV_VERIFY_KEY_PATH")
    signing_path = os.environ.get("GOV_SIGNING_KEY_PATH")

    if verify_path:
        try:
            raw = Path(verify_path).read_bytes()
        except OSError as e:
            return None, None, None, f"FAIL: unable to read GOV_VERIFY_KEY_PATH '{verify_path}': {e}"
        try:
            pub = serialization.load_pem_public_key(raw)
        except Exception as e:
            return None, None, None, f"FAIL: invalid public key PEM at GOV_VERIFY_KEY_PATH: {e}"
        if not isinstance(pub, Ed25519PublicKey):
            return None, None, None, "FAIL: GOV_VERIFY_KEY_PATH is not an Ed25519 public key"
        return pub, serialization, InvalidSignature, None

    if signing_path:
        try:
            raw = Path(signing_path).read_bytes()
        except OSError as e:
            return None, None, None, f"FAIL: unable to read GOV_SIGNING_KEY_PATH '{signing_path}': {e}"
        try:
            priv = serialization.load_pem_private_key(raw, password=None)
        except Exception as e:
            return None, None, None, f"FAIL: invalid private key PEM at GOV_SIGNING_KEY_PATH: {e}"
        if not isinstance(priv, Ed25519PrivateKey):
            return None, None, None, "FAIL: GOV_SIGNING_KEY_PATH is not an Ed25519 private key"
        return priv.public_key(), serialization, InvalidSignature, None

    return None, None, None, (
        "FAIL: signed record requires GOV_VERIFY_KEY_PATH (or GOV_SIGNING_KEY_PATH for dev convenience)"
    )


def _public_key_thumbprint_key_id(pub, serialization) -> str:
    raw = pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return "ed25519:" + hashlib.sha256(raw).hexdigest()


def _verify_signature_if_present(rec: dict):
    sig = rec.get("signature")
    key_id = rec.get("signing_key_id")

    if sig is None and key_id is None:
        if _signing_required_mode_enabled():
            return 1, ["FAIL: unsigned record rejected in GOV_SIGNING_REQUIRED=1 mode"], False
        return 0, [], False

    if sig is None or key_id is None:
        return 1, ["FAIL: signature/signing_key_id present but incomplete"], False

    if not isinstance(sig, str) or not sig:
        return 1, ["FAIL: signature missing or invalid"], False
    if not isinstance(key_id, str) or not key_id:
        return 1, ["FAIL: signing_key_id missing or invalid"], False
    if len(key_id) > 128 or any(ch.isspace() or ord(ch) < 32 for ch in key_id):
        return 1, ["FAIL: signing_key_id has invalid format"], False

    pub, serialization, InvalidSignature, key_load_err = _load_verify_public_key()
    if key_load_err:
        return 2, [key_load_err], False

    expected_key_id = _public_key_thumbprint_key_id(pub, serialization)
    if key_id != expected_key_id:
        return 1, [
            "FAIL: signing_key_id mismatch",
            f" expected: {expected_key_id}",
            f" actual:   {key_id}",
        ], False

    try:
        sig_bytes = _b64url_decode_nopad(sig)
    except Exception as e:
        return 1, [f"FAIL: signature is not valid base64url: {e}"], False

    if len(sig_bytes) != 64:
        return 1, [f"FAIL: signature length invalid (got {len(sig_bytes)} bytes, want 64)"], False

    preimage = signing_preimage_payload(rec).encode("utf-8")
    try:
        pub.verify(sig_bytes, preimage)
    except InvalidSignature:
        return 1, ["FAIL: signature verification failed"], False
    except Exception as e:
        return 2, [f"FAIL: signature verification error: {e}"], False

    return 0, [], True


def _verify_compound_metadata_if_present(rec: dict):
    """Validate compound_metadata if present. Returns (exit_code, output_lines)."""
    compound_meta = rec.get("compound_metadata")
    if compound_meta is None:
        return 0, []
    ok, err = validate_compound_metadata(compound_meta)
    if not ok:
        return 1, [f"FAIL: {err}"]
    return 0, []


def verify_non_action_event_dict(rec: dict):
    """Verify a non-action governance event record. Returns (exit_code, output_lines)."""
    ok, err = validate_non_action_event(rec)
    if not ok:
        return 1, [f"FAIL: {err}"]

    hash_ok, hash_err = verify_non_action_event_hash(rec)
    if not hash_ok:
        return 1, [f"FAIL: {hash_err}"]

    return 0, ["PASS: non-action event verified"]


def _verify_v2_mediated_decision(rec: dict):
    """Verify a v2 mediated_decision record. Returns (exit_code, output_lines)."""
    # v2 records use a simpler hash: sha256 of the record with record_hash=None.
    # Signed records also have signature and signing_key_id fields that must be
    # nulled for hash computation (they are null at hash time, populated after).
    expected = rec.get("record_hash")
    if not isinstance(expected, str) or not expected.startswith("sha256:"):
        return 1, ["FAIL: record_hash missing or invalid"]

    hashable = dict(rec)
    hashable["record_hash"] = None
    # Null out signature fields for hash computation — signed records had
    # these set to None when the hash was originally computed.
    if "signature" in hashable:
        hashable["signature"] = None
    if "signing_key_id" in hashable:
        hashable["signing_key_id"] = None
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    actual = "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if actual != expected:
        return 1, [
            "FAIL: v2 record_hash mismatch",
            f" expected: {expected}",
            f" actual:   {actual}",
        ]

    # Validate required fields.
    for field in ("classification", "policy_decision", "matched_rule", "original_tool"):
        if field not in rec:
            return 1, [f"FAIL: v2 record missing required field: {field}"]

    # Verify Ed25519 signature if present (mixed chain: unsigned old + signed new).
    # For v2 records, we do NOT enforce GOV_SIGNING_REQUIRED — pre-dispatch
    # records have no signature fields. Only validate when a non-null signature
    # is actually present.
    sig_val = rec.get("signature")
    key_id_val = rec.get("signing_key_id")
    if sig_val is not None or key_id_val is not None:
        # At least one signing field is non-null — validate properly.
        sig_rc, sig_lines, did_verify_signature = _verify_signature_if_present(rec)
        if sig_rc != 0:
            return sig_rc, sig_lines
        if did_verify_signature:
            return 0, ["PASS: v2 mediated_decision record_hash + signature verified"]

    return 0, ["PASS: v2 mediated_decision record verified"]


def verify_record_dict(
    rec: dict,
    require_coverage_stamp: Optional[bool] = None,
    check_cap_registry_hash: bool = True,
):
    """Return (exit_code, output_lines)."""

    # Non-action events use a separate verification path.
    if is_non_action_event(rec):
        return verify_non_action_event_dict(rec)

    # v2 mediated_decision records use a separate verification path.
    if rec.get("record_version") == "2.0" and rec.get("record_type") == "mediated_decision":
        return _verify_v2_mediated_decision(rec)

    mode_err = _validate_signing_mode_flags()
    if mode_err is not None:
        return mode_err

    if require_coverage_stamp is None:
        require_coverage_stamp = _coverage_required_from_env()

    coverage = validate_coverage_stamp(rec.get("coverage_stamp"), required=require_coverage_stamp)
    if not coverage.ok:
        return 1, [f"FAIL: {coverage.reason_code} ({coverage.message})"]

    # Validate compound_metadata if present (additive extension).
    cm_rc, cm_lines = _verify_compound_metadata_if_present(rec)
    if cm_rc != 0:
        return cm_rc, cm_lines

    # Verify cap_registry_hash when checking against the live registry surface.
    got_cap_hash = rec.get("cap_registry_hash")
    if not got_cap_hash:
        return 2, ["FAIL: missing cap_registry_hash"]
    if check_cap_registry_hash:
        expected_cap_hash = compute_cap_registry_hash()
        if got_cap_hash != expected_cap_hash:
            return 2, [f"FAIL: cap_registry_hash mismatch (got={got_cap_hash}, expected={expected_cap_hash})"]

    # Verify request_hash against embedded request bytes (if present — older records omit it).
    # C4: record_version 0.3+ omits request_bytes_b64 but retains request_hash.
    got_request_hash = rec.get("request_hash")
    got_b64 = rec.get("request_bytes_b64")
    if got_b64 is not None and got_request_hash is not None:
        # Both present: verify consistency (v0.2 records).
        if not got_request_hash.startswith("sha256:"):
            return 2, ["FAIL: request_hash has unexpected format"]
        try:
            raw = base64.b64decode(got_b64)
        except Exception as e:
            return 2, [f"FAIL: request_bytes_b64 not valid base64: {e}"]
        recomputed = "sha256:" + hashlib.sha256(raw).hexdigest()
        if recomputed != got_request_hash:
            return 2, [f"FAIL: request_hash mismatch (got={got_request_hash}, recomputed={recomputed})"]
    elif got_b64 is not None and got_request_hash is None:
        return 2, ["FAIL: request_bytes_b64 present without request_hash"]

    order_rc, order_lines = _verify_reason_code_order(rec)
    if order_rc != 0:
        return order_rc, order_lines

    expected = rec.get("record_hash")
    if not isinstance(expected, str) or not expected.startswith("sha256:"):
        return 1, ["FAIL: record_hash missing or invalid"]

    actual = "sha256:" + sha256_hex(signing_preimage_payload(rec))
    if actual != expected:
        # H1 backward compat: try legacy preimage that excluded prev_record_hash
        legacy_h1 = "sha256:" + sha256_hex(
            signing_preimage_payload(rec, exclude_set=SIGNING_EXCLUDE_TOP_LEVEL_LEGACY))
        legacy_actual = "sha256:" + sha256_hex(legacy_record_hash_payload(rec))
        if legacy_h1 != expected and legacy_actual != expected:
            return 1, [
                "FAIL: record_hash mismatch",
                f" expected: {expected}",
                f" actual:   {actual}",
                f" legacy:   {legacy_actual}",
            ]

    sig_rc, sig_lines, did_verify_signature = _verify_signature_if_present(rec)
    if sig_rc != 0:
        return sig_rc, sig_lines

    if did_verify_signature:
        return 0, _render_coverage_summary(coverage) + ["PASS: record_hash + signature verified"]

    lines = _render_coverage_summary(coverage)
    if _signing_dev_mode_enabled():
        lines.append("WARN: unsigned record accepted in explicit GOV_SIGNING_DEV_MODE=1 compatibility mode")
    lines.append("PASS: record_hash verified")
    return 0, lines

def main():
    if len(sys.argv) != 2:
        print("Usage: verify-record.py <decision-record.json>", file=sys.stderr)
        sys.exit(2)

    p = sys.argv[1]
    with open(p, "r", encoding="utf-8") as f:
        rec = json.load(f)
    rc, lines = verify_record_dict(rec)
    for line in lines:
        print(line)
    sys.exit(rc)

if __name__ == "__main__":
    main()
