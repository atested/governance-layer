"""WP-RL-010 — Browser-Openable URL and End-to-End Launch Health Check.

Implements the two target-level validators that gate application handoff of
the Reach Lite operator application:

REQ-ATL-039 BrowserOpenableUrlValidator
    When the configured activation profile reports ready, it provides an
    absolute HTTP or HTTPS URL that a browser on the self-host environment
    can open to the Reach Lite operator application.  The recorded launch
    evidence shows the declared URL resolving without placeholder
    substitution, returning a successful response, and rendering a
    recognizable Reach Lite operator surface with the five primary
    destinations available.

REQ-ATL-040 EndToEndLaunchHealthValidator
    Before Application handoff, the delivery passes an end-to-end launch
    health check that uses the configured activation profile to start the
    application, waits for its declared readiness condition, opens its
    declared browser URL, confirms the operator surface, and executes its
    declared cleanup operation.  One recorded check begins with no
    already-running target, uses the handed-off profile without ad hoc
    launch substitution, observes ready within the declared timeout,
    receives a successful browser response containing a recognizable
    operator-surface marker, and finishes with clean shutdown; any failed
    step yields a failing result and blocks handoff.

These are target-level validators (like WP-RL-008's
RunnableOperatorApplicationValidator and WP-RL-009's launch-profile
validators) and are deliberately NOT registered in
reach_lite.validators.VALIDATOR_CATALOG / EXPECTED_VALIDATOR_NAMES /
COMPLETE_VALIDATOR_CATALOG.  They operate on evidence collected from one
recorded run against the live target, not on in-memory fixture
inventories, so the pinned 43/44 catalog counts are untouched.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence
from urllib.parse import urlparse

from .operator_app import FIVE_DESTINATIONS
from .validators import _result

# ---------------------------------------------------------------------------
# Validator identities
# ---------------------------------------------------------------------------
BROWSER_URL_VALIDATOR = "BrowserOpenableUrlValidator"
E2E_HEALTH_VALIDATOR = "EndToEndLaunchHealthValidator"

# ---------------------------------------------------------------------------
# Finding classes per validator (VALCAT v1.1 style).
# ---------------------------------------------------------------------------
BROWSER_URL_FINDING_CLASSES = (
    "profile-not-ready",
    "non-absolute-url",
    "placeholder-substitution",
    "unsuccessful-response",
    "unrecognizable-surface",
    "missing-destination",
)
E2E_HEALTH_FINDING_CLASSES = (
    "preexisting-target",
    "ad-hoc-launch-substitution",
    "readiness-timeout",
    "failed-browser-check",
    "incomplete-cleanup",
    "missing-transcript",
)


def _finding(kind: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "detail": detail}


# Same placeholder-token heuristic the WP-RL-009 schema validator uses, so a
# URL that still carries an unresolved token is rejected at the browser-open
# step as well.
_PLACEHOLDER_RE = re.compile(r"<[^<>s]{1,40}>|\{\{|\}\}|tbd|change_me|fill in")


def _is_absolute_http_url(value: Any) -> bool:
    """True when value is an absolute http:// or https:// URL."""
    if not isinstance(value, str) or not value.strip():
        return False
    parts = urlparse(value)
    return parts.scheme in ("http", "https") and bool(parts.netloc)


# ---------------------------------------------------------------------------
# REQ-ATL-039 BrowserOpenableUrlValidator
# ---------------------------------------------------------------------------
def browser_openable_url_validator(
    evidence: Dict[str, Any],
    expected_destinations: Sequence[str] = FIVE_DESTINATIONS,
) -> Dict[str, Any]:
    """Validate one recorded browser-open run of the declared URL.

    evidence keys:
      readiness:        {"reported_ready": bool}
      url:              {"declared": ..., "resolved": str,
                         "placeholder_substituted": bool}
      http_response:    {"status": int, "content_excerpt": str}
      browser_evidence: {"surface_marker": str, "marker_present": bool,
                         "destinations": {name: bool}}
      evidence_refs:    [str, ...]
    """
    findings: List[Dict[str, str]] = []

    readiness = evidence.get("readiness") or {}
    if not readiness.get("reported_ready"):
        findings.append(
            _finding("profile-not-ready", "the configured activation profile did not report ready")
        )

    url = evidence.get("url") or {}
    resolved = url.get("resolved")
    if not _is_absolute_http_url(resolved):
        findings.append(
            _finding("non-absolute-url", f"resolved browser URL is not an absolute HTTP/HTTPS URL: {resolved!r}")
        )
    if url.get("placeholder_substituted") or (
        isinstance(resolved, str) and _PLACEHOLDER_RE.search(resolved)
    ):
        findings.append(
            _finding(
                "placeholder-substitution",
                f"declared URL required placeholder substitution or still carries a placeholder: {resolved!r}",
            )
        )

    response = evidence.get("http_response") or {}
    status = response.get("status")
    body = response.get("content_excerpt") or ""
    if not (isinstance(status, int) and 200 <= status < 300):
        findings.append(
            _finding("unsuccessful-response", f"browser open returned unsuccessful status {status!r}")
        )

    browser = evidence.get("browser_evidence") or {}
    marker = browser.get("surface_marker")
    marker_present = (
        bool(browser.get("marker_present"))
        and isinstance(marker, str)
        and marker != ""
        and marker in body
    )
    if not marker_present:
        findings.append(
            _finding(
                "unrecognizable-surface",
                f"rendered response does not contain the recognizable operator-surface marker {marker!r}",
            )
        )

    destinations = browser.get("destinations") or {}
    missing = [name for name in expected_destinations if not destinations.get(name)]
    if missing:
        findings.append(
            _finding("missing-destination", f"primary destinations not available in the rendered surface: {missing}")
        )

    return _result(
        BROWSER_URL_VALIDATOR,
        ["REQ-ATL-039"],
        not findings,
        findings,
        list(evidence.get("evidence_refs") or []),
    )


