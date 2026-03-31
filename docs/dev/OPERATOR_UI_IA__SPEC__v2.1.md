# Operator UI IA Spec v2.1

## Scope
Governed-action operator surface only.

## Purpose
Define the first operator-facing UI skeleton for governed actions, with explicit separation between Deterministic and Judgment action classes, lightweight approval management, and a management-only boundary distinct from future audit tooling.

This spec covers:
- information architecture
- screen structure
- navigation/state behavior
- time controls
- action / attempt / step model
- judgment visibility
- lightweight approval management
- operator versus audit boundary

This spec does not cover:
- backend redesign
- repo mechanics
- implementation planning
- visual styling system
- full audit UI design beyond stub boundary

---

## 1. Product boundary

### Operator surface
The operator surface is for management and inspection of governed actions only.

It shows:
- summary behavior of governed actions over time
- top-level Deterministic versus Judgment classification
- filtered category slices of governed actions
- action-level management detail
- attempt progression
- step-level resolution detail
- evidence presented for a step
- governance response
- disposition
- judgment cause/method where relevant
- approval and revocation context where relevant
- lightweight approval-list management

It does not foreground:
- raw chain/event records
- raw substrate logs
- low-level forensic trace
- general raw-data browsing
- forensic correlation tooling
- export/extraction tooling

### Operator-surface rule
The operator surface shows tracked fields and precomputed management summaries only.
It does not provide interactive forensic query, cross-record reconstruction, or audit-style investigative tools.

### Audit surface
Audit is a separate future surface.

Audit will eventually contain:
- raw records
- forensic trace
- deeper provenance/reconstruction views
- low-level record inspection
- exports/extractions

For this phase, audit is a stub only.

---

## 2. Primary object model

### Action
An **Action** is the top-level governed case tracked across its full lifecycle.
It is the primary operator-facing object.

An Action may contain:
- one or more attempts
- one or more steps within each attempt
- governance responses
- evidence presented
- disposition
- approval/revocation context where relevant
- judgment context where relevant

### Attempt
An **Attempt** is one distinct pass through governance for an Action.

Attempts group progression into meaningful tries or resolution episodes.

### Step
A **Step** is an atomic transition or decision point within an Attempt.

Each Step is labeled:
- **Determined**
- **Judged**

Judged steps must expose:
- judgment method
- judgment cause/trigger if tracked

### Top-level action classification
Each Action is explicitly classified as one of:
- **Deterministic**
- **Judgment**

Classification rule:
- **Deterministic**: all steps across all attempts are Determined
- **Judgment**: any step across any attempt is Judged

### Reclassification rule
Action classification is computed from the lifecycle as currently known at query time.

Therefore:
- an Action may appear Deterministic earlier in its lifecycle
- and later appear Judgment if a Judged step is added in a later attempt

### Human judgment
Judgment is not synonymous with human judgment.

Human judgment, where tracked, is a subset or specific instance within the broader Judgment class.

### Evidence
**Evidence** is the supporting material attached to a specific Step and governance response.

For operator UI purposes, evidence should be shown as structured management-facing content, not raw forensic dumps by default.

### Disposition
**Disposition** is the management-level summarized state of an Action, distinct from per-step governance response.

Disposition values must be defined consistently by the system and surfaced consistently across list/detail views.

---

## 3. Screen hierarchy

1. **Governed Actions Summary**
2. **Deterministic Page**
3. **Judgment Page**
4. **Filtered Action List**
5. **Action Detail**
6. **Step Detail**
7. **Approval List**
8. **Audit Surface Stub**

---

## 4. Screen definitions

## Screen 1: Governed Actions Summary

### Role
Entryway into discovery and interaction.

### Purpose
Answer:
- how the governed system behaved over the selected timeframe
- what proportion of Actions were Deterministic versus Judgment
- how much traffic the system handled
- where the operator should drill next

### Default timeframe
- **All recorded history**

### Time controls
Visible at top of page:
- All
- Today
- Week
- Month
- Quarter
- Year
- Custom

Selecting a timeframe recomputes the page for that timeframe.

### Main content regions

#### A. Timeframe and scope bar
Contains:
- timeframe selector
- optional family/type scope filter
- optional additional top-level scope selectors later

#### B. Resolution summary band
Primary region.

Large, explicitly labeled summary blocks for:
- **Deterministic**
- **Judgment**

Each block shows:
- count
- percentage
- explicit label
- click path into the corresponding page

#### C. Secondary operational summaries
Secondary region.

Candidate summaries:
- total identified actions
- traffic over time
- family/type distribution
- approval involvement summary
- judgment involvement summary where useful

### Empty states
If no actions exist for the selected timeframe/scope, show an explicit empty state rather than a blank page.

### Click behavior
- Clicking **Deterministic** opens Screen 2
- Clicking **Judgment** opens Screen 3

### Excluded from this screen
Do not foreground:
- raw action rows
- attempt/step detail
- full evidence detail
- raw record views
- audit tooling

