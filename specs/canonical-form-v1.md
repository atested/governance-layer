# Canonical Form Specification v1

Status: active companion specification
Date: 2026-05-23
Scope: governance-layer Python implementation and future Rust quality service
Reference implementation: `archive/gov/governance-layer/scripts/canonical_form.py`
Conformance vectors: `canonical-form-vectors.json`

## 1. Purpose

Canonical form v1 defines the byte representation used when Atested hashes and signs structured JSON records. The Rust quality service must produce byte-identical output to the Python implementation for every canonicalization, hash, and Ed25519 signature preimage it verifies.

This specification does not change existing code paths. It records the current behavior, identifies divergence, and provides the reference implementation that future unification work will adopt.

## 2. Audit of Existing Python Canonicalization Sites

### Active governance hash/signing sites

| Site | Lines | JSON parameters | Pre-processing | Used for | Divergence |
|---|---:|---|---|---|---|
| `scripts/policy_eval_v2.py` `_canonical_json` | 238-242 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False` | None in helper | Shared canonical JSON for policy hash and v2 record hash | Canonical target |
| `scripts/policy_eval_v2.py` `compute_policy_rules_hash` | 245-251 | Uses `_canonical_json` | Drops policy keys whose string form starts with `_` | Hashing policy snapshot | Domain-specific exclusion |
| `scripts/policy_eval_v2.py` `_compute_record_hash` | 254-268 | Uses `_canonical_json` | Sets `record_hash=None`; sets `signature=None` and `signing_key_id=None` if present | v2 mediated decision record hash | Canonical target |
| `scripts/verify-record.py` `canonical_json` | 63-65 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False` | None in helper | Verifier helper | Canonical target |
| `scripts/verify-record.py` `signing_preimage_payload` | 114-144 | Uses `canonical_json` | Removes `timestamp_utc`, `session_id`, `request_id`, `process_id`, `record_hash`, `signature`, `signing_key_id`, `request_bytes_b64`, `evidence_refs`, `untrusted_inputs`; reduces `policy_reasons` to `{code}`; removes canonical/path fields; redacts expected output paths | Ed25519 signing preimage for mediated decision records | Intentionally different from record hash preimage |
| `scripts/verify-record.py` v2 hash verifier | 397-406 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`; **no `allow_nan=False`** | Sets `record_hash=None`; nulls signature fields if present | Verifying v2 record hash | Diverges: verifier accepts NaN/Infinity serialization if a record contains them |
| `scripts/event_model.py` `canonical_json` | 129-131 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False` | None in helper | Non-action event canonical JSON | Canonical target |
| `scripts/event_model.py` `_compute_event_record_hash` | 583-590 | Uses `canonical_json` | Sets `record_hash=None`; nulls `signature` and `signing_key_id` if present | Non-action event hash | Canonical target |
| `scripts/event_model.py` `sign_non_action_event` | 593-618 | Uses `canonical_json` | Sets `record_hash=None`, `signature=None`, `signing_key_id=None` | Ed25519 signing preimage for non-action events | Canonical target; hash and signing preimage are the same for non-action events |
| `scripts/integrity_monitor.py` `_canonical` | 53-55 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False` | None in helper | Integrity metadata and record hashes | Canonical target |
| `scripts/integrity_monitor.py` `_metadata_hash` | 58-61 | Uses `_canonical` | Sets `metadata_hash=None` | Integrity sidecar metadata hash | Domain-specific nulled field |
| `scripts/integrity_monitor.py` `_record_hash_for_integrity` | 64-79 | Uses `_canonical` | For non-action or v2 mediated decision only; sets `record_hash=None`; nulls signature fields if present | Chain integrity recomputation | Canonical target |
| `scripts/approval_store.py` `_canonical_json` | 39-43 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False` | None in helper | Approval-store hash and approval sorting | Canonical target |
| `scripts/approval_store.py` `approval_store_hash` | 50-60 | Uses `_canonical_json` | Sorts active approvals by each approval's canonical JSON | Approval-store snapshot hash included in decisions | Domain-specific stable ordering |
| `scripts/approval_store.py` `_verify_event_signature` | 76-81 | Uses `event_model.canonical_json` | Sets `record_hash=None`, `signature=None`, `signing_key_id=None` | Approval/revocation signature verification | Canonical target |
| `scripts/machine_identity.py` `canonical_json` | 34-37 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False` | None in helper | Machine registry canonicalization | Canonical target |
| `scripts/machine_identity.py` `_registry_hash` | 178-181 | Uses `canonical_json` | Sets `registry_hash=None` | Machine registry hash | Domain-specific nulled field |
| `scripts/remote_import.py` `sha256_json` | 75-76 | Uses `machine_identity.canonical_json` | None | Import envelope/manifest hash | Canonical target |
| `scripts/remote_import.py` `_compute_remote_record_hash` | 457-468 | Delegates to `policy_eval_v2` or `event_model`; fallback uses `event_model.canonical_json` | Sets `record_hash=None`; nulls signature fields | Remote chain validation | Canonical target |
| `scripts/remote_import.py` `_signature_preimage` | 496-503 | Non-action uses `event_model.canonical_json`; mediated decisions use `verify-record.py` | Non-action nulls hash/signature fields; mediated delegates signing redaction rules | Remote signature verification | Canonical target |
| `proxy/server.py` `ChainRecorder.append_atomic` | 195-206 | Record hash delegates to `policy_eval_v2._compute_record_hash`; signature delegates to `verify-record.py` signing preimage | Nulls signature fields before hash; signs signing preimage after hash | Governance decision hash/sign | Canonical target |
| `dashboard/server.py` `_append_chain_record_atomic` | 818-825 | Record hash and signing delegate to `event_model`; persisted line uses canonical JSON parameters | Sets previous hash, machine identity, freshness, signature fields | Dashboard non-action chain events | Canonical target |

### Adjacent canonical/hash sites that are not the primary governance-chain preimage

| Site | Lines | JSON parameters | Pre-processing | Used for | Divergence |
|---|---:|---|---|---|---|
| `dashboard/server.py` telemetry artifact hash | 382-383 | `sort_keys=True`, `separators=(",", ":")`; default `ensure_ascii=True`, default `allow_nan=True` | Hashes artifact before `artifact_hash` and `signed` are added | Telemetry artifact hash | Diverges from canonical v1 for non-ASCII and non-finite floats |
| `dashboard/server.py` telemetry payload size fallback | 2421-2425 | `sort_keys=True`, `separators=(",", ":")`; default `ensure_ascii=True`, default `allow_nan=True` | None | Payload size metadata | Diverges; size can differ for non-ASCII |
| `dashboard/server.py` trouble report artifact hash | 2504-2511 | `sort_keys=True`, `separators=(",", ":")`; default `ensure_ascii=True`, default `allow_nan=True` | Hashes artifact before `artifact_hash` is added | Trouble artifact hash | Diverges from canonical v1 |
| `scripts/evidence_package.py` `_recompute_simple_hash` | 201-209 | `sort_keys=True`, `separators=(",", ":")`; default `ensure_ascii=True`, default `allow_nan=True` | Drops `record_hash` instead of setting it to null | Legacy/simple record verification | Diverges intentionally for legacy/test records |
| `scripts/evidence_package.py` encrypted package plaintext | 482 | `sort_keys=True`, `separators=(",", ":")`; default `ensure_ascii=True`, default `allow_nan=True` | None | Evidence package encrypted payload bytes | Diverges; not a chain hash preimage |
| `scripts/evidence_package.py` manifest hash | 513-514, 531-532 | `indent=2`; default key order | None | Evidence package manifest hash | Human-readable manifest hash, not canonical v1 |
| `scripts/receipt_signing.py` `sign_digest` | 110-118, 122-139 | No JSON preimage; signs the UTF-8 digest string | Normalizes `sha256:` digest format | Detached digest signature | Different by design |
| `scripts/receipt_signing.py` sigmeta JSON | 168-169, 207-208 | `sort_keys=True`, `separators=(",", ":")`; default `ensure_ascii=True`, default `allow_nan=True` | None | Signature metadata file | Adjacent metadata, not a signed/hash preimage |
| `scripts/aat_gate_b_append.py` | 26-31, 199-211 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`; no `allow_nan=False` | None | Archived AAT decision/event hashes | Archived process; diverges on non-finite floats |
| `scripts/foundation_v0_process_ledger.py` | 46-55, 206-207 | `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`; no `allow_nan=False` | None | Foundation process ledger hash | Archived/foundation process; diverges on non-finite floats |

