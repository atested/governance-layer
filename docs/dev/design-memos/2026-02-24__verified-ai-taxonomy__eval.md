# Evaluation Memo: Verified AI Taxonomy

**Date**: 2026-02-24
**Status**: [SPECULATIVE]
**Evaluator**: Cecil (governance operator)

---

## What It Is

The **Verified AI Taxonomy** is a component-based classification system for AI systems that can be justifiably trusted through verifiable constraints and records rather than trusting the model itself.

**Three orthogonal pillars** (O, E, P) applied **per capability surface**:
- **Observation (O0–O3)**: "What happened?" - Logging quality and completeness
- **Enforcement (E0–E3)**: "What cannot happen?" - Gating and bypass resistance
- **Provenance/Integrity (P0–P3)**: "Can we prove the record?" - Artifact binding and tamper evidence

**Coverage stamp format**: `FS O3 E2 P2 | Web O2 E1 P1 | Reasoning O1 E0 P0`

**Canonical phrase**: *"Verified ≠ correct"* - Operational/evidentiary verification, not truth certification.

**Verified AI Gates** (thresholds):
- **Minimal**: O2 + E1 + P1 (basic auditability)
- **Strong**: O3 + E2 + P2 (institutional admissibility)
- **Institutional**: O3 + E3 + P3 (adversarial environments)

---

## Problem It Solves (Failure Modes)

### Trust Crisis: Plausibility → Verification

**Core problem**: As AI outputs become more non-intuitive (complex reasoning, multi-step tool use, non-obvious failure modes), humans lose the ability to validate by plausibility checking ("does this sound right?").

**Traditional approach fails**:
- "Trust the model" → unjustifiable when outputs are non-intuitive
- "Responsible AI" marketing → no operational meaning
- Post-hoc auditing → can't reconstruct what actually happened

**Solution**: Shift trust from model credibility to process verification. Trust the proof, not the model.

### Specific Failure Modes Addressed

1. **Governance theater**: Systems claim "governance" but only log successes, allow silent bypasses, or use weak integrity boundaries
2. **Selective logging**: Only successful operations logged, failures/denials hidden
3. **Receipt theater**: Models fabricate provenance not backed by actual tool execution
4. **Hidden weak surfaces**: Strong logging on filesystem, no logging on web fetches, but output doesn't declare coverage
5. **Break-glass without audit**: Human overrides exist but aren't logged or propagated
6. **Non-resolvable artifacts**: Logs reference artifacts that can't be retrieved or verified
7. **Weak integrity boundaries**: Vague threat models, missing enumeration of trust assumptions
8. **Trust laundering**: Plausibility-based acceptance without checking if constraints were actually enforced

**Enabling value**: The taxonomy provides **justifiable trust** - reasons a third party can accept (scope, method, evidence, integrity, reconstruction) rather than raw plausibility.

---

## Fit with Governance Layer NOW

### Current State Assessment

The governance-layer likely qualifies as **Verified Minimal** on some surfaces, approaching **Strong** on filesystem operations, but **not Institutional** yet.

**Estimated current ratings** (requires verification):

| Surface | O | E | P | Notes |
|---|---|---|---|---|
| **Filesystem** | O2-O3 | E2 | P2 | Decision chains logged, policy gating enforced, hash-chained records |
| **Shell** | O1-O2 | E0 | P0 | Bash commands logged (via Claude Code), no policy enforcement, no artifact binding |
| **Web** | O0-O1 | E0 | P0 | No governance logging, no enforcement, no provenance |
| **Routing** | O1 | E0 | P0 | Task routing logged (ASSIGNMENTS.md), no enforcement, no integrity |
| **Reasoning** | O0 | E0 | P0 | Internal model reasoning not logged, not governed |

**Coverage stamp (estimated)**: `FS O2-O3 E2 P2 | Shell O1-O2 E0 P0 | Web O0 E0 P0 | Routing O1 E0 P0 | Reasoning O0 E0 P0`

**Gate qualification**: Likely **Verified Minimal** on filesystem surface (O2 + E1 + P1 threshold met), not yet **Strong** (O3 requirements incomplete).

