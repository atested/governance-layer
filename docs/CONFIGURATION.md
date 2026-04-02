# Configuration Reference

Complete reference for all Atested configuration surfaces.

---

## Configuration files

### capabilities/capability-registry.json

**The single most security-critical configuration file.** Controls what every governed tool is allowed to do: allowed directories, per-tool constraints, and hard caps.

| Top-level field | Type | Description |
|---|---|---|
| `version` | string | Registry format version (currently `"0.1"`) |
| `tools` | array | Array of tool configuration entries |

**Per-tool fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `tool` | string | Yes | Tool identifier (e.g., `"FS_WRITE"`) |
| `capability_class` | string | Yes | Capability class name |
| `risk_level` | string | Yes | One of: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `allow_base_dirs` | array | No | Allowed root directories for this tool |
| `deny_hidden_paths` | bool | No | Block dot-prefixed path segments (default: true) |
| `deny_traversal` | bool | No | Block `..` traversal and symlink escapes (default: true) |
| `deny_overwrite_by_default` | bool | No | Require explicit overwrite flag for writes |
| `deny_executable_outputs` | bool | No | Block creation of executable files |
| `args` | object | No | `{required: [...], optional: [...]}` argument specification |
| `caps` | object | No | Tool-specific capability constraints |

**allow_base_dirs placeholders:**

| Placeholder | Resolves to |
|---|---|
| `__GOV_CANONICAL_REPO_PATH__` | `GOV_CANONICAL_REPO_PATH` environment variable |
| `__GOV_RUNTIME_PATH__` | `GOV_RUNTIME_PATH` environment variable |

Any absolute path can also be added directly (e.g., `/home/deploy/staging`).

**Per-tool caps:**

| Tool | Cap field | Default | Description |
|---|---|---|---|
| FS_READ | `max_bytes_default` | 4096 | Default read size |
| FS_READ | `max_bytes_hard` | 65536 | Maximum read size |
| FS_LIST | `max_entries_default` | 100 | Default listing size |
| FS_LIST | `max_entries_hard` | 500 | Maximum listing size |
| FS_LIST | `include_hidden_allowed` | false | Whether hidden files can be listed |
| FS_WRITE | `request_executable_allowed` | false | Whether executable output is allowed |
| FS_MKDIR | `parents_allowed` | true | Whether parent directory creation is allowed |
| FS_MOVE | `overwrite_allowed` | false | Whether moves can overwrite |
| FS_MOVE | `cross_root_allowed` | false | Whether moves across root boundaries are allowed |
| FS_DELETE | `recursive_allowed` | false | Whether recursive deletion is allowed |

---

## Environment variables

### Required (all transports)

| Variable | Description | Example |
|---|---|---|
| `GOV_RUNTIME_DIR` | Path to runtime directory | `/home/you/governance-layer/gov_runtime` |
| `GOV_CANONICAL_REPO_PATH` | Absolute path to the repository root | `/home/you/governance-layer` |
| `GOV_RUNTIME_PATH` | Absolute path to the runtime directory | `/home/you/governance-layer/gov_runtime` |

### Signing

| Variable | Default | Description |
|---|---|---|
| `GOV_SIGNING_KEY_PATH` | — | Path to Ed25519 private key (PEM) |
| `GOV_SIGNING_DEV_MODE` | `"0"` | Set to `"1"` to allow unsigned records (development only) |
| `GOV_SIGNING_REQUIRED` | `"1"` | Set to `"0"` to disable signing |

### Governance context

| Variable | Default | Description |
|---|---|---|
| `GOV_GOVERNED_FAMILY` | `"mcp_tools_v1"` | Governed capability family identifier |
| `GOV_DEPLOYMENT_CONTEXT` | `"default"` | Deployment environment label |
| `GOV_POLICY_VERSION` | `"baseline-v1"` | Policy engine version identifier |

### HTTP transport (multi-client)

| Variable | Default | Description |
|---|---|---|
| `GOVMCP_HOST` | `"127.0.0.1"` | Server bind address |
| `GOVMCP_PORT` | `"8000"` | Server port |
| `GOVMCP_STREAMABLE_HTTP_PATH` | `"/mcp"` | HTTP path for MCP endpoint |
| `GOVMCP_LOG_LEVEL` | `"INFO"` | Logging level |
| `GOVMCP_PUBLIC_BASE_URL` | — | Public URL for OIDC (HTTPS required) |

### Authentication

| Variable | Default | Description |
|---|---|---|
| `GOVMCP_REMOTE_AUTH_MODE` | `"bearer"` | Auth mode: `"bearer"` or `"oidc"` |
| `GOVMCP_REMOTE_AUTH_TOKEN` | — | Shared bearer token |
| `GOVMCP_REMOTE_AUTH_TOKEN_FILE` | — | Path to file containing bearer token |
| `GOVMCP_OIDC_ISSUER_URL` | — | OpenID Connect issuer URL |
| `GOVMCP_OIDC_AUDIENCE` | — | Expected JWT audience claim |
| `GOVMCP_OIDC_REQUIRED_SCOPES` | `""` | Space-separated required scopes |
| `GOVMCP_OIDC_SIGNING_ALGORITHMS` | `"RS256"` | JWT signing algorithms |

---

## Registry integrity

The capability registry is protected with the same rigor as the governance chain:

1. **Startup hash**: SHA-256 computed and stored in memory
2. **Per-call verification**: Every governed tool call re-hashes the file — mismatch fails closed
3. **Permission enforcement**: File must be 0600 or stricter (auto-corrected at startup)
4. **Schema validation**: Enforced at startup and on reload
5. **Tamper detection**: Unauthorized modification logged as `suspicious_event`
6. **Change recording**: Governed reloads produce `registry_config_change` events
7. **Backup**: Copy stored in `gov_runtime/registry_backup.json`

### Governed tools for registry management

| Tool | Purpose |
|---|---|
| `registry_check` | Validate registry file without reloading (catches errors first) |
| `registry_reload` | Apply changes through governance (records old/new hash) |
| `registry_status` | Report current hash, last verified time, reload count |

---

## Runtime directory structure

```
gov_runtime/
├── LOGS/
│   ├── decision-chain.jsonl        # Signed governance chain
│   ├── chain_meta.json             # Chain length metadata
│   ├── chain_stability.jsonl       # Health and stability events
│   ├── records/                    # Individual decision records
│   ├── intents/                    # Request intent files
│   ├── attestations/               # Signed attestation artifacts
│   └── quarantine/                 # Quarantined chains (integrity failures)
├── registry_backup.json            # Startup backup of capability registry
├── TOOL_EVENTS/                    # Tool event logs and bundles
└── tmp/                            # Scratch space
```
