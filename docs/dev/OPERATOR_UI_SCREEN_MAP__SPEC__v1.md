# Operator UI Screen Map / Route-State Spec v1

**Status:** Canonical screen-map and route-state specification for the governed-action operator surface.
**Derived from:** OPERATOR_UI_IA__SPEC__v2.1
**Scope:** Governed-action operator surface only.

## Purpose

Define the per-screen structure, transitions, preserved state, and object-model placement for each screen in the governed-action operator UI. This spec is a mechanical derivation of the IA spec into implementable screen-level detail.

---

## Object-model reference

| Object | Role | Classification labels |
|---|---|---|
| Action | Top-level governed case | Deterministic or Judgment |
| Attempt | Grouped pass through governance within an Action | — |
| Step | Atomic transition or decision point within an Attempt | Determined or Judged |
| Evidence | Supporting material attached to a Step | — |
| Disposition | Management-level summarized state of an Action | System-defined values |

**Classification rule:** An Action is Judgment if any Step across any Attempt is Judged. Otherwise it is Deterministic. Classification is computed at query time and may change as the Action lifecycle progresses.

---

## Screen 1: Governed Actions Summary

### Purpose
Entryway into discovery and interaction. Shows system-wide governed-action behavior for a selected timeframe and routes the operator into Deterministic or Judgment analysis.

### Primary regions

| Region | Content | Role |
|---|---|---|
| A. Timeframe and scope bar | Timeframe selector, optional family/type scope filter | Controls |
| B. Resolution summary band | Deterministic block (count, percentage, label), Judgment block (count, percentage, label) | Primary routing |
| C. Secondary operational summaries | Total actions, traffic over time, family/type distribution, approval involvement, judgment involvement | Secondary analysis |

### Time controls
Summary timeframe controls: All, Today, Week, Month, Quarter, Year, Custom.
Selecting a timeframe recomputes all regions.

### Incoming transitions

| From | Trigger |
|---|---|
| Application entry | Direct load / URL |
| Any screen | Back navigation or breadcrumb to root |

### Outgoing transitions

| To | Trigger | State carried |
|---|---|---|
| Screen 2: Deterministic Page | Click Deterministic block | timeframe, scope filters |
| Screen 3: Judgment Page | Click Judgment block | timeframe, scope filters |
| Screen 7: Approval List | Navigation link where relevant | timeframe |

### Preserved state
- Selected timeframe
- Selected scope filters

### Operator actions available
- Select timeframe
- Select scope filters
- Route into Deterministic or Judgment page
- Navigate to Approval List

### Object-model presence

| Object | Appears as |
|---|---|
| Action | Aggregate counts only (Deterministic count, Judgment count, total) |
| Attempt | Not shown |
| Step | Not shown |
| Determined/Judged | Implicit through Deterministic/Judgment action counts |
| Approval List entry point | Navigation link where relevant |

### Empty state
If no Actions exist for the selected timeframe/scope, show an explicit empty state.

---

## Screen 2: Deterministic Page

### Purpose
Management summary of Deterministic Actions for the selected timeframe. Provides drill-down into Deterministic subsets.

### Primary regions

| Region | Content | Role |
|---|---|---|
| 1. Summary region | Total Deterministic Actions, completed count, failed count, multi-attempt count | Primary metrics |
| 2. Distributions region | Family/type distribution, traffic over time | Pattern visibility |
| 3. Drill-down categories region | Clickable category entries (completed, failed, multi-attempt, etc.) | Routing to Filtered Action List |

### Time controls
Summary timeframe controls remain available. Changing timeframe recomputes all regions.

### Incoming transitions

| From | Trigger |
|---|---|
| Screen 1: Summary | Click Deterministic block |
| Screen 4: Filtered Action List | Back navigation |

### Outgoing transitions

| To | Trigger | State carried |
|---|---|---|
| Screen 4: Filtered Action List | Click a drill-down category | timeframe, scope filters, parent page = Deterministic, selected category |

### Preserved state
- Timeframe (from Summary)
- Top-level scope filters (from Summary)
- Page context = Deterministic

