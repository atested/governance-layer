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

LEVEL3_DISPOSITION_TYPES = frozenset([
    "ESCALATION_JUSTIFIED",
    "BOUNDED_ESTIMATION",
    "RANDOM_TIEBREAK",
    "NO_ADMISSIBLE_CHOICE",
])

DISPOSITION_TO_METHOD = {
    "ESCALATION_JUSTIFIED": "human_authority",
    "BOUNDED_ESTIMATION": "bounded_estimation",
    "RANDOM_TIEBREAK": "random_tiebreak",
    "NO_ADMISSIBLE_CHOICE": "non_resolution",
}

VALID_OUTCOMES = frozenset(["ALLOW", "DENY", "NON_RESOLUTION"])


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


def _validate_triage_record(triage_record: dict) -> None:
    # Rule 1: must be a valid v0.2 triage_decision record
    if triage_record.get("record_type") != "triage_decision":
        _fatal("FATAL: input record_type must be triage_decision")
    if triage_record.get("record_version") != "0.2":
        _fatal("FATAL: input record_version must be 0.2")
    if not isinstance(triage_record.get("record_hash"), str) or not triage_record.get("record_hash"):
        _fatal("FATAL: input missing record_hash")
    if not isinstance(triage_record.get("process_id"), str) or not triage_record.get("process_id"):
        _fatal("FATAL: input missing process_id")

    # Rule 2: disposition.type must route to Level 3
    disposition = triage_record.get("disposition")
    if not isinstance(disposition, dict):
        _fatal("FATAL: input missing disposition object")
    disp_type = disposition.get("type")
    if disp_type not in LEVEL3_DISPOSITION_TYPES:
        _fatal(
            f"FATAL: triage disposition type '{disp_type}' does not route to Level 3. "
            f"Expected one of: {', '.join(sorted(LEVEL3_DISPOSITION_TYPES))}"
        )


def _validate_method_consistency(triage_record: dict, method: str) -> None:
    # Rule 3: method must be consistent with triage disposition
    disposition = triage_record.get("disposition", {})
    disp_type = disposition.get("type")
    expected_method = DISPOSITION_TO_METHOD.get(disp_type)
    if method != expected_method:
        _fatal(
            f"FATAL: method '{method}' inconsistent with triage disposition '{disp_type}'. "
            f"Expected method: '{expected_method}'"
        )


def _validate_outcome(method: str, outcome: str) -> None:
    # Rule 4: outcome must be valid
    if outcome not in VALID_OUTCOMES:
        _fatal(f"FATAL: outcome '{outcome}' not valid. Expected one of: {', '.join(sorted(VALID_OUTCOMES))}")

    # Rule 5: non_resolution method must produce NON_RESOLUTION
    if method == "non_resolution" and outcome != "NON_RESOLUTION":
        _fatal(f"FATAL: method 'non_resolution' must produce outcome 'NON_RESOLUTION', got '{outcome}'")

    # Rule 6: non-non_resolution methods must produce ALLOW or DENY
    if method != "non_resolution" and outcome == "NON_RESOLUTION":
        _fatal(f"FATAL: method '{method}' must not produce outcome 'NON_RESOLUTION'")


def _validate_decider(decider_identity: str, decider_authority: str) -> None:
    # Rule 7: decider fields must be non-empty
    if not decider_identity.strip():
        _fatal("FATAL: decider_identity must be a non-empty string")
    if not decider_authority.strip():
        _fatal("FATAL: decider_authority must be a non-empty string")


def _validate_rationale(rationale: str) -> None:
    # Rule 8: rationale must be non-empty
    if not rationale.strip():
        _fatal("FATAL: rationale must be a non-empty string")


