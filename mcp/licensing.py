"""Licensing posture for the governance layer.

This module manages license state: trial detection, expiry, activation,
and posture fields that are added to every governance record.

Licensing is *evidentiary, not enforcement*.  The governance layer operates
identically regardless of license status — ALLOW/DENY decisions are not
affected.  Licensing fields record the truth about the operator's status.
"""
import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LICENSE_FILENAME = "license.json"
TRIAL_DAYS = 30

VALID_STATUSES = ("trial", "licensed", "unlicensed", "personal")
VALID_TIERS = ("personal", "team", "business", "enterprise")

# License key format: GOV-<tier>-<expiry-YYYYMMDD>-<check8>
# Example: GOV-team-20270101-a1b2c3d4
_KEY_PREFIX = "GOV"
_KEY_SALT = "governance-layer-license-v1"


# ---------------------------------------------------------------------------
# License key scheme
# ---------------------------------------------------------------------------

def _compute_check(tier: str, expiry: str) -> str:
    payload = f"{_KEY_SALT}:{tier}:{expiry}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def generate_license_key(tier: str, expiry_date: str) -> str:
    """Generate a license key for the given tier and expiry (YYYYMMDD)."""
    if tier not in VALID_TIERS:
        raise ValueError(f"invalid tier: {tier}")
    check = _compute_check(tier, expiry_date)
    return f"{_KEY_PREFIX}-{tier}-{expiry_date}-{check}"


def validate_license_key(key: str) -> Optional[Dict[str, str]]:
    """Validate a license key and return its decoded fields, or None."""
    parts = key.strip().split("-")
    if len(parts) != 4 or parts[0] != _KEY_PREFIX:
        return None
    _, tier, expiry, check = parts
    if tier not in VALID_TIERS:
        return None
    if len(expiry) != 8 or not expiry.isdigit():
        return None
    expected = _compute_check(tier, expiry)
    if check != expected:
        return None
    # Parse expiry date
    try:
        exp_date = datetime.strptime(expiry, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return {
        "tier": tier,
        "expiry_date": expiry,
        "expiry_iso": exp_date.strftime("%Y-%m-%dT00:00:00Z"),
    }


# ---------------------------------------------------------------------------
# License file I/O
# ---------------------------------------------------------------------------

def _license_path(runtime_dir: Path) -> Path:
    return runtime_dir / LICENSE_FILENAME


def load_license(runtime_dir: Path) -> Dict[str, Any]:
    """Load license configuration, returning the raw dict or empty."""
    path = _license_path(runtime_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_license(runtime_dir: Path, config: Dict[str, Any]) -> None:
    """Persist license configuration."""
    path = _license_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def initialize_trial(runtime_dir: Path) -> Dict[str, Any]:
    """Create a trial license on first operation.  Returns the new config."""
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=TRIAL_DAYS)
    config = {
        "license_status": "trial",
        "license_tier": "personal",
        "organization_id": "",
        "license_expiry": expiry.strftime("%Y-%m-%dT00:00:00Z"),
        "trial_started": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "license_key": "",
    }
    save_license(runtime_dir, config)
    return config


# ---------------------------------------------------------------------------
# Posture resolution
# ---------------------------------------------------------------------------

def resolve_posture(runtime_dir: Path, unique_user_count: int = 0) -> Dict[str, str]:
    """Resolve the current licensing posture.

    Returns a dict with exactly four fields suitable for embedding in
    governance records:
        license_status, license_tier, organization_id, license_expiry

    Side-effect: creates a trial license.json on first call if none exists.
    """
    config = load_license(runtime_dir)
    if not config:
        config = initialize_trial(runtime_dir)

    now = datetime.now(timezone.utc)
    status = config.get("license_status", "trial")
    tier = config.get("license_tier", "personal")
    org_id = config.get("organization_id", "")
    expiry_str = config.get("license_expiry", "")

    # Check for personal single-user (free tier)
    if status == "trial" and unique_user_count <= 1:
        # Single user during trial — could transition to personal
        pass

    # Check trial expiry
    if status == "trial" and expiry_str:
        try:
            expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
            if now >= expiry_dt:
                # Trial expired — check if single personal user
                if unique_user_count <= 1 and not config.get("license_key"):
                    status = "personal"
                else:
                    status = "unlicensed"
                # Update persisted state
                config["license_status"] = status
                save_license(runtime_dir, config)
        except (ValueError, TypeError):
            pass

    return {
        "license_status": status,
        "license_tier": tier,
        "organization_id": org_id,
        "license_expiry": expiry_str,
    }


def activate_license(
    runtime_dir: Path, license_key: str, organization_id: str = ""
) -> Dict[str, Any]:
    """Activate a license key.  Returns result dict."""
    decoded = validate_license_key(license_key)
    if decoded is None:
        return {"ok": False, "error": "INVALID_LICENSE_KEY"}

    config = load_license(runtime_dir)
    if not config:
        config = initialize_trial(runtime_dir)

    config["license_status"] = "licensed"
    config["license_tier"] = decoded["tier"]
    config["license_expiry"] = decoded["expiry_iso"]
    config["license_key"] = license_key.strip()
    if organization_id:
        config["organization_id"] = organization_id

    save_license(runtime_dir, config)
    return {
        "ok": True,
        "license_status": "licensed",
        "license_tier": decoded["tier"],
        "license_expiry": decoded["expiry_iso"],
        "organization_id": config.get("organization_id", ""),
    }


def trial_days_remaining(runtime_dir: Path) -> Optional[int]:
    """Return days remaining in trial, or None if not in trial."""
    config = load_license(runtime_dir)
    if config.get("license_status") != "trial":
        return None
    expiry_str = config.get("license_expiry", "")
    if not expiry_str:
        return None
    try:
        expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        remaining = (expiry - now).days
        return max(remaining, 0)
    except (ValueError, TypeError):
        return None
