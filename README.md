# Atested

Governance infrastructure for AI operations. Every action your AI agents take is evaluated against policy, signed into an immutable record, and available as auditable proof.

**Website**: [atested.com](https://atested.com) — pricing, documentation, and the business case for governance.

**License**: [Business Source License 1.1](LICENSE) — free for personal use, commercial use requires a paid license. Converts to Apache 2.0 on March 30, 2030.

---

## What it does

Atested is a policy enforcement layer for AI tool execution. It sits between your AI agents and the actions they take, evaluating every action against a capability registry and producing a tamper-evident audit record.

- **Policy evaluation**: Every tool call is evaluated against your policy before execution. ALLOW or DENY.
- **Signed records**: Every decision is cryptographically signed (Ed25519) into an immutable hash chain.
- **Proof packets**: Generate verifiable attestation artifacts for any audit or review.

The system exposes 46 governed tools via the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP).

---

## Quick start

### 1. Clone and install

```bash
git clone https://github.com/GregKeeter/governance-layer.git
cd governance-layer
python3 -m venv mcp/.venv
mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt
```

### 2. Run the release gate

```bash
bash system/scripts/release-gate.sh
```

This runs the test suite, compiles all policy scripts, and produces a proof packet.

### 3. Start the MCP server

```bash
# Local (stdio transport)
mcp/.venv/bin/python3 mcp/server.py

# Remote (HTTP transport with bearer auth)
mcp/.venv/bin/python3 mcp/remote_server.py
```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for the full guide.

---

## Governed tools

| Category | Tools | Purpose |
|---|---|---|
| **Filesystem** (6) | `fs_read`, `fs_write`, `fs_list`, `fs_mkdir`, `fs_move`, `fs_delete` | Policy-governed file operations |
| **Messaging** (2) | `msg_send`, `msg_reply` | Governed message dispatch |
| **Capabilities** (16) | `capabilities_list`, `capabilities_execute`, `capabilities_receipt`, `capabilities_replay_check`, ... | Capability registry, execution, attestation |
| **Tool catalog** (12) | `capabilities_tool_register`, `capabilities_tool_get`, `capabilities_tool_catalog_*`, ... | Tool registration, event tracking, bundle export |
| **Governance** (4) | `governance_status`, `governance_approvals`, `governance_verification`, `governance_activity` | System status, approval state, audit |
| **Surface management** (6) | `approve_artifact`, `revoke_artifact`, `certify_surface`, `recertify_surface`, `report_drift`, `run_probe_and_apply` | Artifact approval, surface certification |

Every tool call produces a policy decision record appended to a tamper-evident decision chain.

---

## How it works

1. An AI agent requests an action through MCP.
2. The governance layer evaluates the action against the capability registry.
3. The decision (ALLOW or DENY) is recorded with a SHA-256 hash linking to the previous record.
4. The record is cryptographically signed with Ed25519.
5. At any point, an attestation artifact can summarize all governance activity.
6. A proof packet bundles everything into a verifiable deliverable.

See [How it works](https://atested.com/how-it-works.html) on the website for the full walkthrough.

---

## Documentation

- [Quickstart Guide](docs/QUICKSTART.md) — get running in under 5 minutes
- [Governance Overview](docs/GOVERNANCE_OVERVIEW.md) — system guarantees, architecture, key concepts
- [Licensing](docs/LICENSING.md) — license terms and commercial use
- [External Contracts](docs/EXTERNAL_CONTRACTS.md) — stability guarantees for CI/CD integration
- [Example proof packets](docs/examples/proof-packets/) — real attestation artifacts from three scenarios

---

## Runtime

All runtime artifacts are written outside the repo. Set `GOV_RUNTIME_DIR` to control the location (default: `gov_runtime/`).

```
$GOV_RUNTIME_DIR/
├── LOGS/
│   ├── decision-chain.jsonl   # append-only tamper-evident chain
│   └── quarantine/            # broken chains preserved on integrity failure
└── tmp/                       # scratch space for governed tool operations
```

---

## License

Atested is source-available under the [Business Source License 1.1](LICENSE).

- **Personal use**: Free, no license key required.
- **Commercial use**: Requires a paid license from [atested.com](https://atested.com/pricing.html).
- **Change date**: March 30, 2030 — after this date, the code converts to Apache License 2.0.

See [docs/LICENSING.md](docs/LICENSING.md) for full details.