### Operator actions available
- Select timeframe
- Select scope filters
- Route into a Deterministic subset via Filtered Action List

### Object-model presence

| Object | Appears as |
|---|---|
| Action | Aggregate counts by category (completed, failed, multi-attempt) |
| Attempt | Reflected in multi-attempt count |
| Step | Not shown |
| Determined/Judged | All Actions here are Deterministic; no per-step labels shown |
| Approval List entry point | Not present on this page |

---

## Screen 3: Judgment Page

### Purpose
Management summary of Judgment Actions for the selected timeframe. Exposes judgment causes, methods, and outcomes. Provides drill-down into Judgment subsets and direct path to Approval List.

### Primary regions

| Region | Content | Role |
|---|---|---|
| 1. Summary region | Total Judgment Actions, judgment-cause breakdown, judgment-method breakdown, judgment-outcome summary | Primary metrics |
| 2. Distributions region | Family/type distribution, approval/revocation implications, judgment-method distribution | Pattern visibility |
| 3. Drill-down categories region | Clickable judgment subset entries | Routing to Filtered Action List |

Judgment-specific content (causes, methods, outcomes) is organized into the same three-region structure, not presented as an unstructured list.

### Time controls
Summary timeframe controls remain available. Changing timeframe recomputes all regions.

### Incoming transitions

| From | Trigger |
|---|---|
| Screen 1: Summary | Click Judgment block |
| Screen 4: Filtered Action List | Back navigation |
| Screen 7: Approval List | Back navigation |

### Outgoing transitions

| To | Trigger | State carried |
|---|---|---|
| Screen 4: Filtered Action List | Click a drill-down category | timeframe, scope filters, parent page = Judgment, selected category |
| Screen 7: Approval List | Direct navigation link | timeframe |

### Preserved state
- Timeframe (from Summary)
- Top-level scope filters (from Summary)
- Page context = Judgment

### Operator actions available
- Select timeframe
- Select scope filters
- Route into a Judgment subset via Filtered Action List
- Navigate to Approval List

### Object-model presence

| Object | Appears as |
|---|---|
| Action | Aggregate counts by judgment category |
| Attempt | Not shown directly |
| Step | Not shown directly; judgment causes/methods are aggregated from Step-level data |
| Determined/Judged | Reflected in judgment-cause and judgment-method summaries |
| Approval List entry point | Direct navigation link present |

---

## Screen 4: Filtered Action List

### Purpose
Show the set of Actions belonging to a chosen subset and timeframe. Reachable from either Deterministic Page or Judgment Page.

### Primary regions

| Region | Content | Role |
|---|---|---|
| Context bar | Parent page indicator (Deterministic or Judgment), selected category, timeframe | Orientation |
| Filter/sort controls | Column sorts, additional filter refinement | List refinement |
| Action list | Paginated rows, one per Action | Primary content |
| Result count / pagination | Total matching count, page controls | List navigation |

### Recommended row fields per Action

- Action identifier or operator-facing label
- Top-level classification: Deterministic or Judgment
- Family/type
- Disposition
- Governance response summary
- Attempt count
- Time-relevant timestamp
- Approval marker (where relevant)
- Revocation marker (where relevant)
- Judgment marker (where relevant)

### Time controls
Summary timeframe controls remain available. Changing timeframe recomputes the list within the current category.

### Incoming transitions

| From | Trigger |
|---|---|
| Screen 2: Deterministic Page | Click a drill-down category |
| Screen 3: Judgment Page | Click a drill-down category |
| Screen 5: Action Detail | Back navigation |

### Outgoing transitions

| To | Trigger | State carried |
|---|---|---|
| Screen 5: Action Detail | Click an Action row | timeframe, scope filters, parent page, category, list filters/sorts, selected Action |

### Preserved state
- Parent page context (Deterministic or Judgment)
- Selected category/subset
- Selected timeframe
- Top-level scope filters
- List filters and sort state

### Operator actions available
- Select timeframe
- Filter and sort the list
- Open an Action for detail inspection

### Object-model presence

