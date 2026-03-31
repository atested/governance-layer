# Record-to-Packet Next Tranche Confirmation v1

Base SHA: `71ebff418c9810099b96f590831a089b7b6fe1d0`
Date: 2026-03-17

---

## 1) What Portion Is Already Consumed By T403A?

T403A (M137, `fc065503`) landed a **structural linkage** `governance_evidence` block inside `proof_packet_verify_summary_v1`. The block contains:

```json
{
  "packet_id": "ppb_<sha256>",
  "manifest_sha256": "sha256:...",
  "record_bytes_sha256": "sha256:...",
  "replay_report_hash": "sha256:...",
  "result": "pass"
}
```

This block mirrors hashes already present elsewhere in the summary (`key_linkage`, `manifest_sha256`, `packet_id`) and echoes the structural `result`. It is tested by `tests/test_proof_packet_summary_json.sh` (lines 121-133).

**What T403A consumed:**
- The additive placement of a `governance_evidence` key in `proof_packet_verify_summary_v1`
- Structural-linkage mirroring (hash re-export for convenience)
- The structural `result` field echo (pass/fail of manifest hash checking)

**What T403A explicitly did NOT consume:**
- Semantic governance outcome (did the enclosed replay actually pass or fail?)
- Replay-outcome propagation (parsing `replay_audit_report.json` and extracting its verdict)
- Propagation of any governance outcome into `validate_proof_bundle_summary_v1`
- Coverage stamp cross-check between manifest and replay
- Field-shape normalization between `proof_packet_verify_summary_v1` and `validate_proof_bundle_summary_v1`

---

## 2) What Remains Open After T405?

T405 did not touch proof-packet, replay, or validator-summary surfaces. It landed in the RDD lane (Category 6 trigger, terminal judgment emitter, chain verification). T405 has no direct effect on the record-to-packet lane.

Current-main note after later verification:
- the narrow replay-outcome governance-evidence propagation slice discussed in this document is already landed on main
- `scripts/proof-packet.py` already emits `governance_evidence.replay_outcome`
- `system/scripts/validate-proof-bundle.sh` already propagates `governance_evidence` into `validate_proof_bundle_summary_v1`
- the bounded pass/fail/unavailable cases are already covered by current-main tests

However, T405 indirectly matters because it resolved the design blockers that previously made "post-selector doctrine continuation" the main competitor for next-direction priority. With doctrine continuation partially consumed, the record-to-packet lane faces less strategic competition.

**What is concretely open:**

| Gap | Current state | Surface |
|---|---|---|
| Replay outcome in proof-packet summary | already landed on main | consumed baseline |
| Replay outcome in bundle validator summary | already landed on main | consumed baseline |
| Coverage stamp cross-check | Coverage stamp in manifest exists; coverage stamp in replay report exists; no cross-comparison | `scripts/proof-packet.py` |
| Field-shape normalization (`packet_hash`) | `proof_packet_verify_summary_v1` uses bare hex string; `validate_proof_bundle_summary_v1` uses `{algo, value}` | Both surfaces |

---

## 3) Is Validator-Summary Coherence The Correct Next Tranche?

### The on-main formulation conclusion

`GOVERNANCE_EVIDENCE_PRODUCT_RECORD_TO_PACKET_FORMULATION__v1.md` (on main, canonical) explicitly concluded:

> **No bounded record-to-packet coherence workfront is currently distinct enough to formulate.** All candidate shapes collapse back into consumed proof-packet handoff or validator parity work when subjected to the fail-closed distinctness tests.

The formulation doc tested three candidates (replay-audit→manifest, verifier-summary→replay, replay+verifier fusion) and all three failed the distinctness test.

### The untracked design spec

`RECORD_TO_PACKET_GOVERNANCE_EVIDENCE_COHERENCE_DESIGN__v1.md` (NOT on main — local session artifact, never committed) proposes a different `governance_evidence` block with semantic `replay_outcome` (pass/fail/unavailable), `replay_record_counts`, `replay_report_version`, and `coverage_stamp_cross_check`. This design spec has 10 must-pass acceptance criteria and explicit distinctness verification.

### Assessment: which is right?

The formulation doc's distinctness test was correct *for the candidates it tested*. Those candidates proposed re-proving structural linkage that was already proven. The design spec's proposal is subtly different: it proposes **extracting semantic governance outcome** from the enclosed replay report, which is a genuinely new operation. The consumed proof-packet handoff work built the pipeline and proved hash linkage. It did NOT surface the replay verdict ("did governance replay match?") into summary output.

However, the design spec is not canonical (not on main), and the formulation doc IS canonical. The honest status is:

**The semantic-outcome gap is real but narrow.** An external consumer currently cannot learn from any summary surface whether governance replay passed — they must parse `payload/replay_audit_report.json` manually. This is a genuine coherence gap. But it is a narrow one, and the canonical formulation conclusion explicitly rejected the broader lane.

