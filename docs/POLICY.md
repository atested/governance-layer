# Policy Rules (v0.1)
Updated: 2026-02-15

> **v3 note:** The API governance proxy uses `capabilities/policy-rules.json`
> for action-based policy evaluation (action type, confidence tier, scope,
> target path checks). The capability-class rules below (`FS_WRITE`, etc.)
> applied to the MCP server surface (archived D-203). The same principles
> apply: deterministic evaluation, fail-closed posture, bounded scope. See
> [docs/design/atested-v3-design.md](design/atested-v3-design.md).

This file is the human-readable source of policy intent.
Implementation should be deterministic.

## Default posture
1. Default deny for any tool without capability metadata.
2. Default deny for any intent missing required fields.
3. Deny if requested action exceeds declared capability bounds.

## Example rule structure
- RULE-ID
- Condition (deterministic)
- Decision (ALLOW/DENY)
- Reason codes
- Required evidence references (if any)

## Placeholder rules
POL-001 Deny unknown tools.
POL-002 Deny malformed intent.
POL-003 Deny if tool args include forbidden paths/patterns (capability-specific).

## Filesystem write (Phase 1)

### Capability class
- `capability_class`: `FS_WRITE`

### Allowlist boundary (Option A)
- Allowed base directory:
  - `<REPO_ROOT>/`
- Default deny for any write target that is not under the allowed base directory after canonicalization.

### Canonicalization requirements
- The policy engine MUST canonicalize the requested path before evaluation.
- Deny if canonicalization fails.
- Deny if the canonical path is not under the allowlisted base directory.
- Deny any traversal or escape attempt (including `..` segments or symlink escapes).

### Hidden paths
- Deny any write where any path segment begins with `.` unless explicitly allowlisted (no hidden allowlists in Phase 1).

### Overwrite semantics
- Default deny overwriting existing files.
- Overwrite is permitted only if BOTH are true:
  1. `intent.constraints.overwrite == true` (explicit)
  2. The policy rule for the target path allows overwrite
- If overwrite is allowed, the decision record MUST state that overwrite was permitted.

### Executable outputs
- Deny writes that attempt to:
  1. Write into known executable locations, or
  2. Set executable permissions (`chmod +x` or equivalent), or
  3. Create or modify files intended to be executed directly
- Phase 1 posture: no executable creation.

### Required intent fields for FS_WRITE
- Deny if missing:
  - `intent.goal`
  - `intent.expected_outputs`

### Required decision record properties (FS_WRITE)
- The decision record MUST include:
  - `tool` and `capability_class`
  - `policy_decision` and machine-parsable `policy_reasons`
  - the canonical path (or a hash if path is sensitive; Phase 1 allows path in clear)

### Reason codes (machine-parsable)
- `RC-FS-PATH-DISALLOWED`
- `RC-FS-HIDDEN-PATH`
- `RC-FS-PATH-TRAVERSAL`
- `RC-FS-OVERWRITE-DISALLOWED`
- `RC-FS-EXECUTABLE-DISALLOWED`
- `RC-FS-MISSING-INTENT-FIELDS`

### Reason code multiplicity and precedence
- The policy evaluator MAY emit multiple reason codes for a single request.
- Reason codes MUST be emitted in the following fixed precedence order (Phase 1):
  1. RC-FS-MISSING-INTENT-FIELDS
  2. RC-FS-PATH-TRAVERSAL
  3. RC-FS-PATH-DISALLOWED
  4. RC-FS-HIDDEN-PATH
  5. RC-FS-OVERWRITE-DISALLOWED
  6. RC-FS-EXECUTABLE-DISALLOWED
- The evaluator MUST deduplicate reason codes (no repeats).
- ALLOW occurs only when the reason-code list is empty.


## FS_LIST

### Purpose
Govern directory listing requests (names/types only) under the same allowlist and traversal/hidden-path rules as FS_WRITE.

### Decision model
FS_LIST uses deterministic policy evaluation and emits a Decision Record v0.1.
If policy decision is DENY, no listing occurs.

### Reason codes (FS_LIST)
- RC-FS-MISSING-INTENT-FIELDS
- RC-FS-PATH-TRAVERSAL
- RC-FS-PATH-DISALLOWED
- RC-FS-HIDDEN-PATH
- RC-FS-NOT-A-DIRECTORY
- RC-FS-INCLUDE-HIDDEN-DISALLOWED

### Precedence (highest to lowest)
1. RC-FS-MISSING-INTENT-FIELDS
2. RC-FS-PATH-TRAVERSAL
3. RC-FS-PATH-DISALLOWED
4. RC-FS-HIDDEN-PATH
5. RC-FS-INCLUDE-HIDDEN-DISALLOWED
6. RC-FS-NOT-A-DIRECTORY

Notes:
- FS_LIST should not invent ad hoc reason codes in the tool action. Policy decisions must come from policy-eval.py.
- Tool action may still return operational errors (e.g., filesystem race) separately from policy reasons.


## FS_READ

### Purpose
Govern file reads under allowlist, traversal, and hidden-path restrictions, with strict byte caps to reduce leakage risk.

### Reason codes (FS_READ)
- RC-FS-MISSING-INTENT-FIELDS
- RC-FS-PATH-TRAVERSAL
- RC-FS-PATH-DISALLOWED
- RC-FS-HIDDEN-PATH
- RC-FS-NOT-A-FILE
- RC-FS-MAX-BYTES-EXCEEDED

### Precedence (highest to lowest)
1. RC-FS-MISSING-INTENT-FIELDS
2. RC-FS-PATH-TRAVERSAL
3. RC-FS-PATH-DISALLOWED
4. RC-FS-HIDDEN-PATH
5. RC-FS-MAX-BYTES-EXCEEDED
6. RC-FS-NOT-A-FILE

Notes:
- FS_READ responses may include content, but must be capped and always include content_hash_sha256.
- Tool action may return operational errors separately from policy reasons (races, permissions).

