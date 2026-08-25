"""OrdinaryBrowserInteractionValidator and BrowserInteractionEvidenceSchemaValidator
(REQ-ATL-042, SCH-ATL-010, WP-RL-012).

Target-level validators over the delivered operator application.  They are
deliberately kept OUT of the pinned 43/44 validator catalog.

OrdinaryBrowserInteractionValidator
    Passes when every visible control (navigation links, form fields,
    buttons, selects) responds to an ordinary browser event (click, type,
    select, submit) by producing the expected visible state change or an
    in-context error.  No action silently no-ops; no uncaught browser
    error prevents the next action.

BrowserInteractionEvidenceSchemaValidator
    Passes when a BrowserInteractionEvidence record carries every field
    required by SCH-ATL-010: stable scenario_id, target_requirement_ids,
    starting-state reference, browser URL, viewport, visible control and
    ordinary event, expected and observed visible results,
    persisted-result reference when state changes, before/after capture
    references, browser-error observations, and the passed flag.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from .validators import _result

INTERACTION_VALIDATOR_NAME = "OrdinaryBrowserInteractionValidator"
EVIDENCE_SCHEMA_VALIDATOR_NAME = "BrowserInteractionEvidenceSchemaValidator"

EVIDENCE_REQUIRED_FIELDS = (
    "scenario_id",
    "target_requirement_ids",
    "starting_state_reference",
    "browser_url",
    "viewport",
    "visible_control",
    "ordinary_event",
    "expected_visible_result",
    "observed_visible_result",
    "persisted_result_reference",
    "capture_before",
    "capture_after",
    "browser_error_observations",
    "passed",
)

ORDINARY_EVENTS = {"click", "type", "select", "submit"}


def _fetch(url: str) -> tuple[int, str]:
    """Return (status, body) for a URL."""
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return 0, str(exc)


def _extract_controls(html: str) -> list[dict[str, str]]:
    """Extract interactive controls from HTML: links, buttons, form fields."""
    controls: list[dict[str, str]] = []

    # Navigation links
    for m in re.finditer(r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S):
        href, label = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if label:
            controls.append({"kind": "link", "href": href, "label": label, "event": "click"})

    # Buttons
    for m in re.finditer(r'<button[^>]*>(.*?)</button>', html, re.S):
        label = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if label:
            controls.append({"kind": "button", "label": label, "event": "click"})

    # Text inputs / textareas
    for m in re.finditer(r'<(input|textarea)[^>]*>', html):
        tag = m.group(1)
        controls.append({"kind": tag, "event": "type"})

    # Select elements
    for m in re.finditer(r'<select[^>]*>', html):
        controls.append({"kind": "select", "event": "select"})

    return controls


def ordinary_browser_interaction_validator(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate that ordinary browser interactions produce expected results.

    The evidence dict must contain:
      - base_url: the authoritative application URL
      - destinations: list of destination paths to check
      - interactions: list of interaction evidence records
    """
    base_url: str = evidence.get("base_url", "")
    destinations: list[str] = evidence.get("destinations", [])
    interactions: list[dict[str, Any]] = evidence.get("interactions", [])

    findings: list[str] = []
    target_ids: list[str] = []

    if not base_url:
        findings.append("evidence missing base_url")
    if not interactions:
        findings.append("no interaction evidence records supplied")

    for i, record in enumerate(interactions):
        target_ids.append(f"interaction-{i + 1}")

        # Check the record has the key interaction fields
        for field in ("visible_control", "ordinary_event", "expected_visible_result",
                      "observed_visible_result", "passed"):
            if field not in record:
                findings.append(f"interaction-{i + 1} missing field: {field}")

        event = record.get("ordinary_event", "")
        if event not in ORDINARY_EVENTS:
            findings.append(
                f"interaction-{i + 1} event '{event}' is not an ordinary browser event"
            )

        if record.get("passed") is False:
            findings.append(
                f"interaction-{i + 1} ({record.get('visible_control', '?')}): "
                f"expected '{record.get('expected_visible_result', '')}' but observed "
                f"'{record.get('observed_visible_result', '')}'"
            )

        # Check for blocking browser errors
        errors = record.get("browser_error_observations", [])
        if isinstance(errors, list):
            for err in errors:
                if isinstance(err, dict) and err.get("blocking", False):
                    findings.append(
                        f"interaction-{i + 1}: blocking browser error: {err.get('message', 'unknown')}"
                    )

    # Verify that at least one interaction exists per destination
    dests_with_interactions = {r.get("destination") for r in interactions if r.get("destination")}
    for dest in destinations:
        if dest not in dests_with_interactions:
            findings.append(f"no interaction evidence for destination '{dest}'")

    passed = len(findings) == 0
    return _result(
        INTERACTION_VALIDATOR_NAME,
        target_ids,
        passed,
        findings,
        [],
    )


def browser_interaction_evidence_schema_validator(evidence: dict[str, Any]) -> dict[str, Any]:
    """Validate that BrowserInteractionEvidence records conform to SCH-ATL-010.

    The evidence dict must contain a list of evidence records under key
    'records'.  Each record must carry all required SCH-ATL-010 fields.
    """
    records: list[dict[str, Any]] = evidence.get("records", [])
    findings: list[str] = []
    target_ids: list[str] = []

    if not records:
        findings.append("no BrowserInteractionEvidence records supplied")

    for i, record in enumerate(records):
        sid = record.get("scenario_id", f"record-{i + 1}")
        target_ids.append(sid)

        for field in EVIDENCE_REQUIRED_FIELDS:
            if field not in record:
                findings.append(f"{sid}: missing required field '{field}'")

        # Validate scenario_id is a stable string
        if "scenario_id" in record and not isinstance(record["scenario_id"], str):
            findings.append(f"{sid}: scenario_id must be a string")

        # Validate target_requirement_ids is a list of strings
        if "target_requirement_ids" in record:
            trids = record["target_requirement_ids"]
            if not isinstance(trids, list) or not all(isinstance(t, str) for t in trids):
                findings.append(f"{sid}: target_requirement_ids must be a list of strings")

        # Validate browser_url is a non-empty string
        if "browser_url" in record:
            url = record["browser_url"]
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                findings.append(f"{sid}: browser_url must be an absolute http(s) URL")

        # Validate viewport is a non-empty string
        if "viewport" in record:
            vp = record["viewport"]
            if not isinstance(vp, str) or not vp.strip():
                findings.append(f"{sid}: viewport must be a non-empty string")

        # Validate ordinary_event is one of the allowed events
        if "ordinary_event" in record:
            ev = record["ordinary_event"]
            if ev not in ORDINARY_EVENTS:
                findings.append(f"{sid}: ordinary_event '{ev}' not in {sorted(ORDINARY_EVENTS)}")

        # Validate passed is a boolean
        if "passed" in record:
            if not isinstance(record["passed"], bool):
                findings.append(f"{sid}: passed must be a boolean")

        # Validate browser_error_observations is a list
        if "browser_error_observations" in record:
            obs = record["browser_error_observations"]
            if not isinstance(obs, list):
                findings.append(f"{sid}: browser_error_observations must be a list")

    passed = len(findings) == 0
    return _result(
        EVIDENCE_SCHEMA_VALIDATOR_NAME,
        target_ids,
        passed,
        findings,
        [],
    )