### Gaps to Strong (O3 + E2 + P2)

**Observation (O → O3)**:
- ✅ **Structured event logs**: decision-chain.jsonl with correlation (request_hash)
- ✅ **Denials logged**: RC-* reason codes in policy decisions
- ⚠️ **Event before result**: Unclear if decision record is durably stored before tool execution returns
- ❌ **Completeness mechanism**: No persistent sequence numbers, signed heartbeats, or merkleized streams
- ❌ **LOGGING_FAILURE handling**: No explicit mechanism to detect or handle logging failures

**Enforcement (E → E2)**:
- ✅ **Policy gating**: policy-eval.py runs before tool execution
- ✅ **Structured denials**: RC-* reason codes enumerated
- ⚠️ **Break-glass detection**: No documented break-glass path, but manual file edits are possible bypass
- ❌ **UNGOVERNED propagation**: No mechanism to mark bypassed sessions and propagate marker

**Provenance/Integrity (P → P2)**:
- ✅ **Hash-chained records**: record_hash links decisions, prev_record_hash chains
- ✅ **Hashed artifacts**: normalized_args include canonical paths
- ⚠️ **Signed checkpoints**: Phase 3 signing adds signatures (TASK_100, TASK_106 merged), but not yet verified
- ❌ **Machine-readable Integrity Boundary**: No enumeration of writers, storage, crypto, threat model

### Reuse (Existing Primitives)

The taxonomy **builds on existing governance-layer primitives**:

**Observation**:
- decision-chain.jsonl (append-only log)
- request_hash (correlation ID)
- policy_reasons (structured denials)

**Enforcement**:
- policy-eval.py (gating before execution)
- RC-* reason codes (structured denials)
- governed_tool() wrappers (tool boundary)

**Provenance/Integrity**:
- record_hash (content hash)
- prev_record_hash (chain linking)
- signature field (Phase 3, in progress)
- cap_registry_hash (capability binding)

### Conflicts (None Identified)

No conflicts with existing governance-layer design. The taxonomy **provides a lens for assessment**, not new requirements that contradict current approach.

### Path to Strong (O3 + E2 + P2)

**To achieve Strong on filesystem surface**:

1. **Add completeness mechanism** (O3):
   - Option A: Persistent sequence numbers in decision records
   - Option B: Signed heartbeats with gap detection
   - Option C: Merkleized stream with provable ordering

2. **Add LOGGING_FAILURE handling** (O3):
   - Detect when decision-chain.jsonl write fails
   - Emit structured LOGGING_FAILURE event or halt execution

3. **Document break-glass policy** (E2):
   - Define explicit override path for operators
   - Require BREAK_GLASS event emission
   - Implement UNGOVERNED marker propagation

4. **Create Integrity Boundary document** (P2):
   - Enumerate writers (policy-eval.py, verify-chain.py, etc.)
   - Document storage (decision-chain.jsonl, GOV_RUNTIME_DIR)
   - Specify crypto (Ed25519 signing, SHA-256 hashing)
   - Define threat model (in-scope: tamper detection; out-of-scope: key compromise before detection)

5. **Add minimum tests** (O3, E2, P2):
   - Test: Simulate logging failure, verify LOGGING_FAILURE or halt
   - Test: Attempt bypass, verify UNGOVERNED marking
   - Test: Tamper with record, verify hash chain breaks
   - Test: Parse Integrity Boundary, validate enumeration

**Estimated effort**: Medium. Requires logging enhancements, documentation work, test additions. No fundamental architecture changes.

---

## Implementation Surface (Areas Touched)

If the Verified AI taxonomy were adopted as a formal assessment framework and governance-layer were to target Strong, the following areas would be touched:

### Documentation (Primary Surface)