---

## Screen 2: Deterministic Page

### Role
Management summary page for Deterministic Actions.

### Purpose
Show how deterministically resolved Actions behave over the selected timeframe and provide drill-down into their subsets.

### Time controls
Time controls remain available here.

### Structure
Use the same structural pattern as the Judgment Page:
1. summary region
2. distributions region
3. drill-down categories region

### Candidate content
- total Deterministic Actions
- completed
- failed
- multi-attempt
- family/type distribution
- traffic over time
- deterministic category drill-downs

### Click behavior
Clicking a category opens Screen 4 filtered to the chosen deterministic subset.

---

## Screen 3: Judgment Page

### Role
Management summary page for Judgment Actions.

### Purpose
Show how judgment-bound Actions behave over the selected timeframe and provide drill-down into their subsets.

### Time controls
Time controls remain available here.

### Structure
Use the same structural pattern as the Deterministic Page:
1. summary region
2. distributions region
3. drill-down categories region

Judgment-specific content must be organized into that structure, not presented as an unstructured field dump.

### Required content directions
This page should expose what the system actually tracks about judgment, including:
- total Judgment Actions
- what made Actions go to judgment
- what judgment methods were used
- judgment outcomes
- approval/revocation implications where relevant
- family/type distribution

### Direct path to Approval List
This page must provide a direct navigation path to the Approval List.

### Click behavior
Clicking a judgment summary category opens Screen 4 filtered to the selected judgment subset.

---

## Screen 4: Filtered Action List

### Role
Show the set of Actions belonging to a chosen subset and timeframe.

This screen may be reached from either Deterministic Page or Judgment Page.

### Time controls
Time controls remain available here.

### Required preserved context
This screen must preserve:
- selected parent page context
- selected category/subset
- selected timeframe
- inherited top-level scope/filter context

### List model
Each row represents one Action.

It is not a raw event list.

### Recommended row fields
- Action identifier or operator-facing label
- top-level classification: Deterministic or Judgment
- family/type
- disposition
- governance response summary
- attempt count
- time-relevant timestamp
- approval marker where relevant
- revocation marker where relevant
- judgment marker where relevant

### List behavior
This screen must show:
- total matching result count
- pagination or progressive loading
- preserved sort/filter state when returning from deeper screens

### Empty state
If the selected subset contains no matching Actions for the timeframe/filter, show an explicit empty state.

### Click behavior
Clicking an Action row opens Screen 5.

---

## Screen 5: Action Detail

### Role
Management-level understanding of one Action.

### Purpose
Allow the operator to understand:
- what this Action is
- whether it is Deterministic or Judgment
- what its disposition is
- how it progressed across attempts
- whether approval or revocation context matters
- whether judgment context matters
- which Step to inspect more deeply

### Required header fields
- Action identifier or operator-facing label
- top-level classification: Deterministic or Judgment
- family/type
- disposition
- governance response summary
- attempt count
- key timestamps
- approval marker where relevant
- revocation marker where relevant
- judgment marker where relevant

### Summary region
Contains:
- why the Action is in the selected subset
- overall disposition
- governance response summary
- key management context
- approval/revocation summary where relevant
- judgment summary where relevant

### Progression region
This is a **two-level structure**:

- **Attempt**
  - contains one or more **Steps**

Each Attempt should be visible as a grouped unit.
Each Step within an Attempt must show:
- step ordering
- resolution-mode label: Determined or Judged
- governance response summary
- evidence-present marker
- key change marker
- approval/revocation marker where relevant

For Judged steps, also show:
- judgment method
- judgment cause/trigger if tracked

### Click behavior
Clicking a Step opens Screen 6.

### Excluded from this screen
Do not dump all deep evidence inline for every Step.
Do not expose raw audit views here.

---

## Screen 6: Step Detail

### Role
Full management-level detail for one selected Step of one Action.

### Purpose
Allow the operator to understand:
- what evidence was presented
- how governance responded
- what result occurred at this Step
- how this Step differed from adjacent Steps
- what judgment method was used if this was a Judged Step

### Required content
- Step identifier
- parent Attempt identifier
- parent Action identifier
- family/type
- timestamp
- resolution-mode label: Determined or Judged
- governance response
- Step result
- evidence presented
- approval/revocation data where relevant
- judgment method where relevant
- judgment cause/trigger where relevant if tracked

### Evidence presentation
Evidence should be shown in structured, operator-readable form by default.
It may expose relevant technical fields where needed, but should not default to raw forensic presentation.

### Navigation within detail
Provide:
- previous Step
- next Step
- return to Action Detail
- return to Filtered Action List
- browser-like back/forward should restore prior state

### Excluded from this screen
Do not force raw record reading as part of normal operator flow.

---

## Screen 7: Approval List

### Role
Lightweight operator-facing view of approved items and approval status.

### Purpose
Support one of the core operator decision areas without expanding into full audit management.

