# GovMCP v2: Governed Mediation Architecture

## Design Brief — Revised After External Review

**Date:** 2026-04-03
**Author:** Atested
**Status:** Design — pre-implementation
**Classification:** Architecture redesign
**Review status:** Three external reviews incorporated

---

## 1. The Problem with the Current Design

The current GovMCP architecture requires AI agents to use a specific catalog of 46 governed tools. If the agent calls `fs_read`, governance applies. If the agent uses its native `Read` command, it bypasses governance entirely.

This creates three failures:

**Compliance depends on agent judgment.** The agent must choose the governed tool over its native equivalent. This is an implicit reliance on the AI's willingness to comply — the exact dependency a governance product should eliminate.

**The tool catalog can never be complete.** Agents use dozens of native operations — git, grep, test runners, package managers, process management. Each unmapped operation is an ungoverned gap. Mapping native tools to governed equivalents produces inaccurate recommendations (e.g., recommending `fs_list` as the governed alternative to `grep` — they are fundamentally different operations).

**The operator bears the burden.** Every standard operation without a governed equivalent shows up as ungoverned activity. The operator is asked to manually approve routine operations like `git push` and `pytest`. The approval system should handle exceptions, not the baseline.

---

## 2. The Architectural Shift

**Old model:** The agent must choose governed tools from our catalog. Governance is opt-in by tool selection.

**New model:** GovMCP accepts any tool call from any agent, classifies it by observable evidence, evaluates policy, records the decision, and either allows the original operation to execute or denies it. Governance applies to everything that transits the boundary.

### Core Principle

**Governance is designed to be invisible to the agent, and comprehensive where the execution environment routes operations through the governance boundary.**

Governance coverage is a function of boundary control. Where the runtime routes all agent operations through GovMCP, governance is structural. Where the agent retains native capabilities outside the MCP path, governance depends on boundary completeness — which the system measures honestly rather than assuming.

### What This Means

- We do not author a capability catalog. We mediate and govern execution of capabilities supplied by the agent runtime or connected environment.
- We do not add capabilities to agents. We govern the capabilities they already have.
- We do not reimplement tools. We wrap real operations in policy evaluation and chain recording.
- We do not ask agents to change their behavior. We govern their existing behavior where it transits our boundary.

---

## 3. Product Shape: Request-Boundary Governance

This design implements **request-boundary governance** (Shape A): GovMCP governs operations at the call boundary. When a tool call arrives, we classify it, evaluate policy, record the decision, and allow or deny execution of the original operation.

This is distinct from **governed execution environments** (Shape B), which would additionally constrain what happens *during and after* an allowed execution — controlling filesystem access, network egress, process spawning, and credential access at the runtime level. Shape B requires control of the compute environment itself (containerization, syscall mediation, process isolation) and represents a future evolution.

### What Shape A governs

- The request: what tool was called, with what parameters, by which agent
- The classification: what action category and targets are observable from the evidence
- The policy decision: ALLOW or DENY based on active rules
- The record: signed into the governance chain with full provenance

### What Shape A does not govern

- Downstream effects of allowed executions. If `python task.py` is allowed, and that script internally reads secrets, writes configs, or makes network calls, those downstream effects are not individually governed at the request boundary.
- Native agent capabilities that bypass the MCP path entirely.

### Why Shape A is the right starting point

Shape A is deployable today without requiring control of the operator's compute environment. It works with any agent on any infrastructure. It provides genuine governance for every operation that transits the boundary, honest measurement of what doesn't, and a clear operator workflow for managing exceptions.

Shape A's honest limits are a product strength, not a weakness. A governance system that acknowledges its boundaries is more credible than one that overstates its coverage.

### The path to Shape B

Shape B requires controlled execution environments — containerized runtimes, filesystem isolation, network egress control, credential mediation, and process-level governance. This is infrastructure work that extends beyond the MCP protocol. Shape B becomes relevant for regulated industries (finance, healthcare, government) where proving not just authorization but realized effect is required. The architecture is designed so that Shape A's classification, policy, and chain recording layers carry forward into Shape B without redesign.

---

## 4. Architecture

### Layer 1: Accept

GovMCP receives any tool call from any connected agent. No rejection for unknown tools. No required catalog. The MCP protocol is the governance boundary — if a tool call flows through MCP, it flows through governance.

### Layer 2: Classify

Determine what the operation *does* in terms relevant to policy. Classification is based on **evidence inference** from the tool call's parameters.

