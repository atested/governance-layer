# MCP Governance Broker — Archived

Archived: 2026-05-03 (D-203)

## Reason

The MCP broker creates an agent-discoverable path around the API proxy
chokepoint. Agents that discover MCP tools may use them instead of routing
through the proxy, producing ungoverned behavior that appears governed.

The proxy architecture (proxy/server.py) is the single governance enforcement
point. The MCP broker undermines that by exposing a parallel tool surface
that bypasses proxy-level classification and policy evaluation.

## Contents

All MCP server modules, capabilities, and supporting infrastructure are
preserved here for potential future use if the architectural concern is
resolved (e.g., by making the MCP server route through the proxy internally).

## Original Entry Points

- `server.py` — stdio MCP server (governance-broker)
- `remote_server.py` — Streamable HTTP MCP server with auth
- `remote_deploy.py` — deployment helper
- `v2_proxy.py` — MCP proxy with tool mediation
