import json
import subprocess
import sys
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from event_model import (
    NON_ACTION_EVENT_TYPES,
    build_non_action_event,
    validate_non_action_event,
    verify_non_action_event_hash,
)
from readout import _EVENT_TYPE_TO_CATEGORY, _normalize_activity_entry


def _payload(**overrides):
    payload = {
        "tool_name": "bash",
        "condition_source": "qa_chain_staleness",
        "condition_id": "QA-GATE:qa_chain_staleness",
        "condition_detail": "qa_environmental_snapshot sequence did not advance",
        "action_taken": "integrity_error_returned",
    }
    payload.update(overrides)
    return payload


def test_governance_integrity_error_registered_and_validates():
    assert "governance_integrity_error" in NON_ACTION_EVENT_TYPES

    event = build_non_action_event("governance_integrity_error", _payload())
    ok, err = validate_non_action_event(event)
    assert ok, err

    hash_ok, hash_err = verify_non_action_event_hash(event)
    assert hash_ok, hash_err


def test_governance_integrity_error_rejects_unknown_condition_source():
    event = build_non_action_event(
        "governance_integrity_error",
        _payload(condition_source="clock_skew"),
    )

    ok, err = validate_non_action_event(event)
    assert not ok
    assert "condition_source" in err


def test_governance_integrity_error_rejects_wrong_action_taken():
    event = build_non_action_event(
        "governance_integrity_error",
        _payload(action_taken="request_denied"),
    )

    ok, err = validate_non_action_event(event)
    assert not ok
    assert "action_taken" in err


def test_governance_integrity_error_readout_category():
    event = build_non_action_event("governance_integrity_error", _payload())

    assert _EVENT_TYPE_TO_CATEGORY["governance_integrity_error"] == "integrity"
    entry = _normalize_activity_entry(event, 1)

    assert entry["event_category"] == "integrity"
    assert entry["detail"]["condition_source"] == "qa_chain_staleness"
    assert entry["detail"]["action_taken"] == "integrity_error_returned"


def test_verify_chain_accepts_governance_integrity_error(tmp_path):
    chain_path = tmp_path / "decision-chain.jsonl"
    event = build_non_action_event("governance_integrity_error", _payload())
    chain_path.write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "verify-chain.py"), str(chain_path)],
        cwd=REPO,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
