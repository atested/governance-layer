# Decision Memo: External Usability Contracts

**Date**: 2026-02-25
**Status**: [DECIDED]
**Decision Maker**: Greg Keeter
**Documented By**: Cecil (governance operator)

---

## Decision Summary

**Chosen Approach:** STANDARD + Selective STRICT

We adopt **STANDARD as baseline** for external usability with **STRICT enforcement for core schemas** where stability is critical for external consumers.

---

## Decisions Recorded

### 1. Contract Stance

**STANDARD baseline:**
- Proof-bundle contract: 5 required files (tar, summary JSON, sha256, log.txt, versions.txt)
- Profile semantics: dev (informational) and ci (gating)
- Dependency handling: MCP smoke runs if available, warns if missing
- Auxiliary file formats: Documented, evolvable with deprecation notices

**Selective STRICT for core schemas:**
- `proof_packet_v1` manifest: **ADDITIVE-ONLY** within v1
  - Can add new fields to manifest
  - Cannot remove fields
  - Cannot rename fields
  - Cannot change field types
  - Breaking changes require v2
- `proof_packet_verify_summary_v1`: **ADDITIVE-ONLY** within v1
  - Same constraints as manifest
  - Version bump to v2 required for breaking changes

### 2. Queue Drift Scan Format

**Decision:** Keep `queue_drift_scan.txt` as human-readable text for now.

**Rationale:**
- Current consumers use it for debugging, not machine parsing
- Keeps format flexible while tool evolves
- Can add `queue_drift_scan.json` in future if external tooling needs structured access

**Contract:** No machine-parse guarantee for `.txt` format. May contain freeform output or "INFO: queue-drift-scan unavailable\n" sentinel.

### 3. MCP Smoke in CI Profile

**Decision:** Run if available, warn if missing, not gating by default.

**Behavior:**
- **dev profile:** Logs "INFO: unavailable", continues
- **ci profile:** Logs "WARN: unavailable", continues (does not gate)
- **Explicit override:** `RELEASE_GATE_REQUIRE_MCP=1` makes it gating in any profile

**Rationale:**
- MCP smoke is still evolving
- Don't want to gate all external CI runs on experimental features
- Allows tightening to STRICT later based on adoption
- Gives operators explicit control when they need strict enforcement

### 4. Proof-Bundle Directory Layout Versioning

**Decision:** Do NOT treat folder layout as a versioned contract.

**Contract:** Schemas are the contract, not directory structure.

**Guidance for Consumers:**
- Use `$PROOF_BUNDLE_OUT_BASE` and `$RELEASE_GATE_RUN_ID` env vars if needed
- Do not parse directory paths
- Rely on file presence within the directory, not directory name format

**Rationale:**
- Allows future flexibility (e.g., moving to `artifacts/`, operator-specified paths)
- Consumers should interact via env vars, not hardcoded paths
- Schema stability is what matters for CI/CD integration

### 5. RUN_ID Format

**Decision:** Treat as implementation detail.

**Current format:** `date +%Y%m%d_%H%M%S` (timestamp-based)

**Contract:** No guarantee on RUN_ID format. May change.

**Guidance for Consumers:**
- Use `$RELEASE_GATE_RUN_ID` env var if you need the run ID
- Do not parse directory names to extract run IDs
- Do not assume timestamp format

**Rationale:**
- Implementation flexibility (could switch to UUID, git SHA, incremental counter)
- Consumers should use env vars, not parse opaque identifiers

---

## Proof Bundle Contract (STANDARD+)

### Required Files

1. **`proof_packet.tar`** → **FROZEN**
   - Schema: `proof_packet_v1` manifest
   - Format: Deterministic tar (USTAR, mtime=0, sorted members)
   - Guarantee: Byte-stable for same inputs

2. **`proof_packet_verify_summary.json`** → **VERSIONED STRICT**
   - Schema: `proof_packet_verify_summary_v1`
   - Guarantee: Additive-only within v1

3. **`proof_packet.sha256`** → **STABLE FORMAT**
   - Format: RFC 3174 hex lowercase
   - Content: `<sha256-hex>  proof_packet.tar\n`

4. **`release_gate_log.txt`** → **DOCUMENTED FORMAT**
   - Format: key=value pairs (one per line)
   - Evolution: New keys can be added, existing keys immutable