| Object | Appears as |
|---|---|
| Action | One row per Action with summary fields |
| Attempt | Attempt count column |
| Step | Not shown |
| Determined/Judged | Classification column (Deterministic/Judgment) per Action; judgment marker per row |
| Approval List entry point | Not present on this screen |

### Empty state
If no Actions match the selected subset and timeframe, show an explicit empty state.

### List behavior
- Total matching result count visible
- Pagination or progressive loading
- Sort/filter state preserved when returning from deeper screens

---

## Screen 5: Action Detail

### Purpose
Management-level understanding of one Action. Shows classification, disposition, progression across Attempts and Steps, and judgment/approval context.

### Primary regions

| Region | Content | Role |
|---|---|---|
| Header | Action identifier, classification (Deterministic/Judgment), family/type, disposition, governance response summary, attempt count, key timestamps, approval/revocation/judgment markers | Identity and status |
| Summary region | Why this Action is in the selected subset, overall disposition, governance response summary, management context, approval/revocation summary, judgment summary | Management narrative |
| Progression region | Two-level structure: Attempts containing Steps | Lifecycle inspection |

### Progression region detail

The progression region is a **two-level structure**:

**Attempt level (grouped unit):**
- Attempt identifier or number
- Attempt-level summary (timestamp range, step count, overall attempt outcome)

**Step level (atomic unit within each Attempt):**
Each Step within an Attempt shows:

| Field | Always shown | Judged Steps only |
|---|---|---|
| Step ordering | Yes | Yes |
| Resolution-mode label: Determined or Judged | Yes | Yes |
| Governance response summary | Yes | Yes |
| Evidence-present marker | Yes | Yes |
| Key change marker | Yes | Yes |
| Approval/revocation marker | Where relevant | Where relevant |
| Judgment method | — | Yes |
| Judgment cause/trigger | — | If tracked |

### Time controls
No summary timeframe controls on this screen. Progression navigation (sequence controls) is used instead.

### Incoming transitions

| From | Trigger |
|---|---|
| Screen 4: Filtered Action List | Click an Action row |
| Screen 6: Step Detail | Back navigation / return to Action Detail |

### Outgoing transitions

| To | Trigger | State carried |
|---|---|---|
| Screen 6: Step Detail | Click a Step in the progression | All preserved state + selected Attempt + selected Step |
| Screen 7: Approval List | Navigation link where relevant | timeframe |
| Screen 4: Filtered Action List | Back navigation | Restores list state |

### Preserved state
- Parent page context
- Selected subset/category
- Timeframe
- List filters/sorts (for return to list)
- Selected Action

### Operator actions available
- Inspect progression
- Open a Step for detail
- Navigate to Approval List where relevant
- Return to Filtered Action List
- Action-level management controls where admissible (contextual, tied to the selected Action)

### Object-model presence

| Object | Appears as |
|---|---|
| Action | Full header and summary |
| Attempt | Grouped unit in progression region |
| Step | Rows within each Attempt group, with Determined/Judged labels |
| Evidence | Presence markers per Step (not inline content) |
| Determined/Judged | Per-Step resolution-mode label in progression |
| Approval List entry point | Navigation link where relevant |

### Excluded
Do not dump all deep evidence inline for every Step. Do not expose raw audit views.

---

## Screen 6: Step Detail

### Purpose
Full management-level detail for one selected Step. Tracing screen for understanding evidence, governance response, and judgment context at the atomic level.

### Primary regions

| Region | Content | Role |
|---|---|---|
| Step header | Step identifier, parent Attempt identifier, parent Action identifier, family/type, timestamp, resolution-mode label (Determined/Judged) | Identity and context |
| Governance response | Full governance response for this Step, Step result | Decision detail |
| Evidence region | Evidence presented, shown in structured operator-readable form | Supporting material |
| Judgment region (Judged Steps only) | Judgment method, judgment cause/trigger if tracked | Judgment detail |
| Approval/revocation region (where relevant) | Approval/revocation data for this Step | Authorization context |
| Sequence navigation | Previous Step, Next Step, return to Action Detail, return to Filtered Action List | Progression traversal |

