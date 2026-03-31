# Phase 1 Schema Package — Residual Discretion Doctrine v1

**Status**: [DRAFT] — review artifact, not yet canonical
**Date**: 2026-03-08 (revised 2026-03-10)
**Author**: Cecil (governance operator), directed by Greg (product owner)
**Implements**: Phase 0 of Residual Discretion Doctrine v1 Implementation Plan — schema contract governing Phase 1 (Pass Extension) and all subsequent phases

---

## 1. IQ-1 RESOLUTION: WHERE UNDECIDED STARTS

### Audit Summary

The policy evaluator (`scripts/policy-eval.py`) was audited for every DENY path. Each was classified as either a **genuine policy violation** (rules explicitly say no) or **deterministic insufficiency** (evaluator lacks rules to decide).

**Genuine violations (stay DENY)**: RC_UNKNOWN_TOOL, RC_MISSING_INTENT_FIELDS, RC_PATH_TRAVERSAL, RC_HIDDEN_PATH, RC_PATH_DISALLOWED, RC_OVERWRITE_DISALLOWED, RC_EXECUTABLE_DISALLOWED, RC_RECURSIVE_DISALLOWED, RC_CROSS_ROOT_DISALLOWED, RC_INCLUDE_HIDDEN_DISALLOWED, REASON_TARGET_IS_HOT_FILE, REASON_IS_EXECUTABLE, RC_MAX_BYTES_EXCEEDED.

**Deterministic insufficiency candidates (UNDECIDED)**:
- **REASON_DEST_EXISTS** (FS_COPY): Destination exists, overwrite not requested. No policy rule governs this disposition. The evaluator is forced into DENY, but the honest answer is "I lack a rule for this case."
- **Coverage stamp edge cases** (PARTIAL, VERSION_UNSUPPORTED): Cryptographic evidence is ambiguous. Not clearly valid, not clearly invalid.
- **RC_NOT_A_FILE / RC_NOT_A_DIRECTORY**: Filesystem state doesn't match expectation. Arguably closer to DENY (the state doesn't satisfy the rule), but symlink and special-file cases expose genuine gaps.

### Selected v1 Case Class

**REASON_DEST_EXISTS for FS_COPY** — destination exists, overwrite not requested.

Rationale:
- **Clear rule gap**: The policy is silent, not prohibitive. No rule says "deny when dest exists and overwrite not requested" — the evaluator just has no other option.
- **Architecturally clean**: Demonstrates the full Pass → Triage flow without exotic edge cases.
- **Natural concurrent findings**: Both a rule gap (policy should specify behavior) and possible input insufficiency (caller may have intended to specify overwrite) co-occur. This validates the concurrent-findings schema from day one.
- **Triage is meaningful**: Classification requires genuine diagnostic work — is this a structural deficiency, an input gap, or both?
- **Terminal Judgment not reached**: The correct disposition is deferral, not terminal judgment. This validates that Level 3 is narrow.

**Scope declaration**: The schemas, walkthrough, and IQ resolutions in this memo are scoped to the FS_COPY dest-exists-no-overwrite case class. Extension to other UNDECIDED case classes (coverage stamp ambiguity, filesystem state mismatches, future domains) requires a separate boundary-extension artifact. This memo does not foreclose those extensions.

### Boundary Principle

A DENY path becomes UNDECIDED when **the evaluator has no explicit rule for the condition**, not when the rule produces an undesired outcome. The v1 operational test: *could someone inspect the capability registry and point to the rule that produces this DENY?* If yes → genuine violation. If no → deterministic insufficiency → UNDECIDED.

This principle governs UNDECIDED expansion beyond the v1 case class, but it is not a complete enumeration of all conditions under which UNDECIDED is appropriate. Future case classes may involve prerequisites that cannot be verified deterministically, ambiguous mappings where the mapping choice changes the outcome, rule conflicts with undefined precedence, or missing meta-policy. None of these are foreclosed by this principle. Applying the principle to future cases requires deliberate boundary-extension work — it does not require that the case pass the registry-inspection test. The registry-inspection test is the v1 operational instantiation of the principle for rule-gap detection; it is not the principle itself.

---

## 2. CHAIN-LINKING SPECIFICATION

### Problem

The existing decision chain is a flat sequence of records, each linking to its predecessor via `prev_record_hash`. A three-level decision process (Pass → Triage → Terminal Judgment) produces multiple records for a single case. The chain must support:
- Grouping records by decision process
- Verifying that process records appear in correct architectural order
- One-way flow enforcement at the record level