5. **`versions.txt`** → **DOCUMENTED FORMAT**
   - Format: key=value pairs (one per line)
   - Evolution: New keys can be added, existing keys immutable

### Optional Files

- **`queue_drift_scan.txt`**: May contain output or "INFO: queue-drift-scan unavailable\n" sentinel
- Future additions allowed without contract change

---

## Profile Semantics (STANDARD)

### dev (default)

- **Proof-packet check:** Informational (failure does not gate)
- **Other checks:** Informational
- **Outputs:** Always emitted
- **Use case:** Local development, testing, iteration

### ci

- **Proof-packet check:** Gating (failure causes exit 1)
- **Other checks:** Informational
- **Outputs:** Emitted on success
- **Use case:** Continuous integration, automated testing

### Override Precedence

```
RELEASE_GATE_STRICT_PROOF_PACKET (explicit env var)
  > GOV_PROFILE (dev/ci)
  > default (dev)
```

**Logging:** Release-gate logs show "strictness source=profile" or "source=env_override"

---

## Compatibility Policy (STRICT for core, STANDARD for auxiliary)

### Core Schemas (STRICT)

**`proof_packet_v1` manifest:**
- **FROZEN** within v1
- No field changes allowed (no add/remove/rename/retype)
- Version bump to v2 required for any changes

**`proof_packet_verify_summary_v1`:**
- **ADDITIVE-ONLY** within v1
- Can add new top-level keys (documented)
- Cannot remove, rename, or retype existing keys
- Version bump to v2 required for breaking changes

### Auxiliary Formats (STANDARD)

**`release_gate_log.txt`, `versions.txt`:**
- Key=value format documented
- New keys can be added without version bump
- Existing keys cannot be removed without 1 release deprecation notice
- Format changes allowed with documentation

### Version Bump Policy

| Change Type | Core Schema | Auxiliary File |
|-------------|-------------|----------------|
| Add field/key | Document, no bump | Document, no bump |
| Remove field/key | MAJOR bump (v1→v2) | Deprecate 1 release, then remove with notes |
| Rename field/key | MAJOR bump | Deprecate + add new key |
| Change type | MAJOR bump | Avoid; treat as remove + add |

---

## Dependency Handling (STANDARD)

### dev Profile

- MCP smoke runs if available
- Missing dependency → INFO log, continue
- `queue_drift_scan.txt` contains output or "INFO: queue-drift-scan unavailable\n"

### ci Profile

- MCP smoke runs if available
- Missing dependency → WARN log, continue (does not gate)
- `queue_drift_scan.txt` contains output or "WARN: queue-drift-scan unavailable\n"

### Explicit Override

- `RELEASE_GATE_REQUIRE_MCP=1` makes MCP smoke gating in any profile
- Fails with exit 1 if dependency unavailable

### Success Criteria

External run success means:
1. `release-gate.sh` exits 0
2. Proof-bundle directory exists at `$PROOF_BUNDLE_OUT_BASE/$RUN_ID/`
3. All required files present (5 files listed above)

---

## Rationale

### Why STRICT for Core Schemas?

1. **External integration dependency:** CI/CD pipelines parse these, breaking them breaks deployments
2. **Attestation use case:** Determinism is critical for cryptographic verification
3. **External tooling:** Third-party tools will build on these, stability enables ecosystem
4. **Trust boundary:** These are the primary external interface, require highest stability

### Why STANDARD for Profiles?

1. **Common mental model:** dev/ci matches standard industry practice
2. **Simple override:** Single env var covers primary use cases
3. **Room for growth:** Can add "prod" profile later without breaking existing usage
4. **Operator clarity:** Two profiles reduces confusion vs. many fine-grained flags

### Why STANDARD for Dependencies?

1. **Evolutionary flexibility:** MCP smoke is still stabilizing
2. **External adoption:** Don't want to gate external runs on experimental features
3. **Explicit control:** Operators can enforce when needed via override flag
4. **Tightenable:** Can move to STRICT later based on real-world usage patterns

### Why STANDARD for Auxiliary Files?

1. **Debugging evolution:** Logs should be evolvable for troubleshooting
2. **Consumer focus:** Key consumers care about proof-packet + summary, not logs
3. **Additive flexibility:** Allows adding useful version/context fields without breaking

---

## Acceptance Criteria

### Proof Bundle Contract

