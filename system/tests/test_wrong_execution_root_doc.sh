#!/bin/bash
set -euo pipefail

doc="docs/design/wrong-execution-root-operator-note.md"
rg '^# Wrong Execution Root Operator Note$' "$doc" >/dev/null
rg '^## WRONG_EXECUTION_ROOT handling$' "$doc" >/dev/null
rg '^## Canonical STOP PACKET shape$' "$doc" >/dev/null
rg '^- Step failed: WRONG_EXECUTION_ROOT$' "$doc" >/dev/null
rg '^## Deterministic example$' "$doc" >/dev/null

echo "TEST_WRONG_EXECUTION_ROOT_DOC:PASS"
