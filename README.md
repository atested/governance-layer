# Atested

Governance infrastructure for AI operations. Atested is an API governance proxy that sits between your AI agents and their model providers. It intercepts every tool call before execution, classifies it by observable evidence, evaluates it against policy, and records the decision in a tamper-evident chain. One environment variable. Every tool call governed. The agent never knows governance is in the path.

**Website**: [atested.com](https://atested.com) — pricing, documentation, and the business case for governance.

**License**: [Business Source License 1.1](LICENSE) — free for personal use, commercial use requires a paid license. Converts to Apache 2.0 on March 30, 2030.

---

## How it works

AI agents work in a loop: send context to the model API, receive tool calls back, execute them locally. Atested sits in this loop at the API transport layer. When the model responds with tool calls, Atested intercepts them before the agent sees them.

```
Agent → Atested Proxy → Model Provider API
                ↓
        Model responds with tool calls
                ↓
        Classify each tool call (evidence inference)
                ↓
        Evaluate against policy rules
                ↓
        Record decision in governance chain
                ↓
        ALLOW → pass tool call to agent unchanged
        DENY  → replace with denial message
```

- **Evidence-based classification.** Every tool call is classified by what its parameters contain — file paths, commands, URLs — not by tool names or agent claims. Classification carries an explicit confidence tier (1–4).
- **Deterministic evaluation.** Same action, same evidence, same decision. Where a decision cannot be made deterministically, the system marks it explicitly as requiring operator judgment.
- **Signed records.** Every decision is recorded with a SHA-256 hash linking to the previous record, forming a tamper-evident chain.
- **Streaming support.** Text streams through in real time. Tool calls are buffered, governed, then passed or replaced. Sub-millisecond classification latency.

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/atested/governance-layer.git
cd governance-layer
python3 -m venv mcp/.venv
mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt
```

### 2. Start the proxy

```bash
ANTHROPIC_API_KEY=sk-... python3 -m proxy.server
```

The proxy starts on `http://127.0.0.1:8080`. It forwards to the Anthropic API by default.

### 3. Point your agent at the proxy

Set one environment variable before launching your AI agent:

```bash
export ANTHROPIC_BASE_URL=http://localhost:8080/anthropic
```

That's it. Your agent talks to Atested instead of the Anthropic API directly. Every tool call is now governed.

### Options

```bash
# Custom port and bind address
python3 -m proxy.server --port 9000 --host 0.0.0.0

# Custom upstream (for non-Anthropic providers)
python3 -m proxy.server --upstream https://api.openai.com

# Friendly identity label (default: system hostname)
python3 -m proxy.server --user-identity "dev-machine-1"
# Or via environment variable:
ATESTED_USER_LABEL="dev-machine-1" python3 -m proxy.server
```

---

## What gets governed

The proxy sees every tool call in the API conversation: file reads, file writes, shell commands, git operations, search queries, network requests — anything the model asks the agent to do.

Each tool call is classified into a confidence tier:

| Tier | Meaning | Policy |
|---|---|---|
| **Tier 1** | Directly observable (file paths, URLs) | Automatic ALLOW/DENY by rule |
| **Tier 2** | High-confidence inferred (git, make, known commands) | Automatic ALLOW/DENY by rule |
| **Tier 3** | Opaque execution (scripts, interpreters) | Candidate for operator approval |
| **Tier 4** | Uninspectable (encoded payloads) | Default DENY |

Policy rules are declarative JSON (`capabilities/policy-rules.json`). First matching rule wins.

---

## Dashboard

Atested includes a live dashboard for real-time visibility into governance activity.

```bash
# Start via the MCP governance-broker, or directly:
python3 dashboard/server.py
```

The dashboard shows: chain health, mediated decisions, denied actions, operation approvals, audit queries, and reports — all backed by the governance chain.

---

## Compatibility

**AI agents:** Any agent that allows configuring its API endpoint — coding assistants, CLI agents, IDE integrations, custom agents.

**Model providers:** Anthropic API (native support). OpenAI-compatible APIs (with `--upstream`). Any provider using the standard tool call format.

**MCP governance (complementary):** The MCP server (`mcp/server.py`) remains available for governing upstream MCP tool servers. The API proxy governs the agent; the MCP proxy governs tool servers. Different layers, both useful.

---

## Documentation

- [Quickstart Guide](docs/QUICKSTART.md) — detailed setup and configuration
- [V3 Architecture Design](docs/design/atested-v3-design.md) — API proxy architecture, design principles, deployment models
- [Governance Overview](docs/GOVERNANCE_OVERVIEW.md) — system guarantees, classification, policy evaluation
- [Licensing](docs/LICENSING.md) — license terms and commercial use
- [External Contracts](docs/EXTERNAL_CONTRACTS.md) — stability guarantees for CI/CD integration

---

## Architecture

| Component | File | Purpose |
|---|---|---|
| API governance proxy | `proxy/server.py` | HTTP proxy that intercepts and governs tool calls |
| Evidence classifier | `scripts/classifier.py` | Tier 1–4 classification by parameter inspection |
| Policy rules | `capabilities/policy-rules.json` | Declarative action-based rules (first match wins) |
| Policy evaluator | `scripts/policy_eval_v2.py` | Evaluate classification against policy |
| Dashboard | `dashboard/server.py` | Live web UI for governance visibility |
| MCP server | `mcp/server.py` | MCP tools for governance operations |

---

## Runtime

All runtime artifacts are written outside the repo. Set `GOV_RUNTIME_DIR` to control the location (default: `gov_runtime/`).

```
$GOV_RUNTIME_DIR/
├── LOGS/
│   ├── decision-chain.jsonl   # append-only tamper-evident chain
│   └── quarantine/            # broken chains preserved on integrity failure
└── tmp/                       # scratch space
```

---

## License

Atested is source-available under the [Business Source License 1.1](LICENSE).

- **Personal use**: Free, no license key required.
- **Commercial use**: Requires a paid license from [atested.com](https://atested.com/pricing.html).
- **Change date**: March 30, 2030 — after this date, the code converts to Apache License 2.0.

See [docs/LICENSING.md](docs/LICENSING.md) for full details.
