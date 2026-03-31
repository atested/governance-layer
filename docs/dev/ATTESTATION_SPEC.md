# Attestation Specification

Technical specification for policy records, attestation objects, replay verification, and evidence bundles.

---

## 1. Object Model

### 1.1 PolicyRecord (Core Attestation Object)

A PolicyRecord is the canonical attestation produced by the policy evaluator for every tool request.

**Required Fields**:
```json
{
  "record_version": "0.1",
  "cap_registry_hash": "sha256:...",
  "request_hash": "sha256:...",
  "request_bytes_b64": "base64(...)",
  "timestamp_utc": "2026-02-24T12:00:00Z",
  "session_id": "sess-...",
  "request_id": "uuid-...",
  "actor": "string",
  "tool": "FS_WRITE",
  "capability_class": "FS_WRITE",
  "intent": { Intent },
  "policy_inputs": { PolicyInputs },
  "normalized_args": { NormalizedArgs },
  "policy_decision": "ALLOW" | "DENY",
  "policy_reasons": [ { "code": "RC-...", "detail": "..." } ],
  "tool_args_redacted": { ... },
  "untrusted_inputs": [ ... ],
  "evidence_refs": [ ... ],
  "prev_record_hash": "sha256:..." | null,
  "record_hash": "sha256:...",
  "signature": "base64(...)" | null,
  "signing_key_id": "string" | null
}
```

**Field Descriptions**:
- `record_version`: Schema version (currently "0.1")
- `cap_registry_hash`: SHA256 of capability registry used for evaluation
- `request_hash`: SHA256 of canonical JSON request bytes
- `request_bytes_b64`: Base64-encoded original request for replay
- `timestamp_utc`: ISO 8601 timestamp (excluded from signing preimage)
- `session_id`, `request_id`: Correlation IDs (excluded from signing preimage)
- `actor`: Executing actor identifier
- `tool`: Tool name from request
- `capability_class`: Matched capability class from registry
- `intent`: Structured intent object (goal, constraints, expected outputs)
- `policy_inputs`: Inputs to policy evaluation (paths, flags, deny rules)
- `normalized_args`: Canonical argument form produced by normalizer
- `policy_decision`: ALLOW or DENY
- `policy_reasons`: Array of reason code objects (empty for ALLOW)
- `tool_args_redacted`: Tool args with sensitive fields redacted/hashed
- `untrusted_inputs`: List of inputs that bypass governance (for audit)
- `evidence_refs`: Links to evidence files/artifacts
- `prev_record_hash`: Hash of previous record in chain (forms tamper-evident log)
- `record_hash`: SHA256 of this record's canonical bytes
- `signature`: Ed25519 signature over signing preimage (Phase 3, null in Phase 2)
- `signing_key_id`: Key identifier for signature verification (Phase 3)

### 1.2 Intent Object

Every request includes a structured intent describing the human-level goal.

```json
{
  "goal": "Write configuration file to project directory",
  "constraints": {
    "max_file_size": 1024,
    "no_hidden_files": true
  },
  "requested_action": "FS_WRITE",
  "inputs": [
    { "ref": "config:source", "value": "app.conf" }
  ],
  "expected_outputs": [
    { "ref": "file:path", "value": "/path/to/config.json" }
  ]
}
```

**Purpose**: Enables human audit of tool usage, links decisions to business logic.

### 1.3 NormalizedArgs

Tool-specific canonical argument form produced by normalizer.

**Example (FS_WRITE)**:
```json
{
  "canonical_path": "/Volumes/SSD/archive/gov/governance-layer/test.txt",
  "content_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "overwrite": false,
  "request_executable": false
}
```

**Invariant**: Normalized args must be deterministic across platforms (canonical paths, sorted keys, etc.).

### 1.4 PolicyInputs

Inputs used during policy evaluation (extracted from request + environment).

```json
{
  "canonical_path": "/Volumes/SSD/archive/gov/governance-layer/test.txt",
  "allow_base_dirs": [
    "/Volumes/SSD/archive/gov/governance-layer/",
    "/Volumes/SSD/archive/gov/runtime"
  ],
  "deny_hidden_paths": true,
  "deny_overwrite_by_default": true,
  "deny_executable_outputs": true,
  "overwrite_intent": false,
  "overwrite_requested": false,
  "request_executable": false
}
```

### 1.5 ReasonCode Object

