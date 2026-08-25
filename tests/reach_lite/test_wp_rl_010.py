"""WP-RL-010 — the activation profile provides a recognizable operator surface and cleans up safely.

Records one end-to-end run of the authoritative activation profile
(reach_lite/activation_profile.json) from a stopped baseline:

1. baseline   — verify the declared port is available and no target is
                already running (a failed baseline is blocking);
2. launch     — execute the profile's declared activation operation
                verbatim as a subprocess from the repository root (no
                ad hoc substitution);
3. readiness  — observe the declared readiness signal
                (GET /api/health -> 200, app == operator_surface_marker)
                within the declared timeout and record the elapsed time;
4. browser    — resolve and open the declared absolute browser URL,
                record the HTTP status and content excerpt, and verify
                the operator surface marker plus all five destinations;
5. cleanup    — apply the declared cleanup operation (SIGTERM, escalating
                to SIGKILL after the 5-second grace period) and verify
                the process exited with no stale process left on the
                declared port.

The recorded evidence is then handed to the two target-level validators
governed by SPEC-atested-reach-lite-f8de0e-v1-1.md:

* REQ-ATL-039 BrowserOpenableUrlValidator (reach_lite/launch_health.py) —
  the readiness signal, the resolved absolute URL, the HTTP response,
  and the browser evidence must present the operator surface;
* REQ-ATL-040 EndToEndLaunchHealthValidator (reach_lite/launch_health.py) —
  the baseline, the declared-operation launch, the bounded readiness
  observation, the browser check, the cleanup, and the run transcript
  must all be recorded and healthy.

Both validators are target-level and are deliberately NOT part of the
pinned 43/44-validator catalog; the final test re-asserts that.
"""
from __future__ import annotations

import json
import shlex
import signal
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import pytest

