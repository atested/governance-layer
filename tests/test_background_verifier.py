import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO / "proxy", REPO / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from background_verifier import read_verification_status, run_verification
from event_model import build_non_action_event
from proxy.server import ChainRecorder


def _append_event(path: Path, label: str) -> dict:
    prev = None
    if path.exists():
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if lines:
            prev = json.loads(lines[-1]).get("record_hash")
    event = build_non_action_event(
        "verification_state_transition",
        {
            "governed_family": label,
            "from_state": "unverified",
            "to_state": "verified",
            "reason": "test",
        },
        prev_record_hash=prev,
    )
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return event


def test_run_verification_writes_status_without_changing_chain(tmp_path):
    chain = tmp_path / "decision-chain.jsonl"
    _append_event(chain, "one")
    before = chain.read_text(encoding="utf-8")

    status = run_verification(chain, threshold=2)

    assert status["status"] == "ok"
    assert status["checked"] is True
    assert status["last_verified_count"] == 1
    assert status["next_due_count"] == 3
    assert chain.read_text(encoding="utf-8") == before
    assert read_verification_status(chain)["status"] == "ok"


def test_run_verification_records_break_point(tmp_path):
    chain = tmp_path / "decision-chain.jsonl"
    _append_event(chain, "one")
    second = build_non_action_event(
        "verification_state_transition",
        {
            "governed_family": "two",
            "from_state": "unverified",
            "to_state": "verified",
            "reason": "test",
        },
        prev_record_hash="sha256:not-the-previous-hash",
    )
    with chain.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(second, sort_keys=True, separators=(",", ":")) + "\n")

    status = run_verification(chain, threshold=2)

    assert status["status"] == "broken"
    assert status["break_count"] >= 1
    assert status["first_break_sequence"] == 2
    assert status["first_break_reason"]


def test_chain_recorder_triggers_background_verification_after_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("ATESTED_CHAIN_VERIFY_EVERY_RECORDS", "1")
    chain = tmp_path / "decision-chain.jsonl"
    recorder = ChainRecorder(chain)
    recorder.append_integrity_event(
        "verification_state_transition",
        {
            "governed_family": "trigger",
            "from_state": "unverified",
            "to_state": "verified",
            "reason": "test",
        },
    )

    status = {}
    for _ in range(50):
        status = read_verification_status(chain)
        if status.get("status") == "ok":
            break
        time.sleep(0.02)

    assert status["status"] == "ok"
    assert status["last_verified_count"] == 1
