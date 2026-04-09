# Atested: Reliability Intelligence

## Design — Production Measurement of AI Model Behavior

**Date:** 2026-04-09
**Author:** Atested
**Status:** Design — pre-implementation
**Classification:** Architecture extension and new product pillar
**Working title:** "Reliability Intelligence" — provisional; final product name deferred
to the marketing and positioning conversation
**Companion docs:** [atested-v3-design.md](atested-v3-design.md) (v3 proxy
architecture), [operator-identity.md](operator-identity.md) (operator identity
layer), [telemetry.md](telemetry.md) (aggregated usage reporting)
**Investigation basis:**
[D-2026-0409-004-data-story-discovery.md](../investigations/D-2026-0409-004-data-story-discovery.md)
(factual foundation for this design)

---

## 1. Purpose and Status

This document defines the reliability intelligence layer for Atested: the
mechanism by which Atested measures AI model behavior in production and
presents concrete evidence of that behavior to users. Reliability intelligence
is both a product feature and a tier differentiator.

The design is pre-implementation. No code, schema changes, or build work is
authorized by this document.

Reliability intelligence extends the v3 proxy architecture
(atested-v3-design.md) by expanding what the proxy extracts from the API
stream beyond governance decisions. It is parallel to the operator identity
layer (operator-identity.md) and the telemetry layer (telemetry.md) — separate
concerns that share infrastructure but do not depend on each other at the
design level. Both are build-time dependencies for the reliability intelligence
implementation.

The factual foundation for this design is the investigation at
D-2026-0409-004, which enumerates every field in the API stream, classifies
each by privacy boundary, categorizes extraction complexity, and identifies the
signals that are unique to Atested's position in the API path.

---

## 2. Problem Statement

Atested's v3 proxy sits on the HTTP path between AI agents and model
providers. It observes every tool call, every response, every conversation
turn. Today the proxy uses this vantage point exclusively for governance:
classifying operations, evaluating policy, recording decisions. The same
vantage point enables a much richer set of measurements about model behavior
— measurements that are valuable to users in ways governance alone is not.

Users running AI agents today have no good way to answer questions that matter
to them:

- How reliable is my model at producing well-formed tool calls?
- How much am I actually spending on AI, broken down by model and workflow?
- Which of my models is most cost-effective for tool-heavy work?
- When governance denies an operation, how does the model respond?
- How does my agent's behavior compare to fleet averages across similar users?

Model vendors publish evaluation numbers from controlled environments.
Observability tools sit outside the API path and reconstruct usage from logs.
No product today provides production-grade reliability measurements for AI
models, because no product today has both the vantage point and the privacy
posture to do so credibly. Atested has both: it sits in the API path (so it
sees every token at the source) and it enforces a rigorous privacy boundary
between model-side and client-side data (so measurements can be aggregated
without exposing what users are doing).

The product opportunity is to turn Atested's governance vantage point into a
reliability intelligence platform that measures what matters about AI agents —
their reliability and their cost — while maintaining the same privacy
discipline that governs everything else in the product.

---

## 3. Design Principles

1. **Model reliability, not agent non-compliance.** The agent faithfully
   executes what the model produces. When tool calls are malformed,
   hallucinated, or repeatedly denied, this is a measurement of model behavior,
   not agent misbehavior. The product framing throughout is diagnostic, not
   adversarial. "Your model produced 12 malformed tool calls this week" is
   actionable. "Your agent misbehaved" is blame.

2. **Client data is protected; model behavior is observable.** The privacy
   boundary established in telemetry.md applies here without modification.
   Client-side data — paths, content, tool arguments, conversation content —
   is rigorously protected and never leaves the client machine in identifiable
   form. Model-side data — model identifier, token usage, stop reasons,
   structural correctness of tool calls, behavioral patterns — is observable,
   measurable, and aggregatable. Every extraction point in this design enforces
   this boundary.

3. **Show the work.** Every metric in the dashboard links to the underlying
   chain records that prove it. No number exists in the UI without auditable
   evidence. This applies to evaluation milestones, ongoing dashboard metrics,
   and any reliability intelligence claim the product makes. It is an invariant
   of the design, not a UX preference.

4. **Prove value, then pay.** The evaluation experience demonstrates concrete
   value on the user's own data before asking for payment. Upgrade prompts are
   grounded in the user's recorded events, not abstract feature promises. This
   is a tone-of-voice commitment across all product surfaces — marketing copy,
   onboarding, upgrade flows, dashboard language — not merely a trial mechanic.

