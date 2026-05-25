#!/usr/bin/env bash
# run-governed-agent.sh — launch an agent with its provider traffic forced
# through the local Atested governance proxy.
#
# QS-054: a process-level ANTHROPIC_BASE_URL pointing straight at
# api.anthropic.com silently bypassed the proxy, so Cecil's Anthropic tool
# calls produced zero governed decision records while OpenAI/Gemini stayed
# routed. Shell profiles set the correct routes, but an inherited override
# wins over them. This wrapper *forces* every provider base URL at the proxy
# (overriding whatever was inherited) and refuses to launch if the proxy is
# not actually accepting connections — so the agent never runs ungoverned and
# never runs pointed at a dead endpoint.
#
# Usage:
#   scripts/run-governed-agent.sh <command> [args...]
#   scripts/run-governed-agent.sh claude
#
# Honored environment:
#   GOV_PROXY_HOST   proxy host (default: localhost)
#   GOV_PROXY_PORT   proxy port (default: 8080, matches process_supervisor)
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $(basename "$0") <command> [args...]" >&2
  echo "  launches <command> with ANTHROPIC/OPENAI/GEMINI_BASE_URL forced through the governance proxy" >&2
  exit 2
fi

PROXY_HOST="${GOV_PROXY_HOST:-localhost}"
PROXY_PORT="${GOV_PROXY_PORT:-8080}"
PROXY_BASE="http://${PROXY_HOST}:${PROXY_PORT}"

# Refuse to launch if the proxy is not accepting connections. Routing an agent
# at a dead proxy would break it; routing it past the proxy would make it
# ungoverned. Fail closed (mirrors the proxy's own INV-005 posture).
if ! python3 - "$PROXY_HOST" "$PROXY_PORT" <<'PY'
import socket, sys
host, port = sys.argv[1], int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=2):
        pass
except OSError:
    sys.exit(1)
PY
then
  echo "error: governance proxy is not reachable at ${PROXY_BASE}." >&2
  echo "       Start it first (e.g. 'atested start') so traffic can be governed." >&2
  exit 1
fi

# Force every provider through the proxy, overriding any inherited override.
export ANTHROPIC_BASE_URL="${PROXY_BASE}/anthropic"
export OPENAI_BASE_URL="${PROXY_BASE}/openai"
export GEMINI_BASE_URL="${PROXY_BASE}/gemini"

echo "governed routing active → ${PROXY_BASE} (anthropic, openai, gemini)" >&2
exec "$@"
