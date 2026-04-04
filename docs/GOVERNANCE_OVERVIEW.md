# Governance Layer Overview

> **v3 architecture note:** Atested now operates as an API governance proxy
> (`proxy/server.py`) that intercepts tool calls at the HTTP transport layer.
> The classification, policy evaluation, and chain recording described below
> are unchanged — only the interception point has moved from MCP to the API
> layer. References to "capability registry" and specific governed tool names
> (e.g., `FS_WRITE`) below describe the MCP server surface, which remains
> available as a complementary layer. See
> [docs/design/atested-v3-design.md](design/atested-v3-design.md) for the
> current architecture.

## What is the Governance Layer?

The Governance Layer is a deterministic policy enforcement system for tool execution. It evaluates every tool request against policy rules, classifies operations by observable evidence, produces auditable decision records, and maintains tamper-evident chains. The system guarantees reproducible policy decisions and complete audit trails.

## Core Guarantees

1. **Deterministic Policy Evaluation**: Same inputs → same decision, same record hash
2. **Tamper-Evident Audit Trails**: All decisions recorded with cryptographic hashes
3. **Replay Verification**: Any decision can be independently replayed and verified
4. **Fail-Closed Posture**: Unrecognized tools, malformed requests, or policy violations → DENY
5. **Bounded Execution Scope**: Filesystem operations constrained to allowlisted paths
6. **Intent Tracking**: Every request includes human-readable goal and constraints

## Non-Guarantees (Out of Scope)

- **Execution Isolation**: Policy layer does not sandbox tool execution
- **Distributed Consensus**: Single-node system, no distributed agreement protocol
- **Real-Time Monitoring**: Batch evaluation model, not streaming/reactive
- **Access Control**: No authentication/authorization layer (assumes trusted operator)
- **Rollback/Undo**: Records are append-only, no automatic state reversion

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Tool Request (MCP client, CLI, or API)                      │
│   { tool: "FS_WRITE", args: {...}, intent: {...} }          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Policy Evaluator (scripts/policy-eval.py)                   │
│  - Normalize args (canonical paths, defaults)               │
│  - Match capability class (FS_WRITE → capability registry)  │
│  - Enforce policy rules (path allowlists, deny flags)       │
│  - Compute decision (ALLOW/DENY + reason codes)             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Policy Record (attestation object)                          │
│  { record_hash, request_hash, policy_decision, reasons,     │
│    normalized_args, intent, timestamp, signature }          │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ Decision Chain (append-only JSONL log)                      │
│  $GOV_RUNTIME_DIR/LOGS/decision-chain.jsonl                 │
└─────────────────────────────────────────────────────────────┘
```

## Documentation

- **This document** (GOVERNANCE_OVERVIEW.md): System guarantees and architecture
- [Quickstart Guide](QUICKSTART.md): Get running in under 5 minutes
- [Licensing](LICENSING.md): License terms and commercial use
- [External Contracts](EXTERNAL_CONTRACTS.md): Stability guarantees for CI/CD integration

## Project Status

**Current Phase**: 3 (GovLayer-core trust-grade signing and verification implemented)

**Implemented**:
- Core policy evaluation (FS_READ, FS_WRITE, FS_LIST, FS_MOVE, FS_DELETE)
- MCP server with governed filesystem tools
- Deterministic record generation and replay
- Trust-grade GovLayer-core record signing and verifier closure (record, chain, replay)
- Reason code taxonomy (12 filesystem rejection codes)
- Evidence bundle requirements

<!-- See [CHANGELOG.md](CHANGELOG.md) for detailed progress — not included in public release -->

---

## Phase 3: Asymmetric Signing

**Status**: [IMPLEMENTED] - GovLayer-core trust-grade emit and verifier closure are implemented. Compatibility mode remains available outside the trust-grade claim path.

Phase 3 adds asymmetric cryptographic signatures to every trust-grade policy record, closing INV-005 for the GovLayer-core trust-grade claim path. This enables:

1. **Non-repudiation**: Records are cryptographically bound to the signing key
2. **Third-party verification**: Verifiers can validate signatures without access to runtime environment
3. **Tamper detection**: Any modification to signed fields invalidates the signature

### Signing Semantics

**Algorithm**: Ed25519 (RFC 8032) deterministic signatures
- 32-byte private key → 64-byte signature
- Deterministic (no nonce leakage)
- Base64url-encoded without padding

**What is signed**: Canonical JSON preimage excluding volatile fields:
- ✓ `cap_registry_hash`, `request_hash` (input bindings)
- ✓ `policy_decision`, `policy_reasons` (evaluation outputs)
- ✓ `normalized_args`, `intent` (with paths redacted)
- ✗ `timestamp_utc`, `session_id` (volatile metadata)
- ✗ `record_hash`, `signature` (self-referential)
- ✗ Path expansions (`canonical_path`, `allow_base_dirs`)

**Preimage canonicalization**:
```python
signing_preimage(record) = json.dumps(
    record | {record_hash: null, signature: null},
    sort_keys=True, separators=(",", ":"), ensure_ascii=False
).encode("utf-8")
```

Both `record_hash` and `signature` are computed over the same preimage bytes.

### Key Management

**Key locations** (priority order):
1. `GOV_SIGNING_KEY_PATH` environment variable
2. `~/.config/gov-layer/signing.key` (default)
3. If `GOV_SIGNING_REQUIRED=1` and no signing key is available → fail closed
4. Otherwise → emit unsigned only in compatibility mode

**Key format**: PEM-encoded Ed25519 private key (PKCS#8, unencrypted)

**Key ID format**: `ed25519:<sha256_hex_of_public_key>`

### Schema Changes

Two fields activated in Phase 3:

| Field | Phase 2 | Phase 3 |
|---|---|---|
| `signature` | `null` | Base64url Ed25519 signature (64 bytes, no padding) |
| `signing_key_id` | `null` | Key identifier (`ed25519:...`) |

**Signing modes**:
- **Trust-grade mode**: `GOV_SIGNING_REQUIRED=1` requires signed PolicyRecords and rejects unsigned verification paths.
- **Compatibility mode**: unsigned records remain allowed unless trust-grade mode is explicitly enabled.
- **Explicit degraded mode**: `GOV_SIGNING_DEV_MODE=1` marks compatibility behavior as intentionally non-trust-grade.

### Verification

**Single record verification** (`verify-record.py`):
1. Cap registry hash matches
2. Request hash matches (if present)
3. Record hash matches signing preimage
4. **Signature is valid** (Phase 3 / trust-grade mode): Ed25519 verification using `signing_key_id`

**Chain verification** (`verify-chain.py`):
- Validates `prev_record_hash` links (unchanged)
- Validates all record signatures when records are present in trust-grade mode

**Replay verification** (`replay-record.py`):
- Verifies the original record baseline through `verify-record.py` without miscounting registry drift as baseline corruption
- Re-runs `policy-eval.py` on the stored request bytes
- Verifies the replay-produced record through `verify-record.py`
- Compares deterministic invariants including decision, reason codes, tool, registry binding, normalized args, and coverage stamp

### GovLayer boundary note

GovLayer-core signing covers canonical `PolicyRecord` semantics only. `mcp/receipt_signing.py` signs MCP receipt digests for the connector/application layer and is not part of the core GovLayer signing completion claim.

**Exit codes**: `0` = pass, `1` = verification failed, `2` = fatal error

### Quickstart

```bash
# Generate signing key
python3 - <<'PY'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pathlib import Path

