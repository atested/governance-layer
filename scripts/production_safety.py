#!/usr/bin/env python3
"""Production readiness, admission, and safe-refusal boundary for Atested.

Liveness is deliberately process-level.  Readiness is governance-level and
therefore fails closed whenever a load-bearing guarantee is unavailable.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional


PRODUCTION = "production"
LOCAL_DEVELOPMENT = "local-development"
RUNTIME_CONTEXTS = frozenset({PRODUCTION, LOCAL_DEVELOPMENT})
DEPENDENCIES = ("policy", "signing", "decision_record", "approval")
FAILURE_CLASSES = frozenset({"integrity", "signing", "authorization", "capacity"})


class StartupSafetyError(RuntimeError):
    """Startup would expose an ambiguous or unsafe governance boundary."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _positive_capacity(value: Any) -> int:
    try:
        capacity = int(value)
    except (TypeError, ValueError) as exc:
        raise StartupSafetyError("ATESTED_GOVERNANCE_CAPACITY must be a positive integer") from exc
    if capacity < 1:
        raise StartupSafetyError("ATESTED_GOVERNANCE_CAPACITY must be a positive integer")
    return capacity


@dataclass(frozen=True)
class RuntimeSafetyConfig:
    context: str
    capacity: int = 32

    @classmethod
    def from_environment(cls, environment: Optional[Mapping[str, str]] = None) -> "RuntimeSafetyConfig":
        source = os.environ if environment is None else environment
        context = str(source.get("ATESTED_RUNTIME_CONTEXT", "")).strip().lower()
        if context not in RUNTIME_CONTEXTS:
            raise StartupSafetyError(
                "ATESTED_RUNTIME_CONTEXT must be explicitly set to production or local-development"
            )
        return cls(
            context=context,
            capacity=_positive_capacity(source.get("ATESTED_GOVERNANCE_CAPACITY", "32")),
        )


def validate_startup(
    config: RuntimeSafetyConfig,
    *,
    signing_usable: bool,
    effective_uid: Optional[int] = None,
) -> None:
    """Reject unsafe deployment identity and signing combinations."""
    if config.context not in RUNTIME_CONTEXTS:
        raise StartupSafetyError("runtime context is ambiguous or unsupported")
    if config.context == PRODUCTION and not signing_usable:
        raise StartupSafetyError("production requires a usable decision-record signing key")
    if config.context == PRODUCTION and effective_uid == 0:
        raise StartupSafetyError("production governance components must not run as root")


class AdmissionLease:
    """Exactly-once release token returned for accepted governance work."""

    def __init__(self, boundary: "ProductionSafetyBoundary"):
        self._boundary = boundary
        self._released = False

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._boundary._release_admission()

    def __enter__(self) -> "AdmissionLease":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.release()


