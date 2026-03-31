# Governance Layer Planning

Last updated: 2026-02-16 (America/New_York)

## Mission
Build a governance layer that makes AI mediated operations defensible through:
1. Deterministic policy evaluation
2. Tamper evident evidence chains
3. Forensic preservation on integrity failure
4. Clear separation of policy vs operations
5. Extensible "governance as a platform" capability model

This is not an OpenClaw specific project. OpenClaw may become a later stage application. The governance layer is designed to be reusable for any system that wants verifiable decision process integrity.

## Primary goals
1. Governance layer first
   1. Policy primitives and invariants
   2. Evidence records and verification
   3. Integration surfaces (MCP broker)
2. Cecil second
   1. Cecil is a test pilot engineer: generates, runs, verifies, and interprets execution evidence
   2. Cecil is not the source of truth; the governance repo is

## Current architecture
### Core objects
1. Intent record
   1. Normalized args
   2. Capability
   3. Goal, constraints, expected outputs
2. Decision record v0.1
   1. Policy inputs and decision
   2. Policy reasons (coded, structured)
   3. Content redaction by hash
   4. record_hash over canonical JSON
3. Decision chain
   1. JSONL chain with prev_record_hash linkage
   2. Chain verifier detects tampering
4. Quarantine rotation
   1. On chain verify failure, chain is moved to runtime quarantine with a reason file
   2. System continues with a fresh chain after quarantine rotation

### Evidence storage
1. Repo evidence (versioned)
   1. docs, scripts, tests, reports in LOGS/report-*.md
2. Runtime evidence (not in git)
   1. /Volumes/SSD/archive/gov/runtime/LOGS/
   2. decision-chain.jsonl
   3. records/ and intents/
   4. quarantine/ for broken chains + reasons

### Integration surface
MCP broker provides governed tools with a common wrapper:
1. verify chain
2. append decision record
3. verify chain
4. enforce decision
5. quarantine on integrity failure

## Implemented capabilities
1. FS_WRITE
   1. Governed write with allowlist boundary
   2. Decision records and chain logging
2. FS_LIST
   1. Governed directory listing (names and types only)
3. FS_READ
   1. Governed file read with strict byte caps, content hash, and safe encoding

All above are implemented through a single governed tool wrapper and a capability registry.

## Capability registry doctrine
The capability registry is the authoritative spec for:
1. Allowlist base paths
2. Deny rules (hidden paths, traversal)
3. Required args and normalization
4. Default and hard caps
5. Phase restrictions (for example include_hidden not allowed)

The system must converge toward: registry as single source of truth, not advisory configuration.

## Process and division of labor
### Greg
1. Owns direction and acceptance criteria
2. Runs external integrations when needed (GitHub, OpenClaw later)
3. Reviews key security posture decisions

### ChatGPT (organizer)
1. Proposes increments and acceptance tests
2. Ensures design stays aligned with invariants
3. Produces single Cecil ready execution blocks

### Cecil (executor and test pilot engineer)
1. Performs file operations and scripted changes
2. Runs test suites and produces reports
3. Commits with atomic increments and pushes
4. Pastes back verification outputs for audit

## Repo hygiene rules
1. One increment = one atomic commit
   1. Include report in same commit
2. Every increment must:
   1. Update tests
   2. Run tests
   3. Produce a LOGS report
   4. Preserve runtime evidence outside git
3. Fail closed always
   1. Chain verify failure must block appends and preserve evidence via quarantine rotation

## Roadmap
### Phase 2 immediate objectives
1. Bind policy decisions to the capability registry version
   1. Emit cap_registry_hash in decision records
   2. Verifiers and tests enforce it
2. Unify policy evaluator and runtime wrapper on the same registry source
   1. policy-eval must load capability-registry.json directly
3. Strengthen verification coverage
   1. Verify chain pre and post append (already done)
   2. Verify record hash (already done)
   3. Add regression tests for precedence ordering and dedup rules

### Phase 3 objectives
1. Attribution via signatures
   1. Ed25519 signing for decision records
   2. Key management in runtime, not git
2. Reference client
   1. Minimal CLI client for stdio MCP
   2. Demonstrates external integration without OpenClaw

### Phase 4 objectives
1. External application candidate
   1. Evaluate OpenClaw integration after robustness is proven internally
2. Expand capability set as needed
   1. FS_MOVE, FS_DELETE (high risk)
   2. EXEC with strict allowlist and sandboxing (very high risk)

## Current status
Latest known milestone:
1. MCP governed tool wrapper is capability spec driven (args and caps)
2. FS_WRITE, FS_LIST, FS_READ are implemented and covered by MCP smoke tests
3. Chain verification is fail closed with quarantine rotation
4. Tests passing at last verification checkpoint

