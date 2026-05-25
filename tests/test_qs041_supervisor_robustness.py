"""QS-041: process supervisor robustness.

Covers:
  #15 write_json_atomic concurrency (no FileNotFoundError under racing writes)
  #16 exponential backoff on the crash-restart-limit disable
"""

import json
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import process_supervisor as ps


def test_write_json_atomic_concurrent_writes_no_error(tmp_path):
    """QS-041 #15: many threads writing the same path concurrently must not
    raise FileNotFoundError; the final file is valid JSON (last write wins)."""
    target = tmp_path / "status.json"
    errors: list[BaseException] = []
    barrier = threading.Barrier(16)

    def writer(n: int) -> None:
        try:
            barrier.wait()  # maximize contention
            for i in range(25):
                ps.write_json_atomic(target, {"writer": n, "i": i})
        except BaseException as exc:  # noqa: BLE001 - capture for assertion
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"concurrent writes raised: {errors!r}"
    # File exists, is valid JSON, and no temp litter remains.
    data = json.loads(target.read_text(encoding="utf-8"))
    assert "writer" in data and "i" in data
    leftover = list(tmp_path.glob("status.json.*tmp")) + list(tmp_path.glob("*.tmp"))
    assert not leftover, f"temp files left behind: {leftover}"


class _Clock:
    def __init__(self, start=1000.0):
        self.t = start

    def time(self):
        return self.t

    def advance(self, dt):
        self.t += dt


class _FakeProc:
    """Fake Popen: poll() returns the shared holder's exit code (None=running)."""

    def __init__(self, holder):
        self._holder = holder
        self.pid = 4242

    def poll(self):
        return self._holder["code"]


def _crash_service(monkeypatch, clock, tmp_path):
    monkeypatch.setattr(ps.time, "time", clock.time)
    svc = ps.ManagedService(
        {"name": "svc", "argv": ["x"]}, tmp_path, tmp_path / "logs", {}
    )
    holder = {"code": 1}  # 1 == crashed; None == running
    starts = {"count": 0}

    def fake_start():
        svc.proc = _FakeProc(holder)
        svc.started_at_epoch = clock.time()
        starts["count"] += 1

    monkeypatch.setattr(svc, "start", fake_start)
    return svc, holder, starts


def _drive_to_backoff(svc):
    # poll #1 starts; then each poll records one crash. MAX_RESTARTS+2 polls
    # guarantees the limit (3 in window) is exceeded.
    for _ in range(ps.MAX_RESTARTS + 3):
        svc.poll()


def test_backoff_disables_then_re_enables_and_doubles(tmp_path, monkeypatch):
    clock = _Clock()
    svc, holder, starts = _crash_service(monkeypatch, clock, tmp_path)

    # Rapid crashes within the window trip the limit -> backoff disable.
    _drive_to_backoff(svc)
    assert svc.disabled is True
    assert svc.disabled_until is not None
    first_retry_at = svc.disabled_until
    assert round(first_retry_at - clock.time()) == ps.INITIAL_BACKOFF_SECONDS
    # Next backoff has doubled.
    assert svc.backoff_seconds == ps.INITIAL_BACKOFF_SECONDS * 2

    # Still disabled before the timer: poll is a no-op.
    starts_before = starts["count"]
    svc.poll()
    assert svc.disabled is True
    assert starts["count"] == starts_before

    # Advance past the backoff: poll re-enables and restarts.
    clock.advance(ps.INITIAL_BACKOFF_SECONDS + 1)
    svc.poll()
    assert svc.disabled is False
    assert starts["count"] == starts_before + 1

    # Crash-loop again -> second disable uses the doubled backoff.
    holder["code"] = 1
    _drive_to_backoff(svc)
    assert svc.disabled is True
    assert round(svc.disabled_until - clock.time()) == ps.INITIAL_BACKOFF_SECONDS * 2
    assert svc.backoff_seconds == ps.INITIAL_BACKOFF_SECONDS * 4


