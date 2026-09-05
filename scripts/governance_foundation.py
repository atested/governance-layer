"""Governed-session and maturity-tier foundation for Atested.

The deployment maturity model is intentionally separate from commercial
license SKUs.  Governance records, session state, and operator views use the
four identities defined here and nowhere else.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


MATURITY_TIERS = ("personal", "crew", "team", "institution")
MATURITY_TIER_LABELS = {
    "personal": "Personal",
    "crew": "Crew",
    "team": "Team",
    "institution": "Institution",
}
SESSION_ROUTE = "http_governance_proxy"
SESSION_HEADER = "x-atested-session-id"


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_maturity_tier(value: Any) -> str:
    tier = str(value or "").strip().lower()
    if tier not in MATURITY_TIERS:
        raise ValueError(
            f"unknown governance maturity tier {value!r}; "
            f"expected one of {', '.join(MATURITY_TIERS)}"
        )
    return tier


def maturity_tier_from_policy(policy: Mapping[str, Any]) -> str:
    """Return the active policy's required deployment maturity identity."""
    # Legacy/local policy fixtures predate the deployment identity field.
    # They remain Personal by default; an explicitly supplied unknown value
    # is rejected instead of silently becoming a fifth tier.
    return normalize_maturity_tier(policy.get("maturity_tier", "personal"))


def maturity_tier_catalog() -> list[dict[str, Any]]:
    return [
        {
            "id": tier,
            "label": MATURITY_TIER_LABELS[tier],
            "order": index + 1,
        }
        for index, tier in enumerate(MATURITY_TIERS)
    ]


class GovernedSessionStore:
    """Small durable state machine for governed-session readiness.

    A configured scope is necessary but insufficient.  Readiness becomes true
    only after a request carrying the session identity reaches the configured
    HTTP governance proxy.  Observations claiming any alternate route are
    retained as rejected attempts and can never make a session ready.
    """

    def __init__(self, runtime_root: Path):
        self.path = Path(runtime_root) / "governed-sessions.json"
        self._lock = threading.RLock()

    def _load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        sessions = data.get("sessions") if isinstance(data, dict) else None
        return {
            "schema_version": 1,
            "sessions": sessions if isinstance(sessions, dict) else {},
        }

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        os.replace(temporary, self.path)

    @staticmethod
    def _public_state(session: Mapping[str, Any]) -> dict[str, Any]:
        state = deepcopy(dict(session))
        state["scope_configured"] = bool(state.get("scope"))
        state["proxy_route_observed"] = bool(state.get("proxy_route_observed"))
        state["governed_ready"] = bool(
            state["scope_configured"] and state["proxy_route_observed"]
        )
        state["required_route"] = SESSION_ROUTE
        state["maturity_tiers"] = maturity_tier_catalog()
        return state

    def configure(
        self,
        scope: Mapping[str, Any] | str,
        *,
        proxy_url: str,
        maturity_tier: str,
    ) -> dict[str, Any]:
        if isinstance(scope, str):
            normalized_scope: dict[str, Any] = {"working_directory": scope.strip()}
        elif isinstance(scope, Mapping):
            normalized_scope = {
                str(key): value
                for key, value in scope.items()
                if str(key).strip() and value not in (None, "", [], {})
            }
        else:
            normalized_scope = {}
        if not normalized_scope or not any(str(value).strip() for value in normalized_scope.values()):
            raise ValueError("intended working scope is required")

        configured_proxy = str(proxy_url or "").strip().rstrip("/")
        if not configured_proxy.startswith(("http://", "https://")):
            raise ValueError("configured HTTP governance proxy URL is required")

        tier = normalize_maturity_tier(maturity_tier)
        session_id = str(uuid.uuid4())
        now = _now_utc_z()
        session = {
            "session_id": session_id,
            "scope": normalized_scope,
            "proxy_url": configured_proxy,
            "maturity_tier": tier,
            "proxy_route_observed": False,
            "created_at": now,
            "updated_at": now,
            "rejected_route_attempts": [],
        }
        with self._lock:
            data = self._load()
            data["sessions"][session_id] = session
            self._write(data)
        return self._public_state(session)

    def observe_route(
        self,
        session_id: str,
        *,
        route: str,
        provider: str = "",
        path: str = "",
    ) -> dict[str, Any] | None:
        identity = str(session_id or "").strip()
        if not identity:
            return None
        with self._lock:
            data = self._load()
            session = data["sessions"].get(identity)
            if not isinstance(session, dict):
                return None
            now = _now_utc_z()
            if route == SESSION_ROUTE:
                session["proxy_route_observed"] = True
                session["last_proxy_observation"] = {
                    "route": SESSION_ROUTE,
                    "provider": str(provider or ""),
                    "path": str(path or ""),
                    "observed_at": now,
                }
            else:
                attempts = session.setdefault("rejected_route_attempts", [])
                attempts.append({
                    "route": str(route or "unknown"),
                    "observed_at": now,
                })
                session["proxy_route_observed"] = False
            session["updated_at"] = now
            self._write(data)
            return self._public_state(session)

    def status(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            session = self._load()["sessions"].get(str(session_id or "").strip())
            return self._public_state(session) if isinstance(session, dict) else None

    def latest(self) -> dict[str, Any] | None:
        with self._lock:
            sessions = list(self._load()["sessions"].values())
        if not sessions:
            return None
        latest = max(sessions, key=lambda item: str(item.get("updated_at", "")))
        return self._public_state(latest)
