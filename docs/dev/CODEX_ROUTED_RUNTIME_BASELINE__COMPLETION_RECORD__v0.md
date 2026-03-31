# Codex Routed-Runtime Baseline Completion Record v0

## 1. Purpose

This record documents bounded proof that the Codex routed-runtime baseline is real at the intended minimum level.

The purpose of this record is not to restate the plan. It is to show, using observed evidence, what is now operational, what was directly proven in Lane 4, and what remains only indirectly evidenced.

## 2. Baseline under test

Baseline under test:
- `docs/dev/CODEX_ROUTED_RUNTIME_BASELINE_PLAN__v0.md`
- `docs/dev/CODEX_CAPABILITY_TIER__v0.md`
- `system/scripts/codex-unattended.sh` as it exists on `main` at `b0ab5e2975818e8aa75b8b6a2361480ac7990099`

Claims under test:
1. Codex capability-tier is live as the controlling role/boundary model.
2. QT-first is the controlling internal delegation rule.
3. Lane 2 completion packet emission works in practice.
4. Lane 3 reception checks work in practice.
5. A full bounded Codex task can run end to end under the now-live baseline.
6. The resulting evidence is sufficient to say the baseline is operational at the intended minimum level.

## 3. Current live components

The following baseline components were present on `main` and available for proof:
- baseline plan document
- Codex capability-tier document
- `codex-unattended.sh` with:
  - task-spec resolution
  - allowed-files parsing
  - verify/finalize flow
  - structured completion packet emission
  - operational reception-check path

These are live components, not proposed-only artifacts.

## 4. Proof actions performed

Lane 4 used a bounded controlled test repository with a local bare `origin` to avoid widening scope while still exercising the live Codex runtime path truthfully.

Proof actions:
1. Created a minimal repository containing the live `codex-unattended.sh`, one bounded task spec, one evidence directory, and one allowed file.
2. Created representative success task `TASK_999` with:
   - valid task spec
   - valid `Allowed Files`
   - valid `docs/dev/evidence/TASK_999/TESTS.txt`
   - topic branch `codex/TASK_999`
3. Ran:
   - `reception-check TASK_999`
   - `finalize-task TASK_999 'TASK_999: demo finalize'`
4. Verified that:
   - reception accepted truthfully
   - finalize succeeded
   - a completion packet was emitted
   - the task branch pushed successfully
   - local and remote branch heads matched
5. Created representative failure task `TASK_998` with:
   - valid task spec
   - no `TESTS.txt`
6. Ran:
   - `reception-check TASK_998`
7. Verified that:
   - reception failed closed
   - the failure reason was truthful and operationally specific

QT was not exercised in this lane.

## 5. Evidence observed

### Success-path observations

Observed success markers:
- `reception-check: OK (TASK_999)`
- `verify-task: OK (TASK_999)`
- `completion-packet: OK (docs/dev/evidence/TASK_999/COMPLETION_PACKET.json)`
- `finalize-task: OK (TASK_999)`

Observed completion-packet facts:
- `PACKET_TASK_ID=TASK_999`
- `PACKET_STATUS=published`
- `PACKET_BRANCH=codex/TASK_999`
- `PACKET_EVIDENCE_PRESENT=true`
- `PACKET_ALLOWED_FILES_COMPLIANT=true`
- `PACKET_FORBIDDEN_FILES_CLEAN=true`
- `PACKET_HAS_MODEL_USED=false`
- `PACKET_HAS_TOKEN_USAGE=false`

Observed publish verification:
- `VALID_HEAD=4ea0cee09f3b0566ff461cec4895889c4a2055e7`
- `VALID_REMOTE=4ea0cee09f3b0566ff461cec4895889c4a2055e7`

This proves the representative run published successfully and that the completion packet did not fabricate opaque internals.

### Failure-path observations

Observed rejection:
- `ERROR: Missing evidence file: docs/dev/evidence/TASK_998/TESTS.txt`

This proves the reception check fails closed when required intake evidence is missing and does not report false success.

## 6. What is proven live

### Directly proven live in Lane 4

The following are directly proven by bounded execution evidence:
- Lane 3 reception acceptance works for a valid bounded intake.
- Lane 3 reception rejection works for an invalid bounded intake.
- Rejection reason is truthful and operationally useful.
- Lane 2 completion packet emission works in practice on success.
- Completion packet output is truthful at the minimum required level.
- A bounded Codex task can run end to end under the live baseline through:
  - topic-branch execution context
  - verification
  - publish
  - completion packet emission

### Live by prior lane implementation plus bounded confirmation

The following are live on `main` and supported by bounded confirmation in this lane:
- the Codex capability-tier document is present as the controlling role/boundary artifact
- the capability-tier truth rules are consistent with the observed completion packet behavior
- QT-first is encoded as the controlling internal delegation rule in the capability-tier artifact

## 7. What is not directly proven and why

QT was **not directly proven** in this lane.

Reason:
- Lane 4 did not execute a bounded QT job with runtime evidence.
- Forcing QT execution here would have widened the lane from baseline proof into additional verification-surface work.
- No truthful runtime evidence from this lane shows QT actually ran.

Therefore QT status in this record is:
- **directly proven:** no
- **indirectly supported:** yes, because QT-first is live in the controlling capability-tier document and QT remains part of the baseline design
- **not yet runtime-proven in Lane 4:** yes

This record does not overclaim QT execution.

## 8. Resulting baseline status

Resulting baseline status:

**complete with residual caveat**

The Codex routed-runtime baseline is operational at the intended minimum level because:
- the role/boundary model is live on main
- reception checks are live and fail closed
- completion packet emission is live and truthful
- a representative bounded Codex task can complete end to end under the baseline

The residual caveat is that QT-first is live as a controlling rule but QT was not directly runtime-proven in this lane.

## 9. Residual caveats

Residual caveats:
- QT was not directly exercised in this lane.
- The proof run used a bounded controlled repository rather than a larger real repo task branch. This is acceptable for baseline proof because the goal was truthful minimal proof, not broader throughput validation.
- The baseline remains intentionally minimal. This record does not prove broader routing redesign, ledger integration, or richer runtime introspection.

## 10. Final conclusion

The Codex routed-runtime baseline is now operational at the intended minimum level, with one named residual caveat: QT-first is live as a controlling rule but not directly runtime-proven by Lane 4 evidence.

That is sufficient to truthfully conclude:
- Codex has a real bounded routed-runtime baseline
- the baseline is usable for branch-scoped execution
- the baseline does not require further runtime changes to support the minimum claim
- any stronger claim about QT runtime proof should wait for a separate direct verification pass
