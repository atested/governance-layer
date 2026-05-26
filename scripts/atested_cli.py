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
  init          First-run setup
  start         Start governance services
  stop          Stop governance services
  sync          Run or request sync
  machine       Machine registry operations
  restore       Primary restore operations
  uninstall     Remove Atested from this machine
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import stat as _stat
import subprocess
import sys
import threading
import time as _time_mod
from pathlib import Path
from typing import Optional

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
OPERATOR_CONFIG_NAME = "operator.json"


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
    from machine_identity import add_machine_identity_fields, add_record_freshness_fields

    CHAIN.parent.mkdir(parents=True, exist_ok=True)
    with _chain_lock:
        lockdir = _acquire_chain_file_lock()
        try:
            add_machine_identity_fields(event, REPO)
            add_record_freshness_fields(event, REPO)
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
    from approval_store import load_approval_store_from_runtime

    return load_approval_store_from_runtime(str(CHAIN))


def _load_verification_tracker():
    from verification import VerificationStateTracker, load_verification_state_from_chain

    if CHAIN.exists():
        return load_verification_state_from_chain(str(CHAIN))
    return VerificationStateTracker()


def _emit(args, data) -> None:
    """Print result as JSON when requested."""
    if getattr(args, "json", False):
        print(json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def _flush_terminal_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except OSError:
            pass


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


def _operator_config_path() -> Path:
    return _runtime() / OPERATOR_CONFIG_NAME


def _supervisor_dir() -> Path:
    return _runtime() / SUPERVISOR_DIR_NAME


def _services_path() -> Path:
    return _supervisor_dir() / "services.json"


def _supervisor_pid_path() -> Path:
    return _supervisor_dir() / "supervisor.pid"


def _supervisor_status_path() -> Path:
    return _supervisor_dir() / "status.json"


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


def _default_operator_identity() -> str:
    import getpass as _getpass

    return (
        str(os.environ.get("ATESTED_USER_LABEL", "")).strip()
        or _getpass.getuser()
        or os.environ.get("USER", "")
        or "operator"
    )


def _load_operator_config() -> dict:
    data = _read_json_file(_operator_config_path(), {})
    return data if isinstance(data, dict) else {}


def _save_operator_config(user_identity: str) -> dict:
    config = {
        "user_identity": user_identity,
        "updated_utc": _now_utc_z(),
    }
    _write_json_file(_operator_config_path(), config)
    return config


def _configured_operator_identity(args=None) -> str:
    from_args = str(getattr(args, "user_identity", "") or "").strip() if args is not None else ""
    if from_args:
        return from_args
    existing = str(_load_operator_config().get("user_identity") or "").strip()
    if existing:
        return existing
    return _default_operator_identity()


def _runtime_initialized() -> bool:
    return (_runtime() / SIGNING_KEY_NAME).exists()


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


def _ensure_runtime_initialized(role: str, *, force: bool = False, display_name: str | None = None) -> dict:
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
    identity = ensure_machine_identity(REPO, role=role, display_name=display_name, signing_key_id=key_id)
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
    except OSError:
        return False
    if os.name != "nt":
        try:
            result = subprocess.run(
                ["ps", "-p", str(pid), "-o", "stat="],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode != 0:
                return True
            state = (result.stdout or "").strip()
            if state.startswith("Z"):
                return False
        except (OSError, subprocess.TimeoutExpired):
            pass
    return True


def _read_supervisor_pid_record() -> dict | None:
    try:
        raw = _supervisor_pid_path().read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            return {"pid": int(raw), "token": "", "runtime": ""}
        except ValueError:
            return None
    if not isinstance(data, dict):
        return None
    pid = data.get("pid")
    if not isinstance(pid, int):
        return None
    return data


def _read_supervisor_pid() -> int | None:
    record = _read_supervisor_pid_record()
    if not record:
        return None
    return int(record.get("pid") or 0) or None


def _pid_command_matches(pid: int, token: str) -> bool:
    if os.name == "nt":
        return True
    ps_failed = False
    try:
        result = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        ps_failed = True
        result = None
    if result is not None:
        command = (result.stdout or "").strip()
        if result.returncode == 0 and command:
            return (
                "process_supervisor.py" in command
                and str(_runtime()) in command
                and token in command
            )
        ps_failed = True
    if not ps_failed:
        return False
    # Some locked-down macOS/Python environments cannot read process command
    # lines. Fall back to the supervisor heartbeat only when the pid, token,
    # runtime, and heartbeat freshness all agree.
    status = _read_json_file(_supervisor_status_path(), {})
    supervisor = status.get("supervisor") if isinstance(status, dict) else {}
    if not isinstance(supervisor, dict):
        return False
    if int(supervisor.get("pid") or 0) != pid:
        return False
    if str(supervisor.get("token") or "") != token:
        return False
    runtime = str(supervisor.get("runtime") or "")
    try:
        if Path(runtime).expanduser().resolve() != _runtime().resolve():
            return False
    except OSError:
        return False
    updated = _parse_utc_epoch(str(status.get("updated_utc") or ""))
    return updated is not None and (_time_mod.time() - updated) <= 15


def _parse_utc_epoch(value: str) -> Optional[float]:
    if not value:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).timestamp()
    except ValueError:
        return None


def _supervisor_record_valid(record: dict | None) -> bool:
    if not isinstance(record, dict):
        return False
    pid = int(record.get("pid") or 0)
    token = str(record.get("token") or "")
    runtime = str(record.get("runtime") or "")
    if not pid or not token or not runtime:
        return False
    try:
        if Path(runtime).expanduser().resolve() != _runtime().resolve():
            return False
    except OSError:
        return False
    if not _pid_alive(pid):
        return False

    status = _read_json_file(_supervisor_status_path(), {})
    supervisor = status.get("supervisor") if isinstance(status, dict) else None
    if isinstance(supervisor, dict) and supervisor:
        status_pid = int(supervisor.get("pid") or 0)
        if status_pid in (0, pid):
            status_token = str(supervisor.get("token") or "")
            if status_token and status_token != token:
                return False
            status_runtime = str(supervisor.get("runtime") or "")
            if status_runtime and Path(status_runtime).expanduser().resolve() != _runtime().resolve():
                return False
        # Accept a fresh heartbeat as proof the supervisor is ours,
        # even when ps-based command-line matching is unavailable.
        if (
            status_pid == pid
            and str(supervisor.get("token") or "") == token
            and supervisor.get("running")
        ):
            updated = _parse_utc_epoch(str(status.get("updated_utc") or ""))
            if updated is not None and (_time_mod.time() - updated) <= 15:
                return True

    return _pid_command_matches(pid, token)


def _supervisor_status() -> dict:
    status = _read_json_file(_supervisor_status_path(), {})
    if not isinstance(status, dict):
        status = {}
    supervisor_data = status.get("supervisor")
    if not isinstance(supervisor_data, dict):
        supervisor_data = {}
    pid_record = _read_supervisor_pid_record()
    pid_record_pid = int((pid_record or {}).get("pid") or 0)
    status_pid = int(supervisor_data.get("pid") or 0)
    if pid_record_pid and status_pid and status_pid != pid_record_pid:
        supervisor_data = {}
        status["services"] = {}
    running = _supervisor_record_valid(pid_record)
    pid = int(supervisor_data.get("pid") or pid_record_pid or 0)
    supervisor = dict(supervisor_data)
    if pid:
        supervisor["pid"] = pid
    supervisor.pop("token", None)
    supervisor["running"] = running
    supervisor.setdefault("pid_file", str(_supervisor_pid_path()))
    supervisor.setdefault("status_path", str(_supervisor_status_path()))
    status["supervisor"] = supervisor
    return status


def _supervisor_running() -> bool:
    return _supervisor_record_valid(_read_supervisor_pid_record())


def _detach_popen_kwargs() -> dict:
    if os.name == "nt":
        flags = 0
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        return {"creationflags": flags} if flags else {}
    return {"start_new_session": True}


def _start_supervisor(role: str, *, sync_host: str, sync_port: int) -> dict:
    if _supervisor_running():
        status = _supervisor_status()
        supervisor = status.get("supervisor", {})
        supervisor["already_running"] = True
        return supervisor

    token = secrets.token_urlsafe(32)
    log_dir = _supervisor_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    _write_json_file(_services_path(), {})
    out = open(log_dir / "supervisor.out.log", "ab")
    err = open(log_dir / "supervisor.err.log", "ab")
    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(_runtime())
    env.setdefault("GOV_SIGNING_KEY_PATH", str(_runtime() / SIGNING_KEY_NAME))
    operator = _load_operator_config()
    if operator.get("user_identity"):
        env["ATESTED_USER_LABEL"] = str(operator["user_identity"])
    argv = [
        sys.executable,
        "scripts/process_supervisor.py",
        "--runtime",
        str(_runtime()),
        "--role",
        role,
        "--sync-host",
        sync_host,
        "--sync-port",
        str(sync_port),
        "--token",
        token,
    ]
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(REPO),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=err,
            **_detach_popen_kwargs(),
        )
    finally:
        out.close()
        err.close()
    pid_record = {
        "pid": proc.pid,
        "token": token,
        "runtime": str(_runtime()),
        "created_utc": _now_utc_z(),
    }
    _write_json_file(_supervisor_pid_path(), pid_record)
    _write_json_file(_supervisor_status_path(), {
        "supervisor": {
            "pid": proc.pid,
            "token": token,
            "runtime": str(_runtime()),
            "running": True,
            "role": role,
            "started_utc": pid_record["created_utc"],
            "uptime_seconds": 0,
            "pid_file": str(_supervisor_pid_path()),
            "status_path": str(_supervisor_status_path()),
            "log_dir": str(log_dir),
        },
        "services": {},
        "updated_utc": pid_record["created_utc"],
    })
    deadline = _time_mod.time() + 2.0
    while _time_mod.time() < deadline:
        status = _read_json_file(_supervisor_status_path(), {})
        supervisor = status.get("supervisor") if isinstance(status, dict) else {}
        services = status.get("services") if isinstance(status, dict) else {}
        if (
            isinstance(supervisor, dict)
            and int(supervisor.get("pid") or 0) == proc.pid
            and isinstance(services, dict)
            and services
        ):
            break
        _time_mod.sleep(0.1)
    return {
        "pid": proc.pid,
        "running": True,
        "role": role,
        "started_utc": _now_utc_z(),
        "pid_file": str(_supervisor_pid_path()),
        "status_path": str(_supervisor_status_path()),
        "log_stdout": str(log_dir / "supervisor.out.log"),
        "log_stderr": str(log_dir / "supervisor.err.log"),
        "already_running": False,
    }


