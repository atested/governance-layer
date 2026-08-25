"""WP-RL-009 — Durable launch instructions + one authoritative activation profile.

Implements the three validators that govern the handoff of the Reach Lite
operator application:

* ```REQ-ATL-037 DurableLaunchInstructionsValidator
    Durable launch instructions that state prerequisites, the configuration
    procedure, the activation operation, the expected browser URL, the
    readiness signal, the shutdown/cleanup operation, and the observable
    failure behavior.  A reviewer can follow them without undocumented
    knowledge; every command and reference resolves within the delivery, and
    any placeholder or stale value is reported rather than silently launched.

* ```REQ-ATL-038 ConfiguredActivationProfileValidator
    One configured activation profile, conforming to SCH-ATL-009, selected as
    the authoritative launch profile.  It carries no unresolved placeholders,
    is runnable (activation + cleanup), declares its resolved working context
    and prerequisites, declares the browser URL and the readiness check, and
    is the profile actually used by launch verification.

* ```SCH-ATL-009 ActivationProfileSchemaValidator
    The activation profile schema: stable profile id, a non-placeholder
    activation operation, a resolved working context, declared prerequisite and
    configuration inputs (secrets referenced by name, never embedded), a
    readiness condition with an explicit timeout, an absolute HTTP/HTTPS
    browser URL or a deterministic runtime URL resolution, a cleanup operation,
    and an operator-surface marker.

These are target-level validators (like WP-RL-008's
RunnableOperatorApplicationValidator) and are deliberately NOT registered in
```reach_lite.validators.VALIDATOR_CATALOG / EXPECTED_VALIDATOR_NAMES /
COMPLETE_VALIDATOR_CATALOG.  They operate on the delivered artifacts on disk,
not on in-memory fixture inventories, so the pinned 43/44 catalog counts are
untouched.
"""
from __future__ import annotations

import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional

from .validators import _result

# ---------------------------------------------------------------------------
# Validator identities
# ---------------------------------------------------------------------------
SCHEMA_VALIDATOR = "ActivationProfileSchemaValidator"
LAUNCH_INSTRUCTIONS_VALIDATOR = "DurableLaunchInstructionsValidator"
CONFIGURED_PROFILE_VALIDATOR = "ConfiguredActivationProfileValidator"

# ---------------------------------------------------------------------------
# Finding classes per validator (VALCAT v1.1 style).
# ---------------------------------------------------------------------------
SCHEMA_FINDING_CLASSES = (
    "missing-field",
    "placeholder-value",
    "embedded-secret",
    "non-resolved-url",
    "missing-timeout",
    "non-resolved-context",
)
LAUNCH_INSTRUCTIONS_FINDING_CLASSES = (
    "missing-section",
    "unresolved-reference",
    "placeholder-instructions",
)
CONFIGURED_PROFILE_FINDING_CLASSES = (
    "no-authoritative-profile",
    "profile-not-conformant",
    "profile-not-used-by-verification",
)


def _finding(kind: str, detail: str) -> Dict[str, str]:
    return {"kind": kind, "detail": detail}


# ---------------------------------------------------------------------------
# Placeholder detection
# ---------------------------------------------------------------------------
_PLACEHOLDER_TOKENS = (
    "todo",
    "tbd",
    "placeholder",
    "change_me",
    "changeme",
    "xxx",
    "???",
    "fill in",
    "fixme",
    "determine",
    "<port>",
)
_ANGLE_BRACKET_RE = re.compile(r"<[^<>s]{1,40}>")
_BRACE_TOKEN_RE = re.compile(r"{{|}}")


def _is_placeholder(value: Any) -> bool:
    """Return True when *value* is a placeholder / stale / unresolved value."""
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v:
        return True
    low = v.lower()
    if any(tok in low for tok in _PLACEHOLDER_TOKENS):
        return True
    if _ANGLE_BRACKET_RE.search(v):
        return True
    if _BRACE_TOKEN_RE.search(v):
        return True
    return False


