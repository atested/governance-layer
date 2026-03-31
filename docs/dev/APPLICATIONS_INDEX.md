# Applications Index

Status-tagged index of downstream consumers, use cases, and applications built on the governance layer.

**Status Tags**:
- `[IMPLEMENTED]` - Code exists, tested, evidence on main
- `[IN_PROGRESS]` - Active development, branch exists or task in queue
- `[DESIGN_ONLY]` - Spec/EPIC exists, no implementation yet
- `[SPECULATIVE]` - Idea/proposal only, no spec or code
- `[NEEDS_VALIDATION]` - Implementation exists but needs verification

---

## Core Capabilities (Governed Tools)

### FS_READ `[IMPLEMENTED]`
**Description**: Read file contents with path restrictions and size limits.

**Policy Enforcement**:
- Path must be within allowlisted base directories
- No hidden path components
- Target must be a regular file (not directory or symlink)
- Size capped by max_bytes parameter

**Evidence**: `docs/dev/evidence/TASK_065/`, `tests/test_rc_fs_not_a_file.sh`

**Reason Codes**: RC-FS-PATH-DISALLOWED, RC-FS-HIDDEN-PATH, RC-FS-NOT-A-FILE, RC-FS-MAX-BYTES-EXCEEDED

---

### FS_WRITE `[IMPLEMENTED]`
**Description**: Write file contents with overwrite control and executable restrictions.

**Policy Enforcement**:
- Path must be within allowlisted base directories
- No hidden path components
- Overwrite requires explicit intent declaration
- Executable output files denied by default

**Evidence**: `docs/dev/evidence/TASK_062/`, `tests/test_rc_fs_executable_disallowed.sh`

**Reason Codes**: RC-FS-PATH-DISALLOWED, RC-FS-HIDDEN-PATH, RC-FS-OVERWRITE-DISALLOWED, RC-FS-EXECUTABLE-DISALLOWED

---

### FS_LIST `[IMPLEMENTED]`
**Description**: List directory contents with hidden file filtering.

**Policy Enforcement**:
- Path must be within allowlisted base directories
- No hidden path components
- Target must be a directory (not file)
- include_hidden must be false (Phase 2 restriction)

**Evidence**: `docs/dev/evidence/TASK_063/`, `docs/dev/evidence/TASK_064/`, `tests/test_rc_fs_not_a_directory.sh`, `tests/test_rc_fs_include_hidden_disallowed.sh`

**Reason Codes**: RC-FS-PATH-DISALLOWED, RC-FS-HIDDEN-PATH, RC-FS-NOT-A-DIRECTORY, RC-FS-INCLUDE-HIDDEN-DISALLOWED

---

### FS_MOVE `[IMPLEMENTED]`
**Description**: Move/rename files with cross-root restrictions.

**Policy Enforcement**:
- Source and destination must be within allowlisted base directories
- No hidden path components
- Cross-root moves denied (except via EPIC_PROMOTION)
- Source must exist, destination must not exist (unless overwrite intent)

**Evidence**: MCP smoke tests, `scripts/policy-eval.py` implementation

**Reason Codes**: RC-FS-PATH-DISALLOWED, RC-FS-HIDDEN-PATH, RC-FS-CROSS-ROOT-DISALLOWED

**Related**: See [EPIC_PROMOTION.md](../EPIC_PROMOTION.md) for bounded cross-root promotion design

---

### FS_DELETE `[IMPLEMENTED]`
**Description**: Delete files with recursive operation restrictions.

**Policy Enforcement**:
- Path must be within allowlisted base directories
- No hidden path components
- Recursive deletion denied (Phase 2 restriction)
- Target must exist

**Evidence**: `docs/dev/evidence/TASK_043/`, `tests/fixtures/fs_delete_*.json`

**Reason Codes**: RC-FS-PATH-DISALLOWED, RC-FS-HIDDEN-PATH, RC-FS-RECURSIVE-DISALLOWED

**Spec**: Task specs TASK_040-043 (intent schema, policy enforcement, MCP tool, test harness)

---

## Infrastructure & Tooling

### MCP Server (Governed Tools) `[IMPLEMENTED]`
**Description**: Model Context Protocol server exposing governed filesystem tools.

**Status**: Operational, smoke tests passing

**Tools Exposed**:
- fs_read (governed)
- fs_write (governed)
- fs_list (governed)
- fs_move (governed)
- fs_delete (governed)

**Evidence**: `tests/run-mcp-smoke.sh`, MCP server logs

**Code**: `mcp/server.py` (or equivalent MCP implementation)

---

