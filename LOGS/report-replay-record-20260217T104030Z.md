# Verifiable Replay Report (Phase 2B.R)

Timestamp (UTC): 20260217T115500Z

## Added

### scripts/replay-record.py
- Loads a decision record, requires request_bytes_b64 + request_hash.
- Verifies sha256(decoded_bytes) == request_hash before any evaluation.
- Writes decoded bytes to mkdtemp temp file (no path injection).
- Invokes policy-eval.py with internal registry (1-arg form, no external registry).
- Compares 5 deterministic invariants: policy_decision, reason_codes, tool,
  cap_registry_hash, normalized_args.
- Exits 0 on full match, 1 on invariant mismatch (diff printed), 2 on fatal error.

### tests/test_replay.sh

T-REPLAY-001: replay DENY (FS_WRITE overwrite mismatch) → exit 0, PASS
T-REPLAY-002: replay ALLOW (FS_READ within caps) → exit 0, PASS
T-REPLAY-003: tamper mid-byte XFF flip in request_bytes_b64 → exit 2,
              "request_hash mismatch" (fail-closed before evaluation)
T-REPLAY-004: registry drift — skipped (future: requires GOV_CAP_REGISTRY_PATH
              env override or filesystem overlay to avoid mutating working tree)

## Test run

```
--- T-REPLAY-001: replay DENY record ---
PASS: T-REPLAY-001 baseline verify-record (record_hash verified)
PASS: T-REPLAY-001 exit 0 (exit=0)
PASS: T-REPLAY-001 PASS output
PASS: T-REPLAY-001 shows DENY
PASS: T-REPLAY-001 shows RC (contains RC-FS-OVERWRITE-DISALLOWED)

--- T-REPLAY-002: replay ALLOW record ---
PASS: T-REPLAY-002 baseline verify-record (record_hash verified)
PASS: T-REPLAY-002 exit 0 (exit=0)
PASS: T-REPLAY-002 PASS output
PASS: T-REPLAY-002 shows ALLOW

--- T-REPLAY-003: tamper request_bytes_b64 → fail-closed ---
PASS: T-REPLAY-003 exit 2 (fail-closed)
PASS: T-REPLAY-003 hash mismatch message

--- T-REPLAY-004: skipped ---

Summary: pass=11 fail=0
```

## Regression

FS_WRITE: pass=12 fail=0
Poisoned intent: pass=14 fail=0
Canonical binding: pass=21 fail=0
MCP smoke: PASS (DENY + ALLOW + tamper + fs_list + fs_read, fail-closed verified)