### Audit conclusion

The active governance-chain canonicalization sites are mostly aligned on:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
```

The real divergences are:

1. `scripts/verify-record.py:405` omits `allow_nan=False` in the v2 hash verifier path.
2. Telemetry and trouble artifact hashes in `dashboard/server.py` omit `ensure_ascii=False` and `allow_nan=False`.
3. Evidence package simple and manifest hashes use compatibility or human-readable preimages and must not be silently unified without migration.
4. v2 mediated decision signing preimage intentionally differs from the v2 record hash preimage because it excludes volatile and sensitive fields and redacts path details.

Canonical v1 unifies the active governance-chain preimage. Divergent compatibility sites remain documented until a later dispatch decides whether to migrate each one.

## 3. Canonical JSON Rules

### 3.1 Serialization

The canonical JSON string is:

```python
json.dumps(
    obj,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
    allow_nan=False,
)
```

The canonical byte sequence is the UTF-8 encoding of that string.

### 3.2 Key ordering

Object keys are sorted lexicographically by Unicode code point, matching Python `json.dumps(sort_keys=True)`.

### 3.3 Separators

No insignificant whitespace is emitted. Item separator is `","`; key/value separator is `":"`.

### 3.4 Non-ASCII handling

Non-ASCII characters are emitted as raw Unicode characters in the JSON string and encoded as UTF-8 bytes. They are not `\u`-escaped except where JSON syntax requires escaping.

### 3.5 NaN and Infinity

NaN, Infinity, and -Infinity are invalid. Python raises `ValueError` because `allow_nan=False`. Rust must reject non-finite floating-point values before serialization or during serialization.

### 3.6 Numeric formatting

Integers are emitted in base-10 without leading zeros. Negative integers use a leading `-`.

Floats must match Python 3.9+ `json.dumps` formatting exactly:

- Finite floats only.
- `-0.0` serializes as `-0.0`.
- `0.0` serializes as `0.0`.
- Integer-valued floats retain decimal form, e.g. `1.0`.
- Trailing zeros from source literals are not preserved; Python floats carry values, not decimal source syntax.
- Python emits the shortest decimal representation that round-trips to the same binary float.
- Scientific notation uses Python's thresholds and spelling, including lowercase `e` and signs such as `1e-07`.
- Subnormal floats serialize using Python's representation, e.g. `5e-324`.

Rust must match these exact strings for the conformance vector set. If `serde_json` output diverges, the Rust implementation must use a formatter that matches Python for the pinned vectors.

### 3.7 Null, booleans, and empty containers

JSON constants are lowercase:

- Python `None` -> `null`
- Python `True` -> `true`
- Python `False` -> `false`

Empty array is `[]`. Empty object is `{}`.

### 3.8 Unicode normalization

No Unicode normalization is performed. Strings are serialized exactly as stored in memory. NFC and NFD forms that look visually similar produce different canonical bytes and different hashes.

### 3.9 String escaping

Python JSON escaping rules apply:

- `"` and `\` are escaped.
- Control characters such as newline and tab are escaped.
- Non-ASCII characters are not escaped because `ensure_ascii=False`.

