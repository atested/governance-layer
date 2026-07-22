import base64
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import licensing


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _token(private_key, *, tier: str, exp: str, license_id: str) -> str:
    claims = {
        "customer_id": "cus_paid_test",
        "exp": exp,
        "license_id": license_id,
        "org": "Example Org",
        "origin": "purchased",
        "tier": tier,
        "v": 3,
    }
    payload = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
    return f"{_b64url(payload)}.{_b64url(private_key.sign(payload))}"


class _Response:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.data).encode()


def test_renewed_license_refresh_is_authenticated_and_activated(tmp_path, monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_hex = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    monkeypatch.setattr(licensing, "_DEFAULT_VERIFY_KEY_HEX", public_hex)

    old_token = _token(private_key, tier="crew", exp="20270720", license_id="lic-renew001")
    renewed_token = _token(private_key, tier="crew", exp="20280720", license_id="lic-renew001")
    licensing.save_license(tmp_path, {
        "license_status": "licensed",
        "license_tier": "crew",
        "license_expiry": "2027-07-20T00:00:00Z",
        "license_key": old_token,
    })

    captured = {}

    def opener(request, timeout):
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data)
        return _Response({"license_key": renewed_token})

    result = licensing.refresh_paid_license(tmp_path, opener=opener)
    assert result == {
        "ok": True,
        "license_id": "lic-renew001",
        "license_tier": "crew",
        "license_expiry": "2028-07-20T00:00:00Z",
        "updated": True,
    }
    assert captured["timeout"] == 10
    assert captured["body"]["license_id"] == "lic-renew001"
    assert captured["body"]["proof"].startswith("hmac-sha256:")
    assert old_token not in json.dumps(captured["body"])
    assert licensing.load_license(tmp_path)["license_key"] == renewed_token


def test_refresh_rejects_tier_change_and_expiry_regression(tmp_path, monkeypatch):
    private_key = Ed25519PrivateKey.generate()
    public_hex = private_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    monkeypatch.setattr(licensing, "_DEFAULT_VERIFY_KEY_HEX", public_hex)
    old_token = _token(private_key, tier="crew", exp="20270720", license_id="lic-renew001")
    licensing.save_license(tmp_path, {
        "license_status": "licensed", "license_tier": "crew",
        "license_expiry": "2027-07-20T00:00:00Z", "license_key": old_token,
    })

    wrong_tier = _token(private_key, tier="team", exp="20280720", license_id="lic-renew001")
    result = licensing.refresh_paid_license(
        tmp_path, opener=lambda *_args, **_kwargs: _Response({"license_key": wrong_tier})
    )
    assert result["error"] == "LICENSE_TIER_MISMATCH"

    older = _token(private_key, tier="crew", exp="20260720", license_id="lic-renew001")
    result = licensing.refresh_paid_license(
        tmp_path, opener=lambda *_args, **_kwargs: _Response({"license_key": older})
    )
    assert result["error"] == "LICENSE_EXPIRY_REGRESSION"


def test_dashboard_has_no_false_billing_toggle():
    ui = (REPO / "dashboard/ui-next/windows/licensing.js").read_text(encoding="utf-8")
    api = (REPO / "dashboard/ui-next/api.js").read_text(encoding="utf-8")
    server = (REPO / "dashboard/server.py").read_text(encoding="utf-8")

    combined = "\n".join((ui, api, server))
    assert "postAutoRenewal" not in combined
    assert "/api/licensing/auto-renewal" not in combined
    assert "lup-renewal-toggle" not in combined
    assert "Turn Off" not in ui and "Turn On" not in ui
    assert "https://atested.com/account/" in ui
    assert "Refresh renewed license" in ui
    assert "/api/licensing/refresh" in server
