#!/usr/bin/env python3
"""VALCAT-atested-reach-lite-f8de0e@1.0 -- complete validator catalog runner.

Runs every validator in the complete catalog (the 43 source validators plus
ValidatorCatalogCompletenessValidator) against conforming reconciliation
fixtures and exits zero only when every result reports passed: true.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reach_lite.reconciliation import run_reconciliation
from reach_lite.validators import EXPECTED_VALIDATOR_NAMES


def main() -> int:
    report = run_reconciliation()
    for name, result in report["results"].items():
        status = "passed: true" if result["passed"] else "passed: false"
        print("VALIDATOR " + name + " => " + status)
    print("expected_validator_count=" + str(len(EXPECTED_VALIDATOR_NAMES)))
    print("catalog_size=" + str(report["catalog_size"]))
    print("complete_catalog_size=" + str(report["complete_catalog_size"]))
    if report["passed_all"]:
        print("VALCAT-atested-reach-lite-f8de0e@1.0: ALL PASSED")
        return 0
    print("FAILURES=" + json.dumps(report["failures"], sort_keys=True))
    return 1


if __name__ == "__main__":
    sys.exit(main())