## 4. Field Exclusion and Preimage Rules

### 4.1 Generic canonical hash

For any object that has no domain-specific preimage rule:

```python
sha256(canonical_json(obj).encode("utf-8"))
```

The published hash string is prefixed with `sha256:`.

### 4.2 V2 mediated decision record hash

For `record_version: "2.0"` / `record_type: "mediated_decision"`:

1. Copy the record shallowly.
2. Set `record_hash = None`.
3. If present, set `signature = None`.
4. If present, set `signing_key_id = None`.
5. Canonicalize the copy.
6. Hash the UTF-8 canonical bytes with SHA-256.

Rationale: the record hash must cover all record content except the hash/signature fields that are filled after the preimage is constructed.

### 4.3 Non-action governance event hash

For `event_type` records from `event_model.NON_ACTION_EVENT_TYPES`:

1. Copy the event shallowly.
2. Set `record_hash = None`.
3. If present, set `signature = None`.
4. If present, set `signing_key_id = None`.
5. Canonicalize and SHA-256 hash.

For non-action events, the Ed25519 signing preimage is the same canonical string as the record-hash preimage.

### 4.4 V2 mediated decision signing preimage

Mediated decision signatures use the existing verifier preimage from `scripts/verify-record.py:114`.

Starting with a deep copy of the record:

Remove top-level fields:

- `timestamp_utc`
- `session_id`
- `request_id`
- `process_id`
- `record_hash`
- `signature`
- `signing_key_id`
- `request_bytes_b64`
- `evidence_refs`
- `untrusted_inputs`

Transform fields:

- `policy_reasons`: each object becomes `{ "code": <code> }`.
- `tool_args_redacted`: remove `path` and `canonical_path`.
- `policy_inputs`: remove `canonical_path` and `allow_base_dirs`.
- `normalized_args`: remove `canonical_path`, `canonical_src_path`, and `canonical_dst_path`.
- `intent.expected_outputs`: for each object whose `ref` ends with `:path`, replace `value` with `<path-redacted>`.

Then canonicalize the result. That UTF-8 canonical string is the Ed25519 message.

Rationale: signatures verify stable security-relevant meaning without binding to volatile request/session identifiers or unredacted path values.

### 4.5 Integrity metadata hash

For integrity metadata, set `metadata_hash = None`, canonicalize, and hash.

### 4.6 Machine registry hash

For machine registry records, set `registry_hash = None`, canonicalize, and hash.

### 4.7 Approval store hash

The approval-store snapshot is:

```json
{
  "approval_store_version": "0.1",
  "active_approvals": [...]
}
```

