# Changelog
## v0.1 (2026-02-15)
- Added initial artifact spine: roadmap, scope, threat model, decision record, invariants, policy, test suite.
- Added operational state templates.

## v0.1 (2026-02-15) — Filesystem write policy (Phase 1)
- Added concrete FS_WRITE policy section with repo-only allowlist boundary.
- Added reason codes for deterministic denials.
- Added 5 filesystem-write bypass tests mapped to reason codes.

## v0.1 (2026-02-16) — Phase 2B.1 (capability registry binding)
- Bound every decision record to the capability registry version via `cap_registry_hash` (sha256 over registry bytes).
- Policy evaluation now loads the internal registry for enforcement and records untrusted external registry inputs for audit.
- Verification/replay flows enforce consistency of request and registry binding metadata.

## v0.1 (2026-02-16) — Phase 2C.1 (POISON_MOVE hardening + RC coverage)
- Added `FS_MOVE` policy test coverage including `T-MOVE-*` and `T-POISON-MOVE-*` cases.
- Added denial coverage for poisoned `cap_cfg` injection and permissive `argv[1]` registry steering.
- Enforced deterministic deny reasons for disallowed move paths/cross-root/overwrite constraints.

## v0.1 (2026-02-16) — Phase 2C.2 (governed FS_MOVE tool)
- Added governed MCP `fs_move` tool wired through `governed_tool` (verify → append → verify).
- Enforced dual-path checks for `src_path` and `dst_path`, with cross-root deny preserved (`cross_root_allowed=false`).
- Enforced overwrite cap behavior (`overwrite_allowed=false`) and destination existence checks.
- Server-side move execution uses `shutil.move` only after policy allow decision and canonical-path validation.
