# CURRENT_MAIN_CAPABILITY_MAP

Last Updated On Branch: `codex/TASK_419__record_complete_for_now_state_and_defer_remaining_residue__v1`  
Current Baseline (`origin/main`): `17bbf84153981ad6de9b10a45bae4037b1b83e31`  
Latest Merge Window: `UNRESOLVED_ON_MAIN` (main does not expose merge-window labels as canonical truth)  
Canonical GitHub URL: `https://github.com/GregKeeter/governance-layer/blob/main/docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`

## 0) Quick State (startup-read)
- `origin/main`: `17bbf84153981ad6de9b10a45bae4037b1b83e31`
- Latest merge window: `UNRESOLVED_ON_MAIN`
- Current control-plane outcome: `COMPLETE_FOR_NOW`
- Current bounded-tranche status: no additional Operator UI v1 follow-on truth is recorded on reachable current main beyond the prototype baseline through T201, T203, T205, and T206
- Preferred immediate formulation candidate: `none; current phase intentionally stopped at complete-for-now`
- Strongest currently-derived subcandidate inside that formulation lane: `none active for this phase`
- Latest narrower follow-on formulation need: `none`
- Planning judgment: `VALID`
- Refresh marker: `map_reflects_current_main=yes` (source SHA `17bbf84153981ad6de9b10a45bae4037b1b83e31`)
- Startup rule: consult this map before proposing a new workfront.
- Hard dependency: if this map path or canonical GitHub URL is unreadable, STOP before workfront selection.

## 1) Current-Main Baseline Truth

### GovLayer
- GovLayer-core trust-grade closure is landed baseline on main.
- Signed-record emission, verifier strictness, and replay verification are materially closed for the canonical `PolicyRecord` path.

### GovMCP
- GovMCP minimum required-path closure is landed baseline on main.
- GovMCP inspectability/query seam closure is landed baseline on main.
- GovMCP tool-catalog exposure coherence closure is landed baseline on main.
- GovMCP tool-catalog slice/query seam closure is landed baseline on main.
- These do not imply broad GovMCP maturity or broad connector completion.

### Proof / Export / External Defensibility
- Receipt-attestation proof/export handoff seam closure is landed baseline on main.
- Proof-packet handoff seam closure is landed baseline on main.
- Shipped-bundle validator parity / external-contract convergence closure is landed baseline on main.
- External summary-contract parity residue audit is landed baseline on main.
- Packet-hash normalization with explicit contract stance is landed baseline on main.

### RDD
- RDD selector-mode contract completion tranche is landed baseline on main.
- Combo A structured summary emission is landed baseline on main.

### Messaging
- Messaging proof-surface baseline slices are landed baseline on main.
- Messaging provider-evidence / receipt-linkage strengthening is landed baseline on main.

### Operator UI
- Operator UI v1 prototype baseline through T201, T203, T205, and T206 is landed on main.
- No reachable current-main evidence supports a landed follow-on batch using `TASK_399` through `TASK_402`.
- Treat any later Operator UI follow-on story for those task IDs as orphaned/unmerged history unless and until reachable current-main evidence says otherwise.

### Process Canon
- Merge-protocol control-plane sync update is landed baseline on main.

## 2) Family Status Map For Selection

### Consumed or materially harvested as obvious next work
- deployment external validator execution-path family
- deployment external packaging/distribution family
- AAT stage -> shim -> Gate C operator-path tranche
- observability receipt/tool-event traceability tranche
- messaging proof-surface baseline slices
- highest-leverage proof/export handoff/parity seams
- bounded GovMCP seam-closure family that used to surface as generic “GovMCP maturity”

### Complete for now / deferred unless concrete need reappears
- `GovCore naming-correction implementation` consumed on main
- `post-slice governed communications expansion beyond provider-evidence strengthening` deferred as complete enough for this phase
- `external validator/operator hardening residue beyond parity audit and packet-hash normalization` deferred unless a concrete testing-discovered issue reopens it
- `post-selector doctrine continuation beyond Combo A structured summary emission` deferred unless testing exposes a concrete presentation/coherence problem
- `AAT / Foundation v0 admissibility convergence restock candidate` remains live inventory, but not active completion work for this phase

### Lower-yield / defer
- `demonstration packaging follow-on`

## 3) What Is Newly True On Main
- main is no longer accurately described by a pre-messaging, pre-proof-packet-handoff, or pre-selector-RDD baseline
- the repo now contains a real governed messaging surface with stronger replay binding kept outside evaluator-facing inputs
- the repo contains the landed Operator UI v1 prototype baseline through T201, T203, T205, and T206
- multiple once-plausible “next tranches” were later shown to be already consumed on main
- T413 consumed the first safe packaged slices from the external validator/operator hardening, messaging follow-on, and post-selector RDD residual lanes
- T415 consumed the bounded GovCore naming-correction implementation tranche
- T418 consumed the packet-hash normalization tranche with an explicit versioned contract stance
- Greg then set the current phase stop rule:
  - messaging is complete enough for this phase
  - presentation coherence is deferred unless testing exposes a concrete problem
  - overall app status is complete for now

