# Hot Shim: validate-proof-bundle + AAT Gate C

## Flags
- `AAT_SHIM_ENABLE=1`: enable Gate C shim hook (default disabled)
- `AAT_SHIM_STRICT=0|1`: advisory (`0`, default) or enforcing (`1`)
- `AAT_SHIM_LEDGER_PATH=<path>`: optional ledger path override

## Default behavior unchanged
With `AAT_SHIM_ENABLE` unset or not `1`, `system/scripts/validate-proof-bundle.sh` behavior is unchanged.

## Shim behavior
When enabled:
- Inputs are discovered deterministically in this order:
  1. `<bundle>/action_record.json` + `<bundle>/decision_record.json`
  2. `<bundle>/aat/action_record.json` + `<bundle>/aat/decision_record.json`
  3. `<bundle>/evidence/aat/action_record.json` + `<bundle>/evidence/aat/decision_record.json`
- Preferred producer location is `<bundle>/aat/`.
- If `action_record.json` or `decision_record.json` cannot be discovered as a pair:
  - strict `0`: prints `AAT_SHIM=SKIP INPUTS_MISSING` and continues success.
  - strict `1`: emits non-admissible shim result and exits nonzero.
- If Gate C returns `HARD_STOP`: exits nonzero.
- If Gate C returns `NON_ADMISSIBLE`:
  - strict `1`: exits nonzero.
  - strict `0`: advisory only, continues success.

## Stable output line
- `AAT_SHIM_INPUTS=FOUND path=<.|aat|evidence/aat>` or `AAT_SHIM_INPUTS=MISSING`
- `AAT_SHIM_RESULT=<STATUS> REASON_CODE=<CODE> LEDGER_APPENDED=<YES|NO>`
