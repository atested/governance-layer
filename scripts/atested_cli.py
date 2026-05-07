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
import signal
import stat as _stat
import subprocess
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
SIGNING_KEY_NAME = ".atested-signing-key.pem"
SYNC_CONFIG_NAME = "config.json"
SYNC_CLIENT_STATE_NAME = "client_state.json"
SYNC_DEGRADED_NAME = "degraded.json"
SUPERVISOR_DIR_NAME = "supervisor"


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


def _runtime() -> Path:
    return runtime_root(REPO)


def _chain_path() -> Path:
    return _runtime() / "LOGS" / "decision-chain.jsonl"


def _sync_dir() -> Path:
    return _runtime() / "sync"


def _sync_config_path() -> Path:
    return _sync_dir() / SYNC_CONFIG_NAME


def _sync_client_state_path() -> Path:
    return _sync_dir() / SYNC_CLIENT_STATE_NAME


def _sync_degraded_path() -> Path:
    return _sync_dir() / SYNC_DEGRADED_NAME


def _supervisor_dir() -> Path:
    return _runtime() / SUPERVISOR_DIR_NAME


def _services_path() -> Path:
    return _supervisor_dir() / "services.json"


def _write_json_file(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _read_json_file(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _load_private_key():
    from receipt_signing import _read_private_key

    explicit = str(os.environ.get("GOV_SIGNING_KEY_PATH", "")).strip()
    key_path = Path(explicit) if explicit else _runtime() / SIGNING_KEY_NAME
    private_key, serialization = _read_private_key(key_path)
    return private_key, serialization, key_path


def _public_key_pem(private_key, serialization) -> str:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _ensure_runtime_initialized(role: str, *, force: bool = False) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from machine_identity import ensure_machine_identity, ensure_primary_machine_registry
    from receipt_signing import _public_key_fingerprint

    runtime = _runtime()
    signing_key_path = runtime / SIGNING_KEY_NAME
    logs_dir = runtime / "LOGS"
    logs_dir.mkdir(parents=True, exist_ok=True)
    (runtime / "LOGS" / "records").mkdir(parents=True, exist_ok=True)

    created_key = False
    if force or not signing_key_path.exists():
        private_key = Ed25519PrivateKey.generate()
        pem_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        signing_key_path.write_bytes(pem_bytes)
        os.chmod(str(signing_key_path), 0o600)
        created_key = True
    else:
        private_key, serialization, _ = _load_private_key()

    key_id = _public_key_fingerprint(private_key.public_key(), serialization)
    identity = ensure_machine_identity(REPO, role=role, signing_key_id=key_id)
    if identity.get("machine_role") != role:
        raise ValueError(f"machine already initialized as {identity.get('machine_role')}, not {role}")
    public_pem = _public_key_pem(private_key, serialization)
    registry = None
    if role == "primary":
        registry = ensure_primary_machine_registry(
            REPO,
            identity=identity,
            public_key_fingerprint=key_id,
            public_key_pem=public_pem,
        )

    return {
        "identity": identity,
        "public_key_fingerprint": key_id,
        "public_key_pem": public_pem,
        "signing_key_path": str(signing_key_path),
        "created_signing_key": created_key,
        "registry": registry,
    }


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _load_services() -> dict:
    data = _read_json_file(_services_path(), {})
    return data if isinstance(data, dict) else {}


def _save_services(data: dict) -> None:
    _write_json_file(_services_path(), data)


def _start_service(name: str, argv: list[str], *, env_extra: dict | None = None) -> dict:
    services = _load_services()
    existing = services.get(name)
    if isinstance(existing, dict) and _pid_alive(int(existing.get("pid") or 0)):
        return existing
    log_dir = _supervisor_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    out = open(log_dir / f"{name}.out.log", "ab")
    err = open(log_dir / f"{name}.err.log", "ab")
    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(_runtime())
    env.setdefault("GOV_SIGNING_KEY_PATH", str(_runtime() / SIGNING_KEY_NAME))
    if env_extra:
        env.update(env_extra)
    proc = subprocess.Popen(
        argv,
        cwd=str(REPO),
        env=env,
        stdout=out,
        stderr=err,
        start_new_session=True,
    )
    out.close()
    err.close()
    record = {
        "name": name,
        "pid": proc.pid,
        "argv": argv,
        "started_utc": _now_utc_z(),
        "log_stdout": str(log_dir / f"{name}.out.log"),
        "log_stderr": str(log_dir / f"{name}.err.log"),
    }
    services[name] = record
    _save_services(services)
    return record


def _stop_service(name: str) -> dict:
    services = _load_services()
    record = services.get(name)
    if not isinstance(record, dict):
        return {"name": name, "stopped": False, "reason": "not_registered"}
    pid = int(record.get("pid") or 0)
    if not _pid_alive(pid):
        services.pop(name, None)
        _save_services(services)
        return {"name": name, "stopped": False, "reason": "not_running"}
    try:
        os.killpg(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = _time_mod.time() + 5
    while _time_mod.time() < deadline:
        if not _pid_alive(pid):
            break
        _time_mod.sleep(0.1)
    if _pid_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    services.pop(name, None)
    _save_services(services)
    return {"name": name, "stopped": True, "pid": pid}


def _now_utc_z() -> str:
    from machine_identity import now_utc_z

    return now_utc_z()


def _service_statuses() -> dict:
    statuses = {}
    for name, record in _load_services().items():
        if isinstance(record, dict):
            statuses[name] = {
                **record,
                "running": _pid_alive(int(record.get("pid") or 0)),
            }
    return statuses


def _set_sync_config(config: dict) -> dict:
    existing = _read_json_file(_sync_config_path(), {})
    if not isinstance(existing, dict):
        existing = {}
    merged = {
        **existing,
        **config,
        "updated_utc": _now_utc_z(),
    }
    _write_json_file(_sync_config_path(), merged)
    return merged


def _request_sync_trigger(trigger: str) -> None:
    path = _sync_dir() / "pending_triggers.json"
    data = _read_json_file(path, {})
    if not isinstance(data, dict):
        data = {}
    pending = data.setdefault("pending", [])
    pending.append({"trigger": trigger, "requested_utc": _now_utc_z()})
    data["updated_utc"] = _now_utc_z()
    _write_json_file(path, data)


def _mark_degraded(reason: str, *, detail: str = "") -> dict:
    data = {
        "degraded": True,
        "reason": reason,
        "detail": detail,
        "updated_utc": _now_utc_z(),
    }
    _write_json_file(_sync_degraded_path(), data)
    return data


def _clear_degraded() -> None:
    try:
        _sync_degraded_path().unlink()
    except FileNotFoundError:
        pass


def _read_chain_records() -> list[dict]:
    path = _chain_path()
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _pending_records() -> tuple[list[dict], dict]:
    state = _read_json_file(_sync_client_state_path(), {})
    if not isinstance(state, dict):
        state = {}
    records = _read_chain_records()
    synced_count = int(state.get("last_synced_line_count") or 0)
    if synced_count < 0 or synced_count > len(records):
        synced_count = 0
    return records[synced_count:], state


def _records_jsonl(records: list[dict]) -> bytes:
    return ("\n".join(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False) for record in records) + "\n").encode("utf-8")


def _update_sync_cursor(records: list[dict], response: dict) -> None:
    all_records = _read_chain_records()
    last_hash = records[-1].get("record_hash") if records else None
    state = {
        "last_successful_sync_utc": _now_utc_z(),
        "last_synced_line_count": len(all_records),
        "last_synced_record_hash": last_hash,
        "last_import_envelope_hash": response.get("import_envelope_hash"),
        "last_segment_id": response.get("segment_id"),
    }
    _write_json_file(_sync_client_state_path(), state)


def _machine_registry_summary() -> dict:
    from machine_identity import load_machine_registry

    registry = load_machine_registry(REPO)
    if not registry:
        return {"registry_present": False, "machines": []}
    machines = registry.get("machines", [])
    stale = [
        machine for machine in machines
        if machine.get("version_status") in {"stale", "stale_update_required", "protocol_incompatible"}
    ]
    return {
        "registry_present": True,
        "registry_hash": registry.get("registry_hash"),
        "machines": machines,
        "version_warnings": [
            {
                "machine_id": machine.get("machine_id"),
                "product_version": machine.get("product_version"),
                "sync_protocol_version": machine.get("sync_protocol_version"),
                "version_status": machine.get("version_status"),
                "minimum_supported_version": machine.get("minimum_supported_version"),
            }
            for machine in stale
        ],
    }


def _freshness_summary() -> dict:
    from approval_store import approval_store_hash
    from policy_eval_v2 import compute_policy_rules_hash

    bundle = _read_json_file(_sync_dir() / "state_bundle.json", {})
    policy_rules = _read_json_file(POLICY_RULES_PATH, {})
    if not isinstance(policy_rules, dict):
        policy_rules = {}
    return {
        "local_approval_store_hash": approval_store_hash(_load_approval_store()),
        "local_policy_rules_hash": compute_policy_rules_hash(policy_rules),
        "received_approval_store_hash": bundle.get("approval_store_hash") if isinstance(bundle, dict) else None,
        "received_policy_rules_hash": bundle.get("policy_rules_hash") if isinstance(bundle, dict) else None,
        "received_at_utc": bundle.get("received_at_utc") if isinstance(bundle, dict) else None,
    }


def _degraded_summary(identity: dict | None, sync_config: dict) -> dict:
    degraded = _read_json_file(_sync_degraded_path(), {})
    bundle = _read_json_file(_sync_dir() / "state_bundle.json", {})
    if isinstance(bundle, dict) and identity:
        registry = bundle.get("machine_registry") or {}
        for machine in registry.get("machines", []):
            if machine.get("machine_id") == identity.get("machine_id"):
                if machine.get("license_status") == "removed" or not machine.get("sync_authorized", True):
                    degraded = degraded or {}
                    degraded.update({
                        "degraded": True,
                        "reason": "machine_removed",
                        "detail": "primary registry no longer authorizes this remote",
                    })
    if not isinstance(degraded, dict):
        degraded = {}
    return {
        "degraded": bool(degraded.get("degraded")),
        "reason": degraded.get("reason"),
        "detail": degraded.get("detail"),
        "sync_enabled": bool(sync_config.get("sync_enabled", False)) and not bool(degraded.get("degraded")),
    }


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------


def cmd_status(args) -> int:
    from readout import assemble_governance_status_record
    from machine_identity import load_machine_identity

    data = assemble_governance_status_record(
        CHAIN,
        _load_verification_tracker(),
        _load_approval_store(),
        window=args.window,
    )
    identity = load_machine_identity(REPO)
    sync_config = _read_json_file(_sync_config_path(), {})
    if not isinstance(sync_config, dict):
        sync_config = {}
    pending, sync_state = _pending_records()
    machine = {
        "identity": identity,
        "role": (identity or {}).get("machine_role"),
        "runtime": str(_runtime()),
        "services": _service_statuses(),
        "sync": {
            "config": sync_config,
            "pending_records": len(pending),
            "last_successful_sync_utc": sync_state.get("last_successful_sync_utc") if isinstance(sync_state, dict) else None,
            "last_synced_record_hash": sync_state.get("last_synced_record_hash") if isinstance(sync_state, dict) else None,
            "freshness": _freshness_summary(),
        },
        "degraded_mode": _degraded_summary(identity, sync_config),
    }
    if (identity or {}).get("machine_role") == "primary":
        machine["registry"] = _machine_registry_summary()
    data["machine"] = machine
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
    _request_sync_trigger("approval_store_changed")
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
    _request_sync_trigger("approval_store_changed")
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
        public_key_pem = _public_key_pem(private_key, serialization)
        identity = ensure_machine_identity(REPO, role="primary", signing_key_id=key_id)
        ensure_primary_machine_registry(REPO, identity=identity, public_key_fingerprint=key_id, public_key_pem=public_key_pem)
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


def cmd_start(args) -> int:
    role = str(args.role or "primary").strip().lower()
    if role not in {"primary", "remote"}:
        print("error: role must be primary or remote", file=sys.stderr)
        return 2
    if role == "remote" and not args.primary_url:
        print("error: remote start requires --primary-url", file=sys.stderr)
        return 2
    try:
        bootstrap = _ensure_runtime_initialized(role, force=bool(args.force))
    except Exception as exc:
        print(f"error: failed to initialize runtime: {exc}", file=sys.stderr)
        return 1

    identity = bootstrap["identity"]
    services = {}
    sync_config = {
        "machine_role": role,
        "sync_enabled": role == "remote",
        "primary_url": args.primary_url if role == "remote" else None,
        "baseline_interval_seconds": int(args.sync_interval),
    }
    if role == "remote":
        sync_config["join_status"] = "pending_primary_confirmation"
        sync_config["remote_public_key_fingerprint"] = bootstrap["public_key_fingerprint"]
        sync_config["remote_public_key_pem"] = bootstrap["public_key_pem"]
    else:
        sync_config["sync_service_host"] = args.sync_host
        sync_config["sync_service_port"] = int(args.sync_port)
    sync_config = _set_sync_config(sync_config)
    _clear_degraded()

    if not args.no_services:
        if role == "primary":
            services["proxy"] = _start_service("proxy", [sys.executable, "-m", "proxy.server"])
            services["dashboard"] = _start_service("dashboard", [sys.executable, "dashboard/server.py"])
            services["sync_service"] = _start_service(
                "sync_service",
                [sys.executable, "scripts/sync_service.py", "--host", args.sync_host, "--port", str(args.sync_port)],
            )
        else:
            services["proxy"] = _start_service("proxy", [sys.executable, "-m", "proxy.server"])
            # The v1 remote client is event/manual driven. This lifecycle marker
            # lets status/stop treat it as enabled without requiring a polling daemon.
            services["sync_client"] = {
                "name": "sync_client",
                "pid": None,
                "running": False,
                "mode": "manual_or_triggered",
                "started_utc": _now_utc_z(),
            }
            saved = _load_services()
            saved["sync_client"] = services["sync_client"]
            _save_services(saved)

    _emit(args, {
        "started": True,
        "role": role,
        "runtime": str(_runtime()),
        "machine_id": identity.get("machine_id"),
        "public_key_fingerprint": bootstrap["public_key_fingerprint"],
        "public_key_pem": bootstrap["public_key_pem"],
        "sync_config": sync_config,
        "services": services or _service_statuses(),
        "operator_action_required": (
            "confirm this remote on the primary with atested machine add"
            if role == "remote" else None
        ),
    })
    return 0


def cmd_stop(args) -> int:
    identity = None
    try:
        from machine_identity import load_machine_identity
        identity = load_machine_identity(REPO)
    except Exception:
        identity = None
    names = list(_load_services().keys())
    stopped = [_stop_service(name) for name in names]
    _emit(args, {
        "stopped": True,
        "role": (identity or {}).get("machine_role"),
        "services": stopped,
    })
    return 0


def cmd_sync(args) -> int:
    from machine_identity import load_machine_identity
    from sync_client import SyncClient, SyncClientError

    identity = load_machine_identity(REPO)
    role = (identity or {}).get("machine_role")
    config = _read_json_file(_sync_config_path(), {})
    if not isinstance(config, dict):
        config = {}
    if role == "primary":
        trigger_path = _sync_dir() / "manual_trigger.json"
        _write_json_file(trigger_path, {"trigger": "manual", "requested_utc": _now_utc_z()})
        _emit(args, {"sync_requested": True, "role": "primary", "trigger_path": str(trigger_path)})
        return 0
    if role != "remote":
        print("error: machine is not initialized as a remote", file=sys.stderr)
        return 1
    degraded = _degraded_summary(identity, config)
    if degraded["degraded"]:
        _emit(args, {"synced": False, "role": "remote", "degraded_mode": degraded})
        return 1
    primary_url = str(args.primary_url or config.get("primary_url") or "").strip()
    if not primary_url:
        print("error: no primary URL configured; pass --primary-url", file=sys.stderr)
        return 2
    pending, _state = _pending_records()
    if not pending:
        _emit(args, {"synced": True, "role": "remote", "pending_records": 0, "message": "no pending records"})
        return 0
    try:
        private_key, _serialization, _key_path = _load_private_key()
        primary_public_key_pem = str(config.get("primary_public_key_pem") or "").strip() or None
        client = SyncClient(
            REPO,
            primary_url,
            remote_private_key=private_key,
            source_machine_id=identity.get("machine_id"),
            primary_public_key_pem=primary_public_key_pem,
            timeout_seconds=int(args.timeout),
        )
        response = client.sync_current_segment(_records_jsonl(pending))
        client.finish_session()
        _update_sync_cursor(pending, response)
        _clear_degraded()
        _set_sync_config({"primary_url": primary_url, "sync_enabled": True, "join_status": "confirmed_or_syncing"})
    except SyncClientError as exc:
        detail = str(exc)
        degraded_data = None
        if "MACHINE_NOT_AUTHORIZED" in detail:
            degraded_data = _mark_degraded("machine_not_authorized", detail=detail)
            _set_sync_config({"sync_enabled": False})
        print(f"error: sync failed: {detail}", file=sys.stderr)
        _emit(args, {"synced": False, "role": "remote", "error": detail, "degraded_mode": degraded_data})
        return 1
    except Exception as exc:
        print(f"error: sync failed: {exc}", file=sys.stderr)
        return 1

    _emit(args, {
        "synced": True,
        "role": "remote",
        "pending_records": len(pending),
        "segment_id": response.get("segment_id"),
        "import_envelope_hash": response.get("import_envelope_hash"),
        "approval_store_hash": response.get("approval_store_hash"),
        "policy_rules_hash": response.get("policy_rules_hash"),
    })
    return 0


def cmd_machine_list(args) -> int:
    _emit(args, _machine_registry_summary())
    return 0


def cmd_machine_add(args) -> int:
    if not args.confirm:
        print("error: --confirm is required for primary-side local operator confirmation", file=sys.stderr)
        return 2
    from machine_identity import add_machine_to_registry, ensure_machine_identity, ensure_primary_machine_registry
    from receipt_signing import _public_key_fingerprint

    try:
        private_key, serialization, _ = _load_private_key()
        identity = ensure_machine_identity(REPO, role="primary")
        primary_key_id = _public_key_fingerprint(private_key.public_key(), serialization)
        ensure_primary_machine_registry(
            REPO,
            identity=identity,
            public_key_fingerprint=primary_key_id,
            public_key_pem=_public_key_pem(private_key, serialization),
        )
        public_key_pem = args.public_key_pem or ""
        if args.public_key_pem_file:
            public_key_pem = Path(args.public_key_pem_file).read_text(encoding="utf-8")
        registry, event = add_machine_to_registry(
            REPO,
            machine_id=args.machine_id,
            role="remote",
            display_name=args.display_name or args.machine_id,
            public_key_fingerprint=args.public_key_fingerprint,
            public_key_pem=public_key_pem,
            operator_confirmation_event_id=f"cli-confirm:{args.operator}",
            append_event=_append_chain_record_atomic,
        )
    except Exception as exc:
        print(f"error: machine add failed: {exc}", file=sys.stderr)
        return 1
    _emit(args, {
        "added": True,
        "machine_id": args.machine_id,
        "registry_hash": registry.get("registry_hash"),
        "event_id": event.get("event_id") if isinstance(event, dict) else None,
    })
    return 0


def cmd_machine_remove(args) -> int:
    from machine_identity import remove_machine_from_registry

    try:
        registry, event = remove_machine_from_registry(
            REPO,
            args.machine_id,
            reason=args.reason or "operator removal",
            append_event=_append_chain_record_atomic,
        )
    except Exception as exc:
        print(f"error: machine remove failed: {exc}", file=sys.stderr)
        return 1
    _emit(args, {
        "removed": True,
        "machine_id": args.machine_id,
        "registry_hash": registry.get("registry_hash"),
        "event_id": event.get("event_id") if isinstance(event, dict) else None,
    })
    return 0


def cmd_restore_verify(args) -> int:
    from multi_machine_ops import validate_primary_restore_runtime

    runtime = Path(args.runtime).expanduser().resolve() if args.runtime else _runtime()
    result = validate_primary_restore_runtime(REPO, runtime=runtime)
    _emit(args, result)
    return 0 if result.get("restore_runtime_valid") else 1


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

    p_start = sub.add_parser("start", help="Start Atested governance services")
    p_start.add_argument("--role", choices=["primary", "remote"], default="primary")
    p_start.add_argument("--primary-url", default=None, help="Primary sync service URL for remote role")
    p_start.add_argument("--sync-host", default="127.0.0.1")
    p_start.add_argument("--sync-port", type=int, default=8765)
    p_start.add_argument("--sync-interval", type=int, default=300)
    p_start.add_argument("--force", action="store_true", help="Regenerate local runtime key during start")
    p_start.add_argument("--no-services", action="store_true", help="Initialize lifecycle state without launching background services")
    p_start.set_defaults(func=cmd_start)

    p_stop = sub.add_parser("stop", help="Stop Atested governance services")
    p_stop.set_defaults(func=cmd_stop)

    p_sync = sub.add_parser("sync", help="Run or request sync")
    p_sync.add_argument("--primary-url", default=None, help="Override configured primary sync service URL")
    p_sync.add_argument("--timeout", type=int, default=10)
    p_sync.set_defaults(func=cmd_sync)

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

    p_machine = sub.add_parser("machine", help="Machine registry operations")
    machine_sub = p_machine.add_subparsers(dest="machine_command", required=True)
    p_machine_list = machine_sub.add_parser("list", help="List registered machines")
    p_machine_list.set_defaults(func=cmd_machine_list)
    p_machine_add = machine_sub.add_parser("add", help="Confirm and add a remote machine to the primary registry")
    p_machine_add.add_argument("--machine-id", required=True)
    p_machine_add.add_argument("--display-name", default=None)
    p_machine_add.add_argument("--public-key-fingerprint", required=True)
    p_machine_add.add_argument("--public-key-pem", default=None)
    p_machine_add.add_argument("--public-key-pem-file", default=None)
    p_machine_add.add_argument("--operator", default="cli_operator")
    p_machine_add.add_argument("--confirm", action="store_true", help="Confirm this remote should be authorized")
    p_machine_add.set_defaults(func=cmd_machine_add)
    p_machine_remove = machine_sub.add_parser("remove", help="Remove a remote from future sync authorization")
    p_machine_remove.add_argument("machine_id")
    p_machine_remove.add_argument("--reason", default="operator removal")
    p_machine_remove.set_defaults(func=cmd_machine_remove)

    p_restore = sub.add_parser("restore", help="Primary restore operations")
    restore_sub = p_restore.add_subparsers(dest="restore_command", required=True)
    p_restore_verify = restore_sub.add_parser("verify", help="Validate a restored primary gov_runtime")
    p_restore_verify.add_argument("--runtime", default=None, help="Runtime directory to validate (default: configured gov_runtime)")
    p_restore_verify.set_defaults(func=cmd_restore_verify)

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
