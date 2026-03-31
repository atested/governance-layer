#!/usr/bin/env python3
"""Verify reason-code assertion coverage.

Usage:
  python3 scripts/verify-rc-coverage.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "scripts" / "policy-eval.py"
TESTS_DIR = ROOT / "tests"
RC_RE = re.compile(r"RC-[A-Z0-9-]+")


def extract_from_text(text: str) -> set[str]:
    return set(RC_RE.findall(text))


def main() -> int:
    policy_text = POLICY.read_text(encoding="utf-8", errors="replace")
    policy_codes = extract_from_text(policy_text)

    asserted_codes: set[str] = set()
    for test_file in sorted(TESTS_DIR.rglob("*.sh")):
        test_text = test_file.read_text(encoding="utf-8", errors="replace")
        asserted_codes |= extract_from_text(test_text)

    missing = sorted(policy_codes - asserted_codes)
    for code in missing:
        print(code)

    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
