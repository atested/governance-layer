# Preliminary Screening Reference v1

**What this is:** The canonical reference for ChatGPT's preliminary screening behavior during project bootstrap. This document defines what ChatGPT checks, what constitutes a deficiency, how deficiency reporting works, and how reruns work after repair.

**Protocol:** NEW_PROJECT_BOOTSTRAP_PROTOCOL v1

---

## 1. Scope of preliminary screening

Preliminary screening is a structural completeness check performed by ChatGPT at Stage 3 of the bootstrap protocol. Its purpose is to catch obvious structural gaps before the Seed Package is forwarded to Cecil for promotability evaluation.

### What preliminary screening is

- A check that the Seed Package contains enough structured information to be evaluable by Cecil.
- A filter for obviously incomplete seeds that would waste Cecil evaluation capacity.

### What preliminary screening is not

- **Not a promotability judgment.** ChatGPT does not decide whether a seed should become a project. That is Cecil's sole authority.
- **Not an architectural evaluation.** ChatGPT does not assess whether the project's architecture is sound, whether its scope is stable, or whether first-pass canon can be authored without major invention.
- **Not a quality gate.** A seed that passes screening may still be rejected or revised by Cecil.

A screening pass means: the Seed Package is structurally complete enough to forward to Cecil for evaluation.

A screening pass does not mean: the seed is ready for bootstrap.

## 2. Screening criteria

All 6 criteria must be met for a preliminary screen pass. Failure on any criterion results in a fail.

### Criterion 1: Implementation intent

The seed contains at least one concrete thing to build — not just discussion, exploration, or brainstorming.

**Pass example:** "We need a CLI tool that converts markdown files to PDF."
**Fail example:** "We've been thinking about whether document conversion is worth pursuing."

### Criterion 2: Scope boundary

The project scope can be stated in 1-3 sentences without requiring further research, discovery, or design work.

**Pass example:** "A Python library for parsing and validating governance chain JSONL files."
**Fail example:** The seed discusses multiple possible projects without settling on one, or the scope requires investigation to determine.

### Criterion 3: Deliverable clarity

The primary deliverable type is identifiable as one of: `library`, `service`, `tool`, `spec_corpus`, or `mixed`.

**Pass example:** The seed clearly describes building a command-line tool.
**Fail example:** The seed discusses ideas without indicating what form the output takes.

### Criterion 4: Task concreteness

At least one initial task candidate can be written with a title, a one-sentence scope, and a deliverable type (`code`, `spec`, `test`, or `config`).

**Pass example:** "Title: Implement markdown parser. Scope: Parse markdown files into an AST. Deliverable: code."
**Fail example:** The seed contains only high-level goals with no decomposition into concrete tasks.

### Criterion 5: Constraint legibility

Key constraints are either explicitly stated in the seed or clearly derivable from the seed content. The project does not require discovering its own constraints through exploratory implementation.

**Pass example:** "Must run on Python 3.10+, must not require external services, output must be deterministic."
**Fail example:** The seed mentions constraints might exist but says "we'll figure those out as we go."

### Criterion 6: Naming viability

A project name and repo name candidate can be derived from the seed without ambiguity. The name must be usable as a GitHub repo name (lowercase, hyphens allowed, no spaces).

**Pass example:** The seed consistently refers to the project by a name, or the scope is specific enough that a name is obvious.
**Fail example:** The seed uses multiple different names interchangeably, or the scope is too vague to derive a name.

## 3. Screening result

The screening result is recorded in the `preliminary_screening` field of the Seed Package:

```
preliminary_screening:
  structural_completeness: pass    # or "fail"
  deficiencies: []                 # empty if pass
  flags_for_cecil:                 # observations regardless of pass/fail
    - "scope boundary may be broader than stated"
    - "operator notes suggest timeline pressure"
```

### Pass behavior

If all 6 criteria are met:
1. Set `structural_completeness: pass`.
2. Leave `deficiencies` empty.
3. Add any observations to `flags_for_cecil` that ChatGPT wants Cecil to be aware of — these are not deficiencies, just items worth noting (e.g., scope might be broader than stated, constraints seem tentative, multiple architectural approaches remain open).
4. Produce a CECIL EVALUATION DISPATCH containing the complete Seed Package.

### Fail behavior

If any criterion is not met:
1. Set `structural_completeness: fail`.
2. List each unmet criterion in `deficiencies` with a specific description of what is missing.
3. Produce a PRELIMINARY DEFICIENCY REPORT (see section 4).
4. Do not produce a Cecil Evaluation Dispatch.

## 4. Preliminary deficiency reporting

When screening fails, ChatGPT produces a Preliminary Deficiency Report:

```
PRELIMINARY DEFICIENCY REPORT v{N}
Evaluating: SEED PACKAGE v{M}

SCREENING RESULT: FAIL

DEFICIENCIES:
- Criterion 2 (scope boundary): The seed discusses three possible project
  directions without settling on one. A scope statement cannot be written
  without the operator choosing a direction.
- Criterion 4 (task concreteness): No concrete tasks can be derived because
  the scope is not yet bounded.

REPAIR GUIDANCE:
- Choose one of the three project directions and state it clearly.
- Describe at least one concrete task that could be worked on first.

NEXT STEP:
Provide the missing information as a follow-up message in this chat.
I will update the Seed Package and re-screen.
```

### Deficiency report requirements

- Each deficiency must cite the specific criterion number and name.
- Each deficiency must describe concretely what is missing, not just restate the criterion.
- Repair guidance must tell the operator specifically what to provide, not just "fix the deficiency."
- The next step must be explicit.

## 5. Rerun model after repair

When the operator provides additional information or clarification after a deficiency report:

1. ChatGPT updates the Seed Package as a new version (e.g., v1 becomes v2). This is an incremental update, not a full restart.
2. The new version's header states `Prior version: v1` and `Addressing: PRELIMINARY DEFICIENCY REPORT v1`.
3. ChatGPT re-screens the updated package against all 6 criteria (not just the previously failed criteria — the full screen runs again).
4. If the updated package passes, ChatGPT produces a Cecil Evaluation Dispatch.
5. If the updated package still fails, ChatGPT produces a new deficiency report (v2) and the repair loop continues.

There is no limit on re-screening attempts. The repair trail remains legible because each Seed Package version references its prior version and the deficiency report it addresses.

## 6. Flags for Cecil

The `flags_for_cecil` field exists regardless of pass or fail. It allows ChatGPT to surface observations for Cecil's attention without treating them as deficiencies.

Appropriate flags:
- Scope may be broader or narrower than the stated scope_statement suggests.
- Constraints appear tentative or may change.
- Multiple architectural approaches remain open in the seed.
- The seed contains significant ambiguity that passed screening but may affect promotability.
- The operator provided notes suggesting timeline pressure or external dependencies.
- Source excerpts contain material that might indicate scope instability.

Flags are informational. They do not affect the pass/fail result. Cecil uses them as additional context during promotability evaluation.