Observable evidence:
- **What is it targeting?** File paths, URLs, endpoints, databases, processes
- **What is it doing to the target?** Reading, writing, executing, deleting, sending, modifying
- **What scope does it affect?** Local filesystem, network, system configuration, credentials

**We do not rely on agent-provided tool manifests for classification.** A manifest is a claim by the agent about what its tools do. An agent could declare a tool as "reads files" when it actually exfiltrates data over the network. Governing based on agent claims is not governance — it is trust. Evidence inference examines what's actually in the call. Manifests are not trustworthy inputs.

#### Classification Confidence Tiers

Classification is not uniformly deterministic. Different operations yield different levels of confidence about their real effects:

**Tier 1 — Directly observable.** The operation's effects are fully visible in its parameters. Examples: `read /tmp/data.txt`, `write /etc/hosts`, `request https://api.example.com`. Classification is deterministic. Policy can be applied with full confidence.

**Tier 2 — High-confidence inferred.** The operation's primary effects are reliably inferred from the command and parameters, though secondary effects may exist. Examples: `git push origin main` (execution + network), `curl https://endpoint` (network + possible file output), `rm -rf /tmp/cache` (destructive filesystem). Classification is reliable for primary effects. Policy applies to what is observable.

**Tier 3 — Opaque execution with bounded evidence.** The operation invokes a script, interpreter, or binary whose internal behavior is not visible from the call parameters. Examples: `bash deploy.sh`, `python sync.py`, `node build.js`, `projectctl run`. Classification can identify the execution surface (shell, interpreter, binary) and the entry point, but downstream effects — file access, network calls, credential use, process spawning — are not deterministically known from the call alone.

**Tier 4 — Uninspectable or adversarial.** The operation uses encoded payloads, compiled binaries with opaque arguments, encrypted command streams, or intentionally obfuscated parameters. Evidence inference yields minimal useful classification.

#### How policy responds to confidence tiers

- **Tier 1:** Automatic ALLOW/DENY by policy rule. High-volume, low-friction.
- **Tier 2:** ALLOW/DENY by policy rule with full chain recording of observable evidence. Secondary effects acknowledged as inferred.
- **Tier 3:** This is where the existing approvals system applies. Opaque execution is a candidate for operator approval. The operator examines the available evidence — entry point, arguments, execution context — and makes an informed decision. Approved opaque operations are recorded in the chain with the operator's explicit authorization. The system is honest: "I can see what was requested but not what it does internally. Operator has taken responsibility for this execution."
- **Tier 4:** Default DENY or operator approval required depending on policy posture. The system surfaces what it can observe and is explicit about what it cannot.

This tiered model replaces the binary "known vs. unknown" framing. It gives the operator and the policy engine a more accurate picture of what the system actually knows about each operation.

### Layer 3: Evaluate Policy

The classified operation is evaluated against active policy rules. Policy is expressed in terms of action categories and evidence — not tool names.

#### Policy dimensions

- **Action type:** read, write, delete, execute, network request, credential access, configuration change
- **Target class:** source tree, system path, secret store, remote endpoint, process table
- **Scope:** local, repository, system, remote, privileged
- **Confidence tier:** direct, inferred, opaque, uninspectable
- **Actor/context:** agent identity, user identity, operating mode, project, environment
- **Risk posture:** unrestricted, restricted, review-required
- **Consequence class:** record-only, require approval, deny, sandbox-only (Shape B)

Policy rules combine these dimensions. Examples:

- "File read operations (Tier 1) targeting the source tree are allowed and recorded"
- "Execution operations with network side effects (Tier 2) require the operator to have an active network-operations approval"
- "Opaque execution (Tier 3) of scripts not previously approved requires operator approval"
- "Uninspectable operations (Tier 4) are denied in restricted mode"
- "All operations targeting paths in `/etc/` or `~/.ssh/` require explicit approval regardless of tier"

### Layer 4: Record

Every decision — ALLOW or DENY — is signed into the governance chain. The record captures:

- What the agent requested (original tool name and parameters)
- What it was classified as (action category, targets, scope, confidence tier)
- Which policy rules were evaluated
- The decision and reasoning
- Timestamp, user identity, chain linkage

Full provenance. The chain is the proof layer.

**Open design question:** Should the chain also record execution outcomes — exit status, output digest, changed artifact hashes, post-state evidence? This would strengthen the proof from "authorization was granted" to "authorization was granted and here is what resulted." This matters more in Shape B but has value in Shape A for operations where outcomes are observable.