def _build_terminal_judgment_record(
    triage_record: dict,
    method: str,
    outcome: str,
    decider_identity: str,
    decider_authority: str,
    rationale: str,
) -> dict:
    return {
        "record_version": "0.2",
        "record_type": "terminal_judgment",
        "cap_registry_hash": _compute_cap_registry_hash(),
        "request_hash": triage_record.get("request_hash"),
        "request_bytes_b64": triage_record.get("request_bytes_b64"),
        "timestamp_utc": _now_utc_z(),
        "session_id": triage_record.get("session_id"),
        "request_id": triage_record.get("request_id"),
        "process_id": triage_record.get("process_id"),
        "actor": os.environ.get("GOV_ACTOR", triage_record.get("actor", "unknown")),
        "tool": triage_record.get("tool", "FS_COPY"),
        "capability_class": triage_record.get("capability_class"),
        "intent": triage_record.get("intent", {}),
        "policy_inputs": triage_record.get("policy_inputs", {}),
        "normalized_args": triage_record.get("normalized_args", {}),
        "policy_decision": outcome,
        "policy_reasons": [],
        "originating_triage_hash": triage_record["record_hash"],
        "method": method,
        "decider": {
            "identity": decider_identity,
            "authority": decider_authority,
        },
        "rationale": rationale,
        "outcome": outcome,
        "prev_record_hash": None,
        "record_hash": None,
        "signature": None,
        "signing_key_id": None,
        "evidence_refs": [],
        "untrusted_inputs": [],
    }


def _resolve_prev_record_hash(terminal_record: dict) -> None:
    chain_path = Path(os.environ.get("GOV_DECISION_CHAIN_PATH", str(DEFAULT_CHAIN_PATH)))
    if chain_path.exists():
        last_hash = None
        with chain_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    last_hash = rec.get("record_hash")
                except Exception:
                    pass
        if last_hash:
            terminal_record["prev_record_hash"] = last_hash
            return
    terminal_record["prev_record_hash"] = terminal_record["originating_triage_hash"]


def _sign_and_hash_record(terminal_record: dict) -> None:
    verify_mod = _load_module(VERIFY_RECORD_PATH, "verify_record_impl_for_terminal")
    policy_mod = _load_module(POLICY_EVAL_PATH, "policy_eval_impl_for_terminal")
    payload = verify_mod.signing_preimage_payload(terminal_record)
    signing_key, signing_key_id, signing_err = policy_mod.load_signing_private_key()
    if signing_err:
        print(signing_err, file=sys.stderr)
        sys.exit(2)
    if signing_key is not None:
        sig = signing_key.sign(payload.encode("utf-8"))
        terminal_record["signature"] = policy_mod._b64url_encode_nopad(sig)
        terminal_record["signing_key_id"] = signing_key_id
    terminal_record["record_hash"] = f"sha256:{_sha256_hex(payload)}"


def _append_to_chain(terminal_record: dict) -> None:
    chain_path = Path(os.environ.get("GOV_DECISION_CHAIN_PATH", str(DEFAULT_CHAIN_PATH)))
    chain_path.parent.mkdir(parents=True, exist_ok=True)
    one_line = _canonical_json(terminal_record)
    with chain_path.open("a", encoding="utf-8") as f:
        f.write(one_line + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Emit terminal judgment record for a Level 3 triage input."
    )
    ap.add_argument("triage_record_path")
    ap.add_argument("--method", required=True,
                     help="Terminal judgment method (human_authority, bounded_estimation, random_tiebreak, non_resolution)")
    ap.add_argument("--outcome", required=True,
                     help="Terminal judgment outcome (ALLOW, DENY, NON_RESOLUTION)")
    ap.add_argument("--decider-identity", required=True,
                     help="Identity of the decider")
    ap.add_argument("--decider-authority", required=True,
                     help="Authority held by the decider")
    ap.add_argument("--rationale", required=True,
                     help="Stated basis for the judgment")
    args = ap.parse_args()

    triage_record = _load_input_record(Path(args.triage_record_path))
    _validate_triage_record(triage_record)
    _validate_method_consistency(triage_record, args.method)
    _validate_outcome(args.method, args.outcome)
    _validate_decider(args.decider_identity, args.decider_authority)
    _validate_rationale(args.rationale)

    terminal_record = _build_terminal_judgment_record(
        triage_record,
        method=args.method,
        outcome=args.outcome,
        decider_identity=args.decider_identity,
        decider_authority=args.decider_authority,
        rationale=args.rationale,
    )
    _resolve_prev_record_hash(terminal_record)
    _sign_and_hash_record(terminal_record)
    _append_to_chain(terminal_record)

    print(json.dumps(terminal_record, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