def _clear_supervisor_status_files() -> None:
    """Remove stale status and services files so the next ``status``
    command does not report PIDs or uptime from a previous session."""
    for path in (_supervisor_status_path(), _services_path()):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _stop_supervisor() -> dict:
    record = _read_supervisor_pid_record()
    pid = int(record.get("pid") or 0) if record else None
    if not pid or not _pid_alive(pid):
        try:
            _supervisor_pid_path().unlink()
        except FileNotFoundError:
            pass
        # Clear stale status so a subsequent ``status`` command does not
        # report old PIDs or impossible uptime values.
        _clear_supervisor_status_files()
        return {"stopped": False, "reason": "not_running", "pid": pid}
    if not _supervisor_record_valid(record):
        return {"stopped": False, "reason": "supervisor_identity_mismatch", "pid": pid}
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _clear_supervisor_status_files()
        return {"stopped": False, "reason": "not_running", "pid": pid}
    deadline = _time_mod.time() + 10
    while _time_mod.time() < deadline:
        if not _pid_alive(pid):
            break
        _time_mod.sleep(0.1)
    if _pid_alive(pid) and hasattr(signal, "SIGKILL"):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    stopped = not _pid_alive(pid)
    if stopped:
        _clear_supervisor_status_files()
    return {"stopped": stopped, "pid": pid}


