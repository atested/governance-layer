# SIGNING_GUIDE.md

Practical guide to Phase 3 asymmetric signing: key generation, configuration, verification, and troubleshooting.

**Status**: [IMPLEMENTED] - GovLayer-core trust-grade signing emit and verifier closure are implemented. Compatibility mode remains explicit outside the trust-grade claim path.

**See also**:
- [EPIC_SIGNING.md](EPIC_SIGNING.md) - Technical specification and design rationale
- [ATTESTATION_SPEC.md](ATTESTATION_SPEC.md) - Complete attestation architecture

---

## Quickstart

### Generate signing key

```bash
# Install cryptography library
pip install 'cryptography>=43.0.0,<44'

# Generate Ed25519 signing key
python3 - <<'PY'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pathlib import Path
import hashlib

key = Ed25519PrivateKey.generate()
pem = key.private_key_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

path = Path.home() / ".config" / "gov-layer" / "signing.key"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(pem)
path.chmod(0o600)

pub = key.public_key()
pub_bytes = pub.public_bytes(encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw)
key_id = "ed25519:" + hashlib.sha256(pub_bytes).hexdigest()

print(f"Signing key created: {path}")
print(f"Key ID: {key_id}")
PY
```

### Sign a decision

```bash
# policy-eval.py automatically signs if signing key exists
python3 scripts/policy-eval.py /path/to/intent.json > record.json

# Verify signature field is populated
jq -r '.signature // "MISSING"' record.json
jq -r '.signing_key_id // "MISSING"' record.json
```

### Verify a signed record

```bash
# Single record verification
python3 scripts/verify-record.py record.json

# Chain verification (verifies all records + signatures)
python3 scripts/verify-chain.py decision-chain.jsonl
```

---

## Key Management

### Key locations (priority order)

1. **`GOV_SIGNING_KEY_PATH` environment variable** - Explicit path override
2. **`~/.config/gov-layer/signing.key`** - Default location
3. **No key found**
   - With `GOV_SIGNING_REQUIRED=1`: emit fails closed
   - Without trust-grade mode: compatibility mode emits unsigned records

### Key format

