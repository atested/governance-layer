# Governed Action Baseline Specification v1.1

**Status: Provisional working specification.**
This document is the working baseline reference for the governed-action layer only. It is not final project canon for the full governance system. Deferred items listed in §3 remain open and undecided. Landing this specification does not imply that any deferred item has been resolved.

## 1. Purpose and scope

This document is the consolidated baseline specification for the governed-action architecture. It defines the minimum committed model for how the governance system handles actions, verifies coverage, manages opaque invocations, and records approval of unverified executable artifacts.

This specification consolidates previously accepted baseline positions into one reference. It does not extend the architecture beyond what has been accepted. It does not specify the full governance system — only the governed-action surface.

The intended audience is anyone who needs to understand what the governed-action baseline commits to, what it explicitly defers, and where its boundaries lie.

## 2. In-scope baseline commitments

The following are committed baseline positions. Each is specified in the relevant section of this document.

1. Governability is bounded by governed exposure, not by attempting to classify all possible AI actions.
2. Family/surface is the host-integration and coverage-reporting abstraction.
3. Capability classes are the fine-grained dispatch unit for policy evaluation.
4. Compound action is the primary conceptual model. Steps belong to compound actions when they have dependency relationships. Governance is per-step at baseline.
5. The baseline governance flow defines how actions are received, classified, evaluated, and recorded.
6. Verification is behavioral, stateful, and exception-surfaced.
7. Probes are precise, bounded, and evidence-bearing.
8. Opaque invocations follow a distinct slow path with transparent restatement as the preferred first response.
9. Unverified opaque executables are identified by content hash and require operator approval.
10. Approval is scoped, recorded as a governance event, and persists until revocation or scope mismatch.
11. Opacity metrics are descriptive and operator-facing, not direct policy triggers.
12. Decision and status events are first-class chain material.

## 3. Out-of-scope and deferred items

The following are explicitly deferred. They are not part of this baseline and must not be pulled into scope by implication or implementation pressure.

| Item | Status | Reason for deferral |
|---|---|---|
| Effects as a formal architectural axis | Deferred | Design exploration incomplete; not needed for baseline action handling |
| Zones as a formal architectural axis | Deferred | Design exploration incomplete; not needed for baseline action handling |
| Case as an architectural primitive or operator object | Deferred | Not needed for baseline; requires operator-surface design work |
| Operator UI / operator surface design | Deferred | Product design, not baseline architecture |
| Compound-level policy | Deferred | Per-step governance is sufficient at baseline; compound-level policy requires further design |
| Compound envelopes or plan semantics | Deferred | The minimal representation (compound identifier + typed dependency link) is sufficient at baseline |
| Compound completion/closure semantics | Deferred | Per-step governance does not require explicit compound lifecycle management |
| Workflow orchestration | Deferred | The governance system records and governs steps; it does not orchestrate them |
| Broader indirect-action mechanisms beyond the opacity boundary | Deferred | The transparent/opaque boundary handles the baseline need |
| Richer approval lifecycle beyond the accepted baseline | Deferred | Approval levels, periodic reapproval, quorum approval, batch approval — none needed at baseline |
| Speculative store lifecycle management | Deferred | Store is a derived index; lifecycle management deferred unless strictly required |
| Provenance chain for approved artifacts | Deferred | Approval records who approved, not origin or build chain |

Any work that requires resolving a deferred item must surface the dependency explicitly rather than pulling the deferred item into scope silently.

## 4. Governability boundary

### 4.1 Governed exposure

Governability is bounded by governed exposure through the governance layer. The governance system governs actions that pass through its action-handling surface. It does not attempt to classify, intercept, or reason about actions that do not pass through that surface.

This is a pragmatic boundary, not a safety claim. The system governs what it can see. It does not claim coverage of what it cannot see.

### 4.2 Family/surface

A governed family (or governed surface) is the abstraction through which the governance system integrates with a host environment. Each family represents a distinct integration surface — a set of capabilities exposed by one host system or subsystem that the governance layer can observe and govern.