# ---------------------------------------------------------------------------
# URL / working-context helpers
# ---------------------------------------------------------------------------
def _is_absolute_http_url(url: str) -> bool:
    try:
        p = urllib.parse.urlparse(url)
    except (ValueError, TypeError):
        return False
    return p.scheme in ("http", "https") and bool(p.netloc) and bool(p.hostname)


def _browser_url_ok(browser_url: Any) -> bool:
    """Accept an absolute HTTP/HTTPS URL string, or a deterministic runtime
    URL resolution object (scheme/host/port/path)."""
    if isinstance(browser_url, str):
        return _is_absolute_http_url(browser_url)
    if isinstance(browser_url, dict) and browser_url.get("mode") == "runtime":
        scheme = browser_url.get("scheme")
        host = browser_url.get("host")
        port = browser_url.get("port")
        path = browser_url.get("path")
        return (
            scheme in ("http", "https")
            and isinstance(host, str)
            and not _is_placeholder(host)
            and isinstance(port, int)
            and not isinstance(port, bool)
            and port > 0
            and isinstance(path, str)
        )
    return False


def _working_context_ok(working_context: Any, delivery_root: Optional[str]) -> bool:
    """A resolved working context: a non-placeholder cwd that, when a delivery
    root is known, resolves to an existing directory within the delivery."""
    if isinstance(working_context, str):
        cwd = working_context
    elif isinstance(working_context, dict):
        cwd = working_context.get("cwd")
    else:
        return False
    if not isinstance(cwd, str) or _is_placeholder(cwd):
        return False
    if delivery_root is not None:
        candidate = cwd if os.path.isabs(cwd) else os.path.join(str(delivery_root), cwd)
        if not os.path.isdir(candidate):
            return False
    return True


# ---------------------------------------------------------------------------
# SCH-ATL-009 ActivationProfileSchemaValidator
# ---------------------------------------------------------------------------
def activation_profile_schema_validator(
    profile: Any, delivery_root: Optional[str] = None
) -> Dict[str, Any]:
    """Validate that a single activation profile conforms to SCH-ATL-009."""
    if not isinstance(profile, dict):
        return _result(
            SCHEMA_VALIDATOR,
            ["<invalid>"],
            False,
            [_finding("missing-field", "activation profile is not an object")],
            ["profile rejected: not an object"],
        )

    findings: List[Dict[str, str]] = []
    evidence: List[str] = []

    pid = profile.get("profile_id")
    target = pid if isinstance(pid, str) and pid.strip() else "<no-profile-id>"

    # (1) Stable profile id; (2) non-placeholder activation operation;
    # (7) cleanup operation; (8) operator-surface marker.
    for key in ("profile_id", "activation_operation", "cleanup_operation", "operator_surface_marker"):
        val = profile.get(key)
        if val is None:
            findings.append(_finding("missing-field", f"{key} is missing"))
        elif _is_placeholder(val):
            findings.append(_finding("placeholder-value", f"{key} is a placeholder value"))

    # (3) Resolved working context.
    wc = profile.get("working_context")
    if wc is None:
        findings.append(_finding("missing-field", "working_context is missing"))
    elif not _working_context_ok(wc, delivery_root):
        findings.append(_finding("non-resolved-context", "working_context is not resolved within the delivery"))

    # (4) Declared prerequisite / configuration inputs; secrets by name only.
    config_inputs = profile.get("configuration_inputs")
    if config_inputs is None:
        findings.append(_finding("missing-field", "configuration_inputs is missing"))
    elif not isinstance(config_inputs, list):
        findings.append(_finding("missing-field", "configuration_inputs must be a list"))
    else:
        for i, entry in enumerate(config_inputs):
            if not isinstance(entry, dict):
                findings.append(_finding("missing-field", f"configuration_inputs[{i}] must be an object"))
                continue
            name = entry.get("name")
            if not isinstance(name, str) or _is_placeholder(name):
                findings.append(_finding("placeholder-value", f"configuration_inputs[{i}] name is missing or a placeholder"))
            is_secret = bool(entry.get("secret"))
            has_value = "value" in entry and entry.get("value") not in (None, "")
            if is_secret and has_value:
                findings.append(_finding("embedded-secret", f"configuration_inputs[{i}] ({name}) embeds a secret value instead of a reference"))
            elif is_secret and not has_value and not (isinstance(entry.get("ref"), str) and entry.get("ref")):
                findings.append(_finding("missing-field", f"configuration_inputs[{i}] ({name}) is a secret but declares no reference"))

    # (5) Readiness condition with an explicit timeout.
    readiness = profile.get("readiness")
    if not isinstance(readiness, dict):
        findings.append(_finding("missing-field", "readiness is missing or not an object"))
    else:
        timeout = readiness.get("timeout_seconds")
        if not (isinstance(timeout, (int, float)) and not isinstance(timeout, bool) and timeout > 0):
            findings.append(_finding("missing-timeout", "readiness.timeout_seconds is not a positive number"))
        condition = readiness.get("condition")
        if not isinstance(condition, str) or _is_placeholder(condition):
            findings.append(_finding("placeholder-value", "readiness.condition is missing or a placeholder"))

    # (6) Absolute HTTP/HTTPS browser URL or deterministic runtime resolution.
    browser_url = profile.get("browser_url")
    if browser_url is None:
        findings.append(_finding("missing-field", "browser_url is missing"))
    elif not _browser_url_ok(browser_url):
        findings.append(_finding("non-resolved-url", "browser_url is not an absolute HTTP/HTTPS URL and not a deterministic runtime resolution"))

    passed = not findings
    evidence.append(f"profile {target}: {'conformant' if passed else 'non-conformant'} to SCH-ATL-009")
    return _result(SCHEMA_VALIDATOR, [target], passed, findings, evidence)


