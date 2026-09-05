#!/usr/bin/env python3
"""Run and report the immutable WP-003 validation manifest scenarios."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ELEMENT_VALIDATORS = {
    "REQ-ATESTED-005": "Tier3OpaqueApprovalGateValidator",
    "REQ-ATESTED-006": "ExplicitHumanApprovalOnlyValidator",
    "REQ-ATESTED-007": "ApprovalScopeLifetimeValidator",
    "REQ-ATESTED-008": "ApprovalRevocationValidator",
    "REQ-ATESTED-009": "NoDeveloperDenyBypassValidator",
}


def main() -> int:
    requested: list[str] = []
    for argument in sys.argv[1:]:
        if argument.startswith("--elements="):
            requested = [item.strip() for item in argument.split("=", 1)[1].split(",") if item.strip()]
    if not requested:
        print("--elements is required", file=sys.stderr)
        return 2
    unknown = [item for item in requested if item not in ELEMENT_VALIDATORS]
    if unknown:
        print(f"unsupported WP-003 elements: {','.join(unknown)}", file=sys.stderr)
        return 2

    repo = Path(__file__).resolve().parents[1]
    test_file = repo / "tests" / "wp_003_validator.py"
    project_python = repo / ".venv" / "bin" / "python"
    test_python = str(project_python) if project_python.exists() else sys.executable
    completed = subprocess.run(
        [test_python, str(test_file)],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    print(completed.stdout, end="")
    if completed.returncode != 0:
        return completed.returncode

    for element in requested:
        print(json.dumps({
            "validator": ELEMENT_VALIDATORS[element],
            "element_id": element,
            "result": "pass",
            "evidence_refs": ["tests/wp_003_validator.py"],
            "observations": ["All required observable scenarios completed without mismatch."],
        }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
