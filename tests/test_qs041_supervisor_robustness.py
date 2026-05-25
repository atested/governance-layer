"""QS-041: process supervisor robustness.

Covers:
  #15 write_json_atomic concurrency (no FileNotFoundError under racing writes)
"""

import json
import sys
import threading
from pathlib import Path

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
