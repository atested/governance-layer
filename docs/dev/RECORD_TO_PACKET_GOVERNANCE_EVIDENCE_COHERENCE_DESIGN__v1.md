# Record-to-Packet Governance Evidence Coherence Design v1

Base SHA: `1feb9ea32537f42d166f29df71adf4450cedc378`
Status: DESIGN SPECIFICATION (not implementation)
Lane: post-traceability governance evidence product work
Subcandidate: record-to-packet governance evidence coherence

## 1) Problem Statement

The current proof-packet verify and validate-proof-bundle pipelines confirm **structural integrity** — that files exist, hashes match, and key linkage holds — but do not propagate the **semantic governance outcome** into their summary surfaces.

Concretely:

- `replay-record.py` produces a `replay_audit_summary_v1` report containing `record_counts` (total, matched, mismatched, fatal) and per-record `invariant_counts`. This report captures whether the governance replay **passed or failed**.
- `proof-packet.py verify` packages this report into a proof packet and validates that the packet's file hashes are intact. Its `proof_packet_verify_summary_v1` output contains `counts` (matched, mismatched, missing, extra, fatal) referring to **manifest file integrity**, plus `key_linkage` and `coverage_stamp_summary`. It does **not** surface the replay outcome.
- `validate-proof-bundle.sh` runs proof-packet verify and record verification, then emits `validate_proof_bundle_summary_v1`. It reports `result: pass/fail` for structural validation. It does **not** surface the replay outcome either.

An external consumer receiving a verification summary sees "result: pass" and learns that the packet is structurally intact. To determine whether the enclosed governance evaluation actually passed replay verification, the consumer must independently parse `payload/replay_audit_report.json` from the raw packet — which defeats the purpose of a summary surface.

## 2) Why Current Main Is Insufficient

Current main lands:
- proof-packet pack/verify with structural integrity checks
- replay verification with full audit reporting
- validate-proof-bundle with external-contract summary
- coverage stamp propagation through record → manifest → verify summary

Current main does **not** land:
- replay outcome propagation into `proof_packet_verify_summary_v1`
- replay outcome propagation into `validate_proof_bundle_summary_v1`
- a unified governance-evidence summary that an external consumer can treat as a single authoritative statement of both structural integrity AND governance outcome
- cross-linkage between coverage stamp in manifest and coverage stamp verified by replay
- field-shape consistency between `proof_packet_verify_summary_v1` and `validate_proof_bundle_summary_v1` (e.g., `packet_hash` is a bare hex string in one and `{algo, value}` in the other)

The gap is not structural — the data exists inside the packet. The gap is **coherence**: the summary surfaces do not compose the structural and semantic evidence into one externally consumable governance statement.

## 3) Bounded Lane Definition

This design covers **one coherence seam**: making the governance replay outcome visible in proof-packet and proof-bundle summary surfaces without requiring external consumers to parse raw inner artifacts.

The lane is bounded by:
- INPUT: an already-packed proof packet containing `manifest.json`, `payload/record.json`, `payload/replay_audit_report.json`, and optional `payload/artifacts/*`
- OUTPUT: enhanced summary surfaces that include both structural integrity AND governance replay outcome
- SCOPE: summary-surface changes only; no changes to pack semantics, replay logic, record schema, or policy evaluation

## 4) In-Scope Artifacts and Surfaces

### Primary surfaces to modify
1. **`proof_packet_verify_summary_v1`** → add governance outcome fields derived from the enclosed `replay_audit_report.json`
2. **`validate_proof_bundle_summary_v1`** → add governance outcome fields propagated from proof-packet verify

### Secondary surfaces to modify
3. **Field-shape normalization** between the two summary formats where they represent the same data (e.g., `packet_hash` representation)

### Artifacts that inform but are not modified
4. `replay_audit_summary_v1` report format (read, not changed)
5. `manifest.json` schema (read, not changed)
6. `PolicyRecord` schema (read, not changed)

## 5) Out-of-Scope Artifacts and Surfaces

The following are **explicitly excluded** from this design:

