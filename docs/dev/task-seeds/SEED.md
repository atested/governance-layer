# Task Seed File

This is the canonical task seed file for generating new task definitions.

Add seed entries below using the format defined in docs/dev/TASK_SEEDS.md

---

## Active Seeds

(Format specified in docs/dev/TASK_SEEDS.md)

=== SEED ===

STATUS: READY
TASK_ID: AUTO
EXECUTOR: Codex
TITLE: Test RC-FS-EXECUTABLE-DISALLOWED
EXECUTOR: Codex
GOAL: |
  Add test coverage asserting RC-FS-EXECUTABLE-DISALLOWED.

NON_GOALS: |
  No policy logic changes.
  No edits outside ALLOWED_FILES.

ALLOWED_FILES: |
  tests/test_rc_fs_executable_disallowed.sh
  tests/fixtures/fs_write_executable_disallowed.json

FORBIDDEN_FILES: |
  Everything else

DEPENDENCIES: none

PROCEDURE: |
  1) Locate an existing FS_WRITE fixture in tests/fixtures to confirm the expected request schema. Copy its structure for this new fixture.
  2) Create fixture tests/fixtures/fs_write_executable_disallowed.json changing only the minimum fields needed to request an executable write (per the confirmed schema).
  3) Create harness tests/test_rc_fs_executable_disallowed.sh that runs the policy eval path used by other tests and asserts:
     - decision is DENY
     - reason_codes contains RC-FS-EXECUTABLE-DISALLOWED

ACCEPTANCE: |
  - Harness exits 0.
  - Output includes RC-FS-EXECUTABLE-DISALLOWED when the request asks to write an executable.

EVIDENCE: |
  - git diff --stat origin/main...HEAD
  - git status --porcelain
  - show created/modified files
  - show exact command + full output for the harness/script run

RETURN_FORMAT: |
  1) Summary
  2) Evidence (full command outputs)
  3) Notes / deviations

=== SEED ===

STATUS: READY
TASK_ID: AUTO
EXECUTOR: Codex
TITLE: Test RC-FS-NOT-A-DIRECTORY
EXECUTOR: Codex
GOAL: |
  Add test coverage asserting RC-FS-NOT-A-DIRECTORY for FS_LIST when path is a file.

NON_GOALS: |
  No policy logic changes.
  No edits outside ALLOWED_FILES.

ALLOWED_FILES: |
  tests/test_rc_fs_not_a_directory.sh
  tests/fixtures/fs_list_not_a_directory.json

FORBIDDEN_FILES: |
  Everything else

DEPENDENCIES: none

PROCEDURE: |
  1) Locate an existing FS_LIST fixture to confirm request schema. Copy its structure for this new fixture.
  2) Create fixture tests/fixtures/fs_list_not_a_directory.json pointing the list path to a known file path used by existing tests (or create a minimal test file in an existing fixture-supported way if required).
  3) Create harness tests/test_rc_fs_not_a_directory.sh asserting DENY + RC-FS-NOT-A-DIRECTORY.

ACCEPTANCE: |
  - Harness exits 0.
  - Output includes RC-FS-NOT-A-DIRECTORY.

EVIDENCE: |
  - git diff --stat origin/main...HEAD
  - git status --porcelain
  - show created/modified files
  - show exact command + full output for the harness/script run

RETURN_FORMAT: |
  1) Summary
  2) Evidence (full command outputs)
  3) Notes / deviations

=== SEED ===

STATUS: READY
TASK_ID: AUTO
EXECUTOR: Codex
TITLE: Test RC-FS-INCLUDE-HIDDEN-DISALLOWED
EXECUTOR: Codex
GOAL: |
  Add test coverage asserting RC-FS-INCLUDE-HIDDEN-DISALLOWED for FS_LIST when include_hidden is requested.

NON_GOALS: |
  No policy logic changes.
  Do not modify any other FS_LIST harness file (keep independent).
  No edits outside ALLOWED_FILES.

ALLOWED_FILES: |
  tests/test_rc_fs_include_hidden_disallowed.sh
  tests/fixtures/fs_list_include_hidden_disallowed.json

FORBIDDEN_FILES: |
  Everything else

DEPENDENCIES: none

PROCEDURE: |
  1) Locate an existing FS_LIST fixture to confirm request schema and the correct field name for include_hidden (copy structure; change only the minimum).
  2) Create fixture tests/fixtures/fs_list_include_hidden_disallowed.json requesting include_hidden=true (per confirmed schema).
  3) Create harness tests/test_rc_fs_include_hidden_disallowed.sh asserting DENY + RC-FS-INCLUDE-HIDDEN-DISALLOWED.