- [ ] Required files present: `release-gate.sh` emits all 5 required files
- [ ] Determinism: Repeated runs produce identical `proof_packet.tar` SHA256
- [ ] Schema compliance: `proof_packet.tar` contains valid `proof_packet_v1` manifest
- [ ] Summary schema: `proof_packet_verify_summary.json` matches `proof_packet_verify_summary_v1`
- [ ] SHA256 format: `proof_packet.sha256` contains lowercase hex
- [ ] Auxiliary formats: `release_gate_log.txt` and `versions.txt` follow key=value format
- [ ] Optional handling: `queue_drift_scan.txt` contains output or "unavailable" sentinel

### Profile Semantics

- [ ] Default profile: `GOV_PROFILE` defaults to `dev`
- [ ] dev behavior: `GOV_PROFILE=dev` sets `STRICT_PROOF_PACKET=0`, non-gating
- [ ] ci behavior: `GOV_PROFILE=ci` sets `STRICT_PROOF_PACKET=1`, gating
- [ ] Override precedence: `RELEASE_GATE_STRICT_PROOF_PACKET` overrides `GOV_PROFILE`
- [ ] Output guarantee: Proof-bundle emitted in both dev and ci when proof-packet check runs
- [ ] Logged source: Logs show "strictness source=profile" or "source=env_override"

### Compatibility

- [ ] Manifest frozen: `proof_packet_v1` documented and frozen
- [ ] Summary additive: `proof_packet_verify_summary_v1` documented, additive-only
- [ ] Version bump policy: Criteria documented for v1 → v2
- [ ] Auxiliary evolution: `log.txt` and `versions.txt` evolution rules documented
- [ ] Deprecation process: Policy documented for deprecating auxiliary keys (1 release notice)

### Dependency Handling

- [ ] MCP availability check: Release-gate checks before running
- [ ] dev missing: Logs "INFO: unavailable", continues, writes sentinel
- [ ] ci missing: Logs "WARN: unavailable", continues (does not gate)
- [ ] Explicit require: `RELEASE_GATE_REQUIRE_MCP=1` makes gating, fails if unavailable
- [ ] Success definition: exit 0 AND proof-bundle directory exists with required files

### Test Enforcement

- [ ] Contract validation: `test_proof_bundle_contract.sh` validates required files
- [ ] Determinism: `test_proof_bundle_determinism.sh` validates byte-stable tar
- [ ] Schema validation: `test_proof_bundle_schema.sh` validates manifest
- [ ] Summary validation: `test_summary_schema.sh` validates summary schema
- [ ] Auxiliary formats: `test_auxiliary_formats.sh` validates key=value formats
- [ ] Profile semantics: `test_profile_semantics.sh` validates dev vs ci
- [ ] Profile override: `test_profile_override.sh` validates precedence
- [ ] Dependency handling: `test_mcp_skip_*.sh` validates skip semantics
- [ ] Regression protection: Schema changes caught by tests before merge

### Documentation Requirements

- [ ] Core schemas: `proof_packet_v1` and `proof_packet_verify_summary_v1` in ATTESTATION_SPEC.md
- [ ] Profile semantics: dev/ci behavior in RUNBOOK.md
- [ ] Auxiliary formats: `log.txt` and `versions.txt` in RUNBOOK.md
- [ ] Version bump policy: Compatibility rules in EXTERNAL_CONTRACTS.md
- [ ] External usage: Quickstart + compatibility in README.md
- [ ] Dependency handling: MCP skip semantics in RUNBOOK.md

---

## Status and Next Steps

**Status**: [DECIDED] as of 2026-02-25

**Implemented:**
- Proof-bundle output directory contract (TASK_136)
- GOV_PROFILE dev/ci mapping (TASK_137)
- GitHub Actions workflow (TASK_138)
- External documentation (TASK_134, TASK_139, TASK_140)

**Remaining Documentation Work:**
- Formalize schema freeze policy in ATTESTATION_SPEC.md
- Document auxiliary file formats in RUNBOOK.md
- Create EXTERNAL_CONTRACTS.md reference
- Add versioning policy to README.md

**No implementation blockers.** Contract decisions are captured and ready to guide future tasks.

---

## References

- Design memo source: Cecil session 2026-02-25 (external usability contracts analysis)
- Related tasks: TASK_134-141 (external usability tranche)
- Related specs: ATTESTATION_SPEC.md (proof-packet schemas)
- Related docs: RUNBOOK.md (operational procedures), README.md (external quickstart)
