#!/usr/bin/env python3
import base64
import json
import os
import sys
import uuid
import hashlib
import copy
from datetime import datetime, timezone
from pathlib import Path
from base64 import urlsafe_b64encode

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from coverage_stamp import (
    COVERAGE_REASON_MALFORMED,
    COVERAGE_REASON_MISSING,
    COVERAGE_REASON_OK,
    COVERAGE_REASON_ORDER_INVALID,
    COVERAGE_REASON_PARTIAL,
    COVERAGE_REASON_SURFACE_UNKNOWN,
    COVERAGE_REASON_VERSION_UNSUPPORTED,
    validate_coverage_stamp,
)
from messaging_surface import (
    contains_content_fields,
    find_mapping_entry,
    load_messaging_map,
    parse_nonnegative_int,
)


CAP_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "capabilities" / "capability-registry.json"
REPO_ROOT = Path(__file__).resolve().parents[1]
HOT_FILE_PATHS = frozenset(
    [
        "system/scripts/release-gate.sh",
        "system/scripts/validate-proof-bundle.sh",
        "system/scripts/codex-unattended.sh",
        "docs/dev/WORK_QUEUE.md",
        "docs/dev/ASSIGNMENTS.md",
    ]
)

cryptography_missing_error = "FATAL: cryptography module required for signing but not installed"


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def signing_dev_mode_enabled() -> bool:
    return _env_flag("GOV_SIGNING_DEV_MODE")


def signing_required_mode_enabled() -> bool:
    return _env_flag("GOV_SIGNING_REQUIRED")


def validate_signing_mode_flags() -> None:
    if signing_dev_mode_enabled() and signing_required_mode_enabled():
        print(
            "FATAL: GOV_SIGNING_DEV_MODE=1 and GOV_SIGNING_REQUIRED=1 are mutually exclusive",
            file=sys.stderr,
        )
        sys.exit(2)

def _default_signing_key_path() -> Path:
    home = Path(os.environ.get("HOME", Path.home()))
    return home / ".config" / "gov-layer" / "signing.key"