### Design

Each record gains two new fields:

| Field | Type | Description |
|---|---|---|
| `record_type` | string enum | `"pass_decision"`, `"triage_decision"`, `"terminal_judgment"` |
| `process_id` | string | Groups records in the same decision process |

Process-level linking uses typed predecessor references (not generic back-references):
- Triage records contain `originating_pass_hash` — the `record_hash` of the Pass record that emitted UNDECIDED
- Terminal Judgment records contain `originating_triage_hash` — the `record_hash` of the Triage record

These are **forward-only** references: Pass does not reference Triage. One-way flow is structural.

### Process ID Generation

Deterministic: `process_id = sha256(session_id + ":" + request_id + ":process")`, truncated to first 16 hex characters.

This gives replay-compatible IDs — the same request in the same session always produces the same process ID. Note: if `GOV_SESSION_ID` is not set, `policy-eval.py` generates a per-invocation `sess-{uuid}`, making process_id unique per invocation (not replay-compatible). This is acceptable for v1 — the primary function of process_id is chain grouping, not replay. See IQ-7.

### Chain Verification Rules (extended)

Existing rules unchanged:
- Each record's `prev_record_hash` must match the preceding record's `record_hash`
- Signature must verify against `signing_key_id`

New rules:
- Records with the same `process_id` must appear in chain order: `pass_decision` before `triage_decision` before `terminal_judgment`
- A `triage_decision` record's `originating_pass_hash` must reference a `pass_decision` record with the same `process_id` and `policy_decision = "UNDECIDED"`
- A `terminal_judgment` record's `originating_triage_hash` must reference a `triage_decision` record with the same `process_id`
- No `pass_decision` record may reference a `triage_decision` or `terminal_judgment` record with the same `process_id` (one-way flow)

### Backward Compatibility

Existing records without `record_type` or `process_id` are implicitly `record_type: "pass_decision"` with no `process_id` (single-record process). Chain verification treats them as valid.

---

## 3. SCHEMAS

### 3.1 Extended Pass Decision Record

Changes from v0.1 (additive only):

```json
{
  "record_version": "0.2",
  "record_type": "pass_decision",
  "process_id": "<deterministic hash, 16 hex chars>",

  "policy_decision": "ALLOW | DENY | UNDECIDED",
  "policy_reasons": [],

  "insufficiency": {
    "trigger": "<condition identifier>",
    "surface": "<domain surface, e.g. filesystem>",
    "tool": "<tool that triggered>",
    "condition": "<human-readable description of what Pass encountered>",
    "rules_consulted": ["<rule/policy identifiers examined>"],
    "gap": "<what is missing from the current deterministic basis>"
  }
}
```

