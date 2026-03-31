# Foundation v0: Implementation Plan

**Status**: Decisions resolved, ready for implementation
**Last updated**: 2026-03-02
**Normative source**: Integrated Governance Substrate: Modified Option B (Foundation v0)
**Decision resolution date**: 2026-03-02

## Resolved Governance Decisions (D1–D13)

**Status**: All decisions resolved as of 2026-03-02. Implementation unblocked.

These are governance decisions that determine correctness of verification. They are not implementation details.

### D1–D5: Core Ledger Mechanics

**D1: Hash algorithm + encoding**
- SHA-256, lowercase hex

**D2: Hash string convention**
- `sha256:<64 lowercase hex>`

**D3: Genesis sentinel for `prev_entry_hash`**
- `sha256:0000000000000000000000000000000000000000000000000000000000000000`

**D4: `append_seq` start value**
- First real ledger entry: `append_seq = 1`
- `append_seq = 0` reserved (optional future header record)

**D5: `operation_id` format and correlation**
- UUIDv4 string
- Correlation to existing run IDs only in non-canonical metadata (excluded from hashed domain)

### D6–D8: Coverage and Surface Binding

**D6: Coverage strictness (v0)**
- Subset rule: `ledger_surfaces ⊆ stamp_surfaces`

**D7: Coverage stamp binding mechanism**
- Coverage stamp reference stored in proof bundle manifest as an explicit hash-only field (fixed location), not in the process ledger

**D8: Capability surface ID validation strategy**
- Catalog membership validation
- Reject surfaces not in the v0 surface catalog

### D9–D10: Verification Correctness

**D9: Hash basis rules per typed reference type (v0)**
- `decision_record`: hash of canonical JSON of the single decision entry (sorted keys, stable separators, UTF-8)
- `rules_version`: hash of canonical JSON snapshot of rules/policy/config (sorted keys, stable separators, UTF-8)
- `proof_bundle`: hash of canonical JSON of the proof bundle manifest (not tar/zip bytes)
- `input_file`: hash of raw bytes of the stored artifact as persisted in the authoritative raw store

**D10: Coverage-required predicate (v0)**
- Coverage stamp required for all governed operations

### D11–D12: Recovery and Failure Handling

**D11: Where `NON_ADMISSIBLE` classification is recorded**
- Verifier output record/report (machine-readable)
- Process ledger non-canonical metadata only: `admissibility_status` and `failure_codes`

**D12: Failure code → recovery outcome mapping (v0)**

Hard STOP:
- Cannot append to ledger
- Ledger entry fails schema validation at append time
- Chain verification fails on active segment (`CHAIN_BREAK`, `ENTRY_HASH_MISMATCH`, `APPEND_SEQ_BREAK`)
- Canonical serialization routine fails or is nondeterministic

NON_ADMISSIBLE but proceed:
- `HASH_NOT_FOUND`
- `ARTIFACT_HASH_MISMATCH`
- `RULES_HASH_MISMATCH`
- `STAMP_MISSING`
- `STAMP_MISMATCH`
- `SILENT_SURFACES`

### D13: Typed Reference Type Governance

**D13: Typed reference type governance**
- Catalog-validated with closed v0 catalog
- Reject any typed reference whose type is not in `typed_ref_catalog.json`
- Catalog maps `type` → `hash_basis_rule_id` (or explicit hash basis spec)
- Adding a new type requires adding its hash basis rule in the same governed change

**v0 typed reference catalog initial set:**
- `decision_record`
- `proof_bundle`
- `rules_version`
- `input_file`

---

## Scope

**What this implements:**
- Process ledger (authoritative for process/bindings only, not data content)
- Minimal capability surface binding
- Verifier checks (chain integrity, binding verification, coverage consistency)

**What this does NOT implement:**
- Data content storage in ledger (ledger stores hashes + typed references only)
- Refetch fallback on missing artifacts (verification fails closed with reason codes)
- Exhaustiveness proof of "everything that happened" (v0 proves declared-surface consistency only)

