#!/usr/bin/env python3
"""Verify the website tier registry copy matches the governance source."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CANONICAL = REPO_ROOT / "dashboard" / "ui-next" / "tier-feature-registry.json"
DEFAULT_WEBSITE = REPO_ROOT.parent / "atested.com" / "tier-feature-registry.json"
CANONICAL_TIERS = ["personal", "personal_plus", "crew", "team", "institution"]


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _canonical_bytes(data: Any) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--website", type=Path, default=DEFAULT_WEBSITE)
    args = parser.parse_args()

    canonical = _load_json(args.canonical)
    website = _load_json(args.website)

    errors: list[str] = []
    if canonical != website:
        errors.append("website registry JSON differs from canonical governance registry")

    tiers = canonical.get("tierOrder")
    if tiers != CANONICAL_TIERS:
        errors.append(f"canonical tierOrder is {tiers!r}, expected {CANONICAL_TIERS!r}")

    tier_keys = sorted(canonical.get("tiers", {}).keys())
    if tier_keys != sorted(CANONICAL_TIERS):
        errors.append(f"canonical tiers are {tier_keys!r}, expected {sorted(CANONICAL_TIERS)!r}")

    disallowed = {"business", "enterprise"}
    found = disallowed.intersection(canonical.get("tiers", {}).keys())
    if found:
        errors.append(f"disallowed tier keys present: {sorted(found)!r}")

    canonical_hash = _sha256(_canonical_bytes(canonical))
    website_hash = _sha256(_canonical_bytes(website))

    print(f"canonical={args.canonical}")
    print(f"website={args.website}")
    print(f"canonical_sha256={canonical_hash}")
    print(f"website_sha256={website_hash}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("tier registry sync verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