Structured rejection reason emitted for DENY decisions.

```json
{
  "code": "RC-FS-PATH-DISALLOWED",
  "detail": "Path is outside allowed base directories: /etc/passwd"
}
```

See [REASON_CODES.md](REASON_CODES.md) for complete taxonomy.

---

## 2. Process Model

### 2.1 Request → Record Pipeline

```
┌────────────────────────────────────────────────────────────┐
│ 1. Tool Request                                            │
│    { tool: "FS_WRITE", args: {...}, intent: {...} }       │
└──────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────────┐
│ 2. Argument Normalization                                  │
│    - Resolve canonical paths (resolve symlinks, ..)        │
│    - Apply defaults (max_bytes, offset, overwrite)         │
│    - Compute content hashes                                │
│    - Build normalized_args dict                            │
└──────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────────┐
│ 3. Capability Lookup                                       │
│    - Match tool name to capability class                   │
│    - Load capability schema from registry                  │
│    - Extract policy inputs (base dirs, deny flags)         │
└──────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────────┐
│ 4. Policy Evaluation                                       │
│    - Check path allowlist (base dir membership)            │
│    - Check deny rules (hidden paths, executables, etc.)    │
│    - Check constraints (max_bytes, overwrite intent)       │
│    - Emit reason codes for any violations                  │
│    - Produce ALLOW or DENY decision                        │
└──────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────────┐
│ 5. Record Construction                                     │
│    - Serialize request to canonical JSON                   │
│    - Compute request_hash (SHA256 of canonical bytes)      │
│    - Build PolicyRecord with all fields                    │
│    - Compute record_hash (SHA256 of canonical record)      │
│    - Optionally sign (Phase 3: compute signing preimage)   │
└──────────────────┬─────────────────────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────────────────────┐
│ 6. Chain Append                                            │
│    - Link prev_record_hash to previous record              │
│    - Append to decision-chain.jsonl                        │
│    - Return record to caller                               │
└────────────────────────────────────────────────────────────┘
```

### 2.2 Fail-Closed Error Handling

Any exception during evaluation results in DENY:
- Capability lookup failures → DENY with RC-UNKNOWN-TOOL
- Path resolution errors → DENY with RC-PATH-DISALLOWED
- Missing intent fields → DENY with RC-FS-MISSING-INTENT-FIELDS
- Normalization exceptions → DENY with error reason code

**Invariant**: No tool execution occurs without a valid PolicyRecord.

---

## 3. Replay Contract

### 3.1 Replay Definition

**Replay**: Re-executing policy evaluation with the same inputs and verifying the output matches the original record.

**Replay Input**: `request_bytes_b64` from PolicyRecord
**Replay Output**: New PolicyRecord with the same deterministic governance semantics as the original record

### 3.2 Determinism Requirements

For replay to succeed, these must be stable:
1. Capability registry (identified by `cap_registry_hash`)
2. Policy evaluation logic (code version must match)
3. Normalization logic (path resolution, defaults)
4. Reason code emission (same violations → same codes)

**Non-deterministic fields** (excluded from record_hash):
- `timestamp_utc`
- `session_id`
- `request_id`
- `actor` (may vary across replay contexts)

### 3.3 Replay Verification

Replay succeeds if:
```python
verify_record(original_record, check_cap_registry_hash=False) == PASS
verify_record(replay_record, check_cap_registry_hash=True) == PASS
original_record["policy_decision"] == replay_record["policy_decision"]
reason_codes(original_record) == reason_codes(replay_record)
original_record["tool"] == replay_record["tool"]
original_record["cap_registry_hash"] == replay_record["cap_registry_hash"]
original_record["normalized_args"] == replay_record["normalized_args"]
coverage_stamp(original_record) == coverage_stamp(replay_record)
```

Replay failures indicate:
- Policy drift (code or registry changed)
- Non-deterministic normalization (path resolution, time-dependent logic)
- Invalid original-record baseline, invalid replay-produced record, or trust-grade unsigned replay paths

---

## 4. Proof Packet v1 (Pack + Verify)

Proof Packet v1 is a deterministic archive that packages a replayable policy record and audit artifacts for transport, CI logging, and review.

### 4.1 Contents (Deterministic Layout)

- Top-level `manifest.json`
- `payload/record.json`
- `payload/replay_audit_report.json`
- `payload/artifacts/**` (operator-selected supporting artifacts)