key = Ed25519PrivateKey.generate()
pem = key.private_key_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)
path = Path.home() / ".config" / "gov-layer" / "signing.key"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(pem)
path.chmod(0o600)
print(f"Key created: {path}")
PY

# Sign a decision
python3 scripts/policy-eval.py intent.json > record.json

# Verify signature
python3 scripts/verify-record.py record.json  # Phase 3
python3 scripts/verify-chain.py decision-chain.jsonl  # Full chain
```

<!-- See also: EPIC_SIGNING.md — not included in public release -->

## Key Concepts

**Capability Registry**: JSON schema defining available tools and their normalized argument contracts.

**Policy Record**: Attestation object produced by evaluator, contains decision + reasons + hashes.

**Intent**: Human-readable goal, constraints, and expected outputs attached to every request.

**Reason Code**: Structured rejection reason (e.g., RC-FS-PATH-DISALLOWED, RC-FS-NOT-A-FILE).

**Evidence Bundle**: Test harness + fixtures + TESTS.txt output proving implementation correctness.

**Replay**: Independent re-execution of policy evaluation to verify record integrity.

**Decision Chain**: Append-only log of all policy records, forming tamper-evident audit trail.

## Fail-Closed Behavior

The system defaults to DENY in all ambiguous or error cases:
- Unrecognized tool names
- Malformed intent or args
- Missing required fields
- Path resolution failures
- Registry lookup failures
- Any exception during evaluation

This posture ensures that policy violations cannot occur due to implementation bugs or unexpected inputs.

## Runtime Directory Structure

All runtime artifacts are written outside the repo to `$GOV_RUNTIME_DIR` (default: `gov_runtime/`):

```
$GOV_RUNTIME_DIR/
├── LOGS/
│   ├── decision-chain.jsonl    # Append-only record log
│   └── quarantine/             # Failed integrity chains preserved
└── tmp/                        # Scratch space for tool operations
```

See README.md for environment variable setup.

## Contact & Contributions

See the [Quickstart Guide](QUICKSTART.md) for getting started.