| Excluded area | Why excluded |
|---|---|
| Proof-packet pack semantics | Already landed, consumed baseline |
| Replay verification logic | Already landed, consumed baseline |
| Receipt-attestation handoff seam | Already landed, consumed baseline |
| Proof-packet handoff seam | Already landed, consumed baseline |
| Shipped-bundle validator parity | Already landed, consumed baseline |
| Receipt/tool-event traceability | Already landed, consumed baseline |
| Messaging-local evidence surfaces | Messaging proof-surface slices are consumed baseline |
| Validator-hardening residue | Separate live-but-unbounded direction |
| Broad reporting or dashboard surfaces | Not bounded, not current-main-useful |
| Cross-family redesign | Explicitly forbidden by dispatch |
| New record types or schema changes | Out of lane |
| Changes to policy evaluation or trust-grade semantics | Out of lane |
| GovMCP inspectability/query surfaces | Already landed, consumed baseline |

## 6) Core Design Decisions

### D1: Replay outcome extraction during verify

When `proof-packet.py verify` validates a packet, it already reads and hash-checks `payload/replay_audit_report.json`. The design adds: after hash verification passes, parse the replay report and extract its governance outcome fields.

**Extracted fields from `replay_audit_summary_v1`:**
- `record_counts.total` — number of records replayed
- `record_counts.matched` — records whose replay matched
- `record_counts.mismatched` — records whose replay diverged
- `record_counts.fatal` — records that failed replay fatally
- `report_version` — confirms the report is a known parseable version

**Derived field:**
- `governance_outcome` — `"pass"` if `mismatched == 0 AND fatal == 0`, `"fail"` otherwise, `"unavailable"` if replay report is missing or unparseable

### D2: Enhanced `proof_packet_verify_summary_v1` schema

Add a new top-level key `governance_evidence` to the existing summary:

```json
{
  "summary_type": "proof_packet_verify_summary_v1",
  "result": "pass",
  "counts": { "matched": 4, "mismatched": 0, "missing": 0, "extra": 0, "fatal": 0 },
  "key_linkage": { ... },
  "coverage_stamp_summary": { ... },
  "governance_evidence": {
    "replay_outcome": "pass",
    "replay_record_counts": {
      "total": 1,
      "matched": 1,
      "mismatched": 0,
      "fatal": 0
    },
    "replay_report_version": "replay_audit_summary_v1",
    "coverage_stamp_cross_check": "consistent"
  }
}
```

The `governance_evidence` block is additive — existing consumers that ignore unknown keys are unaffected.

**`coverage_stamp_cross_check`**: compares the coverage stamp in `manifest.json` `source_summary` against the coverage stamp verified by replay inside the report. Values: `"consistent"`, `"inconsistent"`, `"unavailable"`.

### D3: Enhanced `validate_proof_bundle_summary_v1` schema

Propagate `governance_evidence` from the proof-packet verify result into the bundle summary:

```json
{
  "summary_type": "validate_proof_bundle_summary_v1",
  "result": "pass",
  "packet_hash": { "algo": "sha256", "value": "..." },
  "governance_evidence": {
    "replay_outcome": "pass",
    "replay_record_counts": {
      "total": 1,
      "matched": 1,
      "mismatched": 0,
      "fatal": 0
    },
    "replay_report_version": "replay_audit_summary_v1",
    "coverage_stamp_cross_check": "consistent"
  },
  ...
}
```

### D4: Field-shape normalization

Normalize `packet_hash` representation to use the structured `{algo, value}` form in both summary surfaces. The proof-packet verify summary currently emits `packet_hash` as a bare hex string; this should match the bundle validator's `{algo, value}` shape.

This is a breaking change for `proof_packet_verify_summary_v1` consumers that parse `packet_hash` as a string. Mitigation: version the summary type or document the change as a v1-to-v1.1 migration.

### D5: Governance outcome semantics

The `governance_evidence.replay_outcome` field answers the question: **"Did the governance evaluation that produced this record survive deterministic replay?"**

- `"pass"`: all replayed records matched on all invariants (policy_decision, reason_codes, tool, cap_registry_hash, normalized_args, coverage_stamp)
- `"fail"`: at least one record had a mismatch or fatal error during replay
- `"unavailable"`: the replay audit report is missing, corrupt, or in an unrecognized format

The structural `result` field continues to answer: **"Is the proof packet structurally intact?"**

