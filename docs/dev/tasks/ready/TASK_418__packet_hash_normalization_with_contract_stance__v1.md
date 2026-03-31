1. PURPOSE

- Normalize `packet_hash` to one canonical machine shape across the current-main proof-bundle summary surfaces.
- Implement Greg's `NORMALIZE NOW` decision with an explicit version/compatibility stance instead of mutating an additive-only `v1` schema in place.

2. CURRENT_MAIN_DIVERGENCE

- `scripts/proof-packet.py verify --summary-json` currently emits `proof_packet_verify_summary_v1` with `packet_hash` as a string: `sha256:<hex>`.
- `system/scripts/validate-proof-bundle.sh --summary-json` currently emits `validate_proof_bundle_summary_v1` with `packet_hash` as an object: `{"algo":"sha256","value":"<hex>"}`.
- Current-main contract docs mark `proof_packet_verify_summary_v1` as additive-only within `v1`, so retyping its existing `packet_hash` field in place would be untruthful.

3. CANONICAL_PACKET_HASH_SHAPE

- Canonical shape:
```json
{"algo":"sha256","value":"<lowercase-hex>"}
```
- `algo` is the literal string `sha256`.
- `value` is the lowercase hex SHA-256 digest of `proof_packet.tar`, with no `sha256:` prefix.

4. CONTRACT_AND_MIGRATION_STANCE

- This is a direct producer-contract replacement at the proof-packet verifier summary surface.
- `proof_packet_verify_summary_v1` remains accepted by `validate-proof-bundle.sh` during a bounded compatibility window.
- Current-main producers now emit `proof_packet_verify_summary_v2`.
- Current-main docs and producer-facing tests become the new single source of truth for emitted proof-packet verifier summaries.
- No compatibility shim is retained on the producer side; compatibility is consumer-side only in the validator.

5. TARGET_FILES_OR_SURFACES

- `scripts/proof-packet.py`
- `system/scripts/validate-proof-bundle.sh`
- `tests/test_proof_packet_summary_json.sh`
- `tests/test_external_ci_smoke.sh`
- `tests/test_proof_packet_contract_enforcement.sh`
- `tests/test_proof_packet_manifest_verify.sh`
- `tests/test_proof_packet_roundtrip_smoke.sh`
- `tests/test_validate_proof_bundle.sh`
- `tests/test_external_summary_contract_parity_audit.sh`
- `docs/EXTERNAL_CONTRACTS.md`
- `docs/dev/ATTESTATION_SPEC.md`
- `docs/DISTRIBUTION.md`
- `README.md`
- `docs/TEST-SUITE.md`

6. IMPLEMENTATION

- Change `scripts/proof-packet.py` verifier-summary emission to `proof_packet_verify_summary_v2`.
- Normalize emitted `packet_hash` to the canonical object shape using the tar SHA-256 hex already computed by current main.
- Update `validate-proof-bundle.sh` to accept both `proof_packet_verify_summary_v1` and `proof_packet_verify_summary_v2`.
- Keep `validate_proof_bundle_summary_v1` unchanged because it already uses the canonical `packet_hash` object shape.
- Update only the docs and tests that describe or assert the live producer/validator contract.

7. VERIFICATION

- Verify live proof-packet verifier summaries now emit:
  - `report_version == proof_packet_verify_summary_v2`
  - `packet_hash == {"algo":"sha256","value":"<lowercase-hex>"}`
- Verify validator acceptance of current-main proof-bundles still passes with the normalized summary surface.
- Verify validator-generated `validate_proof_bundle_summary_v1` still emits the same canonical `packet_hash` object shape.
- Verify current docs and contract-facing tests name `proof_packet_verify_summary_v2` as the emitted schema.
- Verify no untouched surface is falsely claimed normalized; legacy `proof_packet_verify_summary_v1` is accepted only as validator compatibility input.

8. STOP_BOUNDARIES

- Stop if current-main evidence reveals additional emitted summary surfaces that also carry divergent `packet_hash` shapes and cannot be handled in this tranche.
- Stop if a truthful canonical shape cannot be chosen without contradicting current-main contract docs.
- Stop if normalization would require broader proof-bundle contract redesign beyond the bounded `v1`-accept / `v2`-emit stance.
