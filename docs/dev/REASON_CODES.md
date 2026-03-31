# REASON_CODES.md

Reason-code index from `scripts/policy-eval.py`.

| RC | where | trigger | related tests |
|---|---|---|---|
| `RC-UNKNOWN-TOOL` | `scripts/policy-eval.py: main()` tool lookup | Requested `tool` is not registered in capability registry. | `tests/test_poisoned_intent.sh` (`T-POISON-001`) |
| `RC-FS-PATH-DISALLOWED` | `scripts/policy-eval.py: main()`, `eval_fs_path_policy()` | Canonical path outside `allow_base_dirs`, missing/invalid path, or `FS_MOVE` missing `src_path`/`dst_path`. | `tests/run-fs-write-tests.sh` (`T-FS-001`), `tests/test_poisoned_intent.sh`, `tests/test_fs_mkdir.sh`, `tests/test_fs_move.sh` |
| `RC-FS-HIDDEN-PATH` | `scripts/policy-eval.py: main()`, `eval_fs_path_policy()` | Any path segment starts with `.` while hidden paths are denied. | `tests/run-fs-write-tests.sh` (`T-FS-002`, `T-FS-003`) |
| `RC-FS-PATH-TRAVERSAL` | `scripts/policy-eval.py: main()`, `eval_fs_path_policy()` | Raw path contains traversal patterns (`../`, `/..`) for single-path tools or `FS_MOVE` src/dst. | `tests/run-fs-write-tests.sh` (`T-FS-003`) |
| `RC-FS-OVERWRITE-DISALLOWED` | `scripts/policy-eval.py: main()` | Overwrite denied by policy (FS_WRITE overwrite mismatch) or `FS_MOVE` overwrite requested while `overwrite_allowed=false`. | `tests/run-fs-write-tests.sh` (`T-FS-004`), `tests/test_canonical_request.sh`, `tests/test_replay.sh`, `tests/test_fs_move.sh` |
| `RC-FS-EXECUTABLE-DISALLOWED` | `scripts/policy-eval.py: main()` | `request_executable=true` when executable outputs are denied. | No explicit RC assertion found in `tests/` |
| `RC-FS-NOT-A-DIRECTORY` | `scripts/policy-eval.py: main()` FS_LIST branch | FS_LIST canonical path exists check fails `isdir`. | No explicit RC assertion found in `tests/` |
| `RC-FS-INCLUDE-HIDDEN-DISALLOWED` | `scripts/policy-eval.py: main()` FS_LIST branch | FS_LIST called with `include_hidden=true`. | No explicit RC assertion found in `tests/` |
| `RC-FS-NOT-A-FILE` | `scripts/policy-eval.py: main()` FS_READ branch, `eval_fs_read()` | FS_READ canonical path fails `isfile`. | No explicit RC assertion found in `tests/` |
| `RC-FS-MAX-BYTES-EXCEEDED` | `scripts/policy-eval.py: main()` FS_READ branch, `eval_fs_read()` | Requested `max_bytes` exceeds `max_bytes_hard`. | `tests/test_canonical_request.sh` (`T-CANON-002b`) |
| `RC-FS-MISSING-INTENT-FIELDS` | `scripts/policy-eval.py: main()`, `eval_fs_read()` | Missing required intent fields (`intent.goal` or `intent.expected_outputs`), or missing FS_READ `args.path`. | No explicit RC assertion found in `tests/` |
| `RC-FS-CROSS-ROOT-DISALLOWED` | `scripts/policy-eval.py: main()` FS_MOVE branch | FS_MOVE src and dst resolve under different allowlist roots while `cross_root_allowed=false`. | `tests/test_fs_move.sh` (`T-MOVE-003`) |
| `RC-MSG-UNKNOWN-SURFACE-BINDING` | `scripts/policy-eval.py: main()` messaging branch | `surface_binding_id` missing from explicit messaging map. | `tests/test_msg_policy_surface.sh` (`T-MSG-MAP-001`) |
| `RC-MSG-MAPPING-VERSION-MISMATCH` | `scripts/policy-eval.py: main()` messaging branch | Request `mapping_version` disagrees with mapped entry. | `tests/test_msg_policy_surface.sh` (`T-MSG-MAP-002`) |
| `RC-MSG-CAPABILITY-MAPPING-MISMATCH` | `scripts/policy-eval.py: main()` messaging branch | Request tool/capability disagrees with mapped capability class. | `tests/test_msg_policy_surface.sh` (`T-MSG-MAP-003`) |
| `RC-MSG-CANONICAL-DESTINATION-MISSING` | `scripts/policy-eval.py: main()` messaging branch | Canonical destination object missing or malformed. | `tests/test_msg_policy_surface.sh` (`T-MSG-DEST-002`) |
| `RC-MSG-CANONICAL-DESTINATION-KIND-MISMATCH` | `scripts/policy-eval.py: main()` messaging branch | Canonical destination kind disagrees with mapped destination kind. | `tests/test_msg_policy_surface.sh` (`T-MSG-DEST-003`) |
| `RC-MSG-DESTINATION-CLASS-DISALLOWED` | `scripts/policy-eval.py: main()` messaging branch | Raw destination audit class is not allowed for the selected binding. | `tests/test_msg_policy_surface.sh` (`T-MSG-RC-003`) |
| `RC-MSG-DESTINATION-DISALLOWED` | `scripts/policy-eval.py: main()` messaging branch | Canonical destination identity falls outside mapped destination scope. | `tests/test_msg_policy_surface.sh` (`T-MSG-RC-002`) |
| `RC-MSG-RAW-DESTINATION-MISSING` | `scripts/policy-eval.py: main()` messaging branch | Raw destination audit evidence absent or malformed. | Coverage via messaging branch fixture matrix |
| `RC-MSG-OPAQUE-PAYLOAD-MISSING` | `scripts/policy-eval.py: main()` messaging branch | Opaque payload handle metadata absent or malformed. | Coverage via messaging branch fixture matrix |
| `RC-MSG-TRANSPORT-UNAUTHORIZED` | `scripts/policy-eval.py: main()` messaging branch | Opaque payload transport kind is not allowed for the selected binding. | `tests/test_msg_policy_surface.sh` (`T-MSG-RC-004`) |
| `RC-MSG-PAYLOAD-SIZE-EXCEEDED` | `scripts/policy-eval.py: main()` messaging branch | Opaque payload byte length exceeds mapped maximum. | `tests/test_msg_policy_surface.sh` (`T-MSG-RC-005`) |
| `RC-MSG-RATE-EXCEEDED` | `scripts/policy-eval.py: main()` messaging branch | Structural rate-window count exceeds mapped maximum. | `tests/test_msg_policy_surface.sh` (`T-MSG-RC-006`) |
| `RC-MSG-CONTENT-FIELD-PRESENT` | `scripts/policy-eval.py: main()` messaging branch | Evaluator-facing messaging request includes content-bearing fields. | `tests/test_msg_policy_surface.sh` (`T-MSG-CONTENT-002`) |
| `RC-MSG-REPLY-CONTEXT-MISSING` | `scripts/policy-eval.py: main()` messaging branch | `MSG_REPLY` missing structural reply context. | `tests/test_msg_policy_surface.sh` (`T-MSG-REPLY-002`) |
| `RC-MSG-REPLY-TARGET-MISMATCH` | `scripts/policy-eval.py: main()` messaging branch | Reply target identity disagrees with canonical destination identity. | `tests/test_msg_policy_surface.sh` (`T-MSG-REPLY-003`) |
| `RC-MSG-DECISION-ALPHABET-VIOLATION` | `scripts/policy-eval.py: main()` messaging branch | Messaging map attempts a non-`ALLOW`/`DENY` decision alphabet. | `tests/test_msg_policy_surface.sh` (`T-MSG-DECISION-001`) |
| `RC-MSG-MISSING-INTENT-FIELDS` | `scripts/policy-eval.py: main()` messaging branch | Required messaging intent fields absent. | `tests/test_msg_policy_surface.sh` (`T-MSG-RC-001`) |

## Coverage follow-up note

- RCs marked with `No explicit RC assertion found in tests/` are expected to be closed by focused RC regression harness tasks (e.g., TASK_062..TASK_066).