### 4.2 Key Linkage Fields

`manifest.json` includes a `source_summary` object used for audit linkage:

- `record_bytes_sha256`: SHA256 of `payload/record.json` bytes (must match `manifest.files["record.json"].sha256`)
- `record_hash`: optional record field copied from `record.json` if present (presence-only provenance)
- `replay_report_hash`: SHA256 of `payload/replay_audit_report.json` bytes (must match manifest hash entry)
- `signing_key_id`: optional record field copied from `record.json` if present (presence-only provenance)

Verifier summary output (`--summary-json`) also emits:

- `packet_hash`: `{"algo":"sha256","value":"<lowercase-hex>"}` for the final proof-packet tar bytes
- deterministic counts (`matched`, `mismatched`, `missing`, `extra`, `fatal`)
- key linkage summary fields for CI/log bundles

### 4.3 Relationship to Attestation Bundle + Replay Audit

- The attestation bundle (`scripts/attest/bundle.py`) provides deterministic pack/verify for record + artifacts.
- The replay audit report (`scripts/replay-record.py --audit-report-json`) captures replay invariant outcomes and mismatch details.
- The proof-packet packer (`scripts/proof-packet.py pack`) combines record + artifacts + replay audit report into one deterministic package.
- The proof-packet verifier (`scripts/proof-packet.py verify`) validates manifest schema, hash index, and linkage invariants.

**External proof-bundle linkage note (release-gate):**
- `status_bundle.json` is an optional output of `system/scripts/release-gate.sh` in the proof-bundle directory.
- `status_bundle.json` is **not** part of `proof_packet_v1`; it belongs to the external proof-bundle output contract documented in `docs/EXTERNAL_CONTRACTS.md`.
- When present, `status_bundle.json` includes a `status_bundle_version` field (current value: `status_bundle_v1`) for explicit consumer compatibility checks.

### 4.4 Canonical Commands (Pack + Verify)

```bash
# Produce replay audit report JSON from a record
python3 scripts/replay-record.py --audit-report-json /tmp/replay_audit_report.json path/to/record.json

# Build deterministic proof packet
python3 scripts/proof-packet.py pack \
  --record path/to/record.json \
  --artifacts-dir path/to/artifacts \
  --replay-audit-report /tmp/replay_audit_report.json \
  --out /tmp/proof_packet.tar

# Verify proof packet and emit deterministic summary JSON
python3 scripts/proof-packet.py verify \
  --bundle /tmp/proof_packet.tar \
  --summary-json /tmp/proof_packet.verify.summary.json
```

### 4.5 Versioning and Compatibility (Proof Packet / Replay Audit Reports)

- Proof packet manifest schema version: `proof_packet_v1` (`manifest.json.proof_packet_version`)
- Proof-packet verifier summary JSON schema version: `proof_packet_verify_summary_v2` (`report_version`)
- Proof-packet verifier summary JSON includes an additive `governance_evidence` block that surfaces packet identity, manifest hash, record/replay hash linkage, and the pass/fail result for operator-facing coherence checks.
- Replay audit report JSON is expected to remain deterministic and versioned by its report payload shape; proof-packet pack/verify treat it as a hashed payload member referenced by `source_summary.replay_report_hash`.

Compatibility expectations:
- Additive fields in `source_summary` are allowed only if verifier/schema rules are updated in lockstep.
- `record_bytes_sha256` and `replay_report_hash` linkage fields are fail-closed invariants for proof-packet verify.
- Consumers should key compatibility checks off explicit version markers, not file names.
- Hash collision (extremely unlikely)

**External contract policy:**
- `proof_packet_v1` manifest: **FROZEN** within v1 (no field add/remove/rename/retype allowed)
- `proof_packet_verify_summary_v2`: **ADDITIVE-ONLY** within v2 (new fields allowed, existing fields stable)
- `validate-proof-bundle.sh` accepts legacy `proof_packet_verify_summary_v1` during the bounded migration window, but current proof-bundle emission is `proof_packet_verify_summary_v2`
- Breaking changes require version bump to v2
- See [EXTERNAL_CONTRACTS.md](../../EXTERNAL_CONTRACTS.md) for full stability guarantees and versioning policy

### 3.4 Replay Script