def _b64url_encode_nopad(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _load_ed25519_private_key_from_pem(path: Path, source_label: str):
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, None, f"FATAL: signing key unreadable ({source_label}): {path}"
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
    except ModuleNotFoundError:
        return None, None, cryptography_missing_error
    try:
        priv = serialization.load_pem_private_key(raw, password=None)
    except ValueError:
        return None, None, f"FATAL: signing key invalid PEM ({source_label}): {path}"
    if not isinstance(priv, Ed25519PrivateKey):
        return None, None, f"FATAL: signing key is not Ed25519 ({source_label}): {path}"
    pub = priv.public_key()
    raw_pub = pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
    key_id = "ed25519:" + hashlib.sha256(raw_pub).hexdigest()
    return priv, key_id, None

def load_signing_private_key():
    validate_signing_mode_flags()
    env_path = os.environ.get("GOV_SIGNING_KEY_PATH")
    if env_path:
        priv, key_id, err = _load_ed25519_private_key_from_pem(Path(env_path), "GOV_SIGNING_KEY_PATH")
        if err or priv:
            return priv, key_id, err
    default_path = _default_signing_key_path()
    if default_path.exists():
        priv, key_id, err = _load_ed25519_private_key_from_pem(default_path, "~/.config/gov-layer/signing.key")
        if err or priv:
            return priv, key_id, err
    return None, None, None
def load_internal_registry() -> tuple:
    """Load capability registry from the fixed internal path.
    Returns (raw_bytes, registry_dict, cap_registry_hash).
    Fails closed on any error.
    """
    try:
        raw = CAP_REGISTRY_PATH.read_bytes()
    except OSError as e:
        print(f"FATAL: capability-registry.json unreadable: {e}", file=sys.stderr)
        sys.exit(2)
    h = "sha256:" + hashlib.sha256(raw).hexdigest()
    try:
        reg = json.loads(raw.decode("utf-8"))
    except Exception as e:
        print(f"FATAL: capability-registry.json invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)
    return raw, reg, h

RC_UNKNOWN_TOOL = "RC-UNKNOWN-TOOL"
RC_PATH_DISALLOWED = "RC-FS-PATH-DISALLOWED"
RC_HIDDEN_PATH = "RC-FS-HIDDEN-PATH"
RC_PATH_TRAVERSAL = "RC-FS-PATH-TRAVERSAL"
RC_OVERWRITE_DISALLOWED = "RC-FS-OVERWRITE-DISALLOWED"
RC_EXECUTABLE_DISALLOWED = "RC-FS-EXECUTABLE-DISALLOWED"
RC_NOT_A_DIRECTORY = "RC-FS-NOT-A-DIRECTORY"
RC_INCLUDE_HIDDEN_DISALLOWED = "RC-FS-INCLUDE-HIDDEN-DISALLOWED"
RC_NOT_A_FILE = "RC-FS-NOT-A-FILE"
RC_MAX_BYTES_EXCEEDED = "RC-FS-MAX-BYTES-EXCEEDED"
RC_MISSING_INTENT_FIELDS = "RC-FS-MISSING-INTENT-FIELDS"
RC_CROSS_ROOT_DISALLOWED = "RC-FS-CROSS-ROOT-DISALLOWED"
RC_RECURSIVE_DISALLOWED = "RC-FS-RECURSIVE-DISALLOWED"
RC_PROMO_ROOT_PAIR_DISALLOWED = "RC-PROMO-ROOT-PAIR-DISALLOWED"
RC_PROMO_SRC_MISSING = "RC-PROMO-SRC-MISSING"
RC_PROMO_SRC_TYPE_DISALLOWED = "RC-PROMO-SRC-TYPE-DISALLOWED"
RC_PROMO_HASH_MISMATCH_SRC = "RC-PROMO-HASH-MISMATCH-SRC"
RC_PROMO_HASH_MISMATCH_DST = "RC-PROMO-HASH-MISMATCH-DST"
RC_PROMO_ARTIFACT_CLASS_DISALLOWED = "RC-PROMO-ARTIFACT-CLASS-DISALLOWED"
RC_PROMO_OVERWRITE_DISALLOWED = "RC-PROMO-OVERWRITE-DISALLOWED"
RC_PROMO_PATH_DISALLOWED = "RC-PROMO-PATH-DISALLOWED"
RC_PROMO_CHAIN_VERIFY_FAIL = "RC-PROMO-CHAIN-VERIFY-FAIL"
RC_MSG_UNKNOWN_SURFACE_BINDING = "RC-MSG-UNKNOWN-SURFACE-BINDING"
RC_MSG_MAPPING_VERSION_MISMATCH = "RC-MSG-MAPPING-VERSION-MISMATCH"
RC_MSG_CAPABILITY_MAPPING_MISMATCH = "RC-MSG-CAPABILITY-MAPPING-MISMATCH"
RC_MSG_CANONICAL_DESTINATION_MISSING = "RC-MSG-CANONICAL-DESTINATION-MISSING"
RC_MSG_CANONICAL_DESTINATION_KIND_MISMATCH = "RC-MSG-CANONICAL-DESTINATION-KIND-MISMATCH"
RC_MSG_RAW_DESTINATION_MISSING = "RC-MSG-RAW-DESTINATION-MISSING"
RC_MSG_OPAQUE_PAYLOAD_MISSING = "RC-MSG-OPAQUE-PAYLOAD-MISSING"
RC_MSG_CONTENT_FIELD_PRESENT = "RC-MSG-CONTENT-FIELD-PRESENT"
RC_MSG_REPLY_CONTEXT_MISSING = "RC-MSG-REPLY-CONTEXT-MISSING"
RC_MSG_REPLY_TARGET_MISMATCH = "RC-MSG-REPLY-TARGET-MISMATCH"
RC_MSG_DECISION_ALPHABET_VIOLATION = "RC-MSG-DECISION-ALPHABET-VIOLATION"
RC_MSG_MISSING_INTENT_FIELDS = "RC-MSG-MISSING-INTENT-FIELDS"
RC_MSG_DESTINATION_DISALLOWED = "RC-MSG-DESTINATION-DISALLOWED"
RC_MSG_DESTINATION_CLASS_DISALLOWED = "RC-MSG-DESTINATION-CLASS-DISALLOWED"
RC_MSG_TRANSPORT_UNAUTHORIZED = "RC-MSG-TRANSPORT-UNAUTHORIZED"
RC_MSG_PAYLOAD_SIZE_EXCEEDED = "RC-MSG-PAYLOAD-SIZE-EXCEEDED"
RC_MSG_RATE_EXCEEDED = "RC-MSG-RATE-EXCEEDED"
REASON_PATH_TRAVERSAL = "PATH_TRAVERSAL"
REASON_OUTSIDE_ALLOWED_ROOT = "OUTSIDE_ALLOWED_ROOT"
REASON_TARGET_IS_HOT_FILE = "TARGET_IS_HOT_FILE"
REASON_IS_EXECUTABLE = "IS_EXECUTABLE"
REASON_SRC_MISSING = "SRC_MISSING"
REASON_DEST_EXISTS = "DEST_EXISTS"
REASON_OVERWRITE_FORBIDDEN = "OVERWRITE_FORBIDDEN"
REASON_UNKNOWN = "UNKNOWN"

REASON_ORDER = [
    COVERAGE_REASON_MISSING,
    COVERAGE_REASON_MALFORMED,
    COVERAGE_REASON_VERSION_UNSUPPORTED,
    COVERAGE_REASON_SURFACE_UNKNOWN,
    COVERAGE_REASON_ORDER_INVALID,
    COVERAGE_REASON_PARTIAL,
    COVERAGE_REASON_OK,
    RC_MISSING_INTENT_FIELDS,
    RC_MSG_MISSING_INTENT_FIELDS,
    RC_UNKNOWN_TOOL,
    RC_MSG_UNKNOWN_SURFACE_BINDING,
    RC_MSG_MAPPING_VERSION_MISMATCH,
    RC_MSG_CAPABILITY_MAPPING_MISMATCH,
    RC_MSG_CANONICAL_DESTINATION_MISSING,
    RC_MSG_CANONICAL_DESTINATION_KIND_MISMATCH,
    RC_MSG_DESTINATION_CLASS_DISALLOWED,
    RC_MSG_DESTINATION_DISALLOWED,
    RC_MSG_RAW_DESTINATION_MISSING,
    RC_MSG_OPAQUE_PAYLOAD_MISSING,
    RC_MSG_TRANSPORT_UNAUTHORIZED,
    RC_MSG_PAYLOAD_SIZE_EXCEEDED,
    RC_MSG_RATE_EXCEEDED,
    RC_MSG_REPLY_CONTEXT_MISSING,
    RC_MSG_REPLY_TARGET_MISMATCH,
    RC_MSG_CONTENT_FIELD_PRESENT,
    RC_MSG_DECISION_ALPHABET_VIOLATION,
    REASON_PATH_TRAVERSAL,
    REASON_OUTSIDE_ALLOWED_ROOT,
    REASON_TARGET_IS_HOT_FILE,
    REASON_IS_EXECUTABLE,
    REASON_SRC_MISSING,
    REASON_DEST_EXISTS,
    REASON_OVERWRITE_FORBIDDEN,
    REASON_UNKNOWN,
    RC_PATH_TRAVERSAL,
    RC_PATH_DISALLOWED,
    RC_CROSS_ROOT_DISALLOWED,
    RC_HIDDEN_PATH,
    RC_INCLUDE_HIDDEN_DISALLOWED,
    RC_MAX_BYTES_EXCEEDED,
    RC_OVERWRITE_DISALLOWED,
    RC_RECURSIVE_DISALLOWED,
    RC_EXECUTABLE_DISALLOWED,
    RC_NOT_A_DIRECTORY,
    RC_NOT_A_FILE,
    RC_PROMO_ROOT_PAIR_DISALLOWED,
    RC_PROMO_SRC_MISSING,
    RC_PROMO_SRC_TYPE_DISALLOWED,
    RC_PROMO_HASH_MISMATCH_SRC,
    RC_PROMO_HASH_MISMATCH_DST,
    RC_PROMO_ARTIFACT_CLASS_DISALLOWED,
    RC_PROMO_OVERWRITE_DISALLOWED,
    RC_PROMO_PATH_DISALLOWED,
    RC_PROMO_CHAIN_VERIFY_FAIL,
]
MESSAGING_CAPABILITY_CLASSES = frozenset(("MSG_SEND", "MSG_REPLY"))

def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_prefixed_from_canonical(obj) -> str:
    return "sha256:" + sha256_hex(canonical_json(obj))


def _extract_reason_codes(record: dict) -> list:
    codes = []
    for r in record.get("policy_reasons", []):
        if isinstance(r, dict) and "code" in r:
            codes.append(r.get("code"))
    return codes


def _manifest_normalized_args(record: dict) -> dict:
    # Exclude path-bearing normalized args so manifest stays path-free and portable.
    normalized_args = record.get("normalized_args")
    if not isinstance(normalized_args, dict):
        return {}
    sanitized = dict(normalized_args)
    for key in ("canonical_path", "canonical_src_path", "canonical_dst_path"):
        sanitized.pop(key, None)
    return sanitized


def build_manifest_from_record(record: dict) -> dict:
    """Deterministic, path-free build manifest derived from stable record fields."""
    reason_codes = _extract_reason_codes(record)
    return {
        "cap_registry_hash": record.get("cap_registry_hash"),
        "capability_class": record.get("capability_class"),
        "manifest_version": "0.1",
        "messaging_map_hash": record.get("messaging_map_hash"),
        "normalized_args_hash": _sha256_prefixed_from_canonical(_manifest_normalized_args(record)),
        "policy_decision": record.get("policy_decision"),
        "reason_codes": reason_codes,
        "request_hash": record.get("request_hash"),
        "tool": record.get("tool"),
    }


def maybe_write_build_manifest(record: dict) -> None:
    out_path = os.environ.get("GOV_BUILD_MANIFEST_PATH")
    if not out_path:
        return
    manifest = build_manifest_from_record(record)
    try:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(canonical_json(manifest) + "\n", encoding="utf-8")
    except OSError as e:
        print(f"FATAL: cannot write build manifest: {e}", file=sys.stderr)
        sys.exit(2)

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


def signing_preimage_payload(record: dict) -> str:
    # Stable preimage excludes volatile metadata and machine-specific path expansions.
    unsigned = copy.deepcopy(record)
    for key in SIGNING_EXCLUDE_TOP_LEVEL:
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

def load_json(p: str):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def is_hidden_segment(path: Path) -> bool:
    return any(part.startswith(".") and part not in (".", "..") for part in path.parts)

def canonicalize(p: str) -> Path:
    return Path(p).expanduser().resolve(strict=False)

def under_base(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        # On case-insensitive filesystems, shell-provided roots can differ in path
        # casing from Python-resolved request paths. Fall back to a case-folded
        # prefix check there so allowed-root enforcement reflects the actual mount.
        if sys.platform == "darwin":
            path_s = str(path).rstrip("/")
            base_s = str(base).rstrip("/")
            path_folded = path_s.casefold()
            base_folded = base_s.casefold()
            return path_folded == base_folded or path_folded.startswith(base_folded + "/")
        return False


def resolve_allow_base_dirs(base_dirs: list) -> list:
    resolved = []
    for base in base_dirs:
        value = str(base)
        value = value.replace(
            "__GOV_CANONICAL_REPO_PATH__",
            os.environ.get("GOV_CANONICAL_REPO_PATH", "__GOV_CANONICAL_REPO_PATH__"),
        )
        value = value.replace(
            "__GOV_RUNTIME_PATH__",
            os.environ.get("GOV_RUNTIME_PATH", "__GOV_RUNTIME_PATH__"),
        )
        resolved.append(value)
    return resolved


def _is_allow_deny_only(values) -> bool:
    return isinstance(values, list) and values == ["ALLOW", "DENY"]


def _all_prefixes_match(value: str, prefixes: list[str]) -> bool:
    return any(value == prefix or value.startswith(prefix) for prefix in prefixes)


def is_hot_file_target(path: Path) -> bool:
    try:
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return False
    return rel in HOT_FILE_PATHS

def is_executable_file(path: Path) -> bool:
    try:
        if not path.is_file():
            return False
        return bool(path.stat().st_mode & 0o111)
    except OSError:
        return False
def add_reason(decision: dict, code: str, detail: str) -> None:
    # Deduplicate by code; keep the first detail for that code.
    existing = {r["code"] for r in decision["policy_reasons"]}
    if code not in existing:
        decision["policy_reasons"].append({"code": code, "detail": detail})

def finalize_reasons(decision: dict) -> None:
    # Order reasons according to fixed precedence.
    by_code = {r["code"]: r for r in decision["policy_reasons"]}
    ordered = []
    for c in REASON_ORDER:
        if c in by_code:
            ordered.append(by_code[c])
    decision["policy_reasons"] = ordered

def eval_fs_path_policy(canonical_path: str, allowlist: list, deny_hidden: bool = True, deny_traversal: bool = True):
    """
    Shared deterministic FS path policy.
    Returns (decision, reasons) where decision is "ALLOW"/"DENY" and reasons is list of {code,detail}.
    """
    reasons = []

    # Traversal detection (defense in depth; canonical_path should already be normalized)
    if deny_traversal and ("../" in canonical_path or "/.." in canonical_path):
        reasons.append({"code": RC_PATH_TRAVERSAL, "detail": {"canonical_path": canonical_path}})

    # Hidden path detection: any segment starting with '.' (excluding root)
    if deny_hidden:
        parts = [p for p in canonical_path.split("/") if p]
        if any(seg.startswith(".") for seg in parts):
            reasons.append({"code": RC_HIDDEN_PATH, "detail": {"canonical_path": canonical_path}})

    # Allowlist base path check
    allowed = False
    for base in allowlist:
        if canonical_path == base or canonical_path.startswith(base.rstrip("/") + "/"):
            allowed = True
            break
    if not allowed:
        reasons.append({"code": RC_PATH_DISALLOWED, "detail": {"canonical_path": canonical_path}})

    decision = "DENY" if reasons else "ALLOW"
    return decision, reasons

def eval_fs_read(intent: dict, tool_meta: dict):
    """Evaluate FS_READ policy."""
    args = intent.get("args", {})
    expected = intent.get("expected_outputs", [])

    # Extract path from args or expected_outputs
    path = args.get("path")
    if not path and expected:
        for out in expected:
            if out.get("ref") == "file:path":
                path = out.get("value")
                break

    if not path:
        return "DENY", [{"code": RC_MISSING_INTENT_FIELDS, "detail": {"missing": ["args.path"]}}]

    # max_bytes handling
    hard = int(tool_meta.get("max_bytes_hard", 65536))
    default = int(tool_meta.get("max_bytes_default", 4096))
    try:
        max_bytes = int(args.get("max_bytes", default))
    except Exception:
        max_bytes = default
    if max_bytes < 1:
        max_bytes = 1
    if max_bytes > hard:
        return "DENY", [{"code": RC_MAX_BYTES_EXCEEDED, "detail": {"max_bytes": max_bytes, "hard": hard}}]

    # Canonicalize path
    canon = canonicalize(path)
    canon_s = str(canon)

    # Get policy config
    allowlist = tool_meta.get("allow_base_dirs", [])
    deny_hidden = bool(tool_meta.get("deny_hidden_paths", True))
    deny_traversal = bool(tool_meta.get("deny_traversal", True))

    # Apply path policy
    decision, reasons = eval_fs_path_policy(
        canonical_path=canon_s,
        allowlist=allowlist,
        deny_hidden=deny_hidden,
        deny_traversal=deny_traversal,
    )
    if decision != "ALLOW":
        return decision, reasons

    # Check if it's a file (deterministic policy check)
    if not os.path.isfile(canon_s):
        return "DENY", [{"code": RC_NOT_A_FILE, "detail": {"canonical_path": canon_s}}]

    return "ALLOW", []

def main():
    validate_signing_mode_flags()
    # Accept 1 arg (intent) or 2 args (legacy: registry intent).
    # Registry is ALWAYS loaded internally from CAP_REGISTRY_PATH; argv[1] is ignored.
    caller_registry_path = None
    if len(sys.argv) == 2:
        intent_path = sys.argv[1]
    elif len(sys.argv) == 3:
        # Legacy callers pass registry path as argv[1]; ignore it for enforcement,
        # but record it as an untrusted steering attempt for audit.
        caller_registry_path = sys.argv[1]
        intent_path = sys.argv[2]
    else:
        print("Usage: policy-eval.py <intent.json>", file=sys.stderr)
        sys.exit(2)

    # Internal registry load: raw bytes → hash → parse (single read, consistent).
    _raw_reg, reg, cap_registry_hash = load_internal_registry()

    # Request binding: read as raw bytes, hash before parse (guarantees hash matches what was evaluated).
    try:
        raw_request = Path(intent_path).read_bytes()
    except OSError as e:
        print(f"FATAL: cannot read intent file: {e}", file=sys.stderr)
        sys.exit(2)
    request_hash = "sha256:" + hashlib.sha256(raw_request).hexdigest()
    request_bytes_b64 = base64.b64encode(raw_request).decode("ascii")
    try:
        obj = json.loads(raw_request.decode("utf-8"))
    except Exception as e:
        print(f"FATAL: intent file invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)

    tool = obj.get("tool")
    args = obj.get("args", {})
    intent = obj.get("intent", {})
    constraints = intent.get("constraints", {}) if isinstance(intent.get("constraints"), dict) else {}
    coverage_required = os.environ.get("GOV_COVERAGE_STAMP_REQUIRED", "0") == "1" or bool(
        constraints.get("require_coverage_stamp", False)
    )
    raw_coverage_stamp = obj.get("coverage_stamp")
    if raw_coverage_stamp is None:
        raw_coverage_stamp = constraints.get("coverage_stamp")
    coverage_validation = validate_coverage_stamp(raw_coverage_stamp, required=coverage_required)

    # Detect and flag untrusted inputs (never used for enforcement).
    untrusted_inputs = []
    if "cap_cfg" in obj:
        untrusted_inputs.append("cap_cfg")
    if caller_registry_path is not None:
        untrusted_inputs.append({
            "cap_registry_path_arg": caller_registry_path,
            "note": "ignored; enforcement uses internal registry only",
        })

    # Actor/session
    actor = os.environ.get("GOV_ACTOR", "unknown")
    session_id = os.environ.get("GOV_SESSION_ID", f"sess-{uuid.uuid4()}")
    request_id = str(uuid.uuid4())
    process_id = hashlib.sha256(f"{session_id}:{request_id}:process".encode("utf-8")).hexdigest()[:16]
    prev_record_hash = os.environ.get("GOV_PREV_RECORD_HASH")

    # Tool lookup
    tool_meta = None
    for t in reg.get("tools", []):
        if t.get("tool") == tool:
            tool_meta = t
            break

    capability_class = tool_meta.get("capability_class") if tool_meta else None

    # Required intent fields
    missing_intent = (not intent.get("goal")) or (not intent.get("expected_outputs"))

    # Content hash (do not embed raw content)
    content = args.get("content", "")
    if isinstance(content, str):
        content_hash = f"sha256:{sha256_bytes(content.encode('utf-8'))}"
    elif isinstance(content, (bytes, bytearray)):
        content_hash = f"sha256:{sha256_bytes(bytes(content))}"
    else:
        content_hash = "sha256:0"

    raw_path = args.get("path", "")
    canon = None
    canon_s = None
    if isinstance(raw_path, str) and raw_path:
        canon = canonicalize(raw_path)
        canon_s = str(canon)

    # Start building decision record
    record = {
        "record_version": "0.2",
        "record_type": "pass_decision",
        "cap_registry_hash": cap_registry_hash,
        "request_hash": request_hash,
        "request_bytes_b64": request_bytes_b64,
        "timestamp_utc": now_utc_z(),
        "session_id": session_id,
        "request_id": request_id,
        "process_id": process_id,
        "actor": actor,
        "tool": tool,
        "capability_class": capability_class,
        "intent": {
            "goal": intent.get("goal"),
            "constraints": intent.get("constraints", {}),
            "requested_action": intent.get("requested_action"),
            "expected_outputs": intent.get("expected_outputs", []),
        },
        "policy_inputs": {},
        "normalized_args": {},
        "policy_decision": "DENY",
        "policy_reasons": [],
        "coverage_stamp_summary": {
            "coverage_stamp_version": "coverage_stamp_v1",
            "overall_status": coverage_validation.overall_status,
            "reason_code": coverage_validation.reason_code,
            "required": coverage_required,
        },
        "tool_args_redacted": {
            "path": raw_path if isinstance(raw_path, str) else None,
            "canonical_path": canon_s,
            "content_hash": content_hash,
            "overwrite": bool(args.get("overwrite", False)),
            "request_executable": bool(args.get("request_executable", False)),
        },
        "untrusted_inputs": untrusted_inputs,
        "evidence_refs": [],
        "prev_record_hash": prev_record_hash,
        "record_hash": None,
        "signature": None,
        "signing_key_id": None,
    }
    if coverage_validation.normalized is not None:
        record["coverage_stamp"] = coverage_validation.normalized

    # Policy evaluation begins

    if not coverage_validation.ok:
        add_reason(record, coverage_validation.reason_code, coverage_validation.message)

    if tool_meta is None or capability_class is None:
        add_reason(record, RC_UNKNOWN_TOOL, f"Tool '{tool}' not registered in capability registry.")
        finalize_reasons(record)
        emit_record(record)
        return

    if capability_class in MESSAGING_CAPABILITY_CLASSES:
        if missing_intent:
            add_reason(
                record,
                RC_MSG_MISSING_INTENT_FIELDS,
                "Missing required intent.goal or intent.expected_outputs.",
            )
        try:
            _raw_map, messaging_map, messaging_map_hash = load_messaging_map()
        except OSError as exc:
            add_reason(record, RC_MSG_UNKNOWN_SURFACE_BINDING, f"messaging map unreadable: {exc}")
            finalize_reasons(record)
            emit_record(record)
            return
        except Exception as exc:
            add_reason(record, RC_MSG_UNKNOWN_SURFACE_BINDING, f"messaging map invalid: {exc}")
            finalize_reasons(record)
            emit_record(record)
            return

        record["governed_surface"] = "messaging_proof_surface.v1"
        record["messaging_map_hash"] = messaging_map_hash

        surface_binding_id = str(args.get("surface_binding_id", ""))
        mapping_version = str(args.get("mapping_version", ""))
        canonical_destination = (
            args.get("canonical_destination")
            if isinstance(args.get("canonical_destination"), dict)
            else {}
        )
        raw_destination_input = (
            args.get("raw_destination_input")
            if isinstance(args.get("raw_destination_input"), dict)
            else {}
        )
        opaque_payload = args.get("opaque_payload") if isinstance(args.get("opaque_payload"), dict) else {}
        reply_context = args.get("reply_context") if isinstance(args.get("reply_context"), dict) else {}
        audit_scope = args.get("audit_scope") if isinstance(args.get("audit_scope"), dict) else {}

        mapping_entry = find_mapping_entry(messaging_map, surface_binding_id)
        if mapping_entry is None:
            add_reason(record, RC_MSG_UNKNOWN_SURFACE_BINDING, "surface_binding_id not present in messaging map.")
            mapping_entry = {}

        requested_decisions = mapping_entry.get("allowed_decisions") if mapping_entry else None
        if mapping_entry and not _is_allow_deny_only(requested_decisions):
            add_reason(
                record,
                RC_MSG_DECISION_ALPHABET_VIOLATION,
                "messaging bindings must expose ALLOW/DENY only.",
            )

        if mapping_entry and str(mapping_entry.get("mapping_version", "")) != mapping_version:
            add_reason(
                record,
                RC_MSG_MAPPING_VERSION_MISMATCH,
                "mapping_version does not match authoritative messaging binding.",
            )

        if mapping_entry and str(mapping_entry.get("capability_class", "")) != capability_class:
            add_reason(
                record,
                RC_MSG_CAPABILITY_MAPPING_MISMATCH,
                "capability_class does not match surface binding.",
            )

        canonical_kind = str(canonical_destination.get("kind", ""))
        canonical_id = str(canonical_destination.get("id", ""))
        if not canonical_kind or not canonical_id:
            add_reason(
                record,
                RC_MSG_CANONICAL_DESTINATION_MISSING,
                "canonical_destination.kind and canonical_destination.id are required.",
            )
        elif mapping_entry and canonical_kind != str(mapping_entry.get("canonical_destination_kind", "")):
            add_reason(
                record,
                RC_MSG_CANONICAL_DESTINATION_KIND_MISMATCH,
                "canonical_destination.kind does not match mapped destination kind.",
            )

        raw_destination_kind = str(raw_destination_input.get("kind", ""))
        raw_destination_value = str(raw_destination_input.get("value", ""))
        if not raw_destination_kind or not raw_destination_value:
            add_reason(
                record,
                RC_MSG_RAW_DESTINATION_MISSING,
                "raw_destination_input.kind and raw_destination_input.value are required.",
            )

        payload_handle = str(opaque_payload.get("payload_handle", ""))
        payload_transport = str(opaque_payload.get("transport", ""))
        payload_byte_length = parse_nonnegative_int(opaque_payload.get("byte_length"), default=-1)
        if not payload_handle or not payload_transport or payload_byte_length < 0:
            add_reason(
                record,
                RC_MSG_OPAQUE_PAYLOAD_MISSING,
                "opaque_payload.payload_handle, transport, and byte_length are required.",
            )

        if contains_content_fields(args):
            add_reason(
                record,
                RC_MSG_CONTENT_FIELD_PRESENT,
                "content-bearing evaluator-facing fields are prohibited on messaging surface.",
            )
            record["request_bytes_b64"] = None

        if mapping_entry:
            allowed_raw_destination_kinds = mapping_entry.get("allowed_raw_destination_kinds", [])
            if raw_destination_kind and isinstance(allowed_raw_destination_kinds, list):
                if raw_destination_kind not in allowed_raw_destination_kinds:
                    add_reason(
                        record,
                        RC_MSG_DESTINATION_CLASS_DISALLOWED,
                        "raw destination class is not allowed for the selected surface binding.",
                    )

            allowed_prefixes = mapping_entry.get("allowed_canonical_destination_prefixes", [])
            if canonical_id and isinstance(allowed_prefixes, list) and not _all_prefixes_match(canonical_id, allowed_prefixes):
                add_reason(
                    record,
                    RC_MSG_DESTINATION_DISALLOWED,
                    "canonical destination identity is outside the allowed surface scope.",
                )

            allowed_transports = mapping_entry.get("allowed_transports", [])
            if payload_transport and isinstance(allowed_transports, list) and payload_transport not in allowed_transports:
                add_reason(
                    record,
                    RC_MSG_TRANSPORT_UNAUTHORIZED,
                    "payload transport is not authorized for the selected surface binding.",
                )

            max_payload_bytes = parse_nonnegative_int(mapping_entry.get("max_payload_bytes"), default=0)
            if max_payload_bytes and payload_byte_length > max_payload_bytes:
                add_reason(
                    record,
                    RC_MSG_PAYLOAD_SIZE_EXCEEDED,
                    f"opaque payload byte_length exceeds max_payload_bytes={max_payload_bytes}.",
                )

            max_rate_window_count = parse_nonnegative_int(mapping_entry.get("max_rate_window_count"), default=0)
            rate_window_count = parse_nonnegative_int(audit_scope.get("rate_window_count"), default=0)
            if max_rate_window_count and rate_window_count > max_rate_window_count:
                add_reason(
                    record,
                    RC_MSG_RATE_EXCEEDED,
                    f"rate_window_count exceeds max_rate_window_count={max_rate_window_count}.",
                )
        else:
            rate_window_count = parse_nonnegative_int(audit_scope.get("rate_window_count"), default=0)
            max_payload_bytes = 0
            max_rate_window_count = 0

        if capability_class == "MSG_REPLY":
            reply_target_kind = str(reply_context.get("reply_target_kind", ""))
            reply_target_id = str(reply_context.get("reply_target_id", ""))
            if not reply_target_kind or not reply_target_id:
                add_reason(
                    record,
                    RC_MSG_REPLY_CONTEXT_MISSING,
                    "reply_context.reply_target_kind and reply_context.reply_target_id are required.",
                )
            elif reply_target_id != canonical_id:
                add_reason(
                    record,
                    RC_MSG_REPLY_TARGET_MISMATCH,
                    "reply_context.reply_target_id must match canonical_destination.id.",
                )
        else:
            reply_target_kind = ""
            reply_target_id = ""

        record["tool_args_redacted"] = {
            "surface_binding_id": surface_binding_id,
            "mapping_version": mapping_version,
            "canonical_destination_kind": canonical_kind or None,
            "canonical_destination_id": canonical_id or None,
            "raw_destination_input_kind": raw_destination_kind or None,
            "raw_destination_input_value": raw_destination_value or None,
            "opaque_payload_handle": payload_handle or None,
            "opaque_payload_transport": payload_transport or None,
            "opaque_payload_byte_length": payload_byte_length if payload_byte_length >= 0 else None,
            "rate_window_count": rate_window_count,
        }
        record["policy_inputs"] = {
            "surface_binding_id": surface_binding_id,
            "mapping_version": mapping_version,
            "messaging_map_hash": messaging_map_hash,
            "canonical_destination": {
                "kind": canonical_kind,
                "id": canonical_id,
            },
            "decision_alphabet": ["ALLOW", "DENY"],
            "content_visible_to_evaluator": False,
            "allowed_transport": (
                str(mapping_entry.get("allowed_transports", [""])[0])
                if mapping_entry and isinstance(mapping_entry.get("allowed_transports"), list) and mapping_entry.get("allowed_transports")
                else ""
            ),
            "max_payload_bytes": max_payload_bytes,
            "max_rate_window_count": max_rate_window_count,
        }
        record["normalized_args"] = {
            "surface_binding_id": surface_binding_id,
            "mapping_version": mapping_version,
            "canonical_destination_kind": canonical_kind or None,
            "canonical_destination_id": canonical_id or None,
            "raw_destination_input_kind": raw_destination_kind or None,
            "raw_destination_input_value": raw_destination_value or None,
            "opaque_payload_handle": payload_handle or None,
            "opaque_payload_transport": payload_transport or None,
            "opaque_payload_byte_length": payload_byte_length if payload_byte_length >= 0 else None,
            "rate_window_count": rate_window_count,
        }
        if capability_class == "MSG_REPLY":
            record["normalized_args"]["reply_target_kind"] = reply_target_kind or None
            record["normalized_args"]["reply_target_id"] = reply_target_id or None

        finalize_reasons(record)
        if not record["policy_reasons"]:
            record["policy_decision"] = "ALLOW"
        emit_record(record)
        return

    if missing_intent:
        add_reason(record, RC_MISSING_INTENT_FIELDS, "Missing required intent.goal or intent.expected_outputs.")

    # Populate policy_inputs from capability registry and normalized request
    allow_base_dirs = resolve_allow_base_dirs(tool_meta.get("allow_base_dirs", []))
    deny_hidden = bool(tool_meta.get("deny_hidden_paths", True))
    deny_overwrite_default = bool(tool_meta.get("deny_overwrite_by_default", True))
    deny_exec = bool(tool_meta.get("deny_executable_outputs", True))

    overwrite_intent = bool(intent.get("constraints", {}).get("overwrite", False))
    overwrite_requested = bool(args.get("overwrite", False))
    request_executable = bool(args.get("request_executable", False))

    record["policy_inputs"] = {
        "canonical_path": canon_s,
        "allow_base_dirs": allow_base_dirs,
        "deny_hidden_paths": deny_hidden,
        "deny_overwrite_by_default": deny_overwrite_default,
        "deny_executable_outputs": deny_exec,
        "overwrite_intent": overwrite_intent,
        "overwrite_requested": overwrite_requested,
        "request_executable": request_executable,
    }

    # Normalized args: canonical post-normalization values actually submitted to enforcement checks.
    norm = {"canonical_path": canon_s}
    if capability_class == "FS_WRITE":
        norm["overwrite_requested"] = overwrite_requested
        norm["overwrite_intent"] = overwrite_intent
        norm["request_executable"] = request_executable
    elif capability_class == "FS_LIST":
        _max_e_hard = int(tool_meta.get("caps", {}).get("max_entries_hard", 500))
        _max_e_default = int(tool_meta.get("caps", {}).get("max_entries_default", 100))
        try:
            _raw_max_e = int(args.get("max_entries", _max_e_default))
        except Exception:
            _raw_max_e = _max_e_default
        norm["max_entries"] = min(max(_raw_max_e, 1), _max_e_hard)
        norm["include_hidden"] = bool(args.get("include_hidden", False))
    elif capability_class == "FS_READ":
        _hard_b = int(tool_meta.get("max_bytes_hard", 65536))
        _default_b = int(tool_meta.get("max_bytes_default", 4096))
        try:
            _raw_mb = int(args.get("max_bytes", _default_b))
        except Exception:
            _raw_mb = _default_b
        if _raw_mb < 1:
            _raw_mb = 1
        norm["max_bytes"] = _raw_mb
        norm["max_bytes_hard"] = _hard_b
        try:
            norm["offset"] = max(0, int(args.get("offset", 0)))
        except Exception:
            norm["offset"] = 0
        norm["as_text"] = bool(args.get("as_text", True))
    elif capability_class == "FS_MKDIR":
        norm["parents"] = bool(args.get("parents", False))
        norm["exist_ok"] = bool(args.get("exist_ok", False))
    elif capability_class == "FS_MOVE":
        _raw_src = str(args.get("src_path", ""))
        _raw_dst = str(args.get("dst_path", ""))
        norm = {
            "canonical_src_path": str(canonicalize(_raw_src)) if _raw_src else None,
            "canonical_dst_path": str(canonicalize(_raw_dst)) if _raw_dst else None,
            "overwrite_requested": bool(args.get("overwrite", False)),
        }
    elif capability_class == "FS_DELETE":
        norm = {
            "canonical_path": canon_s,
            "recursive_requested": bool(args.get("recursive", False)),
        }
    elif capability_class == "FS_DELETE_NONEXEC":
        norm = {
            "canonical_path": canon_s,
        }
    elif capability_class == "FS_COPY":
        _raw_src = str(args.get("src_path", ""))
        _raw_dst = str(args.get("dst_path", ""))
        norm = {
            "canonical_src_path": str(canonicalize(_raw_src)) if _raw_src else None,
            "canonical_dst_path": str(canonicalize(_raw_dst)) if _raw_dst else None,
            "overwrite_requested": bool(args.get("overwrite", False)),
            "recursive_requested": bool(args.get("recursive", False)),
        }
    elif capability_class == "FS_PROMOTE":
        _raw_src = str(args.get("src_path", ""))
        _raw_dst = str(args.get("dst_path", ""))
        norm = {
            "canonical_src_path": str(canonicalize(_raw_src)) if _raw_src else None,
            "canonical_dst_path": str(canonicalize(_raw_dst)) if _raw_dst else None,
            "src_root_id": str(intent.get("src_root_id", "")),
            "dst_root_id": str(intent.get("dst_root_id", "")),
            "promotion_id": str(intent.get("promotion_id", "")),
            "allowed_artifact_class": str(intent.get("allowed_artifact_class", "")),
            "overwrite_requested": bool(args.get("overwrite", False)),
        }
    record["normalized_args"] = norm

    # FS_MOVE: dual-path enforcement (src_path + dst_path instead of single path)
    if capability_class == "FS_MOVE":
        raw_src = str(args.get("src_path", ""))
        raw_dst = str(args.get("dst_path", ""))
        if not raw_src or not raw_dst:
            add_reason(record, RC_PATH_DISALLOWED, "FS_MOVE requires non-empty src_path and dst_path.")
            finalize_reasons(record)
            emit_record(record)
            return

        if ".." in Path(raw_src).parts:
            add_reason(record, REASON_PATH_TRAVERSAL, "Traversal attempt in src_path.")
        if ".." in Path(raw_dst).parts:
            add_reason(record, REASON_PATH_TRAVERSAL, "Traversal attempt in dst_path.")

        canon_src = canonicalize(raw_src)
        canon_dst = canonicalize(raw_dst)
        canon_src_s = str(canon_src)
        canon_dst_s = str(canon_dst)

        if deny_hidden and is_hidden_segment(canon_src):
            add_reason(record, RC_HIDDEN_PATH, f"Hidden path segment in src_path: {canon_src_s}")
        if deny_hidden and is_hidden_segment(canon_dst):
            add_reason(record, RC_HIDDEN_PATH, f"Hidden path segment in dst_path: {canon_dst_s}")

        src_allowed = False
        dst_allowed = False
        src_root_idx = None
        dst_root_idx = None
        for _i, _base_s in enumerate(allow_base_dirs):
            _base = canonicalize(_base_s)
            if src_root_idx is None and under_base(canon_src, _base):
                src_allowed = True
                src_root_idx = _i
            if dst_root_idx is None and under_base(canon_dst, _base):
                dst_allowed = True
                dst_root_idx = _i
        if not src_allowed or not dst_allowed:
            add_reason(record, REASON_OUTSIDE_ALLOWED_ROOT,
                       "src_path or dst_path not under allowlisted base directories.")
        if is_hot_file_target(canon_dst):
            add_reason(record, REASON_TARGET_IS_HOT_FILE, "dst_path targets hot file.")

        _move_caps = tool_meta.get("caps", {})
        if not bool(_move_caps.get("cross_root_allowed", False)):
            if src_allowed and dst_allowed and src_root_idx != dst_root_idx:
                add_reason(record, RC_CROSS_ROOT_DISALLOWED,
                           f"Cross-root move disallowed (src root {src_root_idx} != dst root {dst_root_idx}).")

        if not bool(_move_caps.get("overwrite_allowed", False)):
            if bool(args.get("overwrite", False)):
                add_reason(record, RC_OVERWRITE_DISALLOWED,
                           "overwrite is not permitted: caps.overwrite_allowed=false.")

        finalize_reasons(record)
        if not record["policy_reasons"]:
            record["policy_decision"] = "ALLOW"
        emit_record(record)
        return

    # FS_DELETE_NONEXEC: single-path enforcement, rejects executable files.
    if capability_class == "FS_DELETE_NONEXEC":
        raw_nonexec_path = str(args.get("path", ""))
        if not raw_nonexec_path:
            add_reason(record, RC_PATH_DISALLOWED, "FS_DELETE_NONEXEC requires non-empty path.")
            finalize_reasons(record)
            emit_record(record)
            return

        if ".." in Path(raw_nonexec_path).parts:
            add_reason(record, REASON_PATH_TRAVERSAL, "Traversal attempt detected in path.")

        canon_nonexec = canonicalize(raw_nonexec_path)
        canon_nonexec_s = str(canon_nonexec)

        if deny_hidden and is_hidden_segment(canon_nonexec):
            add_reason(record, RC_HIDDEN_PATH, f"Hidden path segment is not allowed: {canon_nonexec_s}")

        nonexec_allowed = False
        for _base_s in allow_base_dirs:
            if under_base(canon_nonexec, canonicalize(_base_s)):
                nonexec_allowed = True
                break
        if not nonexec_allowed:
            add_reason(record, REASON_OUTSIDE_ALLOWED_ROOT, "Canonical path not under allowlisted base directories.")

        if is_hot_file_target(canon_nonexec):
            add_reason(record, REASON_TARGET_IS_HOT_FILE, "Target path is hot file.")

        if nonexec_allowed and is_executable_file(canon_nonexec):
            add_reason(record, REASON_IS_EXECUTABLE, "Target path is executable.")

        finalize_reasons(record)
        if not record["policy_reasons"]:
            record["policy_decision"] = "ALLOW"
        emit_record(record)
        return

    # FS_COPY: dual-path enforcement (src_path + dst_path).
    if capability_class == "FS_COPY":
        raw_src = str(args.get("src_path", ""))
        raw_dst = str(args.get("dst_path", ""))
        if not raw_src or not raw_dst:
            add_reason(record, RC_PATH_DISALLOWED, "FS_COPY requires non-empty src_path and dst_path.")
            finalize_reasons(record)
            emit_record(record)
            return

        if ".." in Path(raw_src).parts:
            add_reason(record, REASON_PATH_TRAVERSAL, "Traversal attempt in src_path.")
        if ".." in Path(raw_dst).parts:
            add_reason(record, REASON_PATH_TRAVERSAL, "Traversal attempt in dst_path.")

        try:
            canon_src = canonicalize(raw_src)
            canon_dst = canonicalize(raw_dst)
        except Exception:
            add_reason(record, REASON_UNKNOWN, "Path normalization failed.")
            finalize_reasons(record)
            emit_record(record)
            return

        src_allowed = False
        dst_allowed = False
        for _base_s in allow_base_dirs:
            _base = canonicalize(_base_s)
            if under_base(canon_src, _base):
                src_allowed = True
            if under_base(canon_dst, _base):
                dst_allowed = True
        if not src_allowed or not dst_allowed:
            add_reason(record, REASON_OUTSIDE_ALLOWED_ROOT, "src_path or dst_path not under allowlisted base directories.")

        if is_hot_file_target(canon_dst):
            add_reason(record, REASON_TARGET_IS_HOT_FILE, "dst_path targets hot file.")

        if src_allowed and not canon_src.exists():
            add_reason(record, REASON_SRC_MISSING, "src_path does not exist.")

        overwrite_requested = bool(args.get("overwrite", False))
        overwrite_allowed = bool(tool_meta.get("caps", {}).get("overwrite_allowed", False))
        dest_exists_no_overwrite = canon_dst.exists() and not overwrite_requested
        if overwrite_requested and not overwrite_allowed:
            add_reason(record, REASON_OVERWRITE_FORBIDDEN, "overwrite requested but forbidden by policy.")

        if dest_exists_no_overwrite and not record["policy_reasons"]:
            record["policy_decision"] = "UNDECIDED"
            record["policy_reasons"] = []
            record["insufficiency"] = {
                "trigger": "dest_exists_no_overwrite",
                "surface": "filesystem",
                "tool": "FS_COPY",
                "condition": "Destination path exists and overwrite was not requested",
                "rules_consulted": ["FS_COPY.caps.overwrite_allowed"],
                "gap": "No rule specifies disposition when destination exists and overwrite is not requested. The overwrite policy governs whether overwrite is permitted when requested, not what to do when it is not requested and the destination exists.",
            }
            emit_record(record)
            return

        # Category 6: explicit authorization required (genuine residual)
        _intent = record.get("intent") or {}
        _constraints = _intent.get("constraints") or {}
        if _constraints.get("requires_authorization") is True and not record["policy_reasons"]:
            record["policy_decision"] = "UNDECIDED"
            record["policy_reasons"] = []
            record["insufficiency"] = {
                "trigger": "authorization_required",
                "surface": "filesystem",
                "tool": "FS_COPY",
                "condition": "Intent explicitly requires authorization that the evaluator cannot provide",
                "rules_consulted": ["FS_COPY.caps"],
                "gap": "The evaluator has complete rules for filesystem operations but lacks authority to grant or deny authorization explicitly requested by the caller. No deterministic rule can substitute for authorization.",
            }
            emit_record(record)
            return

        finalize_reasons(record)
        if not record["policy_reasons"]:
            record["policy_decision"] = "ALLOW"
        emit_record(record)
        return

    # FS_PROMOTE: guarded cross-root promotion with root-pair allowlist, hash check, artifact class check.
    if capability_class == "FS_PROMOTE":
        raw_src = str(args.get("src_path", ""))
        raw_dst = str(args.get("dst_path", ""))
        if not raw_src or not raw_dst:
            add_reason(record, RC_PROMO_PATH_DISALLOWED, "FS_PROMOTE requires non-empty src_path and dst_path.")
            finalize_reasons(record)
            emit_record(record)
            return

        # Required intent fields for FS_PROMOTE
        _promo_required = ["promotion_id", "src_root_id", "dst_root_id",
                           "src_content_hash_sha256", "allowed_artifact_class", "requested_by"]
        _promo_missing = [f for f in _promo_required if not intent.get(f)]
        if _promo_missing:
            add_reason(record, RC_MISSING_INTENT_FIELDS,
                       f"Missing required intent fields for FS_PROMOTE: {', '.join(_promo_missing)}.")
            finalize_reasons(record)
            emit_record(record)
            return

        if ".." in Path(raw_src).parts:
            add_reason(record, REASON_PATH_TRAVERSAL, "Traversal attempt in src_path.")
        if ".." in Path(raw_dst).parts:
            add_reason(record, REASON_PATH_TRAVERSAL, "Traversal attempt in dst_path.")

        try:
            canon_src = canonicalize(raw_src)
            canon_dst = canonicalize(raw_dst)
        except Exception:
            add_reason(record, REASON_UNKNOWN, "Path normalization failed.")
            finalize_reasons(record)
            emit_record(record)
            return

        if deny_hidden and is_hidden_segment(canon_src):
            add_reason(record, RC_HIDDEN_PATH, f"Hidden path segment in src_path: {canon_src}")
        if deny_hidden and is_hidden_segment(canon_dst):
            add_reason(record, RC_HIDDEN_PATH, f"Hidden path segment in dst_path: {canon_dst}")

        # Root pair validation
        _promo_caps = tool_meta.get("caps", {})
        _root_id_map_raw = _promo_caps.get("root_id_map", {})
        _root_pair_allowlist = _promo_caps.get("root_pair_allowlist", [])
        _src_root_id = str(intent.get("src_root_id", ""))
        _dst_root_id = str(intent.get("dst_root_id", ""))

        _pair_allowed = any(
            p.get("src_root_id") == _src_root_id and p.get("dst_root_id") == _dst_root_id
            for p in _root_pair_allowlist
        )
        if not _pair_allowed:
            add_reason(record, RC_PROMO_ROOT_PAIR_DISALLOWED,
                       f"Root pair src_root_id={_src_root_id!r} -> dst_root_id={_dst_root_id!r} "
                       f"not in root_pair_allowlist.")

        # Resolve declared root base dirs and verify paths are under them
        def _resolve_root_id(root_id: str):
            template = _root_id_map_raw.get(root_id)
            if template is None:
                return None
            resolved = resolve_allow_base_dirs([template])
            return resolved[0] if resolved else None

        _src_base = _resolve_root_id(_src_root_id)
        _dst_base = _resolve_root_id(_dst_root_id)

        if _src_base is not None and not under_base(canon_src, canonicalize(_src_base)):
            add_reason(record, RC_PROMO_PATH_DISALLOWED,
                       f"src_path is not under declared src_root_id base dir.")
        if _dst_base is not None and not under_base(canon_dst, canonicalize(_dst_base)):
            add_reason(record, RC_PROMO_PATH_DISALLOWED,
                       f"dst_path is not under declared dst_root_id base dir.")

        # Artifact class check
        _allowed_classes = _promo_caps.get("allowed_artifact_classes", [])
        _req_class = str(intent.get("allowed_artifact_class", ""))
        if _req_class not in _allowed_classes:
            add_reason(record, RC_PROMO_ARTIFACT_CLASS_DISALLOWED,
                       f"allowed_artifact_class={_req_class!r} not in registry allowed classes.")

        # Source existence and type check (only if no reasons so far — early exit avoided)
        if canon_src.exists():
            if not canon_src.is_file():
                add_reason(record, RC_PROMO_SRC_TYPE_DISALLOWED,
                           "Source path exists but is not a regular file.")
            else:
                # Source hash verification (INV-PROMO-003)
                _declared_hash = str(intent.get("src_content_hash_sha256", ""))
                try:
                    _actual_hash = "sha256:" + hashlib.sha256(canon_src.read_bytes()).hexdigest()
                except OSError:
                    add_reason(record, RC_PROMO_SRC_MISSING, "Source file unreadable.")
                else:
                    if _actual_hash != _declared_hash:
                        add_reason(record, RC_PROMO_HASH_MISMATCH_SRC,
                                   f"Source hash mismatch: declared={_declared_hash!r} "
                                   f"actual={_actual_hash!r}.")
        else:
            add_reason(record, RC_PROMO_SRC_MISSING, "Source path does not exist.")

        # Overwrite check
        if not bool(_promo_caps.get("overwrite_allowed", False)):
            if bool(args.get("overwrite", False)):
                add_reason(record, RC_PROMO_OVERWRITE_DISALLOWED,
                           "overwrite is not permitted: caps.overwrite_allowed=false.")
            elif canon_dst.exists():
                add_reason(record, RC_PROMO_OVERWRITE_DISALLOWED,
                           "Destination exists and overwrite is disallowed.")

        finalize_reasons(record)
        if not record["policy_reasons"]:
            record["policy_decision"] = "ALLOW"
        emit_record(record)
        return

    # FS_DELETE: single-path enforcement (path + recursive flag)
    if capability_class == "FS_DELETE":
        raw_del_path = str(args.get("path", ""))
        if not raw_del_path:
            add_reason(record, RC_PATH_DISALLOWED, "FS_DELETE requires non-empty path.")
            finalize_reasons(record)
            emit_record(record)
            return

        if ".." in Path(raw_del_path).parts:
            add_reason(record, RC_PATH_TRAVERSAL, "Traversal attempt detected in path.")

        canon_del = canonicalize(raw_del_path)
        canon_del_s = str(canon_del)

        if deny_hidden and is_hidden_segment(canon_del):
            add_reason(record, RC_HIDDEN_PATH, f"Hidden path segment is not allowed: {canon_del_s}")

        del_allowed = False
        for _base_s in allow_base_dirs:
            if under_base(canon_del, canonicalize(_base_s)):
                del_allowed = True
                break
        if not del_allowed:
            add_reason(record, RC_PATH_DISALLOWED, "Canonical path not under allowlisted base directories.")

        _del_caps = tool_meta.get("caps", {})
        if bool(args.get("recursive", False)) and not bool(_del_caps.get("recursive_allowed", False)):
            add_reason(record, RC_RECURSIVE_DISALLOWED,
                       "recursive=true is not permitted: caps.recursive_allowed=false.")

        finalize_reasons(record)
        if not record["policy_reasons"]:
            record["policy_decision"] = "ALLOW"
        emit_record(record)
        return

    if not isinstance(raw_path, str) or not raw_path:
        add_reason(record, RC_PATH_DISALLOWED, "Missing or invalid args.path.")
        finalize_reasons(record)
        emit_record(record)
        return

    # Traversal attempt detection: deny attempt if input contains ".." segments
    if ".." in Path(raw_path).parts:
        add_reason(record, RC_PATH_TRAVERSAL, "Traversal attempt detected in raw path input.")

    # Base dir allowlist
    allowed = False
    for base_s in allow_base_dirs:
        base = canonicalize(base_s)
        if canon is not None and under_base(canon, base):
            allowed = True
            break
    if not allowed:
        add_reason(record, RC_PATH_DISALLOWED, "Canonical path not under allowlisted base directories.")

    # Hidden paths
    if deny_hidden and canon is not None and is_hidden_segment(canon):
        add_reason(record, RC_HIDDEN_PATH, "Hidden path segment is not allowed.")

    # Overwrite mismatch logic
    if deny_overwrite_default:
        if overwrite_requested or overwrite_intent:
            if not (overwrite_requested and overwrite_intent):
                add_reason(record, RC_OVERWRITE_DISALLOWED, "Overwrite requires both intent.constraints.overwrite=true and args.overwrite=true.")

    # Include hidden deny (FS_LIST only)
    if capability_class == "FS_LIST":
        include_hidden = bool(args.get("include_hidden", False))
        if include_hidden:
            add_reason(record, RC_INCLUDE_HIDDEN_DISALLOWED, "Phase 2: include_hidden must be False.")

    # Directory check (FS_LIST only)
    if capability_class == "FS_LIST" and canon is not None:
        if not os.path.isdir(canon_s):
            add_reason(record, RC_NOT_A_DIRECTORY, f"Path is not a directory: {canon_s}")

    # FS_READ specific checks
    if capability_class == "FS_READ":
        # max_bytes enforcement
        hard = int(tool_meta.get("max_bytes_hard", 65536))
        default = int(tool_meta.get("max_bytes_default", 4096))
        try:
            max_bytes = int(args.get("max_bytes", default))
        except Exception:
            max_bytes = default
        if max_bytes < 1:
            max_bytes = 1
        if max_bytes > hard:
            add_reason(record, RC_MAX_BYTES_EXCEEDED, f"max_bytes {max_bytes} exceeds hard limit {hard}")

        # File check (FS_READ only)
        if canon is not None:
            if not os.path.isfile(canon_s):
                add_reason(record, RC_NOT_A_FILE, f"Path is not a file: {canon_s}")

    # Executable outputs deny
    if deny_exec and request_executable:
        add_reason(record, RC_EXECUTABLE_DISALLOWED, "Executable outputs are denied in Phase 1.")

    finalize_reasons(record)

    if len(record["policy_reasons"]) == 0:
        record["policy_decision"] = "ALLOW"

    emit_record(record)

def emit_record(record: dict) -> None:
    # Compute record_hash over deterministic signing preimage.
    payload = signing_preimage_payload(record)
    signing_key, signing_key_id, signing_err = load_signing_private_key()
    if signing_err:
        print(signing_err, file=sys.stderr)
        sys.exit(2)
    if signing_key is not None:
        sig = signing_key.sign(payload.encode("utf-8"))
        record["signature"] = _b64url_encode_nopad(sig)
        record["signing_key_id"] = signing_key_id
    elif signing_required_mode_enabled():
        print(
            "FATAL: signed PolicyRecord required for trust-grade mode; "
            "configure GOV_SIGNING_KEY_PATH or use explicit compatibility mode",
            file=sys.stderr,
        )
        sys.exit(2)
    record["record_hash"] = f"sha256:{sha256_hex(payload)}"
    maybe_write_build_manifest(record)
    print(json.dumps(record, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