# ---------------------------------------------------------------------------
# REQ-ATL-040 EndToEndLaunchHealthValidator
# ---------------------------------------------------------------------------
def end_to_end_launch_health_validator(evidence: Dict[str, Any]) -> Dict[str, Any]:
    """Validate one recorded end-to-end launch health check.

    evidence keys:
      baseline:   {"target_already_running": bool, "port_available": bool}
      launch:     {"profile_id": str, "authoritative": bool,
                   "declared_operation_used": bool, "ad_hoc_substitution": bool,
                   "process_started": bool, "pid": int}
      readiness:  {"observed": bool, "within_declared_timeout": bool,
                   "declared_timeout_seconds": number, "elapsed_seconds": number}
      browser:    {"status": int, "surface_marker_present": bool,
                   "resolved_url": str}
      cleanup:    {"executed": bool, "process_exited": bool,
                   "stale_process": bool, "method": str}
      transcript: [str, ...]   (recorded step-by-step run transcript)
      evidence_refs: [str, ...]
    """
    findings: List[Dict[str, str]] = []

    baseline = evidence.get("baseline") or {}
    if baseline.get("target_already_running") or not baseline.get("port_available"):
        findings.append(
            _finding(
                "preexisting-target",
                "the check did not begin from a stopped baseline (target already running or port unavailable)",
            )
        )

    launch = evidence.get("launch") or {}
    if (
        not launch.get("authoritative")
        or not launch.get("declared_operation_used")
        or launch.get("ad_hoc_substitution")
        or not launch.get("process_started")
    ):
        findings.append(
            _finding(
                "ad-hoc-launch-substitution",
                "launch did not use the handed-off authoritative profile's declared activation operation",
            )
        )

    readiness = evidence.get("readiness") or {}
    if not readiness.get("observed") or not readiness.get("within_declared_timeout"):
        findings.append(
            _finding(
                "readiness-timeout",
                "declared readiness condition was not observed within the declared timeout "
                f"(observed={readiness.get('observed')}, "
                f"elapsed={readiness.get('elapsed_seconds')}, "
                f"timeout={readiness.get('declared_timeout_seconds')})",
            )
        )

    browser = evidence.get("browser") or {}
    status = browser.get("status")
    if not (isinstance(status, int) and 200 <= status < 300) or not browser.get("surface_marker_present"):
        findings.append(
            _finding(
                "failed-browser-check",
                f"browser open of {browser.get('resolved_url')!r} was unsuccessful or missing the "
                f"operator-surface marker (status={status!r}, "
                f"marker_present={browser.get('surface_marker_present')!r})",
            )
        )

    cleanup = evidence.get("cleanup") or {}
    if not cleanup.get("executed") or not cleanup.get("process_exited") or cleanup.get("stale_process"):
        findings.append(
            _finding(
                "incomplete-cleanup",
                "declared cleanup did not finish with a clean shutdown "
                f"(executed={cleanup.get('executed')!r}, exited={cleanup.get('process_exited')!r}, "
                f"stale={cleanup.get('stale_process')!r}, method={cleanup.get('method')!r})",
            )
        )

    transcript = evidence.get("transcript")
    if not (
        isinstance(transcript, list)
        and transcript
        and all(isinstance(line, str) and line for line in transcript)
    ):
        findings.append(
            _finding("missing-transcript", "the recorded run transcript is absent or incomplete")
        )

    return _result(
        E2E_HEALTH_VALIDATOR,
        ["REQ-ATL-040"],
        not findings,
        findings,
        list(evidence.get("evidence_refs") or []),
    )
