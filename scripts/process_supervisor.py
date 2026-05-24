#!/usr/bin/env python3
"""Cross-platform process supervisor for Atested services."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO = SCRIPT_DIR.parent

SIGNING_KEY_NAME = ".atested-signing-key.pem"
MAX_RESTARTS = 3
RESTART_WINDOW_SECONDS = 60
STATUS_INTERVAL_SECONDS = 1.0
QUALITY_SERVICE_BUILD_TIMEOUT = 300  # seconds; cargo --release first build can take a few minutes

_stopping = False


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_pid_record(path: Path) -> dict | None:
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            return {"pid": int(raw), "token": "", "runtime": ""}
        except ValueError:
            return None
    if not isinstance(data, dict) or not isinstance(data.get("pid"), int):
        return None
    return data


def read_pid(path: Path) -> int | None:
    record = read_pid_record(path)
    if not record:
        return None
    return int(record.get("pid") or 0) or None


def pid_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def detach_kwargs() -> dict:
    if os.name == "nt":
        flags = 0
        flags |= getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0)
        return {"creationflags": flags} if flags else {}
    return {"start_new_session": True}


def default_quality_service_bin() -> Path:
    return REPO / "quality-service" / "target" / "release" / "quality-service"


def quality_service_bin_path() -> Path:
    return Path(
        os.environ.get(
            "ATESTED_QUALITY_SERVICE_BIN",
            str(default_quality_service_bin()),
        )
    )


def quality_service_source_dir() -> Path:
    return REPO / "quality-service"


def ensure_quality_service_binary(runtime: Path) -> tuple[Path, str | None]:
    """Ensure the quality-service binary exists. Build it if missing/stale.

    Returns (binary_path, error). If error is None, the binary is ready to
    exec. If error is set, the supervisor must disable the quality-service
    spec and surface the reason to the operator via the degraded marker.

    Auto-build policy:
      - Custom ATESTED_QUALITY_SERVICE_BIN: trusted as-is; no build attempted.
      - Default path under quality-service/target/release/: build with
        `cargo build --release` if absent OR if any source file is newer
        than the binary mtime.
      - If `cargo` is not on PATH (no Rust toolchain installed), the
        quality service is disabled with reason 'rust_toolchain_missing'.

    Logs go to {runtime}/supervisor/logs/quality_service.build.log.
    """
    custom_path = os.environ.get("ATESTED_QUALITY_SERVICE_BIN")
    binary = quality_service_bin_path()
    log_path = runtime / "supervisor" / "logs" / "quality_service.build.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    if custom_path:
        if not binary.exists():
            return binary, f"custom ATESTED_QUALITY_SERVICE_BIN not found: {binary}"
        return binary, None

    src_dir = quality_service_source_dir()
    cargo_toml = src_dir / "Cargo.toml"
    if not cargo_toml.exists():
        return binary, f"quality-service crate missing at {src_dir}"

    needs_build = not binary.exists()
    if binary.exists():
        bin_mtime = binary.stat().st_mtime
        for src_file in src_dir.glob("src/**/*.rs"):
            if src_file.stat().st_mtime > bin_mtime:
                needs_build = True
                break
        if not needs_build and cargo_toml.stat().st_mtime > bin_mtime:
            needs_build = True

    if not needs_build:
        return binary, None

    cargo = shutil.which("cargo")
    if cargo is None:
        return (
            binary,
            "rust_toolchain_missing: cargo not found on PATH; install Rust to enable the quality service",
        )

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== {now_utc_z()} cargo build --release ===\n")
        try:
            result = subprocess.run(
                [cargo, "build", "--release", "--manifest-path", str(cargo_toml)],
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=QUALITY_SERVICE_BUILD_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return binary, f"cargo build timed out after {QUALITY_SERVICE_BUILD_TIMEOUT}s; see {log_path}"

    if result.returncode != 0:
        return binary, f"cargo build --release failed (exit {result.returncode}); see {log_path}"
    if not binary.exists():
        return binary, f"cargo build reported success but binary missing at {binary}"
    return binary, None


def write_quality_service_degraded_marker(runtime: Path, reason: str | None) -> None:
    """Write a small JSON marker the dashboard can read.

    Path: {runtime}/supervisor/quality-service.degraded.json
    Body: { reason: <reason or null>, updated_utc: ... }

    The dashboard's conformance reader inspects this marker to distinguish
    a normal HALTED state (quality service running but stale) from a
    self-provisioning failure (toolchain missing, build failed, etc.).
    Removed when the binary is ready.
    """
    marker = runtime / "supervisor" / "quality-service.degraded.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    if reason is None:
        try:
            marker.unlink()
        except FileNotFoundError:
            pass
        return
    payload = {"reason": reason, "updated_utc": now_utc_z()}
    write_json_atomic(marker, payload)


def build_service_specs(role: str, sync_host: str, sync_port: int, runtime: Path) -> list[dict]:
    proxy_port = os.environ.get("GOV_PROXY_PORT", "8080")
    binary, build_error = ensure_quality_service_binary(runtime)
    write_quality_service_degraded_marker(runtime, build_error)
    quality_ready_file = runtime / "supervisor" / "quality-service.ready"
    quality_spec: dict = {
        "name": "quality_service",
        "argv": [str(binary)],
        "ready_file": str(quality_ready_file),
        "startup_timeout_seconds": 30,
    }
    if build_error is not None:
        quality_spec["disabled_at_start"] = True
        quality_spec["disabled_reason"] = build_error
    # QS-033 A2: proxy must start before quality_service. The QS env gate
    # (ENV-001/ENV-002) hashes the policy and capability registry files and
    # compares against the LAST policy_rules_hash / capability_registry_hash
    # in the decision chain. If the policy file changed while no proxy was
    # running, the chain's tail still holds the stale hash and the gate fails
    # critically. Starting the proxy first ensures it writes a startup record
    # (policy_rules_loaded, extended in QS-033 to include policy_rules_hash
    # and capability_registry_hash) so the chain's tail reflects the current
    # policy state before the quality service reads it. The proxy's ready
    # file is written AFTER the startup record is committed, so the
    # supervisor's ready-file wait is the synchronization point.
    proxy_ready_file = runtime / "supervisor" / "proxy.ready"
    specs = [
        {
            "name": "proxy",
            "argv": [sys.executable, "-m", "proxy.server", "--port", proxy_port],
            "ready_file": str(proxy_ready_file),
            "startup_timeout_seconds": 30,
        },
        quality_spec,
        {"name": "dashboard", "argv": [sys.executable, "dashboard/server.py"]},
    ]
    if role == "primary":
        specs.append({
            "name": "sync_service",
            "argv": [
                sys.executable,
                "scripts/sync_service.py",
                "--host",
                sync_host,
                "--port",
                str(sync_port),
            ],
        })
    return specs


class ManagedService:
    def __init__(self, spec: dict, runtime: Path, log_dir: Path, env: dict):
        self.name = str(spec["name"])
        self.argv = list(spec["argv"])
        self.ready_file = Path(spec["ready_file"]) if spec.get("ready_file") else None
        self.startup_timeout_seconds = int(spec.get("startup_timeout_seconds", 0) or 0)
        self.runtime = runtime
        self.log_dir = log_dir
        self.env = env
        self.proc: subprocess.Popen | None = None
        self.restart_times: list[float] = []
        self.restart_count = 0
        self.disabled = bool(spec.get("disabled_at_start", False))
        self.disabled_reason = str(spec.get("disabled_reason", "") or "")
        self.started_at_epoch: float | None = None
        self.started_utc: str | None = None
        self.last_exit_code: int | None = None
        self.last_exit_utc: str | None = None

    def start(self) -> None:
        if self.disabled:
            return
        self.log_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.log_dir / f"{self.name}.out.log"
        err_path = self.log_dir / f"{self.name}.err.log"
        out = open(out_path, "ab")
        err = open(err_path, "ab")
        try:
            self.proc = subprocess.Popen(
                self.argv,
                cwd=str(REPO),
                env=self.env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                **detach_kwargs(),
            )
        finally:
            out.close()
            err.close()
        self.started_at_epoch = time.time()
        self.started_utc = now_utc_z()

    def poll(self) -> None:
        if self.disabled:
            return
        if self.proc is None:
            self.start()
            return
        exit_code = self.proc.poll()
        if exit_code is None:
            return

        self.last_exit_code = exit_code
        self.last_exit_utc = now_utc_z()
        self.proc = None
        now = time.time()
        self.restart_times = [ts for ts in self.restart_times if now - ts <= RESTART_WINDOW_SECONDS]
        self.restart_times.append(now)
        if len(self.restart_times) > MAX_RESTARTS:
            self.disabled = True
            self.disabled_reason = f"crashed more than {MAX_RESTARTS} times in {RESTART_WINDOW_SECONDS}s"
            return
        self.restart_count += 1
        self.start()

    def terminate(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is not None:
            return
        try:
            self.proc.terminate()
        except OSError:
            return

    def kill_if_running(self) -> None:
        if self.proc is None:
            return
        if self.proc.poll() is not None:
            return
        try:
            self.proc.kill()
        except OSError:
            pass
        try:
            self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass

    def status(self) -> dict:
        pid = self.proc.pid if self.proc is not None else None
        running = self.proc is not None and self.proc.poll() is None
        uptime = 0
        if running and self.started_at_epoch:
            uptime = int(max(0, time.time() - self.started_at_epoch))
        return {
            "name": self.name,
            "argv": self.argv,
            "ready_file": str(self.ready_file) if self.ready_file else "",
            "pid": pid,
            "running": running,
            "started_utc": self.started_utc,
            "uptime_seconds": uptime,
            "restart_count": self.restart_count,
            "last_exit_code": self.last_exit_code,
            "last_exit_utc": self.last_exit_utc,
            "disabled": self.disabled,
            "disabled_reason": self.disabled_reason,
            "log_stdout": str(self.log_dir / f"{self.name}.out.log"),
            "log_stderr": str(self.log_dir / f"{self.name}.err.log"),
        }


def write_status(status_path: Path, services_path: Path, payload: dict) -> None:
    write_json_atomic(status_path, payload)
    write_json_atomic(services_path, payload.get("services", {}))


def handle_stop(_signum, _frame) -> None:
    global _stopping
    _stopping = True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the Atested service supervisor")
    parser.add_argument("--runtime", required=True)
    parser.add_argument("--role", choices=["primary", "remote"], required=True)
    parser.add_argument("--sync-host", default="127.0.0.1")
    parser.add_argument("--sync-port", type=int, default=8765)
    parser.add_argument("--token", required=True)
    args = parser.parse_args(argv)

    runtime = Path(args.runtime).expanduser().resolve()
    supervisor_dir = runtime / "supervisor"
    pid_path = supervisor_dir / "supervisor.pid"
    status_path = supervisor_dir / "status.json"
    services_path = supervisor_dir / "services.json"
    log_dir = supervisor_dir / "logs"
    supervisor_dir.mkdir(parents=True, exist_ok=True)

    existing = read_pid_record(pid_path)
    existing_pid = int((existing or {}).get("pid") or 0)
    existing_token = str((existing or {}).get("token") or "")
    if existing_pid and existing_pid != os.getpid() and pid_alive(existing_pid):
        return 0 if existing_token == args.token else 1

    write_json_atomic(pid_path, {
        "pid": os.getpid(),
        "token": args.token,
        "runtime": str(runtime),
        "created_utc": now_utc_z(),
    })

    env = os.environ.copy()
    # QS-033 A3: ATESTED_* names are canonical; GOV_* are kept as legacy
    # aliases that the Rust crate accepts with a deprecation warning. Setting
    # both keeps existing Python consumers (proxy, dashboard) working while
    # any new consumer can read the canonical names. A follow-on dispatch
    # migrates Python reads to ATESTED_*; see QS-033 Observations.
    env["GOV_RUNTIME_DIR"] = str(runtime)
    env["ATESTED_RUNTIME_DIR"] = str(runtime)
    env.setdefault("GOV_SIGNING_KEY_PATH", str(runtime / SIGNING_KEY_NAME))
    env.setdefault("ATESTED_SIGNING_KEY_PATH", env["GOV_SIGNING_KEY_PATH"])
    env.setdefault("ATESTED_QA_SIGNING_KEY_PATH", str(runtime / ".atested-qa-signing-key.pem"))
    env.setdefault("ATESTED_QS_READY_FILE", str(supervisor_dir / "quality-service.ready"))
    # QS-033 A2: the proxy writes a startup record on launch and then signals
    # readiness via this file. The quality_service spec waits for QS's own
    # ready file; the proxy now does the same so the QS env gate sees a fresh
    # policy_rules_loaded record (with policy_rules_hash) before it reads the
    # decision chain tail.
    env.setdefault("ATESTED_PROXY_READY_FILE", str(supervisor_dir / "proxy.ready"))
    # QS-033 A2: the proxy writes a startup record on launch and then signals
    # readiness via this file. The quality_service spec waits for QS's own
    # ready file; the proxy now does the same so the QS env gate sees a fresh
    # policy_rules_loaded record (with policy_rules_hash) before it reads the
    # decision chain tail.
    env.setdefault("ATESTED_PROXY_READY_FILE", str(supervisor_dir / "proxy.ready"))
    operator_path = runtime / "operator.json"
    try:
        operator = json.loads(operator_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        operator = {}
    if isinstance(operator, dict) and operator.get("user_identity"):
        env["ATESTED_USER_LABEL"] = str(operator["user_identity"])

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    started_epoch = time.time()
    started_utc = now_utc_z()
    services = [
        ManagedService(spec, runtime, log_dir, env)
        for spec in build_service_specs(args.role, args.sync_host, args.sync_port, runtime)
    ]

    for service in services:
        if service.disabled:
            # Auto-provisioning could not produce a runnable binary (e.g., the
            # Rust toolchain is missing). Skip ready-file gating; downstream
            # services start anyway so the dashboard can render and explain
            # the degraded state to the operator.
            continue
        if service.ready_file:
            try:
                service.ready_file.unlink()
            except FileNotFoundError:
                pass
        service.start()
        if service.ready_file:
            deadline = time.time() + service.startup_timeout_seconds
            while time.time() < deadline:
                if service.ready_file.exists():
                    break
                if service.proc is not None and service.proc.poll() is not None:
                    raise RuntimeError(
                        f"{service.name} exited before readiness; see {log_dir / (service.name + '.err.log')}"
                    )
                time.sleep(0.1)
            if not service.ready_file.exists():
                raise RuntimeError(f"{service.name} did not signal readiness within {service.startup_timeout_seconds}s")

    try:
        while not _stopping:
            for service in services:
                service.poll()
            payload = {
                "supervisor": {
                    "pid": os.getpid(),
                    "token": args.token,
                    "runtime": str(runtime),
                    "running": True,
                    "role": args.role,
                    "started_utc": started_utc,
                    "uptime_seconds": int(max(0, time.time() - started_epoch)),
                    "pid_file": str(pid_path),
                    "status_path": str(status_path),
                    "log_dir": str(log_dir),
                },
                "services": {service.name: service.status() for service in services},
                "updated_utc": now_utc_z(),
            }
            write_status(status_path, services_path, payload)
            time.sleep(STATUS_INTERVAL_SECONDS)
    finally:
        for service in services:
            service.terminate()
        deadline = time.time() + 8
        while time.time() < deadline:
            if all(service.proc is None or service.proc.poll() is not None for service in services):
                break
            time.sleep(0.1)
        for service in services:
            service.kill_if_running()
        payload = {
            "supervisor": {
                "pid": os.getpid(),
                "token": args.token,
                "runtime": str(runtime),
                "running": False,
                "role": args.role,
                "started_utc": started_utc,
                "stopped_utc": now_utc_z(),
                "uptime_seconds": int(max(0, time.time() - started_epoch)),
                "pid_file": str(pid_path),
                "status_path": str(status_path),
                "log_dir": str(log_dir),
            },
            "services": {service.name: service.status() for service in services},
            "updated_utc": now_utc_z(),
        }
        write_status(status_path, services_path, payload)
        try:
            pid_path.unlink()
        except FileNotFoundError:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
