#!/usr/bin/env python3
"""Cross-platform process supervisor for Atested services."""

from __future__ import annotations

import argparse
import json
import os
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

_stopping = False


def now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


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


def build_service_specs(role: str, sync_host: str, sync_port: int) -> list[dict]:
    specs = [
        {"name": "proxy", "argv": [sys.executable, "-m", "proxy.server"]},
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
        self.runtime = runtime
        self.log_dir = log_dir
        self.env = env
        self.proc: subprocess.Popen | None = None
        self.restart_times: list[float] = []
        self.restart_count = 0
        self.disabled = False
        self.disabled_reason = ""
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

    def status(self) -> dict:
        pid = self.proc.pid if self.proc is not None else None
        running = self.proc is not None and self.proc.poll() is None
        uptime = 0
        if running and self.started_at_epoch:
            uptime = int(max(0, time.time() - self.started_at_epoch))
        return {
            "name": self.name,
            "argv": self.argv,
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
    args = parser.parse_args(argv)

    runtime = Path(args.runtime).expanduser().resolve()
    supervisor_dir = runtime / "supervisor"
    pid_path = supervisor_dir / "supervisor.pid"
    status_path = supervisor_dir / "status.json"
    services_path = supervisor_dir / "services.json"
    log_dir = supervisor_dir / "logs"
    supervisor_dir.mkdir(parents=True, exist_ok=True)

    existing_pid = read_pid(pid_path)
    if existing_pid and existing_pid != os.getpid() and pid_alive(existing_pid):
        return 0

    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(runtime)
    env.setdefault("GOV_SIGNING_KEY_PATH", str(runtime / SIGNING_KEY_NAME))

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    started_epoch = time.time()
    started_utc = now_utc_z()
    services = [
        ManagedService(spec, runtime, log_dir, env)
        for spec in build_service_specs(args.role, args.sync_host, args.sync_port)
    ]

    for service in services:
        service.start()

    try:
        while not _stopping:
            for service in services:
                service.poll()
            payload = {
                "supervisor": {
                    "pid": os.getpid(),
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