ACCEPTANCE: |
  - Harness exits 0.
  - Output includes RC-FS-INCLUDE-HIDDEN-DISALLOWED.

EVIDENCE: |
  - git diff --stat origin/main...HEAD
  - git status --porcelain
  - show created/modified files
  - show exact command + full output for the harness/script run

RETURN_FORMAT: |
  1) Summary
  2) Evidence (full command outputs)
  3) Notes / deviations

=== SEED ===

STATUS: READY
TASK_ID: AUTO
EXECUTOR: Codex
TITLE: Test RC-FS-NOT-A-FILE
EXECUTOR: Codex
GOAL: |
  Add test coverage asserting RC-FS-NOT-A-FILE for FS_READ when path is a directory.

NON_GOALS: |
  No policy logic changes.
  No edits outside ALLOWED_FILES.

ALLOWED_FILES: |
  tests/test_rc_fs_not_a_file.sh
  tests/fixtures/fs_read_not_a_file.json

FORBIDDEN_FILES: |
  Everything else

DEPENDENCIES: none

PROCEDURE: |
  1) Locate an existing FS_READ fixture to confirm request schema. Copy its structure.
  2) Create fixture tests/fixtures/fs_read_not_a_file.json setting the read path to a directory path known to exist in the test environment (prefer a directory already used by tests).
  3) Create harness tests/test_rc_fs_not_a_file.sh asserting DENY + RC-FS-NOT-A-FILE.

ACCEPTANCE: |
  - Harness exits 0.
  - Output includes RC-FS-NOT-A-FILE.

EVIDENCE: |
  - git diff --stat origin/main...HEAD
  - git status --porcelain
  - show created/modified files
  - show exact command + full output for the harness/script run

RETURN_FORMAT: |
  1) Summary
  2) Evidence (full command outputs)
  3) Notes / deviations

=== SEED ===

STATUS: READY
TASK_ID: AUTO
EXECUTOR: Codex
TITLE: Test RC-FS-MISSING-INTENT-FIELDS
EXECUTOR: Codex
GOAL: |
  Add test coverage asserting RC-FS-MISSING-INTENT-FIELDS when intent fields are absent.

NON_GOALS: |
  No policy logic changes.
  No edits outside ALLOWED_FILES.

ALLOWED_FILES: |
  tests/test_rc_fs_missing_intent_fields.sh
  tests/fixtures/fs_missing_intent_goal.json
  tests/fixtures/fs_missing_intent_expected_outputs.json

FORBIDDEN_FILES: |
  Everything else

DEPENDENCIES: none

PROCEDURE: |
  1) Locate an existing fixture that includes intent fields to confirm exact schema.
  2) Create two fixtures:
     - tests/fixtures/fs_missing_intent_goal.json (omit intent.goal)
     - tests/fixtures/fs_missing_intent_expected_outputs.json (omit intent.expected_outputs)
  3) Create harness tests/test_rc_fs_missing_intent_fields.sh that runs both fixtures and asserts DENY + RC-FS-MISSING-INTENT-FIELDS for each.

ACCEPTANCE: |
  - Harness exits 0.
  - Output includes RC-FS-MISSING-INTENT-FIELDS for both missing-field cases.

EVIDENCE: |
  - git diff --stat origin/main...HEAD
  - git status --porcelain
  - show created/modified files
  - show exact command + full output for the harness/script run

RETURN_FORMAT: |
  1) Summary
  2) Evidence (full command outputs)
  3) Notes / deviations

=== SEED ===

STATUS: READY
TASK_ID: AUTO
EXECUTOR: Codex
TITLE: Reason code coverage validator
EXECUTOR: Codex
GOAL: |
  Add a script that reports which RC-* reason codes present in policy evaluation logic do not have explicit test assertions.

NON_GOALS: |
  Do not change policy logic.
  Do not modify docs outside the allowed files.
  No edits outside ALLOWED_FILES.

ALLOWED_FILES: |
  scripts/verify-rc-coverage.py

FORBIDDEN_FILES: |
  Everything else

DEPENDENCIES: none

PROCEDURE: |
  1) Create scripts/verify-rc-coverage.py that:
     - extracts RC-* tokens from policy evaluation source(s) (start with scripts/policy-eval.py)
     - scans tests/ for asserted RC-* tokens
     - prints missing RCs deterministically, one per line, sorted
  2) Exit code:
     - exit 1 if any missing RCs
     - exit 0 if none missing
  3) Include usage in the script header (docstring) with an exact command.