def _terminate_pid(pid: int, *, timeout: float = 5.0) -> bool:
    if not pid or not _pid_alive(pid):
        return True
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = _time_mod.time() + timeout
    while _time_mod.time() < deadline:
        if not _pid_alive(pid):
            return True
        _time_mod.sleep(0.1)
    if _pid_alive(pid) and hasattr(signal, "SIGKILL"):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return True
    deadline = _time_mod.time() + 2.0
    while _time_mod.time() < deadline:
        if not _pid_alive(pid):
            return True
        _time_mod.sleep(0.1)
    return not _pid_alive(pid)


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
    stopped = _terminate_pid(pid)
    services.pop(name, None)
    _save_services(services)
    return {"name": name, "stopped": stopped, "pid": pid}


def _collect_recorded_services() -> dict:
    collected: dict[str, dict] = {}
    for source in (_load_services(), (_read_json_file(_supervisor_status_path(), {}) or {}).get("services", {})):
        if not isinstance(source, dict):
            continue
        for name, record in source.items():
            if isinstance(record, dict):
                collected[str(name)] = dict(record)
    return collected


def _stop_recorded_services(records: Optional[dict] = None) -> list[dict]:
    records = records if isinstance(records, dict) else _collect_recorded_services()
    stopped: list[dict] = []
    for name, record in sorted(records.items()):
        if not isinstance(record, dict):
            continue
        pid = int(record.get("pid") or 0)
        stopped.append({
            "name": name,
            "pid": pid,
            "stopped": _terminate_pid(pid) if pid else True,
        })
    _save_services({})
    return stopped


def _now_utc_z() -> str:
    from machine_identity import now_utc_z

    return now_utc_z()