# ---------------------------------------------------------------------------
# REQ-ATL-037 DurableLaunchInstructionsValidator
# ---------------------------------------------------------------------------
# Each required section is matched by keyword against the instruction headings.
REQUIRED_SECTION_KEYWORDS = (
    ("prerequisites", ("prerequisite",)),
    ("configuration", ("configuration", "config")),
    ("activation", ("activation", "launch", "start")),
    ("browser-url", ("url", "browser")),
    ("readiness", ("readiness", "ready")),
    ("cleanup", ("cleanup", "shutdown")),
    ("failure-behavior", ("failure", "error")),
)

_PATH_REF_RE = re.compile(r"[\w./-]+\.(?:py|json|md|sh|toml|txt|yaml|yml)\b")
_VALUE_LINE_RE = re.compile(
    r"(http[s]?://|\b--port\b|python3 -m|\bGET /api/|\b127\.0\.0\.1\b|localhost)",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)


def _headings(markdown: str) -> List[str]:
    return [m.group(1).strip().lower() for m in _HEADING_RE.finditer(markdown)]


def _extract_path_refs(markdown: str) -> List[str]:
    seen = set()
    out: List[str] = []
    for ref in _PATH_REF_RE.findall(markdown):
        if ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def _has_placeholder_value(markdown: str) -> bool:
    for line in markdown.splitlines():
        if _VALUE_LINE_RE.search(line) and _is_placeholder(line):
            return True
    return False


