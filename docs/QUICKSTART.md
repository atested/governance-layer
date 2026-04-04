# Quickstart

Get from clone to governed operations in under 5 minutes.

---

## Prerequisites

- **Python 3.10+**
- **Git**
- An AI agent that allows configuring its API endpoint (e.g., any coding assistant, CLI agent, or IDE integration)

Check your Python version:

```bash
python3 --version
# Must be 3.10 or higher
```

If your system Python is older, install a newer version via your package manager (e.g., `brew install python@3.12`). The rest of this guide uses `python3` — substitute the versioned binary if needed.

---

## 1. Clone and install

```bash
git clone <repo-url> governance-layer
cd governance-layer

# Create the Python virtualenv and install dependencies
python3 -m venv mcp/.venv
mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt
```

The virtualenv lives at `mcp/.venv/` and is gitignored.

---

## 2. Initialize the runtime directory

The governance layer writes decision chains, logs, and scratch files to a runtime directory. The default is `gov_runtime/` at the repo root (gitignored).

```bash
mkdir -p gov_runtime/LOGS gov_runtime/tmp
```

If you want a different location, set `GOV_RUNTIME_DIR` to that path.

---

## 3. Start the API governance proxy

```bash
ANTHROPIC_API_KEY=sk-... python3 -m proxy.server
```

The proxy starts on `http://127.0.0.1:8080` and forwards to the Anthropic API.

Options:

```bash
# Custom port
python3 -m proxy.server --port 9000

# Custom upstream provider
python3 -m proxy.server --upstream https://api.openai.com

# Friendly identity label (default: system hostname)
python3 -m proxy.server --user-identity "dev-machine-1"
```

---

## 4. Point your agent at the proxy

Set one environment variable before launching your AI agent:

```bash
export ANTHROPIC_BASE_URL=http://localhost:8080/anthropic
```

Your agent now talks to Atested instead of the model provider directly. Every tool call is governed — classified, policy-evaluated, and recorded — before the agent executes it.

---

## 5. Verify it works

Start your agent and perform any action (read a file, run a command, etc.). Check the proxy logs — you should see mediation decisions:

```
Tool ALLOWED (idx=0): Read → ALLOW
Tool DENIED (idx=1): Bash → DENY
```

The governance chain is written to `gov_runtime/LOGS/decision-chain.jsonl`.

---

## 6. Run the test suite

Confirm everything is wired up:

```bash
# Quick smoke test
GOV_RUNTIME_DIR=gov_runtime bash tests/run-mcp-smoke.sh

# Full release gate
GOV_PROFILE=dev bash system/scripts/release-gate.sh
```

---

## Configuring policy

Policy rules live in `capabilities/policy-rules.json`. Rules are declarative and evaluated in order — first match wins.

The default policy:
- **Allows** file reads, writes, lists, moves, deletes within the repo and runtime directories
- **Allows** well-known commands (git, make, pytest) at local/repository scope
- **Allows** agent internal operations (planning, task management, search)
- **Denies** operations targeting sensitive paths (.ssh, .aws, credentials)
- **Denies** network operations without explicit approval
- **Denies** opaque execution (Tier 3) without operator approval
- **Denies** uninspectable operations (Tier 4) by default

To adjust, edit the rules file and restart the proxy.

---

## Dashboard

Start the live governance dashboard:

```bash
python3 dashboard/server.py
```

The dashboard shows chain health, mediated decisions, operation approvals, audit queries, and reports.

---

## MCP server (complementary)

The MCP server remains available for governance operations that have no native agent equivalent — status queries, audit, capabilities management, approvals, and certification:

```bash
# Local (stdio transport)
mcp/.venv/bin/python3 mcp/server.py

# Remote (HTTP transport with bearer auth)
mcp/.venv/bin/python3 mcp/remote_server.py
```

The API proxy governs the agent. The MCP server provides governance tools. Different layers, both useful.

---

## User Identity

The proxy identifies users by system hostname by default. To set a friendly label:

```bash
# Via command line
python3 -m proxy.server --user-identity "alice"

# Via environment variable
ATESTED_USER_LABEL="alice" python3 -m proxy.server
```

The identity appears in the dashboard Users section and in every chain record.

---

## Runtime directory structure

```
$GOV_RUNTIME_DIR/
├── LOGS/
│   ├── decision-chain.jsonl   # append-only tamper-evident chain
│   └── quarantine/            # broken chains preserved on integrity failure
└── tmp/                       # scratch space
```

---

## Troubleshooting

### DENY is correct behavior

A `DENY` response means the governance layer evaluated the request and rejected it on policy grounds. Check the proxy logs for the matched rule and reason.

### Proxy won't start

1. Check Python version: `python3 --version` (must be 3.10+)
2. Check dependencies: `mcp/.venv/bin/python3 -c "import httpx; print('OK')"`
3. Check API key: `ANTHROPIC_API_KEY` must be set

### Agent not connecting

Verify the environment variable is set: `echo $ANTHROPIC_BASE_URL` should show `http://localhost:8080/anthropic`.

---

## Next steps

- [V3 Architecture Design](design/atested-v3-design.md) — how the proxy works, design principles
- [Governance Overview](GOVERNANCE_OVERVIEW.md) — system guarantees, classification, policy
- [Licensing](LICENSING.md) — license terms and commercial use
- [External Contracts](EXTERNAL_CONTRACTS.md) — stability guarantees for CI/CD integration