**Constraints (non-negotiable):**
1. Process ledger is authoritative for process/bindings only, not data content.
2. Ledger entries store hashes + typed references only. No payload content. No "small payload" exceptions.
3. Deterministic ordering uses append sequence. Wall-clock timestamps are metadata only and excluded from hashed canonical domain.
4. Verification must fail closed. Missing hash resolution fails with reason codes. No refetch fallback.
5. v0 "no silent surfaces" is only declared-surface consistency (ledger surfaces vs coverage stamp surfaces). Exhaustiveness of "everything that happened" is deferred.

---

## 1. Recommended Implementation Approach + Alternatives

### Recommended: Single-file append-only ledger with JSON Lines records

Implement the process ledger as an append-only file where each line is a single JSON object representing one ledger entry. Verification scans the file and validates chain integrity and bindings against a local-only artifact resolver.

**Why this approach:**
- Minimal structure that satisfies ordering (`append_seq`) and chain binding (`prev_entry_hash`)
- Simple operational inspection (`tail`, `grep`, `jq`) without requiring a DB
- Deterministic canonical serialization can be defined independent of storage container
- "No refetch" enforcement is straightforward: verifier takes filesystem paths only

**What it does NOT do:**
- No concurrent-writer support in v0 (single appender assumed; see Assumptions)
- No compaction, segmentation, or checkpointing in v0 (explicitly deferred)

### Alternative A: SQLite append-only table (WAL mode)

Each entry is stored as a row. The hash input remains canonical JSON; SQLite is only a container.

| Dimension | Tradeoff vs Recommended |
|-----------|------------------------|
| Query flexibility | Better — filtering by surface, operation_id, seq |
| Verification complexity | Slightly worse — DB access + schema handling |
| Portability | Worse — SQLite runtime dependency |
| Concurrent access | Better — readers during writes |
| "No refetch" enforcement | Same — resolver remains local-only |

**Prefer if:** You need queries over the ledger early.

### Alternative B: Content-addressable object store (Git-like)

Each entry is a blob keyed by its hash, chain tracked by a HEAD reference.

| Dimension | Tradeoff vs Recommended |
|-----------|------------------------|
| Integrity | Strong — storage keyed by hash |
| Inspection | Worse — not line-readable |
| Ordering | Must be tracked separately |
| Complexity | Higher — CAS mechanics |

**Prefer only if:** You already have a CAS store and want to reuse it.

### Alternative C: Embedded event-store infrastructure

Not recommended for v0 due to infrastructure overhead and coupling.

---

## 2. Data Model + Canonical Serialization Strategy

### 2.1 Ledger Entry Schema (v0)

#### Canonical hash domain (included in `entry_hash` computation):

- **`operation_id`**: string
  - Globally unique identifier
  - **Format (D5)**: UUIDv4 string
  - Correlation to existing run IDs only in non-canonical metadata (excluded from hashed domain)

- **`append_seq`**: integer
  - Monotonically increasing integer
  - **Start value (D4)**: First real ledger entry has `append_seq = 1` (`append_seq = 0` reserved for optional future header record)

- **`capability_surfaces`**: [string]
  - List of surface IDs
  - Ordering is not semantically meaningful; canonical serialization sorts
  - **Validation (D8)**: Catalog membership validation; reject surfaces not in the v0 surface catalog

- **`decision_record_ref`**: { type, hash }
  - Typed reference to decision record (see §2.4)

- **`proof_bundle_ref`**: { type, hash }
  - Typed reference to proof bundle (see §2.4)

- **`input_artifact_refs`**: [{ type, hash }]
  - Typed references to input artifacts (see §2.4)

- **`rules_ref`**: { type, hash }
  - Typed reference to rules/policy/config version artifact (see §2.4)