5. **Per-install first, cross-install later.** The product ships in two layers.
   Per-install intelligence runs entirely from local chain data, requires no
   fleet dependency, and delivers value on day one to a single user.
   Cross-install intelligence depends on fleet scale for statistical
   significance and ships as a separate layer. The per-install layer is the
   immediate product. The cross-install layer is the network-effect product
   that compounds with adoption.

6. **Multi-provider from launch.** Reliability intelligence is not credible as
   a single-vendor feature. The first public launch supports multiple model
   providers — Anthropic, OpenAI, Gemini, LiteLLM-compatible — to establish a
   category claim rather than a vendor-specific tool claim. Provider parsers
   are built sequentially during implementation, but the launch happens when
   the parser set is broad enough for the category positioning.

7. **Reliability and cost as co-equal pillars.** The product measures two
   things about AI agents: how reliably they work and how much they cost.
   Neither is secondary. Cost visibility is a first-class product feature,
   not an afterthought attached to reliability metrics.

---

## 4. Scope and Product Layers

The design has two distinct product layers with different timelines and
different build dependencies.

### Layer 1 — Per-install intelligence

Runs entirely from the local chain and proxy-extracted data. No fleet
dependency. Delivers value to a single user from their first day of use.

- Per-model reliability metrics: malformed tool call rate, hallucinated tool
  detection, stop reason distribution
- Per-model cost visibility: token usage, cost estimates, cost-per-tool-call
  analysis
- Time-series trends of governance activity
- Approval utilization and stale approval detection
- Chain health metrics
- Evaluation milestones and upgrade prompts grounded in user-specific evidence

### Layer 2 — Cross-install intelligence

Depends on fleet scale. Ships later, after adoption has produced enough
installs for aggregate metrics to be statistically meaningful.