Family/surface is the organizing unit for:

- Host integration. Each family corresponds to a specific integration with a host environment.
- Setup and configuration. Each family has its own integration configuration.
- Coverage reporting. Governance coverage is reported per family — which capabilities within the family are governed, which are not.
- Verification status. Verification state (§7) is tracked per governed surface.

Family/surface is not a policy grouping, a trust level, or a security boundary. It is an integration and coverage abstraction.

### 4.3 Capability classes

Capability classes are the fine-grained dispatch unit for policy evaluation within a governed family.

A capability class represents a specific type of action that can be governed. Policy rules bind to capability classes. When an action arrives at the governance surface, it is classified into a capability class, and the applicable policy rules for that class are evaluated.

Capability classes are defined per family. The same abstract operation (e.g., "write a file") may appear as different capability classes in different families if the host integration surfaces them differently.

## 5. Compound actions

### 5.1 Compound action as primary model

Compound action is the primary conceptual model for governed work. Most real governed activity consists of steps that depend on prior steps, not isolated independent actions.

This does not mean every action must carry heavy compound metadata. It means the action model naturally supports dependent multi-step structure as the common case, with isolated standalone actions as the degenerate case (a step with no dependencies and no dependents).

### 5.2 Dependency as the defining criterion

A step belongs to a compound action when its execution or meaning depends on one or more preceding steps.

Dependency distinguishes actual compound structure from mere temporal adjacency. Steps that happen to occur sequentially but have no dependency relationship are not compound — they are independent steps that happen to be temporally proximate.

Not every sequence is a compound action. A sequence becomes a compound action when later steps depend on earlier steps.

### 5.3 Baseline dependency types

At baseline, three practical dependency types are recognized:

- **Data dependency.** Step B uses output produced by step A. The output of one step flows forward as input to a subsequent step.
- **State dependency.** Step B assumes state created or changed by step A. Step B does not necessarily reference step A's output directly, but its correctness depends on side effects step A produced.
- **Control dependency.** Step B occurs only if step A succeeded, failed, or returned a specific result. Step A's outcome gates whether step B executes.

These are descriptive categories for the dependency link. They are not a full formal dependency theory. In practice, a single dependency relationship may involve more than one type (e.g., a step that reads a file written by a prior step has both data and state aspects). At baseline, recording the most salient dependency type is sufficient. The categories do not need to be mutually exclusive.

### 5.4 Minimal representation

The baseline representation for compound structure is:

- **Standalone actions** do not require explicit compound metadata. A step with no dependencies and no dependents is a standalone step. No compound_action_id is needed.
- **When dependency exists**, the dependent structure is represented with three fields on the step record:

| Field | Content |
|---|---|
| compound_action_id | Shared identifier grouping all steps that belong to the same compound action |
| depends_on_step_id | Identifier of the predecessor step this step depends on |
| dependency_type | One of: `data`, `state`, `control` |

A step may depend on more than one predecessor. Each dependency is a separate link (separate depends_on_step_id + dependency_type pair).

**Compound identity assignment.** A compound_action_id is assigned when the first dependency relationship is detected. If a step that initially appeared standalone later acquires a dependent, it gains a compound_action_id at that point, and the dependent step shares it. This is a retrospective assignment — compound membership is determined by dependency structure, not by pre-declaration.

This representation provides:

- Grouping of related steps in the chain for replay and review.
- Dependency ordering within a compound for reconstruction and analysis.
- Typed dependency links for future compound-level reasoning.
- No requirement for pre-declared compound plans or envelopes.

### 5.5 Dependency detectability

Dependency detection at baseline covers declared and detectable dependencies — cases where a step explicitly references a prior step's output, names a prior step's result as a precondition, or is visibly gated on a prior step's outcome.

Implicit dependencies may not always be captured. In particular, implicit state dependencies — where step B assumes filesystem or environment state created by step A but does not reference step A directly — may not be detected at the governance surface.

This is a known baseline limitation. The baseline captures the dependency structure that is visible at the governance surface. It does not claim to capture all theoretical dependencies between steps.

