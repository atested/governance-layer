# WORK_QUEUE.md
Single source of truth for task status. Update this file when task status changes.

## Status vocabulary

| Status | Meaning |
|---|---|
| Ready | Defined, unassigned, dependencies met |
| Assigned | Claimed by an executor; work not yet started |
| In Progress | Executor actively working |
| Evidence Submitted | Work done; awaiting gate review |
| Verified | Gate owner reviewed and approved |
| Merged | Branch merged to main |
| Done | Fully closed; in History |
| Blocked | Cannot proceed; reason in Notes |

---

## Now
Tasks actively in progress.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

---

## Next
Ready and prioritised for immediate pickup.

Canonical truth note:
The GovLayer trust-grade lane (`TASK_367`-`TASK_370`), GovMCP required-path lane (`TASK_375`-`TASK_378`), broader GovMCP maturity seam-selection lane (`TASK_387`-`TASK_390`), broader GovMCP inspectability/query lane (`TASK_391`-`TASK_394`), broader GovMCP tool-catalog exposure-coherence lane (`TASK_395`-`TASK_398`), deployment execution-path family, deployment packaging family, AAT operator-path tranche, observability traceability tranche, and messaging baseline slices (`TASK_399`, `TASK_400`) are landed or consumed baselines and are not active immediate-pickup work on current main. Remaining ready inventory below should be treated as defined task stock, not by itself as authoritative next-lane ranking.

Current control-plane mode:
Canonical current-main truth is no longer the pre-T413 `NEXT_WORKFRONT_FORMULATION` state. Replay-outcome governance-evidence propagation, the external summary-contract parity residue audit, messaging provider-evidence / receipt-linkage strengthening, Combo A structured summary emission, GovCore naming correction, and packet-hash normalization are all landed on main. For the current phase, Greg has marked the app complete for now: remaining messaging residue is accepted as sufficient for this phase, and presentation/doctrine residue is deferred unless testing exposes a concrete problem. Queue rows below remain defined task stock, not authoritative ranking or an active completion-critical winner by mere `Ready` status.

### RDD Phase 1: Pass UNDECIDED Extension (Priority)

Restock rationale: Phase 1 of the Residual Discretion Doctrine implementation. Extends `policy-eval.py` to emit v0.2 schema fields on all records and introduces the first UNDECIDED output for the FS_COPY dest-exists case class. Schema contract is accepted (Phase 0). Tasks are strictly sequential: 311 → 312 → 313. Branch: `codex/RDD_PASS_UNDECIDED__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_311 | [RDD Phase 1] Pass record v0.2 schema fields (record_type, process_id) | Ready | Codex | none | [→](tasks/ready/TASK_311__rdd_pass_v02_schema_fields.md) |
| TASK_312 | [RDD Phase 1] Pass UNDECIDED emission — FS_COPY dest-exists | Ready | Codex | TASK_311 | [→](tasks/ready/TASK_312__rdd_pass_undecided_emission.md) |
| TASK_313 | [RDD Phase 1] Pass UNDECIDED test coverage | Ready | Codex | TASK_311, TASK_312 | [→](tasks/ready/TASK_313__rdd_pass_undecided_test_coverage.md) |

### RDD Phase 2: Triage Evaluator (Priority)

Restock rationale: Phase 2 of the Residual Discretion Doctrine implementation plan. Builds the bounded triage evaluator lane for the existing FS_COPY dest-exists UNDECIDED case class introduced in Phase 1, with standalone triage emission, bounded conditional invocation wiring, and deterministic test coverage. Tasks are strictly sequential: 320 → 321 → 322. Branch: `codex/RDD_TRIAGE_EVAL__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_320 | [RDD Phase 2] Triage evaluator emission and chain append (FS_COPY dest-exists) | Ready | Codex | TASK_311, TASK_312, TASK_313 | [→](tasks/ready/TASK_320__rdd_triage_eval_emission_and_chain_append.md) |
| TASK_321 | [RDD Phase 2] Pass→Triage conditional invocation wiring | Ready | Codex | TASK_320 | [→](tasks/ready/TASK_321__rdd_pass_to_triage_conditional_invocation_wiring.md) |
| TASK_322 | [RDD Phase 2] Triage evaluator test coverage | Ready | Codex | TASK_320, TASK_321 | [→](tasks/ready/TASK_322__rdd_triage_eval_test_coverage.md) |

### RDD Phase 3: Chain Verification Extension (Priority)

Restock rationale: Phase 3 continuation after landed triage evaluator implementation. Extends `scripts/verify-chain.py` with bounded multi-record process rules for RDD chains and adds focused regression coverage without widening into server/doctrine/registry surfaces. Tasks are strictly sequential: 323 → 324. Branch: `codex/RDD_CHAIN_VERIFY__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_323 | [RDD Phase 3] Chain verifier multi-record process rules | Ready | Codex | TASK_320, TASK_321, TASK_322 | [→](tasks/ready/TASK_323__rdd_chain_verifier_multi_record_rules.md) |
| TASK_324 | [RDD Phase 3] Chain verifier test coverage and backward-compat regression | Ready | Codex | TASK_323 | [→](tasks/ready/TASK_324__rdd_chain_verifier_test_coverage.md) |

### RDD Phase 5: Replay Extension for Triage/Terminal Records (Priority)

Restock rationale: Phase 5 continuation after landed Phase 4 signal extraction. Extends `scripts/replay-record.py` with bounded replay compatibility for RDD triage/terminal record types and adds focused deterministic coverage, without widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 327 → 328. Branch: `codex/RDD_REPLAY_EXTENSION__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_327 | [RDD Phase 5] Replay extension for triage and terminal record types | Ready | Codex | TASK_323, TASK_324, TASK_325, TASK_326 | [→](tasks/ready/TASK_327__rdd_replay_extension_for_triage_terminal_records.md) |
| TASK_328 | [RDD Phase 5] Replay extension deterministic test coverage | Ready | Codex | TASK_327 | [→](tasks/ready/TASK_328__rdd_replay_extension_test_coverage.md) |

### RDD Phase 6: External Triage Criteria File (Priority)

Restock rationale: Phase 6 continuation after landed Phase 5 replay extension. Externalizes bounded triage classification criteria for the current v1 FS_COPY case class into a deterministic data-file seam, with focused fail-closed and determinism coverage, without widening into server/doctrine/registry surfaces. Tasks are strictly sequential: 329 → 330. Branch: `codex/RDD_TRIAGE_CRITERIA_FILE__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_329 | [RDD Phase 6] External triage classification criteria file | Ready | Codex | TASK_320, TASK_321, TASK_322 | [→](tasks/ready/TASK_329__rdd_external_triage_criteria_file.md) |
| TASK_330 | [RDD Phase 6] External triage criteria deterministic coverage | Ready | Codex | TASK_329 | [→](tasks/ready/TASK_330__rdd_external_triage_criteria_coverage.md) |

### RDD Phase 7: Triage Criteria Selector Routing (Priority)

Restock rationale: Phase 7 continuation after landed Phase 6 external criteria file. Replaces single-key criteria lookup with deterministic selector routing from Pass insufficiency signals and adds focused fail-closed/determinism coverage, without widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 331 → 332. Branch: `codex/RDD_TRIAGE_CRITERIA_SELECTOR__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_331 | [RDD Phase 7] Triage criteria selector from pass insufficiency | Ready | Codex | TASK_329, TASK_330 | [→](tasks/ready/TASK_331__rdd_triage_criteria_selector_from_pass_insufficiency.md) |
| TASK_332 | [RDD Phase 7] Triage criteria selector deterministic coverage | Ready | Codex | TASK_331 | [→](tasks/ready/TASK_332__rdd_triage_criteria_selector_coverage.md) |

### RDD Phase 8: Triage Selector Contract Hardening (Priority)

