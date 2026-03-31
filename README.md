# Governance Layer

Deterministic policy enforcement system for tool execution with tamper-evident audit trails.

---

## Quick Start

**New to the project?** Start here:
1. [Governance Overview](docs/GOVERNANCE_OVERVIEW.md) - What the system does and guarantees
2. [Attestation Spec](docs/dev/ATTESTATION_SPEC.md) - How attestation and replay work
3. [Runbook](docs/dev/RUNBOOK.md) - How to operate the system

**Contributing?** See:
- [Task Seeds](docs/dev/TASK_SEEDS.md) - Task generation format
- [Work Queue](docs/dev/WORK_QUEUE.md) - Current task queue
- [Assignments](docs/dev/ASSIGNMENTS.md) - Task ownership tracking

---

## Documentation Map

### For Newcomers
- **[Governance Overview](docs/GOVERNANCE_OVERVIEW.md)**: System guarantees, architecture, key concepts
- **[Attestation Spec](docs/dev/ATTESTATION_SPEC.md)**: Object model, replay mechanics, evidence structure
- **[Applications Index](docs/dev/APPLICATIONS_INDEX.md)**: Use cases and downstream consumers

### For Operators
- **[Runbook](docs/dev/RUNBOOK.md)**: Operational procedures (seeds, task generation, run loops, safe defaults)
- **[OPS_CANONICAL.md](docs/dev/OPS_CANONICAL.md)**: Canonical ops record and script registry
- **[Ingestion Workflow](docs/dev/INGESTION_WORKFLOW.md)**: Process for canonicalizing chat content

### For Contributors
- **[Task Seeds](docs/dev/TASK_SEEDS.md)**: Task seed format and generation rules
- **[Work Queue](docs/dev/WORK_QUEUE.md)**: Task queue and status
- **[Assignments](docs/dev/ASSIGNMENTS.md)**: Task ownership tracking (Cecil sole writer on main)

### Specifications
- **[EPIC_SIGNING.md](docs/EPIC_SIGNING.md)**: Phase 3 Ed25519 signing specification
- **[EPIC_PROMOTION.md](docs/EPIC_PROMOTION.md)**: Cross-root promotion design
- **[Invariants Map](docs/dev/INVARIANTS_MAP.md)**: System invariants and enforcement mapping
- **[Reason Codes](docs/dev/REASON_CODES.md)**: Policy rejection reason code index
- **[Merge Gate](docs/dev/MERGE_GATE.md)**: Merge requirements and verification rules

### Project Status
- **[Roadmap](docs/ROADMAP.md)**: Project phases and milestones
- **[Changelog](docs/CHANGELOG.md)**: Implementation history
- **[Active Task](docs/ACTIVE-TASK.md)**: Current work in progress

---

## Core Capabilities

The governance layer enforces policy for these filesystem operations:
- **FS_READ**: Read file contents with path and size restrictions
- **FS_WRITE**: Write files with overwrite control and executable restrictions
- **FS_LIST**: List directories with hidden file filtering
- **FS_MOVE**: Move/rename files with cross-root restrictions
- **FS_DELETE**: Delete files with recursive operation restrictions

**Phase 3 Signing** `[IN_PROGRESS]`:
- **Ed25519 Signatures**: Every policy record is cryptographically signed for non-repudiation
- **Key Management**: Automatic key loading from `GOV_SIGNING_KEY_PATH` or `~/.config/gov-layer/signing.key`
- **Third-Party Verification**: Signatures enable independent verification without runtime access
- **Status**: Emit and key loading implemented. Verification tooling pending.
- **See**: [SIGNING_GUIDE.md](docs/dev/SIGNING_GUIDE.md) for practical usage

See [Applications Index](docs/dev/APPLICATIONS_INDEX.md) for detailed feature status and evidence.

---

## Quick Operations

### Generate Task Batch
```bash
bash system/scripts/codex-batch.sh
# Outputs: ops/CODEX_BATCH.txt
```

### Execute Task (Codex)
```bash
bash system/scripts/codex-unattended.sh run-one TASK_XXX
```

### Merge Task (Cecil)
```bash
git fetch origin --prune
git switch main && git reset --hard origin/main
git merge --no-ff origin/codex/TASK_XXX
# Update ASSIGNMENTS.md (Cecil sole writer)
git push origin main
```