### 5.6 Per-step governance

At baseline, governance is per-step. Each step in a compound action is individually classified, evaluated against policy, and recorded. The governance system does not evaluate compound actions as wholes at baseline.

The compound structure recorded via §5.4 is a structural annotation in the chain, not an operational unit for governance handling. Per-step governance does not consult compound membership, dependency type, or compound_action_id when making per-step policy decisions.

The compound structure exists so that:

- The chain faithfully represents the dependency relationships between steps.
- Replay and review can reconstruct compound structure.
- Future compound-level policy, when no longer deferred, can operate over the recorded structure without requiring representation changes.

## 6. Baseline governance flow

The baseline action-handling flow proceeds as follows:

```
Action arrives at governance surface
    │
    ▼
Classification
    Determine: governed family, capability class
    │
    ▼
Dependency check
    Does this step depend on one or more preceding steps?
    │
    ├── YES → Record compound_action_id + dependency links (§5.4)
    │
    └── NO  → Standalone step, no compound metadata required
    │
    ▼
Transparency check
    Are the action's semantics visible at the invocation boundary?
    │
    ├── YES → Transparent path (§6.1)
    │
    └── NO  → Opaque path (§8)
```

### 6.1 Transparent path

```
Transparent action
    │
    ▼
Policy evaluation
    Evaluate applicable policy rules for this capability class
    │
    ▼
Decision
    Allow / Deny / Conditional
    │
    ▼
Record
    Record the action, classification, decision, and any compound
    metadata as a chain event
    │
    ▼
Execute or reject
```

The transparent path is the fast path. The governance system can see the action, classify it, evaluate policy, and record the decision. This is the expected path for the majority of governed actions.

### 6.2 Decision recording

Every governance decision — allow, deny, or conditional — is recorded in the decision chain. The chain event includes the action classification, the policy rules evaluated, the decision reached, sufficient context to replay the decision, and any compound metadata (compound_action_id, dependency links) if the step belongs to a compound action.

### 6.3 Per-step invariant

At baseline, every step that passes through the governance surface is individually handled by this flow. There is no mechanism for blanket pre-approval of action sequences, skip-ahead past governance for intermediate steps, or deferred evaluation of steps within a compound action. Compound membership does not alter the per-step handling rule.

## 7. Verification model

### 7.1 Purpose

Verification confirms that governed surfaces behave as the governance system expects. It detects drift between the governance model and actual host behavior.

### 7.2 Verification character

Verification is:

- **Behavioral, not purely static.** Verification tests actual behavior, not only configuration or declared state. A surface that is configured correctly but behaves incorrectly must be detectable.
- **Initial certification plus ongoing drift probes.** A governed surface undergoes initial verification when integrated. After certification, ongoing lightweight probes detect behavioral drift without repeating full verification.
- **Managed as an internal control loop.** The governance system manages verification scheduling, probe execution, and result evaluation internally. Verification is not an operator-driven manual workflow.
- **Surfaced to operators by exception.** Operators are notified when verification detects a problem. They are not required to monitor verification continuously or interpret routine probe results. Normal verification is silent to the operator.

### 7.3 Verification state

Verification state is tracked per governed surface. A surface is in one of:

- **Unverified.** Not yet certified. Actions from this surface follow the unverified path.
- **Verified.** Certified and no drift detected. Actions follow the normal governance flow.
- **Drift-detected.** A probe has detected behavioral divergence. The governance system must handle this surface's actions with appropriate caution until the drift is resolved or the surface is recertified.

Transitions between these states are governance-significant events (§11).

## 8. Opaque invocation model

### 8.1 Transparent and opaque defined

- **Transparent action.** A governable action whose semantics are visible at the invocation boundary. The governance system can classify it, evaluate policy against it, and record it meaningfully.
- **Opaque action.** A governable action whose semantics are not visible at the invocation boundary. The governance system can see that something is being invoked but cannot determine what it does by inspecting the invocation.

This distinction is about semantic visibility at the invocation boundary, not about the artifact's inherent complexity or the governance system's analytical sophistication.

