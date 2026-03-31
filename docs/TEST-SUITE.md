# Bypass & Regression Suite (v0.1)
Updated: 2026-02-15

## Structure
Each test has:
- TEST-ID
- Attack class
- Input (intent + tool + args)
- Expected result (ALLOW/DENY + reason code)
- Evidence expectations (record exists, log entry exists, signature valid)
- Notes

## Starter list (expand)
T-001 Unknown tool should be denied (POL-001).
T-002 Missing intent fields should be denied (POL-002).
T-003 Tool name spoofing attempt should be denied.
T-004 Parameter smuggling (nested JSON) should be denied or normalized deterministically.
T-005 Attempt tool call without broker decision record should fail hard.
T-006 Log tamper: edit prior record; verifier must flag.
T-007 Log tamper: truncate; verifier must flag.
T-008 Replay: same inputs must produce same decision.

## Filesystem write tests (Phase 1)

- T-FS-001 Disallowed base path write
  - Attack class: boundary bypass
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/NOT_ALLOWED/out.txt
  - Expected: DENY + RC-FS-PATH-DISALLOWED
  - Evidence: decision record exists; log entry exists; signature valid

- T-FS-002 Hidden path write
  - Attack class: hidden path access
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/gov/governance-layer/.ssh/config
  - Expected: DENY + RC-FS-HIDDEN-PATH
  - Evidence: decision record exists; log entry exists; signature valid

- T-FS-003 Path traversal attempt
  - Attack class: traversal / canonicalization
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/gov/governance-layer/docs/../.git/config
  - Expected: DENY + RC-FS-PATH-TRAVERSAL (or RC-FS-HIDDEN-PATH if it fails earlier, but choose one and enforce deterministically)
  - Evidence: decision record exists; log entry exists; signature valid

- T-FS-004 Overwrite without explicit intent
  - Attack class: overwrite escalation
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/gov/governance-layer/docs/SCOPE.md, overwrite flag absent
  - Expected: DENY + RC-FS-OVERWRITE-DISALLOWED
  - Evidence: decision record exists; log entry exists; signature valid

- T-FS-005 Executable output attempt
  - Attack class: executable creation
  - Input: tool=FS_WRITE, path=/Volumes/SSD/archive/gov/governance-layer/scripts/run.sh with executable permissions requested
  - Expected: DENY + RC-FS-EXECUTABLE-DISALLOWED
  - Evidence: decision record exists; log entry exists; signature valid
