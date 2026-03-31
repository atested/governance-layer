# QT Runtime Proof v0

## 1. Purpose

This record captures one bounded direct runtime proof for QT under the now-live Codex routed-runtime baseline.

Its purpose is to answer a narrow question:

Can Codex truthfully invoke QT on one bounded task and verify the result well enough to close the residual QT caveat?

## 2. Residual caveat under test

Residual caveat under test:
- QT-first was already live as the controlling delegation rule
- QT runtime execution had not yet been directly proven

This record tests runtime proof, not policy restatement.

## 3. QT invocation path used

QT invocation path used:
- `system/scripts/qt-runner.sh`

Schema used:
- `docs/dev/QT_JOB_SCHEMA.md`

Invocation form used:

```bash
bash system/scripts/qt-runner.sh jobs/QT_JOB_999.md
```

Job type used:
- `merge_readiness`

This is an actual runnable QT path, not an inferred or hypothetical path.

## 4. Bounded proof task selected

Selected proof task:
- one controlled `merge_readiness` QT job against a minimal `codex/TASK_999` branch in a temporary bounded git repository

Why this task shape was selected:
- QT is the correct default worker for a small merge-readiness validation
- success/failure is deterministic and easy to verify
- parent verification cost is low
- no product work is mixed into the proof
- no broader repo redesign is required

Task content under test:
- one task spec with `TASK_ID: TASK_999`
- one allowed-files section
- one evidence file at `docs/dev/evidence/TASK_999/TESTS.txt`
- one target branch `codex/TASK_999`

## 5. Proof steps performed

1. Verified current `main` contains the Codex routed-runtime baseline and capability-tier artifacts.
2. Identified `system/scripts/qt-runner.sh` as the actual QT runtime invocation path.
3. Created a minimal temporary repository with:
   - a bare local `origin`
   - `main`
   - one topic branch `codex/TASK_999`
   - one task spec
   - one evidence file
4. Authored QT job file `jobs/QT_JOB_999.md` with:
   - `JOB_ID: QT_JOB_999`
   - `JOB_TYPE: merge_readiness`
   - `TARGET_BRANCH: codex/TASK_999`
   - `TASK_ID: TASK_999`
   - `TASK_SPEC: docs/dev/tasks/ready/TASK_999__qt_runtime_demo.md`
5. Ran:
   - `bash system/scripts/qt-runner.sh jobs/QT_JOB_999.md`
6. Verified:
   - runner exit code
   - stdout result
   - emitted `docs/dev/evidence/QT/QT_JOB_999/QT_REPORT.md`
   - emitted `docs/dev/evidence/QT/QT_JOB_999/TESTS.txt`
   - correctness of the returned checks at parent level

## 6. Observed result

Observed invocation result:
- exit code: `0`
- stdout: `qt-runner: PASS (QT_JOB_999)`

Observed QT report result:
- `PASS`
- `All merge-readiness checks passed.`

Observed checks inside QT evidence:
- target branch resolved
- task spec readable from target branch
- `TASK_ID` matched
- evidence file existed on target branch
- evidence file contained command/exit markers
- changed files complied with the allowlist

Observed output artifacts:
- `docs/dev/evidence/QT/QT_JOB_999/QT_REPORT.md`
- `docs/dev/evidence/QT/QT_JOB_999/TESTS.txt`

## 7. Parent verification performed

Parent verification performed:
- verified the invocation path was an actual executable script
- verified the job schema used matched the live QT schema
- verified the runner exited `0`
- verified the report file recorded `PASS`
- inspected the raw QT `TESTS.txt` evidence
- confirmed the checks QT reported were concrete and low-cost to verify

The parent did not rely only on the `PASS` headline.
The parent checked the underlying logged checks and their outputs.

## 8. Final QT status

Final QT status:

**QT directly proven live**

This record supports that conclusion because:
- QT was actually invoked
- the invocation path was clear and runnable
- QT produced concrete output artifacts
- the result was parent-verifiable at low cost
- the bounded task shape was appropriate for QT as the default subordinate worker

## 9. If not proven, exact blocking layer

Not applicable in this run.

No blocking layer was observed in:
- configuration
- invocation surface
- runtime access
- output quality
- verification burden

## 10. Conclusion

QT is directly proven live as a usable bounded subordinate worker for Codex in practice.

This closes the residual QT runtime caveat at the minimum level required by the Codex routed-runtime baseline:
- QT-first is not only documented
- QT is actually invokable
- QT can complete one bounded representative verification task
- the result is parent-verifiable without excessive review burden