### Policy Evaluator `[IMPLEMENTED]`
**Description**: Core policy evaluation engine producing attestation records.

**Status**: Deterministic evaluation confirmed via replay tests

**Features**:
- Capability registry lookup
- Argument normalization
- Policy rule enforcement
- Reason code emission
- Record hash computation
- Build manifest generation

**Evidence**: All TASK_062-067, TASK_092-095 test harnesses

**Code**: `scripts/policy-eval.py`

---

### Replay Verification `[IMPLEMENTED]`
**Description**: Independent replay of policy decisions to verify record integrity.

**Status**: GovLayer-core replay verifies the original record baseline, the replay-produced record, and deterministic invariants. Trust-grade replay mode is explicit and fail-closed.

**Features**:
- Request deserialization from base64
- Original-record verification through `verify-record.py`
- Policy re-evaluation with same registry and stored request bytes
- Replay-output verification through `verify-record.py`
- Invariant comparison for decision, reason codes, tool, registry binding, normalized args, and coverage stamp
- Registry-drift mismatch detection without collapsing replay into a false baseline fatal

**Evidence**: `tests/test_replay.sh`, `tests/test_replay_audit_report.sh`, `tests/test_coverage_stamp_replay.sh`, `tests/test_replay_trust_grade_mode.sh`

**Code**: `scripts/replay-record.py`

---

### Build Manifest Generation `[IMPLEMENTED]`
**Description**: Path-free deterministic summaries for CI/CD verification.

**Status**: Implemented, E2E tests passing

**Features**:
- Extract stable fields from PolicyRecord
- Compute normalized_args_hash
- Generate deterministic manifest JSON

**Evidence**: `tests/test_build_manifest_determinism.sh` (TASK_097)

**Code**: `scripts/policy-eval.py::build_manifest_from_record()`

---

## Phase 3: Signing & Verification

### Ed25519 Signing `[IMPLEMENTED]`
**Description**: Cryptographic signatures over policy records for non-repudiation.

**Status**: Core GovLayer record-signing semantics, verifier support, and explicit trust-grade mode are implemented. Compatibility mode remains available for non-trust-grade operation.

**Implemented Features**:
- Ed25519 signature emission (`policy-eval.py → emit_record()`)
- Signing preimage computation (path-redacted, volatile fields excluded)
- Key loading from `GOV_SIGNING_KEY_PATH` or `~/.config/gov-layer/signing.key`
- Base64url-encoded signatures (no padding)
- Key ID format: `ed25519:<sha256_hex_of_public_key>`
- Signature verification in `verify-record.py`
- Chain verification through `verify-chain.py`
- Explicit trust-grade mode via `GOV_SIGNING_REQUIRED=1`
- Explicit compatibility/degraded mode via `GOV_SIGNING_DEV_MODE=1`

**Boundary Note**:
- GovLayer-core signing covers canonical `PolicyRecord` semantics.
- MCP-local receipt signing in `mcp/receipt_signing.py` is connector-layer behavior and does not count as GovLayer-core signing completion.

**Evidence**:
- TASK_100: `docs/dev/evidence/TASK_100/`, `tests/test_signing_emit.sh`
- TASK_106: `docs/dev/evidence/TASK_106/`, `tests/test_signing_key_loading.sh`
- Trust-grade mode: `tests/test_verify_signatures.sh`, `tests/test_signing_required_mode.sh`

**Spec**: [EPIC_SIGNING.md](../EPIC_SIGNING.md), [SIGNING_GUIDE.md](SIGNING_GUIDE.md)

**Tasks**:
- ✓ TASK_100 (signing preimage + emit) - merged
- ✓ TASK_106 (key loading) - merged
- ✓ TASK_101 semantics now present in core verifier paths

---

### Signing Determinism Tests `[IMPLEMENTED]`
**Description**: Verify that signatures are stable across replay.

**Status**: Core signature determinism coverage exists; follow-on expansion may still deepen coverage.

**Evidence**: `tests/test_signing_determinism.sh` (TASK_099, TASK_012)

**Code**: Signing determinism coverage and verifier-side signature checks are both present

---

## Workflow Automation

### Task Scaffolding `[IMPLEMENTED]`
**Description**: Generate task specifications from seed files.

**Status**: Operational, EXECUTOR field support added

**Features**:
- Parse SEED.md batch files
- Allocate unique TASK_IDs
- Generate task spec markdown with allowlists
- Auto-append evidence paths
- Support EXECUTOR field (Codex, Cecil, UNASSIGNED)

**Evidence**: `docs/dev/evidence/TASK_073/`, TASK_071 test task

**Code**: `scripts/task_scaffold.py`

---

