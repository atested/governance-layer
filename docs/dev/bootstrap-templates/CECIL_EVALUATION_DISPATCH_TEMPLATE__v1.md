# Cecil Evaluation Dispatch Template v1

**What this is:** The canonical template for the Cecil Evaluation Dispatch that ChatGPT produces at Stage 3 of the bootstrap protocol when preliminary screening passes. ChatGPT fills in this template with the Seed Package contents and screening notes, then the operator pastes the result to Cecil.

**Protocol:** NEW_PROJECT_BOOTSTRAP_PROTOCOL v1

---

## 1. Purpose

The Cecil Evaluation Dispatch delivers a screened Seed Package to Cecil for promotability evaluation. It is the handoff artifact between ChatGPT (preliminary screening) and Cecil (sole promotability authority).

## 2. Authority boundary

- ChatGPT produces this dispatch after preliminary screening passes.
- ChatGPT's screening is structural completeness only. It does not constitute a promotability judgment.
- Cecil is the sole authority on whether a seed is promoted to bootstrap.
- The dispatch must explicitly state this authority boundary.

## 3. Template

ChatGPT produces the dispatch by instantiating the following structure. All `{placeholder}` fields are filled from the Seed Package and screening results.

```
CECIL EVALUATION DISPATCH
Protocol: NEW_PROJECT_BOOTSTRAP_PROTOCOL v1
Dispatch type: SEED PROMOTABILITY EVALUATION
Date: {ISO 8601 UTC date}

AUTHORITY NOTE:
This dispatch carries a preliminary-screened Seed Package.
Preliminary screening was performed by ChatGPT and checks structural
completeness only. Promotability evaluation is Cecil's sole authority.

SEED PACKAGE VERSION: v{N}
PRIOR VERSIONS: {count of prior versions, or "none"}

--- SEED PACKAGE ---

{The complete Seed Package, including all sections:
 - Version header
 - Structured extraction
 - Source excerpts
 - Implementation sketches (if any)
 - Preliminary screening result}

--- END SEED PACKAGE ---

PRELIMINARY SCREENING SUMMARY:
  Result: PASS
  Criteria met: all 6 (implementation intent, scope boundary, deliverable
    clarity, task concreteness, constraint legibility, naming viability)
  Flags for Cecil:
    - {flag 1, if any}
    - {flag 2, if any}
    - {or "none"}

CHATGPT OBSERVATIONS:
{Any additional observations ChatGPT wants to provide that are not
 captured in the Seed Package fields or flags. For example:
 - notes about the quality or clarity of the seed content
 - concerns about scope stability that did not constitute screening failures
 - suggestions for Cecil to examine specific source excerpts
 If none: "No additional observations."}

REQUESTED CECIL ACTION:
Evaluate this Seed Package for promotability. Return one of:

  PROMOTE — the seed is viable for project bootstrap.
    Include an Approved Bootstrap Plan with:
    - finalized project identity binding fields
    - repo name and directory structure
    - universal file manifest
    - repo-local file list with stub guidance
    - any project-specific constraints or deviations
    - activation test suite parameters

  REVISE — the seed has specific deficiencies that must be addressed
    before promotion.
    Include:
    - specific deficiencies with descriptions
    - what the operator or ChatGPT must provide to resolve them

  REJECT — the seed is not viable for project creation.
    Include:
    - clear reason for rejection
    - whether the seed could become viable with substantial rework
      or is fundamentally unsuitable
```

## 4. Dispatch requirements

### Must include

- The complete Seed Package with all sections intact (structured extraction, source excerpts, implementation sketches, preliminary screening result). Do not summarize or truncate the package.
- The version number of the Seed Package and count of prior versions.
- The preliminary screening summary with explicit pass confirmation and all criteria listed.
- All `flags_for_cecil` from the screening result.
- The authority note stating that promotability evaluation is Cecil's sole authority.
- The explicit list of expected Cecil outputs (PROMOTE / REVISE / REJECT) with required contents for each.

### Must not include

- A promotability recommendation from ChatGPT. ChatGPT does not recommend promotion or rejection.
- Architectural opinions or design suggestions. Those are Cecil's domain.
- References to repo surfaces that do not yet exist. This is a pre-repo artifact.

## 5. Operator instructions

When ChatGPT produces this dispatch:

1. ChatGPT presents it to the operator in the destination working chat.
2. The operator copies the entire dispatch.
3. The operator opens a Cecil session (governance-layer repo or any Cecil-capable context).
4. The operator pastes the dispatch to Cecil.
5. Cecil evaluates and returns a verdict.
6. The operator brings Cecil's verdict back to the destination working chat.

If Cecil returns REVISE:
- The operator provides the deficiency information in the destination working chat.
- ChatGPT updates the Seed Package (new version).
- ChatGPT produces a new Cecil Evaluation Dispatch with the updated package.
- The operator re-dispatches to Cecil.

If Cecil returns REJECT:
- The bootstrap halts.
- Cecil's reason is the authoritative explanation.
- The operator may attempt a new bootstrap with different or expanded seed material.
