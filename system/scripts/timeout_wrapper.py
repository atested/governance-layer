#!/usr/bin/env python3
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time


def usage() -> None:
    print(
        "Usage: timeout_wrapper.py <seconds> <task_id> "
        "[--startup-seconds N --startup-regex REGEX] -- <command...>",
        file=sys.stderr,
    )


def killpg(proc: subprocess.Popen, sig: int) -> None:
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        pass


if len(sys.argv) < 4:
    usage()
    sys.exit(2)

try:
    secs = float(sys.argv[1])
except ValueError:
    print("Invalid timeout", file=sys.stderr)
    sys.exit(2)

task_id = sys.argv[2]
startup_secs = None
startup_re = None

i = 3
while i < len(sys.argv):
    a = sys.argv[i]
    if a == "--":
        i += 1
        break
    if a == "--startup-seconds" and i + 1 < len(sys.argv):
        startup_secs = float(sys.argv[i + 1])
        i += 2
        continue
    if a == "--startup-regex" and i + 1 < len(sys.argv):
        startup_re = re.compile(sys.argv[i + 1])
        i += 2
        continue
    usage()
    sys.exit(2)

cmd = sys.argv[i:]
if not cmd:
    print("No command provided", file=sys.stderr)
    sys.exit(2)

proc = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    start_new_session=True,
)

_SENTINEL = object()
q = queue.Queue()


def reader() -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        q.put(line)
        q.put(_SENTINEL)


threading.Thread(target=reader, daemon=True).start()

start = time.monotonic()
startup_deadline = (start + startup_secs) if startup_secs is not None else None
startup_seen = startup_re is None
rc = None
stream_done = False

while True:
    got_item = False
    try:
        item = q.get(timeout=0.1)
        got_item = True
    except queue.Empty:
        item = None

    if got_item:
        if item is _SENTINEL:
            stream_done = True
        else:
            print(item, end="")
            if (not startup_seen) and startup_re and startup_re.search(item):
                startup_seen = True

    rc = proc.poll()
    now = time.monotonic()

    if (not startup_seen) and startup_deadline is not None and now >= startup_deadline:
        print(f"STOP: EXEC_START_TIMEOUT after {int(startup_secs)}s for {task_id}")
        killpg(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            killpg(proc, signal.SIGKILL)
            proc.wait(timeout=5)
        sys.exit(1)

    if now - start >= secs and rc is None:
        print(f"STOP: TIMEOUT after {int(secs)}s for {task_id}")
        killpg(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=1)
        except subprocess.TimeoutExpired:
            killpg(proc, signal.SIGKILL)
            proc.wait(timeout=5)
        sys.exit(1)

    if rc is not None and stream_done and q.empty():
        sys.exit(rc)
