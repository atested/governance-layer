# AAT Shim Proof-Bundle Input Convention

This document defines deterministic input discovery for the AAT shim in `system/scripts/validate-proof-bundle.sh`.

## Required inputs

Both files are required:

- `action_record.json`
- `decision_record.json`

Partial presence is treated as inputs missing.

## Preferred producer layout

Writers should place AAT inputs under:

- `<bundle>/aat/action_record.json`
- `<bundle>/aat/decision_record.json`

Keep the supporting AAT sidecars in the same directory when Gate C execution is expected.

## Backward-compatible discovery order

The shim checks these locations in this exact order:

1. `<bundle>/action_record.json` and `<bundle>/decision_record.json`
2. `<bundle>/aat/action_record.json` and `<bundle>/aat/decision_record.json`
3. `<bundle>/evidence/aat/action_record.json` and `<bundle>/evidence/aat/decision_record.json`

## Shim output line

When `AAT_SHIM_ENABLE=1`, shim emits one deterministic input-discovery line:

- Found: `AAT_SHIM_INPUTS=FOUND path=<relative_subpath>`
- Missing: `AAT_SHIM_INPUTS=MISSING`

`path` values are stable:

- `.` for root
- `aat`
- `evidence/aat`
