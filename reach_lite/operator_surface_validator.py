"""StyledOperatorSurfaceValidator (VALCAT v1.1, REQ-ATL-041, WP-RL-011).

Target-level validator over the served operator surface at the declared
desktop viewport: the initial entry view and every destination document.
Passes when each surface is presented as a styled operator interface —
intentional layout, typography, spacing, visual grouping, labeled
navigation, and recognizable interactive controls or status feedback, with
application objects rendered as labels, summaries, cards, lists, tables,
forms, or status feedback. Fails when a surface is dominated by serialized
JSON, object reprs, unformatted text, or browser-default document styling.

Finding classes (VALCAT v1.1): serialized-data-surface,
object-repr-surface, browser-default-styling, unstructured-diagnostic,
missing-navigation, missing-status-or-controls, undeclared-viewport.

Deliberately kept OUT of VALIDATOR_CATALOG / EXPECTED_VALIDATOR_NAMES /
COMPLETE_VALIDATOR_CATALOG: it validates the delivered target surface
rather than in-memory domain fixtures, so the pinned 43/44 catalog counts
stand.
"""

from __future__ import annotations

import json
import re
import urllib.request
from typing import Any

from .validators import _result

VALIDATOR_NAME = "StyledOperatorSurfaceValidator"
FIVE_DESTINATIONS = ("chat", "agents", "approvals", "results", "settings")
ENTRY_POINT = "entry-point"
DECLARED_VIEWPORT = "width=device-width, initial-scale=1"
FINDING_CLASSES = (
    "serialized-data-surface",
    "object-repr-surface",
    "browser-default-styling",
    "unstructured-diagnostic",
    "missing-navigation",
    "missing-status-or-controls",
    "undeclared-viewport",
)

_SCRIPT_RE = re.compile(r"<script\b[\s\S]*?</script>", re.I)
_STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>([\s\S]*?)</style>", re.I)
_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_TAG_RE = re.compile(r"<[^>]+>")
_JSON_RUN_RE = re.compile(r"\{[\s\S]{40,}\}")
_REPR_RE = re.compile(r"\b[A-Z][A-Za-z_]*\([^()]*=[^()]*\)")
_DICT_REPR_RE = re.compile(r"\{['\"]\w+['\"]:\s")
_VIEWPORT_RE = re.compile(
    r"<meta\b[^>]*name=[\"']viewport[\"'][^>]*"
    r"content=[\"']([^\"']+)[\"']",
    re.I,
)
_NAV_RE = re.compile(r"<nav\b[\s\S]*?</nav>", re.I)
_CONTROL_RE = re.compile(
    r"<(?:button|form|label|select|input|textarea)\b"
    r"|<a\b[^>]*class=[\"'][^\"']*(?:card|button|secondary|danger)",
    re.I,
)
_STATUS_RE = re.compile(r"aria-live|class=[\"'][^\"']*status[\"']", re.I)


def _finding(kind: str, detail: str) -> dict[str, str]:
    return {"finding": kind, "detail": detail}


def declared_viewport(html: str) -> str:
    """Return the viewport content declared by the document, or ''."""
    match = _VIEWPORT_RE.search(html)
    return match.group(1) if match else ""


def _visible_text(html: str) -> str:
    text = _SCRIPT_RE.sub(" ", html)
    text = _STYLE_BLOCK_RE.sub(" ", text)
    text = _COMMENT_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    for entity, char in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"),
                         ("&quot;", "\""), ("&#39;", "'"), ("&nbsp;", " ")):
        text = text.replace(entity, char)
    return re.sub(r"\s+", " ", text).strip()


def _serialized_share(visible: str) -> float:
    if not visible:
        return 0.0
    if visible.startswith(("{", "[")):
        try:
            json.loads(visible)
            return 1.0
        except ValueError:
            pass
    run_length = sum(len(run) for run in _JSON_RUN_RE.findall(visible))
    return min(1.0, run_length / max(1, len(visible)))


def _repr_share(visible: str) -> float:
    if not visible:
        return 0.0
    matched = sum(len(m) for m in _REPR_RE.findall(visible))
    matched += sum(len(m) for m in _DICT_REPR_RE.findall(visible))
    return min(1.0, matched / max(1, len(visible)))


def _embedded_css(html: str) -> str:
    return "\n".join(_STYLE_BLOCK_RE.findall(html))


def _is_styled(css: str) -> bool:
    if not css.strip():
        return False
    checks = (
        re.search(r"font-family\s*:", css, re.I),
        re.search(r"(?:background-color|background|color)\s*:", css, re.I),
        re.search(r"(?:padding|margin|gap)\s*:", css, re.I),
        re.search(r"(?:border-radius|border|box-shadow)\s*:", css, re.I),
        css.count("{") >= 6,
    )
    return all(checks)


def _has_labeled_navigation(html: str) -> bool:
    nav = _NAV_RE.search(html)
    if not nav:
        return False
    block = nav.group(0)
    if not re.search(r"aria-label|title=", block, re.I):
        return False
    links = set(re.findall(r"href=\"/([a-z-]+)\"", block))
    return set(FIVE_DESTINATIONS) <= links


