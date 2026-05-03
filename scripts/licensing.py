"""Licensing posture for the governance layer.

This module manages license state: trial detection, expiry, activation,
and posture fields that are added to every governance record.

Licensing is *evidentiary, not enforcement*.  The governance layer operates
identically regardless of license status — ALLOW/DENY decisions are not
affected.  Licensing fields record the truth about the operator's status.

License key scheme (v2/v3):
    License tokens are Ed25519-signed JSON payloads.  The signing private key
    is held by the license issuer (website/Stripe backend) and is NOT shipped
    with the client code.  The client embeds only the public key for
    verification.

    Token format: base64url(JSON-payload) + "." + base64url(Ed25519-signature)
    v2 payload: {"tier": "team", "exp": "20271231", "org": "acme", "v": 2}
    v3 payload: {"customer_id": "cus_...", "exp": "20271231", "license_id": "lic-...",
                 "org": "acme", "origin": "purchased", "tier": "crew", "v": 3}

    The public verification key is embedded in this module.  To generate
    license tokens, use the issuer tool (not shipped in this repo) with the
    corresponding private key stored at the issuer's infrastructure.

    For development/testing, set GOV_LICENSE_SIGNING_KEY_PATH to a PEM file
    containing the Ed25519 private key to enable local key generation via
    generate_license_token().
"""
import base64
import hashlib
import json
import os
import stat
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LICENSE_FILENAME = "license.json"
TRIAL_DAYS = 30

VALID_STATUSES = ("trial", "licensed", "unlicensed", "personal", "clock_anomaly")
VALID_TIERS = ("personal", "personal_plus", "crew", "team", "institution",
                "business", "enterprise")  # last two are legacy v2 names

# ---------------------------------------------------------------------------
# Ed25519 license token scheme (v2)
# ---------------------------------------------------------------------------

# Embedded public key for license verification.
# The corresponding private key is held by the license issuer and is NOT
# in this repository.  To rotate: generate a new Ed25519 keypair, update
# this constant, and deploy new tokens from the issuer.
#
# Generate keypair (issuer-side, NOT in this repo):
#   from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
#   from cryptography.hazmat.primitives import serialization
#   priv = Ed25519PrivateKey.generate()
#   pub_bytes = priv.public_key().public_bytes(
#       serialization.Encoding.Raw, serialization.PublicFormat.Raw)
#   print(pub_bytes.hex())
#
# Set GOV_LICENSE_VERIFY_KEY_HEX to override for testing.
_PRODUCTION_VERIFY_KEY_HEX = (
    "ec1ebd3ac6ff62e352f327820b56bddec423d594a9ddfce5117106536bf16bae"
)
_env_override = os.environ.get("GOV_LICENSE_VERIFY_KEY_HEX")
if _env_override is not None:
    if not os.environ.get("GOV_LICENSE_OVERRIDE_ACKNOWLEDGED"):
        import sys as _sys
        print(
            "WARNING: GOV_LICENSE_VERIFY_KEY_HEX is overridden via environment. "
            "License verification uses a non-production public key. "
            "Set GOV_LICENSE_OVERRIDE_ACKNOWLEDGED=1 to suppress this warning.",
            file=_sys.stderr,
        )
    _DEFAULT_VERIFY_KEY_HEX = _env_override
else:
    _DEFAULT_VERIFY_KEY_HEX = _PRODUCTION_VERIFY_KEY_HEX


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    padded = s + "=" * (4 - len(s) % 4)
    return base64.urlsafe_b64decode(padded)


