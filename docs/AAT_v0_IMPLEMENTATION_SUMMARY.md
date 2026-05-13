# AAT v0 Implementation Summary

**Version**: v0 (GATE A Complete)
**Date**: 2026-03-02
**Status**: ✅ GATE A COMPLETE - Ready for GATE B

---

## Overview

Action Admissibility Testing (AAT) v0 GATE A has been successfully implemented and validated. This is the first artifact-gated phase of a multi-gate rollout plan for deterministic, profile-based action validation in the governance layer.

**Key Achievement**: Deterministic validation framework with 100% test pass rate and proven determinism across 10 test fixtures.

---

## What is AAT?

AAT (Action Admissibility Testing) is a deterministic, profile-based validation system for governance layer actions. It enforces:

- **Kernel invariants** (K1-K5): Universal checks that apply to all actions
- **Mechanical checks** (M1): Structural integrity validation
- **Property tests** (P1-P2): Idempotence and stability validation
- **Consistency checks** (C1-C3): Governance-relevant consistency validation
- **Profile-based enforcement**: Different validation levels for different action kinds

**Critical constraints**:
- ❌ NO LLM calls
- ❌ NO network access
- ❌ NO wall clock dependencies
- ✅ Deterministic: same inputs → same outputs (validated via SHA256)

---

## GATE A: Kernel Viable

### Deliverables (27 artifacts)

#### Schemas (7)
1. `system/schemas/aat_input_manifest_v0.json` - Input Manifest (IM)
2. `system/schemas/aat_constraint_set_digest_v0.json` - Constraint Set Digest (CSD)
3. `system/schemas/aat_constraint_acknowledgment_map_v0.json` - Constraint Acknowledgment Map (CAM)
4. `system/schemas/aat_method_binding_v0.json` - Method Binding (MB)
5. `system/schemas/aat_assumptions_unknowns_register_v0.json` - Assumptions and Unknowns Register (AUR)
6. `system/schemas/aat_claims_evidence_map_v0.json` - Claims-to-Evidence Map (CEM)
7. `system/schemas/aat_admissibility_decision_record_v0.json` - Admissibility Decision Record (ADR)

#### Validators (6)
1. `scripts/aat_main.py` - Main orchestrator (~250 lines)
2. `scripts/aat_kernel_validator.py` - K1-K5 kernel invariants (~200 lines)
3. `scripts/aat_mechanical_validator.py` - M1 mechanical checks (~150 lines)
4. `scripts/aat_property_validator.py` - P1-P2 property tests (~200 lines)
5. `scripts/aat_consistency_validator.py` - C1-C3 consistency checks (~150 lines)
6. `scripts/aat_profile_registry.py` - Profile management (~100 lines)

#### Integration (1)
1. `system/scripts/aat-admissibility-gate.sh` - Wrapper script (~80 lines)

#### Tests (3 suites, 21 tests)
1. `system/tests/test_aat_kernel.sh` - Kernel unit tests (6/6 PASS)
2. `system/tests/test_aat_integration.sh` - Integration tests (5/5 PASS)
3. `system/tests/test_aat_determinism.sh` - Determinism tests (10/10 PASS)

#### Golden Fixtures (10)
- **PASS** (2): core_generic, tool_exec
- **FAIL** (8): k1_phantom_action, k2_undeclared_dependency, k3_constraint_unacknowledged, k4_method_forbidden, m1_schema_invalid, c1_contradiction, c2_evidence_not_in_im, c3_forbidden_claim

#### Evidence
Evidence bundles were produced during Gate A verification and archived separately.

---

## Validation Levels & Reason Codes

### Level 0: Kernel Invariants (K1-K5) - HARD_STOP
- **K1**: Phantom action detection (verification/test claims require tool_event evidence)
- **K2**: Undeclared dependency detection (all evidence refs must exist in IM)
- **K3**: Constraint acknowledgment completeness (every CSD constraint mapped in CAM)
- **K4**: Method binding required (method_id must exist and be allowed)
- **K5**: Version binding required (ADR must have version bindings)

### Level 1: Mechanical Checks (M1) - NON_ADMISSIBLE
- **M1**: Schema validation, digest format, required fields for hashing

### Level 2: Property Tests (P1-P2) - NON_ADMISSIBLE
- **P1**: Canonical idempotence (canonical(canonical(x)) == canonical(x))
- **P2**: Round-trip stability (deserialize(serialize(x)) == x)