from reach_lite.launch_health import (
    BROWSER_URL_VALIDATOR,
    E2E_HEALTH_VALIDATOR,
    browser_openable_url_validator,
    end_to_end_launch_health_validator,
)
from reach_lite.launch_profile import PROFILE_FILENAME, load_profile
from reach_lite.operator_app import FIVE_DESTINATIONS
from reach_lite.validators import (
    COMPLETE_VALIDATOR_CATALOG,
    EXPECTED_VALIDATOR_NAMES,
    VALIDATOR_CATALOG,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_PATH = str(REPO_ROOT / PROFILE_FILENAME)
CLEANUP_GRACE_SECONDS = 5.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve_browser_url(profile: Dict[str, Any]) -> str:
    url = profile["browser_url"]
    if isinstance(url, str):
        return url
    return f"{url['scheme']}://{url['host']}:{url['port']}{url['path']}"


def _port_of(base_url: str) -> int:
    return urlparse(base_url).port or 80


def _health(base_url: str) -> Optional[Tuple[int, Dict[str, Any]]]:
    url = base_url.rstrip("/") + "/api/health"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def _port_available(port: int) -> bool:
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        probe.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        probe.close()


def _get(url: str, timeout: float = 5.0) -> Tuple[int, str]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8")


def _launch_declared(profile: Dict[str, Any]) -> subprocess.Popen:
    """Execute the profile's declared activation operation verbatim."""
    return subprocess.Popen(
        shlex.split(profile["activation_operation"]),
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _apply_cleanup(proc: subprocess.Popen) -> str:
    """Declared cleanup: SIGTERM, then SIGKILL after the 5-second grace."""
    proc.send_signal(signal.SIGTERM)
    try:
        proc.wait(timeout=CLEANUP_GRACE_SECONDS)
        return "SIGTERM"
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=CLEANUP_GRACE_SECONDS)
        return "SIGTERM+SIGKILL"


# ---------------------------------------------------------------------------
# The one recorded run
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def recorded_run() -> Dict[str, Any]:
    """Record one end-to-end run of the authoritative activation profile.

    Every step failure is blocking: the fixture fails the session rather
    than silently substituting a fallback, per the dispatch scope.
    """
    profile = load_profile(PROFILE_PATH)
    assert profile.get("authoritative") is True, "delivered profile must be authoritative"
    base_url = _resolve_browser_url(profile)
    port = _port_of(base_url)
    marker = profile["operator_surface_marker"]
    transcript: list[str] = []
    evidence_refs = [PROFILE_FILENAME, "recorded_run_transcript"]

    # 1. stopped baseline ---------------------------------------------------
    probe = _health(base_url)
    target_already_running = probe is not None and probe[0] == 200
    port_ok = _port_available(port)
    baseline = {"target_already_running": target_already_running, "port_available": port_ok}
    if target_already_running or not port_ok:
        pytest.fail(
            f"blocking: stopped baseline not established — port {port} already "
            f"serving (target_already_running={target_already_running})"
        )
    transcript.append(f"baseline: port {port} available, no target already running")

    proc = _launch_declared(profile)
    try:
        launch = {
            "profile_id": profile["profile_id"],
            "authoritative": True,
            "declared_operation_used": True,
            "ad_hoc_substitution": False,
            "process_started": proc.poll() is None,
            "pid": proc.pid,
        }
        if not launch["process_started"]:
            pytest.fail("blocking: declared activation operation did not start a process")
        transcript.append(
            f"launch: {profile['activation_operation']} (pid {proc.pid}) "
            f"profile={profile['profile_id']} (authoritative, declared operation verbatim)"
        )

        # 3. bounded readiness ---------------------------------------------
        timeout = float(profile["readiness"]["timeout_seconds"])
        deadline = time.monotonic() + timeout
        observed = False
        while time.monotonic() < deadline:
            probe = _health(base_url)
            if probe is not None and probe[0] == 200 and probe[1].get("app") == marker:
                observed = True
                break
            time.sleep(0.1)
        elapsed = timeout - (deadline - time.monotonic())
        readiness = {
            "observed": observed,
            "within_declared_timeout": observed,
            "declared_timeout_seconds": timeout,
            "elapsed_seconds": round(elapsed, 3),
        }
        if not observed:
            pytest.fail(f"blocking: declared readiness signal not observed within {timeout}s")
        transcript.append(
            f"readiness: GET /api/health -> 200 app={marker} "
            f"(elapsed {readiness['elapsed_seconds']}s within declared {timeout}s)"
        )

        # 4. browser surface -------------------------------------------------
        status, html = _get(base_url)
        marker_present = marker in html
        destinations: Dict[str, bool] = {}
        for dest in FIVE_DESTINATIONS:
            try:
                dest_status, _body = _get(f"{base_url.rstrip('/')}/{dest}")
                destinations[dest] = dest_status == 200
                transcript.append(f"browser: GET /{dest} -> {dest_status}")
            except (urllib.error.URLError, OSError):
                destinations[dest] = False
                transcript.append(f"browser: GET /{dest} -> connection failure")
        browser = {
            "status": status,
            "surface_marker_present": marker_present,
            "resolved_url": base_url,
        }
        if status != 200 or not marker_present or not all(destinations.values()):
            pytest.fail(
                f"blocking: operator surface not recognizable — status={status}, "
                f"marker_present={marker_present}, destinations={destinations}"
            )
        transcript.append(
            f"browser: GET {base_url} -> {status}, marker '{marker}' present, "
            f"destinations {list(FIVE_DESTINATIONS)} all served"
        )

        # 5. declared cleanup ------------------------------------------------
        method = _apply_cleanup(proc)
        stale_probe = _health(base_url)
        process_exited = proc.poll() is not None
        stale_process = not process_exited or (
            stale_probe is not None and stale_probe[0] == 200
        )
        cleanup = {
            "executed": True,
            "process_exited": process_exited,
            "stale_process": stale_process,
            "method": method,
        }
        if not process_exited or stale_process:
            pytest.fail(
                f"blocking: cleanup incomplete — process_exited={process_exited}, "
                f"stale_process={stale_process}"
            )
        transcript.append(
            f"cleanup: {method} -> process exited (pid {proc.pid}), "
            f"port {port} no longer serving, no stale process"
        )
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=CLEANUP_GRACE_SECONDS)

    browser_evidence = {
        "surface_marker": marker,
        "marker_present": marker_present,
        "destinations": destinations,
    }
    evidence = {
        "baseline": baseline,
        "launch": launch,
        "readiness": readiness,
        "browser": browser,
        "cleanup": cleanup,
        "transcript": transcript,
        "evidence_refs": evidence_refs,
        # REQ-ATL-039 evidence shape
        "url": {
            "declared": base_url,
            "resolved": base_url,
            "placeholder_substituted": False,
        },
        "http_response": {
            "status": status,
            "content_excerpt": html[:200],
        },
        "browser_evidence": browser_evidence,
    }
    return {"profile": profile, "evidence": evidence, "proc": proc}


# ---------------------------------------------------------------------------
# REQ-ATL-039 BrowserOpenableUrlValidator against the recorded run
# ---------------------------------------------------------------------------
def _good_browser_evidence() -> Dict[str, Any]:
    return {
        "readiness": {"reported_ready": True},
        "url": {
            "declared": "http://127.0.0.1:9700/",
            "resolved": "http://127.0.0.1:9700/",
            "placeholder_substituted": False,
        },
        "http_response": {
            "status": 200,
            "content_excerpt": "<title>reach-lite-operator</title>",
        },
        "browser_evidence": {
            "surface_marker": "reach-lite-operator",
            "marker_present": True,
            "destinations": {dest: True for dest in FIVE_DESTINATIONS},
        },
        "evidence_refs": ["recorded_run_transcript"],
    }


