#!/usr/bin/env python3
"""VALCAT-atested-reach-lite-f8de0e@1.1 -- complete companion catalog runner.

Runs every validator in the complete catalog (the 43 source validators plus
ValidatorCatalogCompletenessValidator) against conforming reconciliation
fixtures, verifies that every target resolves and that no prohibited scope
is present, and exits zero only when every check passes.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reach_lite.valcat_1_1 import accept_companion_catalog_1_1
from reach_lite.validators import EXPECTED_VALIDATOR_NAMES


def main() -> int:
    verdict = accept_companion_catalog_1_1()
    for name, result in verdict["results"].items():
        status = "passed: true" if result["passed"] else "passed: false"
        print("VALIDATOR " + name + " => " + status)
    print("expected_validator_count=" + str(len(EXPECTED_VALIDATOR_NAMES)))
    print("catalog_size=" + str(verdict["catalog_size"]))
    print("complete_catalog_size=" + str(verdict["complete_catalog_size"]))
    print(
        "targets_resolved=" + str(verdict["targets_resolved"])
        + "/" + str(verdict["complete_catalog_size"])
    )
    print(
        "prohibited_scope_findings="
        + str(len(verdict["prohibited_scope_findings"]))
    )
    if verdict["passed"]:
        print("VALCAT-atested-reach-lite-f8de0e@1.1: ALL PASSED")
        return 0
    print(
        "FAILURES="
        + json.dumps(
            {
                "success_path_failures": verdict["success_path_failures"],
                "unresolved_targets": verdict["unresolved_targets"],
                "prohibited_scope_findings": verdict["prohibited_scope_findings"],
            },
            sort_keys=True,
        )
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