```bash
# Replay a single record
python3 scripts/policy-eval.py \
  capabilities/capability-registry.json \
  path/to/original-request.json

# Verify hash matches
jq -r .record_hash output.json
# Should equal original record's record_hash
```

See `scripts/replay-record.py` for batch replay tooling.

---

## 4. Evidence Structure

### 4.1 Evidence Bundle Layout

Every implemented feature requires an evidence bundle under `docs/dev/evidence/TASK_XXX/`:

```
docs/dev/evidence/TASK_XXX/
├── TESTS.txt           # Test execution transcript (required)
├── REPO_LAYOUT.txt     # Directory tree snapshot (optional)
├── fixtures/           # Test fixtures (if applicable)
│   └── *.json
└── [other artifacts]
```

### 4.2 TESTS.txt Format

TESTS.txt is the canonical evidence artifact. It contains:
1. Git status and diff checks (verify clean state)
2. Test harness execution with full output
3. Exit codes for all commands
4. Pass/fail assertions

**Example**:
```
$ git diff --stat origin/main...HEAD
[exit=0]

$ git status --porcelain
?? docs/dev/evidence/TASK_XXX/
[exit=0]

$ bash tests/test_rc_fs_not_a_file.sh
--- TASK_065: RC-FS-NOT-A-FILE ---
$ python3 scripts/policy-eval.py ...
{ "policy_decision": "DENY", "policy_reasons": [{"code": "RC-FS-NOT-A-FILE", ...}] }
PASS: decision DENY with RC-FS-NOT-A-FILE
[exit=0]
```

### 4.3 Evidence Requirements (from MERGE_GATE.md)

Cecil verifies evidence bundles before merge:
- TESTS.txt must exist for CODE branches
- Test output must show PASS assertions
- Reason code tests must emit expected RC-* codes
- No failures or unexpected exits allowed

---

## 5. Signing Preimage (Phase 3)

**Status**: [IMPLEMENTED] - GovLayer-core trust-grade emit and verifier closure are implemented. Compatibility mode remains outside the trust-grade claim path.

Phase 3 adds Ed25519 asymmetric signatures to every trust-grade policy record, enabling non-repudiation and third-party verification. This section specifies the complete end-to-end flow from key loading through emit to verification.

### 5.1 Signature Coverage

The signing preimage includes all fields that determine policy evaluation semantics, excluding volatile metadata and self-referential fields.

**Included in preimage** (deterministic policy inputs/outputs):
- `record_version` (schema version)
- `cap_registry_hash` (binds to registry snapshot)
- `request_hash` (binds to request bytes)
- `tool`, `capability_class` (tool identification)
- `intent` (with `expected_outputs` path-redacted)
- `policy_inputs` (without `canonical_path`, `allow_base_dirs`)
- `normalized_args` (without `canonical_path`, `canonical_src_path`, `canonical_dst_path`)
- `policy_decision`, `policy_reasons` (codes only, not `detail` text)
- `tool_args_redacted` (with `path` and `canonical_path` excluded)

**Excluded from preimage** (volatile or self-referential):
- `timestamp_utc`, `session_id`, `request_id` (volatile)
- `actor` (volatile, context-dependent)
- `prev_record_hash` (chain link, not attestation)
- `record_hash`, `signature`, `signing_key_id` (self-referential)
- `request_bytes_b64` (bound via `request_hash` instead)
- `evidence_refs`, `untrusted_inputs` (audit metadata)
- Path expansions in `normalized_args`, `policy_inputs`, `tool_args_redacted`

**Rationale**: The preimage captures policy evaluation semantics independent of execution context. Machine-specific paths, timestamps, and audit metadata are excluded to ensure deterministic verification across environments.

### 5.2 End-to-End Emit Flow

**Phase 3 emit sequence** (`scripts/policy-eval.py → emit_record()`):