See [Runbook](docs/dev/RUNBOOK.md) for detailed operational procedures.

## External Run Quickstart (Proof Packet + Release Gate)

### Canonical Python Virtualenv

Use a single repo-local virtualenv location for smoke/tests and MCP tooling:

```bash
python3 -m venv mcp/.venv
mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt
```

Use `mcp/.venv/bin/python3` directly in commands to avoid shell activation variance.

One-command local setup + gate run:

```bash
bash system/scripts/bootstrap-run.sh
```

Canonical direct commands:

```bash
# Default/informational proof-packet mode (dev profile)
bash system/scripts/release-gate.sh

# CI/strict proof-packet mode (fails closed if proof-packet check is unavailable)
GOV_PROFILE=ci bash system/scripts/release-gate.sh
```

Expected proof-bundle outputs (when enabled by release-gate features):
- `out/proof-bundles/<run-id>/proof_packet.tar`
- `out/proof-bundles/<run-id>/proof_packet.sha256`
- `out/proof-bundles/<run-id>/proof_packet_verify_summary.json`
- `out/proof-bundles/<run-id>/versions.txt`
- `out/release_gate.stdout.log` (top-level release-gate transcript for CI artifact upload)

Optional proof-bundle outputs (when available):
- `out/proof-bundles/<run-id>/queue_drift_scan.txt` (informational text)
- `out/proof-bundles/<run-id>/status_bundle.json` (recommended machine-readable status summary)

Interpreting status lines:
- `PASS`: check ran and succeeded
- `FAIL`: check ran and failed (nonzero)
- `SKIP`: verifier unavailable due to explicit missing dependency (for `verify-task`, rc=3)

### MCP Smoke Dependency Note

MCP smoke checks may report deterministic `SKIP` when the canonical interpreter lacks the `mcp` dependency. Use the runbook notes to enable full mode and interpret `SKIP` vs `FAIL`.

### MCP Dependency Pin Note

- Pin location: `mcp/requirements.txt` (`mcp==1.26.0`).
- Rationale: keep MCP smoke/client-server behavior deterministic across local runs and CI.
- Safe update flow:
  1. Change only the pin in `mcp/requirements.txt`.
  2. Reinstall into `mcp/.venv`.
  3. Re-run `tests/run-mcp-smoke.sh`.
  4. Record evidence for the version change.

Enable full mode deterministically:
1. `python3 -m venv mcp/.venv`
2. `mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt`
3. `GOV_RUNTIME_DIR=${GOV_RUNTIME_DIR:-.gov_runtime} bash tests/run-mcp-smoke.sh`

Interpretation:
- `SKIP`: missing MCP dependency in the selected interpreter (environment setup gap)
- `FAIL`: smoke executed but behavioral contract check failed

### Stability Guarantees for External Consumers

The governance-layer provides **stability contracts** for CI/CD integration:

- **Proof-packet schemas frozen:** `proof_packet_v1` manifest and `proof_packet_verify_summary_v1` summary schemas are versioned and stable
- **Required files guaranteed:** `proof_packet.tar`, `proof_packet_verify_summary.json`, `proof_packet.sha256`, `release_gate_log.txt`, `versions.txt`
- **Optional files may be present:** `queue_drift_scan.txt`, `status_bundle.json` (do not treat as required)
- **Profile semantics:** `dev` (informational) and `ci` (gating) profiles for strictness control
- **Versioning policy:** Additive-only changes within v1, breaking changes require v2

See [EXTERNAL_CONTRACTS.md](docs/EXTERNAL_CONTRACTS.md) for full contract details, versioning policy, and what's guaranteed vs. what's implementation detail.

---

## Runtime directory

All runtime artifacts (decision chain, quarantine, scratch files) are written outside the repo.
Set `GOV_RUNTIME_DIR` to control the location. Default when unset: `.gov_runtime/` (gitignored).

```
$GOV_RUNTIME_DIR/
├── LOGS/
│   ├── decision-chain.jsonl   # append-only tamper-evident chain
│   └── quarantine/            # broken chains preserved on integrity failure
└── tmp/                       # scratch space for governed tool operations
```

The MCP server and policy evaluator both read `GOV_RUNTIME_DIR` at startup.
Example: `GOV_RUNTIME_DIR=/path/to/runtime bash tests/run-mcp-smoke.sh`
No component should require a machine-specific absolute default path.