`active_approvals` is sorted by each approval row's canonical JSON string before the snapshot is canonicalized and hashed.

## 5. Ed25519 Signature Requirements

Python implementation:

- Library: `cryptography`
- Version used to generate the v1 vectors: `46.0.5`
- Key type: Ed25519
- Private key encoding: PKCS#8 PEM, unencrypted
- Public key encoding: SubjectPublicKeyInfo PEM or raw 32-byte public key for fingerprinting
- Algorithm: Ed25519 pure, no prehash
- Signature length: 64 bytes
- Signature text encoding in records: URL-safe base64 without padding

The signing message is always UTF-8 bytes:

- For non-action governance events: canonical JSON with `record_hash`, `signature`, and `signing_key_id` set to null.
- For mediated decision records: the signing preimage from Section 4.4.
- For detached receipt signatures: the normalized `sha256:` digest string, not canonical JSON.

Rust implementation requirement:

- `ed25519-dalek` or equivalent must sign the exact same message bytes.
- Given the same 32-byte private seed and message, Rust must produce the exact signature bytes in the vector below.
- No prehash, context string, domain separation tag, or alternate Ed25519 variant is allowed.

### Ed25519 test vector

Private seed:

```text
000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f
```

Private key PKCS#8 PEM:

```text
-----BEGIN PRIVATE KEY-----
MC4CAQAwBQYDK2VwBCIEIAABAgMEBQYHCAkKCwwNDg8QERITFBUWFxgZGhscHR4f
-----END PRIVATE KEY-----
```

Public key raw hex:

```text
03a107bff3ce10be1d70dd18e74bc09967e4d6309ba50d5f1ddc8664125531b8
```

Public key fingerprint:

```text
ed25519:56475aa75463474c0285df5dbf2bcab73da651358839e9b77481b2eab107708c
```

Message:

```json
{"event_type":"qa_environmental_snapshot","overall":"healthy","sequence":1}
```

Expected signature hex:

```text
e951731a592f4072d16f3595d9d5c0ef07be988b01daf72442a52ab62969a6370aa6fbd996d893dc5e455eb4d370262f19a28078a7188d877dc92440f6e6110e
```

Expected signature base64url without padding:

```text
6VFzGlkvQHLRbzWV2dXA7we-mIsB2vckQqUqtilppjcKpvvZltiT3F5FXrTTcCYvGaKAeKcYjYd9ySRA9uYRDg
```

## 6. Conformance Vector Set

`canonical-form-vectors.json` contains 30 canonical vectors and one Ed25519 signature vector. Vectors cover:

- ASCII records
- CJK, emoji, accent characters, NFC/NFD distinction
- integers, large integers, floats, negative zero, scientific notation, subnormal floats
- null, booleans, empty arrays/objects
- nested and deeply nested structures
- mixed-type arrays
- non-sorted input key order
- actual mediated decision and non-action governance event shapes
- integrity metadata, registry, approval-store snapshots
- QA chain record shapes for environmental snapshots, conditions, decision verification, SPC, element verification, behavioral analysis, and session summary

Validation command:

```bash
python3 archive/gov/governance-layer/scripts/canonical_form.py \
  --validate-vectors archive/project-management/atested/claude-project-files/canonical-form-vectors.json
```

Expected output:

```text
PASS: 30 canonical vectors validated
```

## 7. Reference Implementation API

`scripts/canonical_form.py` exports:

- `canonical_json(obj) -> str`
- `canonicalize(obj) -> bytes`
- `sha256_prefixed(obj) -> str`
- `record_hash_preimage(record) -> str`
- `record_hash(record) -> str`
- `metadata_hash_preimage(metadata) -> str`
- `metadata_hash(metadata) -> str`
- `registry_hash_preimage(registry) -> str`
- `registry_hash(registry) -> str`
- `approval_store_hash(approvals) -> str`
- `signing_preimage_payload(record) -> str`
- `non_action_signing_preimage(event) -> str`
- `build_conformance_vectors() -> dict`
- `validate_vector_set(path) -> (bool, list[str])`

It also provides:

```bash
python3 scripts/canonical_form.py --write-vectors PATH
python3 scripts/canonical_form.py --validate-vectors PATH
```

## 8. Migration Guidance

A follow-up unification dispatch should replace active canonicalization sites with calls into `scripts/canonical_form.py`. That dispatch should not silently migrate divergent compatibility sites. Each divergent site needs a deliberate decision:

- `verify-record.py` v2 hash verifier should add `allow_nan=False`.
- Telemetry and trouble artifact hashes should either remain as artifact-specific legacy hashes or migrate with an artifact version bump.
- Evidence package manifest hashes should remain human-readable unless a new canonical manifest version is introduced.
- Archived/foundation scripts can remain as historical tooling unless they are reactivated.