class ProductionSafetyBoundary:
    """Thread-safe readiness and bounded-admission state for a service."""

    def __init__(
        self,
        config: RuntimeSafetyConfig,
        *,
        signing_usable: bool,
        effective_uid: Optional[int] = None,
    ):
        validate_startup(
            config,
            signing_usable=signing_usable,
            effective_uid=effective_uid,
        )
        self.config = config
        self._lock = threading.RLock()
        self._dependencies: dict[str, dict[str, Any]] = {
            dependency: {"available": True, "detail": "available", "observed_at": _utc_now()}
            for dependency in DEPENDENCIES
        }
        self._dependencies["signing"] = {
            "available": bool(signing_usable),
            "detail": "usable" if signing_usable else "disabled for explicit local development",
            "observed_at": _utc_now(),
        }
        self._in_flight = 0
        self._accepted = 0
        self._refused = 0
        self._last_failure: Optional[dict[str, Any]] = None

    def set_dependency(self, dependency: str, available: bool, detail: str = "") -> None:
        if dependency not in DEPENDENCIES:
            raise ValueError(f"unknown load-bearing dependency: {dependency}")
        with self._lock:
            self._dependencies[dependency] = {
                "available": bool(available),
                "detail": str(detail or ("available" if available else "unavailable")),
                "observed_at": _utc_now(),
            }
            if not available:
                failure_class = "signing" if dependency == "signing" else (
                    "authorization" if dependency == "approval" else "integrity"
                )
                self._record_failure(failure_class, dependency, self._dependencies[dependency]["detail"])

    def blocking_condition(self) -> Optional[dict[str, str]]:
        with self._lock:
            for dependency in DEPENDENCIES:
                state = self._dependencies[dependency]
                # Unsigned operation is intentionally valid only in the
                # already-validated explicit local-development context.
                if dependency == "signing" and self.config.context == LOCAL_DEVELOPMENT:
                    continue
                if not state["available"]:
                    return {
                        "failure_class": "signing" if dependency == "signing" else (
                            "authorization" if dependency == "approval" else "integrity"
                        ),
                        "dependency": dependency,
                        "detail": str(state["detail"]),
                    }
        return None

    def try_admit(self) -> Optional[AdmissionLease]:
        """Accept immediately within capacity or explicitly refuse excess work."""
        with self._lock:
            condition = self.blocking_condition()
            if condition is not None:
                self._refused += 1
                self._record_failure(
                    condition["failure_class"], condition["dependency"], condition["detail"]
                )
                return None
            if self._in_flight >= self.config.capacity:
                self._refused += 1
                self._record_failure(
                    "capacity", "admission", f"declared capacity {self.config.capacity} is saturated"
                )
                return None
            self._in_flight += 1
            self._accepted += 1
            return AdmissionLease(self)

    def _release_admission(self) -> None:
        with self._lock:
            if self._in_flight < 1:
                raise RuntimeError("admission accounting underflow")
            self._in_flight -= 1

    def _record_failure(self, failure_class: str, source: str, detail: str) -> None:
        if failure_class not in FAILURE_CLASSES:
            raise ValueError(f"unknown unsafe-condition class: {failure_class}")
        self._last_failure = {
            "failure_class": failure_class,
            "source": source,
            "detail": detail,
            "observed_at": _utc_now(),
            "action": "affected_operation_refused",
        }

    def refuse(self, failure_class: str, source: str, detail: str) -> dict[str, Any]:
        """Produce an operator-visible refusal that cannot resemble success."""
        with self._lock:
            self._refused += 1
            self._record_failure(failure_class, source, detail)
            failure = dict(self._last_failure or {})
        return self._refusal_payload(failure_class, failure)

    def current_refusal(self) -> dict[str, Any]:
        """Describe the refusal already recorded by a failed admission."""
        with self._lock:
            failure = dict(self._last_failure or {
                "failure_class": "capacity",
                "source": "admission",
                "detail": "governance work was not admitted",
                "observed_at": _utc_now(),
                "action": "affected_operation_refused",
            })
        return self._refusal_payload(str(failure["failure_class"]), failure)

    @staticmethod
    def _refusal_payload(failure_class: str, failure: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "released": False,
            "governed_success": False,
            "policy_decision": "DENY",
            "reason_code": f"GOVERNANCE_{failure_class.upper()}_UNAVAILABLE",
            "degraded_condition": dict(failure),
        }

    def health(self) -> dict[str, Any]:
        """Return honest, separate liveness and governance readiness."""
        with self._lock:
            condition = self.blocking_condition()
            dependencies = {key: dict(value) for key, value in self._dependencies.items()}
            capacity = {
                "limit": self.config.capacity,
                "in_flight": self._in_flight,
                "available": max(0, self.config.capacity - self._in_flight),
                "accepted_total": self._accepted,
                "refused_total": self._refused,
            }
            conditions = []
            if condition is not None:
                conditions.append(condition)
            if self._last_failure is not None:
                conditions.append(dict(self._last_failure))
            return {
                "live": True,
                "ready": condition is None,
                "runtime_context": self.config.context,
                "dependencies": dependencies,
                "capacity": capacity,
                "degraded_conditions": conditions,
            }