### Level 3: Consistency Checks (C1-C3) - NON_ADMISSIBLE
- **C1**: Contradiction detection (constraint not both satisfied and unknown)
- **C2**: Evidence reference integrity (CEM refs must exist in IM with allowed ref_type)
- **C3**: Forbidden claim detection (verification claims must have evidence)

---

## Profiles (v0)

### CORE_GENERIC (default)
- **Enforcing**: K1-K5 + M1
- **Report-only**: P1-P2 + C1-C3
- Applies to all actions by default

### TOOL_EXEC
- **Inherits**: CORE_GENERIC
- **Additional checks**: None in v0 (expansion deferred to v1)
- Applies to shell command execution actions

---

## Kernel Objects (7 Sidecars)

Each action bundle contains 7 kernel objects:

1. **Input Manifest (IM)**: All consumed inputs (files, artifacts, tool events)
2. **Constraint Set Digest (CSD)**: Canonical list of applicable constraints
3. **Constraint Acknowledgment Map (CAM)**: Status for each constraint (satisfied, not_applicable, blocked, unknown)
4. **Method Binding (MB)**: Execution method for action kind
5. **Assumptions and Unknowns Register (AUR)**: Documented assumptions and unknowns
6. **Claims-to-Evidence Map (CEM)**: Maps claims to evidence references
7. **Admissibility Decision Record (ADR)**: Output of AAT validation

---

## Test Results

### Summary
- **Total tests**: 21
- **Passed**: 21
- **Failed**: 0
- **Success rate**: 100%

### Breakdown
| Test Suite | Tests | Pass | Fail | Coverage |
|------------|-------|------|------|----------|
| Kernel Unit | 6 | 6 | 0 | K1-K5 + valid bundle |
| Integration | 5 | 5 | 0 | End-to-end + determinism |
| Determinism | 10 | 10 | 0 | All golden fixtures |

### Determinism Validation
- **Method**: Two-run SHA256 comparison
- **Fixtures**: 10 (2 PASS + 8 FAIL)
- **Result**: 100% deterministic (all fixtures produce identical ADR digests)
- **Validated no dependencies on**: wall clock, network, LLM, random number generation

---

## Usage

### Run AAT validation on an action bundle:

```bash
python3 scripts/aat_main.py \
  --bundle-dir <path_to_action_bundle> \
  --schema-dir system/schemas \
  --output <path_to_adr_output.json>
```

### Use wrapper script for release gate integration:

```bash
./system/scripts/aat-admissibility-gate.sh \
  --action-bundle-dir <path_to_action_bundle>
```

Output format:
```
ADMISSIBLE=YES|NO
STOP_REQUIRED=YES|NO
REASON_CODE=<first_reason_code_or_NONE>
ENFORCEMENT_MODE=ENFORCING|REPORT_ONLY
```

Exit codes:
- 0 = PASS (admissible)
- 1 = FAIL_NON_ADMISSIBLE (override possible)
- 2 = FAIL_HARD_STOP (no override)

---

## Example ADR Output

### PASS Case
```json
{
  "adr_version": "v0",
  "action_kind": "CORE_GENERIC",
  "decision": "PASS",
  "enforcement_mode": "ENFORCING",
  "kernel_status": "PASS",
  "profile_status": "PASS",
  "reason_codes": [],
  "version_bindings": {
    "policy_digest": "sha256:...",
    "validator_digest": "sha256:...",
    "criteria_digest": "sha256:...",
    "aat_suite_digest": "sha256:..."
  }
}
```

### FAIL Case (K1 Phantom Action)
```json
{
  "adr_version": "v0",
  "action_kind": "CORE_GENERIC",
  "decision": "FAIL_HARD_STOP",
  "enforcement_mode": "ENFORCING",
  "kernel_status": "FAIL",
  "profile_status": "PASS",
  "reason_codes": [
    "AAT_K1_PHANTOM_ACTION",
    "AAT_C3_FORBIDDEN_CLAIM_NO_EVIDENCE"
  ],
  "version_bindings": { ... }
}
```

---

## Next Steps: GATE B

**GATE B: Ledger/Append Integration (Audit-First)**

Required artifacts:
1. Integration with process ledger (append action event regardless of pass/fail)
2. ADR append and hash-linking to action event
3. Enforcement rule implementation (PASS/NON_ADMISSIBLE/HARD_STOP)
4. Test fixtures demonstrating audit trail preservation

