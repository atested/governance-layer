# TASK_412C — External validator / operator hardening residue inventory v1

## 1. PURPOSE

Inventory the remaining current-main external validator / operator hardening residue, separate real gaps from stale planning text, and identify bounded closure candidates without reopening consumed proof/export closures.

## 2. CURRENT_MAIN_RESIDUE

Current-main planning truth consistently treats this lane as incremental residue rather than a strategic bundle:

- `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
- `docs/dev/GOVCORE_BROAD_STATE_DELTA_REFRESH_AFTER_T408__v1.md`
- `docs/dev/DESIGN_TO_REPO_GAP_AUDIT__v1.md`

Current-main residue repeatedly named:
- `packet_hash` field-shape inconsistency between summary surfaces
- broader export contract convergence
- external validator / operator hardening residue

Current-main consumed baselines that must not be reopened:
- receipt-attestation proof/export handoff seam
- proof-packet handoff seam
- shipped-bundle validator parity / external-contract convergence closure

## 3. REAL_GAPS_VS_STALE_TEXT

### Real current-main gaps
- `packet_hash` shape inconsistency remains real:
  - `proof_packet_verify_summary_v1` uses bare hex
  - `validate_proof_bundle_summary_v1` uses `{algo, value}`
- external validator/operator residue remains live as a planning bucket, but current-main does not yet split it into narrow closure tranches
- broader export-contract convergence is still real where machine-readable summary semantics and external-facing contract wording may drift

### Stale or over-broad planning text
- older bundle language that still frames this as one large cross-cutting next launch
- any wording that implies proof/export family closure is still missing in a strategic sense
- any language that collapses consumed validator parity back into an open broad redesign lane

## 4. CLOSURE_CANDIDATES

### Candidate A — `packet_hash` shape-normalization tranche
- Bounded and concrete
- Risk: potentially breaking for existing consumers, so needs explicit migration/contract stance

### Candidate B — external summary-contract parity residue audit
- Bounded audit of remaining mismatches between published external-contract language and machine-readable summary behavior
- Lower risk than field-shape change

### Candidate C — operator hardening residue shortlist
- Narrow inventory-to-shortlist pass over validator/operator usability residue that still exists after parity closure
- Useful as packaging, but one step less concrete than A or B

## 5. PRIORITIZED_SHORTLIST

1. **Candidate B — external summary-contract parity residue audit**
   - safest bounded closure candidate
   - avoids immediate breaking-change pressure
   - distinguishes real current-main contract residue from stale broad-bundle framing
2. **Candidate A — `packet_hash` shape-normalization tranche**
   - strongest single concrete gap
   - but should not go first unless consumer/migration stance is made explicit
3. **Candidate C — operator hardening residue shortlist**
   - useful if the lane needs one more packaging pass before execution work

## 6. STOP_BOUNDARIES

- STOP if a candidate collapses back into consumed shipped-bundle validator parity work.
- STOP if closure would require editing hot validator/release scripts as a first move rather than packaging a bounded tranche.
- STOP if broad proof/export redesign is needed to justify the candidate.
