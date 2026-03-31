# CURRENT_MAIN_CAPABILITY_MAP

Last Updated On Branch: codex/PLANNING_COHERENCE_CLEANUP__v3  
Current Baseline (`origin/main`): `25218fce214c4677157512e3c0c37cb2ee9907cb`  
Latest Merge Window: `UNRESOLVED_ON_MAIN` (cleanup does not infer merge-window labels)
Canonical GitHub URL: `https://github.com/GregKeeter/governance-layer/blob/main/docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`

## 0) Quick State (startup-read)
- `origin/main`: `25218fce214c4677157512e3c0c37cb2ee9907cb`
- Latest merge window: `UNRESOLVED_ON_MAIN`
- Latest landed tasks: `TASK_337`, `TASK_338`, `TASK_339`, `TASK_340`
- Planning judgment: `PARTIALLY_CONSUMED`
- Preferred next lane: RDD next-seam restock/spec determination (post-`TASK_339-340`) or whole-project contract-convergence lane.
- Secondary candidates: proof/attestation contract convergence seam; MCP tool-event/tool-catalog bounded resilience seam
- Refresh marker: `map_reflects_current_main=yes` (source SHA `25218fce214c4677157512e3c0c37cb2ee9907cb`)
- Startup rule: consult this map before proposing a new workfront.
- Hard dependency: if this map path or canonical GitHub URL is unreadable, STOP before workfront selection.
- Dual-source requirement: startup refresh must inspect both capability state and authoritative workfront state on main.

## 1) Latest Landed Tasks (Planning-Relevant)
- `TASK_337`, `TASK_338`: RDD Phase 10 selector-mode source contract hardening + coverage
- `TASK_339`, `TASK_340`: RDD Phase 11 selector-mode request-source strictness + coverage
- `TASK_331` through `TASK_336`: RDD Phase 7-9 selector routing/contract/mode progression
- `TASK_325` through `TASK_330`: RDD Phase 4-6 signal extraction, replay extension, external criteria progression
- `TASK_323`, `TASK_324`: RDD Phase 3 chain verifier multi-record rules + coverage
- `TASK_320`, `TASK_321`, `TASK_322`: RDD Phase 2 triage evaluator + wiring + coverage
- `TASK_311`, `TASK_312`, `TASK_313`: RDD Phase 1 pass undecided schema/emission/coverage

## 2) Live Surfaces
- RDD v1 staged implementation surface (landed through Phase 11 seams on main):
  `scripts/policy-eval.py`, `scripts/rdd-pass-triage.sh`, `scripts/triage-eval.py`,
  `scripts/verify-chain.py`, `scripts/replay-record.py`,
  `tests/test_policy_pass_undecided.sh`, `tests/test_rdd_*`,
  `tests/fixtures/rdd_phase11_selector_mode_*`
- Tool-catalog inspectability and validation surface:
  `mcp/tool_catalog_store.py`, `scripts/attest/export_tool_catalog_bundle.py`,
  `scripts/attest/verify_tool_catalog_bundle.py`,
  `scripts/attest/summarize_tool_catalog_slice.py`, `system/tests/test_tool_catalog_*`
- Tool-event inspectability and validation surface:
  `mcp/tool_event_store.py`, `mcp/tool_event_link_store.py`,
  `scripts/attest/export_tool_event_bundle.py`,
  `scripts/attest/verify_tool_event_bundle.py`,
  `scripts/attest/summarize_tool_event_slice.py`, `system/tests/test_tool_event_*`
- Planning/process dispatch surface:
  `docs/dev/BRIEFING_FORMAT__BFPS_v12.md`,
  `docs/dev/DISPATCH_LIBRARY__CECIL_CODEX__CANON.md`,
  `docs/dev/WORK_QUEUE.md`

## 3) Recent Landed Work By Live Surface
### RDD planning + refresh-scope governance
- RDD implementation progressed from Phase 1 through Phase 11 bounded seams on main (`TASK_311` through `TASK_340` present as ready specs; corresponding runtime/tests landed).
- Authoritative refresh scope rules remain active (TASK_314-316): planning refreshes must inspect capability state and authoritative workfront state.
- Planning docs and queue cadence are partially stale against landed RDD reality; treat RDD status as `PARTIALLY_CONSUMED` rather than `Phase 1 ready`.

### Tool-catalog
- Added deterministic slice selection + summary/report and expanded negative matrix (TASK_278-280).
- Contract-style bundle export/verify tests strengthened.

### Tool-event
- Added helper/output hardening and follow-on negative controls (TASK_275-277).
- Added deterministic event-slice summary capability and negative matrix expansion (TASK_284-286).

