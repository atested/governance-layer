#!/bin/bash
# Start the Atested Governance Dashboard.
# Preferred method: ask the AI agent to open the dashboard (atested_dashboard MCP tool).
# This script is a manual fallback.
cd "$(cd "$(dirname "$0")" && pwd)" || exit 1
DASHBOARD_PORT="${DASHBOARD_PORT:-9700}" \
  GOV_RUNTIME_DIR="${GOV_RUNTIME_DIR:-$(pwd)/gov_runtime}" \
  GOV_CANONICAL_REPO_PATH="${GOV_CANONICAL_REPO_PATH:-$(pwd)}" \
  GOV_RUNTIME_PATH="${GOV_RUNTIME_PATH:-$(pwd)/gov_runtime}" \
  python3 dashboard/server.py &
sleep 1
open "http://localhost:${DASHBOARD_PORT:-9700}"
wait
