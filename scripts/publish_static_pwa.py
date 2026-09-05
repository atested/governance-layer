#!/usr/bin/env python3
"""Publish the reviewed static PWA to its stable Cloudflare Pages endpoint.

The default is a reviewable dry run.  Supplying --confirm is intentionally the
only mutating mode and delegates credentials to Wrangler's normal environment.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "static-pwa" / "release.json"
CATALOG = ROOT / "catalog" / "dws-apps.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", action="store_true", help="perform the Cloudflare Pages publish")
    args = parser.parse_args()

    release = load_json(RELEASE)
    catalog = load_json(CATALOG)
    print(f"stable_release_url={release['stable_release_url']}")
    print(f"latest_catalog_entries={sum(app.get('version_status') == 'latest' for app in catalog['apps'])}")
    if not args.confirm:
        print("dry_run=true")
        return 0
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        print("CLOUDFLARE_API_TOKEN is required with --confirm", file=sys.stderr)
        return 2
    wrangler = shutil.which("wrangler")
    if not wrangler:
        print("wrangler must be installed before a confirmed publish", file=sys.stderr)
        return 2
    result = subprocess.run([wrangler, "pages", "deploy", "static-pwa", "--project-name", "atested-governance-layer"], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