## 4) Honest Remaining Capability Picture

### Materially complete / operational baseline
- GovLayer-core trust-grade semantics
- GovMCP bounded minimum required-path, inspectability/query, tool-catalog exposure coherence, and tool-catalog slice/query seams
- receipt-attestation handoff, proof-packet handoff, and shipped-bundle validator parity / external-contract convergence seams
- RDD selector-mode contract completion tranche
- messaging proof-surface baseline slices
- Operator UI v1 prototype baseline through T201, T203, T205, and T206
- merge-process control-plane sync responsibility

### Live but still requiring fresh formulation or restock
- AAT / Foundation v0 admissibility convergence
- any new messaging or presentation follow-on only if concrete testing exposes a bounded problem

### Inventory that must not be treated as direct next-lane truth
- large ready-task stock in `docs/dev/WORK_QUEUE.md`
- stale family labels such as generic `GovMCP maturity`, generic `deployment`, and generic `observability`

## 5) Current Control-Plane Outcome

### Recommended mode
`COMPLETE_FOR_NOW`

### Why current main is complete for now
- T413 consumed the first packaged slices in the messaging, external validator/operator hardening, and post-selector RDD residual lanes
- T415 consumed the bounded GovCore naming-correction package
- T418 consumed the packet-hash normalization residue with a clear contract stance
- Greg explicitly accepted the remaining messaging residue as sufficient for this phase
- Greg explicitly deferred remaining presentation/doctrine coherence unless testing exposes a concrete problem

### Preferred immediate formulation candidate
`none`

### Current bounded next tranche
1. none active for the current phase
2. reopen only on concrete testing-discovered failure or a new explicitly authorized tranche

## 6) Constraints And Risk Notes
- Do not reopen landed GovLayer, GovMCP, proof/export, RDD selector, or messaging baseline closures unless current-main evidence directly contradicts them.
- Do not import orphaned Operator UI follow-on history into current-main planning truth; only the landed prototype baseline through T201, T203, T205, and T206 is supported on reachable main.
- If a future Operator UI tranche is proposed, frame it as a deliberate new tranche or canon-driven need rather than continuation cleanup.
- Do not treat stale queue stock as authoritative next-lane ranking.
- Do not collapse consumed GovMCP seam closures and already-landed replay-outcome governance-evidence propagation into one generic `GovMCP maturity` family.
- Treat broad deployment, observability, and proof/export labels as too blunt unless they are restocked into bounded current-main-useful workfronts.
- Treat T413’s three landed slices as consumed baseline, not as remaining packaged candidates.
- Treat messaging residue as deferred for this phase unless testing exposes a concrete bounded problem.
- Treat presentation/doctrine residue as deferred unless testing exposes a concrete operator-facing coherence problem.

## 7) Current Planning Judgment
- Judgment State: `VALID`
- Why:
  - current-main baseline truth is clear
  - T413, T415, and T418 consumed the strongest previously packaged bounded slices
  - Greg explicitly closed the phase as complete for now
  - the leftover messaging and presentation residue is intentionally deferred rather than active completion work
  - orphaned Operator UI follow-on history must not be treated as landed current-main truth
- Preferred immediate control step:
  - no new tranche by default; reopen only on testing-discovered concrete issues or a deliberate new tranche decision
- Secondary live-but-unbounded directions:
  - AAT / Foundation v0 admissibility convergence
  - any future messaging follow-on beyond provider-evidence strengthening, if a new concrete need appears
  - any future presentation/coherence follow-on beyond Combo A, if testing exposes a concrete issue

## 8) Staleness / Exhaustion Note
- Mark map `VALID` when baseline truth is current and the present control-plane state is honestly recorded, including complete-for-now phase stops.
- Mark map `PARTIALLY_CONSUMED` when baseline truth is current but obvious next tranches have been harvested and only formulation-grade work remains.
- Mark map `EXHAUSTED` when no credible remaining live direction survives comparison.
- Mark map `INSUFFICIENT` if canonical artifacts and repo surfaces no longer support honest bounded comparison.

## 9) Lightweight Update / Read Protocol

### Update after each Cecil merge window
1. Update baseline SHA and latest merge-window field if canonical evidence exists.
2. Add newly landed planning-relevant capabilities and consumed-family consequences.
3. Reclassify whether the repo is in bounded-tranche mode or formulation mode.
4. Refresh only the affected family-status rows and quick-state block.

### Read before new workfront selection
- Read this map first.
- If state is `VALID`, follow the current control-plane state recorded here before drafting a new family or reopening a deferred lane.
- If state is `PARTIALLY_CONSUMED`, `EXHAUSTED`, or `INSUFFICIENT`, run formulation or refresh work before choosing implementation scope.