class TestBrowserOpenableUrl:
    def test_recorded_run_passes_browser_openable_url_validator(self, recorded_run):
        """REQ-ATL-039: the single recorded run presents the operator surface."""
        evidence = dict(recorded_run["evidence"])
        evidence["readiness"] = {
            "reported_ready": bool(evidence["readiness"]["observed"])
        }
        result = browser_openable_url_validator(evidence)
        assert result["validator"] == BROWSER_URL_VALIDATOR
        assert result["passed"] is True, "; ".join(
            f"{f['kind']}: {f['detail']}" for f in result["findings"]
        )
        assert result["findings"] == []
        assert result["evidence_refs"] == evidence["evidence_refs"]

    def test_recorded_run_browser_evidence_is_complete(self, recorded_run):
        ev = recorded_run["evidence"]
        assert ev["url"]["resolved"] == "http://127.0.0.1:9700/"
        assert ev["url"]["placeholder_substituted"] is False
        assert ev["http_response"]["status"] == 200
        assert ev["browser_evidence"]["marker_present"] is True
        assert set(ev["browser_evidence"]["destinations"]) == set(FIVE_DESTINATIONS)
        assert all(ev["browser_evidence"]["destinations"].values())

    def _kinds(self, result: Dict[str, Any]) -> set:
        return {f["kind"] for f in result["findings"]}

    def test_rejects_profile_not_ready(self):
        evidence = _good_browser_evidence()
        evidence["readiness"] = {"reported_ready": False}
        result = browser_openable_url_validator(evidence)
        assert result["passed"] is False
        assert "profile-not-ready" in self._kinds(result)

    def test_rejects_non_absolute_url(self):
        evidence = _good_browser_evidence()
        evidence["url"]["resolved"] = "localhost:9700/"
        result = browser_openable_url_validator(evidence)
        assert result["passed"] is False
        assert "non-absolute-url" in self._kinds(result)

    def test_rejects_placeholder_substitution(self):
        evidence = _good_browser_evidence()
        evidence["url"]["placeholder_substituted"] = True
        result = browser_openable_url_validator(evidence)
        assert result["passed"] is False
        assert "placeholder-substitution" in self._kinds(result)

    def test_rejects_unsuccessful_response(self):
        evidence = _good_browser_evidence()
        evidence["http_response"]["status"] = 500
        result = browser_openable_url_validator(evidence)
        assert result["passed"] is False
        assert "unsuccessful-response" in self._kinds(result)

    def test_rejects_unrecognizable_surface(self):
        evidence = _good_browser_evidence()
        evidence["browser_evidence"]["marker_present"] = False
        result = browser_openable_url_validator(evidence)
        assert result["passed"] is False
        assert "unrecognizable-surface" in self._kinds(result)

    def test_rejects_missing_destination(self):
        evidence = _good_browser_evidence()
        evidence["browser_evidence"]["destinations"]["settings"] = False
        result = browser_openable_url_validator(evidence)
        assert result["passed"] is False
        kinds = self._kinds(result)
        assert "missing-destination" in kinds
        assert any(
            "settings" in f["detail"]
            for f in result["findings"]
            if f["kind"] == "missing-destination"
        )


# ---------------------------------------------------------------------------
# REQ-ATL-040 EndToEndLaunchHealthValidator against the recorded run
# ---------------------------------------------------------------------------
def _good_e2e_evidence() -> Dict[str, Any]:
    return {
        "baseline": {"target_already_running": False, "port_available": True},
        "launch": {
            "profile_id": "reach-lite-operator-default",
            "authoritative": True,
            "declared_operation_used": True,
            "ad_hoc_substitution": False,
            "process_started": True,
            "pid": 4242,
        },
        "readiness": {
            "observed": True,
            "within_declared_timeout": True,
            "declared_timeout_seconds": 20.0,
            "elapsed_seconds": 0.4,
        },
        "browser": {
            "status": 200,
            "surface_marker_present": True,
            "resolved_url": "http://127.0.0.1:9700/",
        },
        "cleanup": {
            "executed": True,
            "process_exited": True,
            "stale_process": False,
            "method": "SIGTERM",
        },
        "transcript": [
            "baseline: port 9700 available, no target already running",
            "launch: python3 -m reach_lite.operator_app --port 9700 (pid 4242)",
            "readiness: GET /api/health -> 200 app=reach-lite-operator (0.4s within 20.0s)",
            "browser: GET http://127.0.0.1:9700/ -> 200, marker present",
            "cleanup: SIGTERM -> process exited, no stale process",
        ],
        "evidence_refs": ["reach_lite/activation_profile.json", "recorded_run_transcript"],
    }


