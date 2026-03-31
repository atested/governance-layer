#!/usr/bin/env python3
import base64
import json
import os
import sys
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path

CAP_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "capabilities" / "capability-registry.json"

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

REASON_ORDER = [
    RC_MISSING_INTENT_FIELDS,
    RC_UNKNOWN_TOOL,
    RC_PATH_TRAVERSAL,
    RC_PATH_DISALLOWED,
    RC_CROSS_ROOT_DISALLOWED,
    RC_HIDDEN_PATH,
    RC_INCLUDE_HIDDEN_DISALLOWED,
    RC_MAX_BYTES_EXCEEDED,
    RC_OVERWRITE_DISALLOWED,
    RC_EXECUTABLE_DISALLOWED,
    RC_NOT_A_DIRECTORY,
    RC_NOT_A_FILE,
]

def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

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
        "record_version": "0.1",
        "cap_registry_hash": cap_registry_hash,
        "request_hash": request_hash,
        "request_bytes_b64": request_bytes_b64,
        "timestamp_utc": now_utc_z(),
        "session_id": session_id,
        "request_id": request_id,
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

    # Policy evaluation begins

    if missing_intent:
        add_reason(record, RC_MISSING_INTENT_FIELDS, "Missing required intent.goal or intent.expected_outputs.")

    if tool_meta is None or capability_class is None:
        add_reason(record, RC_UNKNOWN_TOOL, f"Tool '{tool}' not registered in capability registry.")
        finalize_reasons(record)
        emit_record(record)
        return

    # Populate policy_inputs from capability registry and normalized request
    allow_base_dirs = tool_meta.get("allow_base_dirs", [])
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
            add_reason(record, RC_PATH_TRAVERSAL, "Traversal attempt in src_path.")
        if ".." in Path(raw_dst).parts:
            add_reason(record, RC_PATH_TRAVERSAL, "Traversal attempt in dst_path.")

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
            add_reason(record, RC_PATH_DISALLOWED,
                       "src_path or dst_path not under allowlisted base directories.")

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
    # Compute record_hash over canonical JSON excluding record_hash and signature
    unsigned = dict(record)
    unsigned["record_hash"] = None
    unsigned["signature"] = None
    payload = canonical_json(unsigned)
    record["record_hash"] = f"sha256:{sha256_hex(payload)}"
    print(json.dumps(record, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