### Planning/process
- BFPS v12 dispatch-shape guidance and canonical dispatch-pointer seam cleanup (TASK_281-282).
- Discovery lane recommendation introduced and consumed by M73 execution (TASK_283).
- Capability map artifact and baseline protocol landed (TASK_287-289).
- BFPS startup now requires capability-map reference + canonical URL and fail-closed unreadable rule (TASK_290-292).
- BFPS hard-dependency startup and explicit DEV numbering landed (TASK_293-295).
- BFPS now requires map-derived Current Planning State and DEV-number prompt pre-briefing startup (TASK_296-298).
- BFPS now requires refresh-then-brief sequencing with canonical extraction contract (TASK_299-301).
- Pre-briefing refresh workflow now requires packetized standardized extraction block and fail-closed completeness check (TASK_305-307).

## 4) Adjacent Bounded Seams (Next-Lane Candidates)
- RDD next-seam restock/spec lane:
  bounded determination of post-`TASK_340` continuation before further implementation.
- Tool-catalog continued inspectability seam:
  bounded follow-on on catalog slice/report semantics and extension-safe negative controls.
- Tool-event receipt/replay seam:
  bounded continuation on receipt-linked event query/report semantics without server wiring.
- Attestation/proof utility seam:
  bounded contract consistency continuation across existing attest scripts/tests.
- MCP RPC seam (`mcp/server.py`):
  architecture-sensitive and often outside bounded Codex lanes; treat as separate class.

## 5) Constraints And Risk Notes
- Common hard boundary: no `mcp/server.py`, capability registry, release scripts, or assignment hot-file edits during Codex bounded lanes.
- Prefer lanes with deterministic artifacts and self-contained tests.
- Server/RPC failures observed in MCP tests should not be folded into bounded non-server lanes unless explicitly authorized.

## 6) Leverage Judgment
- Highest leverage comes from bounded lanes that are simultaneously:
  - implementation-ready in authoritative workfront state,
  - constrained to existing code/test surfaces,
  - and explicitly fail-closed in task specs.
- For current main at `25218fce214c4677157512e3c0c37cb2ee9907cb`, highest near-term leverage is bounded next-seam determination with queue/plan/map coherence refresh rather than replaying already-landed early-phase RDD lanes.
- Lowest leverage for bounded Codex lanes comes from server-integration seams requiring cross-surface architecture judgment.

## 7) Current Planning Judgment
- Judgment State: `PARTIALLY_CONSUMED`
- Why: main includes explicit authoritative-workfront refresh rules and substantial landed RDD implementation through Phase 11 seams, but canonical planning artifacts (map/impl-plan/queue cross-view) were stale before this cleanup and still require periodic reconciliation.
- Prior discovery guidance status (`TASK_283`): `CONSUMED` (preferred lane executed in M73); capability-only preference requires authoritative reconciliation.
- Preferred next lane: bounded post-`TASK_340` RDD restock/spec determination or equivalent bounded contract-convergence lane selected from authoritative workfront state.
- Secondary candidates:
  - tool-catalog continued inspectability seam
  - tool-event receipt/replay seam
- Major constraints / sensitive areas:
  - Respect authoritative workfront sources when they diverge from capability-only seam preferences.
  - `mcp/server.py` and capability registry remain out of bounded lane scope
  - release/validation hot files remain protected
  - avoid cross-surface architecture work in pre-briefing refresh lanes
- Divergence note: queue and historical planning text may lag landed implementation; authoritative truth requires reconciling code/tests/evidence with ready-task and plan surfaces, not relying on a single stale planning artifact.
- Next lane selection should use this map first, then run targeted discovery only if state drops below `VALID` or authoritative state becomes ambiguous.

## 8) Staleness / Exhaustion Note
- Mark map `STALE` if two or more merge windows land without map refresh.
- Mark map `PARTIALLY_CONSUMED` when a recommended lane has been merged but adjacent seams remain open.
- Mark map `EXHAUSTED` when all listed high-leverage seams are consumed or blocked by forbidden boundaries.
- Mark map `INSUFFICIENT` if current-main facts cannot support bounded candidate comparison.

## 9) Lightweight Update / Read Protocol
### Update after each Cecil merge window
1. Update baseline SHA and latest merge window fields.
2. Add landed tasks relevant to active live surfaces.
3. Refresh only affected surface rows and seam notes.
4. Reclassify planning judgment state (`VALID`, `PARTIALLY_CONSUMED`, `EXHAUSTED`, `STALE`, `INSUFFICIENT`).
5. Refresh the `0) Quick State (startup-read)` block to mirror the new baseline and latest landed tasks.

### Session-state extraction for BFPS briefings
- Capability map remains canonical.
- New briefings extract a compact `Current Planning State` subset from this map:
  - current baseline
  - latest merge window
  - latest landed tasks
  - planning judgment state
  - live surfaces summary
  - preferred next lane
  - secondary candidates
  - major constraints / sensitive areas
  - refresh marker (`map reflects current main = yes/no` + source SHA)
  - refresh / new-chat trigger note
- Do not duplicate full map content inside BFPS.

### Briefing extraction contract (required for refresh-then-brief)
- A new briefing MUST be generated only from refreshed canonical map state (after Codex refresh + Cecil merge).
- Required extraction fields:
  - full current `origin/main` SHA
  - latest merge window
  - latest landed tasks
  - planning judgment state
  - live surfaces summary
  - preferred next lane
  - secondary candidates
  - major constraints / sensitive areas
  - refresh marker indicating map reflects current main