### Evidence presentation
Evidence is shown in structured, operator-readable form by default. Relevant technical fields may be exposed where needed, but the default is not raw forensic presentation.

### Time controls
Sequence navigation controls only:
- Previous Step
- Next Step
- Jump back to Action Detail progression

No summary timeframe controls on this screen.

### Incoming transitions

| From | Trigger |
|---|---|
| Screen 5: Action Detail | Click a Step in the progression |
| Screen 6: Step Detail (adjacent) | Previous Step / Next Step navigation |

### Outgoing transitions

| To | Trigger | State carried |
|---|---|---|
| Screen 6: Step Detail (adjacent) | Previous Step / Next Step | All preserved state, updated selected Step |
| Screen 5: Action Detail | Return to Action Detail | Restores Action Detail state |
| Screen 4: Filtered Action List | Return to Filtered Action List | Restores list state |

### Preserved state
- Parent page context
- Selected subset/category
- Timeframe
- List filters/sorts
- Selected Action
- Selected Attempt
- Selected Step

### Operator actions available
- Navigate previous/next Step
- Return to Action Detail
- Return to Filtered Action List
- Step-level management controls where admissible (only if tied to step-level decisions)

### Object-model presence

| Object | Appears as |
|---|---|
| Action | Parent reference in header |
| Attempt | Parent reference in header |
| Step | Full detail (primary content of this screen) |
| Evidence | Structured content in evidence region |
| Determined/Judged | Resolution-mode label in header; judgment region for Judged Steps |
| Approval List entry point | Not present on this screen |

### Excluded
Do not force raw record reading as part of normal operator flow.

---

## Screen 7: Approval List

### Purpose
Lightweight operator-facing view of approved items and approval status. Supports core operator decision area without expanding into full audit management.

### Primary regions

| Region | Content | Role |
|---|---|---|
| Approval list | Rows of approved items with status | Primary content |
| Entry detail (on selection) | Expanded detail for one approval entry | Inspection |
| Action controls | Inspect, revoke, create from reviewed case (where admissible) | Management |

### Recommended row fields per approval entry

- Approved item / artifact identity
- Family/type
- Approval basis summary
- Approved by
- Approved at
- Active / revoked status
- Revocation history (where relevant)
- Related or originating Action/case (where the system tracks it)

### Time controls
No summary timeframe controls. The Approval List shows current approval state, not time-sliced history.

### Incoming transitions

| From | Trigger |
|---|---|
| Screen 1: Summary | Navigation link where relevant |
| Screen 3: Judgment Page | Direct navigation link |
| Screen 5: Action Detail | Navigation link where relevant |

### Outgoing transitions

| To | Trigger | State carried |
|---|---|---|
| Originating Action (Screen 5) | Click related/originating Action link | Navigates to Action Detail for that Action |
| Previous screen | Back navigation | Restores prior screen state |

### Preserved state
- Timeframe (inherited from referring screen, for back navigation)
- Referring screen context (for back navigation)

### Operator actions available
- Inspect an approval entry
- Revoke an approval entry (where admissible)
- Create an approval entry from a reviewed Action/case (where admissible)

### Object-model presence

| Object | Appears as |
|---|---|
| Action | Related/originating Action link per entry |
| Attempt | Not shown |
| Step | Not shown |
| Determined/Judged | Not shown (approval context is independent of resolution-mode labels) |
| Approval List entry point | This is the Approval List |

---

## Screen 8: Audit Surface Stub

### Purpose
Placeholder establishing the boundary between operator surface and future audit surface.

### Primary regions

| Region | Content | Role |
|---|---|---|
| Stub message | "Audit surface reserved. Out of scope for current operator UI phase. Raw record and forensic inspection live here later." | Boundary marker |

### Time controls
None.

### Incoming transitions

| From | Trigger |
|---|---|
| Global navigation | Audit link (if exposed in navigation) |

### Outgoing transitions

| To | Trigger | State carried |
|---|---|---|
| Previous screen | Back navigation | Restores prior state |

