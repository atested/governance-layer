# Canonical Request Binding + Normalization Snapshot Report

Timestamp (UTC): 20260217T110000Z

## Changes

### policy-eval.py
- Added `import base64`.
- Request payload read as raw bytes (`Path.read_bytes()`); JSON parsed from those same bytes.
- `request_hash = sha256(raw_request_bytes)` computed before parse.
- `request_bytes_b64 = base64(raw_request_bytes)` embedded in decision record.
- Both fields placed after `cap_registry_hash` in record header region.
- `normalized_args` dict built after tool_meta confirmed, capturing per-capability canonical values:
  - FS_WRITE: canonical_path, overwrite_requested, overwrite_intent, request_executable
  - FS_LIST: canonical_path, max_entries (clamped), include_hidden
  - FS_READ: canonical_path, max_bytes (requested), max_bytes_hard, offset, as_text

### verify-record.py
- Added `import base64`.
- New enforcement block: if record contains `request_hash` or `request_bytes_b64`,
  both must be present; decoded bytes must produce the stated `request_hash`.
- Older records without these fields pass (graceful degradation).

## T-CANON-001 (identical semantics, different byte encoding)

```
PASS: T-CANON-001a decision DENY (contains "policy_decision": "DENY")
PASS: T-CANON-001b decision DENY (contains "policy_decision": "DENY")
PASS: T-CANON-001a reason overwrite (contains RC-FS-OVERWRITE-DISALLOWED)
PASS: T-CANON-001b reason overwrite (contains RC-FS-OVERWRITE-DISALLOWED)
PASS: T-CANON-001 request_hash differs (values differ as expected)
PASS: T-CANON-001 normalized_args.canonical_path same
PASS: T-CANON-001 normalized overwrite_requested same
PASS: T-CANON-001a hash (record_hash verified)
PASS: T-CANON-001b hash (record_hash verified)
```

## T-CANON-002 (same path, max_bytes normalization diverges)

```
PASS: T-CANON-002a decision ALLOW (max_bytes=4096)
PASS: T-CANON-002b decision DENY  (max_bytes=99999 > hard limit 65536)
PASS: T-CANON-002b reason max_bytes (contains RC-FS-MAX-BYTES-EXCEEDED)
PASS: T-CANON-002 request_hash differs
PASS: T-CANON-002 normalized max_bytes differs
PASS: T-CANON-002a normalized max_bytes is 4096
PASS: T-CANON-002b normalized max_bytes is 99999
PASS: T-CANON-002 normalized_args.canonical_path same
PASS: T-CANON-002a hash (record_hash verified)
PASS: T-CANON-002b hash (record_hash verified)
Summary: pass=21 fail=0
```

## Regression

FS_WRITE: pass=12 fail=0
Poisoned intent: pass=14 fail=0
MCP smoke: PASS (DENY + ALLOW + tamper + fs_list + fs_read, fail-closed verified)