Restock rationale: Phase 8 continuation after landed Phase 7 selector routing. Hardens selector-map contract behavior (explicit fail-closed selector-map semantics and stable reason markers) with focused deterministic coverage, without widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 333 → 334. Branch: `codex/RDD_TRIAGE_SELECTOR_CONTRACT__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_333 | [RDD Phase 8] Triage selector contract strictness | Ready | Codex | TASK_331, TASK_332 | [→](tasks/ready/TASK_333__rdd_triage_selector_contract_strictness.md) |
| TASK_334 | [RDD Phase 8] Triage selector contract deterministic coverage | Ready | Codex | TASK_333 | [→](tasks/ready/TASK_334__rdd_triage_selector_contract_coverage.md) |

### RDD Phase 9: Selector-Mode Invocation Wiring (Priority)

Restock rationale: Phase 9 continuation after landed Phase 8 selector-contract hardening. Wires explicit selector-mode invocation for bounded triage path and adds focused deterministic coverage for explicit/compatibility behavior, without widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 335 → 336. Branch: `codex/RDD_TRIAGE_SELECTOR_MODE__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_335 | [RDD Phase 9] Selector-mode explicit wiring for triage invocation | Ready | Codex | TASK_333, TASK_334 | [→](tasks/ready/TASK_335__rdd_selector_mode_explicit_wiring.md) |
| TASK_336 | [RDD Phase 9] Selector-mode deterministic coverage | Ready | Codex | TASK_335 | [→](tasks/ready/TASK_336__rdd_selector_mode_coverage.md) |

### RDD Phase 13: Legacy-Alias Source Conflict Tightening (Priority)

Restock rationale: Phase 13 continuation after landed Phase 12 canonical source-conflict hardening. Tightens the remaining legacy-only multi-alias selector-mode source conflict seam so dual legacy aliases fail closed with explicit deterministic markers, and adds focused bounded coverage without widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 343 → 344. Branch: `codex/RDD_SELECTOR_MODE_LEGACY_ALIAS_CONFLICT__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_343 | [RDD Phase 13] Selector-mode legacy-alias conflict fail-closed | Ready | Codex | TASK_341, TASK_342 | [→](tasks/ready/TASK_343__rdd_selector_mode_legacy_alias_conflict_fail_closed.md) |
| TASK_344 | [RDD Phase 13] Selector-mode legacy-alias conflict deterministic coverage | Ready | Codex | TASK_343 | [→](tasks/ready/TASK_344__rdd_selector_mode_legacy_alias_conflict_coverage.md) |

### RDD Phase 14: Legacy Dual-Alias Mismatch Strictness (Priority)

Restock rationale: Phase 14 continuation after landed Phase 13 legacy-only dual-alias conflict handling. Tightens the dual legacy-alias seam by distinguishing equal-value dual aliases (conflict) from mismatched dual aliases (explicit mismatch), with focused deterministic coverage and no widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 345 → 346. Branch: `codex/RDD_SELECTOR_MODE_LEGACY_ALIAS_MISMATCH__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_345 | [RDD Phase 14] Selector-mode legacy dual-alias mismatch fail-closed | Ready | Codex | TASK_343, TASK_344 | [→](tasks/ready/TASK_345__rdd_selector_mode_legacy_dual_alias_mismatch_fail_closed.md) |
| TASK_346 | [RDD Phase 14] Selector-mode legacy dual-alias mismatch deterministic coverage | Ready | Codex | TASK_345 | [→](tasks/ready/TASK_346__rdd_selector_mode_legacy_dual_alias_mismatch_coverage.md) |

### RDD Phase 15: Legacy Dual-Alias Value-Contract Hardening (Priority)

Restock rationale: Phase 15 continuation after landed Phase 14 mismatch strictness. Tightens legacy dual-alias value-contract handling so malformed dual legacy alias values fail closed with explicit deterministic markers while preserving valid equal/mismatch behavior; bounded to the same selector-mode seam without widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 347 → 348. Branch: `codex/RDD_SELECTOR_MODE_LEGACY_ALIAS_VALUE_CONTRACT__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_347 | [RDD Phase 15] Selector-mode legacy dual-alias value-contract hardening | Ready | Codex | TASK_345, TASK_346 | [→](tasks/ready/TASK_347__rdd_selector_mode_legacy_dual_alias_value_contract_hardening.md) |
| TASK_348 | [RDD Phase 15] Selector-mode legacy dual-alias value-contract deterministic coverage | Ready | Codex | TASK_347 | [→](tasks/ready/TASK_348__rdd_selector_mode_legacy_dual_alias_value_contract_coverage.md) |

### RDD Phase 16: Legacy Dual-Alias Allowed-Value Contract Hardening (Priority)

Restock rationale: Phase 16 continuation after landed Phase 15 value-contract hardening. Tightens the remaining dual legacy-alias seam by fail-closing unsupported non-empty selector-mode strings while preserving existing valid conflict/mismatch and value-invalid behavior, with focused deterministic coverage and no widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 349 → 350. Branch: `codex/RDD_SELECTOR_MODE_LEGACY_ALIAS_ALLOWED_VALUE_CONTRACT__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_349 | [RDD Phase 16] Selector-mode legacy dual-alias allowed-value contract hardening | Ready | Codex | TASK_347, TASK_348 | [→](tasks/ready/TASK_349__rdd_selector_mode_legacy_dual_alias_allowed_value_contract_hardening.md) |
| TASK_350 | [RDD Phase 16] Selector-mode legacy dual-alias allowed-value contract deterministic coverage | Ready | Codex | TASK_349 | [→](tasks/ready/TASK_350__rdd_selector_mode_legacy_dual_alias_allowed_value_contract_coverage.md) |

### RDD Phase 17: Legacy Dual-Alias Normalized-Value Equivalence Hardening (Priority)

Restock rationale: Phase 17 continuation after landed Phase 16 allowed-value hardening. Tightens dual legacy-alias classification by applying normalized (trimmed) allowed-value equivalence before conflict/mismatch classification, preventing whitespace-only formatting differences from producing false mismatch outcomes, with focused deterministic coverage and no widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 351 → 352. Branch: `codex/RDD_SELECTOR_MODE_LEGACY_ALIAS_NORMALIZED_VALUE_EQUIVALENCE__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_351 | [RDD Phase 17] Selector-mode legacy dual-alias normalized-value equivalence hardening | Ready | Codex | TASK_349, TASK_350 | [→](tasks/ready/TASK_351__rdd_selector_mode_legacy_dual_alias_normalized_value_equivalence_hardening.md) |
| TASK_352 | [RDD Phase 17] Selector-mode legacy dual-alias normalized-value equivalence deterministic coverage | Ready | Codex | TASK_351 | [→](tasks/ready/TASK_352__rdd_selector_mode_legacy_dual_alias_normalized_value_equivalence_coverage.md) |

### RDD Phase 18: Legacy Dual-Alias Case-Normalization Hardening (Priority)

Restock rationale: Phase 18 continuation after landed Phase 17 normalized-value equivalence hardening. Tightens dual legacy-alias classification by applying bounded lowercase normalization for trimmed allowed values before conflict/mismatch classification, preventing case-only formatting differences from producing false mismatch outcomes, with focused deterministic coverage and no widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 353 → 354. Branch: `codex/RDD_SELECTOR_MODE_LEGACY_ALIAS_CASE_NORMALIZATION__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_353 | [RDD Phase 18] Selector-mode legacy dual-alias case-normalization hardening | Ready | Codex | TASK_351, TASK_352 | [→](tasks/ready/TASK_353__rdd_selector_mode_legacy_dual_alias_case_normalization_hardening.md) |
| TASK_354 | [RDD Phase 18] Selector-mode legacy dual-alias case-normalization deterministic coverage | Ready | Codex | TASK_353 | [→](tasks/ready/TASK_354__rdd_selector_mode_legacy_dual_alias_case_normalization_coverage.md) |

### RDD Phase 19: Canonical Request Selector-Mode Case-Normalization Hardening (Priority)

