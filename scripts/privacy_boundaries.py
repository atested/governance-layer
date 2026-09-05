"""Fail-closed privacy and consent boundaries for optional product features.

The telemetry exporter deliberately has a much narrower contract than the
locally stored dashboard summary.  Only fixed, non-identifying dimensions and
non-negative integer counts may leave an installation.  Likewise, an
AI-assisted feature is an explicit interactive action, never a background or
delegated operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, TypeVar


class PrivacyBoundaryError(ValueError):
    """A request tried to cross a privacy or consent boundary unsafely."""


TELEMETRY_EXPORT_DIMENSIONS = frozenset({
    "ui_window_opens",
    "ui_report_runs",
    "ui_range_shortcuts",
    "ui_actions",
    "trouble_reports",
    "governance_total_operations",
    "governance_allow",
    "governance_deny",
})


def _count(value: Any) -> int:
    """Return a non-negative count, refusing booleans and non-count values."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PrivacyBoundaryError("telemetry values must be non-negative integer counts")
    return value


def validate_aggregate_only_telemetry(payload: Mapping[str, Any]) -> dict[str, int]:
    """Validate the complete wire payload before telemetry export.

    This rejects every field outside the fixed aggregate schema, including
    free-text content and identifying metadata.  The returned copy prevents a
    caller from changing a validated mapping before it is sent.
    """
    if not isinstance(payload, Mapping):
        raise PrivacyBoundaryError("telemetry payload must be an object")
    unknown = set(payload) - TELEMETRY_EXPORT_DIMENSIONS
    if unknown:
        raise PrivacyBoundaryError(
            "telemetry contains excluded or non-aggregate dimensions: "
            + ", ".join(sorted(str(item) for item in unknown))
        )
    return {dimension: _count(payload.get(dimension, 0)) for dimension in TELEMETRY_EXPORT_DIMENSIONS}


def _nested_total(value: Any) -> int:
    if isinstance(value, Mapping):
        return sum(_nested_total(item) for item in value.values())
    return _count(value)


def aggregate_telemetry_export(summary: Mapping[str, Any], categories: Mapping[str, Any]) -> dict[str, int]:
    """Reduce local telemetry data to the only values eligible for export."""
    if not isinstance(summary, Mapping) or not isinstance(categories, Mapping):
        raise PrivacyBoundaryError("telemetry summary and categories must be objects")
    lifetime = summary.get("lifetime", {})
    if not isinstance(lifetime, Mapping):
        raise PrivacyBoundaryError("telemetry lifetime summary must be an object")
    governance = categories.get("governance_usage_data", {})
    trouble = categories.get("trouble_submissions", {})
    if not isinstance(governance, Mapping) or not isinstance(trouble, Mapping):
        raise PrivacyBoundaryError("telemetry categories must be aggregate objects")
    return validate_aggregate_only_telemetry({
        "ui_window_opens": _nested_total(lifetime.get("window_opens", {})),
        "ui_report_runs": _nested_total(lifetime.get("report_runs", {})),
        "ui_range_shortcuts": _nested_total(lifetime.get("range_shortcuts", {})),
        "ui_actions": _nested_total(lifetime.get("ui_actions", {})),
        "trouble_reports": _nested_total(trouble.get("submitted", 0)),
        "governance_total_operations": _nested_total(governance.get("total_operations", 0)),
        "governance_allow": _nested_total(governance.get("allow", 0)),
        "governance_deny": _nested_total(governance.get("deny", 0)),
    })


def aggregate_local_telemetry_summary(summary: Mapping[str, Any]) -> dict[str, int]:
    """Make a safe relay payload when only a local summary is available."""
    lifetime = summary.get("lifetime", {}) if isinstance(summary, Mapping) else {}
    if not isinstance(lifetime, Mapping):
        raise PrivacyBoundaryError("telemetry lifetime summary must be an object")
    return aggregate_telemetry_export(summary, {
        "governance_usage_data": {},
        "trouble_submissions": {"submitted": _nested_total(lifetime.get("trouble_reports", {}))},
    })


@dataclass(frozen=True)
class AuthenticatedAiSession:
    """The authenticated user's currently active session identity."""

    session_id: str
    user_id: str
    authenticated: bool = True


@dataclass(frozen=True)
class AiFeatureRequest:
    """An attempted invocation of an AI-assisted product feature."""

    session_id: str
    user_id: str
    origin: str
    delegated: bool = False


_T = TypeVar("_T")


class OptInAuthenticatedAiFeatureGate:
    """Permit AI work only for an opted-in user's current interactive session."""

    def authorize(
        self,
        *,
        opted_in: bool,
        current_session: AuthenticatedAiSession | None,
        request: AiFeatureRequest,
    ) -> None:
        if not opted_in:
            raise PrivacyBoundaryError("AI-assisted features require explicit operator opt-in")
        if current_session is None or not current_session.authenticated:
            raise PrivacyBoundaryError("AI-assisted features require an authenticated current session")
        if not current_session.session_id or not current_session.user_id:
            raise PrivacyBoundaryError("authenticated current session identity is required")
        if request.delegated or request.origin != "interactive":
            raise PrivacyBoundaryError("automatic and delegated AI requests are refused")
        if request.session_id != current_session.session_id:
            raise PrivacyBoundaryError("AI request does not belong to the current session")
        if request.user_id != current_session.user_id:
            raise PrivacyBoundaryError("AI request user does not match the authenticated session")

    def invoke(
        self,
        *,
        opted_in: bool,
        current_session: AuthenticatedAiSession | None,
        request: AiFeatureRequest,
        feature: Callable[[], _T],
    ) -> _T:
        """Authorize before calling the feature, so refused cases make no AI call."""
        self.authorize(opted_in=opted_in, current_session=current_session, request=request)
        return feature()
