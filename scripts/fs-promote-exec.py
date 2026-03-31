#!/usr/bin/env python3
"""fs-promote-exec.py — FS_PROMOTE bounded execution layer.

Implements EPIC_PROMOTION.md guarded workflow steps 8–10:
  8. Execute bounded copy+verify (copy bytes, re-hash destination, compare hashes).
  9. Emit completion record with destination hash/path metadata (INV-PROMO-005).
 10. Re-verify chain and fail closed on any integrity anomaly.

Usage:
  fs-promote-exec.py <decision_record.json>

The decision record must be a policy_decision=ALLOW record for FS_PROMOTE
emitted by policy-eval.py.

Exit codes:
  0 — promotion executed and completion record emitted successfully.
  1 — promotion failed (src missing, dst hash mismatch); completion record emitted.
  2 — chain integrity failure or precondition violation; no completion record emitted.

Environment variables (standard):
  GOV_ACTOR            — actor identity string for the completion record.
  GOV_SESSION_ID       — session identifier; auto-generated if absent.
  GOV_PROMO_TEST_DST_CORRUPTION=1
                       — inject a byte corruption into the destination after
                         copy, for testing INV-PROMO-004 fail-closed behaviour.
                         NEVER set in production.
"""

import base64
import copy
import hashlib
import importlib.util
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

CAP_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "capabilities" / "capability-registry.json"
VERIFY_RECORD_PATH = SCRIPT_DIR / "verify-record.py"

# Reason codes used in completion records.  Must be present in REASON_ORDER in
# policy-eval.py so that verify-record.py accepts records that contain them.
RC_PROMO_SRC_MISSING = "RC-PROMO-SRC-MISSING"
RC_PROMO_HASH_MISMATCH_SRC = "RC-PROMO-HASH-MISMATCH-SRC"
RC_PROMO_HASH_MISMATCH_DST = "RC-PROMO-HASH-MISMATCH-DST"
RC_PROMO_CHAIN_VERIFY_FAIL = "RC-PROMO-CHAIN-VERIFY-FAIL"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def load_cap_registry_hash() -> str:
    raw = CAP_REGISTRY_PATH.read_bytes()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Signing-preimage and record-hash logic (must match verify-record.py exactly)
# ---------------------------------------------------------------------------

