#!/usr/bin/env python3
"""
Minimal integrated E2E harness wrapper for attestation-related checks.

Usage:
    integrated_e2e.py render-time-ribbon <records.json>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import time_ribbon  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "render-time-ribbon":
        print(
            "Usage: integrated_e2e.py render-time-ribbon <records.json>",
            file=sys.stderr,
        )
        raise SystemExit(2)

    records = time_ribbon.load_records(Path(sys.argv[2]))
    print(time_ribbon.render(records))


if __name__ == "__main__":
    main()