### Recommendation

**Do not dispatch the replay-outcome propagation slice as a new tranche.** It is already landed on current main.

If this document is used after the narrow slice is verified on main, treat it as historical analysis only. The remaining record-to-packet residue is the broader set of items that were explicitly excluded from the narrow slice:
- coverage-stamp cross-check
- field-shape normalization
- richer replay metadata propagation

---

## 4) What Files/Surfaces Would The Next Tranche Touch?

### Must-touch

| File | Change |
|---|---|
| `scripts/proof-packet.py` | In `verify` mode, after hash-checking `replay_audit_report.json`, parse the report and extract replay outcome; add `replay_outcome` field to existing `governance_evidence` block |
| `system/scripts/validate-proof-bundle.sh` | Propagate `governance_evidence` from proof-packet verify summary into `validate_proof_bundle_summary_v1` output |
| `tests/test_proof_packet_summary_json.sh` | Add assertion that `governance_evidence.replay_outcome` exists and is correct |
| `tests/test_validate_proof_bundle_summary_json.sh` | Add assertion that `governance_evidence` block exists in bundle validator summary |

### May-touch (depending on implementation)

| File | Why |
|---|---|
| `tests/test_validate_proof_bundle_summary_json_contract.sh` | If contract enforcement tests check summary schema completeness |
| `tests/test_shipped_bundle_machine_contract_parity.sh` | If parity checks cover governance_evidence propagation |

### Must-NOT-touch

| File | Why not |
|---|---|
| `scripts/replay-record.py` | Replay logic is consumed baseline |
| `scripts/policy-eval.py` | Policy evaluation is out of lane |
| `scripts/verify-record.py` | Record verification is out of lane |
| Any RDD surface | T405 lane, separate |
| Any messaging surface | Consumed baseline |
| Any GovMCP surface | Consumed baseline |

---

## 5) Is The Next Tranche Implementation-Ready Now?

**NO as a replay-outcome propagation tranche.** That tranche is already consumed on current main.

### What is already true
- `replay_outcome` is already present in `proof_packet_verify_summary_v1`
- `governance_evidence` is already propagated into `validate_proof_bundle_summary_v1`
- current-main tests already cover pass, fail, and unavailable cases

### What would need a different bounded selection
- any future work in this lane would need to target a different still-open residue item
- that selection is outside this document's former recommendation

### What does NOT need further design
- no further design is needed for the already-landed replay-outcome propagation slice

---

## 6) Explicit Exclusions

| Excluded | Why |
|---|---|
| Full design spec implementation (`RECORD_TO_PACKET_GOVERNANCE_EVIDENCE_COHERENCE_DESIGN__v1.md`) | Not on main; proposes shape that conflicts with T403A landed block; overclaims scope |
| Coverage stamp cross-check | Lower priority; risks widening into validator-parity replay; can follow later if needed |
| Field-shape normalization (`packet_hash`) | Breaking change for existing consumers; separate tranche concern |
| Replay logic changes | Consumed baseline; explicitly excluded by formulation doc |
| Record schema changes | Out of lane |
| Proof-packet pack changes | Consumed baseline |
| New CLI commands or scripts | Out of lane |
| Gate C or RDD-to-Gate-C changes | T405 lane, separate |
| Broad proof/export redesign | Too wide; would replay consumed validator-parity work |
| Overwriting T403A `governance_evidence` fields | Must be additive to avoid breaking existing consumers |

---

## 7) Recommended Next Control Step

**Do not dispatch the narrow replay-outcome propagation slice again.** Treat it as landed current-main baseline.

### Must-pass
1. future planning state must not treat replay-outcome propagation as an open next tranche
2. any future record-to-packet work must target a different residue item explicitly
3. any future selection must preserve the already-landed `governance_evidence.replay_outcome` behavior

### Must-not
1. Must NOT change replay verification logic
2. Must NOT change proof-packet pack behavior
3. Must NOT change record schema
4. Must NOT remove or restructure the landed `governance_evidence` fields
5. Must NOT present the already-landed replay-outcome slice as still pending

---

## 8) Evidence That Would Overturn This Recommendation

1. **Product confirms the formulation doc's rejection stands**: If the broader "not distinct enough" conclusion is still the product position, then no record-to-packet tranche should be dispatched and a different direction (FS_PROMOTE, Combo A summary, AAT convergence) should be selected instead.
2. **Replay outcome is already surfaced**: If analysis reveals an existing surface that already exposes the replay verdict to external consumers, the gap is illusory.
3. **External consumers don't need summary-level governance outcome**: If parsing `replay_audit_report.json` directly is acceptable, the coherence gap is a convenience issue, not a governance issue.
4. **T403A governance_evidence shape is frozen**: If the product owner considers the T403A block's schema contract immutable, additive fields would need to go in a separate key.