SIGNING_EXCLUDE_TOP_LEVEL = frozenset([
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


def signing_preimage_payload(record: dict) -> str:
    unsigned = copy.deepcopy(record)
    for key in SIGNING_EXCLUDE_TOP_LEVEL:
        unsigned.pop(key, None)
    if isinstance(unsigned.get("policy_reasons"), list):
        unsigned["policy_reasons"] = [
            {"code": r.get("code")} if isinstance(r, dict) else r
            for r in unsigned["policy_reasons"]
        ]
    if isinstance(unsigned.get("normalized_args"), dict):
        for key in ("canonical_path", "canonical_src_path", "canonical_dst_path"):
            unsigned["normalized_args"].pop(key, None)
    return canonical_json(unsigned)


def compute_record_hash(record: dict) -> str:
    payload = signing_preimage_payload(record)
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Load verify-record module for decision-record chain pre-check
# ---------------------------------------------------------------------------

_verify_record_mod = None


def _load_verify_record_mod():
    global _verify_record_mod
    if _verify_record_mod is not None:
        return _verify_record_mod
    spec = importlib.util.spec_from_file_location("verify_record_impl", VERIFY_RECORD_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load verify-record module from {VERIFY_RECORD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _verify_record_mod = mod
    return mod


def verify_decision_record(rec: dict) -> tuple:
    """Return (ok, message).  Verifies record_hash only (no cap-registry staleness check)."""
    try:
        mod = _load_verify_record_mod()
    except Exception as e:
        return False, f"verify-record module unavailable: {e}"
    rc, lines = mod.verify_record_dict(
        rec,
        require_coverage_stamp=False,
        check_cap_registry_hash=False,
    )
    return rc == 0, " | ".join(lines) if lines else ""


# ---------------------------------------------------------------------------
# Completion record helpers
# ---------------------------------------------------------------------------

def build_completion_record(
    *,
    cap_registry_hash: str,
    session_id: str,
    request_id: str,
    actor: str,
    promotion_id: str,
    decision_record_hash: str,
    canonical_dst_path: str,
    dst_content_hash_sha256: str,
    src_content_hash_sha256: str,
    dst_hash_verified: bool,
    completion_outcome: str,
    policy_reasons: list,
) -> dict:
    return {
        "record_version": "0.2",
        "record_type": "promotion_completion",
        "cap_registry_hash": cap_registry_hash,
        "timestamp_utc": now_utc_z(),
        "session_id": session_id,
        "request_id": request_id,
        "actor": actor,
        "tool": "FS_PROMOTE",
        "promotion_id": promotion_id,
        "decision_record_hash": decision_record_hash,
        "canonical_dst_path": canonical_dst_path,
        "dst_content_hash_sha256": dst_content_hash_sha256,
        "src_content_hash_sha256": src_content_hash_sha256,
        "dst_hash_verified": dst_hash_verified,
        "completion_outcome": completion_outcome,
        "policy_reasons": policy_reasons,
        "prev_record_hash": decision_record_hash,
        "record_hash": None,
        "signature": None,
        "signing_key_id": None,
    }


def emit_completion_record(record: dict) -> None:
    """Compute record_hash, perform chain re-verify (step 10), then print JSON."""
    record["record_hash"] = compute_record_hash(record)

    # Step 10: chain re-verify — round-trip through JSON serialization and recompute.
    try:
        round_tripped = json.loads(json.dumps(record, ensure_ascii=False))
    except Exception as e:
        print(
            f"FATAL: {RC_PROMO_CHAIN_VERIFY_FAIL} — JSON round-trip failed: {e}",
            file=sys.stderr,
        )
        sys.exit(2)

    recomputed = compute_record_hash(round_tripped)
    if recomputed != record["record_hash"]:
        print(
            f"FATAL: {RC_PROMO_CHAIN_VERIFY_FAIL} — record_hash mismatch after round-trip "
            f"(expected={record['record_hash']!r}, got={recomputed!r})",
            file=sys.stderr,
        )
        sys.exit(2)

    print(json.dumps(record, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------------
# Main execution flow
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 2:
        print("Usage: fs-promote-exec.py <decision_record.json>", file=sys.stderr)
        sys.exit(2)

    decision_path = sys.argv[1]

    # Load decision record.
    try:
        with open(decision_path, "r", encoding="utf-8") as f:
            decision_rec = json.load(f)
    except Exception as e:
        print(f"FATAL: cannot read decision record: {e}", file=sys.stderr)
        sys.exit(2)

    # Step 10 (pre-exec): verify decision record chain integrity.
    ok, msg = verify_decision_record(decision_rec)
    if not ok:
        print(
            f"FATAL: {RC_PROMO_CHAIN_VERIFY_FAIL} — decision record_hash invalid; "
            f"operation aborted ({msg})",
            file=sys.stderr,
        )
        sys.exit(2)

    # Validate tool and decision.
    if decision_rec.get("tool") != "FS_PROMOTE":
        print(
            f"FATAL: decision record tool={decision_rec.get('tool')!r}, expected FS_PROMOTE",
            file=sys.stderr,
        )
        sys.exit(2)

    if decision_rec.get("policy_decision") != "ALLOW":
        print(
            f"FATAL: policy_decision={decision_rec.get('policy_decision')!r}; "
            "FS_PROMOTE execution requires ALLOW",
            file=sys.stderr,
        )
        sys.exit(2)

    # Extract required fields from the decision record.
    norm = decision_rec.get("normalized_args", {})
    canonical_src = norm.get("canonical_src_path")
    canonical_dst = norm.get("canonical_dst_path")
    promotion_id = norm.get("promotion_id", "")
    decision_record_hash = decision_rec.get("record_hash", "")
    cap_registry_hash = decision_rec.get("cap_registry_hash") or load_cap_registry_hash()

    if not canonical_src or not canonical_dst:
        print(
            "FATAL: decision record missing canonical_src_path or canonical_dst_path "
            "in normalized_args",
            file=sys.stderr,
        )
        sys.exit(2)

    # Extract declared source hash from original request bytes (TOCTOU re-check).
    declared_src_hash: str = ""
    try:
        raw_req = base64.b64decode(decision_rec["request_bytes_b64"])
        req_obj = json.loads(raw_req.decode("utf-8"))
        declared_src_hash = str(req_obj.get("intent", {}).get("src_content_hash_sha256", ""))
    except Exception:
        # Not fatal — we still verify dst==src below.
        pass

    # Runtime identifiers.
    session_id = os.environ.get("GOV_SESSION_ID", f"sess-{uuid.uuid4()}")
    request_id = str(uuid.uuid4())
    actor = os.environ.get("GOV_ACTOR", "unknown")

    def _completion(**kwargs):
        return build_completion_record(
            cap_registry_hash=cap_registry_hash,
            session_id=session_id,
            request_id=request_id,
            actor=actor,
            promotion_id=promotion_id,
            decision_record_hash=decision_record_hash,
            canonical_dst_path=canonical_dst,
            **kwargs,
        )

    # -----------------------------------------------------------------------
    # Step 8a: Read source bytes and compute source hash.
    # -----------------------------------------------------------------------
    src_path = Path(canonical_src)
    if not src_path.exists() or not src_path.is_file():
        completion = _completion(
            dst_content_hash_sha256="",
            src_content_hash_sha256="",
            dst_hash_verified=False,
            completion_outcome="FAIL_SRC_MISSING",
            policy_reasons=[{
                "code": RC_PROMO_SRC_MISSING,
                "detail": f"Source not found or not a regular file at execution time: {canonical_src}",
            }],
        )
        emit_completion_record(completion)
        sys.exit(1)

    try:
        src_bytes = src_path.read_bytes()
    except OSError as e:
        completion = _completion(
            dst_content_hash_sha256="",
            src_content_hash_sha256="",
            dst_hash_verified=False,
            completion_outcome="FAIL_SRC_MISSING",
            policy_reasons=[{
                "code": RC_PROMO_SRC_MISSING,
                "detail": f"Source unreadable at execution time: {e}",
            }],
        )
        emit_completion_record(completion)
        sys.exit(1)

    src_hash = "sha256:" + sha256_bytes(src_bytes)

    # TOCTOU re-check: source must still match the hash approved at policy-eval time.
    if declared_src_hash and src_hash != declared_src_hash:
        completion = _completion(
            dst_content_hash_sha256="",
            src_content_hash_sha256=src_hash,
            dst_hash_verified=False,
            completion_outcome="FAIL_SRC_HASH_MISMATCH",
            policy_reasons=[{
                "code": RC_PROMO_HASH_MISMATCH_SRC,
                "detail": (
                    f"Source hash changed between policy-eval and execution: "
                    f"declared={declared_src_hash!r} actual={src_hash!r}"
                ),
            }],
        )
        emit_completion_record(completion)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 8b: Bounded atomic copy — write to temp file then rename.
    # -----------------------------------------------------------------------
    dst_path = Path(canonical_dst)
    try:
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_dst = dst_path.with_name(dst_path.name + ".promote_tmp")
        tmp_dst.write_bytes(src_bytes)
        tmp_dst.rename(dst_path)
    except OSError as e:
        print(f"FATAL: copy to destination failed: {e}", file=sys.stderr)
        sys.exit(2)

    # Test hook: inject a byte corruption into the destination to exercise the
    # INV-PROMO-004 fail-closed path.  Never triggered in production.
    if _env_flag("GOV_PROMO_TEST_DST_CORRUPTION"):
        try:
            corrupted = src_bytes + b"\x00"
            dst_path.write_bytes(corrupted)
        except OSError:
            pass

    # -----------------------------------------------------------------------
    # Step 8c: Re-hash destination bytes (INV-PROMO-004).
    # -----------------------------------------------------------------------
    try:
        dst_bytes = dst_path.read_bytes()
    except OSError as e:
        print(f"FATAL: cannot read destination after copy: {e}", file=sys.stderr)
        sys.exit(2)

    dst_hash = "sha256:" + sha256_bytes(dst_bytes)

    # -----------------------------------------------------------------------
    # Step 8d: Compare src_hash == dst_hash (INV-PROMO-004 enforcement).
    # -----------------------------------------------------------------------
    if dst_hash != src_hash:
        completion = _completion(
            dst_content_hash_sha256=dst_hash,
            src_content_hash_sha256=src_hash,
            dst_hash_verified=False,
            completion_outcome="FAIL_DST_HASH_MISMATCH",
            policy_reasons=[{
                "code": RC_PROMO_HASH_MISMATCH_DST,
                "detail": (
                    f"Destination hash does not match source after copy "
                    f"(INV-PROMO-004 violated): src={src_hash!r} dst={dst_hash!r}"
                ),
            }],
        )
        emit_completion_record(completion)
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Step 9: Emit success completion record (INV-PROMO-005).
    # -----------------------------------------------------------------------
    completion = _completion(
        dst_content_hash_sha256=dst_hash,
        src_content_hash_sha256=src_hash,
        dst_hash_verified=True,
        completion_outcome="PROMOTED",
        policy_reasons=[],
    )
    emit_completion_record(completion)
    sys.exit(0)


if __name__ == "__main__":
    main()