def _service_statuses() -> dict:
    status = _supervisor_status()
    # Prefer services from the status file (written by the running
    # supervisor). Fall back to the standalone services.json only when
    # the status file has no service entries at all.
    services = status.get("services")
    if not isinstance(services, dict) or not services:
        services = _load_services()
    statuses = {}
    for name, record in services.items():
        if isinstance(record, dict):
            pid = int(record.get("pid") or 0)
            statuses[name] = {
                **record,
                "running": _pid_alive(pid) if pid else False,
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


def _profile_path_for_shell(shell_path: str | None = None, home: Path | None = None) -> Path | None:
    shell = Path(shell_path or os.environ.get("SHELL", "")).name
    home_dir = home or Path.home()
    if shell == "zsh":
        return home_dir / ".zshrc"
    if shell == "bash":
        return home_dir / ".bash_profile"
    return None


PROXY_ROUTE_EXPORTS = (
    ("ANTHROPIC_BASE_URL", "http://localhost:8080/anthropic"),
    ("OPENAI_BASE_URL", "http://localhost:8080/openai"),
    ("GEMINI_BASE_URL", "http://localhost:8080/gemini"),
)


def _proxy_route_lines() -> list[str]:
    return [f"export {name}={value}" for name, value in PROXY_ROUTE_EXPORTS]


def _profile_display_path(profile_path: Path) -> str:
    try:
        home = Path.home().resolve()
        resolved = profile_path.resolve()
        if resolved.parent == home:
            return f"~/{resolved.name}"
    except OSError:
        pass
    return str(profile_path)


def _write_prompt(prompt: str) -> str:
    """Write prompt to stdout and read one line from stdin."""
    try:
        os.write(sys.stdout.fileno(), prompt.encode("utf-8", errors="replace"))
    except OSError:
        sys.stdout.write(prompt)
        sys.stdout.flush()
    return sys.stdin.readline().strip()


def _write_terminal(text: str) -> None:
    """Write text to stdout immediately.

    The start path must be observable through redirected stdout as well as an
    interactive terminal, so this helper intentionally avoids terminal-device
    side channels.
    """
    data = text.encode("utf-8", errors="replace")
    try:
        os.write(sys.stdout.fileno(), data)
    except OSError:
        sys.stdout.write(text)
        sys.stdout.flush()


def _write_terminal_line(text: str) -> None:
    _write_terminal(text.rstrip("\n") + "\n")


def _configure_provider_base_urls(profile_path: Path) -> dict:
    begin_marker = "# Atested proxy endpoints"
    old_marker = "# Atested proxy endpoint"
    route_lines = _proxy_route_lines()
    existing = ""
    try:
        existing = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        profile_path.parent.mkdir(parents=True, exist_ok=True)

    lines = existing.splitlines()
    cleaned: list[str] = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped in {begin_marker, old_marker}:
            i += 1
            while i < len(lines) and (
                lines[i].strip().startswith("export ANTHROPIC_BASE_URL=")
                or lines[i].strip().startswith("export OPENAI_BASE_URL=")
                or lines[i].strip().startswith("export GEMINI_BASE_URL=")
            ):
                i += 1
            continue
        if (
            stripped.startswith("export ANTHROPIC_BASE_URL=")
            or stripped.startswith("export OPENAI_BASE_URL=")
            or stripped.startswith("export GEMINI_BASE_URL=")
        ):
            i += 1
            continue
        cleaned.append(lines[i])
        i += 1

    block = [begin_marker, *route_lines]
    new_lines = cleaned
    if new_lines and new_lines[-1].strip():
        new_lines.append("")
    new_lines.extend(block)
    new_text = "\n".join(new_lines).rstrip() + "\n"
    if new_text == existing:
        return {
            "updated": False,
            "profile": str(profile_path),
            "profile_display": _profile_display_path(profile_path),
            "reason": "already_present",
            "routes": dict(PROXY_ROUTE_EXPORTS),
        }
    try:
        profile_path.write_text(new_text, encoding="utf-8")
    except OSError as exc:
        return {
            "updated": False,
            "profile": str(profile_path),
            "profile_display": _profile_display_path(profile_path),
            "reason": "write_failed",
            "error": str(exc),
            "routes": dict(PROXY_ROUTE_EXPORTS),
        }
    return {
        "updated": True,
        "profile": str(profile_path),
        "profile_display": _profile_display_path(profile_path),
        "routes": dict(PROXY_ROUTE_EXPORTS),
    }


def _remove_shell_profile_entry(profile_path: Path) -> dict:
    """Remove provider base URL lines added by ``atested init``."""
    markers = {"# Atested proxy endpoint", "# Atested proxy endpoints"}
    try:
        text = profile_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"removed": False, "reason": "profile_not_found"}
    except OSError as exc:
        return {
            "removed": False,
            "profile": str(profile_path),
            "profile_display": _profile_display_path(profile_path),
            "reason": "read_failed",
            "error": str(exc),
        }
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    i = 0
    found = False
    while i < len(lines):
        stripped = lines[i].rstrip("\n")
        if stripped in markers:
            found = True
            i += 1
            while i < len(lines) and (
                "ANTHROPIC_BASE_URL" in lines[i]
                or "OPENAI_BASE_URL" in lines[i]
                or "GEMINI_BASE_URL" in lines[i]
            ):
                i += 1
            continue
        new_lines.append(lines[i])
        i += 1
    if not found:
        return {"removed": False, "profile": str(profile_path), "reason": "marker_not_found"}
    try:
        profile_path.write_text("".join(new_lines), encoding="utf-8")
    except OSError as exc:
        return {
            "removed": False,
            "profile": str(profile_path),
            "profile_display": _profile_display_path(profile_path),
            "reason": "write_failed",
            "error": str(exc),
        }
    return {"removed": True, "profile": str(profile_path)}


def _clean_runtime_ephemeral(runtime: Path) -> list[str]:
    """Remove transient artifacts from *runtime* while preserving chain data and keys."""
    import shutil as _shutil

    ephemeral = [
        runtime / "supervisor",
        runtime / "tmp",
    ]
    # Lock directories under LOGS
    logs = runtime / "LOGS"
    if logs.is_dir():
        for child in logs.iterdir():
            if child.name.endswith(".lock.d"):
                ephemeral.append(child)
    cleaned: list[str] = []
    for p in ephemeral:
        if not p.exists():
            continue
        try:
            if p.is_dir():
                _shutil.rmtree(str(p))
            else:
                p.unlink()
            cleaned.append(str(p))
        except OSError:
            pass
    return cleaned


def _configure_shell_profile(args) -> dict:
    if getattr(args, "no_shell_profile", False):
        return {"offered": False, "updated": False, "reason": "disabled_by_flag"}
    profile_path = _profile_path_for_shell()
    if profile_path is None:
        return {"offered": False, "updated": False, "reason": "unsupported_shell"}
    result = _configure_provider_base_urls(profile_path)
    result["offered"] = True
    return result


def _collect_base_dirs(args) -> list[str]:
    base_dirs = ["__GOV_CANONICAL_REPO_PATH__", "__GOV_RUNTIME_PATH__"]
    dirs_arg = getattr(args, "dirs", None)
    repo_default = str(REPO.resolve())
    if dirs_arg:
        candidates = dirs_arg
    elif sys.stdin.isatty():
        raw = _write_prompt(f"Working directories to govern [default: {repo_default}]: ")
        candidates = [part.strip() for part in raw.split(",") if part.strip()] if raw else [repo_default]
    else:
        candidates = [repo_default]
    for directory in candidates:
        resolved = str(Path(directory).expanduser().resolve())
        if resolved != str(REPO.resolve()) and resolved not in base_dirs:
            base_dirs.append(resolved)
    return base_dirs


