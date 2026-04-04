# Atested: AI Agent Governance Proxy

## Design Brief — Revised After API Proxy Discovery

**Date:** 2026-04-03
**Author:** Atested
**Status:** Design — pre-implementation
**Classification:** Architecture redesign (v3)
**Review status:** Three external reviews incorporated, API proxy evaluation complete

---

## 1. What Atested Is

Atested is a governance proxy that sits between AI agents and their model providers. It intercepts the API conversation before any action executes, classifies operations by observable evidence, evaluates policy, records every decision in a signed chain, and allows or denies operations — all before the agent acts.

One configuration change. Every tool call governed. The agent never knows governance is in the path.

---

## 2. The Evolution

### v1: Tool catalog (retired)

Required agents to use a specific set of 46 governed tools. Governance depended on the agent choosing our tools over its native ones. Compliance was voluntary. Coverage was incomplete.

### v2: MCP mediation proxy

Accepted any tool call through MCP, classified by evidence, governed transparently. Fixed the voluntary compliance problem for MCP-routed operations. But agents with native built-in tools (file read/write, bash, git) bypassed the MCP boundary entirely. Coverage gap remained.

### v3: API-level governance proxy

Sits at the HTTP transport layer between the agent and its model provider. The agent thinks it's talking to Anthropic, OpenAI, or any model API. It's actually talking to Atested. Every tool call the model requests is visible in the API response before the agent executes it. No native tool gap. No MCP dependency. No agent modification.

---

## 3. How It Works

### The interception point

AI agents work in a loop:
1. Agent sends context to the model API
2. Model responds with tool calls: "read this file," "run this command," "write this code"
3. Agent executes the tool calls locally
4. Agent sends results back to the model API

Atested sits between steps 1-2 and 3-4. When the model responds with tool calls (step 2), Atested intercepts them before the agent sees them. Each tool call is classified, policy-evaluated, and recorded. ALLOW passes the tool call through to the agent unchanged. DENY replaces it with a denial message — the agent never receives the tool call and never executes it.

**Governance happens before any action is possible.**

### The flow

```
Agent → Atested Proxy → Model Provider
                ↓
        [Model responds with tool calls]
                ↓
        Classify each tool call (evidence inference)
                ↓
        Evaluate against policy rules
                ↓
        Record decision in governance chain
                ↓
        ALLOW: pass tool call to agent
        DENY: replace with denial text
                ↓
Agent receives response (governed)
```

### What the proxy sees

The API conversation contains everything needed for governance:
- **Tool definitions:** What tools the agent has available
- **Tool calls:** What the model is asking the agent to do — tool name, parameters, targets
- **Tool results:** What happened when the agent executed a previous call

This is the complete picture of agent activity. File paths, commands, URLs, arguments — all visible in the API payload. The evidence inference classifier operates directly on this data.

### Streaming support

The proxy buffers tool_use blocks from streaming responses, classifies each one (sub-millisecond), and either passes through or replaces. Text blocks stream through unmodified. The user experiences normal streaming with governance applied selectively to tool calls.

---

## 4. Classification and Policy

### Evidence inference

Classification is based on observable evidence in the tool call parameters — not on tool names, not on agent claims.

### Confidence tiers

- **Tier 1 — Directly observable.** File paths, URLs, explicit targets. Deterministic.
- **Tier 2 — High-confidence inferred.** Git operations, curl, common commands. Primary effects reliable.
- **Tier 3 — Opaque execution.** Scripts, interpreters, binaries. Entry point visible, internal behavior not.
- **Tier 4 — Uninspectable.** Encoded payloads, obfuscated parameters. Minimal classification.

### Policy dimensions

Action type, target class, scope, confidence tier, actor/context, risk posture, consequence class.

### Policy response by tier

- Tier 1-2: Automatic ALLOW/DENY by policy rule
- Tier 3: Candidate for operator approval
- Tier 4: Default DENY or explicit approval required

---

## 5. What Carries Forward

The API proxy architecture reuses 95%+ of the v2 components:

