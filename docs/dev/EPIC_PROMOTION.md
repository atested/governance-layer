# EPIC_PROMOTION.md

## Purpose
Define a sanctioned, auditable promotion workflow for moving vetted artifacts across roots without weakening the existing `FS_MOVE` cross-root deny invariant.

## Why `FS_MOVE` Cross-Root Must Stay Denied
- Cross-root moves are high-risk because they bypass normal boundary controls between trust zones.
- Existing `FS_MOVE` invariants enforce same-root source/destination to prevent implicit privilege escalation.
- Allowing arbitrary cross-root in `FS_MOVE` would blur policy intent and expand blast radius for a single capability.
- Therefore: `FS_MOVE` remains deny for any `src_root != dst_root`.

## Promotion Model (Distinct Capability)
Use a separate governed capability (or guarded procedure) named `FS_PROMOTE`, not `FS_MOVE`.

### Scope
- Only allow source roots and destination roots from an explicit allowlist matrix.
- Only allow promotion of artifact classes explicitly listed in policy.
- No wildcard paths; canonical absolute paths only.
- No recursive directory promotions unless explicitly enabled by policy.

### Required Intent Fields
- `intent.goal`: explicit promotion purpose.
- `intent.expected_outputs`: expected destination artifact(s).
- `intent.promotion_id`: unique operation identifier for audit correlation.
- `intent.src_root_id`: source root label from registry.
- `intent.dst_root_id`: destination root label from registry.
- `intent.src_path`: canonical source path.
- `intent.dst_path`: canonical destination path.
- `intent.src_content_hash_sha256`: hash of source bytes.
- `intent.allowed_artifact_class`: registry-defined artifact class.
- `intent.requested_by`: actor identity string (or service principal).

## Guarded Workflow
1. Normalize and validate intent fields.
2. Resolve canonical `src_path` and `dst_path`; reject hidden/traversal paths.
3. Verify `src_root_id -> dst_root_id` pair is explicitly allowed.
4. Verify source exists, is regular file, and hash matches `src_content_hash_sha256`.
5. Verify destination policy (path allowlist, overwrite policy, class constraints).
6. Re-check chain integrity before decision append.
7. Emit decision record with full promotion context and policy reasons.
8. Execute bounded copy+verify (copy bytes, re-hash destination, compare hashes).
9. Emit completion record with resulting destination hash/path metadata.
10. Re-verify chain and fail closed on any integrity anomaly.

## Invariants
- INV-PROMO-001: `FS_MOVE` cross-root remains denied in all cases.
- INV-PROMO-002: cross-root movement occurs only via `FS_PROMOTE` (or equivalent guarded path).
- INV-PROMO-003: source hash must match declared intent hash before promotion.
- INV-PROMO-004: destination hash must match source hash after promotion.
- INV-PROMO-005: both decision and completion records are present and linked.
- INV-PROMO-006: source/destination roots must be from explicit allowlist matrix.
- INV-PROMO-007: promotion is deny-by-default for unknown artifact class.

## Failure Modes and Reason Codes
- `RC-PROMO-ROOT-PAIR-DISALLOWED`: source/destination root pair not in allowlist.
- `RC-PROMO-SRC-MISSING`: source path missing at execution time.
- `RC-PROMO-SRC-TYPE-DISALLOWED`: source is not a regular file.
- `RC-PROMO-HASH-MISMATCH-SRC`: source bytes hash does not match declared hash.
- `RC-PROMO-HASH-MISMATCH-DST`: destination bytes hash does not match source hash after copy.
- `RC-PROMO-ARTIFACT-CLASS-DISALLOWED`: artifact class not permitted for promotion.
- `RC-PROMO-OVERWRITE-DISALLOWED`: destination exists and overwrite is disallowed.
- `RC-PROMO-PATH-DISALLOWED`: canonical path outside allowed base for selected root.
- `RC-PROMO-CHAIN-VERIFY-FAIL`: chain integrity failed pre/post append; operation fails closed.
- Determinism boundary: identical promotion inputs must emit stable fail markers and deterministic RC ordering.

## Required Tests
- T-PROMO-001: deny direct `FS_MOVE` cross-root attempt (invariant preservation).
- T-PROMO-002: deny `FS_PROMOTE` when root pair is not explicitly allowed.
- T-PROMO-003: deny when source hash does not match declared hash.
- T-PROMO-004: deny hidden/traversal source or destination paths.
- T-PROMO-005: allow valid promotion with matching source/destination hash and full records.
- T-PROMO-006: fail closed and quarantine on chain verification failure.
- T-PROMO-007: deny unapproved artifact class.
- T-PROMO-008: deny overwrite when policy disallows overwrite.

## Audit Expectations
- Every promotion attempt yields a decision record with:
  - normalized intent
  - root identifiers
  - canonical src/dst paths
  - request hash and source hash
  - reason codes on DENY
- Every successful promotion yields a completion record with:
  - destination hash verification result
  - final destination canonical path
  - linkage to original `promotion_id`