```python
def emit_record(record: dict) -> None:
    # Step 1: Compute signing preimage (record_hash and signature still null)
    #         This is the same preimage used for record_hash
    preimage = signing_preimage_payload(record)  # canonical JSON as UTF-8 bytes

    # Step 2: Load signing key (if available)
    #         Priority: GOV_SIGNING_KEY_PATH → ~/.config/gov-layer/signing.key → None
    signing_key, signing_key_id, signing_err = load_signing_private_key()

    if signing_err:
        # Fatal: key exists but unreadable/invalid
        print(signing_err, file=sys.stderr)
        sys.exit(2)

    # Step 3: Sign preimage (if key loaded)
    if signing_key is not None:
        sig_bytes = signing_key.sign(preimage)  # Ed25519 deterministic signature (64 bytes)
        record["signature"] = _b64url_encode_nopad(sig_bytes)  # Base64url without padding
        record["signing_key_id"] = signing_key_id  # "ed25519:<sha256_hex>"
    elif signing_required_mode_enabled():
        # Trust-grade mode: fail closed if signed PolicyRecord cannot be emitted
        print("FATAL: signed PolicyRecord required for trust-grade mode", file=sys.stderr)
        sys.exit(2)
    else:
        # Compatibility mode: no key → emit unsigned
        record["signature"] = None
        record["signing_key_id"] = None

    # Step 4: Compute record_hash (from same preimage, with signature/hash still null)
    #         Both signature and record_hash cover the same canonical bytes
    record["record_hash"] = f"sha256:{sha256_hex(preimage)}"

    # Step 5: Emit to stdout (append to decision-chain.jsonl)
    print(json.dumps(record, indent=2, ensure_ascii=False))
```

**Key properties**:
1. **Same preimage for signature and record_hash**: Both computed from null-signature form
2. **Deterministic**: Ed25519 signature is deterministic (no nonce)
3. **Trust-grade capable**: `GOV_SIGNING_REQUIRED=1` fails closed if signed emission is impossible
4. **Backward compatible**: No key → emit unsigned only outside trust-grade mode

### 5.3 Key Loading Flow

**Function**: `load_signing_private_key()` (in `scripts/policy-eval.py`)

**Key search order** (fail-fast on first match):
1. **`GOV_SIGNING_KEY_PATH` environment variable**: Explicit path override
   - If set and exists: load from specified path
   - If set and missing: FATAL error (explicit path must exist)
2. **`~/.config/gov-layer/signing.key`**: Default location
   - If exists: load from default path
   - If missing: return `(None, None, None)` and let emit semantics decide whether to fail closed
3. **No key found**:
   - with `GOV_SIGNING_REQUIRED=1`: fail closed at emit time
   - otherwise: compatibility mode may emit unsigned

**Key validation** (`_load_ed25519_private_key_from_pem()`):
```python
def _load_ed25519_private_key_from_pem(path: Path, source_label: str):
    # 1. Read key file
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, None, f"FATAL: signing key unreadable ({source_label}): {path}"

    # 2. Parse PEM format
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
    except ModuleNotFoundError:
        return None, None, cryptography_missing_error

    try:
        priv = serialization.load_pem_private_key(raw, password=None)
    except ValueError:
        return None, None, f"FATAL: signing key invalid PEM ({source_label}): {path}"

    # 3. Verify key type is Ed25519
    if not isinstance(priv, Ed25519PrivateKey):
        return None, None, f"FATAL: signing key is not Ed25519 ({source_label}): {path}"

    # 4. Compute key_id from public key
    pub = priv.public_key()
    raw_pub = pub.public_bytes(encoding=serialization.Encoding.Raw,
                                 format=serialization.PublicFormat.Raw)
    key_id = "ed25519:" + hashlib.sha256(raw_pub).hexdigest()

    return priv, key_id, None
```

**Error modes**:
- **FATAL** (exit 2): Key exists but unreadable, invalid PEM, not Ed25519, or cryptography module missing
- **Non-fatal** (emit unsigned): No key found at any location and trust-grade mode is not enabled

### 5.4 Signing Preimage Canonicalization

**Function**: `signing_preimage_payload(record)` (in `scripts/policy-eval.py`)