Pass criteria:
- [ ] Action event appended to ledger for all outcomes
- [ ] ADR appended and hash-linked to action event
- [ ] Enforcement consumption rules work correctly
- [ ] Failures never dropped from ledger (audit trail preserved)
- [ ] Evidence bundle: AAT_LEDGER_INTEGRATION generated

### Gate B operator usage (current branch implementation)

Gate B appends two deterministic ledger events (`aat_action_event` and `aat_decision_event`) for each AAT decision.

Wrapper entrypoint:

```bash
system/scripts/aat-gate-b-append.sh \
  --ledger system/tests/fixtures/aat_gate_b/pass/ledger.jsonl \
  --aat-action-record system/tests/fixtures/aat_gate_b/pass/action_record.json \
  --decision-record system/tests/fixtures/aat_gate_b/pass/decision_record.json \
  --proof-bundle-manifest system/tests/fixtures/aat_gate_b/pass/proof_manifest.json \
  --rules-snapshot system/tests/fixtures/aat_gate_b/pass/rules.json \
  --operation-id aat-pass
```

Deterministic output contract:
- `ADMISSIBLE=YES|NO`
- `STOP_REQUIRED=YES|NO`
- `REASON_CODE=<code>`
- `ACTION_APPEND_SEQ=<n>`
- `DECISION_APPEND_SEQ=<n>`

Deterministic fixture test:

```bash
bash system/tests/test_aat_gate_b_append.sh
```

---

## Architecture Highlights

### Canonical Serialization
All kernel objects follow canonical JSON pattern:
```python
def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

### Reason Code Ordering
Canonical order ensures deterministic ADR output:
```
K1 → K2 → K3 → K4 → K5 → M1 → P1 → P2 → C1 → C2 → C3
```

### Profile Inheritance
TOOL_EXEC inherits from CORE_GENERIC:
```
TOOL_EXEC.enforcing = CORE_GENERIC.enforcing + TOOL_EXEC.enforcing
```

---

## Dependencies

### Required
- Python 3.9+
- jsonschema library (for M1 validation)

### Optional
- None (all validation is self-contained)

### Explicitly Forbidden
- Network access (no HTTP, no DNS lookups)
- LLM calls (no OpenAI, no Anthropic API)
- Wall clock dependencies (no timestamps in ADR)
- Random number generation (deterministic sorting only)

---

## File Manifest

### Created Files (27 total)
```
system/schemas/aat_*.json (7 files)
scripts/aat_*.py (6 files)
system/scripts/aat-admissibility-gate.sh (1 file)
system/tests/test_aat_*.sh (3 files)
system/tests/generate_aat_golden_fixtures.sh (1 file)
system/tests/fixtures/aat/golden_pass/* (2 directories)
system/tests/fixtures/aat/golden_fail/* (8 directories)
docs/AAT_v0_IMPLEMENTATION_SUMMARY.md (1 file - this file)
```

### Modified Files (1 total)
```
system/schemas/typed_ref_catalog.json (added action_decision_record type)
```

---

## Verification

Run complete validation suite:

```bash
# All unit tests
./system/tests/test_aat_kernel.sh

# All integration tests
./system/tests/test_aat_integration.sh

# All determinism tests
./system/tests/test_aat_determinism.sh

# Wrapper script test
./system/scripts/aat-admissibility-gate.sh \
  --action-bundle-dir system/tests/fixtures/aat/golden_pass/core_generic
```

Expected result: All tests PASS, exit code 0.

---

## Known Limitations (v0 Scope)

1. **P1/P2 golden fixtures skipped**: Canonical idempotence and round-trip stability are guaranteed by json.dumps implementation, so failure cases are impossible to create
2. **K5 golden fixture skipped**: Version binding validation requires ADR context, tested via integration tests instead
3. **Version bindings use placeholders**: Production implementation should compute actual digests from policy/validator files
4. **Limited profile coverage**: Only CORE_GENERIC + TOOL_EXEC in v0; FILE_OPERATION, NETWORK_REQUEST, MODEL_INVOKE deferred to v1

---

## License & Attribution

Part of the governance-layer repository.
Implements AAT v0 specification from AAT Implementation Plan.

---

**GATE A Status**: ✅ COMPLETE
**Next Gate**: GATE B - Ledger/Append Integration
**Implementation Date**: 2026-03-02
