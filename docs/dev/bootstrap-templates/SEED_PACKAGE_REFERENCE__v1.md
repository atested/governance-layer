# Seed Package Reference v1

**What this is:** The canonical reference for Seed Package structure and behavior. ChatGPT uses this reference when producing Seed Packages during project bootstrap. Cecil uses this reference when evaluating Seed Packages for promotability.

**Protocol:** NEW_PROJECT_BOOTSTRAP_PROTOCOL v1

---

## 1. Purpose

The Seed Package is a structured artifact that ChatGPT produces from raw seed content provided by the operator. It serves as:

- the canonical record of what was extracted from the seed
- the input to preliminary screening
- the input to Cecil's promotability evaluation
- a self-documenting record of project creation

The Seed Package is a chat-level artifact (pre-repo). It is not a file until the project reaches post-repo status.

## 2. Structure

```
SEED PACKAGE v{N}
Protocol: NEW_PROJECT_BOOTSTRAP_PROTOCOL v1
Timestamp: {ISO 8601 UTC}
Prior version: {v{N-1} or "none"}

--- STRUCTURED EXTRACTION ---

project_name:           {string — valid repo name candidate}
scope_statement:        {1-3 sentences}
deliverable_type:       {library | service | tool | spec_corpus | mixed}
primary_language:       {string or "tbd"}
key_constraints:
  - {constraint}
  - {constraint}
initial_task_candidates:
  - title: {string}
    scope: {one sentence}
    deliverable: {code | spec | test | config}
  - title: {string}
    scope: {one sentence}
    deliverable: {code | spec | test | config}
source_reference:       {human-readable source chat/doc reference}
governed_families:      {list or "none"}
external_dependencies:  {list or "none"}
operator_notes:         {string or "none"}
architectural_decisions:
  - decision: {string}
    rationale: {string}

preliminary_screening:
  structural_completeness: {pass | fail}
  deficiencies: []
  flags_for_cecil: []

--- SOURCE EXCERPTS ---

-- excerpt: {label} --
why_preserved: {rationale — e.g., "scope boundary is ambiguous here",
               "two competing approaches discussed without resolution",
               "constraint stated but not confirmed"}
source_content: |
  {verbatim excerpt from seed content}
--

-- excerpt: {label} --
why_preserved: {rationale}
source_content: |
  {verbatim excerpt}
--

--- IMPLEMENTATION SKETCHES ---

-- sketch: {label} --
{code or pseudocode content}
--
```

## 3. Required fields

Every Seed Package must include the following fields in the STRUCTURED EXTRACTION section:

| Field | Type | Description |
|---|---|---|
| `project_name` | string | Working name for the project. Must be usable as a repo name (lowercase, hyphens, no spaces). |
| `scope_statement` | string | What the project does and does not do. 1-3 sentences. |
| `deliverable_type` | enum | One of: `library`, `service`, `tool`, `spec_corpus`, `mixed`. |
| `primary_language` | string | Primary implementation language. Use `tbd` if not yet decided, `mixed` if multiple. |
| `key_constraints` | list of strings | Architectural or process constraints identified in the seed. At least one entry. |
| `initial_task_candidates` | list of objects | At least 1 concrete task. Each must have `title` (string), `scope` (one sentence), `deliverable` (one of: `code`, `spec`, `test`, `config`). |
| `source_reference` | string | Human-readable reference to the source chat or document (e.g., "ChatGPT chat: project-name / 2026-03-15 / architecture discussion"). |
| `extraction_timestamp` | string | ISO 8601 UTC timestamp of when the package was created. |
| `preliminary_screening` | object | Structural completeness check result. See section 6. |

## 4. Optional fields

| Field | Type | Description |
|---|---|---|
| `governed_families` | list of strings | Only if the project will use governed-action patterns. Most projects will not. |
| `external_dependencies` | list of strings | Known external systems, services, or APIs the project depends on. |
| `operator_notes` | string | Context from the operator that is not present in the seed content itself. Provided when the operator prefixes a message with `OPERATOR NOTES:`. |
| `architectural_decisions` | list of objects | Decisions already made in the seed. Each has `decision` (string) and `rationale` (string). |
| `implementation_sketches` | list of objects | Code or pseudocode fragments from the seed worth preserving. Each has `label` (string) and content. |

## 5. Source-excerpt preservation rules

