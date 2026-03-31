# TASK_420 — existing-test acceptance plan for complete-for-now governance-layer v1

## 1. PURPOSE

Determine what product-acceptance coverage already exists on current main, define the smallest credible first acceptance run using existing tests only, and identify the few highest-value scenario gaps if stronger acceptance confidence is later required.

## 2. CURRENT_MAIN_ACCEPTANCE_CLAIMS

Current-main product claims that are reasonable to treat as acceptance targets for this phase:

- a governed record can be packaged into a deterministic proof packet and verified with stable machine-readable summary output
- proof-bundle validation produces stable machine-readable output and surfaces replay outcome without raw artifact inspection
- proof-bundle contract docs and machine-readable summary surfaces agree on the current public summary contract
- post-ALLOW governed messaging exposes provider-evidence / receipt linkage while keeping evaluator-facing records payload-blind
- replay can detect receipt/payload divergence on the governed messaging path
- verify-chain emits bounded structured summary output for RDD terminal-process chains
- current packet-hash normalization stance is landed: emitted proof-packet summaries are `v2`, validator summary shape is canonical, and validator acceptance of current bundles remains stable

## 3. EXISTING_TEST_COVERAGE_MAP

### ACCEPTANCE
- `tests/test_proof_packet_summary_json.sh`
  - proves deterministic proof-packet verify summary emission
  - proves canonical `proof_packet_verify_summary_v2`
  - proves canonical `packet_hash` object shape
  - proves replay outcome is surfaced as `pass` / `fail` / `unavailable`
- `tests/test_validate_proof_bundle.sh`
  - proves a real proof-bundle validates successfully
  - proves validator output is deterministic
  - proves current proof-bundle acceptance path recognizes `proof_packet_verify_summary_v2`
- `tests/test_validate_proof_bundle_summary_json.sh`
  - proves validator emits `validate_proof_bundle_summary_v1`
  - proves replay outcome is visible in validator summary output
  - proves validator summary remains machine-readable and deterministic
- `tests/test_external_summary_contract_parity_audit.sh`
  - proves public contract docs and emitted summary surfaces align on current main
- `system/tests/test_mcp_msg_surface.sh`
  - proves governed messaging emits `provider_evidence` and receipt linkage on the allow path
  - proves the decision record remains payload-blind
- `system/tests/test_mcp_msg_replay_receipt.sh`
  - proves replay checks catch message payload divergence using the stored receipt evidence
- `tests/test_rdd_terminal_judgment.sh`
  - proves a full pass → triage → terminal chain can be produced, verified, and summarized
  - proves `verify-chain.py --summary-json` reports completed terminal-chain outcome data

### FAILURE_MODE_SUPPORT
- `tests/test_validate_proof_bundle_summary_json_contract.sh`
  - true fail-closed coverage for validator `PASS` / `FAIL` / `ERROR` summary-contract behavior
- `tests/test_validate_proof_bundle_negative_controls.sh`
  - true fail-closed coverage for missing required files and malformed checksum-sidecar conditions
- `tests/test_validate_proof_bundle_aux_parser_hardening.sh`
  - true fail-closed coverage for malformed `versions.txt` / `release_gate_log.txt`
- `tests/test_proof_packet_contract_enforcement.sh`
  - indirect acceptance support plus contract enforcement for proof-packet manifest / summary / sha alignment
- `tests/test_rdd_chain_verify.sh`
  - true fail-closed support for invalid RDD chain ordering and linkage

### OPERATOR_OUTPUT_SUPPORT
- `tests/test_proof_packet_summary_json.sh`
  - supports operator-usable output via `governance_evidence.replay_outcome`, packet identity markers, and linkage fields
- `tests/test_validate_proof_bundle_summary_json.sh`
  - supports operator-usable output via validator summary fields and replay outcome propagation
- `tests/test_external_summary_contract_parity_audit.sh`
  - supports operator confidence indirectly by proving docs and emitted summaries still align
- `system/tests/test_mcp_msg_surface.sh`
  - supports operator-usable messaging output through `provider_evidence` rather than raw receipt inspection
- `tests/test_rdd_terminal_judgment.sh`
  - supports operator-usable RDD output via `chain_verification_summary_v1` completed-terminal rows

## 4. MINIMAL_ACCEPTANCE_RUN

