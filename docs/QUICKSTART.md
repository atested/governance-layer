# Quickstart

Get from clone to governed operations in under 5 minutes.

---

## Prerequisites

- **Python 3.10+** (the MCP server and `mcp` package require it)
- **Git**
- An MCP client (e.g., [Claude Code](https://claude.com/claude-code))

Check your Python version:

```bash
python3 --version
# Must be 3.10 or higher
```

If your system Python is older, install a newer version via Homebrew (`brew install python@3.12`) or your package manager of choice. The rest of this guide uses `python3` — substitute the versioned binary (e.g., `python3.12`) if needed.

---

## 1. Clone and install

```bash
git clone <repo-url> governance-layer
cd governance-layer

# Create the Python virtualenv and install dependencies
python3 -m venv mcp/.venv
mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt
```

The virtualenv lives at `mcp/.venv/` and is gitignored. All commands in this guide use `mcp/.venv/bin/python3` directly to avoid shell activation variance.

---

## 2. Initialize the runtime directory

The governance layer writes decision chains, logs, and scratch files to a runtime directory. The default is `gov_runtime/` at the repo root (gitignored).

```bash
mkdir -p gov_runtime/LOGS gov_runtime/tmp
```

If you want a different location, set `GOV_RUNTIME_DIR` everywhere below to that path.

---

## 3. Configure your MCP client

### Claude Code

Create `.mcp.json` in the repo root (it is gitignored):

```json
{
  "mcpServers": {
    "governance-broker": {
      "type": "stdio",
      "command": "<REPO_ROOT>/mcp/.venv/bin/python3",
      "args": ["<REPO_ROOT>/mcp/server.py"],
      "env": {
        "GOV_RUNTIME_DIR": "<REPO_ROOT>/gov_runtime",
        "GOV_CANONICAL_REPO_PATH": "<REPO_ROOT>",
        "GOV_RUNTIME_PATH": "<REPO_ROOT>/gov_runtime"
      }
    }
  }
}
```

Replace every `<REPO_ROOT>` with the absolute path to your clone (e.g., `/home/you/governance-layer`).

Restart Claude Code (or reload the window) to pick up the new server.

### Other MCP clients

Any client that speaks the [Model Context Protocol](https://modelcontextprotocol.io/) over stdio can connect. Point it at:

- **Command**: `<REPO_ROOT>/mcp/.venv/bin/python3`
- **Args**: `["<REPO_ROOT>/mcp/server.py"]`
- **Environment variables** (all three are required for policy evaluation):
  - `GOV_RUNTIME_DIR` — path to the runtime directory
  - `GOV_CANONICAL_REPO_PATH` — absolute path to the repo root
  - `GOV_RUNTIME_PATH` — absolute path to the runtime directory

---

## 4. Verify: make a governed tool call

Once your client is connected, call the `fs_list` tool to list the repo root:

```
Tool: fs_list
Arguments: { "path": "<REPO_ROOT>" }
```

A successful response looks like:

```json
{
  "policy_decision": "ALLOW",
  "policy_reasons": [],
  "entries": ["README.md", "docs/", "mcp/", "scripts/", "..."]
}
```

Key things to check:

- `"policy_decision": "ALLOW"` — the path is within the configured allow-list
- `"policy_reasons": []` — no policy violations

If you see `"policy_decision": "DENY"`, that is the governance layer working correctly — see Troubleshooting below.

---

## 5. Run the test suite

Confirm everything is wired up:

```bash
# Quick smoke test (MCP server round-trip)
GOV_RUNTIME_DIR=gov_runtime bash tests/run-mcp-smoke.sh

# Full release gate (28 test suites)
GOV_PROFILE=dev bash system/scripts/release-gate.sh
```

All 28 suites should report PASS. MCP smoke requires the virtualenv from step 1.

---

## 6. Explore the tool surface

The server exposes 42 governed tools across these categories:

| Category | Tools | Purpose |
|---|---|---|
| **Filesystem** | `fs_read`, `fs_write`, `fs_list`, `fs_mkdir`, `fs_move`, `fs_delete` | Policy-governed file operations |
| **Messaging** | `msg_send`, `msg_reply` | Governed message dispatch |
| **Capabilities** | `capabilities_list`, `capabilities_describe`, `capabilities_execute`, `capabilities_receipt`, ... | Capability registry, execution, attestation |
| **Tool catalog** | `capabilities_tool_register`, `capabilities_tool_get`, `capabilities_tool_catalog_*`, `capabilities_tool_event_*` | Tool registration, event tracking, bundle export/verify |
| **Governance** | `governance_status`, `governance_approvals`, `governance_verification`, `governance_activity` | System status and audit |
| **Surface management** | `approve_artifact`, `revoke_artifact`, `certify_surface`, `recertify_surface`, `report_drift`, `run_probe_and_apply` | Artifact approval, surface certification, drift detection |

Call `capabilities_list` or `governance_status` from your client to see the live tool inventory.

---

## Configuring your governance boundary

The governance boundary — what your AI tools are allowed to do — is controlled by a single file: `capabilities/capability-registry.json`. This is the most security-critical configuration file in Atested.

### What it controls

Each entry in the `tools` array defines one governed tool:

| Field | What it does |
|---|---|
| `allow_base_dirs` | Directories the tool can access. Paths outside this list are denied. |
| `deny_hidden_paths` | Block access to dot-prefixed paths (`.git/`, `.env`, etc.) |
| `deny_overwrite_by_default` | Require explicit `overwrite: true` for writes to existing files |
| `deny_executable_outputs` | Block creation of executable files |
| `caps` | Hard limits (max bytes, max entries, etc.) |

### Out-of-the-box defaults

Without changing anything, Atested:
- Limits all tools to the project repository and runtime directory
- Blocks hidden paths, overwrites, and executable outputs
- Caps file reads at 64KB and directory listings at 500 entries
- Blocks recursive deletes and cross-root moves

### Adding a directory to scope

To let `fs_write` write to `/home/deploy/staging`, edit the registry:

```json
{
  "tool": "FS_WRITE",
  "allow_base_dirs": [
    "__GOV_CANONICAL_REPO_PATH__",
    "__GOV_RUNTIME_PATH__",
    "/home/deploy/staging"
  ]
}
```

The placeholders `__GOV_CANONICAL_REPO_PATH__` and `__GOV_RUNTIME_PATH__` resolve at runtime from your environment variables.

### Adjusting per-tool constraints

To allow recursive deletes (use with caution):

```json
{
  "tool": "FS_DELETE",
  "caps": {
    "recursive_allowed": true
  }
}
```

To increase the read size limit:

```json
{
  "tool": "FS_READ",
  "caps": {
    "max_bytes_default": 8192,
    "max_bytes_hard": 131072
  }
}
```

### Applying changes

After editing the registry, use the governed reload process:

```
1. registry_check    — Validate your changes (catches errors before they take effect)
2. registry_reload   — Apply the new configuration through governance
3. registry_status   — Confirm the new hash is active
```

Do not restart the server to apply registry changes — use `registry_reload` so the change is recorded as a governance event with the old and new configuration hashes.

### Integrity protections

The registry is protected with the same rigor as the governance chain:

- **Startup verification**: SHA-256 hash computed and stored; schema validated; file permissions checked (0600 enforced)
- **Per-call verification**: Every governed tool call verifies the registry hasn't changed — fail closed on mismatch
- **Tamper detection**: Modifications without `registry_reload` are logged as SUSPICIOUS events in the stability log
- **Configuration change recording**: Every reload records old hash → new hash as a governance event
- **Backup**: A copy is stored in `gov_runtime/registry_backup.json` at startup

---

## Troubleshooting

### DENY is correct behavior

A `DENY` response means the governance layer evaluated the request and rejected it on policy grounds. Common reason codes:

| Code | Meaning |
|---|---|
| `RC-FS-PATH-DISALLOWED` | Path is outside the configured `allow_base_dirs` |
| `RC-FS-HIDDEN-PATH` | Path contains a dot-prefix segment (e.g., `.git/`) |
| `RC-FS-PATH-TRAVERSAL` | Path contains `..` traversal |
| `RC-FS-WRITE-OVERWRITE` | Write to existing file with `overwrite: false` |

### Server won't start

1. Check Python version: `mcp/.venv/bin/python3 --version` (must be 3.10+)
2. Check dependencies: `mcp/.venv/bin/python3 -c "import mcp; print('OK')"`
3. Check env vars: all three (`GOV_RUNTIME_DIR`, `GOV_CANONICAL_REPO_PATH`, `GOV_RUNTIME_PATH`) must be absolute paths

### Missing runtime directory

If you see errors about missing chain files:

```bash
mkdir -p gov_runtime/LOGS gov_runtime/tmp
```

### Environment variable placeholders not resolving

If `fs_list` on the repo root returns DENY with `RC-FS-PATH-DISALLOWED`, the env vars are likely not set. Verify your `.mcp.json` has all three env entries with correct absolute paths, then restart your MCP client.

---

## Multi-client HTTP deployment

The stdio transport (above) serves a single client. For multi-client / team use,
the HTTP transport allows multiple MCP clients to share one server process with
concurrent-safe chain locking and per-user identity tracking.

### Start the HTTP server

```bash
export GOV_RUNTIME_DIR="<REPO_ROOT>/gov_runtime"
export GOV_CANONICAL_REPO_PATH="<REPO_ROOT>"
export GOV_RUNTIME_PATH="<REPO_ROOT>/gov_runtime"
export GOVMCP_HOST="0.0.0.0"
export GOVMCP_PORT="8000"
export GOVMCP_STREAMABLE_HTTP_PATH="/mcp"
export GOVMCP_REMOTE_AUTH_TOKEN="<your-shared-secret>"
export GOVMCP_PUBLIC_BASE_URL="https://govmcp.example.com"

mcp/.venv/bin/python3 mcp/remote_server.py
```

The server listens on `http://0.0.0.0:8000/mcp` and requires a Bearer token.

> **Security: proxy-only deployment (H9)**
>
> The HTTP transport provides **no TLS**. You **must** deploy it behind a
> TLS-terminating reverse proxy (nginx, Caddy, AWS ALB, etc.) before exposing
> it to any network. Bearer tokens sent over plain HTTP are visible to network
> observers. The server emits a startup warning when binding to `0.0.0.0` or
> `::` as a reminder.

### Connect clients

Each MCP client connects over HTTP with an `Authorization: Bearer <token>` header.
Multiple simultaneous connections are safe — a `threading.Lock` in the server plus
a portable file lock in the chain-append script prevent interleaving.

### User identity

Every governance record includes a `user_identity` field derived from the auth token:

- **Bearer mode**: `bearer:<sha256-prefix>` (stable hash of the token)
- **OIDC mode**: `oidc:<sub-claim>` (from the JWT `sub` field)

Subagents using the same auth token are attributed to the same user identity.
Call `governance_user_report` to see unique user counts and per-user action totals.

> **Limitation: bearer token user collapsing (H10)**
>
> In bearer mode, user identity is derived from a SHA-256 prefix of the token.
> All clients sharing the same bearer token are collapsed into a single user
> identity (`bearer:<hash-prefix>`). This means:
>
> - **Unique user counts** will under-count if multiple people share one token.
> - **Trial-to-personal transition** (which checks unique user count ≤ 1) may
>   incorrectly trigger for multi-user deployments sharing a token.
> - **Per-user audit trails** cannot distinguish between individuals sharing a token.
>
> For accurate per-user tracking, issue distinct bearer tokens per user or use
> OIDC mode, which derives identity from the JWT `sub` claim.

### Deployment modes summary

| Mode | Transport | Clients | Use case |
|---|---|---|---|
| **stdio** | stdin/stdout | 1 (spawned by client) | Personal use, Claude Code |
| **HTTP** | streamable-http | Many (concurrent) | Team/business, multi-agent |

---

## Next steps

- [Governance Overview](GOVERNANCE_OVERVIEW.md) — architecture and guarantees
- [Licensing](LICENSING.md) — license terms and commercial use
- [External Contracts](EXTERNAL_CONTRACTS.md) — stability guarantees for CI/CD integration