- **Algorithm**: Ed25519 (RFC 8032)
- **Encoding**: PEM (PKCS#8), unencrypted
- **Permissions**: 0600 (user read/write only)

**Example PEM structure**:
```
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIB... (base64 bytes) ...
-----END PRIVATE KEY-----
```

### Key ID format

```
ed25519:<sha256_hex_thumbprint>
```

- `<sha256_hex_thumbprint>`: lowercase hex SHA-256 of the raw 32-byte Ed25519 public key
- Maximum length: 128 characters
- No whitespace or control characters

**Example**: `ed25519:a3f2d1c5b8e9...`

### Key rotation (future)

Phase 3 supports single-key signing. Multi-key rotation will be specified in Phase 4.

**Current workaround**:
1. Generate new key at new path
2. Set `GOV_SIGNING_KEY_PATH` to new path
3. Archive old key securely
4. Old records remain verifiable with old key; new records use new key

---

## Signing Semantics

### What is signed

Every decision record emitted by `policy-eval.py → emit_record()` in trust-grade mode is signed at emission time. Compatibility mode remains outside this claim path.

**Signed fields** (via signing preimage):
- All policy evaluation inputs and outputs
- `cap_registry_hash` (binds to registry snapshot)
- `request_hash` (binds to request bytes)
- `record_version`, `tool`, `capability_class`
- `policy_decision`, `policy_reasons` (codes only, not detail text)
- `normalized_args` (path-redacted)
- `intent` (with `expected_outputs` path-redacted)

**NOT signed** (excluded from preimage):
- `timestamp_utc` (volatile)
- `session_id`, `request_id` (volatile)
- `prev_record_hash` (chain link, not attestation)
- `record_hash`, `signature`, `signing_key_id` (self-referential)
- `request_bytes_b64` (bound via `request_hash` instead)
- `evidence_refs`, `untrusted_inputs` (audit metadata, not policy)
- Path expansions (`canonical_path`, `allow_base_dirs`)
- Reason `detail` fields (codes only)

**Rationale**: The preimage captures deterministic policy evaluation semantics. Machine-specific paths, timestamps, and audit metadata are excluded to ensure reproducibility and cross-machine verification.

See [EPIC_SIGNING.md §2](EPIC_SIGNING.md) for exact canonicalization rules.

### Signature encoding

- **Input**: `signing_preimage(record)` (canonical JSON as UTF-8 bytes)
- **Algorithm**: Ed25519 deterministic signature
- **Output**: 64-byte signature
- **Encoding**: Base64url without padding (RFC 4648 §5, no `=` chars)

**Example**:
```json
{
  "signature": "Xy9kL3RtYWluLXNpZ25hdHVyZS1oZXJl...",
  "signing_key_id": "ed25519:a3f2d1c5b8e9...",
  "record_hash": "sha256:4f8a3c2d..."
}
```

### Emit-time ordering

`emit_record()` computes fields in this order:

1. Compute signing preimage (with `signature` and `record_hash` as `null`)
2. Sign preimage → populate `signature` and `signing_key_id`
3. Compute `record_hash` from same preimage (still has `null` for both fields)
4. Emit record to chain

Both `signature` and `record_hash` cover the same canonical bytes.

---

## Verification

### Single record verification

```bash
python3 scripts/verify-record.py <record.json>
```

**Verification steps** (Phase 3):
1. ✓ Cap registry hash matches `capability-registry.json`
2. ✓ Request hash matches `request_bytes_b64` decoded
3. ✓ Record hash matches recomputed signing preimage
4. ✓ Signature is valid for signing preimage using public key identified by `signing_key_id`

**Exit codes**:
- `0`: All checks passed
- `1`: Verification failed (signature invalid, hash mismatch, etc.)
- `2`: Fatal error (missing files, invalid JSON, etc.)

### Chain verification

```bash
python3 scripts/verify-chain.py <chain.jsonl>
```

**Additional checks**:
- `prev_record_hash` links are valid (each record references previous record's `record_hash`)
- All records in chain pass single-record verification (including signatures)
- No gaps or ordering violations

### Replay verification

```bash
python3 scripts/replay-record.py <record.json>
```

**Replay guarantees**:
- The original record baseline is verified through `verify-record.py` before replay proceeds
- `policy-eval.py` is re-run on the stored request bytes
- The replay-produced record is verified through `verify-record.py`
- Deterministic invariants are compared for decision, reason codes, tool, registry binding, normalized args, and coverage stamp
- In trust-grade mode, replay fails closed if either the original record or the replay-produced record is unsigned or otherwise unverifiable

### Phase 2 compatibility

Records with `signature: null` are rejected in trust-grade mode and accepted only in explicit compatibility/degraded operation.

**Modes**:
- **Trust-grade mode**: `GOV_SIGNING_REQUIRED=1` rejects unsigned records during emit and verification
- **Explicit degraded mode**: `GOV_SIGNING_DEV_MODE=1` accepts unsigned records with an explicit warning in verifier output
- **Compatibility mode**: if neither flag is set, unsigned records remain allowed for legacy compatibility

Boundary note:
- GovLayer-core signing is the signing of canonical `PolicyRecord` semantics.
- `mcp/receipt_signing.py` signs MCP receipt digests and is not part of GovLayer-core signing closure.

---

## Troubleshooting

### "FATAL: cryptography module required for signing but not installed"

**Cause**: `cryptography` library not installed.

**Fix**:
```bash
pip install 'cryptography>=43.0.0,<44'
```

### "FATAL: signing key unreadable"

**Cause**: Key file doesn't exist or has incorrect permissions.

**Fix**:
```bash
# Check key exists
ls -l ~/.config/gov-layer/signing.key

# Fix permissions if needed
chmod 600 ~/.config/gov-layer/signing.key
```

### "FATAL: signing key invalid PEM"

**Cause**: Key file is corrupted or not valid PEM format.

**Fix**: Regenerate key using quickstart steps above.

### "FATAL: signing key is not Ed25519"

**Cause**: Key file contains a different key type (RSA, ECDSA, etc.).

**Fix**: Generate Ed25519 key using quickstart steps above.

### "Signature verification failed"

**Possible causes**:
1. **Wrong public key**: `signing_key_id` doesn't match loaded key
2. **Record tampered**: Signature computed over different preimage than record
3. **Canonicalization mismatch**: Verifier using different JSON serialization

**Debug steps**:
```bash
# Check key ID matches
jq -r '.signing_key_id' record.json

# Recompute preimage and compare
python3 -c "
import json
from pathlib import Path
from scripts.policy_eval import signing_preimage_payload

rec = json.loads(Path('record.json').read_text())
preimage = signing_preimage_payload(rec)
print(f'Preimage length: {len(preimage)} bytes')
print(f'First 100 chars: {preimage[:100]}')
"
```

### "prev_record_hash link broken"

**Cause**: Chain records out of order or missing.

**Fix**: Ensure `decision-chain.jsonl` is complete and records are in emission order.

---

## Evidence Requirements

### Required evidence for signing tasks

Tasks that modify signing implementation must include:

1. **Key generation smoke test**:
   ```bash
   python3 tests/helpers/signing_key_probe.py
   ```

2. **Signature emit test**:
   ```bash
   bash tests/test_signing_emit.sh
   ```

3. **Round-trip verification test**:
   - Emit signed record
   - Verify with `verify-record.py`
   - Verify with `verify-chain.py`

4. **Evidence log format** (use helper):
   ```bash
   docs/dev/evidence/TASK_###/evidence-log.sh \
     docs/dev/evidence/TASK_###/TESTS.txt -- \
     <command>
   ```

See [RUNBOOK.md §Signing Evidence Requirements](RUNBOOK.md) for full checklist.

---

## Phase 3 Rollout Status

| Component | Status | Branch | Notes |
|---|---|---|---|
| Signing preimage | [IMPLEMENTED] | TASK_100 merged | Emit with `signature` field |
| Key loading | [IMPLEMENTED] | TASK_106 merged | Load from `GOV_SIGNING_KEY_PATH` or default |
| Verification script | [IMPLEMENTED] | Core verifier support landed | `verify-record.py` validates signatures when present and rejects unsigned records in trust-grade mode |
| Chain verification | [IMPLEMENTED] | Core chain verifier support landed | `verify-chain.py` inherits per-record signature validation through `verify-record.py` |
| Key rotation | [FUTURE] | Phase 4 | Multi-key support deferred |

---

## References

- [EPIC_SIGNING.md](EPIC_SIGNING.md) - Phase 3 signing specification
- [ATTESTATION_SPEC.md](ATTESTATION_SPEC.md) - Complete attestation architecture
- [INVARIANTS_MAP.md](INVARIANTS_MAP.md) - INV-005 (signing requirement)
- RFC 8032 - Ed25519 signature algorithm
- RFC 4648 §5 - Base64url encoding without padding