def _load_verify_public_key():
    """Load the Ed25519 public key for license verification."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        raw = bytes.fromhex(_DEFAULT_VERIFY_KEY_HEX)
        return Ed25519PublicKey.from_public_bytes(raw)
    except Exception:
        return None


def _load_issuer_private_key():
    """Load the Ed25519 private key for license generation (issuer-side only)."""
    key_path = os.environ.get("GOV_LICENSE_SIGNING_KEY_PATH", "")
    if not key_path:
        return None
    try:
        from cryptography.hazmat.primitives import serialization
        raw = Path(key_path).read_bytes()
        return serialization.load_pem_private_key(raw, password=None)
    except Exception:
        return None


def generate_license_token(
    tier: str, expiry_date: str, org: str = "",
    version: int = 2,
    license_id: str = "", customer_id: str = "", origin: str = "",
) -> str:
    """Generate a signed license token (issuer-side only).

    Requires GOV_LICENSE_SIGNING_KEY_PATH to point to the Ed25519 private key.
    This function is NOT available in production client deployments.

    version=2: legacy format {tier, exp, org, v}
    version=3: adds {license_id, customer_id, origin}
    """
    if tier not in VALID_TIERS:
        raise ValueError(f"invalid tier: {tier}")
    priv = _load_issuer_private_key()
    if priv is None:
        raise RuntimeError(
            "GOV_LICENSE_SIGNING_KEY_PATH not set or key unreadable. "
            "License generation requires the issuer private key."
        )
    claims: Dict[str, Any] = {"tier": tier, "exp": expiry_date, "org": org, "v": version}
    if version >= 3:
        claims["license_id"] = license_id
        claims["customer_id"] = customer_id
        claims["origin"] = origin
    payload = json.dumps(
        claims, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    sig = priv.sign(payload)
    return _b64url_encode(payload) + "." + _b64url_encode(sig)


def validate_license_token(token: str) -> Optional[Dict[str, str]]:
    """Validate a signed license token and return decoded fields, or None.

    Accepts Ed25519-signed v2 and v3 tokens.  Legacy v1 GOV-* keys are
    rejected (C1: forgeable deterministic scheme removed).

    v2 payload: {"tier", "exp", "org", "v": 2}
    v3 payload: {"tier", "exp", "org", "v": 3, "license_id", "customer_id", "origin"}
    """
    parts = token.strip().split(".")
    if len(parts) != 2:
        return None
    try:
        payload_bytes = _b64url_decode(parts[0])
        sig_bytes = _b64url_decode(parts[1])
    except Exception:
        return None

    pub = _load_verify_public_key()
    if pub is None:
        return None
    try:
        pub.verify(sig_bytes, payload_bytes)
    except Exception:
        return None

    try:
        claims = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None

    tier = claims.get("tier", "")
    if tier not in VALID_TIERS:
        return None
    expiry = claims.get("exp", "")
    if len(expiry) != 8 or not expiry.isdigit():
        return None
    try:
        exp_date = datetime.strptime(expiry, "%Y%m%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    version = claims.get("v", 2)
    result = {
        "tier": tier,
        "expiry_date": expiry,
        "expiry_iso": exp_date.strftime("%Y-%m-%dT00:00:00Z"),
        "organization": claims.get("org", ""),
        "version": version,
    }

    # v3 additional fields
    if version >= 3:
        result["license_id"] = claims.get("license_id", "")
        result["customer_id"] = claims.get("customer_id", "")
        result["origin"] = claims.get("origin", "")

    return result


def validate_license_key(key: str) -> Optional[Dict[str, str]]:
    """Validate a license key.  Accepts Ed25519-signed v2 and v3 tokens."""
    return validate_license_token(key)


# ---------------------------------------------------------------------------
# License file I/O (C2: atomic write, permissions, fail-closed on corruption)
# ---------------------------------------------------------------------------

def _license_path(runtime_dir: Path) -> Path:
    return runtime_dir / LICENSE_FILENAME


def load_license(runtime_dir: Path) -> Dict[str, Any]:
    """Load license configuration.

    Returns the parsed dict, empty dict if file does not exist, or raises
    ValueError if the file exists but is corrupted/malformed (C2: fail closed).
    """
    path = _license_path(runtime_dir)
    if not path.exists():
        return {}
    try:
        data = path.read_text(encoding="utf-8")
        config = json.loads(data)
        if not isinstance(config, dict):
            raise ValueError(f"license.json is not a JSON object: {path}")
        return config
    except json.JSONDecodeError as e:
        raise ValueError(f"license.json is corrupted (invalid JSON): {path}: {e}") from e
    except OSError as e:
        raise ValueError(f"license.json unreadable: {path}: {e}") from e


def save_license(runtime_dir: Path, config: Dict[str, Any]) -> None:
    """Persist license configuration with atomic write and restrictive permissions."""
    path = _license_path(runtime_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(config, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    # Atomic write: write to temp file then rename (C2)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.fchmod(fd, stat.S_IRUSR | stat.S_IWUSR)  # 0600 (H8)
        os.close(fd)
        os.rename(tmp_path, str(path))
    except Exception:
        os.close(fd) if not os.get_inheritable(fd) else None
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


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
        "trial_started_chain_marker": "",  # H5: set by caller with chain record count
        "license_key": "",
    }
    save_license(runtime_dir, config)
    return config


# ---------------------------------------------------------------------------
# Posture resolution (C3: enforce expiry for licensed; H5: clock rollback)
# ---------------------------------------------------------------------------

def _chain_last_timestamp(runtime_dir: Path) -> Optional[datetime]:
    """Read the timestamp of the most recent chain record as a rollback anchor."""
    chain_path = runtime_dir / "LOGS" / "decision-chain.jsonl"
    if not chain_path.exists():
        return None
    try:
        last_line = ""
        with open(chain_path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if not last_line:
            return None
        import json as _json
        rec = _json.loads(last_line)
        ts = rec.get("timestamp_utc", "")
        if not ts:
            return None
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def resolve_posture(runtime_dir: Path, unique_user_count: int = 0,
                    chain_record_count: int = 0) -> Dict[str, str]:
    """Resolve the current licensing posture.

    Returns a dict with exactly four fields suitable for embedding in
    governance records:
        license_status, license_tier, organization_id, license_expiry

    Side-effect: creates a trial license.json on first call if none exists.
    """
    try:
        config = load_license(runtime_dir)
    except ValueError:
        # C2: corrupted license.json → fail closed to unlicensed, do NOT
        # silently reset to trial.
        return {
            "license_status": "unlicensed",
            "license_tier": "personal",
            "organization_id": "",
            "license_expiry": "",
        }

    if not config:
        config = initialize_trial(runtime_dir)

    now = datetime.now(timezone.utc)
    status = config.get("license_status", "trial")
    tier = config.get("license_tier", "personal")
    org_id = config.get("organization_id", "")
    expiry_str = config.get("license_expiry", "")

    # H5 (D-019): Clock rollback detection using chain timestamp as anchor.
    # If system time is before the last chain record timestamp, fail closed.
    last_chain_ts = _chain_last_timestamp(runtime_dir)
    if last_chain_ts is not None and now < last_chain_ts - timedelta(minutes=5):
        return {
            "license_status": "clock_anomaly",
            "license_tier": tier,
            "organization_id": org_id,
            "license_expiry": expiry_str,
        }

    # Parse expiry once
    expiry_dt = None
    if expiry_str:
        try:
            expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    # Check trial expiry
    if status == "trial" and expiry_dt is not None:
        if now >= expiry_dt:
            if unique_user_count <= 1 and not config.get("license_key"):
                status = "personal"
            else:
                status = "unlicensed"
            config["license_status"] = status
            save_license(runtime_dir, config)

    # C3: Check licensed expiry — expired licensed → unlicensed
    if status == "licensed" and expiry_dt is not None:
        if now >= expiry_dt:
            status = "unlicensed"
            config["license_status"] = status
            save_license(runtime_dir, config)

    return {
        "license_status": status,
        "license_tier": tier,
        "organization_id": org_id,
        "license_expiry": expiry_str,
    }


def activate_license(
    runtime_dir: Path, license_key: str, organization_id: str = ""
) -> Dict[str, Any]:
    """Activate a license key (Ed25519-signed v2 or v3 token).  Returns result dict."""
    decoded = validate_license_key(license_key)
    if decoded is None:
        return {"ok": False, "error": "INVALID_LICENSE_KEY"}

    try:
        config = load_license(runtime_dir)
    except ValueError:
        config = {}
    if not config:
        config = initialize_trial(runtime_dir)

    org = organization_id or decoded.get("organization", "")
    config["license_status"] = "licensed"
    config["license_tier"] = decoded["tier"]
    config["license_expiry"] = decoded["expiry_iso"]
    config["license_key"] = license_key.strip()
    if org:
        config["organization_id"] = org

    save_license(runtime_dir, config)
    return {
        "ok": True,
        "license_status": "licensed",
        "license_tier": decoded["tier"],
        "license_expiry": decoded["expiry_iso"],
        "organization_id": config.get("organization_id", ""),
    }


def trial_days_remaining(runtime_dir: Path) -> Optional[int]:
    """Return days remaining in trial, or None if not in trial.

    H5 (D-021): Returns None when clock anomaly is detected so the caller
    never sees a positive remaining count with an anomalous status.
    """
    try:
        config = load_license(runtime_dir)
    except ValueError:
        return None
    if config.get("license_status") != "trial":
        return None
    # H5: Check for clock rollback before reporting remaining days.
    now = datetime.now(timezone.utc)
    last_chain_ts = _chain_last_timestamp(runtime_dir)
    if last_chain_ts is not None and now < last_chain_ts - timedelta(minutes=5):
        return None
    expiry_str = config.get("license_expiry", "")
    if not expiry_str:
        return None
    try:
        expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        remaining = (expiry - now).days
        return max(remaining, 0)
    except (ValueError, TypeError):
        return None
