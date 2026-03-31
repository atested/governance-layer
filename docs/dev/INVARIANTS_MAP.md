# INVARIANTS_MAP.md
Maps each invariant (INV-001–008) to its enforcement location(s) and test coverage.
Source of invariant text: docs/INVARIANTS.md.

---

## Map

| INV | Statement | Enforcement file / function | Test IDs | Gap |
|-----|-----------|----------------------------|----------|-----|
| INV-001 | No privileged action without a decision record. | `mcp/server.py` → `governed_tool()`: verify→append→verify wraps every tool call; action callable is only invoked after ALLOW decision is recorded and chain re-verified. | T-FS-001..004, T-DELETE-001..004, T-MKDIR-001..002, T-MOVE-001..004 (all verify record present) | No test exercises action-block path when record creation itself fails (integration-only). |
| INV-002 | No decision record without a completed policy evaluation. | `scripts/policy-eval.py` → `main()`: `emit_record()` is only called after all enforcement checks run and `policy_decision` is set; record is never emitted mid-evaluation. | All T-* tests (every test invokes policy-eval and checks `policy_decision` field). | None. |
| INV-003 | No policy evaluation without tool capability metadata. | `scripts/policy-eval.py` → `load_internal_registry()` (fails closed on unreadable registry); tool lookup denies with `RC-UNKNOWN-TOOL` if not in registry; `cap_registry_hash` bound to every record. | T-POISON-001 (RC-UNKNOWN-TOOL on injected tool), all positive tests (registry load required). | None. |
| INV-004 | Logs are append-only and tamper-evident via hash chaining. | `scripts/verify-chain.py` → sequential `prev_record_hash` validation; `mcp/server.py` → `_verify_chain()` called before and after every append. | T-REPLAY-001..004, `tests/run-chain-tests.sh` (tamper detection test confirms hash mismatch detected). | Edge cases (binary truncation, partial-write) not explicitly tested. |
| INV-005 | Trust-grade records are signed; verifier must validate chain + signatures. | `scripts/policy-eval.py` → emits signed PolicyRecords and fails closed in `GOV_SIGNING_REQUIRED=1` mode when signing is impossible; `scripts/verify-record.py` → validates `record_hash`, `signing_key_id`, and signatures; `scripts/verify-chain.py` → validates chain links and per-record signature checks through `verify-record.py`; `scripts/replay-record.py` → trust-grade replay verifies both the original record baseline and the replay-produced record through `verify-record.py`. | T-REPLAY-001..004, T-CANON-001..002, `tests/test_signing_emit.sh`, `tests/test_verify_signatures.sh`, `tests/test_signing_required_mode.sh`, `tests/test_replay_trust_grade_mode.sh` | Compatibility mode remains available outside the trust-grade claim path and is intentionally non-counting for INV-005. |
| INV-006 | Any denial must include machine-parsable reason codes. | `scripts/policy-eval.py` → `add_reason()` + `finalize_reasons()`: every DENY path calls these; `REASON_ORDER` enforces deterministic precedence. | T-FS-001..004, T-DELETE-002..004, T-MKDIR-002, T-MOVE-002..004, T-POISON-001..003, T-POISON-DELETE-001..002, T-POISON-MKDIR-001..002, T-POISON-MOVE-001..002. | None. |
| INV-007 | Any redaction must be explicit; never silently drop args/evidence. | `scripts/policy-eval.py`: `tool_args_redacted` field documents captured args; content replaced by `content_hash`; `request_bytes_b64` embeds full request; `untrusted_inputs` explicitly logs cap_cfg / registry-path steering attempts. | T-POISON-001..003, T-POISON-DELETE-001..002, T-POISON-MKDIR-001..002, T-POISON-MOVE-001..002 (all assert `untrusted_inputs` populated). | None. |
| INV-008 | Replay verifier must reproduce policy outcomes for stored inputs. | `scripts/replay-record.py` → verifies the original record baseline, re-runs `policy-eval.py` on stored `request_bytes_b64`, verifies the replay-produced record, and compares `policy_decision`, `reason_codes` (ordered), `tool`, `cap_registry_hash`, `normalized_args`, and `coverage_stamp`. Exits 2 on request hash mismatch or invalid trust-grade replay output (fail-closed). | T-REPLAY-001..015, T-CANON-001..002, `tests/test_coverage_stamp_replay.sh`, `tests/test_replay_audit_report.sh`, `tests/test_replay_trust_grade_mode.sh` | None. |

---

## Coverage summary

| Status | Count | INVs |
|--------|-------|------|
| Full | 7 | INV-002, INV-003, INV-004, INV-005, INV-006, INV-007, INV-008 |
| Partial (gap noted) | 1 | INV-001 |
| No coverage | 0 | — |

### Active gaps

- **INV-001**: No test exercises the action-blocking path when `_append_decision` or `_verify_chain` raises (fail-closed on record failure). Covered operationally but not by an automated test case.
- **Determinism guard**: multi-reason DENY paths should keep stable reason-code ordering; regression tests should assert order explicitly when adding new checks.