### 8.2 Transparent fast path

Transparent actions follow the baseline governance flow (§6.1) without additional friction. They are the expected common case.

### 8.3 Opaque slow path

Opaque actions require additional handling because the governance system cannot classify them by content inspection alone.

```
Opaque action detected
    │
    ▼
Identity check
    Compute content-derived identity of the invoked artifact
    │
    ▼
Approval lookup
    Does a valid approval exist for this identity in the current scope? (§9)
    │
    ├── YES → Approved opaque path
    │         Record invocation with approved-artifact reference
    │         and any compound metadata
    │         Execute
    │
    └── NO  → Unapproved opaque path
              │
              ▼
          Transparent restatement attempt (§8.4)
              │
              ├── SUCCESS → Execute restated transparent action via §6.1
              │
              └── NOT POSSIBLE → Opaque friction path
                                 Operator decision required
                                 Record outcome
```

### 8.4 Transparent restatement

Transparent restatement is the preferred first response to an unapproved opaque invocation.

Restatement means: can the intended operation be expressed as a transparent action (or sequence of transparent actions) that the governance system can classify and evaluate normally?

If yes, the restated transparent action follows the normal governance flow. The original opaque invocation is not executed. The restatement is an alternate execution path, not a verification or certification of the original opaque artifact.

If restatement is not possible (the operation cannot be expressed transparently), the invocation remains on the opaque friction path and requires operator decision.

### 8.5 Unverified opaque executable rule

Any opaque executable artifact whose content-derived identity does not match a previously approved identity within the current scope is treated as unverified, regardless of origin. There is no exception for artifacts that appear trustworthy, are located in trusted paths, or were previously approved under a different scope.

## 9. Approved artifact identity and approval contract

### 9.1 Identity rule