def test_backoff_caps_at_thirty_minutes(tmp_path, monkeypatch):
    clock = _Clock()
    svc, holder, _ = _crash_service(monkeypatch, clock, tmp_path)
    for _ in range(12):
        holder["code"] = 1
        _drive_to_backoff(svc)
        clock.advance(svc.backoff_seconds + 1)
        svc.poll()  # re-enable
    assert svc.backoff_seconds <= ps.MAX_BACKOFF_SECONDS
    assert ps.MAX_BACKOFF_SECONDS == 30 * 60


def test_clean_run_resets_backoff(tmp_path, monkeypatch):
    clock = _Clock()
    svc, holder, _ = _crash_service(monkeypatch, clock, tmp_path)
    _drive_to_backoff(svc)
    assert svc.backoff_seconds > ps.INITIAL_BACKOFF_SECONDS

    # Re-enable, then run cleanly (proc stays alive) for a full window.
    clock.advance(ps.INITIAL_BACKOFF_SECONDS + 1)
    svc.poll()  # re-enable + start
    holder["code"] = None  # running, no crash
    svc.poll()  # observes running
    clock.advance(ps.RESTART_WINDOW_SECONDS + 1)
    svc.poll()  # clean-run reset fires
    assert svc.backoff_seconds == ps.INITIAL_BACKOFF_SECONDS


def test_permanently_disabled_never_re_enables(tmp_path, monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(ps.time, "time", clock.time)
    svc = ps.ManagedService(
        {"name": "svc", "argv": ["x"], "disabled_at_start": True, "disabled_reason": "missing binary"},
        tmp_path,
        tmp_path / "logs",
        {},
    )
    assert svc.permanently_disabled is True
    clock.advance(10_000)
    svc.poll()
    assert svc.disabled is True
    assert svc.proc is None


# ---------- #17 orphan port clearing ----------

def test_clear_orphan_on_port_kills_untracked(tmp_path, monkeypatch):
    """An untracked listener (orphan from a prior supervisor) is killed and
    the warning is logged; the wait loop then sees the port free."""
    # Port held by orphan 9999 on the first probe, free afterwards.
    probes = iter([[9999], [9999], []])
    monkeypatch.setattr(ps, "_pids_listening_on_port", lambda port: next(probes, []))
    killed = []
    monkeypatch.setattr(ps, "_terminate_orphan", lambda pid: killed.append(pid))
    logs = []
    monkeypatch.setattr(ps, "_log", lambda msg: logs.append(msg))
    monkeypatch.setattr(ps.time, "sleep", lambda *_a, **_k: None)

    ps.clear_orphan_on_port(8080, "proxy", managed_pids={ps.os.getpid()})

    assert killed == [9999]
    assert any("killed orphan process 9999 on port 8080" in m for m in logs)


def test_clear_orphan_on_port_spares_managed_pid(tmp_path, monkeypatch):
    """A listener whose PID is managed by the current supervisor is NOT killed;
    a logic-error is logged and escalated instead."""
    monkeypatch.setattr(ps, "_pids_listening_on_port", lambda port: [4321])
    killed = []
    monkeypatch.setattr(ps, "_terminate_orphan", lambda pid: killed.append(pid))
    logs = []
    monkeypatch.setattr(ps, "_log", lambda msg: logs.append(msg))
    monkeypatch.setattr(ps.time, "sleep", lambda *_a, **_k: None)
    # Bound the wait loop: managed pid keeps "remaining" empty, so it returns.
    monkeypatch.setattr(ps.time, "time", lambda: 0.0)

    ps.clear_orphan_on_port(8080, "proxy", managed_pids={4321})

    assert killed == []  # never kill our own
    assert any("IS managed by the current supervisor" in m for m in logs)


def test_clear_orphan_on_port_noop_when_free(monkeypatch):
    monkeypatch.setattr(ps, "_pids_listening_on_port", lambda port: [])
    killed = []
    monkeypatch.setattr(ps, "_terminate_orphan", lambda pid: killed.append(pid))
    monkeypatch.setattr(ps, "_log", lambda msg: None)
    ps.clear_orphan_on_port(9700, "dashboard", managed_pids=set())
    assert killed == []