The SOURCE EXCERPTS section preserves verbatim passages from the seed content that bear on ambiguity, instability, or contested decisions. This section exists so Cecil can evaluate the raw shape of uncertain material, not only ChatGPT's interpretation.

### Rules

1. **Ambiguity-bearing material must be preserved.** If the seed contains competing approaches, unresolved questions, or statements that could be interpreted multiple ways, the relevant passages go in SOURCE EXCERPTS with a `why_preserved` label explaining the ambiguity.

2. **Instability-bearing material must be preserved.** If the seed contains ideas that were proposed and then partially walked back, or constraints stated tentatively, those passages are preserved with a label noting the instability.

3. **Resolved material may be distilled.** If the seed clearly resolved a question (e.g., "we decided to use Rust"), ChatGPT may distill that into the structured extraction (`architectural_decisions`) without preserving the deliberation.

4. **When in doubt, preserve.** ChatGPT should err toward preserving excerpts rather than discarding them. Cecil can ignore irrelevant excerpts but cannot evaluate material that was discarded.

5. **Source excerpts are not the full seed.** ChatGPT selects passages that bear on evaluation-relevant ambiguity. Routine conversational content (greetings, tangents, resolved questions) is not preserved.

### Labeling

Each excerpt must include:
- A short descriptive label (e.g., "scope boundary discussion", "competing data model approaches")
- A `why_preserved` field explaining what makes this excerpt relevant to promotability evaluation
- The verbatim `source_content` from the seed

## 6. Preliminary screening fields

The `preliminary_screening` object in the Seed Package records ChatGPT's structural completeness check. It has three fields:

| Field | Type | Description |
|---|---|---|
| `structural_completeness` | `pass` or `fail` | Whether all 6 screening criteria are met. |
| `deficiencies` | list of strings | Empty if pass. If fail, lists each unmet criterion with a specific description. |
| `flags_for_cecil` | list of strings | Items ChatGPT wants to flag for Cecil's attention regardless of pass/fail. These are observations, not deficiency claims. |

Screening criteria are defined in `PRELIMINARY_SCREENING_REFERENCE__v1.md`.

Preliminary screening is a structural completeness check only. A screening pass means the package is ready for Cecil evaluation. It does not mean the seed is promotable.

## 7. Size bounds

| Element | Maximum | Overflow handling |
|---|---|---|
| `initial_task_candidates` | 10 entries | Additional candidates deferred to post-activation backlog. Note the deferral. |
| `source_excerpts` | 10 excerpts, each ~500 words | Consolidate related excerpts and note the consolidation. |
| `implementation_sketches` | 5 sketches, each ~200 lines | Select the most architecturally significant. Note any omissions. |

The total Seed Package should remain readable in a single pass. If it cannot, the seed is likely too large or too ambiguous for promotion and should be flagged in `flags_for_cecil`.

## 8. Large or multi-part seeds

If seed content exceeds what can be processed in a single pass:

1. The operator provides it in labeled chunks (e.g., "Seed Part 1 of 3").
2. ChatGPT asks whether more chunks are coming before finalizing the package.
3. ChatGPT processes each chunk incrementally, building up the Seed Package.
4. ChatGPT prioritizes extraction in this order: scope statement, constraints, task candidates, architectural decisions, implementation sketches.

## 9. Versioning model

### Version numbering

- First package: `SEED PACKAGE v1` with `Prior version: none`.
- After repair: `SEED PACKAGE v2` with `Prior version: v1`.
- Each subsequent update increments the version number.

### Prior-version retention

- Prior versions are retained in the chat history. They are chat messages and are not deleted or overwritten.
- The CECIL EVALUATION DISPATCH always carries the latest version and states the version number and how many prior versions exist.
- Cecil may request a prior version. The operator can scroll up and paste it, or ChatGPT can reproduce it from chat history.

### Deficiency report versioning

Deficiency reports follow the same numbering and reference the Seed Package version they evaluated:

```
PRELIMINARY DEFICIENCY REPORT v1
Evaluating: SEED PACKAGE v1
...

SEED PACKAGE v2
Prior version: v1
Addressing: PRELIMINARY DEFICIENCY REPORT v1
...
```

The repair trail is: Package v1 → Deficiency v1 → Package v2 → (screen pass or further deficiency) → ... → Cecil dispatch carrying the latest version. Each artifact references its predecessor.