1. **New document: VERIFIED_AI_ASSESSMENT.md**:
   - Per-surface coverage stamp for current state
   - Gap analysis (what's missing for each level)
   - Integrity Boundary enumeration (P2 requirement)
   - Minimum test requirements and current pass/fail status

2. **GOVERNANCE_OVERVIEW.md enhancement**:
   - Add "Verified AI Classification" section
   - Position governance-layer within taxonomy
   - State current gate qualification (Minimal/Strong/Institutional)

3. **RUNBOOK.md enhancement**:
   - Document break-glass policy for operators
   - Add LOGGING_FAILURE troubleshooting
   - Add UNGOVERNED marker propagation protocol

4. **AGENT_CONTRACT.md enhancement**:
   - Add break-glass logging requirement
   - Add UNGOVERNED propagation requirement

### Code (Logging and Enforcement Enhancements)

5. **scripts/policy-eval.py**:
   - Add persistent sequence numbers to decision records
   - Add LOGGING_FAILURE detection and emission
   - Add event-before-result enforcement (flush before return)

6. **mcp/server.py**:
   - Add LOGGING_FAILURE handling in governed tools
   - Add break-glass detection hooks (if applicable)

7. **New: scripts/verify-integrity-boundary.py**:
   - Validate Integrity Boundary machine-readable format
   - Check enumeration completeness (writers, storage, crypto, threat model)

### Tests (Minimum Requirements for O3, E2, P2)

8. **New: tests/test_logging_completeness.sh**:
   - Simulate logging failure (fill disk, break permissions)
   - Verify LOGGING_FAILURE event or halt behavior

9. **New: tests/test_break_glass.sh**:
   - Simulate operator bypass (manual file edit)
   - Verify UNGOVERNED marking (if detectable)

10. **New: tests/test_integrity_boundary.sh**:
    - Parse VERIFIED_AI_ASSESSMENT.md Integrity Boundary section
    - Validate required enumerations present

11. **Enhancement: tests/test_verify_signatures.sh**:
    - Add tamper detection test (modify record, verify hash chain breaks)

### Reporting (Coverage Stamp Generation)

12. **New: system/scripts/generate-coverage-stamp.sh**:
    - Assess current O/E/P levels per surface
    - Generate coverage stamp (e.g., `FS O3 E2 P2 | Shell O1 E0 P0`)
    - Output machine-readable format for downstream systems

---

## Risks and Open Questions

### Risks

1. **Gaming and self-certification**: Systems could claim higher levels without meeting requirements (selective logging, weak boundaries, hallucinated artifacts).

   **Mitigation**: Require minimum tests to claim levels. Evidence packs must accompany claimed ratings. Independent verification for Institutional gate.

2. **Overhead vs value tradeoff**: Achieving O3 + E2 + P2 requires significant engineering (completeness mechanisms, break-glass detection, key custody).

   **Mitigation**: Target Strong only on high-stakes surfaces. Allow honest lower ratings on other surfaces. Coverage stamps make tradeoffs explicit.

3. **Abstraction complexity**: Three pillars × 4 levels × N surfaces = complex classification space. Risk of confusion or misapplication.

   **Mitigation**: Provide worked examples. Start with single-surface assessments (filesystem first). Document decision criteria for each level clearly.

4. **"Verified ≠ correct" misunderstanding**: Risk that users interpret "Verified" as "guaranteed correct" rather than "operationally auditable."

   **Mitigation**: Explicit disclaimer in all materials. Separate CV overlay for claim substantiation. Emphasize admissibility vs truth.

5. **Scope creep**: Attempting to govern reasoning (E for thoughts) or achieve E3 cross-tool invariants could create excessive overhead.

   **Mitigation**: Accept O0 E0 P0 for reasoning surface. Define E3 narrowly (specific cross-tool checks, not "govern all planning"). Honest coverage stamps prevent hidden gaps.

6. **Break-glass detection limits**: Manual file edits, environment variable changes, and other bypasses may be undetectable without OS-level hooks.

   **Mitigation**: Document threat model clearly. Mark filesystem surface as E2 with "break-glass via manual edit undetected" caveat. Consider E1 rating if detection is impossible.

### Open Questions

1. **What is governance-layer's exact current rating?**
   - Does decision-chain.jsonl implement "event before result"?
   - Are denials and failures fully captured?
   - Is there a completeness mechanism (sequence numbers, heartbeats)?

2. **What completeness mechanism is most appropriate for O3?**
   - Persistent sequence numbers: Simple, but requires gap detection logic
   - Signed heartbeats: Detects crashes, but adds signing overhead
   - Merkleized streams: Strong ordering proof, but complex implementation

3. **How should break-glass be handled?**
   - Should governance-layer provide explicit override API?
   - Or document that manual file edits are undetectable bypass?
   - How should UNGOVERNED propagate in git workflow?

4. **What strength Integrity Boundary is needed for Institutional?**
   - Hardware security modules for key custody?
   - External anchoring (blockchain, trusted timestamping)?
   - Air-gapped verification nodes?

5. **Should CV overlay be mandatory?**
   - Filesystem surface: CV not needed (no claims, just operations)
   - Reasoning surface: CV2 or CV3 mandatory for high-stakes domains?

6. **How should coverage stamps be reported?**
   - In every decision record?
   - In session metadata?
   - In external certification document?

7. **What evidence pack format proves ratings?**
   - Test results (O3, E2, P2 minimum tests passing)
   - Integrity Boundary document (P2 requirement)
   - Independent audit report?

8. **How does this interact with MCP/Claude Code?**
   - Should Claude Code UI display coverage stamps?
   - Should MCP servers declare their O/E/P ratings?
   - Should governance-layer provide rating API?

---

## Go / No-Go Criteria

### Go Criteria (Conditions for Adopting Taxonomy as Formal Assessment Framework)

The Verified AI taxonomy should be formally adopted if:

1. **Institutional admissibility required**: Outputs must be justifiable to third parties (auditors, regulators, legal review)
2. **Multiple surfaces governed**: Filesystem, shell, web, routing span different risk/maturity levels requiring differentiated reporting
3. **Gaming risk present**: Need to distinguish governance theater from real verification
4. **Adversarial environment**: Outputs may face hostile scrutiny requiring tamper evidence
5. **Long-term trust shift**: Reliance on AI outputs growing, plausibility checking insufficient

**Threshold**: If 3+ conditions met, taxonomy provides clear value for assessment and roadmap planning.

### No-Go Criteria (Conditions for Rejection)

The taxonomy should NOT be adopted if:

1. **Single surface, low stakes**: Only filesystem operations, internal use only, no audit requirements
2. **No adversarial pressure**: Outputs accepted on plausibility, no third-party scrutiny
3. **Overhead unjustified**: Cost of O3/E2/P2 exceeds value of stronger trust
4. **Classification overkill**: Simple "logged vs unlogged" distinction sufficient
5. **Premature formalization**: Taxonomy designed for mature systems, but governance-layer still evolving rapidly

**Current Assessment**:

**Pro adoption**:
- Governance-layer operates in institutional context (AI-mediated code generation)
- Multiple surfaces exist with different maturity (filesystem strong, shell/web weak)
- Long-term trust shift underway (AI outputs non-intuitive)

**Con adoption**:
- Taxonomy is complex (3 pillars × 4 levels × N surfaces)
- Current state unclear (needs assessment to determine exact ratings)
- Institutional gate not yet required (internal use, not external audit)

**Recommendation**: **Adopt taxonomy as assessment framework** with following approach:

1. **Phase 1**: Document current state
   - Create VERIFIED_AI_ASSESSMENT.md with per-surface ratings
   - Acknowledge gaps (O2 not O3, no Integrity Boundary, etc.)
   - Use honest coverage stamps (don't overclaim)

2. **Phase 2**: Target Strong on filesystem surface
   - Add completeness mechanism (persistent sequence numbers)
   - Add LOGGING_FAILURE handling
   - Document Integrity Boundary (P2 requirement)
   - Add minimum tests (O3, E2, P2)

3. **Phase 3**: Expand to other surfaces selectively
   - Shell: Target O2 E1 P1 (Minimal)
   - Web: Accept O1 E0 P0 (documented as ungoverned)
   - Reasoning: Accept O0 E0 P0 (out of scope)

4. **Phase 4**: Re-evaluate Institutional need
   - If external audit required → target O3 E3 P3
   - If internal use only → Strong sufficient

**Decision gate**: After Phase 1 assessment, decide whether Strong is justified by cost/benefit. If overhead exceeds value, stop at Minimal with honest coverage stamps.

---

## Status and Next Steps

**Status**: [SPECULATIVE]

The Verified AI taxonomy is conceptually coherent and provides a useful lens for assessing governance-layer's current state and roadmap. However, it has not yet been applied to produce actual ratings or guide implementation priorities.

**Proposed Next Steps** (if taxonomy adopted):

1. **Create VERIFIED_AI_ASSESSMENT.md** [Phase 1]
   - Assess current O/E/P levels per surface
   - Generate coverage stamp
   - Document gaps to Strong
   - Create Integrity Boundary enumeration (even if incomplete)

2. **Add taxonomy overview to GOVERNANCE_OVERVIEW.md** [Phase 1]
   - Explain Verified AI concept
   - Position governance-layer within taxonomy
   - State current coverage stamp
   - Link to VERIFIED_AI_ASSESSMENT.md for details

3. **Enhance logging for O3** [Phase 2]
   - Add persistent sequence numbers to decision records
   - Implement "event before result" enforcement
   - Add LOGGING_FAILURE detection and handling
   - Add gap detection mechanism

4. **Document break-glass policy** [Phase 2]
   - Define operator override path (or document undetectable bypass)
   - Require BREAK_GLASS event if detectable
   - Design UNGOVERNED marker propagation

5. **Complete Integrity Boundary** [Phase 2]
   - Enumerate writers, storage, crypto, anchoring, completeness mechanism
   - Define threat model (in-scope vs out-of-scope)
   - Make machine-readable for verification

6. **Add minimum tests** [Phase 2]
   - Test logging completeness (simulate failure)
   - Test break-glass detection (simulate bypass)
   - Test tamper detection (modify record)
   - Test Integrity Boundary parsing

7. **Generate coverage stamp reporting** [Phase 3]
   - Create script to assess and report current ratings
   - Add coverage stamp to session outputs
   - Consider MCP server rating declaration

**Blockers**: None technical. Adoption decision required: Is institutional admissibility needed? Is Strong worth the overhead?

**Risks to Monitor**:
- Gaming (self-certification without evidence)
- Overhead (O3 + E2 + P2 engineering cost)
- Complexity (three pillars × four levels × N surfaces)
- Misunderstanding ("Verified ≠ correct")
- Scope creep (attempting E3 or O3 on reasoning surface)

**Decision Point**: After Phase 1 assessment (document current state), evaluate cost/benefit of Phase 2 (target Strong). If Strong is not justified, maintain Minimal with honest coverage stamps.

---

## Assessment: Governance-Layer vs Verified AI Taxonomy

**Likely current state** (requires verification):

| Surface | O | E | P | Gate Qualification |
|---|---|---|---|---|
| Filesystem | O2-O3 | E2 | P2 | **Minimal** (O2+E1+P1), approaching **Strong** |
| Shell | O1-O2 | E0 | P0 | Below Minimal |
| Web | O0-O1 | E0 | P0 | Below Minimal |
| Routing | O1 | E0 | P0 | Below Minimal |
| Reasoning | O0 | E0 | P0 | Below Minimal (expected) |

**Overall coverage stamp (estimated)**:
```
FS O2-O3 E2 P2 | Shell O1-O2 E0 P0 | Web O0-O1 E0 P0 | Routing O1 E0 P0 | Reasoning O0 E0 P0
```

**Path to Strong (FS surface only)**:
- Close O gaps: Add sequence numbers, LOGGING_FAILURE, event-before-result
- Close P gaps: Complete Integrity Boundary, add minimum tests
- E2 maintained: Existing policy gating + governed tools sufficient

**Estimated effort**: 2-3 weeks for Phase 1 assessment + Phase 2 enhancements to reach Strong on filesystem surface.

**Recommendation**: Proceed with Phase 1 (assessment) to establish baseline. Defer Phase 2 (Strong) until institutional admissibility requirement confirmed.
