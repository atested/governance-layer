#!/usr/bin/env bash
set -euo pipefail

# Minimal bootstrap helper: ensures the runtime directory structure exists.
# Usage: bootstrap.sh [RUNTIME_DIR]
#
# If RUNTIME_DIR is not provided, uses $GOV_RUNTIME_DIR or defaults to
# gov_runtime/ relative to the repo root.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME="${1:-${GOV_RUNTIME_DIR:-$ROOT/gov_runtime}}"

# Restrict file creation permissions
umask 0077
mkdir -p "$RUNTIME/LOGS" "$RUNTIME/tmp" "$RUNTIME/TOOL_EVENTS"

echo "Bootstrap complete."
echo "  Runtime directory: $RUNTIME"
echo
echo "Next steps:"
echo "  1) Configure capabilities/capability-registry.json for your environment"
echo "  2) Set up your MCP client — see docs/QUICKSTART.md"
echo "  3) Run the test suite: GOV_PROFILE=dev bash system/scripts/release-gate.sh"