def durable_launch_instructions_validator(
    instructions: Any, delivery_root: Optional[str] = None
) -> Dict[str, Any]:
    """Validate the durable launch instructions (REQ-ATL-037)."""
    if not isinstance(instructions, str) or not instructions.strip():
        return _result(
            LAUNCH_INSTRUCTIONS_VALIDATOR,
            ["launch-instructions"],
            False,
            [_finding("missing-section", "launch instructions are empty or missing")],
            ["instructions empty or missing"],
        )

    findings: List[Dict[str, str]] = []
    evidence: List[str] = []

    headings = _headings(instructions)
    for label, keywords in REQUIRED_SECTION_KEYWORDS:
        if not any(any(k in h for k in keywords) for h in headings):
            findings.append(_finding("missing-section", f"required section is missing: {label}"))

    if delivery_root is not None:
        for ref in _extract_path_refs(instructions):
            if _is_placeholder(ref):
                continue
            cand = ref if os.path.isabs(ref) else os.path.join(str(delivery_root), ref)
            if not os.path.exists(cand):
                findings.append(_finding("unresolved-reference", f"referenced path does not resolve within the delivery: {ref}"))

    if _has_placeholder_value(instructions):
        findings.append(_finding("placeholder-instructions", "an activation, URL, or readiness value is a placeholder or stale value"))

    passed = not findings
    evidence.append("launch-instructions: " + ("complete and resolved" if passed else "incomplete or unresolved"))
    return _result(LAUNCH_INSTRUCTIONS_VALIDATOR, ["launch-instructions"], passed, findings, evidence)


# ---------------------------------------------------------------------------
# REQ-ATL-038 ConfiguredActivationProfileValidator
# ---------------------------------------------------------------------------
def configured_activation_profile_validator(
    profiles: Any,
    verification_inventory: Optional[Dict[str, Any]] = None,
    delivery_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate that exactly one authoritative, conformant profile is present
    and that it is the profile used by launch verification (REQ-ATL-038)."""
    findings: List[Dict[str, str]] = []
    evidence: List[str] = []

    if not isinstance(profiles, list):
        profiles = [profiles] if isinstance(profiles, dict) else []
    if not profiles:
        findings.append(_finding("no-authoritative-profile", "no activation profile was provided"))
        return _result(CONFIGURED_PROFILE_VALIDATOR, ["<none>"], False, findings, ["no profile provided"])

    authoritative = [p for p in profiles if isinstance(p, dict) and p.get("authoritative") is True]
    if len(authoritative) != 1:
        findings.append(_finding("no-authoritative-profile", f"expected exactly one authoritative profile, found {len(authoritative)}"))
        target = "<ambiguous>"
    else:
        ap = authoritative[0]
        pid = ap.get("profile_id")
        target = pid if isinstance(pid, str) and pid.strip() else "<no-id>"

        schema = activation_profile_schema_validator(ap, delivery_root)
        if not schema["passed"]:
            detail = "; ".join(f["detail"] for f in schema["findings"])
            findings.append(_finding("profile-not-conformant", f"authoritative profile does not conform to SCH-ATL-009: {detail}"))

        if verification_inventory is None:
            findings.append(_finding("profile-not-used-by-verification", "no verification inventory: the authoritative profile was not used by launch verification"))
        else:
            used = verification_inventory.get("used_profile_id")
            alive = bool(verification_inventory.get("alive"))
            if used != target:
                findings.append(_finding("profile-not-used-by-verification", f"verification used profile {used!r} but the authoritative profile is {target!r}"))
            elif not alive:
                findings.append(_finding("profile-not-used-by-verification", "verification inventory reports no live process started by the authoritative profile"))

    passed = not findings
    evidence.append(
        f"activation-profile {target}: "
        + ("one authoritative SCH-ATL-009 profile, used by launch verification" if passed else "authoritative selection invalid")
    )
    return _result(CONFIGURED_PROFILE_VALIDATOR, [target], passed, findings, evidence)


# ---------------------------------------------------------------------------
# Artifacts + helpers
# ---------------------------------------------------------------------------
PROFILE_FILENAME = "reach_lite/activation_profile.json"
INSTRUCTIONS_FILENAME = "docs/operations/reach-lite-launch.md"


def load_profile(path: str) -> Dict[str, Any]:
    import json

    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_instructions(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def build_verification_inventory(profile: Any, base_url: str, pid: Optional[int], alive: bool) -> Dict[str, Any]:
    """Inventory describing the profile actually used to launch/verify."""
    used = profile.get("profile_id") if isinstance(profile, dict) else None
    return {
        "used_profile_id": used if isinstance(used, str) else None,
        "base_url": base_url,
        "pid": pid,
        "alive": bool(alive),
    }