class TestEndToEndLaunchHealth:
    def test_recorded_run_passes_end_to_end_launch_health_validator(self, recorded_run):
        """REQ-ATL-040: the single recorded run is healthy end to end."""
        evidence = dict(recorded_run["evidence"])
        result = end_to_end_launch_health_validator(evidence)
        assert result["validator"] == E2E_HEALTH_VALIDATOR
        assert result["passed"] is True, "; ".join(
            f"{f['kind']}: {f['detail']}" for f in result["findings"]
        )
        assert result["findings"] == []
        assert result["evidence_refs"] == evidence["evidence_refs"]

    def test_recorded_run_stopped_baseline(self, recorded_run):
        baseline = recorded_run["evidence"]["baseline"]
        assert baseline["target_already_running"] is False
        assert baseline["port_available"] is True

    def test_recorded_run_used_declared_operation_verbatim(self, recorded_run):
        launch = recorded_run["evidence"]["launch"]
        profile = recorded_run["profile"]
        assert launch["profile_id"] == profile["profile_id"]
        assert launch["authoritative"] is True
        assert launch["declared_operation_used"] is True
        assert launch["ad_hoc_substitution"] is False
        assert launch["process_started"] is True
        assert isinstance(launch["pid"], int)

    def test_recorded_run_readiness_within_declared_timeout(self, recorded_run):
        readiness = recorded_run["evidence"]["readiness"]
        assert readiness["observed"] is True
        assert readiness["within_declared_timeout"] is True
        assert 0.0 <= readiness["elapsed_seconds"] <= readiness["declared_timeout_seconds"]

    def test_recorded_run_cleanup_complete(self, recorded_run):
        cleanup = recorded_run["evidence"]["cleanup"]
        assert cleanup["executed"] is True
        assert cleanup["process_exited"] is True
        assert cleanup["stale_process"] is False
        assert cleanup["method"] in ("SIGTERM", "SIGTERM+SIGKILL")

    def test_recorded_run_transcript_covers_every_step(self, recorded_run):
        transcript = recorded_run["evidence"]["transcript"]
        assert len(transcript) >= 6
        text = " ".join(transcript)
        for needle in ("baseline", "launch", "readiness", "browser", "cleanup"):
            assert needle in text, f"transcript missing step: {needle}"

    def _kinds(self, result: Dict[str, Any]) -> set:
        return {f["kind"] for f in result["findings"]}

    def test_rejects_preexisting_target(self):
        evidence = _good_e2e_evidence()
        evidence["baseline"]["target_already_running"] = True
        result = end_to_end_launch_health_validator(evidence)
        assert result["passed"] is False
        assert "preexisting-target" in self._kinds(result)

    def test_rejects_ad_hoc_launch_substitution(self):
        evidence = _good_e2e_evidence()
        evidence["launch"]["ad_hoc_substitution"] = True
        result = end_to_end_launch_health_validator(evidence)
        assert result["passed"] is False
        assert "ad-hoc-launch-substitution" in self._kinds(result)

    def test_rejects_readiness_timeout(self):
        evidence = _good_e2e_evidence()
        evidence["readiness"]["within_declared_timeout"] = False
        result = end_to_end_launch_health_validator(evidence)
        assert result["passed"] is False
        assert "readiness-timeout" in self._kinds(result)

    def test_rejects_failed_browser_check(self):
        evidence = _good_e2e_evidence()
        evidence["browser"]["surface_marker_present"] = False
        result = end_to_end_launch_health_validator(evidence)
        assert result["passed"] is False
        assert "failed-browser-check" in self._kinds(result)

    def test_rejects_incomplete_cleanup(self):
        evidence = _good_e2e_evidence()
        evidence["cleanup"]["process_exited"] = False
        evidence["cleanup"]["stale_process"] = True
        result = end_to_end_launch_health_validator(evidence)
        assert result["passed"] is False
        assert "incomplete-cleanup" in self._kinds(result)

    def test_rejects_missing_transcript(self):
        evidence = _good_e2e_evidence()
        evidence["transcript"] = []
        result = end_to_end_launch_health_validator(evidence)
        assert result["passed"] is False
        assert "missing-transcript" in self._kinds(result)


# ---------------------------------------------------------------------------
# Catalog integrity
# ---------------------------------------------------------------------------
def test_wp_rl_010_validators_are_not_in_pinned_catalogs():
    for name in (BROWSER_URL_VALIDATOR, E2E_HEALTH_VALIDATOR):
        assert name not in EXPECTED_VALIDATOR_NAMES
        assert name not in COMPLETE_VALIDATOR_CATALOG
        assert name not in VALIDATOR_CATALOG