Restock rationale: Phase 19 continuation after landed Phase 18 legacy dual-alias case-normalization hardening. Tightens canonical request selector-mode handling by applying bounded case-normalization for trimmed canonical request values before allowed-value validation, preventing case-only formatting differences in `intent.constraints.selector_mode` from producing false invalid outcomes, with focused deterministic coverage and no widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 355 → 356. Branch: `codex/RDD_SELECTOR_MODE_CANONICAL_REQUEST_CASE_NORMALIZATION__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_355 | [RDD Phase 19] Selector-mode canonical request case-normalization hardening | Ready | Codex | TASK_353, TASK_354 | [→](tasks/ready/TASK_355__rdd_selector_mode_canonical_request_case_normalization_hardening.md) |
| TASK_356 | [RDD Phase 19] Selector-mode canonical request case-normalization deterministic coverage | Ready | Codex | TASK_355 | [→](tasks/ready/TASK_356__rdd_selector_mode_canonical_request_case_normalization_coverage.md) |

### RDD Phase 20: Canonical Request Value-Contract Precedence Hardening (Priority)

Restock rationale: Phase 20 continuation after landed Phase 19 canonical request case-normalization hardening. Tightens canonical request selector-mode value-contract precedence so invalid canonical request values fail closed as canonical-invalid before any legacy-source conflict classification, while preserving existing valid canonical conflict behavior, with focused deterministic coverage and no widening into doctrine/server/registry surfaces. Tasks are strictly sequential: 357 → 358. Branch: `codex/RDD_SELECTOR_MODE_CANONICAL_REQUEST_VALUE_CONTRACT_PRECEDENCE__v1`. Plan: `docs/dev/RESIDUAL_DISCRETION_DOCTRINE__IMPL_PLAN__v1.md`.

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_357 | [RDD Phase 20] Selector-mode canonical request value-contract precedence hardening | Ready | Codex | TASK_355, TASK_356 | [→](tasks/ready/TASK_357__rdd_selector_mode_canonical_request_value_contract_precedence_hardening.md) |
| TASK_358 | [RDD Phase 20] Selector-mode canonical request value-contract precedence deterministic coverage | Ready | Codex | TASK_357 | [→](tasks/ready/TASK_358__rdd_selector_mode_canonical_request_value_contract_precedence_coverage.md) |

---

Restock rationale: this tranche prioritises CODE-producing proof-packet integration work that composes attestation bundles, replay audit reports, and deterministic verification summaries into merge-ready audit artifacts. It also adds governance/informational integration tasks so operators can see proof-packet readiness without blocking release gates by default.

### CODE Throughput (Priority)

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_110 | [Attestation bundle v1] Attestation bundle v1: deterministic pack command | Ready | Codex | none | [→](tasks/ready/TASK_110__attestation_bundle_v1_deterministic_pack_command.md) |
| TASK_111 | [Attestation bundle v1] Attestation bundle v1: bundle verifier (hash and manifest checks) | Ready | Codex | TASK_110 | [→](tasks/ready/TASK_111__attestation_bundle_v1_bundle_verifier_hash_and_manifest_checks.md) |
| TASK_112 | [Attestation bundle v1] Attestation bundle v1: determinism regression for pack output | Ready | Codex | TASK_110 | [→](tasks/ready/TASK_112__attestation_bundle_v1_determinism_regression_for_pack_output.md) |
| TASK_113 | [Attestation bundle v1] Attestation bundle v1: tamper detection matrix tests | Ready | Codex | TASK_111 | [→](tasks/ready/TASK_113__attestation_bundle_v1_tamper_detection_matrix_tests.md) |
| TASK_114 | [Replay / audit hardening] Replay negative controls: broaden invariant mismatch matrix | Ready | Codex | none | [→](tasks/ready/TASK_114__replay_negative_controls_broaden_invariant_mismatch_matrix.md) |
| TASK_115 | [Replay / audit hardening] Replay audit report: deterministic mismatch summary output | Ready | Codex | TASK_114 | [→](tasks/ready/TASK_115__replay_audit_report_deterministic_mismatch_summary_output.md) |
| TASK_116 | [Replay / audit hardening] Replay strictness: missing and extra invariant field controls | Ready | Codex | TASK_114 | [→](tasks/ready/TASK_116__replay_strictness_missing_and_extra_invariant_field_controls.md) |
| TASK_117 | [Governance tooling / gates] Queue drift scan: informational integration in project-status | Ready | Codex | none | [→](tasks/ready/TASK_117__queue_drift_scan_informational_integration_in_project_status.md) |
| TASK_124 | [Proof packet] Deterministic proof-packet builder from attestation bundle + replay audit report | Ready | Codex | TASK_110, TASK_111, TASK_115 | [→](tasks/ready/TASK_124__proof_packet_deterministic_proof_packet_builder_from_attes.md) |
| TASK_125 | [Proof packet] Proof-packet manifest schema and hash index verification checks | Ready | Codex | TASK_124 | [→](tasks/ready/TASK_125__proof_packet_proof_packet_manifest_schema_and_hash_index_v.md) |
| TASK_126 | [Proof packet] Tamper detection matrix tests for proof-packet components | Ready | Codex | TASK_124, TASK_125 | [→](tasks/ready/TASK_126__proof_packet_tamper_detection_matrix_tests_for_proof_packe.md) |
| TASK_127 | [Proof packet] Include signing provenance summary (key id + record hash linkage) in packet manifest | Ready | Codex | TASK_124 | [→](tasks/ready/TASK_127__proof_packet_include_signing_provenance_summary_key_id_rec.md) |
| TASK_128 | [Governance tooling / gates] Informational proof-packet check in release-gate | Ready | Codex | TASK_124 | [→](tasks/ready/TASK_128__governance_tooling_gates_informational_proof_packet_check_.md) |
| TASK_129 | [Governance tooling / gates] Proof-packet verifier summary JSON for CI/log bundles | Ready | Codex | TASK_125 | [→](tasks/ready/TASK_129__governance_tooling_gates_proof_packet_verifier_summary_jso.md) |

### External CI Correctness (contracts enforced)

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_146 | [External CI correctness] CI integrates contract enforcement tests into release-gate (ci profile) | Ready | Codex | TASK_142, TASK_143 | [→](tasks/ready/TASK_146__ci_integrates_contract_enforcement_tests_into_release_gate.md) |
| TASK_147 | [External CI correctness] GitHub Actions enforces GOV_PROFILE=ci and uploads proof-bundle outputs | Ready | Codex | TASK_144, TASK_145 | [→](tasks/ready/TASK_147__github_actions_enforces_gov_profile_ci_and_uploads_proof_bundles.md) |
| TASK_148 | [External CI correctness] CI validates proof-bundle required-files contract | Ready | Codex | TASK_136, TASK_142, TASK_143 | [→](tasks/ready/TASK_148__ci_validates_proof_bundle_required_files_contract.md) |
| TASK_149 | [External CI correctness] status_bundle_v1 optional contract sanity test | Ready | Codex | TASK_141 | [→](tasks/ready/TASK_149__status_bundle_v1_optional_contract_sanity_test.md) |
| TASK_150 | [External CI correctness] queue_drift_scan optional-file semantics test | Ready | Codex | TASK_136 | [→](tasks/ready/TASK_150__queue_drift_scan_optional_file_semantics_test.md) |
| TASK_151 | [External CI correctness] External CI single-command smoke (bootstrap + release-gate + contract checks) | Ready | Codex | TASK_135, TASK_136, TASK_141, TASK_142, TASK_143 | [→](tasks/ready/TASK_151__external_ci_single_command_smoke_bootstrap_release_gate.md) |

| TASK_193 | [External readiness regressions] Locale invariance completion for dirscan contract (validator + dirscan parity) | Ready | Codex | TASK_188 | [→](tasks/ready/TASK_193__locale_invariance_completion_for_dirscan_contract.md) |
### External Usability Next

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_156 | [External usability next] release-gate ci profile runs external validator | Ready | Codex | TASK_154, TASK_146 | [→](tasks/ready/TASK_156__release_gate_ci_profile_runs_external_validator.md) |
| TASK_157 | [External usability next] validate-proof-bundle supports deterministic summary JSON output | Ready | Codex | TASK_154 | [→](tasks/ready/TASK_157__validate_proof_bundle_supports_deterministic_summary_json.md) |
| TASK_158 | [External usability next] GitHub Actions uploads extended release-gate artifacts | Ready | Codex | TASK_147, TASK_157 | [→](tasks/ready/TASK_158__github_actions_uploads_extended_release_gate_artifacts.md) |
| TASK_159 | [External usability next] versions.txt and release_gate_log.txt canonical ordering enforcement | Ready | Codex | TASK_143 | [→](tasks/ready/TASK_159__versions_and_release_gate_log_canonical_ordering_enforcement.md) |
| TASK_160 | [External usability next] queue_drift_scan optional JSON machine output | Ready | Codex | TASK_150 | [→](tasks/ready/TASK_160__queue_drift_scan_optional_json_machine_output.md) |
| TASK_165 | [External packaging] Repo packaging check (tree completeness + forbidden local artifacts) | Ready | Codex | none | [→](tasks/ready/TASK_165__repo_packaging_check_tree_completeness_and_forbidden_local_artifacts.md) |
| TASK_166 | [External packaging] Minimal distribution manifest (what to ship) | Ready | Codex | none | [→](tasks/ready/TASK_166__minimal_distribution_manifest_what_to_ship.md) |
| TASK_167 | [External packaging] Proof-bundle validator usage docs (CLI + exit taxonomy) | Ready | Codex | TASK_154 | [→](tasks/ready/TASK_167__proof_bundle_validator_usage_docs_cli_and_exit_taxonomy.md) |
| TASK_168 | [External packaging] External packaging smoke (docs + required files scan) | Ready | Codex | none | [→](tasks/ready/TASK_168__external_packaging_smoke_docs_and_required_files_scan.md) |
| TASK_169 | [External packaging] GitHub Actions artifact completeness test (wildcard optionals) | Ready | Codex | TASK_158 | [→](tasks/ready/TASK_169__github_actions_artifact_completeness_test_wildcard_optionals.md) |
| TASK_170 | [External packaging tranche 2] Proof-bundle directory contract scanner (tests-only) | Ready | Codex | TASK_136, TASK_141, TASK_160 | [→](tasks/ready/TASK_170__proof_bundle_directory_contract_scanner_tests_only.md) |
| TASK_171 | [External packaging tranche 2] Docs consistency check for required/optional proof-bundle outputs | Ready | Codex | TASK_166, TASK_167 | [→](tasks/ready/TASK_171__docs_consistency_check_for_required_optional_proof_bundle_outputs.md) |
| TASK_172 | [External packaging tranche 2] Forbidden committed artifacts scanner (tracked files only) | Ready | Codex | TASK_165 | [→](tasks/ready/TASK_172__forbidden_committed_artifacts_scanner_tracked_files_only.md) |
| TASK_173 | [External packaging tranche 2] External checks meta-runner (cold-surface bounded suite) | Ready | Codex | TASK_165, TASK_168, TASK_169, TASK_170, TASK_171, TASK_172 | [→](tasks/ready/TASK_173__external_checks_meta_runner_cold_surface_bounded_suite.md) |
| TASK_174 | [External packaging tranche 2] Verify-task hook mapping for external packaging checks | Ready | Codex | TASK_170, TASK_171, TASK_172, TASK_173 | [→](tasks/ready/TASK_174__verify_task_hook_mapping_for_external_packaging_checks.md) |
| TASK_175 | [External validator hardening] Validator negative-controls matrix (required files + checksum) | Ready | Codex | TASK_154 | [→](tasks/ready/TASK_175__validator_negative_controls_matrix_required_files_and_checksum.md) |
| TASK_176 | [External validator hardening] Aux parser hardening (versions.txt + release_gate_log.txt) | Ready | Codex | TASK_154, TASK_143 | [→](tasks/ready/TASK_176__validator_aux_parser_hardening_duplicate_keys_and_malformed_lines.md) |
| TASK_177 | [External validator hardening] Summary JSON contract enforcement tests | Ready | Codex | TASK_157, TASK_162 | [→](tasks/ready/TASK_177__validator_summary_json_contract_enforcement_tests.md) |
| TASK_178 | [External validator hardening] Cold-surface meta-runner determinism and ordering | Ready | Codex | TASK_170, TASK_171, TASK_172, TASK_173 | [→](tasks/ready/TASK_178__external_packaging_meta_runner_determinism_and_ordering.md) |
| TASK_179 | [External validator hardening 2] Optional-file negative controls matrix (status_bundle + queue_drift JSON) | Ready | Codex | TASK_160, TASK_170 | [→](tasks/ready/TASK_179__validator_optional_files_negative_controls_matrix.md) |
| TASK_180 | [External validator hardening 2] SHA sidecar whitespace/line-ending parsing contract tests | Ready | Codex | TASK_154 | [→](tasks/ready/TASK_180__validator_sha_sidecar_whitespace_and_line_endings_contract_tests.md) |
| TASK_181 | [External validator hardening 2] Proof-bundle dir scanner contract ordering/rejection markers | Ready | Codex | TASK_170 | [→](tasks/ready/TASK_181__proof_bundle_dir_scanner_contract_ordering_and_rejection_markers.md) |
| TASK_183 | [External validator hardening] Enforce queue_drift_scan.json text_sha256 linkage in validator | Ready | Codex | TASK_160 | [→](tasks/ready/TASK_183__validator_enforces_queue_drift_scan_json_text_sha256_linkage.md) |
| TASK_187 | [External packaging docs consistency] EXTERNAL_CONTRACTS optional outputs consistency fix (`queue_drift_scan.json`) | Ready | Codex | TASK_167, TASK_171 | [→](tasks/ready/TASK_187__external_contracts_optional_outputs_consistency_fix.md) |
| TASK_188 | [External readiness regressions] Locale invariance regression for external validator + proof-bundle scans | Ready | Codex | TASK_154, TASK_170 | [→](tasks/ready/TASK_188__locale_invariance_regression_for_external_validator_and_scans.md) |
| TASK_189 | [External readiness regressions] Bash portability regression scan for external scripts/tests | Ready | Codex | none | [→](tasks/ready/TASK_189__bash_portability_regression_scan_for_external_scripts_and_tests.md) |
| TASK_190 | [External readiness regressions] Cold-surface meta runner ordering hardening regression | Ready | Codex | TASK_173 | [→](tasks/ready/TASK_190__cold_surface_meta_runner_ordering_hardening_regression.md) |
| TASK_191 | [External readiness regressions] Proof-bundle required-files parity scan (docs vs tests) | Ready | Codex | TASK_148, TASK_166 | [→](tasks/ready/TASK_191__proof_bundle_required_files_parity_scan_docs_vs_tests.md) |

## Backlog
Defined but not yet prioritised for immediate pickup.

### CODE Throughput (Queued)

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_118 | [Governance tooling / gates] Queue drift scan: regression tests for parser and pending-merge detection | Ready | Codex | none | [→](tasks/ready/TASK_118__queue_drift_scan_regression_tests_for_parser_and_pending_merge_detection.md) |
| TASK_119 | [Governance tooling / gates] OPS_CANONICAL verifier: regression tests for forbidden-command block exceptions | Ready | Codex | none | [→](tasks/ready/TASK_119__ops_canonical_verifier_regression_tests_for_forbidden_command_block_exceptions.md) |
| TASK_120 | [MCP smoke + policy completeness] MCP smoke: deterministic failure-mode expansion for unsupported/invalid tool paths | Ready | Codex | none | [→](tasks/ready/TASK_120__mcp_smoke_deterministic_failure_mode_expansion_for_unsupported_invalid_tool_paths.md) |
| TASK_121 | [MCP smoke + policy completeness] Policy completeness: deterministic RC matrix regression for core FS intents | Ready | Codex | none | [→](tasks/ready/TASK_121__policy_completeness_deterministic_rc_matrix_regression_for_core_fs_intents.md) |
| TASK_130 | [Replay / audit hardening] Embed replay audit report into proof-packet with path contract checks | Ready | Codex | TASK_124, TASK_115 | [→](tasks/ready/TASK_130__replay_audit_hardening_embed_replay_audit_report_into_proo.md) |
| TASK_131 | [Proof packet] Round-trip smoke: pack + verify bundle + replay report generation | Ready | Codex | TASK_124, TASK_125, TASK_130 | [→](tasks/ready/TASK_131__proof_packet_round_trip_smoke_pack_verify_bundle_replay_re.md) |
| TASK_132 | [Replay / audit hardening] Deterministic negative controls for proof-packet missing components | Ready | Codex | TASK_124, TASK_125 | [→](tasks/ready/TASK_132__replay_audit_hardening_deterministic_negative_controls_for.md) |
| TASK_133 | [Proof packet] Determinism regression: byte stability and component ordering | Ready | Codex | TASK_124 | [→](tasks/ready/TASK_133__proof_packet_determinism_regression_byte_stability_and_com.md) |
| TASK_050 | Verify invariants doc vs code | Ready | — | none | [→](tasks/ready/TASK_050__verify-invariants-doc-vs-code.md) |
| TASK_051 | Reason-codes index | Ready | — | none | [→](tasks/ready/TASK_051__reason-codes-index.md) |


| TASK_192 | [External validator hardening 2] Bash portability remediation for external surface scan | Ready | Codex | TASK_189 | [→](tasks/ready/TASK_192__bash_portability_remediation_for_external_surface.md) |
| TASK_218 | [Attestation utility hardening lane] Attestation output contract normalization | Ready | Codex | none | [→](tasks/ready/TASK_218__attestation_output_contract_normalization.md) |
| TASK_219 | [Attestation utility hardening lane] Attestation shared test harness | Ready | Codex | TASK_218 | [→](tasks/ready/TASK_219__attestation_shared_test_harness.md) |
| TASK_220 | [Attestation utility hardening lane] Attestation negative-control alignment | Ready | Codex | TASK_218 | [→](tasks/ready/TASK_220__attestation_negative_control_alignment.md) |
| TASK_221 | [Tool-event lifecycle hardening lane] Tool-event output contract normalization | Ready | Codex | none | [→](tasks/ready/TASK_221__tool_event_output_contract_normalization.md) |
| TASK_222 | [Tool-event lifecycle hardening lane] Tool-event test harness alignment | Ready | Codex | TASK_221 | [→](tasks/ready/TASK_222__tool_event_test_harness_alignment.md) |
| TASK_223 | [Tool-event lifecycle hardening lane] Tool-event negative-control alignment | Ready | Codex | TASK_221 | [→](tasks/ready/TASK_223__tool_event_negative_control_alignment.md) |
| TASK_224 | [Tool-catalog hardening lane] Tool-catalog output contract normalization | Ready | Codex | none | [→](tasks/ready/TASK_224__tool_catalog_output_contract_normalization.md) |
| TASK_225 | [Tool-catalog hardening lane] Tool-catalog test harness alignment | Ready | Codex | TASK_224 | [→](tasks/ready/TASK_225__tool_catalog_test_harness_alignment.md) |
| TASK_226 | [Tool-catalog hardening lane] Tool-catalog negative-control alignment | Ready | Codex | TASK_224 | [→](tasks/ready/TASK_226__tool_catalog_negative_control_alignment.md) |
| TASK_227 | [Tool-event receipt/replay hardening lane] Tool-event receipt query contract alignment | Ready | Codex | none | [→](tasks/ready/TASK_227__tool_event_receipt_query_contract_alignment.md) |
| TASK_228 | [Tool-event receipt/replay hardening lane] Tool-event replay-check alignment | Ready | Codex | TASK_227 | [→](tasks/ready/TASK_228__tool_event_replay_check_alignment.md) |
| TASK_229 | [Tool-event receipt/replay hardening lane] Tool-event receipt test harness extension | Ready | Codex | TASK_227 | [→](tasks/ready/TASK_229__tool_event_receipt_test_harness_extension.md) |
| TASK_230 | [Tool-event receipt/replay negative-path completion lane] Tool-event receipt negative matrix | Ready | Codex | none | [→](tasks/ready/TASK_230__tool_event_receipt_negative_matrix.md) |
| TASK_231 | [Tool-event receipt/replay negative-path completion lane] Tool-event replay negative matrix | Ready | Codex | TASK_230 | [→](tasks/ready/TASK_231__tool_event_replay_negative_matrix.md) |
| TASK_232 | [Tool-event receipt/replay negative-path completion lane] Tool-event receipt fixture alignment | Ready | Codex | TASK_230 | [→](tasks/ready/TASK_232__tool_event_receipt_fixture_alignment.md) |
| TASK_233 | [Tool-catalog query/verify edge-case hardening lane] Tool-catalog query edge alignment | Done | Cecil | none | Merged M55 |
| TASK_234 | [Tool-catalog query/verify edge-case hardening lane] Tool-catalog verify edge alignment | Done | Cecil | TASK_233 | Merged M55 |
| TASK_235 | [Tool-catalog query/verify edge-case hardening lane] Tool-catalog query test harness extension | Done | Cecil | TASK_233 | Merged M55 |
| TASK_236 | [Tool-event export/verify contract hardening lane] Tool-event export contract alignment | Done | Cecil | none | Merged M56 |
| TASK_237 | [Tool-event export/verify contract hardening lane] Tool-event verify contract alignment | Done | Cecil | TASK_236 | Merged M56 |
| TASK_238 | [Tool-event export/verify contract hardening lane] Tool-event export/verify test harness extension | Done | Cecil | TASK_236 | Merged M56 |
| TASK_239 | [Attestation/proof utility unification follow-on lane] Attestation/proof output unification | Ready | Codex | none | [→](tasks/ready/TASK_239__attestation_proof_output_unification.md) |
| TASK_240 | [Attestation/proof utility unification follow-on lane] Attestation/proof negative-path completion | Ready | Codex | TASK_239 | [→](tasks/ready/TASK_240__attestation_proof_negative_path_completion.md) |
| TASK_241 | [Attestation/proof utility unification follow-on lane] Attestation/proof test harness extension | Ready | Codex | TASK_239 | [→](tasks/ready/TASK_241__attestation_proof_test_harness_extension.md) |
| TASK_242 | [Tool-catalog negative-path completion lane] Tool-catalog negative matrix | Ready | Codex | none | [→](tasks/ready/TASK_242__tool_catalog_negative_matrix.md) |
| TASK_243 | [Tool-catalog negative-path completion lane] Tool-catalog verify negative matrix | Ready | Codex | TASK_242 | [→](tasks/ready/TASK_243__tool_catalog_verify_negative_matrix.md) |
| TASK_244 | [Tool-catalog negative-path completion lane] Tool-catalog fixture alignment | Ready | Codex | TASK_242 | [→](tasks/ready/TASK_244__tool_catalog_fixture_alignment.md) |
| TASK_245 | [Tool-event export/verify negative-path completion lane] Tool-event export negative matrix | Ready | Codex | none | [→](tasks/ready/TASK_245__tool_event_export_negative_matrix.md) |
| TASK_246 | [Tool-event export/verify negative-path completion lane] Tool-event verify negative matrix | Ready | Codex | TASK_245 | [→](tasks/ready/TASK_246__tool_event_verify_negative_matrix.md) |
| TASK_247 | [Tool-event export/verify negative-path completion lane] Tool-event export/verify fixture alignment | Ready | Codex | TASK_245 | [→](tasks/ready/TASK_247__tool_event_export_verify_fixture_alignment.md) |
| TASK_248 | [Attestation/proof verify negative-path follow-on lane] Attestation verify negative matrix | Ready | Codex | none | [→](tasks/ready/TASK_248__attestation_verify_negative_matrix.md) |
| TASK_249 | [Attestation/proof verify negative-path follow-on lane] Attestation verify reason alignment | Ready | Codex | TASK_248 | [→](tasks/ready/TASK_249__attestation_verify_reason_alignment.md) |
| TASK_250 | [Attestation/proof verify negative-path follow-on lane] Attestation verify fixture alignment | Ready | Codex | TASK_248 | [→](tasks/ready/TASK_250__attestation_verify_fixture_alignment.md) |
| TASK_251 | [Tool-event receipt/replay follow-on lane] Tool-event receipt/replay output alignment | Ready | Codex | none | [→](tasks/ready/TASK_251__tool_event_receipt_replay_output_alignment.md) |
| TASK_252 | [Tool-event receipt/replay follow-on lane] Tool-event receipt/replay negative follow-on | Ready | Codex | TASK_251 | [→](tasks/ready/TASK_252__tool_event_receipt_replay_negative_followon.md) |
| TASK_253 | [Tool-event receipt/replay follow-on lane] Tool-event receipt/replay fixture alignment | Ready | Codex | TASK_251 | [→](tasks/ready/TASK_253__tool_event_receipt_replay_fixture_alignment.md) |
| TASK_254 | [Attestation/proof export-side follow-on lane] Attestation export output alignment | Ready | Codex | none | [→](tasks/ready/TASK_254__attestation_export_output_alignment.md) |
| TASK_255 | [Attestation/proof export-side follow-on lane] Attestation export negative follow-on | Ready | Codex | TASK_254 | [→](tasks/ready/TASK_255__attestation_export_negative_followon.md) |
| TASK_256 | [Attestation/proof export-side follow-on lane] Attestation export fixture alignment | Ready | Codex | TASK_254 | [→](tasks/ready/TASK_256__attestation_export_fixture_alignment.md) |
| TASK_257 | [Tool-catalog export/verify follow-on lane] Tool-catalog export/verify output alignment | Ready | Codex | none | [→](tasks/ready/TASK_257__tool_catalog_export_verify_output_alignment.md) |
| TASK_258 | [Tool-catalog export/verify follow-on lane] Tool-catalog export/verify negative follow-on | Ready | Codex | TASK_257 | [→](tasks/ready/TASK_258__tool_catalog_export_verify_negative_followon.md) |
| TASK_259 | [Tool-catalog export/verify follow-on lane] Tool-catalog export/verify fixture alignment | Ready | Codex | TASK_257 | [→](tasks/ready/TASK_259__tool_catalog_export_verify_fixture_alignment.md) |
| TASK_260 | [Tool-event export/verify output follow-on lane] Tool-event export/verify output alignment | Ready | Codex | none | [→](tasks/ready/TASK_260__tool_event_export_verify_output_alignment.md) |
| TASK_261 | [Tool-event export/verify output follow-on lane] Tool-event export/verify shape consistency | Ready | Codex | TASK_260 | [→](tasks/ready/TASK_261__tool_event_export_verify_shape_consistency.md) |
| TASK_262 | [Tool-event export/verify output follow-on lane] Tool-event export/verify fixture alignment | Ready | Codex | TASK_260 | [→](tasks/ready/TASK_262__tool_event_export_verify_fixture_alignment.md) |
| TASK_263 | [Attestation helper cleanup follow-on lane] Attestation helper contract alignment | Ready | Codex | none | [→](tasks/ready/TASK_263__attestation_helper_contract_alignment.md) |
| TASK_264 | [Attestation helper cleanup follow-on lane] Attestation helper determinism alignment | Ready | Codex | TASK_263 | [→](tasks/ready/TASK_264__attestation_helper_determinism_alignment.md) |
| TASK_265 | [Attestation helper cleanup follow-on lane] Attestation helper duplication reduction | Ready | Codex | TASK_263 | [→](tasks/ready/TASK_265__attestation_helper_duplication_reduction.md) |
| TASK_266 | [Tool-catalog helper/output follow-on lane] Tool-catalog helper contract alignment | Ready | Codex | none | [→](tasks/ready/TASK_266__tool_catalog_helper_contract_alignment.md) |
| TASK_267 | [Tool-catalog helper/output follow-on lane] Tool-catalog helper determinism alignment | Ready | Codex | TASK_266 | [→](tasks/ready/TASK_267__tool_catalog_helper_determinism_alignment.md) |
| TASK_268 | [Tool-catalog helper/output follow-on lane] Tool-catalog helper duplication reduction | Ready | Codex | TASK_266 | [→](tasks/ready/TASK_268__tool_catalog_helper_duplication_reduction.md) |
| TASK_269 | [Tool-event helper/output follow-on lane] Tool-event helper contract alignment | Ready | Codex | none | [→](tasks/ready/TASK_269__tool_event_helper_contract_alignment.md) |
| TASK_270 | [Tool-event helper/output follow-on lane] Tool-event helper determinism alignment | Ready | Codex | TASK_269 | [→](tasks/ready/TASK_270__tool_event_helper_determinism_alignment.md) |
| TASK_271 | [Tool-event helper/output follow-on lane] Tool-event helper duplication reduction | Ready | Codex | TASK_269 | [→](tasks/ready/TASK_271__tool_event_helper_duplication_reduction.md) |
| TASK_272 | [Tool-catalog follow-on hardening lane] Tool-catalog output contract normalization | Ready | Codex | none | [→](tasks/ready/TASK_272__tool_catalog_output_contract_normalization.md) |
| TASK_273 | [Tool-catalog follow-on hardening lane] Tool-catalog test harness alignment | Ready | Codex | TASK_272 | [→](tasks/ready/TASK_273__tool_catalog_test_harness_alignment.md) |
| TASK_274 | [Tool-catalog follow-on hardening lane] Tool-catalog negative-control alignment | Ready | Codex | TASK_272 | [→](tasks/ready/TASK_274__tool_catalog_negative_control_alignment.md) |
| TASK_275 | [Tool-event follow-on hardening lane] Tool-event helper/output contract follow-on | Ready | Codex | none | [→](tasks/ready/TASK_275__tool_event_helper_output_contract_followon.md) |
| TASK_276 | [Tool-event follow-on hardening lane] Tool-event shared fixture refinement | Ready | Codex | TASK_275 | [→](tasks/ready/TASK_276__tool_event_shared_fixture_refinement.md) |
| TASK_277 | [Tool-event follow-on hardening lane] Tool-event negative-control follow-on | Ready | Codex | TASK_275 | [→](tasks/ready/TASK_277__tool_event_negative_control_followon.md) |
| TASK_278 | [Tool-catalog coverage expansion lane] Tool-catalog filtered-slice support | Ready | Codex | none | [→](tasks/ready/TASK_278__tool_catalog_filtered_slice_support.md) |
| TASK_279 | [Tool-catalog coverage expansion lane] Tool-catalog summary report | Ready | Codex | TASK_278 | [→](tasks/ready/TASK_279__tool_catalog_summary_report.md) |
| TASK_280 | [Tool-catalog coverage expansion lane] Tool-catalog negative matrix expansion | Ready | Codex | TASK_278 | [→](tasks/ready/TASK_280__tool_catalog_negative_matrix_expansion.md) |
| TASK_281 | [BFPS v12 dispatch-format update lane] BFPS v12 Codex dispatch shape update | Ready | Codex | none | [→](tasks/ready/TASK_281__bfps_v12_codex_dispatch_shape_update.md) |
| TASK_282 | [BFPS v12 dispatch-format update lane] BFPS v12 dispatch pointer seam resolution | Ready | Codex | TASK_281 | [→](tasks/ready/TASK_282__bfps_v12_dispatch_pointer_seam_resolution.md) |
| TASK_283 | [Discovery lane] Current-main deeper bounded lane recommendation | Ready | Codex | none | [→](tasks/ready/TASK_283__discovery_next_deeper_bounded_lane_recommendation.md) |
| TASK_284 | [Tool-event coverage expansion lane] Tool-event filtered-slice support | Ready | Codex | none | [→](tasks/ready/TASK_284__tool_event_filtered_slice_support.md) |
| TASK_285 | [Tool-event coverage expansion lane] Tool-event summary report | Ready | Codex | TASK_284 | [→](tasks/ready/TASK_285__tool_event_summary_report.md) |
| TASK_286 | [Tool-event coverage expansion lane] Tool-event negative matrix expansion | Ready | Codex | TASK_284 | [→](tasks/ready/TASK_286__tool_event_negative_matrix_expansion.md) |
| TASK_287 | [Current-main capability map lane] Current-main capability map create | Ready | Codex | none | [→](tasks/ready/TASK_287__current_main_capability_map_create.md) |
| TASK_288 | [Current-main capability map lane] Current-main capability map seed | Ready | Codex | TASK_287 | [→](tasks/ready/TASK_288__current_main_capability_map_seed.md) |
| TASK_289 | [Current-main capability map lane] Current-main capability map protocol | Ready | Codex | TASK_287 | [→](tasks/ready/TASK_289__current_main_capability_map_protocol.md) |
| TASK_290 | [BFPS + capability map integration lane] BFPS v12 capability map required reference | Ready | Codex | none | [→](tasks/ready/TASK_290__bfps_v12_capability_map_required_reference.md) |
| TASK_291 | [BFPS + capability map integration lane] Capability map lightweight maintenance protocol | Ready | Codex | TASK_290 | [→](tasks/ready/TASK_291__capability_map_lightweight_maintenance_protocol.md) |
| TASK_292 | [BFPS + capability map integration lane] Dev chat startup state wiring | Ready | Codex | TASK_290 | [→](tasks/ready/TASK_292__dev_chat_startup_state_wiring.md) |
| TASK_293 | [BFPS hard-dependency capability-map link lane] BFPS capability-map hard-dependency link | Ready | Codex | none | [→](tasks/ready/TASK_293__bfps_capability_map_hard_dependency_link.md) |
| TASK_294 | [BFPS hard-dependency capability-map link lane] Capability-map canonical link integration | Ready | Codex | TASK_293 | [→](tasks/ready/TASK_294__capability_map_canonical_link_integration.md) |
| TASK_295 | [BFPS hard-dependency capability-map link lane] Dev chat numbering and startup wiring | Ready | Codex | TASK_293 | [→](tasks/ready/TASK_295__dev_chat_numbering_and_startup_wiring.md) |
| TASK_296 | [BFPS session-state startup lane] BFPS map-derived session state | Ready | Codex | none | [→](tasks/ready/TASK_296__bfps_map_derived_session_state.md) |
| TASK_297 | [BFPS session-state startup lane] Capability-map session update protocol | Ready | Codex | TASK_296 | [→](tasks/ready/TASK_297__capability_map_session_update_protocol.md) |
| TASK_298 | [BFPS session-state startup lane] Dev number prompt in briefing creation | Ready | Codex | TASK_296 | [→](tasks/ready/TASK_298__dev_number_prompt_in_briefing_creation.md) |
| TASK_299 | [BFPS refresh-then-brief lane] BFPS refresh-then-brief rule | Ready | Codex | none | [→](tasks/ready/TASK_299__bfps_refresh_then_brief_rule.md) |
| TASK_300 | [BFPS refresh-then-brief lane] Capability-map briefing extraction contract | Ready | Codex | TASK_299 | [→](tasks/ready/TASK_300__capability_map_briefing_extraction_contract.md) |
| TASK_301 | [BFPS refresh-then-brief lane] New briefing operator sequence | Ready | Codex | TASK_299 | [→](tasks/ready/TASK_301__new_briefing_operator_sequence.md) |
| TASK_305 | [Pre-briefing refresh packet extraction lane] Pre-briefing refresh packet extraction block | Ready | Codex | none | [→](tasks/ready/TASK_305__pre_briefing_refresh_packet_block.md) |
| TASK_306 | [Pre-briefing refresh packet extraction lane] Capability-map extraction support | Ready | Codex | TASK_305 | [→](tasks/ready/TASK_306__capability_map_extraction_support.md) |
| TASK_307 | [Pre-briefing refresh packet extraction lane] Pre-briefing workflow packet rule | Ready | Codex | TASK_305 | [→](tasks/ready/TASK_307__pre_briefing_workflow_packet_rule.md) |
| TASK_308 | [Pre-briefing capability-map refresh v2 lane] Capability-map lightweight state refresh v2 | Ready | Codex | none | [→](tasks/ready/TASK_308__capability_map_lightweight_state_refresh_v2.md) |
| TASK_309 | [Pre-briefing capability-map refresh v2 lane] Capability-map planning judgment refresh v2 | Ready | Codex | TASK_308 | [→](tasks/ready/TASK_309__capability_map_planning_judgment_refresh_v2.md) |
| TASK_310 | [Pre-briefing capability-map refresh v2 lane] Capability-map briefing extraction refresh v2 | Ready | Codex | TASK_308 | [→](tasks/ready/TASK_310__capability_map_briefing_extraction_refresh_v2.md) |
| TASK_314 | [BFPS authoritative workfront refresh scope-fix lane] BFPS authoritative workfront refresh rule | Ready | Codex | none | [→](tasks/ready/TASK_314__bfps_authoritative_workfront_refresh_rule.md) |
| TASK_315 | [BFPS authoritative workfront refresh scope-fix lane] Authoritative workfront source contract | Ready | Codex | TASK_314 | [→](tasks/ready/TASK_315__authoritative_workfront_source_contract.md) |
| TASK_316 | [BFPS authoritative workfront refresh scope-fix lane] Briefing extraction workfront alignment | Ready | Codex | TASK_314 | [→](tasks/ready/TASK_316__briefing_extraction_workfront_alignment.md) |
| TASK_317 | [Pre-briefing capability-map refresh v3 lane] Capability-map lightweight state refresh v3 | Ready | Codex | none | [→](tasks/ready/TASK_317__capability_map_lightweight_state_refresh_v3.md) |
| TASK_318 | [Pre-briefing capability-map refresh v3 lane] Capability-map planning judgment refresh v3 | Ready | Codex | TASK_317 | [→](tasks/ready/TASK_318__capability_map_planning_judgment_refresh_v3.md) |
| TASK_319 | [Pre-briefing capability-map refresh v3 lane] Capability-map briefing extraction refresh v3 | Ready | Codex | TASK_317 | [→](tasks/ready/TASK_319__capability_map_briefing_extraction_refresh_v3.md) |
### External Usability (Queued)

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_141 | [External usability] Deterministic status bundle JSON for operator logs (optional) | Ready | Codex | TASK_117, TASK_128, TASK_129 | [→](tasks/ready/TASK_141__deterministic_status_bundle_json_for_operator_logs.md) |
| TASK_142 | [External usability] Core contract enforcement tests for proof-packet and release-gate outputs | Ready | Codex | TASK_136, TASK_141 | [→](tasks/ready/TASK_142__core_contract_enforcement_tests_for_proof_packet_and_release_gate_outputs.md) |
| TASK_143 | [External usability] Auxiliary format sanity tests for versions.txt and release_gate_log.txt | Ready | Codex | TASK_136 | [→](tasks/ready/TASK_143__aux_format_sanity_tests_for_versions_and_release_gate_log.md) |
| TASK_144 | [External usability] GitHub Actions CI runs release-gate with GOV_PROFILE=ci and uploads proof-bundle artifacts | Ready | Codex | TASK_138 | [→](tasks/ready/TASK_144__github_actions_ci_runs_release_gate_with_gov_profile_ci.md) |
| TASK_145 | [External usability] Deterministic regression sanity test for CI workflow (GOV_PROFILE=ci + artifact paths) | Ready | Codex | TASK_144 | [→](tasks/ready/TASK_145__workflow_regression_sanity_test_for_ci_profile_and_artifacts.md) |

### Docs / Process (Not for Throughput)

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_001 | [Docs / process] Upload snapshot to ChatGPT | Ready | Greg | TASK_000 | [→](tasks/ready/TASK_001__upload-snapshot.md) |
| TASK_002 | [Docs / process] Batch plan from snapshot | Ready | — | TASK_001 | [→](tasks/ready/TASK_002__batch-plan-from-snapshot.md) |
| TASK_013 | [Docs / process] Roadmap position update | Ready | — | none | [→](tasks/ready/TASK_013__roadmap-position-update.md) |
| TASK_020 | [Docs / process] Phase 2D scope proposal | Ready | — | none | [→](tasks/ready/TASK_020__phase-2d-scope-proposal.md) |
| TASK_060 | Normalize runtime dir doc | Ready | — | none | [→](tasks/ready/TASK_060__normalize-runtime-dir-doc.md) |
| TASK_061 | MCP requirements pin note | Ready | — | none | [→](tasks/ready/TASK_061__mcp-requirements-pin-note.md) |
| TASK_122 | [Docs / process (optional)] Docs: throughput operator notes for queue-drift-scan and release-gate | Ready | Cecil | none | [→](tasks/ready/TASK_122__docs_throughput_operator_notes_for_queue_drift_scan_and_release_gate.md) |
| TASK_123 | [Docs / process (optional)] Docs: attestation bundle v1 tasking and test catalogue entry | Ready | Cecil | none | [→](tasks/ready/TASK_123__docs_attestation_bundle_v1_tasking_and_test_catalogue_entry.md) |

### Pending Merge / Hold

| TASK_ID | Title | Status | Executor | Dependencies | Task File |
|---|---|---|---|---|---|
| TASK_003 | Dry-run doc task | Evidence Submitted | Cecil | TASK_000 | [→](tasks/ready/TASK_003__dry-run-doc-task.md) |
| TASK_022 | Cross-root promotion design | Evidence Submitted | Cecil | none | [→](tasks/ready/TASK_022__cross-root-promotion-design.md) · pending merge: `origin/codex/TASK_022__53c6c2e` |
| TASK_031 | Document canonical venv | Evidence Submitted | Cecil | none | [→](tasks/ready/TASK_031__document-venv-canonical.md) · pending merge: `origin/codex/TASK_031__4aad760` |

## Blocked

| TASK_ID | Title | Status | Executor | Blocker | Task File |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

---

## Done

| TASK_ID | Title | Status | Completed | Notes |
|---|---|---|---|---|---|
| TASK_134 | Quickstart external run: canonical commands + outputs | Done | 2026-02-26 | Already merged to origin/main via aec3fe7 (Merge FEATURE_EXTERNAL_DOCS: quickstart + versioning + MCP smoke docs); README quickstart and output interpretation added. |
| TASK_135 | Bootstrap runner: one-command setup + release-gate | Done | 2026-02-26 | Already merged to origin/main via d999af6 (Merge FEATURE_BOOTSTRAP_RUNNER: one-command setup and release-gate runner). |
| TASK_136 | Proof bundle output directory contract + emitter in release-gate | Done | 2026-02-26 | Already merged to origin/main via c4847e8 (Merge FEATURE_PROOF_BUNDLE_OUTPUT: proof-bundle output directory contract). |
| TASK_137 | GOV_PROFILE dev/ci strictness profile mapping for release-gate | Done | 2026-02-26 | Already merged to origin/main via 006453e (Merge FEATURE_GOV_PROFILE: dev/ci strictness mapping for release-gate). |
| TASK_138 | GitHub Actions CI workflow for release-gate + proof bundle artifacts | Done | 2026-02-26 | Already merged to origin/main via 53dc3ef (Merge FEATURE_GITHUB_ACTIONS_CI: release-gate workflow + proof-bundle artifacts). |
| TASK_139 | Versioning/compat docs for proof_packet_v1 + summary/replay report formats | Done | 2026-02-26 | Already merged to origin/main via aec3fe7 (Merge FEATURE_EXTERNAL_DOCS: quickstart + versioning + MCP smoke docs); proof packet/report versioning notes documented. |
| TASK_140 | MCP smoke dependency story (SKIP semantics + enable-full-mode steps) | Done | 2026-02-26 | Already merged to origin/main via aec3fe7 (Merge FEATURE_EXTERNAL_DOCS: quickstart + versioning + MCP smoke docs); SKIP/full-mode operator notes documented. |
| TASK_010 | Update ops/ACTIVE-TASK.md | Done | 2026-02-25 | Already implemented on origin/main via b84246c (docs(active-task): refresh status for Phase 2C.2 and next focus); reconciled spec/queue to evidence-closeout |
| TASK_011 | Update CHANGELOG 2B1-2C2 | Done | 2026-02-25 | Already implemented on origin/main via c6039b8 (docs(changelog): add Phase 2B.1 through 2C.2 entries); reconciled spec/queue to evidence-closeout |
| TASK_012 | Sync TEST-SUITE catalogue | Done | 2026-02-25 | Already implemented on origin/main via 7694654 (docs(test-suite): sync catalogue through MOVE and POISON_MOVE); reconciled spec/queue to evidence-closeout |
| TASK_021 | Signing phase 3 spec | Done | 2026-02-25 | Already implemented on origin/main via 838f0c0 (docs(signing): add EPIC_SIGNING.md Phase 3 signing spec); reconciled spec/queue to evidence-closeout |
| TASK_092 | Test RC-FS-EXECUTABLE-DISALLOWED | Done | 2026-02-25 | Already implemented on origin/main via bcd062d (TASK_092: implement), d80477a (TASK_062: RC-FS-EXECUTABLE-DISALLOWED harness); reconciled spec/queue to evidence-closeout |
| TASK_093 | Test RC-FS-NOT-A-DIRECTORY | Done | 2026-02-25 | Already implemented on origin/main via bd87113 (TASK_093: implement), f4a4f25 (TASK_063: RC-FS-NOT-A-DIRECTORY harness); reconciled spec/queue to evidence-closeout |
| TASK_094 | Test RC-FS-INCLUDE-HIDDEN-DISALLOWED | Done | 2026-02-25 | Already implemented on origin/main via faf0cae (TASK_094: implement), a6a7339 (TASK_064: RC-FS-INCLUDE-HIDDEN-DISALLOWED harness); reconciled spec/queue to evidence-closeout |
| TASK_095 | Test RC-FS-NOT-A-FILE | Done | 2026-02-25 | Already merged to origin/main via d20001e (TASK_095: Test RC-FS-NOT-A-FILE harness with fixture and evidence); reconciled spec/queue to evidence-closeout |
| TASK_000 | Dev workflow scaffold | Done | 2026-02-11 | Branch feat/dev-workflow-scaffold-000 |
| TASK_004 | Seed batch task files | Done | 2026-02-17 | Branch feat/seed-batch-tasks-004 |
| TASK_030 | MCP smoke deterministic python | Done | 2026-02-17 | Already implemented on origin/main via 99c7f70 (test(smoke): make python invocation deterministic); c24b4e3 (test(smoke): make runner portable across interpreters and runtime roots); 397c2ad (docs(smoke): align canonical command with policy runtime); reconciled spec/queue to evidence-closeout |
| TASK_032 | Add smoke failure-mode test | Done | 2026-02-17 | Already implemented on origin/main via 99c7f70 (test(smoke): make python invocation deterministic); c24b4e3 (test(smoke): make runner portable across interpreters and runtime roots); reconciled spec/queue to evidence-closeout |
| TASK_040 | Phase 2D FS_DELETE: intent schema | Done | 2026-02-18 | Already implemented on origin/main via ea30ab3 (docs(task-040): define FS_DELETE intent schema); reconciled spec/queue to evidence-closeout |
| TASK_041 | Phase 2D FS_DELETE: policy-eval | Done | 2026-02-18 | Already implemented on origin/main via c860b74 (feat(policy): add FS_DELETE enforcement and RC-FS-RECURSIVE-DISALLOWED); reconciled spec/queue to evidence-closeout |
| TASK_042 | Phase 2D FS_DELETE: MCP tool | Done | 2026-02-18 | Already implemented on origin/main via a645215 (feat(mcp): add fs_delete governed tool and extend smoke suite); reconciled spec/queue to evidence-closeout |
| TASK_043 | Phase 2D FS_DELETE: tests | Done | 2026-02-18 | Already implemented on origin/main via f0a2ba0 (test(task-043): add FS_DELETE harness and fixtures); 7694654 (docs(test-suite): sync catalogue through MOVE and POISON_MOVE); reconciled spec/queue to evidence-closeout |
