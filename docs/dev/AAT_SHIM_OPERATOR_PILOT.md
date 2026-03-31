# AAT Shim Operator Pilot

This pilot provides an operator-controlled workflow to run the AAT shim on a chosen proof bundle without editing hot scripts.

## 1) Stage AAT objects into a proof bundle

Preferred layout is `<bundle>/aat/`.

```bash
python3 scripts/aat_stage_into_proof_bundle.py \
  --bundle-dir <proof_bundle_dir> \
  --aat-dir <source_aat_dir>
```

Stable output:

- `AAT_STAGE=PASS|FAIL`
- `COPIED_FILES=<count>`
- `DEST=aat/`

## 2) Run validate-proof-bundle with shim

```bash
bash scripts/run_validate_proof_bundle_with_aat_shim.sh \
  --bundle-dir <proof_bundle_dir> \
  --strict 0
```

Use `--strict 1` for fail-closed non-admissible behavior.

The runner prints shim lines only:

- `AAT_SHIM_INPUTS=...`
- `AAT_SHIM_RESULT=...`

## Strict vs non-strict

- `--strict 1`: `NON_ADMISSIBLE` from Gate C exits nonzero.
- `--strict 0`: `NON_ADMISSIBLE` is advisory and validate-proof-bundle exits success.

This pilot is backward compatible and keeps default behavior unchanged when shim flags are not enabled.