- **`prev_entry_hash`**: string
  - Hash of previous ledger entry's canonical serialization
  - **Genesis sentinel (D3)**: `sha256:0000000000000000000000000000000000000000000000000000000000000000`

#### Non-canonical metadata (excluded from hash computation):

- **`wall_clock_ts`**: string (optional)
  - ISO 8601 UTC (metadata only)
- **`host_id`**: string (optional)
- Any other metadata must be excluded from canonical domain

#### Stored fields:

- **`entry_hash`**: string
  - Stored as convenience, but must be recomputed during verification
  - Must NOT be part of the canonical hash input

### 2.2 Canonical Serialization Rules (for hashing)

The canonical form is a UTF-8 encoded JSON object representing only the canonical hash domain fields, with these constraints:

1. **Key set**: exactly these keys:
   - `append_seq`
   - `capability_surfaces`
   - `decision_record_ref`
   - `input_artifact_refs`
   - `operation_id`
   - `prev_entry_hash`
   - `proof_bundle_ref`
   - `rules_ref`

2. **Key ordering**: lexicographic ordering by key (implementation uses stable key sorting)

3. **List ordering**:
   - `capability_surfaces`: sort lexicographically
   - `input_artifact_refs`: sort lexicographically by (type, hash)

4. **No whitespace**: canonical JSON must be serialized with no extra spaces and stable separators

5. **Integers**: `append_seq` is a JSON integer (no quotes, no leading zeros)

6. **No optional fields**: every canonical key must be present. For genesis `prev_entry_hash`, use sentinel (D3): `sha256:0000000000000000000000000000000000000000000000000000000000000000`

7. **Hash algorithm and prefix convention (D1, D2)**:
   - Algorithm: SHA-256, lowercase hex
   - Prefix: `sha256:<64 lowercase hex>`

#### Example canonical JSON (illustrative only):

```json
{"append_seq":1,"capability_surfaces":["FS_WRITE"],"decision_record_ref":{"type":"decision_record","hash":"sha256:..."},"input_artifact_refs":[{"type":"input_file","hash":"sha256:..."},{"type":"input_file","hash":"sha256:..."}],"operation_id":"...","prev_entry_hash":"sha256:...","proof_bundle_ref":{"type":"proof_bundle","hash":"sha256:..."},"rules_ref":{"type":"rules_version","hash":"sha256:..."}}
```

`entry_hash = HASH(canonical_json_bytes)`

### 2.3 Storage Format (JSON Lines)

Each line is a single JSON object containing:
- The canonical domain fields
- Plus `entry_hash` (stored convenience)
- Plus optional metadata fields (non-canonical)

#### Example line:

```json
{"append_seq":1,"capability_surfaces":["FS_WRITE"],"decision_record_ref":{"type":"decision_record","hash":"sha256:..."},"input_artifact_refs":[{"type":"input_file","hash":"sha256:..."}],"operation_id":"...","prev_entry_hash":"sha256:...","proof_bundle_ref":{"type":"proof_bundle","hash":"sha256:..."},"rules_ref":{"type":"rules_version","hash":"sha256:..."},"entry_hash":"sha256:...","wall_clock_ts":"2026-03-02T12:34:56Z"}
```

Verifier must ignore non-canonical metadata during hashing and must recompute `entry_hash` from canonical fields.

### 2.4 Typed References and Hash Basis

**CRITICAL**: This must be explicit to avoid "hash bytes of whatever file we find."

Each reference has:
- **`type`**: a finite enum (string) — **Type governance (D13)**: Catalog-validated with closed v0 catalog in `typed_ref_catalog.json`
- **`hash`**: hash of a specific canonical representation of the referenced object

**Hash format (D1, D2)**: SHA-256, `sha256:<64 lowercase hex>`

#### Reference types and hash basis rules (D9):

**`decision_record`**
- Hash basis: hash of canonical JSON of the single decision entry (sorted keys, stable separators, UTF-8)
- If decisions are stored as JSONL, hash the canonical JSON for the entry