Both can independently pass or fail. A structurally intact packet with a failed governance outcome is a valid and important state — it means the evidence was preserved correctly but the governance decision did not survive replay.

### D6: No new files or commands

This design modifies existing verify/validate output, not new scripts or commands. No new CLI entry points. No new artifact types.

## 7) Distinctness From Already-Consumed Work

| This design | Already-consumed work |
|---|---|
| Adds governance outcome to verify/validate **summaries** | Proof-packet handoff seam: built the pack/verify pipeline itself |
| Extracts replay semantics into summary surfaces | Receipt-attestation handoff: built the record → proof-packet flow |
| Cross-checks coverage stamp across manifest and replay | Coverage stamp v1: built stamp flow through record and manifest |
| Normalizes field shapes between summary formats | Validator parity: established both summary formats |
| Does NOT change replay logic | Replay verification: built the replay engine |
| Does NOT change record schema | Trust-grade closure: built signed-record emission |
| Does NOT touch GovMCP query surfaces | GovMCP seam closures: built inspectability/query/catalog |
| Does NOT touch messaging evidence | Messaging proof-surface slices: built MSG_SEND/MSG_REPLY evidence |

The consumed work built the **pipeline**. This design makes the pipeline's **output intelligible** at the summary level.

## 8) Acceptance Criteria For A Future Implementation Tranche

A bounded implementation tranche derived from this design is complete when:

### Must-pass criteria
1. `proof_packet_verify_summary_v1` output includes `governance_evidence.replay_outcome` with correct pass/fail/unavailable semantics
2. `proof_packet_verify_summary_v1` output includes `governance_evidence.replay_record_counts` matching the enclosed replay report
3. `validate_proof_bundle_summary_v1` output includes `governance_evidence` block propagated from proof-packet verify
4. `governance_evidence.coverage_stamp_cross_check` correctly reports `consistent`/`inconsistent`/`unavailable`
5. Existing structural verification behavior is unchanged — `result` field semantics are preserved
6. A packet with a passing structural check but failing replay outcome emits `result: pass` AND `governance_evidence.replay_outcome: fail`
7. A packet missing `replay_audit_report.json` emits `governance_evidence.replay_outcome: unavailable` (not a structural failure)
8. All existing proof-packet and validate-proof-bundle tests continue to pass (with updated expected output where summary schema changes)
9. At least one new test validates governance-outcome propagation for each of: pass, fail, unavailable
10. `packet_hash` field shape is consistent between both summary surfaces

### Must-not criteria
1. Must NOT change replay verification logic or invariant set
2. Must NOT change proof-packet pack behavior or manifest schema
3. Must NOT change PolicyRecord schema
4. Must NOT add new CLI commands or scripts
5. Must NOT modify GovMCP, messaging, or AAT surfaces

## 9) False-Closure Cases

The following would represent false closure if claimed as completing this design:

1. **Adding governance_evidence to only one summary surface** — both `proof_packet_verify_summary_v1` and `validate_proof_bundle_summary_v1` must carry it
2. **Hardcoding replay_outcome to "pass"** — must actually parse and evaluate the enclosed replay report
3. **Treating structural result as governance outcome** — `result: pass` (structural) must remain independent of `governance_evidence.replay_outcome`
4. **Omitting the unavailable case** — packets without replay reports must emit `unavailable`, not error or silently omit the field
5. **Omitting coverage_stamp_cross_check** — the cross-linkage between manifest coverage stamp and replay-verified coverage stamp is part of the coherence contract
6. **Claiming field-shape normalization without actually changing proof-packet verify's packet_hash representation** — the inconsistency must be resolved, not just documented
7. **Reopening replay logic, record schema, or pack semantics** — these are out of lane and would represent scope creep, not closure of this design

## 10) Recommended Next Control Step

- This artifact is a **design specification**, not an implementation plan.
- The recommended next control step is: **confirm this design as the bounded next implementation tranche** in the capability map and work queue.
- If confirmed, produce a bounded implementation task scoped to the acceptance criteria above.
- Do NOT bundle this with other formulation-grade work (post-selector RDD, AAT convergence, messaging follow-on, validator hardening). This design is intentionally narrow.
