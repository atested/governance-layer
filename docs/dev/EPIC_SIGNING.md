# EPIC_SIGNING.md
Phase 3 signing design: what is signed, canonical bytes, key management, verification, and failure modes.
Closes INV-005 for the GovLayer-core trust-grade claim path ("Trust-grade records are signed; verifier must validate chain + signatures").

---

## Context

Phase 2 deferred asymmetric signing. Core GovLayer signing semantics are now implemented:
`policy-eval.py` can emit signed `PolicyRecord`s, and `verify-record.py` / `verify-chain.py`
can validate them. The remaining purpose of this document is to define the intended trust-grade
mode semantics and boundary rules without inventing new ownership.

Non-goals: cryptographic library selection beyond integration interfaces; key rotation schedules;
multi-key or multi-party schemes.

---

## 1. Objects Signed

### 1.1 Decision records

Every decision record emitted to `decision-chain.jsonl` in trust-grade mode is signed at emission time by
`policy-eval.py → emit_record()`. Compatibility mode remains outside this claim path. The signing pre-image is defined in §2.

### 1.2 Capability registry binding

The `cap_registry_hash` field (already `"sha256:" + SHA256(raw registry bytes)`) binds each record
to a specific registry snapshot. No separate signature is applied to the registry itself in Phase 3.

### 1.3 Request bytes binding

The `request_hash` field (`"sha256:" + SHA256(request_bytes_b64 decoded)`) is already embedded in
the pre-image (§2) and therefore covered by the record signature.

---

## 2. Canonicalization Rules (exact bytes)

The signing pre-image is computed as follows — **identical to the existing `record_hash` pre-image**:

1. Take the full decision record `dict` as it will be emitted.
2. Set `record_hash` → `null` (JSON null).
3. Set `signature` → `null` (JSON null).
4. Serialize with: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`
   - Keys sorted lexicographically.
   - No spaces (compact separators).
   - No trailing newline.
   - `ensure_ascii=False`: Unicode passes through as-is.
5. Encode the resulting string as **UTF-8 bytes**. This byte string is the signing pre-image.

```
signing_preimage(record) =
    json.dumps(
        record | {record_hash: null, signature: null},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")
```

No additional normalization (e.g., NFC, whitespace stripping) is applied. Implementations must
use the same function already used for `record_hash`. Any deviation produces an unverifiable record.

The existing `record_hash` algorithm is unchanged:
```
record["record_hash"] = "sha256:" + sha256_hex(signing_preimage(record))
```

---

## 3. Signature Fields and Schema

Two fields are reserved in the decision record schema today. Phase 3 activates both.

| Field | Type | Phase 2 value | Phase 3 value |
|---|---|---|---|
| `signature` | `string \| null` | `null` | Base64url-encoded Ed25519 signature bytes (no padding) |
| `signing_key_id` | `string \| null` | `null` | Key identifier matching the signing key (see §3.2) |

### 3.1 Algorithm

**Ed25519** (RFC 8032).

- Input: `signing_preimage(record)` as defined in §2.
- Output: 64-byte deterministic signature.
- Encoded as base64url without padding (RFC 4648 §5, no `=`).

Rationale: deterministic (no nonce leakage), small keys/signatures (32/64 bytes), widely available
in Python (`cryptography` library), no algorithm agility needed at this tier.

### 3.2 `signing_key_id` format

Opaque ASCII string identifying the signing key. Recommended format:

```
ed25519:<hex_thumbprint>
```

where `hex_thumbprint` is the lowercase hex SHA-256 of the raw 32-byte public key.

Constraints: maximum 128 characters; no whitespace or control characters.

### 3.3 Emit-time field ordering

`emit_record()` must follow this order:

```
# Step 1: compute pre-image (record_hash and signature still null)
pre_image = signing_preimage(record)

# Step 2: sign
signature_bytes = ed25519_sign(private_key, pre_image)   # → 64 bytes
record["signature"] = base64url_encode(signature_bytes)  # no padding
record["signing_key_id"] = key_id

# Step 3: compute record_hash (pre-image still uses null for both fields)
record["record_hash"] = "sha256:" + sha256_hex(signing_preimage(record))
#   signing_preimage zeros out record_hash and signature → same null-form pre-image

# Step 4: emit to chain
```

`record_hash` covers the null-signature form. The signature also covers the null-signature form.
Both are computed over the same pre-image bytes.

---

## 4. Verification Steps

`verify-record.py` verification order (steps 1–3 unchanged from Phase 2; step 4 is new):

1. **Cap registry hash**: recompute `"sha256:" + SHA256(capability-registry.json raw bytes)`;
   compare to `cap_registry_hash`. FAIL on mismatch.

2. **Request hash**: decode `request_bytes_b64` from base64; recompute `"sha256:" + SHA256(decoded)`;
   compare to `request_hash`. FAIL on mismatch. (Skip only if both fields absent — legacy records.)

3. **Record hash**: compute `signing_preimage(record)` → `"sha256:" + SHA256(...)`;
   compare to `record_hash`. FAIL on mismatch.

4. **Signature** (Phase 3):
   a. If `signature` is `null`: FAIL in production mode; WARN in dev mode (see §6).
   b. If `signing_key_id` does not match the loaded key's thumbprint: FAIL immediately.
   c. Decode `signature` from base64url.
   d. Verify the 64-byte signature against `signing_preimage(record)` using Ed25519 and the
      public key identified by `signing_key_id`.
   e. FAIL if signature is invalid.

`verify-chain.py` is unchanged at the chain level (`prev_record_hash` link verification).
It must invoke per-record signature validation (step 4 above) for each record in Phase 3 mode.

Exit codes (no change to existing codes):
- `0` — all checks pass.
- `1` — verification failure (tamper or invalid signature).
- `2` — input error or configuration failure (unreadable key, invalid format).

---

## 5. Key Handling Assumptions

### 5.1 No secrets in repo

Private keys must never be committed. `.gitignore` already excludes `*.key`, `*.pem`, `*.p12`,
`keys/`, `secrets/`. This constraint is unconditional.

### 5.2 Runtime key loading

The signing key is loaded at runtime from the first of:

1. Path in `GOV_SIGNING_KEY_PATH` environment variable (PEM-encoded Ed25519 private key).
2. `~/.config/gov-layer/signing.key` (default dev path).

If neither is readable and Phase 3 signing is active, `emit_record()` fails closed: no record
is emitted and the tool call is blocked.

The verifying key is loaded from:

1. Path in `GOV_VERIFY_KEY_PATH` environment variable (PEM-encoded Ed25519 public key).
2. Derived from `GOV_SIGNING_KEY_PATH` if only the private key is available (dev convenience).

### 5.3 Dev environment

Single Ed25519 keypair. No HSM. No rotation in Phase 3.

Key generation reference (not normative):
```
openssl genpkey -algorithm ED25519 -out signing.key
openssl pkey -in signing.key -pubout -out signing.pub
```

### 5.4 Prod environment

Out of scope for Phase 3. The interface is unchanged; private key source (HSM, vault) is an
external concern. The `GOV_SIGNING_KEY_PATH` variable points to the appropriate loader.

### 5.5 Key-to-record binding

The verifier must reject any record where `signing_key_id` does not match the thumbprint of the
loaded public key. Records signed by an unknown key are treated as tampered.

---

## 6. Failure Modes (fail closed)

| Condition | Action |
|---|---|
| `signature` is `null` (Phase 3 active, prod mode) | FAIL — exit 1 |
| `signature` is `null` (Phase 3 active, dev mode) | WARN — print, continue |
| `signing_key_id` does not match loaded key thumbprint | FAIL — exit 1; do not attempt verify |
| Ed25519 signature bytes invalid (not 64 bytes or wrong format) | FAIL — exit 1 |
| Ed25519 signature verification fails | FAIL — exit 1 |
| Public key file unreadable at verify time | FAIL — exit 2; never silently skip |
| Private key file unreadable at emit time | FAIL closed — do not emit; block action |
| `record_hash` mismatch (existing check) | FAIL — exit 1; no change |

Policy: the verifier must never silently skip signature validation. Degraded mode (null signature,
missing key) must be explicitly operator-configured via `GOV_SIGNING_DEV_MODE=1`, not implicit.

---

## 7. INV-005 Linkage

**INV-005:** "Trust-grade records are signed; verifier must validate chain + signatures."

Current closure rule:
- Trust-grade operation is explicit via `GOV_SIGNING_REQUIRED=1`.
- Compatibility/degraded behavior remains available outside the trust-grade claim path and does not count toward INV-005 completion.

Phase 3 closes INV-005 for the trust-grade claim path by:

- Activating `signature` and `signing_key_id` fields at emit time (`policy-eval.py`).
- Extending `verify-record.py` to enforce signature validation as a hard failure.
- Extending `verify-chain.py` to invoke per-record signature validation.
- Extending `replay-record.py` to verify both the original record baseline and the replay-produced record through `verify-record.py` in trust-grade mode.

INVARIANTS_MAP.md INV-005 is therefore **Full** for the trust-grade claim path, with compatibility mode remaining an explicit non-claim operating mode.