**Implementation**:
```python
SIGNING_EXCLUDE_TOP_LEVEL = frozenset([
    "timestamp_utc", "session_id", "request_id",
    "prev_record_hash", "record_hash",
    "signature", "signing_key_id",
    "request_bytes_b64", "evidence_refs", "untrusted_inputs",
])

def signing_preimage_payload(record: dict) -> str:
    # 1. Deep copy to avoid mutating original
    unsigned = copy.deepcopy(record)

    # 2. Exclude volatile top-level fields
    for key in SIGNING_EXCLUDE_TOP_LEVEL:
        unsigned.pop(key, None)

    # 3. Redact reason detail (keep codes only)
    if isinstance(unsigned.get("policy_reasons"), list):
        unsigned["policy_reasons"] = [
            {"code": r.get("code")} if isinstance(r, dict) else r
            for r in unsigned["policy_reasons"]
        ]

    # 4. Redact paths from tool_args_redacted
    if isinstance(unsigned.get("tool_args_redacted"), dict):
        unsigned["tool_args_redacted"].pop("path", None)
        unsigned["tool_args_redacted"].pop("canonical_path", None)

    # 5. Redact paths from policy_inputs
    if isinstance(unsigned.get("policy_inputs"), dict):
        unsigned["policy_inputs"].pop("canonical_path", None)
        unsigned["policy_inputs"].pop("allow_base_dirs", None)

    # 6. Redact paths from normalized_args
    if isinstance(unsigned.get("normalized_args"), dict):
        for key in ("canonical_path", "canonical_src_path", "canonical_dst_path"):
            unsigned["normalized_args"].pop(key, None)

    # 7. Sanitize expected_outputs (redact path values)
    if isinstance(unsigned.get("intent"), dict):
        unsigned["intent"]["expected_outputs"] = _sanitize_expected_outputs_for_signing(
            unsigned["intent"].get("expected_outputs", [])
        )

    # 8. Canonical JSON serialization
    return canonical_json(unsigned)  # json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)
```

**Invariant**: `signing_preimage_payload(record)` is identical to the preimage used for `record_hash` computation.

### 5.5 Verification Flow

**Single record verification** (`scripts/verify-record.py`, Phase 3 mode):

```python
def verify_record_phase3(record: dict) -> None:
    # Step 1: Cap registry hash
    raw_reg, _reg, computed_cap_hash = load_internal_registry()
    if record["cap_registry_hash"] != computed_cap_hash:
        raise VerificationError("Cap registry hash mismatch")

    # Step 2: Request hash (if present)
    if "request_bytes_b64" in record and "request_hash" in record:
        decoded = base64.b64decode(record["request_bytes_b64"])
        computed_req_hash = "sha256:" + hashlib.sha256(decoded).hexdigest()
        if record["request_hash"] != computed_req_hash:
            raise VerificationError("Request hash mismatch")

    # Step 3: Record hash
    preimage = signing_preimage_payload(record)
    computed_record_hash = "sha256:" + sha256_hex(preimage)
    if record["record_hash"] != computed_record_hash:
        raise VerificationError("Record hash mismatch")

    # Step 4: Signature (Phase 3)
    if record.get("signature") is None:
        # Production mode: FAIL, Dev mode: WARN
        if VERIFICATION_MODE == "production":
            raise VerificationError("Signature missing (required in Phase 3)")
        else:
            print("WARNING: Signature missing (Phase 2 record)", file=sys.stderr)
            return

    # 4a. Load public key by signing_key_id
    signing_key_id = record.get("signing_key_id")
    if not signing_key_id:
        raise VerificationError("signing_key_id missing")

    public_key = load_public_key_by_id(signing_key_id)  # Raises if key not found

    # 4b. Decode signature
    try:
        sig_bytes = base64.urlsafe_b64decode(record["signature"] + "==")  # Add padding
    except Exception as e:
        raise VerificationError(f"Invalid signature encoding: {e}")

    # 4c. Verify Ed25519 signature
    try:
        public_key.verify(sig_bytes, preimage.encode("utf-8"))
    except Exception as e:
        raise VerificationError(f"Signature verification failed: {e}")

    print("✓ Record verification passed (Phase 3)")
```

**Chain verification** (`scripts/verify-chain.py`, Phase 3 mode):
- Validates `prev_record_hash` links (unchanged from Phase 2)
- Invokes `verify_record_phase3()` for each record in chain

**Verification modes**:
- **Trust-grade mode**: `GOV_SIGNING_REQUIRED=1` rejects unsigned records
- **Explicit degraded mode**: `GOV_SIGNING_DEV_MODE=1` accepts unsigned records with warning
- **Compatibility mode**: unsigned records remain allowed when trust-grade mode is not enabled

### 5.6 Phase 2 Compatibility

**Backward compatibility guarantees**:
1. **Emit**: No signing key → emit with `signature: null`, `signing_key_id: null` only outside trust-grade mode
2. **Verification**: Explicit degraded mode accepts unsigned records with WARNING
3. **Schema**: `signature` and `signing_key_id` fields already reserved (no schema change)

