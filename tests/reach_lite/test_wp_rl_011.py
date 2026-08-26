"""WP-RL-011: the operator surface is presented as a styled operator
interface at the entry point and at every destination (REQ-ATL-041).

Live tests start the application as a real subprocess
("python3 -m reach_lite.operator_app"), collect the browser-served
documents for the entry point and all five destinations at the declared
viewport, and run StyledOperatorSurfaceValidator over that evidence.
Negative tests exercise each VALCAT v1.1 finding class in isolation.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from reach_lite.operator_app import FIVE_DESTINATIONS
from reach_lite.operator_surface_validator import (
    VALIDATOR_NAME,
    analyze_surface,
    build_live_surface_inventory,
    declared_viewport,
    styled_operator_surface_validator,
)
from reach_lite.validators import (
    COMPLETE_VALIDATOR_CATALOG,
    EXPECTED_VALIDATOR_NAMES,
    VALIDATOR_CATALOG,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SURFACE_NAMES = ("entry-point", *FIVE_DESTINATIONS)


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def operator_app():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "reach_lite.operator_app", "--port", str(port), "--bind", "127.0.0.1"],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    last_error: Exception | None = None
    healthy = False
    while time.time() < deadline:
        if proc.poll() is not None:
            output = proc.stdout.read().decode("utf-8", "replace") if proc.stdout else ""
            pytest.fail(f"operator application exited early (rc={proc.returncode}): {output}")
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=2) as response:
                if response.status == 200:
                    healthy = True
                    break
        except Exception as exc:  # noqa: BLE001 - readiness probe
            last_error = exc
        time.sleep(0.1)
    if not healthy:
        proc.kill()
        pytest.fail(f"operator application never became healthy: {last_error}")
    yield {"base": base, "proc": proc, "port": port}
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _kinds(result: dict) -> set[str]:
    return {item["finding"] for item in result["findings"]}


def _inventory(html: str) -> dict:
    return {
        "target_id": "operator-app",
        "viewport": {
            "declared": "width=device-width, initial-scale=1",
            "evidence": "test fixture viewport",
        },
        "surfaces": {
            name: {"url": f"/{name}", "status": 200, "html": html} for name in SURFACE_NAMES
        },
    }


STYLE = (
    "<style>:root{font-family:system-ui,sans-serif;color:#152238;background:#f6f8fb}"
    ".shell{padding:24px;gap:12px}.card{background:#fff;border:1px solid #d9e0ea;"
    "border-radius:10px;padding:16px;margin:12px 0}.status{color:#0d6135;font-weight:600}"
    "label{display:block;margin:8px 0 4px}button{background:#123b68;color:#fff;"
    "padding:8px;border-radius:6px;cursor:pointer}</style>"
)


def _page(
    body: str,
    *,
    style: bool = True,
    nav: bool = True,
    viewport: bool = True,
    doctype: bool = True,
    shell: bool = True,
) -> str:
    parts = []
    if doctype:
        parts.append("<!doctype html><html><head>")
    else:
        parts.append("<html><head>")
    if viewport:
        parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    if style:
        parts.append(STYLE)
    parts.append("</head><body>")
    if shell:
        parts.append('<main class="shell">')
    if nav:
        links = "".join(f'<a href="/{dest}">{dest.title()}</a>' for dest in FIVE_DESTINATIONS)
        parts.append(f'<nav aria-label="Operator destinations"><a href="/">Home</a>{links}</nav>')
    parts.append("<h1>Surface</h1>")
    parts.append(body)
    if shell:
        parts.append("</main>")
    parts.append("</body></html>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Live evidence: entry point + five destinations at the declared viewport
# ---------------------------------------------------------------------------


def test_live_entry_and_destinations_pass_styled_surface_validator(operator_app):
    inventory = build_live_surface_inventory(operator_app["base"])
    assert set(inventory["surfaces"]) == set(SURFACE_NAMES)
    assert "width=device-width" in inventory["viewport"]["declared"]
    for surface in inventory["surfaces"].values():
        assert surface["status"] == 200

    result = styled_operator_surface_validator(inventory)
    assert result["passed"] is True, result["findings"]
    assert result["findings"] == []
    assert result["evidence_refs"]


def test_each_live_surface_is_styled_at_declared_viewport(operator_app):
    inventory = build_live_surface_inventory(operator_app["base"])
    for name in SURFACE_NAMES:
        html = inventory["surfaces"][name]["html"]
        assert analyze_surface(html) == [], name
        assert "width=device-width" in declared_viewport(html), name


# ---------------------------------------------------------------------------
# Negative controls: one VALCAT v1.1 finding class per surface shape
# ---------------------------------------------------------------------------


def test_json_dominant_surface_fails():
    payload = json.dumps(
        {
            "agents": [
                {
                    "agent_id": f"agent-{i:02d}",
                    "state": "live",
                    "model": "llama-3.2-1b",
                    "notes": "qualification notes " * 4,
                }
                for i in range(1, 5)
            ]
        },
        indent=2,
    )
    result = styled_operator_surface_validator(_inventory(_page(f"<pre>{payload}</pre>")))
    assert result["passed"] is False
    assert "serialized-data-surface" in _kinds(result)


def test_object_repr_dominant_surface_fails():
    lines = " ".join(
        f"Agent(agent_id='agent-{i:02d}', state='live', model='llama-3.2-1b')" for i in range(1, 9)
    )
    result = styled_operator_surface_validator(_inventory(_page(f"<p>{lines}</p>")))
    assert result["passed"] is False
    assert "object-repr-surface" in _kinds(result)


def test_browser_default_styled_surface_fails():
    result = styled_operator_surface_validator(
        _inventory(_page("<p>Loaded 4 agents.</p>", style=False))
    )
    assert result["passed"] is False
    assert "browser-default-styling" in _kinds(result)


def test_raw_diagnostic_text_fails():
    diagnostic = (
        "Traceback (most recent call last):\n"
        '  File "reach_lite/operator_app.py", line 5, in <module>\n'
        "KeyError: 'agents'\n"
    )
    result = styled_operator_surface_validator(_inventory(diagnostic))
    assert result["passed"] is False
    assert "unstructured-diagnostic" in _kinds(result)


def test_missing_navigation_fails():
    result = styled_operator_surface_validator(
        _inventory(_page("<p>Loaded 4 agents.</p>", nav=False))
    )
    assert result["passed"] is False
    assert "missing-navigation" in _kinds(result)


def test_missing_controls_and_status_fails():
    result = styled_operator_surface_validator(
        _inventory(_page("<p>Loaded 4 agents.</p>"))
    )
    assert result["passed"] is False
    assert "missing-status-or-controls" in _kinds(result)


def test_missing_viewport_declaration_fails():
    result = styled_operator_surface_validator(
        _inventory(_page("<p>Loaded 4 agents.</p>", viewport=False))
    )
    assert result["passed"] is False
    assert "undeclared-viewport" in _kinds(result)


# ---------------------------------------------------------------------------
# Catalog integrity: target-level validator stays out of the pinned catalog
# ---------------------------------------------------------------------------


def test_wp_rl_011_validator_is_not_in_pinned_catalogs():
    assert VALIDATOR_NAME not in EXPECTED_VALIDATOR_NAMES
    assert VALIDATOR_NAME not in COMPLETE_VALIDATOR_CATALOG
    assert VALIDATOR_NAME not in VALIDATOR_CATALOG