**`proof_bundle`**
- Hash basis: hash of canonical JSON of the proof bundle manifest (not tar/zip bytes)

**`rules_version`**
- Hash basis: hash of canonical JSON snapshot of rules/policy/config (sorted keys, stable separators, UTF-8)

**`input_file`**
- Hash basis: hash of raw bytes of the stored artifact as persisted in the authoritative raw store

**Important**: Verification must compute hashes according to type-specific rules, not a single "SHA256(artifact.bytes)" rule.

### 2.5 Schema Validation (Boundary enforcement, no heuristics)

Ledger append must enforce boundary constraints via strict schema:

- Reject any unknown keys in canonical domain
- Require canonical keys to be present with correct types
- Enforce strict patterns for hash fields:
  - Pattern: `^sha256:[0-9a-f]{64}$`
- Enforce `capability_surfaces` membership (D8):
  - Catalog membership validation; reject surfaces not in the v0 surface catalog
- No regex heuristics like "resembles payload"
- Only strict schema + membership checks

---

## 3. Verifier Design

### 3.1 verify_chain

**Input**: Ledger file, optionally a range `[start_seq..end_seq]`

**v0 policy**: No checkpoints; verify from genesis to target when computing admissibility for a target entry (unless verifying entire ledger).

**Algorithm**:
1. For each line:
   - Parse JSON
   - Extract canonical-domain fields
   - Serialize to canonical JSON bytes per §2.2
   - Compute `computed_entry_hash`
   - Compare with stored `entry_hash` (if present)

2. Validate chain:
   - `prev_entry_hash` matches previous computed hash
   - `append_seq` increments by 1

**Fails closed with explicit reason codes**:
- `ENTRY_HASH_MISMATCH`
- `CHAIN_BREAK`
- `APPEND_SEQ_BREAK`
- `SCHEMA_INVALID`

### 3.2 verify_bindings

**Input**: A single parsed entry, a local artifact resolver

**Resolver contract**:
- `resolve(type, hash) -> bytes | structured-object | None` (local only)
- No URL inputs
- No network client dependencies

**Verification**:
For each typed ref (decision, proof bundle, rules, each input):
1. Resolver must return an object or bytes locally, else FAIL `HASH_NOT_FOUND`
2. Compute hash using the type-specific hash basis rules in §2.4
3. Compare computed hash to reference hash, else FAIL `ARTIFACT_HASH_MISMATCH`

### 3.3 verify_no_refetch (enforced by design)

**Verifier must**:
- Accept only filesystem paths (or in-memory maps) as input sources
- Have no HTTP/socket dependencies in its module graph

**Evidence test** requires network isolation and verifying no network activity (see §4).

### 3.4 verify_coverage_consistency (v0)

**v0 meaning**: Compare declared surfaces in the ledger entry to declared surfaces in the coverage stamp bound to the same operation. This does NOT prove exhaustiveness of "everything that happened" beyond what is instrumented.

**Inputs**:
- `entry.capability_surfaces`
- Coverage stamp artifact (resolved via explicit binding)

**Binding mechanism (D7)**: Coverage stamp reference stored in proof bundle manifest as an explicit hash-only field (fixed location), not in the process ledger

**Strictness (D6)**: Subset rule — `ledger_surfaces ⊆ stamp_surfaces`

**Failure codes**:
- `STAMP_MISSING`
- `STAMP_MISMATCH`
- `SILENT_SURFACES` (for missing declared surfaces)

### 3.5 ADMISSIBLE(output) composite predicate

**Given an output that identifies an operation** (`operation_id` or `append_seq`):

1. Locate ledger entry for that operation
   - Index strategy is implementation detail, not policy

2. `verify_chain` (at least through that entry, per v0 rule)

3. `verify_bindings`

4. Coverage consistency check (D10: coverage stamp required for all governed operations)
   - Resolve coverage stamp via proof bundle manifest (D7)
   - Verify `ledger_surfaces ⊆ stamp_surfaces` (D6)