ACCEPTANCE: |
  - Script runs deterministically and exits 1 on current main if gaps exist (expected initially).
  - Script exits 0 after all RC assertion tests are merged.

EVIDENCE: |
  - git diff --stat origin/main...HEAD
  - git status --porcelain
  - show created/modified files
  - show exact command + full output for the harness/script run

RETURN_FORMAT: |
  1) Summary
  2) Evidence (full command outputs)
  3) Notes / deviations

=== SEED ===

EXECUTOR: CODEX
TITLE: Integrated E2E determinism: records aggregate hash path independent
GOAL: Ensure the integrated E2E harness produces identical RECORDS_SHA across two runs when record JSON contents are identical, regardless of absolute paths.
NON_GOALS: No crypto strength guarantees; only determinism. No UI work.
ALLOWLIST:
- scripts/attest/**
- tests/test_integrated_e2e_full.sh
- tests/fixtures/integrated_e2e/**
- docs/dev/evidence/TASK_###/**
EVIDENCE:
- git diff --stat origin/main...HEAD
- git status --porcelain
- exact command + full output for the harness
ACCEPTANCE:
- Running tests/test_integrated_e2e_full.sh twice yields identical summary (including RECORDS_SHA).
STATUS: READY
TASK_ID: AUTO
FORBIDDEN_FILES: []
PROCEDURE: TBD
RETURN_FORMAT: TBD
DEPENDENCIES: []
ALLOWED_FILES: []
=== SEED ===
EXECUTOR: CODEX
TITLE: Integrated E2E determinism: manifest build is stable across runs
GOAL: Ensure build-manifest output (MANIFEST.json and any build_manifest.txt/log) is deterministic across two runs with identical inputs.
NON_GOALS: No new manifest fields unless required for determinism.
ALLOWLIST:
- scripts/attest/**
- tests/test_integrated_e2e_full.sh
- tests/fixtures/integrated_e2e/**
- docs/dev/evidence/TASK_###/**
EVIDENCE:
- diff of run1 vs run2 manifest artifacts (or hashes)
ACCEPTANCE:
- MANIFEST_SHA identical across run1/run2 without path normalization.
STATUS: READY
TASK_ID: AUTO
FORBIDDEN_FILES: []
PROCEDURE: TBD
RETURN_FORMAT: TBD
DEPENDENCIES: []
ALLOWED_FILES: []
=== SEED ===
EXECUTOR: CODEX
TITLE: Integrated E2E determinism: time ribbon render schema strict and stable
GOAL: Ensure time ribbon renderer fails closed on missing required fields (speculation_tag) and renders deterministically with stable ordering.
NON_GOALS: No UI; text output only.
ALLOWLIST:
- scripts/attest/time_ribbon.py
- scripts/attest/integrated_e2e.py
- tests/test_integrated_negative_bad_time_ribbon.sh
- tests/fixtures/integrated_e2e/**
- docs/dev/evidence/TASK_###/**
EVIDENCE:
- full harness output showing expected failure message including speculation_tag
ACCEPTANCE:
- Negative test passes and error mentions missing speculation_tag.
STATUS: READY
TASK_ID: AUTO
FORBIDDEN_FILES: []
PROCEDURE: TBD
RETURN_FORMAT: TBD
DEPENDENCIES: []
ALLOWED_FILES: []
=== SEED ===
EXECUTOR: CODEX
TITLE: Integrated E2E determinism: signing outputs contain no timestamps or nondeterministic fields
GOAL: Ensure sign-records outputs are stable across runs and do not embed timestamps, random nonces, or machine-dependent paths into signed payloads.
NON_GOALS: No security audit; determinism only.
ALLOWLIST:
- scripts/attest/**
- tests/test_integrated_e2e_full.sh
- tests/fixtures/integrated_e2e/**
- docs/dev/evidence/TASK_###/**
EVIDENCE:
- show record JSON diffs/hashes across run1/run2
ACCEPTANCE:
- Per-record JSON hashes identical across run1/run2 and aggregate RECORDS_SHA identical.
STATUS: READY
TASK_ID: AUTO
FORBIDDEN_FILES: []
PROCEDURE: TBD
RETURN_FORMAT: TBD
DEPENDENCIES: []
ALLOWED_FILES: []
