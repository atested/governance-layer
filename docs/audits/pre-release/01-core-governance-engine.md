## Code Review — Core Governance Engine

### Scope
- Files reviewed: `scripts/classifier.py`, `scripts/policy_eval_v2.py`, `scripts/policy_eval_shared.py`, `scripts/mediation.py`, `scripts/event_model.py`, `scripts/append-record-runtime.sh`, `scripts/append-record.sh`, `scripts/verify-chain.py`, `scripts/atested_cli.py`
- Design docs referenced: `docs/design/atested-v3-design.md` (sections 3-5, 10), `docs/INVARIANTS.md` (INV-001, INV-002, INV-004, INV-006, INV-008, INV-010)
- Tests examined: `tests/test_classifier.py`, `tests/test_policy_eval_v2.py`, `tests/test_mediation.py`, `tests/test_inv010_enforcement.py`, `tests/test_behavioral_equivalence.py`, `tests/test_atested_cli.py`

### Confirmed Working As Designed
- Evidence-based classification is implemented as designed (classification sourced from call parameters, not declarations), with explicit confidence tiers and extracted evidence fields in `scripts/classifier.py`.
- Policy evaluation is deterministic and hash-linked: v2 record hash computation uses canonical JSON with `record_hash` nulled before hashing (`scripts/policy_eval_v2.py:204-209`), matching replay/verifiability intent.
- Chain append lock protocol is implemented in shell writers with cross-process `mkdir` lock and read-head-inside-lock flow (`scripts/append-record-runtime.sh:26-45`, `scripts/append-record.sh:24-42`), aligned with INV-010.
- Targeted core tests passed cleanly: `113 passed` (`test_classifier`, `test_policy_eval_v2`, `test_mediation`).

### Issues Found
| # | Severity | File:Line | Description | Design Reference |
|---|----------|-----------|-------------|-----------------|
| 1 | minor | `scripts/classifier.py:21`, `scripts/policy_eval_v2.py:10` | File headers still reference `docs/design/govmcp-v2-design-revised.md`; current design baseline for this repo is v3 (`docs/design/atested-v3-design.md`). This creates maintenance ambiguity for future changes. | `docs/design/atested-v3-design.md` |

### Test Coverage Assessment
- Coverage is strong for core classifier/policy/mediation paths and decision-record shape.
- INV-010 enforcement has explicit tests.
- Behavioral equivalence has 8 skipped tests (`tests/test_behavioral_equivalence.py`), so parity guarantees remain partially unverified in routine runs.

### Observations
- Core engine code is generally coherent and deterministic.
- Locking and record-shape invariants are consistently applied in reviewed core paths.