**Migration path**:
1. Phase 2 → Phase 3: Generate signing key, emit will automatically sign new records
2. Mixed chains: compatibility or explicit degraded mode can still accept signed and unsigned records together
3. Trust-grade mode: all new records must be signed, and unsigned verification paths are rejected

### 5.7 Example: Complete Emit-Verify Flow

```bash
# 1. Generate signing key (one-time setup)
python3 - <<'PY'
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
from pathlib import Path
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
print(f"Key created: {path}")
PY

# 2. Emit signed record
python3 scripts/policy-eval.py intent.json > record.json

# 3. Verify fields populated
jq -r '.signature // "MISSING"' record.json
# Output: Xy9kL3RtYWluLXNpZ25hdHVyZS1oZXJl... (base64url)

jq -r '.signing_key_id // "MISSING"' record.json
# Output: ed25519:a3f2d1c5b8e9...

jq -r '.record_hash' record.json
# Output: sha256:4f8a3c2d...

# 4. Verify signature
python3 scripts/verify-record.py record.json
# Output: ✓ Record verification passed (Phase 3)

# 5. Append to chain and verify full chain
cat record.json >> $GOV_RUNTIME_DIR/LOGS/decision-chain.jsonl
python3 scripts/verify-chain.py $GOV_RUNTIME_DIR/LOGS/decision-chain.jsonl
# Output: ✓ Chain verification passed (N records, Phase 3)
```

**See also**:
- [SIGNING_GUIDE.md](SIGNING_GUIDE.md) - Practical guide with key management and troubleshooting
- [EPIC_SIGNING.md](../EPIC_SIGNING.md) - Complete Phase 3 specification and design rationale

---

## 6. Build Manifest (Integrated E2E Tests)

### 6.1 Purpose

Build manifests are path-free deterministic summaries of PolicyRecords, used for:
- Verifying policy evaluation determinism across environments
- Comparing decisions without path-specific details
- Detecting policy drift in CI/CD pipelines

### 6.2 Manifest Schema

```json
{
  "manifest_version": "0.1",
  "record_version": "0.1",
  "record_hash": "sha256:...",
  "request_hash": "sha256:...",
  "tool": "FS_WRITE",
  "capability_class": "FS_WRITE",
  "cap_registry_hash": "sha256:...",
  "normalized_args_hash": "sha256:...",
  "policy_decision": "ALLOW",
  "reason_codes": []
}
```

### 6.3 Generation

```bash
# Set output path
export GOV_BUILD_MANIFEST_PATH=/path/to/manifest.json

# Run policy evaluation
python3 scripts/policy-eval.py registry.json request.json

# Manifest is written to GOV_BUILD_MANIFEST_PATH
cat "$GOV_BUILD_MANIFEST_PATH"
```

See `tests/test_build_manifest_determinism.sh` for E2E determinism tests.

---

## 7. Open Questions / Needs Placement

### Signing Key Management
- Key generation procedure (deterministic vs random)
- Key rotation strategy
- Key storage (filesystem, env var, hardware token)
- Multi-key scenarios (different actors, different sessions)

**Current status**: [DESIGN_ONLY] - specified in EPIC_SIGNING.md, not implemented

### Time Ribbon Rendering
- How to construct attestation chains from decision logs
- How to handle branching/merging chains (multiple sessions)
- Rendering format (JSON, visual, etc.)

**Current status**: [DESIGN_ONLY] - mentioned in TASK_098, no implementation

### Distributed Replay
- How to replay across multiple nodes
- Consensus on replay results
- Handling non-deterministic environment differences

**Current status**: [SPECULATIVE] - out of scope for Phase 2/3

---

## 8. Related Documentation

- [GOVERNANCE_OVERVIEW.md](../GOVERNANCE_OVERVIEW.md): High-level system description
- [EXTERNAL_CONTRACTS.md](../../EXTERNAL_CONTRACTS.md): Stability guarantees for external consumers
- [EPIC_SIGNING.md](../EPIC_SIGNING.md): Phase 3 signing specification
- [REASON_CODES.md](REASON_CODES.md): Rejection reason code taxonomy
- [INVARIANTS_MAP.md](INVARIANTS_MAP.md): System invariants and enforcement
- [APPLICATIONS_INDEX.md](APPLICATIONS_INDEX.md): Downstream use cases
