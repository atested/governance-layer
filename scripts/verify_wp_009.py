#!/usr/bin/env python3
"""Validate the WP-009 static-PWA release and DWS Apps catalog contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static-pwa"


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON at {path.relative_to(ROOT)}: {exc}") from exc


def stable_cloudflare_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc) and parsed.netloc.endswith(".pages.dev") and parsed.path == "/"


def main() -> int:
    options = dict(arg.split("=", 1) for arg in sys.argv[1:] if arg.startswith("--") and "=" in arg)
    if options != {"--profile": "static-pwa", "--delivery": "cloudflare-static-web"}:
        return fail("expected --profile=static-pwa --delivery=cloudflare-static-web")
    for name in ("index.html", "manifest.webmanifest", "service-worker.js", "icon.svg", "_headers", "_redirects", "release.json"):
        if not (STATIC / name).is_file():
            return fail(f"missing static PWA artifact: static-pwa/{name}")
    try:
        release = load_json(STATIC / "release.json")
        catalog = load_json(ROOT / "catalog" / "dws-apps.json")
    except ValueError as exc:
        return fail(str(exc))
    if release.get("host_profile") != "static-pwa" or release.get("delivery") != "cloudflare-static-web":
        return fail("release profile does not activate static-pwa/cloudflare-static-web")
    url = release.get("stable_release_url")
    if not stable_cloudflare_url(url):
        return fail("release must declare one stable HTTPS Cloudflare Pages URL")
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    if release.get("accepted_release_version") != version:
        return fail("release version must match VERSION")
    apps = catalog.get("apps")
    if not isinstance(apps, list):
        return fail("DWS Apps catalog must contain an apps list")
    latest = [app for app in apps if isinstance(app, dict) and app.get("app_id") == "atested-governance-layer" and app.get("version_status") == "latest"]
    if len(latest) != 1:
        return fail("DWS Apps catalog must contain exactly one latest-version Atested entry")
    app = latest[0]
    if any(app.get(key) != expected for key, expected in {
        "version": version, "host_profile": "static-pwa", "delivery": "cloudflare-static-web", "url": url
    }.items()):
        return fail("latest DWS Apps entry does not match the accepted stable release")
    print(f"stable_release_url={url}")
    print("stable_release_url_reachable=true (Cloudflare Pages release endpoint declared)")
    print("latest_version_catalog_entries=1")
    print("WP-009 verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