### Candidate content
- approved item / artifact identity
- family/type
- approval basis summary
- approved by
- approved at
- active / revoked status
- revocation history where relevant
- related or originating action/case where the system tracks it

### Candidate actions
Where admissible, support:
- inspect approval entry
- revoke approval entry
- create approval entry from reviewed action/case

This is lightweight approval management, not full forensic approval analysis.

---

## Screen 8: Audit Surface Stub

### Role
Placeholder only.

### Purpose
Establish the boundary that:
- raw records
- forensic inspection
- deeper provenance trace
- exports/extractions

belong in a separate future audit surface.

### Stub content
Minimal placeholder:
- Audit surface reserved
- Out of scope for current operator UI phase
- Raw record and forensic inspection live here later

---

## 5. Navigation model

### Core navigation flow
Governed Actions Summary
-> Deterministic Page or Judgment Page
-> Filtered Action List
-> Action Detail
-> Step Detail

Approval List may be reached from:
- Governed Actions Summary where relevant
- Judgment Page
- Action Detail where relevant

### Required navigation behavior
The operator must be able to:
1. open Governed Actions Summary with a selected timeframe
2. click Deterministic or Judgment
3. see the corresponding page for that timeframe
4. click a category/subset
5. see the filtered list
6. click one Action
7. see the Action Detail
8. click one Step
9. move previous/next through Steps
10. return back through prior views without losing context

### State preservation rules

#### Summary -> Deterministic/Judgment Page
Preserve:
- timeframe
- top-level scope filters
- selected page context

#### Deterministic/Judgment Page -> Filtered Action List
Preserve:
- selected parent page context
- selected category/subset
- selected timeframe
- inherited top-level scope/filter context

#### Filtered Action List -> Action Detail
Preserve:
- parent page context
- selected subset
- timeframe
- list filters/sorts
- selected Action context

#### Action Detail -> Step Detail
Preserve:
- parent page context
- selected subset
- timeframe
- list filters/sorts
- selected Action
- selected Attempt
- selected Step

### Back/forward behavior
Back/forward should restore:
- prior screen
- page context
- timeframe
- subset/category
- list filter/sort state
- selected Action
- selected Attempt
- selected Step where applicable

This should behave like a web application with meaningful navigation state.

---

## 6. Time-control model

### A. Summary timeframe controls
Used on:
- Governed Actions Summary
- Deterministic Page
- Judgment Page
- Filtered Action List

Purpose:
- slice governed-action summaries and subsets by timeframe

Controls:
- All
- Today
- Week
- Month
- Quarter
- Year
- Custom

### B. Sequence navigation controls
Used on:
- Action Detail
- Step Detail

Purpose:
- navigate an Action's progression through its attempts and steps

Controls:
- previous Step
- next Step
- jump back to attempt grouping/detail

Important distinction:
- summary timeframe controls are not the same as progression navigation

---

## 7. Control placement model

This phase is primarily about inspection, but operator controls should still be planned.

### Governed Actions Summary
No deep action controls here.
This is summary and routing.

### Deterministic Page / Judgment Page
No deep action controls here beyond:
- filtering
- narrowing subsets
- opening actions
- opening Approval List where relevant

### Filtered Action List
No deep controls here beyond:
- filtering
- sorting
- opening actions

### Action Detail
This is the first place where action-relevant controls may appear, if admissible.

Controls here should be:
- contextual
- tied to the selected Action
- accompanied by sufficient summary context

### Step Detail
Step-specific controls may appear here only if they are truly tied to step-level management decisions.

### Approval List
Approval actions may appear here where admissible.

### General rule
Management controls belong where the operator has enough context to act responsibly.
They should not dominate summary or list surfaces.

---

## 8. Judgment-specific visibility rules

Judgment must be made explicit to the operator.

### Summary level
The Summary page must explicitly show the Deterministic versus Judgment split.

### Judgment page
The Judgment page must show what the system actually tracks about:
- why Actions went to judgment
- what methods were used
- what outcomes occurred

### Action-detail level
If an Action is Judgment-classified, Action Detail must surface judgment context clearly.

### Progression level
Each Step must show whether it was Determined or Judged.

### Step-detail level
A Judged Step must show the judgment method used and any tracked judgment cause/trigger.

Judgment must not be flattened into "human only" if the system distinguishes broader judgment forms.

---

## 9. Empty-state and edge handling

### Empty states
The operator surface must distinguish:
- no Actions in timeframe/scope
- no matching Actions in a selected subset

These should render as explicit empty states, not blank surfaces.

### In-progress assumption
If in-progress or pending Actions exist in the system, the UI must classify and display them consistently.
If they do not exist in this operator phase, that assumption should be stated explicitly in implementation.

---

## 10. Summary of deferred items

Deferred from this phase:
- verification-state indicators
- data-health indicators
- direct identifier lookup/search
- export/extraction from operator surface
- audit-surface design beyond stub
