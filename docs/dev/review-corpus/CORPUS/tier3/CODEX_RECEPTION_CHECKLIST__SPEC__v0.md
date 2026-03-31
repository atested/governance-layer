# Codex Reception Checklist Specification

Version: v0 (planning draft)
Status: Phase 1 specification — not yet operational
Deployment: Codex project-level instruction or dispatch preamble

## 1. Purpose

1.1. The Codex reception checklist defines validation that Codex MUST perform on every incoming dispatch before beginning execution.

1.2. It ensures that Codex does not begin work on an underspecified dispatch by inferring missing elements.

1.3. It complements the ChatGPT dispatch operating card: the card defines what ChatGPT must produce; the checklist defines what Codex must verify upon receipt.

## 2. Required Dispatch Envelope Elements

Every incoming dispatch MUST contain the following elements. Codex MUST verify their presence before starting work.

| Element | Description | Required |
|---|---|---|
| Mode | Execute or Investigate | YES |
| Objective | What the work must accomplish | YES |
| What is fixed | Invariants, constraints, non-goals | YES |
| Output contract | Expected output type and landing location | YES |
| Acceptance boundary | What "done" looks like | YES |
| STOP conditions | Conditions that halt work | YES |
| Base SHA | Expected origin/main or branch base | YES |
| Allowed files | Files permitted for modification (Execute mode) | YES for Execute |
| Lane structure | Lane definitions if multi-lane | YES if multi-lane |
| Synthesis contract | Synthesis action and final artifact if multi-lane | YES if multi-lane |
| Prior investigation references | Pointers to prior investigation outputs if applicable | IF APPLICABLE |

## 3. Missing-Element Behavior

### 3.1. If Any Required Element Is Missing

Codex MUST request clarification before starting work. Codex MUST NOT:
- Infer the missing element from context.
- Assume a default value.
- Begin work and treat the missing element as optional.

### 3.2. Clarification Request Format

Codex SHOULD request clarification using this format:

```
DISPATCH INCOMPLETE: The following required elements are missing:
1. [element name]: [what is needed]
2. [element name]: [what is needed]

Cannot proceed until these are provided.
```

### 3.3. If Clarification Cannot Be Obtained

If Codex cannot obtain clarification (e.g., running in unattended mode), Codex MUST fail closed:
- Do not begin execution.
- Report the missing elements in the completion packet.
- Set completion status to BLOCKED.

## 4. Prior Investigation References

### 4.1. When Applicable

If the dispatch references prior investigation work (e.g., "see investigation report from TASK_NNN"), Codex MUST:
1. Verify the referenced file exists at the specified location.
2. Read the referenced file before beginning execution.
3. If the referenced file does not exist, treat this as a missing required element (Section 3.1).

### 4.2. When Not Referenced

If the dispatch does not reference prior investigations, Codex MUST NOT search for or consume investigation outputs on its own initiative. Investigation outputs are consumed only when explicitly referenced in the dispatch.

## 5. Landing-Zone References

### 5.1. Execute Mode

For Execute-mode dispatches, the output contract specifies where code changes, evidence, and completion artifacts land. Codex MUST follow the specified locations.

### 5.2. Investigate Mode

For Investigate-mode dispatches, the output contract MUST specify a landing location for the investigation report. At Phase 1, this is stated in the dispatch. Starting in Phase 2, the default landing zone will be `docs/dev/analysis/`.

If no landing location is specified in an Investigate-mode dispatch, Codex MUST request clarification (Section 3.1).

## 6. What Codex MUST NOT Infer Silently

Codex MUST NOT silently infer or assume any of the following:

1. **Mode**: If mode is not declared, do not guess Execute or Investigate.
2. **Scope**: If allowed files or scope boundaries are not stated, do not assume "everything is in scope."
3. **Acceptance criteria**: If acceptance boundary is not stated, do not assume "compiles and passes tests" is sufficient.
4. **STOP conditions**: If STOP conditions are not stated, do not assume only the default OPS_PROCESS v1 STOP conditions apply.
5. **Synthesis action**: If multi-lane work lacks a synthesis contract, do not assume how to combine lane outputs.
6. **Prior work**: If the dispatch does not reference prior investigations, do not search for or consume them.

## 7. Relation to Existing Codex Workfront Rules

### 7.1. OPS_PROCESS v1 Section 9.1

The reception checklist extends, but does not replace, the requirements in OPS_PROCESS v1 Section 9.1. Specifically:
- Base SHA expectations remain required.
- Hot file list and "do not touch" rules remain required.
- Per-task reporting requirements remain required.

The reception checklist adds: mode declaration, shared-frame elements, output contract with acceptance boundary, and prior-investigation-reference handling.

### 7.2. DISPATCH_LIBRARY v10

The reception checklist does not replace DISPATCH_LIBRARY v10 requirements. Specifically:
- Mandatory preflight (task-id-guard.sh) remains required for restock/publish batches.
- Validation-scope expansion for sensitive surfaces remains required.

The reception checklist validates the dispatch envelope. DISPATCH_LIBRARY v10 validates task-level and sensitive-surface requirements. Both apply.

### 7.3. OPS_CANONICAL

The reception checklist does not affect OPS_CANONICAL. Lane rules, invariants, and script registry remain unchanged.

## 8. Deployment

### 8.1. Form

The reception checklist is deployed as a project-level instruction for Codex. It is not a separate file that Codex reads at runtime — it is part of Codex's operating context.

### 8.2. Content

The project-level instruction contains the validation rules from Sections 2–6 of this specification in a concise operational form.

### 8.3. Update Cadence

When this specification changes, the Codex project-level instruction MUST be updated to match before the next dispatch.
