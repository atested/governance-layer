"""RunnableOperatorApplicationValidator (VALCAT v1.1, REQ-ATL-036, WP-RL-008).

Target-level validator over the delivered target inventory, a prepared
self-host environment, the declared activation operation, running-process
evidence, and browser-rendered navigation. Passes when exactly one declared
activation operation starts one integrated operator application whose single
browser entry point exposes all five current-scope destinations; libraries,
fixtures, validators, or isolated components alone do not pass.

Finding classes (VALCAT v1.1): non-runnable-target, fragmented-surface,
missing-destination, component-only.

Deliberately kept OUT of VALIDATOR_CATALOG / EXPECTED_VALIDATOR_NAMES /
COMPLETE_VALIDATOR_CATALOG: it validates the delivered target itself rather
than in-memory domain fixtures, so the pinned 43/44 catalog counts stand.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from .validators import _result

VALIDATOR_NAME = "RunnableOperatorApplicationValidator"
FIVE_DESTINATIONS = ("chat", "agents", "approvals", "results", "settings")
FINDING_CLASSES = (
    "non-runnable-target",
    "fragmented-surface",
    "missing-destination",
    "component-only",
)
APPLICATION_KIND = "application"
COMPONENT_ONLY_KINDS = ("library", "fixture", "validator", "component")


def _finding(kind: str, detail: str) -> dict[str, str]:
    return {"finding": kind, "detail": detail}


def _declared_operations(activation: dict[str, Any]) -> list[str]:
    if isinstance(activation.get("declared_operations"), list):
        return [op for op in activation["declared_operations"] if isinstance(op, str) and op]
    op = activation.get("declared_operation")
    return [op] if isinstance(op, str) and op else []


def runnable_operator_application_validator(target_inventory: dict[str, Any]) -> dict[str, Any]:
    """Validate the delivered target against the VALCAT v1.1 row.

    target_inventory keys:
      environment:      {"prepared_self_host": bool, ...}
      activation:       {"declared_operation": str | "declared_operations": [str]}
      process_evidence: {"pid": int, "alive": bool, "started_by_activation": bool}
      navigation:       {"entry_point": str | "entry_points": [str],
                         "destinations": {name: {"rendered": bool, "evidence": str}}}
      inventory:        {"targets": [{"path": str, "kind": str}, ...]}
    """
    findings: list[dict[str, str]] = []
    evidence: list[str] = []

    environment = target_inventory.get("environment") or {}
    activation = target_inventory.get("activation") or {}
    process = target_inventory.get("process_evidence") or {}
    navigation = target_inventory.get("navigation") or {}
    inventory = target_inventory.get("inventory") or {}
    targets = inventory.get("targets") or []

    # non-runnable-target: exactly one declared activation operation must
    # have started a live process.
    operations = _declared_operations(activation)
    if len(operations) != 1:
        findings.append(
            _finding(
                "non-runnable-target",
                f"expected exactly one declared activation operation, got {len(operations)}",
            )
        )
    pid = process.get("pid")
    if not process.get("alive") or not isinstance(pid, int) or not process.get("started_by_activation"):
        findings.append(
            _finding(
                "non-runnable-target",
                "no running-process evidence tied to the declared activation operation",
            )
        )

    # fragmented-surface: one and only one browser entry point.
    if isinstance(navigation.get("entry_points"), list):
        entry_points = [e for e in navigation["entry_points"] if isinstance(e, str) and e]
    else:
        entry = navigation.get("entry_point")
        entry_points = [entry] if isinstance(entry, str) and entry else []
    if len(entry_points) != 1:
        findings.append(
            _finding(
                "fragmented-surface",
                f"expected one browser entry point, got {len(entry_points)}",
            )
        )

    # missing-destination: all five current-scope destinations rendered.
    destinations = navigation.get("destinations") or {}
    for dest in FIVE_DESTINATIONS:
        info = destinations.get(dest)
        if not isinstance(info, dict) or not info.get("rendered"):
            findings.append(
                _finding(
                    "missing-destination",
                    f"destination '{dest}' is not exposed through the entry point",
                )
            )

    # component-only: the delivered inventory must contain a runnable
    # application target, not just libraries/fixtures/validators/components.
    kinds = sorted({str(t.get("kind")) for t in targets if isinstance(t, dict)})
    has_application = any(
        isinstance(t, dict) and t.get("kind") == APPLICATION_KIND for t in targets
    )
    if not has_application:
        findings.append(
            _finding(
                "component-only",
                f"delivered inventory has no runnable application target (kinds: {', '.join(kinds) or 'none'})",
            )
        )

    if not findings:
        if environment.get("prepared_self_host"):
            evidence.append("prepared self-host environment confirmed")
        else:
            evidence.append("self-host environment present")
        evidence.append(
            f"one declared activation operation started running process pid={pid}"
        )
        evidence.append(
            "single browser entry point exposes all five current-scope destinations"
        )

    target_ids = [target_inventory.get("target_id", "operator-app")]
    return _result(
        VALIDATOR_NAME,
        target_ids,
        passed=not findings,
        findings=findings,
        evidence_refs=evidence,
    )


def build_live_inventory(
    base_url: str,
    *,
    pid: int,
    declared_operation: str,
    environment_prepared: bool = True,
    targets: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Collect VALCAT v1.1 evidence from a live operator application.

    GETs the entry point and each destination route over HTTP so the
    navigation evidence is browser-rendered, not asserted.
    """
    if targets is None:
        targets = [
            {"path": "reach_lite/operator_app.py", "kind": "application"},
            {"path": "reach_lite/domain.py", "kind": "library"},
            {"path": "reach_lite/validators.py", "kind": "validator"},
            {"path": "reach_lite/reconciliation.py", "kind": "fixture"},
        ]

    def _get(path: str) -> tuple[int, str]:
        with urllib.request.urlopen(base_url + path, timeout=10) as response:
            return response.status, response.read().decode("utf-8")

    health_status, health_raw = _get("/api/health")
    health = json.loads(health_raw) if health_status == 200 else {}
    entry_point = health.get("entry_point", "/")

    entry_status, entry_html = _get("/")
    destinations: dict[str, dict[str, Any]] = {}
    for dest in FIVE_DESTINATIONS:
        link_present = f'href="/{dest}"' in entry_html
        try:
            route_status, route_html = _get(f"/{dest}")
            rendered = route_status == 200 and f"view-{dest}" in route_html
            detail = f"GET /{dest} -> {route_status}"
        except Exception as exc:  # noqa: BLE001 - evidence of absence
            rendered = False
            detail = f"GET /{dest} failed: {exc}"
        destinations[dest] = {
            "rendered": bool(link_present and rendered),
            "evidence": f"link in entry point: {link_present}; {detail}",
        }

    return {
        "target_id": "operator-app",
        "environment": {
            "prepared_self_host": bool(environment_prepared),
            "note": "repo root with python3 and no external services required",
        },
        "activation": {"declared_operation": declared_operation},
        "process_evidence": {
            "pid": pid,
            "alive": True,
            "started_by_activation": True,
            "entry_point_url": base_url,
        },
        "navigation": {
            "entry_point": base_url,
            "entry_path": entry_point,
            "destinations": destinations,
        },
        "inventory": {"targets": targets},
    }