def _collect_operator_identity(args) -> str:
    provided = str(getattr(args, "user_identity", "") or "").strip()
    if provided:
        return provided
    default_identity = _configured_operator_identity()
    if sys.stdin.isatty():
        answer = _write_prompt(f"Operator identity [{default_identity}]: ")
        return answer or default_identity
    return default_identity


def _configure_policy_base_dirs(base_dirs: list[str]) -> None:
    policy_data = json.loads(POLICY_RULES_PATH.read_text(encoding="utf-8"))
    if policy_data.get("base_dirs") == base_dirs:
        return
    policy_data["base_dirs"] = base_dirs
    POLICY_RULES_PATH.write_text(
        json.dumps(policy_data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _print_first_run_guidance() -> None:
    print("")
    print("What happens next:")
    print("")
    print("  1. Restart your terminal or source your shell profile.")
    print("")
    print("  2. Use your agent normally.")
    print("")
    print("How governance works:")
    print("")
    print("  The proxy evaluates every tool call against policy before it")
    print("  executes. Operations within your working directories are allowed")
    print("  by policy. Operations outside that scope — or opaque commands")
    print("  the proxy cannot inspect — are denied until you approve them.")
    print("")
    print("  Open the dashboard to see governance in action:")
    print("     http://localhost:9700")
    print("")


def _print_proxy_routes(profile_result: dict) -> None:
    if profile_result.get("reason") in {"unsupported_shell", "disabled_by_flag"}:
        return
    print("Configured proxy routes:")
    for name, value in PROXY_ROUTE_EXPORTS:
        print(f"  {name}={value}")
    profile = profile_result.get("profile_display") or profile_result.get("profile")
    if profile:
        if profile_result.get("reason") == "write_failed":
            print(f"  Could not add to {profile}: {profile_result.get('error')}")
        else:
            print(f"  Added to {profile}")
    print("")


def _print_status_summary(data: dict) -> None:
    machine = data.get("machine", {}) if isinstance(data, dict) else {}
    supervisor = machine.get("supervisor", {}) if isinstance(machine, dict) else {}
    services = machine.get("services", {}) if isinstance(machine, dict) else {}
    sync = machine.get("sync", {}) if isinstance(machine, dict) else {}
    chain_health = data.get("chain_integrity", "unknown")
    if isinstance(chain_health, dict):
        chain_health = f"broken at {chain_health.get('broken_at', '?')}"
    print("Atested status")
    print(f"  Role:       {machine.get('role') or 'uninitialized'}")
    print(f"  Runtime:    {machine.get('runtime') or _runtime()}")
    print(f"  Supervisor: {'running' if supervisor.get('running') else 'stopped'}"
          f"{' pid ' + str(supervisor.get('pid')) if supervisor.get('pid') else ''}")
    print(f"  Chain:      {chain_health} ({data.get('chain_event_count', 0)} records)")
    if services:
        print("  Services:")
        for name, record in sorted(services.items()):
            svc_status = "running" if record.get("running") else "stopped"
            pid = f" pid {record.get('pid')}" if record.get("pid") else ""
            # Compute live uptime from started_utc when possible.
            uptime = int(record.get("uptime_seconds") or 0)
            started = _parse_utc_epoch(str(record.get("started_utc") or ""))
            if started is not None and record.get("running"):
                uptime = max(0, int(_time_mod.time() - started))
            print(f"    {name}: {svc_status}{pid} uptime {uptime}s")
    pending = sync.get("pending_records", 0) if isinstance(sync, dict) else 0
    last_sync = sync.get("last_successful_sync_utc") if isinstance(sync, dict) else None
    print(f"  Sync:       {pending} pending"
          f"{' last ' + str(last_sync) if last_sync else ''}")


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


def _print_uninstall_summary(result: dict) -> None:
    print("Atested uninstall")
    print(f"  Status: {'complete' if result.get('uninstalled') else 'incomplete'}")
    steps = result.get("steps", {}) if isinstance(result, dict) else {}

    stop = steps.get("stop", {}) if isinstance(steps, dict) else {}
    if stop:
        if stop.get("stopped"):
            stop_status = "stopped"
        else:
            stop_status = stop.get("reason") or "not_running"
        pid = f" pid {stop.get('pid')}" if stop.get("pid") else ""
        print(f"  Services: {stop_status}{pid}")

    profile = steps.get("shell_profile", {}) if isinstance(steps, dict) else {}
    if profile:
        if profile.get("removed"):
            profile_status = "removed"
        else:
            profile_status = profile.get("reason") or "unchanged"
        path = profile.get("profile_display") or profile.get("profile") or ""
        print(f"  Shell profile: {profile_status}{' (' + path + ')' if path else ''}")

    runtime = steps.get("runtime", {}) if isinstance(steps, dict) else {}
    if runtime:
        action = runtime.get("action") or "unknown"
        if action == "move":
            print(f"  Runtime: moved from {runtime.get('from')} to {runtime.get('to')}")
        elif action == "keep":
            print(f"  Runtime: kept at {runtime.get('path')}")
        elif action == "delete":
            print(f"  Runtime: deleted {runtime.get('path')}")
        else:
            print(f"  Runtime: {action}")

    repo = steps.get("repo", {}) if isinstance(steps, dict) else {}
    if repo:
        action = repo.get("action") or "unknown"
        path = f" {repo.get('path')}" if repo.get("path") else ""
        print(f"  Repo: {action}{path}")

    for err in result.get("errors", []) or []:
        print(f"  Error: {err.get('step')}: {err.get('error')}")


def _emit_uninstall_result(args, result: dict) -> None:
    if getattr(args, "json", False):
        _emit(args, result)
        return
    if result.get("steps"):
        _print_uninstall_summary(result)
        return
    print("Atested uninstall")
    print("  Status: incomplete")
    message = result.get("message") or result.get("error") or result.get("reason") or "uninstall did not complete"
    print(f"  Error: {message}")


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
        "supervisor": _supervisor_status().get("supervisor", {}),
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
    if getattr(args, "json", False):
        _emit(args, data)
    else:
        _print_status_summary(data)
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
    operator = (args.operator or _configured_operator_identity()).strip()

    payload = {
        "artifact_identity": artifact_identity,
        "approving_operator": operator,
        "user_identity": operator,
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
    operator = (args.operator or _configured_operator_identity()).strip()

    payload = {
        "artifact_identity": artifact_identity,
        "revoking_operator": operator,
        "user_identity": operator,
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

    operator_identity = _collect_operator_identity(args)
    _save_operator_config(operator_identity)

    # 3. Create persistent machine identity and primary registry.
    try:
        from receipt_signing import _public_key_fingerprint
        from machine_identity import ensure_machine_identity, ensure_primary_machine_registry
        key_id = _public_key_fingerprint(private_key.public_key(), serialization)
        public_key_pem = _public_key_pem(private_key, serialization)
        identity = ensure_machine_identity(
            REPO,
            role="primary",
            display_name=operator_identity,
            signing_key_id=key_id,
        )
        ensure_primary_machine_registry(REPO, identity=identity, public_key_fingerprint=key_id, public_key_pem=public_key_pem)
        print(f"  Assigned machine ID:      {identity['machine_id']}")
        print("  Machine role:             primary")
        print(f"  Operator identity:        {operator_identity}")
    except Exception as exc:
        print(f"error: failed to create machine identity: {exc}", file=sys.stderr)
        return 1

    # 4. Ask for working directories (or use defaults)
    base_dirs = _collect_base_dirs(args)
    for d in base_dirs[2:]:
        print(f"  Added working directory:  {d}")

    # 5. Configure policy-rules.json base_dirs
    _configure_policy_base_dirs(base_dirs)
    print(f"  Configured policy rules:  {POLICY_RULES_PATH}")
    if len(base_dirs) > 2:
        for d in base_dirs[2:]:
            print(f"    base_dir: {d}")

    # 6. Summary
    print("")
    print("Atested is initialized.")
    print("")
    profile_result = _configure_shell_profile(args)
    _print_proxy_routes(profile_result)
    _print_first_run_guidance()
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
    primary_public_key_pem = ""
    if role == "remote":
        primary_public_key_pem = str(args.primary_public_key_pem or "").strip()
        if args.primary_public_key_pem_file:
            primary_public_key_pem = Path(args.primary_public_key_pem_file).read_text(encoding="utf-8").strip()
        if not primary_public_key_pem:
            print("error: remote start requires --primary-public-key-pem or --primary-public-key-pem-file", file=sys.stderr)
            return 2
    first_run = bool(args.force) or not _runtime_initialized()
    operator_identity = _configured_operator_identity(args)
    configured_base_dirs: list[str] = []
    profile_result: dict = {}
    if first_run:
        if not getattr(args, "json", False):
            print("Atested first-run setup", flush=True)
        operator_identity = _collect_operator_identity(args)
        _save_operator_config(operator_identity)
        configured_base_dirs = _collect_base_dirs(args)
        try:
            _configure_policy_base_dirs(configured_base_dirs)
        except Exception as exc:
            print(f"error: failed to configure policy rules: {exc}", file=sys.stderr)
            return 1
    elif getattr(args, "user_identity", None):
        _save_operator_config(operator_identity)

    try:
        bootstrap = _ensure_runtime_initialized(
            role,
            force=bool(args.force),
            display_name=operator_identity,
        )
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
        sync_config["primary_public_key_pem"] = primary_public_key_pem
    else:
        sync_config["sync_service_host"] = args.sync_host
        sync_config["sync_service_port"] = int(args.sync_port)
    sync_config = _set_sync_config(sync_config)
    _clear_degraded()

    if first_run:
        profile_result = _configure_shell_profile(args)
        if not getattr(args, "json", False):
            print("Atested is initialized.")
            if configured_base_dirs:
                print(f"  Operator identity: {operator_identity}")
                for d in configured_base_dirs[2:]:
                    print(f"  Working directory: {d}")
            _print_proxy_routes(profile_result)
            _print_first_run_guidance()

    _flush_terminal_output()

    supervisor = {}
    if not args.no_services:
        supervisor = _start_supervisor(role, sync_host=args.sync_host, sync_port=int(args.sync_port))
        services = _service_statuses()

    payload = {
        "started": True,
        "first_run": first_run,
        "role": role,
        "runtime": str(_runtime()),
        "machine_id": identity.get("machine_id"),
        "operator_identity": operator_identity,
        "public_key_fingerprint": bootstrap["public_key_fingerprint"],
        "public_key_pem": bootstrap["public_key_pem"],
        "configured_base_dirs": configured_base_dirs,
        "shell_profile": profile_result,
        "sync_config": sync_config,
        "supervisor": supervisor or _supervisor_status().get("supervisor", {}),
        "services": services or _service_statuses(),
        "operator_action_required": (
            "confirm this remote on the primary with atested machine add"
            if role == "remote" else None
        ),
    }
    if getattr(args, "json", False):
        _emit(args, payload)
    else:
        print("Atested started.")
        print(f"  Role:    {role}")
        print(f"  Runtime: {_runtime()}")
        print(f"  Machine: {identity.get('machine_id')}")
        if supervisor:
            print(f"  Supervisor: running pid {supervisor.get('pid')}")
        current_services = services or _service_statuses()
        if current_services:
            print("  Services:")
            for name, record in sorted(current_services.items()):
                state = "running" if record.get("running") else "starting"
                pid = f" pid {record.get('pid')}" if record.get("pid") else ""
                print(f"    {name}: {state}{pid}")
        if payload.get("operator_action_required"):
            print(f"  Action required: {payload['operator_action_required']}")
    return 0


def cmd_stop(args) -> int:
    identity = None
    try:
        from machine_identity import load_machine_identity
        identity = load_machine_identity(REPO)
    except Exception:
        identity = None
    service_records = _collect_recorded_services()
    supervisor = _stop_supervisor()
    stopped = _stop_recorded_services(service_records)
    if not supervisor.get("stopped"):
        # If the supervisor did not exit cleanly, kill it after child cleanup so
        # it cannot respawn services onto occupied ports.
        pid = int(supervisor.get("pid") or 0)
        if pid:
            supervisor["stopped"] = _terminate_pid(pid, timeout=2.0)
            if supervisor["stopped"]:
                supervisor.pop("reason", None)
    payload = {
        "stopped": True,
        "role": (identity or {}).get("machine_role"),
        "supervisor": supervisor,
        "services": stopped,
    }
    if getattr(args, "json", False):
        _emit(args, payload)
    else:
        role = payload.get("role") or "uninitialized"
        print("Atested stopped.")
        print(f"  Role:       {role}")
        print(f"  Supervisor: {'stopped' if supervisor.get('stopped') else supervisor.get('reason', 'not_running')}")
        if supervisor.get("pid"):
            print(f"  PID:        {supervisor.get('pid')}")
        if stopped:
            print("  Services:")
            for record in stopped:
                name = record.get("name", "service")
                state = "stopped" if record.get("stopped") else record.get("reason", "not_running")
                print(f"    {name}: {state}")
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


def cmd_uninstall(args) -> int:
    """Remove Atested from this machine."""
    import shutil as _shutil

    runtime = _runtime()
    result: dict = {"uninstalled": False, "steps": {}}
    errors: list[dict] = []

    # --- Resolve runtime action early so we can fail before doing anything ---
    keep_rt = getattr(args, "keep_runtime", False)
    move_rt = getattr(args, "move_runtime", None)
    delete_rt = getattr(args, "delete_runtime", False)
    flag_count = sum([keep_rt, bool(move_rt), delete_rt])
    if flag_count > 1:
        _emit_uninstall_result(args, {"uninstalled": False, "error": "mutually_exclusive_runtime_flags",
                                      "message": "Specify at most one of --keep-runtime, --move-runtime, --delete-runtime."})
        return 1

    if flag_count == 0:
        if getattr(args, "yes", False) or not sys.stdin.isatty():
            _emit_uninstall_result(args, {"uninstalled": False, "error": "runtime_action_required",
                                          "message": "Specify --keep-runtime, --move-runtime PATH, or --delete-runtime."})
            return 1
        # Interactive prompt
        print(f"Runtime directory: {runtime}")
        answer = input("  [k]eep  /  [m]ove  /  [d]elete runtime data? ").strip().lower()
        if answer in ("k", "keep"):
            keep_rt = True
        elif answer in ("m", "move"):
            move_rt = input("  Move to: ").strip()
            if not move_rt:
                _emit_uninstall_result(args, {"uninstalled": False, "error": "no_move_destination"})
                return 1
        elif answer in ("d", "delete"):
            delete_rt = True
        else:
            _emit_uninstall_result(args, {"uninstalled": False, "reason": "operator_cancelled"})
            return 1

    # Conflict: keeping runtime that lives inside repo while deleting repo
    keep_repo = getattr(args, "keep_repo", False)
    if keep_rt and not keep_repo:
        try:
            runtime.resolve().relative_to(REPO.resolve())
            _emit_uninstall_result(args, {"uninstalled": False, "error": "runtime_inside_repo",
                                          "message": f"Runtime is inside the repo. Use --move-runtime PATH to relocate it, or add --keep-repo."})
            return 1
        except ValueError:
            pass  # runtime is outside repo — no conflict

    # --- Confirmation ---
    if not getattr(args, "yes", False):
        if not sys.stdin.isatty():
            _emit_uninstall_result(args, {"uninstalled": False, "error": "non_interactive_requires_yes"})
            return 1
        confirm = input(f"Uninstall Atested from {REPO}? [y/N] ").strip().lower()
        if confirm not in ("y", "yes"):
            _emit_uninstall_result(args, {"uninstalled": False, "reason": "operator_cancelled"})
            return 1

    # --- Step 1: Stop services ---
    try:
        stop_result = _stop_supervisor()
        result["steps"]["stop"] = stop_result
    except Exception as exc:
        errors.append({"step": "stop", "error": str(exc)})
        result["steps"]["stop"] = {"error": str(exc)}

    # --- Step 2: Remove shell profile entry ---
    try:
        profile_path = _profile_path_for_shell()
        if profile_path is not None:
            profile_result = _remove_shell_profile_entry(profile_path)
        else:
            profile_result = {"removed": False, "reason": "unsupported_shell"}
        result["steps"]["shell_profile"] = profile_result
    except Exception as exc:
        errors.append({"step": "shell_profile", "error": str(exc)})
        result["steps"]["shell_profile"] = {"error": str(exc)}

    # --- Step 3: Handle gov_runtime ---
    try:
        if not runtime.exists():
            result["steps"]["runtime"] = {"action": "skip", "reason": "runtime_not_found"}
        elif keep_rt:
            cleaned = _clean_runtime_ephemeral(runtime)
            result["steps"]["runtime"] = {"action": "keep", "path": str(runtime),
                                          "ephemeral_cleaned": cleaned}
        elif move_rt:
            dest = Path(move_rt).expanduser().resolve()
            cleaned = _clean_runtime_ephemeral(runtime)
            _shutil.move(str(runtime), str(dest))
            result["steps"]["runtime"] = {"action": "move", "from": str(runtime),
                                          "to": str(dest), "ephemeral_cleaned": cleaned}
        elif delete_rt:
            _shutil.rmtree(str(runtime), ignore_errors=True)
            result["steps"]["runtime"] = {"action": "delete", "path": str(runtime)}
    except Exception as exc:
        errors.append({"step": "runtime", "error": str(exc)})
        result["steps"]["runtime"] = {"error": str(exc)}

    # --- Step 4: Remove repo ---
    try:
        if keep_repo:
            result["steps"]["repo"] = {"action": "keep", "path": str(REPO)}
        else:
            home = str(Path.home())
            os.chdir(home)
            _shutil.rmtree(str(REPO), ignore_errors=True)
            result["steps"]["repo"] = {"action": "delete", "path": str(REPO)}
    except Exception as exc:
        errors.append({"step": "repo", "error": str(exc)})
        result["steps"]["repo"] = {"error": str(exc)}

    result["uninstalled"] = len(errors) == 0
    if errors:
        result["errors"] = errors
    _emit_uninstall_result(args, result)
    return 0 if not errors else 1


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
        help="Emit full JSON output",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="First-run setup (create runtime, generate key, configure policy)")
    p_init.add_argument("--dirs", nargs="*", metavar="DIR",
                        help="Working directories for your AI agent (default: current directory)")
    p_init.add_argument("--user-identity", default=None, help="Operator identity recorded on governance events")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing configuration")
    p_init.add_argument("--yes-shell-profile", action="store_true", help=argparse.SUPPRESS)
    p_init.add_argument("--no-shell-profile", action="store_true", help=argparse.SUPPRESS)
    p_init.set_defaults(func=cmd_init)

    p_start = sub.add_parser("start", help="Start Atested governance services")
    p_start.add_argument("--role", choices=["primary", "remote"], default="primary")
    p_start.add_argument("--primary-url", default=None, help="Primary sync service URL for remote role")
    p_start.add_argument("--primary-public-key-pem", default=None, help="Primary Ed25519 public key PEM for remote response verification")
    p_start.add_argument("--primary-public-key-pem-file", default=None, help="File containing the primary Ed25519 public key PEM")
    p_start.add_argument("--sync-host", default="127.0.0.1")
    p_start.add_argument("--sync-port", type=int, default=8765)
    p_start.add_argument("--sync-interval", type=int, default=300)
    p_start.add_argument("--dirs", nargs="*", metavar="DIR",
                         help="Working directories for first-run setup")
    p_start.add_argument("--user-identity", default=None, help="Operator identity recorded on governance events")
    p_start.add_argument("--yes-shell-profile", action="store_true", help=argparse.SUPPRESS)
    p_start.add_argument("--no-shell-profile", action="store_true", help=argparse.SUPPRESS)
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
    p_approve.add_argument("--operator", default=None, help="Approving operator name")
    p_approve.set_defaults(func=cmd_approve)

    p_revoke = sub.add_parser("revoke", help="Revoke an existing approval")
    p_revoke.add_argument("artifact_identity", help="Artifact identity to revoke")
    p_revoke.add_argument("--operator", default=None, help="Revoking operator name")
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

    p_uninstall = sub.add_parser("uninstall", help="Remove Atested from this machine")
    p_uninstall.add_argument("--keep-runtime", action="store_true",
                             help="Keep gov_runtime data in place")
    p_uninstall.add_argument("--move-runtime", metavar="PATH",
                             help="Move gov_runtime to specified path")
    p_uninstall.add_argument("--delete-runtime", action="store_true",
                             help="Delete gov_runtime and all data")
    p_uninstall.add_argument("--keep-repo", action="store_true",
                             help="Keep the governance-layer repository")
    p_uninstall.add_argument("--yes", action="store_true",
                             help="Skip confirmation prompts")
    p_uninstall.set_defaults(func=cmd_uninstall)

    return parser


def main(argv=None) -> int:
    # Force line-buffered stdout so output appears immediately on all
    # platforms, even when Python detects block-buffered mode.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, OSError):
        pass  # Python < 3.7 or non-reconfigurable stream
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "func", None) is cmd_start and not getattr(args, "json", False):
        _write_terminal_line("Starting Atested...")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
