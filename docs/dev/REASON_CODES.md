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

## Coverage follow-up note

- RCs marked with `No explicit RC assertion found in tests/` are expected to be closed by focused RC regression harness tasks (e.g., TASK_062..TASK_066).