### Codex Batch Execution `[IMPLEMENTED]`
**Description**: Automated batch processing of Codex-assigned tasks.

**Status**: Read-only mode, filtering by EXECUTOR field operational

**Features**:
- List tasks from WORK_QUEUE.md "Next" section
- Filter to Codex-executable tasks (Executor: Codex)
- Generate batch instructions (CODEX_BATCH.txt)
- Respect current branch (no forced checkout to main)
- Fail-closed: no queue claims in batch mode

**Evidence**: `docs/dev/evidence/TASK_072/`, `docs/dev/evidence/TASK_078/`

**Code**: `system/scripts/codex-batch.sh`, `system/scripts/codex-unattended.sh`

---

### Codex Throughput Loop `[IMPLEMENTED]`
**Description**: Automated loop for high-throughput task execution.

**Status**: Implemented, evidence recorded

**Features**:
- Continuous batch generation
- Task claiming and execution
- Evidence bundle creation
- Branch management

**Evidence**: `docs/dev/evidence/TASK_012/`

**Code**: `system/scripts/codex-throughput-loop.sh`

---

### Cecil Runloop `[IMPLEMENTED]`
**Description**: Cecil's operational loop (claim, plan, merge).

**Status**: Operational

**Features**:
- Merge queue processing
- Task claiming for Cecil
- Plan mode integration
- ASSIGNMENTS.md updates with UNION rule

**Code**: `system/scripts/cecil-runloop.sh`

---

### Merge Queue Automation `[IMPLEMENTED]`
**Description**: Automated merging with conflict resolution and verification.

**Status**: Operational, ASSIGNMENTS.md union rule enforced

**Features**:
- No-ff merge strategy
- ASSIGNMENTS.md-only conflict auto-resolution (union merge)
- Post-merge verification (inventory + ops canonical)
- Fail-closed on verification failures

**Evidence**: Multiple merge operations tracked in ASSIGNMENTS.md History

**Code**: `system/scripts/merge-queue.sh`

---

### Qt Runner (QA Model) `[IMPLEMENTED]`
**Description**: Quality assurance checks via Ollama-based QA model.

**Status**: Schema defined, runner operational, evidence tracking added

**Features**:
- QT job JSON schema
- Merge readiness checks
- Evidence directory tracking (docs/dev/evidence/QT/)
- Constrained to qa/ writes only

**Evidence**: `docs/dev/evidence/TASK_090/`, Qt job schema, `system/scripts/qt-runner.sh`

**Code**: `system/scripts/qt-runner.sh`

---

## Downstream Applications (External)

### Case Strength (Citation Layer) `[SPECULATIVE]`
**Description**: Scoring system for legal/research citations using attestation chains.

**Concept**: Each citation claim is backed by a PolicyRecord attestation, forming a verifiable chain from claim → source → evidence. Case Strength aggregates attestation confidence scores to produce an overall citation strength metric.

**Use Case**: Legal research, academic citations, fact-checking

**Status**: Speculative concept discussed in planning sessions, no spec or implementation

**Dependencies**:
- Attestation chain construction (time ribbon)
- Signature verification (Phase 3)
- Scoring heuristics (undefined)

**Open Questions**:
- How to model citation claims as tool requests?
- What policy rules apply to citation verification?
- How to aggregate attestation confidence across chains?

---

### Time Ribbon Rendering `[DESIGN_ONLY]`
**Description**: Visual representation of attestation chains with temporal ordering.

**Status**: Design sketched, no implementation

**Features** (proposed):
- Parse decision-chain.jsonl
- Construct DAG from prev_record_hash links
- Render temporal sequence
- Highlight integrity failures (hash mismatches)

**Evidence**: `docs/dev/evidence/TASK_098/`, test fixtures for time ribbon validation

**Code**: `scripts/attest/time_ribbon.py` (scaffolding exists), `scripts/attest/integrated_e2e.py`

**Related**: TASK_098 (time ribbon render script)

---

### Audit Bundle Export `[SPECULATIVE]`
**Description**: Package decision chains and evidence for external audit.

**Concept**: Generate tamper-evident archive containing:
- decision-chain.jsonl
- Capability registry snapshot
- Evidence bundles
- Signature verification keys
- Replay scripts

**Use Case**: Compliance audits, security reviews, forensic analysis

**Status**: Speculative, no design or implementation

**Open Questions**:
- Archive format (tar.gz, zip, custom)?
- How to handle large decision chains (GB scale)?
- Verification procedure for auditors unfamiliar with system?

---

### Distributed Replay Network `[SPECULATIVE]`
**Description**: Multi-node replay verification for consensus.

