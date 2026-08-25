"""WP-RL-009 — reproducible launch instructions and one authoritative activation profile.

Covers the three target-level validators that govern the handoff of the
Reach Lite operator application (see reach_lite/launch_profile.py):

* REQ-ATL-037 DurableLaunchInstructionsValidator — the durable launch
  instructions must state prerequisites, the configuration procedure, the
  activation operation, the expected browser URL, the readiness signal, the
  cleanup operation, and the observable failure behavior; every reference
  must resolve within the delivery; no placeholder or stale value.
* REQ-ATL-038 ConfiguredActivationProfileValidator — exactly one
  authoritative activation profile, conforming to SCH-ATL-009, that is the
  profile actually used by launch verification.
* SCH-ATL-009 ActivationProfileSchemaValidator — the activation profile
  schema for reach_lite/activation_profile.json.

The live tests execute the declared activation operation as a real
subprocess from the repository root in a prepared self-host environment,
observe the declared readiness signal over HTTP, resolve the declared
browser URL, collect a verification inventory, and hand it to the
configured-profile validator.
"""
from __future__ import annotations

import json
import shlex
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest

from reach_lite.launch_profile import (
    CONFIGURED_PROFILE_VALIDATOR,
    INSTRUCTIONS_FILENAME,
    LAUNCH_INSTRUCTIONS_VALIDATOR,
    PROFILE_FILENAME,
    SCHEMA_VALIDATOR,
    activation_profile_schema_validator,
    build_verification_inventory,
    configured_activation_profile_validator,
    durable_launch_instructions_validator,
    load_instructions,
    load_profile,
)
from reach_lite.validators import (
    COMPLETE_VALIDATOR_CATALOG,
    EXPECTED_VALIDATOR_NAMES,
    VALIDATOR_CATALOG,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = str(REPO_ROOT / PROFILE_FILENAME)
INSTRUCTIONS_PATH = str(REPO_ROOT / INSTRUCTIONS_FILENAME)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _kinds(result: Dict[str, Any]) -> set:
    return {f["kind"] for f in result["findings"]}


def _details(result: Dict[str, Any]) -> str:
    return " | ".join(f["detail"] for f in result["findings"])


def _resolve_browser_url(profile: Dict[str, Any]) -> str:
    url = profile["browser_url"]
    if isinstance(url, str):
        return url
    return f"{url['scheme']}://{url['host']}:{url['port']}{url['path']}"


def _health(base_url: str) -> Optional[Tuple[int, Dict[str, Any]]]:
    url = base_url.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _wait_for_readiness(base_url: str, timeout: float, marker: str) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        probe = _health(base_url)
        if probe is not None:
            status, body = probe
            if status == 200 and body.get("app") == marker:
                return True
        time.sleep(0.1)
    return False


def _launch(profile: Dict[str, Any]) -> subprocess.Popen:
    return subprocess.Popen(
        shlex.split(profile["activation_operation"]),
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _terminate(proc: subprocess.Popen) -> None:
    """Apply the profile's declared cleanup operation: SIGTERM, then SIGKILL
    after the 5-second grace period if the process has not exited."""
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture()
def live_target() -> Dict[str, Any]:
    profile = load_profile(PROFILE_PATH)
    assert profile.get("authoritative") is True, "delivered profile must be authoritative"
    base_url = _resolve_browser_url(profile)
    proc = _launch(profile)
    try:
        timeout = float(profile["readiness"]["timeout_seconds"])
        assert _wait_for_readiness(base_url, timeout, profile["operator_surface_marker"]), (
            "declared readiness signal never observed"
        )
        yield {"profile": profile, "proc": proc, "base_url": base_url}
    finally:
        _terminate(proc)


# ---------------------------------------------------------------------------
# SCH-ATL-009 ActivationProfileSchemaValidator
# ---------------------------------------------------------------------------
class TestActivationProfileSchema:
    def test_delivered_profile_conforms(self):
        profile = load_profile(PROFILE_PATH)
        result = activation_profile_schema_validator(profile, str(REPO_ROOT))
        assert result["validator"] == SCHEMA_VALIDATOR
        assert result["passed"] is True, _details(result)
        assert result["findings"] == []

    def test_delivered_profile_declares_prerequisites(self):
        profile = load_profile(PROFILE_PATH)
        prereqs = profile.get("prerequisites")
        assert isinstance(prereqs, list) and prereqs
        assert all(isinstance(p, str) and p.strip() for p in prereqs)

    def test_rejects_non_object(self):
        result = activation_profile_schema_validator("not-a-profile", str(REPO_ROOT))
        assert result["passed"] is False
        assert "missing-field" in _kinds(result)

    def test_rejects_placeholder_fields(self):
        profile = load_profile(PROFILE_PATH)
        profile["profile_id"] = "tbd"
        profile["activation_operation"] = "python3 -m reach_lite.operator_app --port <port>"
        result = activation_profile_schema_validator(profile, str(REPO_ROOT))
        assert result["passed"] is False
        assert "placeholder-value" in _kinds(result)

    def test_rejects_missing_fields(self):
        result = activation_profile_schema_validator({}, str(REPO_ROOT))
        assert result["passed"] is False
        assert "missing-field" in _kinds(result)
        details = _details(result)
        for key in ("profile_id", "working_context", "configuration_inputs", "readiness", "browser_url"):
            assert key in details

    def test_rejects_embedded_secret(self):
        profile = load_profile(PROFILE_PATH)
        profile["configuration_inputs"] = [{"name": "API_TOKEN", "secret": True, "value": "hunter2"}]
        result = activation_profile_schema_validator(profile, str(REPO_ROOT))
        assert result["passed"] is False
        assert "embedded-secret" in _kinds(result)

    def test_rejects_secret_without_reference(self):
        profile = load_profile(PROFILE_PATH)
        profile["configuration_inputs"] = [{"name": "API_TOKEN", "secret": True, "ref": ""}]
        result = activation_profile_schema_validator(profile, str(REPO_ROOT))
        assert result["passed"] is False
        assert "missing-field" in _kinds(result)

    def test_rejects_non_resolved_url(self):
        profile = load_profile(PROFILE_PATH)
        profile["browser_url"] = "localhost:9700/"
        result = activation_profile_schema_validator(profile, str(REPO_ROOT))
        assert result["passed"] is False
        assert "non-resolved-url" in _kinds(result)

    def test_rejects_missing_timeout(self):
        profile = load_profile(PROFILE_PATH)
        profile["readiness"]["timeout_seconds"] = 0
        result = activation_profile_schema_validator(profile, str(REPO_ROOT))
        assert result["passed"] is False
        assert "missing-timeout" in _kinds(result)

    def test_rejects_non_resolved_context(self):
        profile = load_profile(PROFILE_PATH)
        profile["working_context"] = {"cwd": "no_such_dir"}
        result = activation_profile_schema_validator(profile, str(REPO_ROOT))
        assert result["passed"] is False
        assert "non-resolved-context" in _kinds(result)


# ---------------------------------------------------------------------------
# REQ-ATL-037 DurableLaunchInstructionsValidator
# ---------------------------------------------------------------------------
class TestDurableLaunchInstructions:
    def test_delivered_instructions_pass(self):
        text = load_instructions(INSTRUCTIONS_PATH)
        result = durable_launch_instructions_validator(text, str(REPO_ROOT))
        assert result["validator"] == LAUNCH_INSTRUCTIONS_VALIDATOR
        assert result["passed"] is True, _details(result)
        assert result["findings"] == []

    def test_instructions_reference_delivered_artifacts(self):
        text = load_instructions(INSTRUCTIONS_PATH)
        profile = load_profile(PROFILE_PATH)
        assert PROFILE_FILENAME in text
        assert profile["activation_operation"] in text

    def test_rejects_empty(self):
        result = durable_launch_instructions_validator("", str(REPO_ROOT))
        assert result["passed"] is False
        assert "missing-section" in _kinds(result)

    def test_rejects_missing_sections(self):
        md = "# Activation\n\npython3 -m reach_lite.operator_app --port 9700\n"
        result = durable_launch_instructions_validator(md, str(REPO_ROOT))
        assert result["passed"] is False
        assert "missing-section" in _kinds(result)
        details = _details(result)
        for name in ("prerequisites", "configuration", "browser-url", "readiness", "cleanup", "failure-behavior"):
            assert name in details

    def test_rejects_unresolved_reference(self):
        md = (
            "# Prerequisites\npython3 on the host.\n"
            "# Configuration\nSee the activation profile.\n"
            "# Activation\npython3 -m reach_lite.operator_app --port 9700\n"
            "# Browser URL\nhttp://127.0.0.1:9700/\n"
            "# Readiness\nGET /api/health returns 200.\n"
            "# Cleanup\nSIGTERM then SIGKILL.\n"
            "# Failure Behavior\nSee reach_lite/does_not_exist.py for details.\n"
        )
        result = durable_launch_instructions_validator(md, str(REPO_ROOT))
        assert result["passed"] is False
        assert "unresolved-reference" in _kinds(result)

    def test_rejects_placeholder_values(self):
        md = "# Activation\n\npython3 -m reach_lite.operator_app --port <port>\n"
        result = durable_launch_instructions_validator(md, str(REPO_ROOT))
        assert result["passed"] is False
        assert "placeholder-instructions" in _kinds(result)


# ---------------------------------------------------------------------------
# REQ-ATL-038 ConfiguredActivationProfileValidator (live)
# ---------------------------------------------------------------------------
class TestConfiguredActivationProfile:
    def test_delivered_profile_is_authoritative_but_requires_verification(self):
        profile = load_profile(PROFILE_PATH)
        assert profile.get("authoritative") is True
        result = configured_activation_profile_validator([profile], None, str(REPO_ROOT))
        assert result["validator"] == CONFIGURED_PROFILE_VALIDATOR
        assert result["passed"] is False
        assert "profile-not-used-by-verification" in _kinds(result)

    def test_live_launch_is_used_by_verification(self, live_target):
        profile = live_target["profile"]
        inventory = build_verification_inventory(
            profile, live_target["base_url"], live_target["proc"].pid, True
        )
        assert inventory["used_profile_id"] == profile["profile_id"]
        result = configured_activation_profile_validator([profile], inventory, str(REPO_ROOT))
        assert result["passed"] is True, _details(result)
        assert result["findings"] == []

    def test_live_health_matches_declared_readiness(self, live_target):
        probe = _health(live_target["base_url"])
        assert probe is not None
        status, body = probe
        assert status == 200
        assert body["app"] == live_target["profile"]["operator_surface_marker"]
        assert body["status"] == "ok"

    def test_live_browser_url_serves_operator_surface(self, live_target):
        base_url = live_target["base_url"]
        assert base_url == "http://127.0.0.1:9700/"
        with urllib.request.urlopen(base_url, timeout=5) as response:
            html = response.read().decode("utf-8")
            assert response.status == 200
        assert live_target["profile"]["operator_surface_marker"] in html

    def test_failure_behavior_when_port_in_use(self, live_target):
        profile = live_target["profile"]
        second = _launch(profile)
        _out, err = second.communicate(timeout=15)
        assert second.returncode != 0
        assert "Address already in use" in err

    def test_cleanup_operation_stops_instance(self):
        profile = load_profile(PROFILE_PATH)
        base_url = _resolve_browser_url(profile)
        proc = _launch(profile)
        try:
            assert _wait_for_readiness(
                base_url,
                float(profile["readiness"]["timeout_seconds"]),
                profile["operator_surface_marker"],
            )
        finally:
            _terminate(proc)
        assert proc.returncode != 0
        assert _health(base_url) is None


def test_wp_rl_009_validators_are_not_in_pinned_catalogs():
    names = (SCHEMA_VALIDATOR, LAUNCH_INSTRUCTIONS_VALIDATOR, CONFIGURED_PROFILE_VALIDATOR)
    for name in names:
        assert name not in EXPECTED_VALIDATOR_NAMES
        assert name not in COMPLETE_VALIDATOR_CATALOG
        assert name not in VALIDATOR_CATALOG