**Constraints**:
- `insufficiency` is present if and only if `policy_decision` is `"UNDECIDED"`
- `insufficiency` must not classify the insufficiency (classification is Triage's responsibility)
- `insufficiency` must identify what Pass encountered, not why it matters
- `policy_reasons` must be an empty array `[]` when `policy_decision` is `"UNDECIDED"` — Pass is not denying; no reason code is appropriate
- All other existing fields remain required and unchanged

**New fields**:
- `record_type`: `"pass_decision"` — identifies this as a Pass-level record
- `process_id`: groups this record with any subsequent Triage/Terminal Judgment records for the same case
- `insufficiency`: structured metadata about what the deterministic basis lacked

### 3.2 Triage Decision Record

```json
{
  "record_version": "0.2",
  "record_type": "triage_decision",
  "timestamp_utc": "<ISO 8601>",
  "session_id": "<from originating Pass>",
  "request_id": "<from originating Pass>",
  "process_id": "<matches originating Pass>",
  "originating_pass_hash": "<record_hash of the Pass UNDECIDED record>",

  "findings": [
    {
      "finding_id": "<F1, F2, ...>",
      "category": "<rule_gap | rule_conflict | ambiguous_mapping | missing_meta_policy | insufficient_information | genuine_residual>",
      "description": "<what this finding is>",
      "basis": "<deterministic | judgmental>",
      "basis_detail": "<required when basis is judgmental: what judgment was exercised and why deterministic classification was insufficient>",
      "structural_deficiency": "<true | false>"
    }
  ],

  "governing_condition": "<finding_id of the condition that governs immediate disposition>",
  "governing_rationale": "<why this finding governs over others>",

  "disposition": {
    "type": "<DEFER_INPUT_INSUFFICIENCY | DEFER_STRUCTURAL_DEFICIENCY | ESCALATION_JUSTIFIED | NO_ADMISSIBLE_CHOICE | RANDOM_TIEBREAK | BOUNDED_ESTIMATION>",
    "detail": {}
  },

  "structural_signals": [
    {
      "signal_id": "<S1, S2, ...>",
      "finding_ref": "<finding_id that generated this signal>",
      "deficiency_class": "<rule_gap | rule_conflict | ambiguous_mapping | missing_meta_policy>",
      "surface": "<domain surface>",
      "description": "<what structural deficiency was identified>",
      "case_ref": "<originating request_id>"
    }
  ],

  "prev_record_hash": "<previous record in chain>",
  "record_hash": "<SHA256 of canonical record>",
  "signature": "<Ed25519 over record_hash>",
  "signing_key_id": "<key identifier>"
}
```

**Constraints**:
- `findings` is a non-empty array (concurrent findings preserved from day one)
- Every finding must have `basis` tag (INV-9)
- `basis_detail` is required and must be non-empty when `basis` is `"judgmental"`; `basis_detail` is omitted when `basis` is `"deterministic"`
- `structural_signals` is emitted for every finding where `structural_deficiency` is `true`; `structural_signals` is an empty array `[]` when no findings have `structural_deficiency: true`
- `disposition.type` must be consistent with the `governing_condition`'s category:
  - Categories 1–4 (structural deficiencies) → `DEFER_STRUCTURAL_DEFICIENCY`
  - Category 5 (insufficient_information) → `DEFER_INPUT_INSUFFICIENCY`
  - Category 6 (genuine_residual) → `ESCALATION_JUSTIFIED`, `NO_ADMISSIBLE_CHOICE`, `RANDOM_TIEBREAK`, or `BOUNDED_ESTIMATION`
  - When the governing condition is category 6 (genuine_residual) and one or more structural deficiencies also appear as concurrent findings: the disposition type is determined by the genuine_residual finding, and structural signals must still be emitted for all structural deficiencies present. The structural deficiency findings are not suppressed; they are non-governing concurrent findings.
- Triage must NOT emit `"ALLOW"`, `"DENY"`, or `"UNDECIDED"` as disposition type

**Disposition detail by type**:

```
DEFER_INPUT_INSUFFICIENCY:
  detail: {
    "missing_input": "<what is missing>",
    "needed_from": "<source, if known>",
    "resumable": true | false
  }

DEFER_STRUCTURAL_DEFICIENCY:
  detail: {
    "signal_ref": "<signal_id of corresponding structural signal>",
    "structural_change_needed": "<description of the gap that must be closed>"
  }

ESCALATION_JUSTIFIED:
  detail: {
    "authority": "<who>",
    "material_contribution": "<what they add that the system lacks>",
    "method": "<human_authority | bounded_estimation | other>"
  }

NO_ADMISSIBLE_CHOICE:
  detail: {
    "basis": "<why no choice is admissible>",
    "permanent_or_contingent": "permanent | contingent"
  }

RANDOM_TIEBREAK:
  detail: {
    "options": ["<option_a>", "<option_b>"],
    "symmetry_criteria": "<how symmetry was assessed>"
  }

BOUNDED_ESTIMATION:
  detail: {
    "method": "<estimation method>",
    "bounds": "<stated bounds>",
    "limitations": "<method limitations>"
  }
```

**Note on `structural_change_needed`**: This field describes the gap that prevents deterministic resolution. It must not enumerate or recommend resolution options — that is a governance decision, not a Triage determination. Triage identifies that a structural change is needed and describes what the current basis lacks; it does not select among possible changes.

### 3.3 Terminal Judgment Record (Minimal Placeholder)

```json
{
  "record_version": "0.2",
  "record_type": "terminal_judgment",
  "timestamp_utc": "<ISO 8601>",
  "session_id": "<from originating Pass>",
  "request_id": "<from originating Pass>",
  "process_id": "<matches originating Pass and Triage>",
  "originating_triage_hash": "<record_hash of the Triage record>",

  "method": "<human_authority | bounded_estimation | random_tiebreak>",
  "decider": {
    "identity": "<who decided>",
    "authority": "<what authority they hold>"
  },
  "rationale": "<stated basis for the judgment>",
  "outcome": "<the terminal decision>",

  "prev_record_hash": "<previous record in chain>",
  "record_hash": "<SHA256 of canonical record>",
  "signature": "<Ed25519 over record_hash>",
  "signing_key_id": "<key identifier>"
}
```

**Constraints**:
- `method` must match the method Triage selected as the admissible exit
- `originating_triage_hash` must reference a Triage record whose disposition routed to Level 3
- This schema is a minimal placeholder — field expansion deferred until Terminal Judgment has real operational use. No runtime implementation in v1.

### 3.4 Structural Signals

Structural signals are **embedded in Triage records** (the `structural_signals` array in Section 3.2), not separate chain records. This is the simplest design that preserves ordering and avoids record proliferation.

**Collection**: Any consumer of structural signals reads them from Triage records in the chain. No separate collection mechanism is needed in v1; the signal extractor (Phase 4) reads from the chain directly.

**Future option**: If signal volume or processing needs warrant it, a separate signal index or extraction tool can be built later without schema changes.

---

## 4. WALKTHROUGH: ONE REAL SLICE

### Case: FS_COPY to existing destination without overwrite

**Request**:
```json
{
  "tool": "FS_COPY",
  "args": {
    "src": "/Volumes/SSD/archive/gov/governance-layer/config.json",
    "dst": "/Volumes/SSD/archive/gov/governance-layer/config.backup.json",
    "overwrite": false
  },
  "intent": {
    "goal": "Create backup copy of config",
    "constraints": {},
    "requested_action": "FS_COPY",
    "inputs": [{"ref": "file:config.json"}],
    "expected_outputs": [{"ref": "file:config.backup.json"}]
  }
}
```

**Precondition**: `config.backup.json` already exists on disk.

---

### Step 1: Pass Decision

Pass evaluates:
- Tool known: FS_COPY ✓
- Intent fields present: goal ✓, expected_outputs ✓
- Path traversal: no ✓
- Hidden paths: no ✓
- Src in allowlist: yes ✓
- Dst in allowlist: yes ✓
- Src exists: yes ✓
- **Dst exists: YES — overwrite=false**
- Policy for dest-exists-no-overwrite: **NONE**

Pass cannot produce ALLOW (no rule authorizes this). Pass cannot produce DENY (no rule prohibits this — there is no "deny when dest exists without overwrite" rule; the current DENY is a forced default, not a policy judgment). Pass emits UNDECIDED.

```json
{
  "record_version": "0.2",
  "record_type": "pass_decision",
  "timestamp_utc": "2026-03-08T14:30:00Z",
  "session_id": "sess-a1b2c3",
  "request_id": "req-d4e5f6",
  "process_id": "7f3a9b2c1d4e5f60",
  "actor": "mcp-client",
  "tool": "FS_COPY",
  "capability_class": "FS_COPY",
  "intent": { "...": "..." },
  "policy_inputs": {
    "allow_base_dirs": ["/Volumes/SSD/archive/gov/governance-layer"],
    "deny_hidden_paths": true
  },
  "policy_decision": "UNDECIDED",
  "policy_reasons": [],
  "insufficiency": {
    "trigger": "dest_exists_no_overwrite",
    "surface": "filesystem",
    "tool": "FS_COPY",
    "condition": "Destination path exists and overwrite was not requested",
    "rules_consulted": ["FS_COPY.caps.overwrite_allowed"],
    "gap": "No rule specifies disposition when destination exists and overwrite is not requested. The overwrite policy governs whether overwrite is permitted when requested, not what to do when it is not requested and the destination exists."
  },
  "tool_args_redacted": {
    "src": "/Volumes/SSD/.../config.json",
    "dst": "/Volumes/SSD/.../config.backup.json",
    "overwrite": false
  },
  "normalized_args": { "...": "..." },
  "prev_record_hash": "sha256:aabbccdd...",
  "record_hash": "sha256:11223344...",
  "signature": "EdDSA:...",
  "signing_key_id": "ed25519:gov-layer-01",
  "cap_registry_hash": "sha256:eeff0011..."
}
```

Gate remains **closed**. UNDECIDED does not open the gate. The record transfers internally to Triage.

---

### Step 2: Triage Decision

Triage receives the UNDECIDED record with full context.

**Diagnostic work**:

1. Why was the deterministic basis insufficient? The FS_COPY capability defines whether overwrite is *allowed* (`overwrite_allowed` cap), but no rule addresses the case where overwrite is *not requested* and the destination *already exists*. This is a gap in the rule structure, not a gap in the request.

2. Are there concurrent findings?
   - **F1 (rule gap)**: The capability registry lacks a disposition rule for dest-exists-no-overwrite. This is a structural deficiency — the system should have a rule for this case. *Basis: deterministic* — the gap is verifiable by inspecting the registry.
   - **F2 (possible input insufficiency)**: The caller specified `overwrite: false` explicitly. But did they know the destination existed? If not, the request may be incomplete — the caller may have expected the destination to not exist. *Basis: judgmental* — this is an inference about caller awareness of filesystem state that cannot be determined from the request alone.

3. Which finding governs? **F1 governs.** The system should have a rule for this case regardless of caller intent. Even if the caller intended to overwrite, the structural gap would still exist.

4. Disposition: **DEFER_STRUCTURAL_DEFICIENCY** — resolution depends on a policy rule that doesn't exist yet.

5. Structural signal: emitted for F1.

```json
{
  "record_version": "0.2",
  "record_type": "triage_decision",
  "timestamp_utc": "2026-03-08T14:30:01Z",
  "session_id": "sess-a1b2c3",
  "request_id": "req-d4e5f6",
  "process_id": "7f3a9b2c1d4e5f60",
  "originating_pass_hash": "sha256:11223344...",

  "findings": [
    {
      "finding_id": "F1",
      "category": "rule_gap",
      "description": "FS_COPY capability registry defines overwrite_allowed (whether overwrite is permitted when requested) but no rule addresses the disposition when destination exists and overwrite is not requested.",
      "basis": "deterministic",
      "structural_deficiency": true
    },
    {
      "finding_id": "F2",
      "category": "insufficient_information",
      "description": "Caller specified overwrite=false but may not have known destination exists. Caller intent regarding existing destination is ambiguous.",
      "basis": "judgmental",
      "basis_detail": "Inference about caller awareness of destination state. The request is syntactically complete but the caller's expectation about filesystem state cannot be determined from the request alone.",
      "structural_deficiency": false
    }
  ],

  "governing_condition": "F1",
  "governing_rationale": "The structural gap exists regardless of caller intent. Even if the caller intended to overwrite, the capability registry would still lack a dest-exists-no-overwrite rule.",

  "disposition": {
    "type": "DEFER_STRUCTURAL_DEFICIENCY",
    "detail": {
      "signal_ref": "S1",
      "structural_change_needed": "FS_COPY capability registry lacks a disposition rule for the dest-exists-no-overwrite condition. A rule must be added before this case class can be resolved deterministically."
    }
  },

  "structural_signals": [
    {
      "signal_id": "S1",
      "finding_ref": "F1",
      "deficiency_class": "rule_gap",
      "surface": "filesystem",
      "description": "FS_COPY capability registry lacks dest-exists-no-overwrite disposition rule",
      "case_ref": "req-d4e5f6"
    }
  ],

  "prev_record_hash": "sha256:11223344...",
  "record_hash": "sha256:55667788...",
  "signature": "EdDSA:...",
  "signing_key_id": "ed25519:gov-layer-01"
}
```

**Decision process ends here.** The disposition is deferral. Terminal Judgment is not reached — this is not genuine residual uncertainty; it's a structural deficiency. The case may be re-evaluated after the Structural Feedback Function surfaces a candidate rule and governance approves it.

---

### Step 3: Terminal Judgment — NOT REACHED

Correct. The walkthrough validates that Terminal Judgment is narrow. Only genuine residual uncertainty (category 6) reaches Level 3. A rule gap is a structural deficiency (category 1) — the system should be able to handle this deterministically once the rule exists.

---

### What this walkthrough validates

| Doctrine requirement | Validated |
|---|---|
| UNDECIDED as distinct Pass output | ✓ Pass emits UNDECIDED, not DENY |
| Insufficiency metadata without classification | ✓ Pass says what it encountered, not what it means |
| `policy_reasons: []` for UNDECIDED | ✓ No reason code emitted |
| Triage receives UNDECIDED with context | ✓ Full evaluation context available |
| Concurrent findings (array, not single) | ✓ F1 and F2 are independent findings |
| Basis tagging (INV-9) | ✓ F1 deterministic (no basis_detail), F2 judgmental with non-empty basis_detail |
| Governing condition selection | ✓ F1 governs with stated rationale |
| Structural signal emission | ✓ S1 emitted for the rule gap |
| `structural_change_needed` describes gap only | ✓ No resolution options enumerated |
| DEFER_STRUCTURAL_DEFICIENCY disposition | ✓ Correct for structural deficiency |
| Terminal Judgment NOT reached | ✓ Deferral, not escalation |
| One-way flow | ✓ Pass → Triage → end. No back-reference |
| Chain linking | ✓ process_id groups; originating_pass_hash links |
| Fail-closed preserved | ✓ Gate stays closed throughout |

---

## 5. IMPLEMENTATION QUESTIONS

### IQ-2: Triage evaluator architecture

**Resolved**: Standalone Python script (`triage-eval.py`), same pattern as `policy-eval.py`. Called by shell scripts and MCP server. Preserves evaluator independence. Invocation: caller checks `policy_decision == "UNDECIDED"` in Pass output and conditionally invokes `triage-eval.py` with the UNDECIDED record as input.

### IQ-4: Triage classification criteria format

**Resolved for v1**: Classification criteria for the FS_COPY case class are hardcoded in `triage-eval.py`. No external criteria file in v1. An external `triage-classification-criteria.json` (analogous to `capability-registry.json`) is the v2 target once more than one case class exists and criteria need to be audited and versioned independently of the evaluator.

### IQ-6: Automated vs. manual Triage boundary in v1

**Resolved**: Both F1 and F2 are emitted automatically by `triage-eval.py` for all FS_COPY dest-exists-no-overwrite cases. No manual review gate.

- **F1 (rule_gap, deterministic)**: Fully automatable. The gap is verifiable by registry inspection. The evaluator checks whether a dest-exists-no-overwrite rule exists in the capability registry; it does not. No judgment required.
- **F2 (insufficient_information, judgmental)**: Emitted automatically using a standard-template `basis_detail`. The `basis` field is correctly `"judgmental"` because the inference about caller awareness of filesystem state cannot be derived deterministically from the request. Automatic emission of a labeled judgment is honest: the system is not hiding the judgment; it is accurately characterizing an automated inference as judgmental and stating why. The standard basis_detail text for this case is fixed in `triage-eval.py`.

F2 remains architecturally secondary. The governing condition is F1. F2 is present to ensure concurrent findings are recorded from day one, not to drive the disposition.

### IQ-7: process_id replay-compatibility

**Noted, not blocking**: process_id is replay-compatible only when `GOV_SESSION_ID` is stable across invocations. If `GOV_SESSION_ID` is absent, `policy-eval.py` generates `sess-{uuid}` per invocation, making process_id unique per run. This is acceptable for v1: the primary function of process_id is chain grouping for verification, not replay. If replay-compatible grouping is needed in the future, `GOV_SESSION_ID` must be set consistently by the caller. No schema change required; this is an operational practice note.

---

## 6. ACCEPTANCE CRITERIA FOR THIS ARTIFACT

- [ ] IQ-1 resolved: UNDECIDED case class identified, boundary principle stated, scope declaration present
- [ ] Boundary principle explicitly does not narrow UNDECIDED to registry-gap-only for future case classes
- [ ] Chain-linking specification defines process_id, predecessor references, verification rules, and backward compatibility
- [ ] Pass record schema extends v0.1 additively: UNDECIDED, `policy_reasons: []`, insufficiency block, record_type, process_id
- [ ] Triage record schema: concurrent findings (array), basis tags, `basis_detail` absent for deterministic / required+non-empty for judgmental, structural signals, typed dispositions
- [ ] Disposition consistency rule is unambiguous for both single-finding and concurrent-finding cases (including structural + genuine_residual co-occurrence)
- [ ] `structural_change_needed` describes the gap only — no resolution options
- [ ] Terminal Judgment record schema is minimal placeholder with correct chain links and no v1 runtime
- [ ] Structural signals embedded in Triage records; no separate record type
- [ ] Walkthrough exercises FS_COPY dest-exists case through full flow
- [ ] Walkthrough validates: concurrent findings, basis tagging, basis_detail omission on deterministic, governing condition, one-way flow, fail-closed
- [ ] IQ-6 resolved: F2 is emitted automatically via standard template; no manual review gate
- [ ] IQ-4 resolved for v1: hardcoded criteria, external file deferred
- [ ] IQ-7 noted: process_id replay behavior is operational practice, not schema change
- [ ] Schemas are additive-compatible with existing v0.1 records
- [ ] No schema field forces single-cause simplicity
- [ ] No schema field introduces back-references (one-way flow preserved)

---

## 7. RECOMMENDED NEXT ACTION

Accept or revise this schema package, then proceed to **Phase 1: Pass Extension** — implement UNDECIDED emission in `policy-eval.py` for the REASON_DEST_EXISTS case class, using these schemas as the record contract.
