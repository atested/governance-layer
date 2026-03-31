# Risk Assessment: Wire Ops Process Doc to Codex

## Risk Level: LOW

## Changes

This change modifies the Codex execution contract construction to automatically prepend the ops process doc to every Codex run.

## Risk Factors

### 1. Execution Contract Size
**Risk**: Prepending ~10KB ops doc increases prompt size for every Codex execution
**Mitigation**:
- Ops doc is ~265 lines, well within Claude's context window
- Content is stable and won't grow unboundedly
- Benefit (consistent ops guidance) outweighs cost (slightly larger prompts)

### 2. Missing File Failure Mode
**Risk**: If ops doc is deleted/moved, all Codex runs will fail
**Mitigation**:
- Fail-closed is intentional design (better than silent degradation)
- Clear error message identifies the missing file
- Test coverage verifies fail-closed behavior

### 3. Execution Performance
**Risk**: Reading ops doc file on every execute-task call adds overhead
**Mitigation**:
- File read is ~10KB (negligible I/O)
- Happens once per task, not per-command
- No network calls or external dependencies

## Rollback Plan

If issues arise:
1. Revert the change to `cmd_execute_task()` in codex-unattended.sh
2. Remove ops doc prepending logic (lines with `cat "$ops_process_doc"`)
3. Keep AGENTS.md (informational only, no execution impact)

## Testing

- Verification test passes all 8 checks
- Fail-closed guards confirmed working
- No changes to existing task execution flow beyond preamble

## Conclusion

Low-risk change with high value. Fail-closed design ensures ops doc absence is caught immediately rather than causing silent degradation of Codex guidance quality.