---

## 4. Evidence Test Plan

### Test 1: Deterministic entry hash (canonicalization determinism)

**Important**: Production `operation_id` may be generated per run; determinism tests must use injected fixed values.

**Procedure**:
- Build two entries with identical canonical-domain values (including `operation_id`, `append_seq`, `prev_entry_hash`, refs)
- Canonicalize and hash in two separate invocations

**Expected**: Same `entry_hash`

### Test 2: Tamper detection

**Procedure**:
- Modify canonical-domain field in a previously written entry

**Expected**: `verify_chain` FAIL with `ENTRY_HASH_MISMATCH` at that entry

**Variant**:
- Modify `entry_hash` field to match tampered content but do not update subsequent `prev_entry_hash`

**Expected**: `verify_chain` FAIL with `CHAIN_BREAK` at next entry

### Test 3: Missing artifact resolution

**Procedure**:
- Remove one referenced artifact from local store (e.g., proof bundle)

**Expected**: `verify_bindings` FAIL with `HASH_NOT_FOUND` for that ref

### Test 4: No-refetch enforcement

**Procedure**:
- Run verifier in a network-isolated environment with missing artifacts

**Expected**: FAIL `HASH_NOT_FOUND` and no network calls

**Supplementary**: Dependency audit confirms no network libraries imported

### Test 5: Coverage mismatch

**Procedure**:
- Ledger entry surfaces include X; coverage stamp omits X

**Expected**: FAIL `SILENT_SURFACES` or `STAMP_MISMATCH` (depending on chosen strictness)

---

## 5. Cost Model

### 5.1 Ledger storage growth

**Per entry**: ~600–900 bytes typical (depends on number of input refs and surface IDs)

**Growth examples**:
- 1,000 ops/day → ~1 MB/day → ~30 MB/month
- 10,000 ops/day → ~10 MB/day → ~300 MB/month

### 5.2 Verification cost

- **`verify_chain`**: O(n) scan from genesis in v0 (no checkpoints)
  - Expected acceptable at v0 volumes
  - Checkpointing deferred to v1 decision gate

- **`verify_bindings`**: IO-bound on artifact resolution and hashing
  - Cost scales with number and size of referenced artifacts and chosen hash basis

---

## 6. Assumptions + Required Decisions

### Assumptions (planning only)

**A1**: Single writer to ledger (v0)

**A2**: Artifact resolver is local-only and deterministic

**A3**: Ledger volume remains manageable without checkpoints in v0

**A4**: Coverage stamps exist and are bound mechanically via proof bundle manifest (D7)

### Required Decisions

**Status**: All decisions D1–D13 resolved as of 2026-03-02. See top of document for full list.

---

## Appendix: Implementation Sequence (Suggested, still within v0)

### Phase 1 — Canonicalizer + hashing
- Implement canonical serialization (§2.2)
- Implement `entry_hash` computation
- Pass Test 1

### Phase 2 — Append + chain verification
- Implement append with strict schema validation (§2.5)
- Implement `verify_chain` (§3.1)
- Pass Test 2

### Phase 3 — Typed ref resolution + binding verification
- Implement local-only resolver interface
- Implement `verify_bindings` using type-specific hash basis (§2.4, §3.2)
- Pass Tests 3 and 4

### Phase 4 — Coverage consistency
- Implement coverage stamp binding via proof bundle manifest (D7)
- Implement `verify_coverage_consistency` with subset rule (D6)
- Pass Test 5

### Phase 5 — Admissibility predicate + recovery wiring
- Implement composite `ADMISSIBLE` predicate
- Implement recovery outcomes per D11/D12
- End-to-end integration test with a representative governed operation

**Gate**: All evidence tests pass before calling v0 "admissibility-grade."

---

## Document History

- 2026-03-02: Initial document created from Opus planning output
- 2026-03-02: All governance decisions D1–D13 resolved; implementation unblocked