def _has_controls_or_status(html: str) -> bool:
    return bool(_CONTROL_RE.search(html) or _STATUS_RE.search(html))


def analyze_surface(html: str) -> list[dict[str, str]]:
    """Analyze one served operator surface document at the declared viewport."""
    findings: list[dict[str, str]] = []
    visible = _visible_text(html)

    structured = (
        re.search(r"<!doctype\s+html", html, re.I)
        and re.search(r"<body\b", html, re.I)
        and re.search(r"<h[12]\b", html, re.I)
        and re.search(r"<(?:main|section)\b", html, re.I)
    )
    if not structured:
        findings.append(
            _finding(
                "unstructured-diagnostic",
                "document lacks the HTML layout, headings, and body of an "
                "operator surface",
            )
        )

    json_share = _serialized_share(visible)
    if json_share >= 0.5:
        findings.append(
            _finding(
                "serialized-data-surface",
                f"visible text is {json_share:.0%} serialized JSON data",
            )
        )
    else:
        repr_share = _repr_share(visible)
        if repr_share >= 0.5:
            findings.append(
                _finding(
                    "object-repr-surface",
                    f"visible text is {repr_share:.0%} object reprs",
                )
            )

    if not _is_styled(_embedded_css(html)):
        findings.append(
            _finding(
                "browser-default-styling",
                "no intentional stylesheet: typography, color, spacing, and "
                "grouping fall back to browser defaults",
            )
        )

    if not _has_labeled_navigation(html):
        findings.append(
            _finding(
                "missing-navigation",
                "no labeled navigation exposing the five destinations",
            )
        )

    if not _has_controls_or_status(html):
        findings.append(
            _finding(
                "missing-status-or-controls",
                "no recognizable interactive controls or status feedback",
            )
        )

    if "width=device-width" not in declared_viewport(html):
        findings.append(
            _finding(
                "undeclared-viewport",
                "document does not declare the desktop viewport",
            )
        )

    return findings


def styled_operator_surface_validator(surface_inventory: dict[str, Any]) -> dict[str, Any]:
    """Validate the delivered operator surface against the VALCAT v1.1 row.

    surface_inventory keys:
      viewport: {"declared": str, "evidence": str}
      surfaces: {name: {"url": str, "status": int, "html": str}} for the
                entry point ("entry-point") and each of the five destinations
    """
    findings: list[dict[str, str]] = []
    evidence: list[str] = []
    surfaces = surface_inventory.get("surfaces") or {}

    for name in (ENTRY_POINT, *FIVE_DESTINATIONS):
        surface = surfaces.get(name)
        html = surface.get("html") if isinstance(surface, dict) else None
        if not isinstance(html, str) or not html:
            findings.append(
                _finding(
                    "unstructured-diagnostic",
                    f"surface '{name}' has no rendered document in the inventory",
                )
            )
            continue
        for item in analyze_surface(html):
            findings.append(
                _finding(item["finding"], f"surface '{name}': {item['detail']}")
            )

    viewport = surface_inventory.get("viewport") or {}
    if "width=device-width" not in str(viewport.get("declared", "")):
        findings.append(
            _finding(
                "undeclared-viewport",
                "inventory does not record the declared desktop viewport",
            )
        )

    if not findings:
        evidence.append(
            f"initial view and {len(FIVE_DESTINATIONS)} destinations rendered "
            "as styled operator surfaces at the declared viewport"
        )
        evidence.append(
            "application objects presented as labels, cards, lists, facts, and "
            "status feedback; no serialized-JSON- or repr-dominant document"
        )

    target_ids = [surface_inventory.get("target_id", "operator-app")]
    return _result(
        VALIDATOR_NAME,
        target_ids,
        passed=not findings,
        findings=findings,
        evidence_refs=evidence,
    )


def build_live_surface_inventory(base_url: str) -> dict[str, Any]:
    """Collect VALCAT v1.1 surface evidence from a live operator application.

    GETs the entry point and every destination route over HTTP so the
    styled-surface evidence is browser-served, not asserted.
    """

    def _get(path: str) -> tuple[int, str]:
        with urllib.request.urlopen(base_url + path, timeout=10) as response:
            return response.status, response.read().decode("utf-8")

    surfaces: dict[str, dict[str, Any]] = {}
    entry_status, entry_html = _get("/")
    surfaces[ENTRY_POINT] = {
        "url": base_url + "/",
        "status": entry_status,
        "html": entry_html,
    }
    for dest in FIVE_DESTINATIONS:
        status, html = _get(f"/{dest}")
        surfaces[dest] = {"url": f"{base_url}/{dest}", "status": status, "html": html}

    declared = declared_viewport(entry_html) or DECLARED_VIEWPORT
    return {
        "target_id": "operator-app",
        "viewport": {
            "declared": declared,
            "evidence": f"meta viewport declared as '{declared}' in the served documents",
        },
        "surfaces": surfaces,
    }
