#!/usr/bin/env python3
import argparse
import hashlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[0]
CAP_REGISTRY_PATH = REPO_ROOT / "capabilities" / "capability-registry.json"
VERIFY_RECORD_PATH = SCRIPT_DIR / "verify-record.py"
POLICY_EVAL_PATH = SCRIPT_DIR / "policy-eval.py"
DEFAULT_CHAIN_PATH = REPO_ROOT / "LOGS" / "decision-chain.jsonl"
DEFAULT_TRIAGE_CRITERIA_PATH = REPO_ROOT / "scripts" / "attest" / "rdd_triage_criteria.v1.json"
DEFAULT_SELECTOR_MODE = "compat_legacy_single_case"


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _compute_cap_registry_hash() -> str:
    raw = CAP_REGISTRY_PATH.read_bytes()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _load_input_record(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"FATAL: unable to read input record: {exc}", file=sys.stderr)
        sys.exit(2)
    try:
        rec = json.loads(raw)
    except Exception as exc:
        print(f"FATAL: input is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(rec, dict):
        print("FATAL: input record must be a JSON object", file=sys.stderr)
        sys.exit(2)
    return rec


def _fatal(msg: str) -> None:
    print(msg, file=sys.stderr)
    sys.exit(2)


def _validate_pass_record(pass_record: dict) -> None:
    if pass_record.get("record_type") != "pass_decision":
        _fatal("FATAL: input record_type must be pass_decision")
    if pass_record.get("policy_decision") != "UNDECIDED":
        _fatal("FATAL: input policy_decision must be UNDECIDED")
    if not isinstance(pass_record.get("record_hash"), str) or not pass_record.get("record_hash"):
        _fatal("FATAL: input missing record_hash")
    if not isinstance(pass_record.get("process_id"), str) or not pass_record.get("process_id"):
        _fatal("FATAL: input missing process_id")


def _required_criteria_fields() -> dict:
    return {
        "findings": list,
        "governing_condition": str,
        "governing_rationale": str,
        "disposition": dict,
        "structural_signals": list,
    }


def _is_criteria_case(candidate: object) -> bool:
    if not isinstance(candidate, dict):
        return False
    return all(field in candidate for field in _required_criteria_fields().keys())


def _derive_selector(pass_record: dict) -> str:
    insufficiency = pass_record.get("insufficiency")
    if not isinstance(insufficiency, dict):
        _fatal("FATAL: TRIAGE_CRITERIA_SELECTOR_INPUT_INVALID missing_or_invalid=insufficiency")
    required = ("tool", "surface", "trigger")
    values: dict[str, str] = {}
    for field in required:
        value = insufficiency.get(field)
        if not isinstance(value, str) or not value.strip():
            _fatal(f"FATAL: TRIAGE_CRITERIA_SELECTOR_INPUT_INVALID missing_field={field}")
        values[field] = value.strip()
    return f"{values['tool']}|{values['surface']}|{values['trigger']}"


def _normalize_selector_map(obj: dict, selector: str) -> dict:
    selector_mode = os.environ.get("GOV_TRIAGE_SELECTOR_MODE", DEFAULT_SELECTOR_MODE).strip()
    if selector_mode not in ("compat_legacy_single_case", "explicit"):
        _fatal(f"FATAL: TRIAGE_CRITERIA_SELECTOR_MODE_INVALID mode={selector_mode}")

    selector_map = obj.get("selector_map")
    if selector_map is not None:
        if not isinstance(selector_map, dict):
            _fatal("FATAL: TRIAGE_CRITERIA_SELECTOR_MAP_INVALID expected=object")
        normalized = {k: v for k, v in selector_map.items() if isinstance(k, str) and isinstance(v, str)}
        if len(normalized) != len(selector_map):
            _fatal("FATAL: TRIAGE_CRITERIA_SELECTOR_MAP_INVALID non_string_entry=present")
        if len(normalized) == 0:
            _fatal("FATAL: TRIAGE_CRITERIA_SELECTOR_MAP_INVALID empty_map=present")
        return normalized

    if selector_mode == "explicit":
        _fatal("FATAL: TRIAGE_CRITERIA_SELECTOR_MAP_REQUIRED mode=explicit")

    # Legacy compatibility: infer a single criteria case from top-level content.
    ignored = {"criteria_version", "selector_map"}
    legacy_cases = [key for key, value in obj.items() if key not in ignored and isinstance(value, dict)]
    if len(legacy_cases) == 1:
        return {selector: legacy_cases[0]}
    _fatal("FATAL: TRIAGE_CRITERIA_SELECTOR_MAP_MISSING")


def _load_triage_criteria(pass_record: dict) -> dict:
    criteria_path = Path(os.environ.get("GOV_TRIAGE_CRITERIA_PATH", str(DEFAULT_TRIAGE_CRITERIA_PATH)))
    if not criteria_path.exists():
        _fatal(f"FATAL: TRIAGE_CRITERIA_MISSING_FILE path={criteria_path}")
    try:
        raw = criteria_path.read_text(encoding="utf-8")
    except OSError as exc:
        _fatal(f"FATAL: TRIAGE_CRITERIA_READ_ERROR path={criteria_path} error={exc}")
    try:
        obj = json.loads(raw)
    except Exception as exc:
        _fatal(f"FATAL: TRIAGE_CRITERIA_MALFORMED_JSON path={criteria_path} error={exc}")
    if not isinstance(obj, dict):
        _fatal("FATAL: TRIAGE_CRITERIA_SCHEMA_INVALID expected=object")

    selector = _derive_selector(pass_record)
    selector_map = _normalize_selector_map(obj, selector)
    case_key = selector_map.get(selector)
    if not isinstance(case_key, str) or not case_key:
        _fatal(f"FATAL: TRIAGE_CRITERIA_SELECTOR_UNSUPPORTED selector={selector}")
    criteria = obj.get(case_key)
    if not isinstance(criteria, dict):
        _fatal(f"FATAL: TRIAGE_CRITERIA_SELECTOR_TARGET_MISSING key={case_key}")

    required = _required_criteria_fields()
    for field, expected_type in required.items():
        if field not in criteria:
            _fatal(f"FATAL: TRIAGE_CRITERIA_SCHEMA_INVALID missing_field={field}")
        if not isinstance(criteria[field], expected_type):
            _fatal(
                "FATAL: TRIAGE_CRITERIA_SCHEMA_INVALID "
                f"invalid_type={field} expected={expected_type.__name__}"
            )
    return criteria


def _build_triage_record(pass_record: dict, criteria: dict) -> dict:
    return {
        "record_version": "0.2",
        "record_type": "triage_decision",
        "cap_registry_hash": _compute_cap_registry_hash(),
        "request_hash": pass_record.get("request_hash"),
        "request_bytes_b64": pass_record.get("request_bytes_b64"),
        "timestamp_utc": _now_utc_z(),
        "session_id": pass_record.get("session_id"),
        "request_id": pass_record.get("request_id"),
        "process_id": pass_record.get("process_id"),
        "actor": os.environ.get("GOV_ACTOR", pass_record.get("actor", "unknown")),
        "tool": pass_record.get("tool", "FS_COPY"),
        "capability_class": pass_record.get("capability_class"),
        "intent": pass_record.get("intent", {}),
        "policy_inputs": pass_record.get("policy_inputs", {}),
        "normalized_args": pass_record.get("normalized_args", {}),
        "policy_decision": "TRIAGE",
        "policy_reasons": [],
        "originating_pass_hash": pass_record["record_hash"],
        "findings": criteria["findings"],
        "governing_condition": criteria["governing_condition"],
        "governing_rationale": criteria["governing_rationale"],
        "disposition": criteria["disposition"],
        "structural_signals": criteria["structural_signals"],
        "prev_record_hash": pass_record["record_hash"],
        "record_hash": None,
        "signature": None,
        "signing_key_id": None,
        "evidence_refs": [],
        "untrusted_inputs": [],
    }


def _sign_and_hash_record(triage_record: dict) -> None:
    verify_mod = _load_module(VERIFY_RECORD_PATH, "verify_record_impl_for_triage")
    policy_mod = _load_module(POLICY_EVAL_PATH, "policy_eval_impl_for_triage")
    payload = verify_mod.signing_preimage_payload(triage_record)
    signing_key, signing_key_id, signing_err = policy_mod.load_signing_private_key()
    if signing_err:
        print(signing_err, file=sys.stderr)
        sys.exit(2)
    if signing_key is not None:
        sig = signing_key.sign(payload.encode("utf-8"))
        triage_record["signature"] = policy_mod._b64url_encode_nopad(sig)
        triage_record["signing_key_id"] = signing_key_id
    triage_record["record_hash"] = f"sha256:{_sha256_hex(payload)}"


def _append_to_chain(triage_record: dict) -> None:
    chain_path = Path(os.environ.get("GOV_DECISION_CHAIN_PATH", str(DEFAULT_CHAIN_PATH)))
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    one_line = _canonical_json(triage_record)
    with chain_path.open("a", encoding="utf-8") as f:
        f.write(one_line + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit triage decision record for a pass UNDECIDED input.")
    ap.add_argument("pass_record_path")
    args = ap.parse_args()

    pass_record = _load_input_record(Path(args.pass_record_path))
    _validate_pass_record(pass_record)
    criteria = _load_triage_criteria(pass_record)

    triage_record = _build_triage_record(pass_record, criteria)
    _sign_and_hash_record(triage_record)
    _append_to_chain(triage_record)

    print(json.dumps(triage_record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