- Do not generate briefings from in-chat memory or stale prior briefing text.

### Pre-briefing refresh completion packet contract (required)
- Every pre-briefing refresh completion packet MUST include a standardized `BRIEFING EXTRACTION BLOCK`.
- Briefing generation after refresh MUST consume this block directly; do not reconstruct missing state from chat/session memory.
- If the extraction block is missing or incomplete, STOP before briefing generation.

### Standard BRIEFING EXTRACTION BLOCK (required packet payload)
- `CURRENT_ORIGIN_MAIN_SHA`: full `origin/main` SHA from refreshed canonical map state.
- `LATEST_MERGE_WINDOW`: latest merge window marker (for example `M81` with merge short SHA when available).
- `LATEST_LANDED_TASKS`: latest landed task IDs from refreshed canonical map state.
- `PLANNING_JUDGMENT_STATE`: one of `VALID`, `PARTIALLY_CONSUMED`, `EXHAUSTED`, `STALE`, `INSUFFICIENT`.
- `LIVE_SURFACES_SUMMARY`: compact live-surface summary from refreshed canonical map state.
- `PREFERRED_NEXT_LANE`: current preferred bounded lane from refreshed canonical map state.
- `SECONDARY_CANDIDATES`: current secondary candidates from refreshed canonical map state.
- `MAJOR_CONSTRAINTS`: major constraints / sensitive areas from refreshed canonical map state.
- `REFRESH_MARKER`: map-reflects-current-main marker (`yes/no`) with source SHA.
- `CURRENT_PROCESS_STATE`: required BFPS startup process state:
  - canonical map path + canonical URL readable
  - startup read rule active
  - fail-closed unreadable rule active
  - refresh-then-brief sequencing active
  - DEV-number prompt step active

### Extraction mapping note
- Source extraction-block fields from this canonical map only.
- Do not source extraction-block fields from prior briefing text or assistant reconstruction.

### Trigger deeper planning refresh
- Trigger when:
  - state becomes `STALE` / `INSUFFICIENT`, or
  - next candidate lane requires cross-surface/server judgment, or
  - bounded candidates are no longer distinguishable from map contents.
  - session quality becomes flaky enough to reduce trust.

### Read before new workfront selection
- Dev chat + Greg should read this map before drafting any new combined workfront dispatch.
- If this map path or canonical URL is unreadable, STOP and resolve readability before workfront selection.
- If state is `VALID` or `PARTIALLY_CONSUMED`, choose from listed seams first.
- If state is `EXHAUSTED`, `STALE`, or `INSUFFICIENT`, run a bounded discovery-restock lane before selecting implementation scope.

### Dual-source refresh contract (authoritative)
Refresh and briefing-extraction workflows must consume two truth classes:

1. Capability state:
   - `docs/dev/CURRENT_MAIN_CAPABILITY_MAP.md`
2. Authoritative workfront state on main:
   - `docs/dev/WORK_QUEUE.md`
   - active initiative implementation-plan docs
   - corresponding `docs/dev/tasks/ready/` task specs for that initiative

Current required authoritative workfront source instance (RDD initiative):
- `docs/dev/WORK_QUEUE.md`
- `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`
- doctrine source path resolution:
  - expected legacy path: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE.md`
  - current canonical path on main: `docs/RESIDUAL_DISCRETION_DOCTRINE.md`
  - fail-closed: if neither path is readable, STOP
- `docs/dev/tasks/ready/TASK_311__rdd_pass_v02_schema_fields.md`
- `docs/dev/tasks/ready/TASK_312__rdd_pass_undecided_emission.md`
- `docs/dev/tasks/ready/TASK_313__rdd_pass_undecided_test_coverage.md`

Refresh extraction alignment rule:
- extracted planning state must reflect both truth classes
- if capability state and authoritative workfront state diverge, refresh output must say so explicitly
- if authoritative workfront state cannot be determined cleanly, STOP rather than guess

### Operator sequence for "create new Dev briefing"
1. Tell Greg briefing creation starts with canonical map refresh.
2. Provide Codex refresh task.
3. After Codex returns, provide Cecil merge block.
4. After Cecil merge completes, ask for DEV number.
5. Create briefing from refreshed canonical map state.
6. Negative rule: do not create a new briefing immediately upon request.
7. Require full `BRIEFING EXTRACTION BLOCK` in refresh packet; if missing/incomplete, STOP.
8. Ensure refresh inspected authoritative workfront state sources; if unavailable or divergent without clear resolution, STOP.

### In-chat continuation rule
- During a Dev chat, local session planning state may be updated after merges and reused for additional lane selection while judgment remains coherent.
- Create a new chat and refresh map-derived startup state when judgment becomes `EXHAUSTED`, `STALE`, or `INSUFFICIENT`, or when chat quality is flaky enough to reduce trust.