- Fleet-wide reliability comparisons per model ("your Claude Opus 4.6
  reliability is in the 62nd percentile")
- Fleet-averaged cost efficiency benchmarks
- Cross-vendor model comparisons derived from the fleet ("Claude Opus 4.6
  produces malformed tool calls at rate X across the fleet; GPT-5 at rate Y")
- Denial recovery behavior patterns per model — the most expensive signal to
  build but also the most uniquely Atested, requiring both fleet scale and
  cross-request state
- Industry-segmented comparisons as the fleet grows large enough to segment
  meaningfully

Layer 1 ships first. Layer 2 is a later phase whose schedule depends on fleet
growth.

---

## 5. Proxy Extraction Scope

Per the investigation at D-2026-0409-004 §4, proxy extraction is classified by
implementation complexity. The first reliability intelligence build implements
the "minimal extension plus free wins" scope: Option A from the investigation,
plus one zero-cost addition.

### Included in the first build

All of the following are stateless per-request extractions. None require
cross-request conversation state. The proxy remains a stateless request filter.

| Signal | Source | Notes |
|---|---|---|
| `model` | Request and response body | Trivial extraction. Core attribution primitive for every per-model metric. |
| `usage` object | Response body | `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`. Foundation for cost visibility. |
| `stop_reason` | Response body and `message_delta` event | Model completion signal. Distribution is a reliability indicator. |
| Sampling parameters | Request body | `temperature`, `top_k`, `top_p`, `max_tokens`. Model configuration metadata. |
| Conversation depth | Request body | Length of the `messages` array. Proxy inspects array length only, not content. |
| Tool call density | Response body | Count of `tool_use` blocks per response. Partially implemented in the current proxy. |
| Tool definition count | Request body | Length of the `tools` array. Proxy inspects array length only, not content. |
| Request-response latency | Proxy timing | Measured at the proxy as round-trip time. Labeled as "round-trip time" in all product surfaces, never as "model inference time" (per D-2026-0409-004 §7.2 — the measurement includes network conditions and is confounded for cross-install comparison). |
| Governance overhead | Proxy timing | Time spent in the classify + evaluate path. Useful for proxy performance monitoring. |
| Malformed JSON detection | Proxy error path | The existing JSON parse failure at `server.py:408-413` is systematically recorded as a field on the chain event rather than silently logged. This is a zero-cost addition — the detection already exists; the recording is new. |
| Hallucinated tool detection | Request body and response body | Compares tool names in response `tool_use` blocks against the `tools` array in the request body. Detects cases where the model invoked a tool that was not defined in the request. Medium complexity — requires request body parsing and per-request state, but stateless across requests. Promoted from R-12a to R-1 (D-2026-0409-006) because the §11 evaluation experience depends on this signal. |

### Deferred to later phases

These signals are not out of scope for reliability intelligence. They are
deferred to later build phases because they require either nontrivial
per-request parsing or cross-request conversation state.

| Signal | Complexity | Reason for deferral |
|---|---|---|
| Tool result error rate | High — cross-request stateful | Requires correlating `tool_result` blocks in incoming requests with prior `tool_use` blocks in previous responses. Phase identifier: R-12b. |
| Denial recovery patterns | High — cross-request stateful | Requires a conversation-level state machine to track how models respond after governance denies an operation. The most uniquely Atested signal. Phase identifier: R-12c. |
| Repeated failure loop detection | High — cross-request stateful | Requires cross-request state to identify agents retrying the same denied operation. Phase identifier: R-12d. |

---

## 6. Multi-Provider Architecture

The design is provider-agnostic at the schema level. The proxy dispatches
incoming requests to provider-specific parsers based on the request shape or
routing URL. Each parser extracts the fields named in §5 and normalizes them
into a common schema.

### Provider parsers in the first launch

1. **Anthropic Messages API parser.** Built first. Proves the extraction
   pattern end-to-end against the API that the current proxy already handles.
2. **OpenAI Chat Completions API parser.** Built second. The most important
   second provider for category credibility.
3. **Google Gemini API parser.** Built third.
4. **LiteLLM-compatible generic parser.** Built fourth. Covers self-hosted
   models and aggregator endpoints that conform to a common interface.

The public launch happens when all four parsers are working. Launching with
Anthropic alone is explicitly rejected — a reliability intelligence product
that works only with one vendor's models cannot make the category claim the
positioning requires.

### Provider feature parity

Not every provider exposes the same fields in the same shapes. Some self-hosted
models do not support structured tool calling at all and fall back to
text-parsed tool calls. The design acknowledges this honestly: the metrics
available for a given install depend on which providers the install uses and
what those providers expose.

An install running only OpenAI gets the full OpenAI metric set. An install
running a self-hosted Llama via LiteLLM gets a reduced set because the
underlying model does not produce structured tool calls. The dashboard
indicates what is measurable versus what is unavailable for each model, rather
than silently omitting missing data.

### Per-install model coverage as a tier differentiator

Free tier users pick one model to analyze via an explicit first-run choice.
From then on, the free tier's reliability intelligence dashboard covers only
that one chosen model, even if the user runs others through the same Atested
install. Paid tier users get reliability intelligence for every model they run.

The upgrade prompt for free users who run multiple models is concrete and tied
to something they are actively doing: "Upgrade to Paid Personal to analyze
GPT-5 alongside Claude Opus 4.6."

---

## 7. Where Per-Install Metrics Live

All per-install metrics are computed and displayed locally from chain data and
proxy-extracted data. Nothing additional leaves the machine beyond the existing
telemetry payload defined in telemetry.md. Paid tiers unlock richer dashboard
views of the same locally-held data, not a richer transmission.

This has two implications.

**Local metrics can be richer than transmitted metrics.** Per-install metrics
can include fields that would never be safe to transmit — per-tool-name
breakdowns, full path patterns visible only to the local user, MCP server
names the user has connected — because these never leave the machine. The
privacy constraints that bind telemetry payloads do not bind the local
dashboard.

**The transmission pipeline stays simple.** No enhanced telemetry payload for
paid tiers. No tier-varying opt-out. Everything that ships off the machine
ships under the same rules for every install, as specified in telemetry.md.

Cross-install metrics (Layer 2) ship through a separate telemetry channel.
See §8.

---

## 8. Cross-Install Intelligence (Layer 2)

Cross-install intelligence is a separate data channel from the governance
telemetry defined in telemetry.md. The rationale, per D-2026-0409-004 §8.3
and Tier 0 concurrence: keeping the two channels separate preserves the v1
telemetry contract as documented, enables independent schema evolution, and
makes opt-in/opt-out behavior clean per channel.

### Channel properties

- **Separate chain event type** for cross-install observations:
  `request_observation` (distinct from the per-tool-call governance decision
  events and from the `telemetry_send` events in telemetry.md).
- **Separate payload schema** with its own version number, independent of the
  governance telemetry v1 schema.
- **Separate transmission endpoint** on atested.com.
- **Separate opt-out control** from governance telemetry. A user can opt out
  of reliability intelligence cross-install data while still contributing
  governance telemetry, or vice versa, or both.
- **Same privacy boundary** as governance telemetry: aggregated only,
  content-free, path-free, no identifying details about the client's work.

### Aggregation requirements

Cross-install metrics require a minimum fleet size to be statistically
meaningful. The design specifies a minimum sample threshold (specific number
to be calibrated during the build phase) below which fleet-comparison metrics
are not presented. Below the threshold, the dashboard shows: "Fleet comparison
data will be available when the Atested fleet reaches sufficient scale."

---

## 9. Chain Event Model

Reliability intelligence observations are recorded in the chain as a new event
type, `request_observation`, distinct from the per-tool-call governance
decision events. One `request_observation` event is written per API
request-response cycle, containing the request-level metadata extracted from
the API stream: model, usage, stop reason, sampling parameters, conversation
depth, latency, and governance overhead.

The governance decision events — one per `tool_use` block — remain unchanged
and continue to record per-tool-call classification and policy evaluation. The
data model stays clean: governance records describe decisions, observation
records describe measurements. The two can be joined by request ID for analyses
that need both.

Both event types are written to the chain via the INV-010 lock protocol. No
changes to the protocol are required.

---

## 10. Cost Visibility

Cost visibility is a co-equal pillar of reliability intelligence. The
rationale: every paying user of AI cares about what it costs, and Atested is
structurally positioned to answer the question credibly because it sits in the
API path and sees every token at the source.

### Feature set

**Built-in pricing data.** For models where Atested knows the published rates
(Anthropic, OpenAI, Google), the dashboard multiplies token counts by published
pricing to produce cost estimates. Estimates are labeled as approximate because
real billing depends on account tier and discounts that Atested does not see.

**User-provided pricing.** For models where Atested does not have built-in
pricing data — self-hosted models, aggregator services, negotiated enterprise
rates — the user enters their per-token cost in settings. The dashboard uses
it for that user's cost calculations.

**Per-session cost reporting.** "This chat session cost approximately $X."
Useful for users who want to understand the cost of a specific piece of work.

**Running totals.** Daily and hourly cost accumulations visible in the
dashboard header.

**Daily/weekly/monthly summaries.** Per-model breakdowns over configurable
time windows.

**Cost-per-tool-call analysis.** "Your average tool call on Claude Opus 4.6
costs $0.03. Claude Sonnet 4.5 averages $0.008 per tool call and handled 73%
of your tool calls at 19% of the cost."

**New-tool evaluation helper.** When a user adds a new AI model to their
workflow, the dashboard shows the actual token usage and cost from their
first N days of usage, giving real data for the adopt-or-abandon decision.

Cost visibility metrics respect the same privacy boundary as everything else.
Token counts are model-side. Costs derived from token counts are model-side.
What the user was doing that incurred the cost is client-side and never leaves
the machine.

---

## 11. Evaluation Model

The evaluation model is milestone-based with a time cap. It is not
time-based.

### During evaluation

The user sees the full per-install reliability intelligence dashboard — every
metric, every chart, every per-model breakdown (for the one model they chose
on free tier, or all models on paid tier during a trial). The dashboard header
shows an Evaluation Progress section with counters for each milestone.

### Milestones

The milestones are counts of specific, chain-verifiable events. Placeholder
values to be calibrated during the build phase against real usage data:

- Hallucinated tool calls prevented: target count TBD
- Malformed tool calls surfaced: target count TBD
- Destructive operations governed: target count TBD
- Tokens governed reliably (token-based milestone): target count TBD

Every milestone counter links directly to the chain records that prove it.
Clicking the counter shows the specific events — timestamp, model, what was
caught, what was prevented. The counts are not aspirational. They are receipts.

### Evaluation end conditions

Evaluation ends when either condition is true:

- Any one milestone is reached (proves the product's value on the user's own
  data).
- 60 calendar days have elapsed from install (hard cap, no exceptions).

### After evaluation

The dashboard collapses to the free-tier experience: a single headline
reliability metric visible in the dashboard header, with rich views gated
behind upgrade prompts. The upgrade prompts reference the user's own recorded
events: "During your 60-day evaluation, Atested recorded X tool calls,
surfaced Y potential issues, and governed Z tokens of AI activity" — even if
no milestone was fully reached. The pitch is always grounded in actual data.

### Chain evidence

Every claim the evaluation makes must be backed by chain records the user can
audit. There is no "evaluation complete" state that the dashboard declares
without being able to produce the specific events that triggered it. This is
the "show the work" principle applied to the evaluation flow specifically.

---

## 12. Tier Differentiation

This section summarizes how the tiers differ on reliability intelligence
specifically. It does not redefine Atested's overall tier structure.

### Free tier

- Single-model reliability intelligence (user picks one model at first run)
- Headline reliability metric visible after evaluation
- Basic cost visibility for the chosen model
- Access to governance dashboard sections (unchanged from current product)
- Evaluation experience: full rich dashboard until milestone or 60-day cap

### Paid Personal

- Multi-model reliability intelligence (every model the user runs)
- Full per-install dashboard with trends, comparisons, time-series views
- Full cost visibility including cost-per-tool-call analysis and new-tool
  evaluation helper
- Priority email support
- **Pricing:** monthly or annual billing. Monthly is available for lower
  commitment; annual carries a discount.

### Team

- Everything Paid Personal offers, plus:
- Multi-user visibility (per the tier's existing team-size allowance)
- Per-agent / per-project reliability breakdowns
- Team-level cost aggregation
- **Pricing:** annual only. No monthly option.

### Business

- Everything Team offers, plus:
- Early access to cross-install intelligence features as they ship
- Organization-level reporting suitable for compliance and finance teams
- **Pricing:** annual only.

### Enterprise

- Everything Business offers, plus:
- Negotiated terms
- Custom reliability metric definitions on request
- Potential access to aggregate fleet data via API under appropriate licensing
- **Pricing:** negotiated; annual or multi-year.

### Pricing rationale

Paid Personal is an individual commitment where monthly billing reduces the
friction of the upgrade decision. Higher tiers are organizational commitments
where annual-only pricing aligns incentives — the vendor invests in long-term
value, the customer commits to adoption — and reduces billing complexity for
both sides.

---

## 13. Dashboard Architecture

Reliability intelligence introduces enough new functionality that the existing
dashboard architecture cannot absorb it as a minor addition. The dashboard
needs a new top-level section — working title "Intelligence" — that becomes
the primary landing experience for users whose interest is model behavior
rather than governance administration.

The existing dashboard sections (Overview, Activity, Approvals, Audit, Record
Detail, Report, Health, Configuration, Feedback) remain available. They serve
a real audience: operators and auditors whose job is governance administration.
But they are no longer the default view for users whose primary interest is
"how are my models behaving and what are they costing me."

### This is substantial UI work

The design names it as such so that build sequencing acknowledges the real
scope. The new Intelligence section contains:

- Landing view with headline metrics and current state
- Per-model reliability views
- Cost visibility views (including the multi-modal cost features from §10)
- Time-series trends
- Evaluation progress view (during evaluation) or upgrade prompt view (after)
- Click-through evidence from every metric to its underlying chain records

The specific UX design of each view is build-time work. This section
establishes that the dashboard architecture requires the new section and
sketches its responsibilities.

---

## 14. Honest Limits and Acknowledged Complexities

**Multi-provider parity is uneven.** Some providers expose rich tool calling;
others do not. The measurements available depend on what each provider's API
reveals. The dashboard must indicate what is and is not measurable per
provider, not silently omit fields.

**Latency is confounded.** Request-response latency measured at the proxy
includes network conditions. It is useful for per-install trend analysis but
misleading for cross-install comparison. The design labels it as "round-trip
time" and never as "model inference time."

**Cross-install intelligence needs fleet scale.** Layer 2 is not useful with a
small fleet. The design specifies a minimum sample threshold below which
cross-install metrics are not presented. The specific threshold is build-time
calibration.

**Cross-request state is architecturally expensive and deferred.** The signals
that require it — denial recovery patterns, tool result error rates, repeated
failure loops — are the most uniquely Atested signals but also the most
expensive to build. The first build explicitly defers them.

**Per-model attribution has implicit competitive implications.** Publishing
per-model reliability data makes Atested an implicit model evaluation product.
The design is aware of this. Per-install data (user sees their own model's
behavior) carries different risk than cross-install data (fleet averages
published on atested.com). Publication strategy is deferred to the marketing
and positioning conversation and noted as an open item in §16.

**Evaluation milestone thresholds are placeholder.** The specific numbers must
be calibrated against real usage data after the feature ships. The design
specifies the mechanism; calibration is build-time work.

**The minimum sample threshold for cross-install metrics is also placeholder.**
Same reasoning: the threshold requires real fleet data to calibrate.

**The dashboard rewrite scope is real.** The Intelligence section described in
§13 is not absorbed into a minor UI update. Build sequencing must acknowledge
the effort.

---

## 15. Build Sequence (Informational)

This section is informational only. It describes the anticipated dispatch
sequence to implement this design. The actual dispatches are not authorized by
this document.

Reliability intelligence build work sequences after operator identity (L-1
through L-6) and after telemetry (T-1 through T-8 or a compressed subset; see
§16 open items). Both are dependencies.

**R-1: Proxy extraction — Anthropic parser.** Implement the §5 field set for
the Anthropic Messages API. Stateless per-request extraction. Includes
systematic recording of the existing JSON parse failure detection. Anthropic
parser only — this phase proves the extraction pattern end-to-end. R-1 also
includes hallucinated tool detection, which was originally classified by the
D-2026-0409-004 investigation as a deferred signal (R-12a) but promoted into
R-1 (D-2026-0409-006) to support the launch evaluation experience described in
§11. The expanded scope adds request body `tools` array parsing to the proxy,
which is medium-complexity stateless work — bounded but nontrivial.

**R-2: OpenAI parser.** Add the OpenAI Chat Completions API parser to the same
extraction infrastructure. Sequential, not parallel with R-1.

**R-3: Gemini parser.** Add the Google Gemini API parser.

**R-4: LiteLLM-compatible generic parser.** Add the parser for self-hosted
models and aggregator endpoints.

**R-5: Chain event schema.** Extend the chain event schema for
`request_observation` events. Writer conforms to INV-010.

**R-6: Per-install dashboard — Intelligence section.** The new top-level
dashboard section from §13. Includes landing view, per-model reliability
views, click-through evidence to chain records, evaluation progress UX.

**R-7: Cost visibility.** The feature set from §10: built-in pricing data,
user-provided pricing, per-session cost, running totals, cost-per-tool-call
analysis, new-tool evaluation helper.

**R-8: Evaluation milestones.** Milestone counters, threshold detection,
dashboard state transitions, upgrade prompt logic, 60-day cap.

**R-9: Tier enforcement.** Single-model restriction on free tier with explicit
user choice. Multi-model unlock on paid tiers. Integration with the licensing
layer from operator-identity.md.

**R-10: Public launch.** Requires R-1 through R-9 complete. This is when
reliability intelligence becomes publicly available. The public claim
"reliability intelligence for your AI agents" requires the multi-provider
parser set, the dashboard, the cost features, the evaluation flow, and the
tier enforcement all working together. Launching with any of these missing
would be a partial product.

**R-11+: Cross-install intelligence (Layer 2).** New telemetry channel,
aggregation pipeline on atested.com, fleet-comparison metrics, cross-vendor
reliability data. Ships after R-10 and after fleet scale justifies it.

**R-12+: Deferred signals.** Tool result error rate (R-12b), denial recovery
patterns (R-12c), repeated failure loop detection (R-12d). Each is its own
build phase. (R-12a — hallucinated tool detection — was promoted into R-1; see
above.)

---

## 16. Open Items

**Dashboard rewrite scope.** This design establishes that a new Intelligence
section is needed. The exact boundary between "new section" and "fuller
rethink of the operator UI" is not decided. Build dispatches will need to
resolve this.

**Specific milestone thresholds.** The milestone mechanism is specified; the
exact counts are placeholder. Calibration against real usage data is build-time
work.

**Build sequence compression.** Whether to compress the telemetry build (T-1
through T-4 only as a prerequisite for reliability intelligence, with T-5
through T-8 landing in parallel) or wait for full telemetry completion before
starting reliability intelligence. This is a scheduling question that affects
time-to-market. The design names both options and defers the decision.

**Cross-install intelligence fleet threshold.** The specific minimum fleet
size for statistical validity. Build-time calibration.

**Final product name.** Working title is "Reliability Intelligence." Final
name comes from the marketing and positioning conversation.

**Publication strategy for cross-install metrics.** Whether per-model fleet
data is published externally on atested.com, shown only privately to paying
customers, or something in between. This is a marketing and positioning
decision, not a design decision. Noted here because per-model attribution
carries competitive implications (§14) and the decision should be made
deliberately rather than by default.