Smallest credible first-run acceptance bundle using existing tests only:

1. `bash tests/test_proof_packet_summary_json.sh`
2. `bash tests/test_validate_proof_bundle.sh`
3. `bash tests/test_validate_proof_bundle_summary_json.sh`
4. `bash tests/test_external_summary_contract_parity_audit.sh`
5. `bash system/tests/test_mcp_msg_surface.sh`
6. `bash system/tests/test_mcp_msg_replay_receipt.sh`
7. `bash tests/test_rdd_terminal_judgment.sh`

Why this is the first bundle:
- it covers the core product claims end to end enough for phase-level acceptance:
  - governed artifact packaging
  - proof-bundle validation
  - replay outcome visibility
  - messaging provider-evidence / receipt linkage
  - terminal-chain structured summary output
- it stays smaller than the full failure-mode matrix
- it prioritizes user-visible and operator-visible product surfaces over pure hardening coverage

## 5. FAILURE_MODE_SUPPORT_FROM_EXISTING_TESTS

### True fail-closed coverage
- `tests/test_validate_proof_bundle_summary_json_contract.sh`
  - validator emits stable `FAIL` and `ERROR` machine summaries, not just `PASS`
- `tests/test_validate_proof_bundle_negative_controls.sh`
  - validator rejects missing required files and malformed checksum formats deterministically
- `tests/test_validate_proof_bundle_aux_parser_hardening.sh`
  - validator rejects malformed auxiliary files deterministically
- `tests/test_rdd_chain_verify.sh`
  - chain verification rejects invalid chain ordering/backlinks/duplicates
- `system/tests/test_mcp_msg_replay_receipt.sh`
  - replay fails when forwarded payload no longer matches the bound receipt digest

### Indirect coverage
- `tests/test_validate_proof_bundle.sh`
  - proves the positive validator path and one missing-file negative control, but not the full taxonomy
- `tests/test_proof_packet_summary_json.sh`
  - proves replay outcome surfacing across `pass` / `fail` / `unavailable`, but not broader proof-packet negative matrices
- `tests/test_proof_packet_contract_enforcement.sh`
  - proves manifest / summary / sha contract coherence, but not the full malformed-input surface

## 6. OPERATOR_OUTPUT_SUPPORT_FROM_EXISTING_TESTS

- Existing tests already support several operator-usable outputs without adding new scenario tests:
  - `tests/test_proof_packet_summary_json.sh` supports:
    - packet identity
    - manifest linkage
    - replay outcome visibility
    - canonical packet hash shape
  - `tests/test_validate_proof_bundle_summary_json.sh` supports:
    - validator machine summary
    - replay outcome visibility in the validator-facing output
  - `system/tests/test_mcp_msg_surface.sh` supports:
    - visible provider-evidence / receipt linkage for governed messaging
  - `tests/test_rdd_terminal_judgment.sh` supports:
    - chain summary rows that communicate completed terminal outcomes
- These are operator-output-support tests, not full operator workflow acceptance scenarios.

## 7. IMPORTANT_GAPS_NOT_COVERED_YET

Only a few important acceptance claims remain weakly covered by existing tests alone:

- one explicit cross-surface scenario showing the full acceptance story in a single run:
  - governed artifact → proof packet → proof-bundle validation → operator-usable summary outputs
- one explicit packet-hash migration scenario:
  - real legacy `proof_packet_verify_summary_v1` compatibility input and current `v2` producer output compared in one dedicated scenario
- one explicit “complete-for-now” operator-facing scenario:
  - a concise acceptance path demonstrating that the current surfaces are sufficient for the phase without relying on multiple separate tests to infer that story

These are the highest-value future scenario gaps. Larger generalized hardening or doctrine expansion is not the next testing need.

## 8. RECOMMENDED_NEXT_TESTING_STEP

`RUN_EXISTING_BUNDLE_THEN_ADD_FEW_SCENARIO_TESTS`

Reason:
- current-main already has a credible first acceptance bundle built from existing tests
- that bundle is strong enough to run first before authoring anything new
- if Greg wants stronger product-acceptance confidence after that run, only a few explicit scenario tests add clear value
- the existing suite is not too weak to start, but it is still somewhat compositional rather than driven by one or two end-to-end product-acceptance scenarios
