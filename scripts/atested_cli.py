#!/usr/bin/env python3
"""
atested — Command-line interface for Atested governance.

Thin wrapper over existing modules: approval store, chain readout, policy
evaluator, chain integrity. Reads the same data sources as the dashboard.

Subcommands:
  status        Governance status summary
  activity      Recent governance activity
  approvals     List active approvals
  approve       Approve an artifact (record approval event in chain)
  revoke        Revoke an existing approval (record revocation event in chain)
  policy        List policy rules
  chain         Chain operations (verify)
  verification  Show surface verification states
"""

from __future__ import annotations

import argparse
import json
import os
import stat as _stat
import sys
import threading
import time as _time_mod
from pathlib import Path

# Resolve the repository root and ensure scripts/ + mcp/ are importable.
SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent
MCP_DIR = REPO / "mcp"
for _p in (str(SCRIPT_DIR), str(MCP_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from storage_contract import runtime_root  # noqa: E402

RUNTIME = runtime_root(REPO)
CHAIN = RUNTIME / "LOGS" / "decision-chain.jsonl"
RECORDS_DIR = RUNTIME / "LOGS" / "records"
POLICY_RULES_PATH = REPO / "capabilities" / "policy-rules.json"


# ---------------------------------------------------------------------------
# Helpers — context resolution and chain append (mirrors dashboard semantics)
# ---------------------------------------------------------------------------


def _governed_family() -> str:
    return str(os.environ.get("GOV_GOVERNED_FAMILY", "mcp_tools_v1")).strip() or "mcp_tools_v1"


def _deployment_context() -> str:
    return str(os.environ.get("GOV_DEPLOYMENT_CONTEXT", "default")).strip() or "default"


def _policy_version() -> str:
    return str(os.environ.get("GOV_POLICY_VERSION", "baseline-v1")).strip() or "baseline-v1"


_chain_lock = threading.Lock()


def _acquire_chain_file_lock():
    """Cross-process mkdir lock — same protocol as dashboard/server.py."""
    lockdir = Path(str(CHAIN) + ".lock.d")
    lock_meta = lockdir / "lock_owner.json"
    max_wait = 50

    def _try_acquire() -> bool:
        try:
            lockdir.mkdir(exist_ok=False)
            try:
                meta = json.dumps({"pid": os.getpid(), "ts": _time_mod.time()})
                lock_meta.write_text(meta, encoding="utf-8")
            except OSError:
                pass
            return True
        except FileExistsError:
            return False

    def _holder_is_alive() -> bool:
        try:
            data = json.loads(lock_meta.read_text(encoding="utf-8"))
            pid = data.get("pid")
            if not isinstance(pid, int):
                return True
            os.kill(pid, 0)
            return True
        except (OSError, json.JSONDecodeError, KeyError):
            return False

    waited = 0
    while True:
        if _try_acquire():
            return lockdir
        waited += 1
        if waited >= max_wait:
            if not _holder_is_alive():
                try:
                    lock_meta.unlink(missing_ok=True)
                    lockdir.rmdir()
                except OSError:
                    pass
                if _try_acquire():
                    return lockdir
            raise TimeoutError(f"timed out waiting for chain lock ({lockdir})")
        _time_mod.sleep(0.1)


def _release_chain_file_lock(lockdir: Path) -> None:
    try:
        (lockdir / "lock_owner.json").unlink(missing_ok=True)
        lockdir.rmdir()
    except OSError:
        pass


def _get_chain_head_hash():
    if not CHAIN.exists():
        return None
    last_line = ""
    with open(CHAIN, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if not last_line:
        return None
    try:
        return json.loads(last_line).get("record_hash")
    except json.JSONDecodeError:
        return None


def _append_chain_record_atomic(event: dict) -> dict:
    """Atomically append a non-action event to the chain."""
    from event_model import _compute_event_record_hash
    from machine_identity import add_machine_identity_fields

    CHAIN.parent.mkdir(parents=True, exist_ok=True)
    with _chain_lock:
        lockdir = _acquire_chain_file_lock()
        try:
            add_machine_identity_fields(event, REPO)
            event["prev_record_hash"] = _get_chain_head_hash()
            event["record_hash"] = _compute_event_record_hash(event)
            line = json.dumps(
                event, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ) + "\n"
            fd = os.open(
                str(CHAIN),
                os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                _stat.S_IRUSR | _stat.S_IWUSR,
            )
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
        finally:
            _release_chain_file_lock(lockdir)
    return event


def _load_approval_store():
    from approval_store import ApprovalStore, load_approval_store_from_chain

    if CHAIN.exists():
        return load_approval_store_from_chain(str(CHAIN))
    return ApprovalStore()


def _load_verification_tracker():
    from verification import VerificationStateTracker, load_verification_state_from_chain

    if CHAIN.exists():
        return load_verification_state_from_chain(str(CHAIN))
    return VerificationStateTracker()


def _emit(args, data) -> None:
    """Print result as JSON (default) or pretty text if --pretty."""
    if getattr(args, "json", False):
        print(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False))
    else:
        # Default: also JSON for machine-readable; matches dashboard payloads.
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_status(args) -> int:
    from readout import assemble_governance_status_record

    data = assemble_governance_status_record(
        CHAIN,
        _load_verification_tracker(),
        _load_approval_store(),
        window=args.window,
    )
    _emit(args, data)
    return 0


def cmd_activity(args) -> int:
    from readout import governance_activity_view

    data = governance_activity_view(
        CHAIN,
        limit=args.limit,
        offset=args.offset,
        governed_family=args.governed_family,
        event_category=args.event_category,
        resolution=args.resolution,
        start_time=args.start_time,
        end_time=args.end_time,
    )
    _emit(args, data)
    return 0


def cmd_approvals(args) -> int:
    from readout import governance_approvals_view

    data = governance_approvals_view(CHAIN, _load_approval_store())
    _emit(args, data)
    return 0


def cmd_approve(args) -> int:
    from event_model import build_non_action_event

    artifact_identity = args.artifact_identity.strip()
    if not artifact_identity:
        print("error: artifact_identity is required", file=sys.stderr)
        return 2
    operator = (args.operator or "cli_operator").strip()

    payload = {
        "artifact_identity": artifact_identity,
        "approving_operator": operator,
        "governed_family": _governed_family(),
        "deployment_context": _deployment_context(),
        "policy_version": _policy_version(),
    }
    event = build_non_action_event("opaque_artifact_approval", payload, prev_record_hash=None)
    event = _append_chain_record_atomic(event)
    _emit(args, {
        "approved": True,
        "event_id": event.get("event_id"),
        "artifact_identity": artifact_identity,
        "approving_operator": operator,
    })
    return 0


def cmd_revoke(args) -> int:
    from event_model import build_non_action_event

    artifact_identity = args.artifact_identity.strip()
    if not artifact_identity:
        print("error: artifact_identity is required", file=sys.stderr)
        return 2
    operator = (args.operator or "cli_operator").strip()

    payload = {
        "artifact_identity": artifact_identity,
        "revoking_operator": operator,
        "governed_family": _governed_family(),
        "deployment_context": _deployment_context(),
        "policy_version": _policy_version(),
    }
    event = build_non_action_event("opaque_artifact_revocation", payload, prev_record_hash=None)
    event = _append_chain_record_atomic(event)
    _emit(args, {
        "revoked": True,
        "event_id": event.get("event_id"),
        "artifact_identity": artifact_identity,
        "revoking_operator": operator,
    })
    return 0


def cmd_policy_list(args) -> int:
    if not POLICY_RULES_PATH.exists():
        print(f"error: policy rules file not found: {POLICY_RULES_PATH}", file=sys.stderr)
        return 1
    rules = json.loads(POLICY_RULES_PATH.read_text(encoding="utf-8"))
    _emit(args, rules)
    return 0


def cmd_chain_verify(args) -> int:
    from readout import check_chain_integrity

    result = check_chain_integrity(CHAIN)
    _emit(args, result)
    return 0 if result.get("status") == "ok" else 1


def cmd_verification(args) -> int:
    from readout import governance_verification_view

    data = governance_verification_view(
        CHAIN,
        _load_verification_tracker(),
        governed_family=args.governed_family,
    )
    _emit(args, data)
    return 0


# ---------------------------------------------------------------------------
# Init command — first-run setup
# ---------------------------------------------------------------------------


def cmd_init(args) -> int:
    """First-run setup: create gov_runtime, generate signing key, configure base_dirs."""
    runtime = RUNTIME
    signing_key_path = runtime / ".atested-signing-key.pem"
    logs_dir = runtime / "LOGS"

    # Guard against overwrite
    if signing_key_path.exists() and not getattr(args, "force", False):
        print("Atested is already initialized.", file=sys.stderr)
        print(f"  Signing key: {signing_key_path}", file=sys.stderr)
        print(f"  Runtime:     {runtime}", file=sys.stderr)
        print("", file=sys.stderr)
        print("To reinitialize, run: atested init --force", file=sys.stderr)
        return 1

    # 1. Create runtime directory structure
    logs_dir.mkdir(parents=True, exist_ok=True)
    (runtime / "LOGS" / "records").mkdir(parents=True, exist_ok=True)
    print(f"  Created runtime directory: {runtime}")

    # 2. Generate Ed25519 signing key
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
    except ImportError:
        print("error: 'cryptography' package is required. Install with:", file=sys.stderr)
        print("  pip install cryptography", file=sys.stderr)
        return 1

    private_key = Ed25519PrivateKey.generate()
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    signing_key_path.write_bytes(pem_bytes)
    os.chmod(str(signing_key_path), 0o600)
    print(f"  Generated signing key:    {signing_key_path}")

    # 3. Create persistent machine identity and primary registry.
    try:
        from receipt_signing import _public_key_fingerprint
        from machine_identity import ensure_machine_identity, ensure_primary_machine_registry
        key_id = _public_key_fingerprint(private_key.public_key(), serialization)
        identity = ensure_machine_identity(REPO, role="primary", signing_key_id=key_id)
        ensure_primary_machine_registry(REPO, identity=identity, public_key_fingerprint=key_id)
        print(f"  Assigned machine ID:      {identity['machine_id']}")
        print("  Machine role:             primary")
    except Exception as exc:
        print(f"error: failed to create machine identity: {exc}", file=sys.stderr)
        return 1

    # 4. Ask for working directories (or use defaults)
    base_dirs = ["__GOV_CANONICAL_REPO_PATH__", "__GOV_RUNTIME_PATH__"]
    dirs_arg = getattr(args, "dirs", None)
    if dirs_arg:
        for d in dirs_arg:
            resolved = str(Path(d).resolve())
            if resolved not in base_dirs:
                base_dirs.append(resolved)
    else:
        # Default: current working directory
        cwd = str(Path.cwd().resolve())
        if cwd != str(REPO.resolve()):
            base_dirs.append(cwd)
            print(f"  Added working directory:  {cwd}")

    # 5. Configure policy-rules.json base_dirs
    policy_data = json.loads(POLICY_RULES_PATH.read_text(encoding="utf-8"))
    policy_data["base_dirs"] = base_dirs
    POLICY_RULES_PATH.write_text(
        json.dumps(policy_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  Configured policy rules:  {POLICY_RULES_PATH}")
    if len(base_dirs) > 2:
        for d in base_dirs[2:]:
            print(f"    base_dir: {d}")

    # 6. Summary
    print("")
    print("Atested is initialized.")
    print("")
    print("What happens next:")
    print("")
    print("  1. Start the proxy:")
    print(f"     python3 -m proxy.server")
    print("")
    print("  2. Point your AI agent at the proxy:")
    print("     export ANTHROPIC_BASE_URL=http://localhost:8080/anthropic")
    print("")
    print("  3. Use your agent normally.")
    print("")
    print("How governance works:")
    print("")
    print("  The proxy evaluates every tool call against policy before it")
    print("  executes. Operations within your working directories are allowed")
    print("  by policy. Operations outside that scope — or opaque commands")
    print("  the proxy cannot inspect — are denied until you approve them.")
    print("")
    print("  Your first session will have the most approval prompts as the")
    print("  proxy encounters new tools and paths. After that, approvals")
    print("  should be rare. Each approval is you deciding what is acceptable")
    print("  in your environment.")
    print("")
    print("  Open the dashboard to see governance in action:")
    print("     python3 dashboard/server.py")
    print("     http://localhost:9700")
    print("")
    return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atested",
        description="Atested governance command-line interface",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON output (currently always JSON; reserved for future formats)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="First-run setup (create runtime, generate key, configure policy)")
    p_init.add_argument("--dirs", nargs="*", metavar="DIR",
                        help="Working directories for your AI agent (default: current directory)")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing configuration")
    p_init.set_defaults(func=cmd_init)

    p_status = sub.add_parser("status", help="Show governance status summary")
    p_status.add_argument("--window", type=int, default=None, help="Limit metrics to last N records")
    p_status.set_defaults(func=cmd_status)

    p_act = sub.add_parser("activity", help="Show recent governance activity")
    p_act.add_argument("--limit", type=int, default=50)
    p_act.add_argument("--offset", type=int, default=0)
    p_act.add_argument("--governed-family", dest="governed_family", default=None)
    p_act.add_argument("--event-category", dest="event_category", default=None)
    p_act.add_argument("--resolution", default=None)
    p_act.add_argument("--start-time", dest="start_time", default=None)
    p_act.add_argument("--end-time", dest="end_time", default=None)
    p_act.set_defaults(func=cmd_activity)

    p_appr = sub.add_parser("approvals", help="List active approvals")
    p_appr.set_defaults(func=cmd_approvals)

    p_approve = sub.add_parser("approve", help="Approve an artifact (record approval event)")
    p_approve.add_argument("artifact_identity", help="Artifact identity (sha256:... or content hash)")
    p_approve.add_argument("--operator", default="cli_operator", help="Approving operator name")
    p_approve.set_defaults(func=cmd_approve)

    p_revoke = sub.add_parser("revoke", help="Revoke an existing approval")
    p_revoke.add_argument("artifact_identity", help="Artifact identity to revoke")
    p_revoke.add_argument("--operator", default="cli_operator", help="Revoking operator name")
    p_revoke.set_defaults(func=cmd_revoke)

    p_policy = sub.add_parser("policy", help="Policy operations")
    policy_sub = p_policy.add_subparsers(dest="policy_command", required=True)
    p_policy_list = policy_sub.add_parser("list", help="List policy rules")
    p_policy_list.set_defaults(func=cmd_policy_list)

    p_chain = sub.add_parser("chain", help="Chain operations")
    chain_sub = p_chain.add_subparsers(dest="chain_command", required=True)
    p_chain_verify = chain_sub.add_parser("verify", help="Verify chain integrity")
    p_chain_verify.set_defaults(func=cmd_chain_verify)

    p_ver = sub.add_parser("verification", help="Show surface verification states")
    p_ver.add_argument("--governed-family", dest="governed_family", default=None)
    p_ver.set_defaults(func=cmd_verification)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