Artifact identity is content-derived. The identity of an opaque artifact is its SHA-256 content hash (lowercase hexadecimal digest of the artifact's byte content).

Two artifacts with identical content have the same identity regardless of path, filename, or location. An artifact whose content changes has a different identity, even if its path and name are unchanged.

No other identity mechanism (path, filename, timestamp, version label) is a substitute for content-derived identity at baseline.

### 9.2 Approval actor and trust source

The approval actor is the operator. The operator is the sole trust source for opaque artifact approval at baseline. No system component may approve an opaque artifact on the operator's behalf.

Trust flows from the operator's willingness to accept responsibility for repeated opaque invocation of a specific artifact identity within a specific scope. The governance system records and enforces this decision. It does not originate it.

### 9.3 Approval meaning

Approval means: this exact content-derived identity is accepted by the operator for repeated opaque invocation within the approval scope defined in §9.4.

Approval does not mean: globally safe, semantically verified by the system, safe in all contexts, valid for modified versions, or applicable outside the granted scope.

The governance system makes no claim about the artifact's internal behavior. It claims only that the operator has approved this identity for repeated opaque use within a defined scope.

### 9.4 Approval scope

An approval is meaningful only within a defined scope. At baseline, approval scope is the conjunction of five fields:

| Field | What it binds |
|---|---|
| artifact_identity | The content-derived hash of the artifact |
| approving_operator | The operator who granted approval |
| governed_family | The governed family or surface the artifact operates within |
| deployment_context | The deployment or host environment |
| policy_version | The policy or baseline version in effect at approval time |

An approval applies only when all five fields match the current context. Reuse of an approved artifact outside its recorded scope is not implied by the approval and must be treated as unapproved.

The governance system determines the current value of each scope field at both approval time and invocation time. The operator supplies the artifact identity and the approval decision. The remaining four fields are resolved from the current governance context — the operator does not manually specify them.

Scope is conjunctive. All five fields must match. There is no mechanism for partial-scope matching, wildcard scoping, or scope relaxation at baseline.

### 9.5 Approval persistence and invalidation

An approval persists until one of the following conditions is met:

1. **Operator revocation.** The operator explicitly revokes the approval.
2. **Identity mismatch.** The artifact presented for invocation no longer matches the approved content-derived identity.
3. **Scope mismatch.** Any scope field no longer matches the value recorded at approval time.

Conditions 2 and 3 are automatic. The governance system does not need operator action to invalidate an out-of-scope approval — the approval simply does not apply.

Scope mismatch does not destroy the approval record. If the scope fields return to matching values, the original approval applies again. The approval record is permanent; its applicability is conditional on scope match.

There is no baseline requirement for periodic reapproval, automatic expiry, or time-bounded approval.

### 9.6 Approval event record

Every approval and every revocation is recorded as a governance-significant event in the decision chain.

The approval event record contains at minimum:

| Field | Content |
|---|---|
| event_type | `opaque_artifact_approval` or `opaque_artifact_revocation` |
| artifact_identity | SHA-256 content hash, lowercase hex |
| approving_operator | Operator identity |
| governed_family | Governed family or surface identifier |
| deployment_context | Deployment or host identifier |
| policy_version | Policy or baseline version identifier |
| timestamp | Event time |

The event record is the source of truth for approval status and scope.

### 9.7 Approved artifact store

The approved artifact store, if it exists, is a derived index over approval events for invocation-time lookup. It is not an independent authority. It must be consistent with the approval event history.

This specification does not require a specific store implementation, storage format, or query interface.

## 10. Evidence-bearing probes

### 10.1 Probe character

Probes used for verification (§7) and drift detection are:

- **Precise.** Each probe tests a specific behavioral property, not a general health check.
- **Bounded.** Each probe has defined execution limits. A probe that exceeds its bounds is a failed probe, not an ongoing investigation.
- **Evidence-bearing.** Each probe produces a concrete result — observed output, measured behavior, captured response — that can be recorded and reviewed. Probes do not produce bare pass/fail verdicts without supporting evidence.
- **Nonce-based where useful.** Where replay or caching could produce false positives, probes use nonces or unique markers to ensure the observed response is fresh.
- **Cross-checked against observable outcomes.** Where possible, probe results are compared against independently observable outcomes rather than relying solely on the probed surface's self-reporting.
- **Supported by instrumented targets where needed.** Where a governed surface cannot be probed purely from outside, the product may provide dedicated instrumented targets — lightweight endpoints or hooks designed specifically for governance verification. These are product-managed, not governance-imposed.

### 10.2 Probe results as chain material

Probe results that affect verification state (§7.3) are recorded in the decision chain as governance-significant events.

## 11. Decision and status events

### 11.1 Governance-significant events beyond tool actions

Not all governance-significant transitions are tool actions. The following are first-class chain material:

- **Verification state transitions.** A surface moving from unverified to verified, verified to drift-detected, or drift-detected back to verified.
- **Approval and revocation events.** Operator approval or revocation of an opaque artifact identity (§9.6).
- **Opaque invocation decisions.** The outcome of an opaque-path encounter — whether it was resolved by approval lookup, transparent restatement, or operator intervention.
- **Drift detection events.** A probe detecting behavioral divergence on a governed surface.
- **Policy evaluation decisions.** Allow, deny, or conditional decisions on governed actions.

These events are recorded with the same tamper-evidence and replay properties as action-handling events. They are not second-class log entries.

### 11.2 Event chain integrity

All governance-significant events participate in the same decision chain. The chain must support:

- Tamper-evidence. Modifications to recorded events must be detectable.
- Replay. The sequence of events must be reproducible from the chain record.
- Ordering. Events must have a deterministic order.

The internal structure and implementation of the chain is not specified in this document.

## 12. Opaque-operation metrics

### 12.1 Purpose

Opacity metrics describe the system's current opacity posture. They help operators understand how much governed activity is transparent versus opaque, and how the opacity profile is trending.

### 12.2 Metric character

Opacity metrics are:

- **Descriptive.** They describe what is happening. They do not prescribe what should happen.
- **System and operator facing.** They are available to the governance system for internal reporting and to operators for situational awareness.
- **Not direct policy triggers.** No policy rule at baseline fires solely because an opacity metric crosses a threshold. Metrics inform operator judgment. They do not automate policy escalation.

### 12.3 Baseline metrics

The specific metric definitions are not enumerated in this specification. The baseline commitment is that the governance system must be able to report, at minimum:

- The proportion of governed actions handled via the transparent path versus the opaque path.
- The frequency of opaque-path encounters over a reporting period.
- The resolution distribution of opaque-path encounters (approved lookup, transparent restatement, operator intervention).

## 13. Known baseline limitations

**Governability is bounded by exposure.** Actions that do not pass through the governance surface are not governed. The system makes no coverage claim beyond its integration surface.

**Per-step governance only.** The baseline does not reason about action sequences as wholes. Compound-action patterns that are individually benign but collectively problematic are not detected at baseline. The compound structure recorded in the chain (§5.4) supports future compound-level policy but does not enable it at baseline.

**Dependency detection is limited to the governance surface.** Declared and detectable dependencies are captured. Implicit dependencies — particularly implicit state dependencies where a step assumes environment state created by a prior step without referencing that step directly — may not be detected. The recorded compound structure reflects visible dependency, not all theoretical dependency.

**Retrospective compound identity.** Compound membership is determined by dependency structure, not by pre-declaration. A step that initially appears standalone may retroactively gain a compound_action_id when a dependent step arrives. This means compound structure in the chain may be updated after initial recording.

**No semantic verification of opaque artifacts.** Operator approval is a trust decision, not a verification result. The governance system does not analyze, simulate, or test approved opaque artifacts.

**Content-hash identity is brittle to benign changes.** Any byte-level change to an approved artifact produces a new identity requiring new approval. This is deliberate — brittleness to benign changes is preferable to silent approval transfer across actual changes.

**Scope transitions require reapproval.** A policy version change or deployment migration invalidates existing opaque artifact approvals for the new scope. This is deliberate — silent approval carryover across scope boundaries is the failure this prevents.

**Single approval actor.** Multi-operator approval, quorum approval, and delegated approval are not supported at baseline.

**Metrics are descriptive only.** The system can report its opacity posture but cannot act on it automatically. Operator attention is required to interpret metrics and decide on action.

**Verification is evidence-bearing but not exhaustive.** Probes test specific properties. A verified surface is a surface where tested properties behave as expected, not a surface where all possible behaviors have been confirmed.

## 14. Open questions intentionally left for later

1. **Governed family granularity.** What exactly constitutes a governed family for integration and scope purposes? Left to the family/surface integration specification.

2. **Deployment context granularity.** What constitutes a deployment or host context — machine identifier, cluster name, environment label? Left to the deployment model.

3. **Policy version identity.** How is the policy version identified for approval-scope purposes? Left to the policy versioning specification.

4. **Compound-level policy.** What policy rules, if any, should apply to compound actions as wholes? Deferred until per-step governance proves insufficient. The recorded compound structure (§5.4) supports this work when it is needed.

5. **Compound completion semantics.** When is a compound action finished? At baseline, this question does not need a precise answer — per-step governance does not depend on compound lifecycle. The dependency structure naturally supports inferring completion when needed.

6. **Probe scheduling and management.** How does the governance system decide when and how often to probe? Left to verification implementation.

7. **Approved artifact store implementation.** Structure, query interface, and synchronization mechanism for the derived approval index. Left to store-layer specification.

8. **Operator identity and authentication.** How is the operator authenticated for approval and other governance interactions? Left to the operator-identity specification.

9. **Transparent restatement boundaries.** When exactly is restatement possible versus not possible? This depends on the expressiveness of the transparent action vocabulary, which is family-specific.

10. **Metric definitions and reporting interface.** Exact metric names, computation methods, and reporting format. Left to the metrics specification.

11. **Scope relaxation or cross-scope approval.** Could an operator approve an artifact for multiple scopes simultaneously? Not at baseline. Compatible with the design if needed later.

12. **Implicit dependency detection.** Could the governance system improve detection of implicit state dependencies through instrumentation or host-integration cooperation? Compatible with the baseline but not specified here.