- **Evidence classifier** (`scripts/classifier.py`) — operates on (tool_name, args), transport-agnostic
- **Policy evaluator** (`scripts/policy_eval_v2.py`) — takes classifier output, returns decisions
- **Policy rules** (`capabilities/policy-rules.json`) — declarative, transport-agnostic
- **Shared validation** (`scripts/policy_eval_shared.py`) — path validation primitives
- **Chain recording** — append, verify, sign, all unchanged
- **Approval mechanics** — scoped approvals for Tier 3/4 operations
- **Dashboard** — all tabs, all visualizations
- **Audit tools** — chain queries, reports, detail views

What's new: the HTTP proxy layer that intercepts API traffic (`proxy/server.py`). What's complementary: `mcp/v2_proxy.py` (MCP transport binding for upstream tool servers).

The MCP proxy remains complementary for governing upstream MCP tool servers. The API proxy governs the agent. Different layers, both useful.

---

## 6. Deployment Models

### Self-hosted (local proxy)

The user runs Atested on their own machine or server. The agent points at `localhost` instead of the model provider. This is the developer, power user, and enterprise compliance path.

**Installation:** Run the proxy, set one environment variable (`ANTHROPIC_BASE_URL=http://localhost:PORT/anthropic` or equivalent for other providers). Done.

No MCP configuration. No tool catalogs. No agent modification. One environment variable.

### Cloud-hosted (governance as a service)

Atested runs as a hosted service. The user signs up, receives a proxy endpoint URL, and configures their AI tool to use it. We proxy to the real model provider, governing everything in transit. The user doesn't install or run anything.

**Works on any device, any platform.** If the AI application allows configuring its API endpoint, it can be governed — desktop, mobile, web-based agents.

### Hybrid

Enterprise customers run Atested on their own infrastructure but connect to our management plane for policy updates, dashboard hosting, and support. Conversation data stays on their network; governance configuration is managed centrally.

---

## 7. Who This Is For

### Developers and AI engineers

Govern coding agents. Policy enforcement, audit trails, tool-level governance. Self-hosted.

### Teams and organizations

Shared policies across a team's AI usage. Visibility into what AI agents are doing across the organization. Budget controls, access controls, compliance reporting.

### Regulated industries

Finance, healthcare, government. Provable governance, signed audit chains, policy enforcement. Self-hosted or hybrid with data sovereignty.

---

## 8. Product Shape

### Shape A: Request-boundary governance (current)

Governs the API conversation between agent and model. Classifies tool calls, evaluates policy, records decisions. Does not govern what happens during execution of an allowed tool call.

### Shape B: Governed execution environment (future)

Additionally constrains what happens during and after allowed execution — filesystem isolation, network egress control, credential mediation, process-level governance. Requires compute environment control.

Shape B builds on Shape A.

---

## 9. Honest Limits

- **We govern the request, not the execution.** An allowed tool call executes on the agent's machine. We don't control what happens during execution. (Shape A limitation.)
- **Classification is not omniscient.** Tier 3 and 4 operations have limited visibility into real effects. The system is explicit about what it knows and what it doesn't.
- **We don't validate correctness.** A governed `git push` to the wrong branch is still governed. We prove the operation was within policy boundaries, not that it was the right thing to do.
- **Cloud-hosted means trust.** Users routing through our hosted service trust us with their AI conversations. We must earn and maintain that trust through transparency, minimal retention, and clear privacy commitments.

---

## 10. Design Principles

1. **Governance before execution.** Every tool call is governed before the agent acts on it.
2. **One configuration change.** No agent modification, no tool catalogs, no MCP dependency. Change the API endpoint, governance is active.
3. **Evidence over claims.** Classify based on what the tool call contains.
4. **Wrap, don't reimplement.** The real operation executes unchanged — we evaluate and record.
5. **Honest limits.** Explicit about what we can and cannot govern.
6. **Confidence tiers.** Every classification carries an explicit confidence level.
7. **Invisible to the agent.** The agent works normally. Zero context window cost.
8. **Platform and provider agnostic.** Any agent, any model provider, any device.
9. **Exceptions, not baseline.** Standard operations governed automatically. Operator involvement only for the unusual.
10. **Transparent about boundaries.** The system measures and reports its own coverage.