### Layer 5: Execute or Deny

**ALLOW:** The original operation executes as-is. We do not rewrite it, reimplement it, or translate it. The agent's tool call passes through untouched. We wrap the real operation — we do not replace it.

**DENY:** The agent receives a denial with the reason and the policy rule that triggered it. The denial is recorded in the chain.

### Layer 0: Leak Detection (Hook)

The observation hook sits outside MCP. In Shape A, its role is **boundary integrity measurement**. It detects operations that bypassed the MCP path — native agent capabilities that executed without transiting the governance boundary.

In a properly configured system where the runtime routes all operations through GovMCP, the hook should report almost nothing. Significant hook activity tells the operator that the boundary is incomplete — something is getting around GovMCP.

The transparency meter measures boundary completeness, not agent compliance. 100% means the boundary is tight. Anything less means operations are executing outside governance and the operator needs to understand why.

**Evolution toward Shape B:** In a governed execution environment, the hook's role shifts from boundary leak detection to **runtime effect monitoring** — observing what happens during and after allowed executions, detecting policy violations within governed execution (e.g., an approved script attempting unauthorized network access). This is a future capability that builds on the same hook infrastructure.

---

## 5. What This Is Not

### Not a correctness validator

Atested does not validate that the AI is making the right decision. A governed `git push` to the wrong branch is still a governed operation. The chain records that it happened, policy allowed it, and there's an audit trail.

The operator is not asking: "Is this AI doing good work?" They are asking: "Is this AI operating within the boundaries I set, and can I prove it?"

Policy defines boundaries — what operations are allowed, under what conditions, with what evidence. Policy does not judge whether a particular function is good code or whether a particular commit is the right architectural choice.

### Not a capability platform

We do not author a capability catalog. We do not add capabilities to agents. If an agent doesn't support git, it won't call git through us. We govern existing capabilities — we don't create new ones.

### Not a trust system

Governance decisions are based on observable evidence in the tool call — not on agent claims, manifests, or self-reported metadata. Where evidence is sufficient, classification is deterministic. Where evidence is insufficient, the system is explicit about its uncertainty and routes to operator judgment.

### Not a guarantee of effect containment (in Shape A)

Shape A governs the request boundary. It proves that authorization was evaluated, a decision was made, and the decision was recorded. It does not prove what happened during execution of an allowed operation. That distinction is important and must be communicated honestly to operators.

---

## 6. On-Install Experience

In the current design, a fresh installation shows 26% transparency because standard operations (git, grep, pytest) aren't governed. The operator spends their first session approving routine tools.

In the new design, a fresh installation routes all agent traffic through GovMCP. Standard operations at Tier 1 and Tier 2 are classified and governed automatically. The transparency meter starts near 100% for operations that transit the boundary. Opaque operations (Tier 3) surface for operator approval only when they first occur. The approvals workflow handles exceptions — not the baseline.

No catalog to configure. No tool mappings to maintain. No context window overhead from loading tool definitions. The agent connects to GovMCP and works normally.

---

## 7. Adversarial Considerations

A serious governance architecture must assume agents may — intentionally or through emergent behavior — attempt to circumvent governance.

### Attack surfaces

- **Compress destructive intent into generic execution.** Agent calls `bash -c "..."` with harmful commands that look benign at the parameter level.
- **Hide effects inside scripts.** Agent creates a script via an approved write, then executes it. The write is governed; the execution is governed; but the script's internal behavior is opaque.
- **Split actions across multiple benign calls.** Each individual call passes policy. The combined sequence achieves something no single call would be allowed to do.
- **Use encoded or obfuscated payloads.** Base64-encoded commands, compressed archives, encrypted instruction streams.
- **Exploit approved wrappers.** Once an opaque tool is approved, use it as a tunnel for unauthorized operations.
- **Abuse operator fatigue.** Generate many ambiguous approval requests, training the operator to approve without careful review.

### How Shape A addresses these

Shape A is honest about what it can and cannot defend against:

- **Generic execution and script hiding** are Tier 3 operations. Policy can require operator approval for all opaque execution. The approvals system — scoped to exact content hash, deployment context, and policy version — limits the blast radius of any single approval.
- **Multi-call sequences** are visible in the chain. Audit tools can correlate sequences across time. Pattern detection is a future capability but the data is captured.
- **Encoded payloads** are Tier 4. Default policy posture is DENY or explicit approval.
- **Operator fatigue** is a real risk. The system should surface approval requests with full evidence and confidence tier, and could implement rate limiting or escalation for high-frequency approval requests.