**Concept**: Multiple independent nodes replay policy decisions and vote on correctness. Detects platform-specific non-determinism or malicious tampering.

**Use Case**: High-assurance environments, Byzantine fault tolerance

**Status**: Speculative, no design or implementation

**Open Questions**:
- Consensus protocol (majority vote, quorum)?
- How to handle legitimate platform differences (path separators, etc.)?
- Performance implications (replay is CPU-bound)?

---

## Integration Points (MCP / API)

### MCP Protocol Integration `[IMPLEMENTED]`
**Description**: Governance layer exposed via Model Context Protocol.

**Status**: Operational, Claude Desktop integration tested

**Features**:
- Tool registration via MCP manifest
- Request/response JSON-RPC format
- Intent extraction from tool calls
- Error propagation (DENY → MCP error response)

**Evidence**: MCP smoke tests, operational deployment

**Code**: MCP server implementation (language/framework TBD based on actual codebase)

---

### Standalone CLI `[NEEDS_VALIDATION]`
**Description**: Command-line interface for policy evaluation without MCP.

**Status**: `scripts/policy-eval.py` serves as CLI, needs formalization

**Features** (current):
- Accept request JSON from file or stdin
- Output PolicyRecord JSON to stdout
- Exit code 0 for ALLOW, 1 for DENY

**Missing**:
- Argument parsing (--help, --version)
- Chain management (append to decision-chain.jsonl)
- Signature generation (Phase 3)

---

### HTTP API Wrapper `[SPECULATIVE]`
**Description**: REST API for policy evaluation and replay.

**Concept**: HTTP server wrapping policy-eval.py with endpoints:
- POST /evaluate (accept request, return record)
- POST /replay (accept record, verify)
- GET /chain (fetch decision chain segments)

**Use Case**: Remote policy evaluation, web-based auditing

**Status**: Speculative, no design or implementation

**Open Questions**:
- Authentication/authorization model?
- Rate limiting for abuse prevention?
- Deployment model (single-tenant, multi-tenant)?

---

## Test Infrastructure

### Reason Code Coverage Validator `[IMPLEMENTED]`
**Description**: Verify all reason codes have test harnesses.

**Status**: Implemented, evidence recorded

**Features**:
- Scan policy-eval.py for RC-* constants
- Cross-reference with test harnesses
- Report uncovered reason codes

**Evidence**: `docs/dev/evidence/TASK_067/`

**Code**: `scripts/verify-reason-code-coverage.py` (or inline in test harness)

---

### Integrated E2E Determinism Tests `[IN_PROGRESS]`
**Description**: End-to-end tests verifying determinism across all subsystems.

**Status**: Partial implementation (TASK_096-099)

**Features**:
- Records aggregate hash determinism (TASK_096) `[IMPLEMENTED]`
- Manifest build stability (TASK_097) `[IMPLEMENTED]`
- Time ribbon render script (TASK_098) `[IMPLEMENTED]`
- Signing outputs containment (TASK_099) `[IMPLEMENTED]`

**Evidence**: `docs/dev/evidence/TASK_096/`, `TASK_097/`, `TASK_098/`, `TASK_099/`

**Tasks**: TASK_100-107 (generated specs for Phase 3 work)

---

## Open Questions / Needs Placement

### Multi-Actor Scenarios
- How to handle concurrent requests from different actors?
- Should PolicyRecords include actor-specific allowlists?
- How to enforce actor-level access control?

**Status**: Not addressed in Phase 2/3 design

---

### Policy Evolution & Versioning
- How to version policy rules over time?
- Can old decisions be re-evaluated under new policies?
- How to handle breaking changes in capability registry?

**Status**: Not addressed in Phase 2/3 design

---

### Performance Benchmarks
- What is the throughput limit for policy evaluation?
- Latency targets for interactive tools?
- Decision chain size limits (GB scale chains)?

**Status**: No benchmarks or profiling data exists

---

### Cross-Language Implementations
- Can policy-eval.py logic be ported to Rust, Go, TypeScript?
- How to ensure determinism across language implementations?
- Reference implementation vs multi-language ecosystem?

**Status**: Python is reference implementation, no ports exist

---

## Contact & Contributions

Applications and integrations follow the Cecil-managed workflow. To propose a new application:
1. Create a seed entry in `docs/dev/task-seeds/SEED.md`
2. Run `scripts/task_scaffold.py` to generate task spec
3. Claim task via `system/scripts/queue-claim.sh`
4. Implement with evidence bundle
5. Submit for Cecil review/merge

See [RUNBOOK.md](RUNBOOK.md) for detailed contribution workflow.
