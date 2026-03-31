# AAT v0 Profiles

This document defines the deterministic profile contract for AAT v0.

## Available profiles

- `CORE_GENERIC` (default)
  - Enforcing checks: `K1,K2,K3,K4,K5,M1`
  - Report-only checks: `P1,P2,C1,C2,C3`
- `TOOL_EXEC` (first profile expansion)
  - Inherits `CORE_GENERIC`
  - Additional enforcing checks: `C1,C2`
  - Effective enforcing checks: `K1,K2,K3,K4,K5,M1,C1,C2`

## Selection order

Profile selection is explicit and deterministic:

1. If `--profile <NAME>` is provided to `scripts/aat_main.py`, it is used.
2. Otherwise, `method_binding.action_kind` is used.
3. If missing, fallback is `CORE_GENERIC`.

Unknown profile names are fail-closed with nonzero exit.

## How to select

Direct orchestrator invocation:

```bash
python3 scripts/aat_main.py \
  --bundle-dir system/tests/fixtures/aat/golden_pass/tool_exec_profile \
  --schema-dir system/schemas \
  --profile TOOL_EXEC
```

Gate wrapper invocation:

```bash
system/scripts/aat-admissibility-gate.sh \
  --action-bundle-dir system/tests/fixtures/aat/golden_fail/tool_exec_profile_c1_enforced \
  --schema-dir system/schemas \
  --repo-root . \
  --profile TOOL_EXEC
```

## Operational meaning

- `CORE_GENERIC` is the stable baseline and remains the default.
- `TOOL_EXEC` raises strictness by enforcing contradiction and evidence-integrity checks (`C1`,`C2`) as admissibility gates instead of report-only signals.