Shape A does not claim to prevent all adversarial behavior. It claims to record everything that transits the boundary, enforce policy on what it can classify, route uncertainty to operator judgment, and make its limits explicit.

Shape B, when implemented, addresses the execution containment gap through runtime isolation, egress control, and post-execution attestation.

---

## 8. Open Questions for Review

1. **MCP protocol constraints.** Does MCP support transparent proxying of arbitrary tool calls without prior registration? If not, what protocol extensions or shim layers are required? This needs a concrete feasibility check against real MCP implementations.

2. **Classification performance.** Evidence inference and policy evaluation add latency to every tool call. What is the acceptable latency budget? (Proposed targets: <50ms for Tier 1, <200ms for Tier 2, approval-gated for Tier 3-4.) Caching strategies for repeated identical calls.

3. **Policy expressiveness.** Are action categories + evidence + confidence tiers sufficient for all meaningful governance rules? Are there real-world governance policies that require sequence awareness or state tracking beyond single-call evaluation?

4. **Execution identity.** Whose credentials execute the operation — user, service account, agent session, delegated token? This affects both governance and proof.

5. **Result recording.** Should the chain capture execution outcomes (exit status, output digest, changed artifact hashes)? This strengthens proof from "authorization was granted" to "authorization was granted and here is what resulted."

6. **Approval inheritance.** When an operator approves an opaque tool, what generalizes? Exact binary hash? Command pattern? Signer? Target class? The scoping of approvals determines how much ongoing operator involvement is required.

7. **Multi-agent provenance.** When multiple agents act through GovMCP, what is the unit of accountability — agent identity, session, operator, request chain?

8. **Adversarial red team.** Before production release, run a structured red team exercise where testers attempt to bypass governance using obfuscated calls, script composition, binary execution, multi-step sequences, and approval exploitation. Results directly inform classification and policy improvements.

---

## 9. Design Principles

1. **Governance is structural, not voluntary.** The agent cannot avoid governance where the execution environment routes operations through the governance boundary.
2. **Evidence over claims.** Classify based on what the call contains, not what the agent says about it.
3. **Wrap, don't reimplement.** The real operation executes — we evaluate and record, we don't replace.
4. **Honest limits.** Classification is deterministic for observable properties. Effect determination ranges from deterministic to unavailable for opaque execution. We state which.
5. **Confidence tiers, not binary.** Every classification carries an explicit confidence level that informs policy response.
6. **Invisible to the agent.** The agent works normally. Governance adds no cognitive load and no context window cost.
7. **Exceptions, not baseline.** Operator intervention is for the unusual, not the routine. Standard operations are governed automatically.
8. **Transparent about boundaries.** The system measures and reports its own coverage gaps rather than assuming completeness.

---

## 10. Commercial Positioning

The strongest commercial message is not "we understand every tool."

It is:

**We shift governance from agent cooperation to execution-path control, record every decision in a signed chain, classify operations by observable evidence rather than agent claims, and make our uncertainty explicit rather than hiding it.**

Key differentiators:
- Governance by boundary position, not by prompt obedience
- Action-based policy instead of tool-name policy
- Signed, immutable chain of every ALLOW/DENY decision
- Explicit confidence tiers — the system tells you what it knows and what it doesn't
- Leak detection as boundary integrity measurement
- Zero agent-side configuration or context window cost
- Honest about the limits of request-boundary governance

---

## Appendix: Glossary

- **Shape A (Request-boundary governance):** Governance applied at the tool-call boundary. Classifies, evaluates, records, and allows/denies the request. Does not govern downstream execution effects.
- **Shape B (Governed execution environment):** Governance applied at both the request boundary and the runtime level. Controls filesystem, network, process, and credential access during execution. Requires compute-environment control.
- **Evidence inference:** Classification of tool calls based on observable parameters (paths, URLs, commands, targets) rather than agent-declared metadata.
- **Confidence tier:** The level of certainty about an operation's real effects, ranging from directly observable (Tier 1) to uninspectable (Tier 4).
- **Governance chain:** The signed, immutable, append-only log of every policy decision.
- **Leak detection:** Measurement of operations that bypass the governance boundary entirely, indicating boundary incompleteness.
- **Opaque execution:** Operations where the call parameters are visible but the internal behavior of the executed code is not deterministically known.