### Preserved state
None.

### Operator actions available
None.

### Object-model presence
None. This is a stub.

---

## Route-state summary

### Full transition map

```
Screen 1: Governed Actions Summary
  -> Screen 2: Deterministic Page         [click Deterministic block]
  -> Screen 3: Judgment Page              [click Judgment block]
  -> Screen 7: Approval List              [navigation link]
  -> Screen 8: Audit Surface Stub         [navigation link]

Screen 2: Deterministic Page
  -> Screen 4: Filtered Action List       [click drill-down category]
  <- Screen 1: Summary                    [back]

Screen 3: Judgment Page
  -> Screen 4: Filtered Action List       [click drill-down category]
  -> Screen 7: Approval List              [direct link]
  <- Screen 1: Summary                    [back]

Screen 4: Filtered Action List
  -> Screen 5: Action Detail              [click Action row]
  <- Screen 2: Deterministic Page         [back]
  <- Screen 3: Judgment Page              [back]

Screen 5: Action Detail
  -> Screen 6: Step Detail                [click Step]
  -> Screen 7: Approval List              [navigation link]
  <- Screen 4: Filtered Action List       [back]

Screen 6: Step Detail
  -> Screen 6: Step Detail (adjacent)     [prev/next Step]
  <- Screen 5: Action Detail              [return]
  <- Screen 4: Filtered Action List       [return]

Screen 7: Approval List
  -> Screen 5: Action Detail              [click originating Action]
  <- (referring screen)                   [back]

Screen 8: Audit Surface Stub
  <- (referring screen)                   [back]
```

### Cumulative preserved state by depth

| Depth | Screen | State accumulated |
|---|---|---|
| 0 | Summary | timeframe, scope filters |
| 1 | Deterministic/Judgment Page | + page context |
| 2 | Filtered Action List | + category/subset, list filters/sorts |
| 3 | Action Detail | + selected Action |
| 4 | Step Detail | + selected Attempt, selected Step |

### Time-control placement

| Screen | Time-control type |
|---|---|
| Screen 1: Summary | Summary timeframe controls |
| Screen 2: Deterministic Page | Summary timeframe controls |
| Screen 3: Judgment Page | Summary timeframe controls |
| Screen 4: Filtered Action List | Summary timeframe controls |
| Screen 5: Action Detail | Sequence navigation only |
| Screen 6: Step Detail | Sequence navigation only |
| Screen 7: Approval List | None (current-state view) |
| Screen 8: Audit Surface Stub | None |

### Determined/Judged label placement

| Screen | Where labels appear |
|---|---|
| Screen 1: Summary | Implicit (Deterministic/Judgment counts) |
| Screen 2: Deterministic Page | All Actions here are Deterministic (no per-step labels) |
| Screen 3: Judgment Page | Aggregate judgment-method and judgment-cause summaries |
| Screen 4: Filtered Action List | Classification column per Action row; judgment marker |
| Screen 5: Action Detail | Per-Step labels in progression region (Determined/Judged) |
| Screen 6: Step Detail | Resolution-mode label in header; judgment detail region for Judged Steps |
| Screen 7: Approval List | Not shown |
| Screen 8: Audit Surface Stub | Not shown |

### Approval List entry-point placement

| Screen | Entry point present |
|---|---|
| Screen 1: Summary | Navigation link where relevant |
| Screen 2: Deterministic Page | Not present |
| Screen 3: Judgment Page | Direct navigation link (required) |
| Screen 4: Filtered Action List | Not present |
| Screen 5: Action Detail | Navigation link where relevant |
| Screen 6: Step Detail | Not present |
| Screen 7: Approval List | (is the Approval List) |
| Screen 8: Audit Surface Stub | Not present |

### Back/forward behavior

All back/forward navigation restores:
- prior screen
- page context (Deterministic or Judgment)
- timeframe
- subset/category
- list filter/sort state
- selected Action
- selected Attempt (where applicable)
- selected Step (where applicable)

Navigation must behave like a web application with meaningful URL/state management, not like a stateless modal stack.
