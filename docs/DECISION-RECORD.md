# Decision Record (v0.1)
Updated: 2026-02-15

A decision record is the canonical audit artifact emitted for every governed tool invocation.

## Required fields (minimum set)
1. `record_version`
2. `timestamp_utc`
3. `session_id`
4. `request_id`
5. `actor` (client identifier, not model identity)
6. `tool`
7. `capability_class`
8. `intent`
9. `policy_inputs`
10. `policy_decision` (ALLOW | DENY)
11. `policy_reasons` (machine-parsable codes + human text)
12. `tool_args_redacted` (or hash of full args if sensitive)
13. `evidence_refs` (hashes/paths to any evidence objects)
14. `prev_record_hash` (for hash chain)
15. `record_hash`
16. `signature` (over `record_hash`)
17. `signing_key_id`

## Intent object (embedded or referenced)
Minimum fields
1. `goal`
2. `constraints`
3. `requested_action`
4. `inputs` (references; avoid raw secrets)
5. `expected_outputs` (references)
6. `risk_level` (derived from tool capability metadata)

## Notes
- Determinism requirement: given the same `policy_inputs`, the `policy_decision` must be identical.
- If any nondeterminism is permitted, it must be explicitly represented as a field and forced into a quarantined class.
