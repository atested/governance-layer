# Design rationale

Atested's architecture is the result of choices that have alternatives. This page explains the choices and their tradeoffs so you can evaluate whether the approach makes sense for your situation.

## Why an HTTP proxy

The proxy sits at the API transport layer between the agent and the model provider. This was not the first approach. Atested v1 used a governed tool catalog (46 wrapper functions the agent called instead of native tools). v2 used an MCP mediation proxy. Both required the agent to cooperate: call the governed tools, route through the governed endpoint. If the agent used a native tool directly, governance didn't see it.

The HTTP proxy eliminates voluntary compliance. The agent sends API traffic through `ANTHROPIC_BASE_URL=http://localhost:8080/anthropic` and every model response passes through the proxy. The agent uses its normal tools. Governance applies because the proxy can see every tool call the model proposes before the agent receives it.

The tradeoff: the proxy only sees API-level traffic. If the agent has local capabilities that don't go through the model (a hardcoded file write in agent code, for example), the proxy can't govern them. In practice, tool-calling agents execute the tools the model proposes, so this gap is narrow. But it's real, and Atested doesn't pretend otherwise.

## Why evidence inference

The classifier determines what a tool call does by inspecting its parameters (file paths, URLs, command strings, target patterns), not by trusting the tool's name. A tool called "SafeWrite" might write to `/etc/passwd`. A tool called "Bash" might just run `ls`.

Evidence inference means classification accuracy depends on how much evidence is visible in the parameters, not on whether tool names are honest. This maps directly to the confidence tiers: Tier 1 operations have their effects fully visible in the parameters (a file write with an explicit path). Tier 4 operations have their effects hidden (a base64-encoded payload).

The tradeoff: inference from parameters is not omniscient. Tier 3 operations (running a script, launching an interpreter) have their entry point visible but their actual behavior unknown. The classifier knows the agent is running `python3 deploy.py` but doesn't know what `deploy.py` does. This is handled by defaulting Tier 3 to DENY unless explicitly approved.

## Why confidence tiers

Four tiers quantify how much the classifier knows about a tool call's effects.

Tier 1 means the effects are directly observable in the parameters. A file read with an explicit path. The classifier knows exactly what will happen. Tier 2 means the effects are reliably inferred from known patterns: `git push`, `curl https://example.com`, `npm install`. The classifier has high confidence but is pattern-matching, not observing directly. Tier 3 means the entry point is visible but the behavior is opaque: running a script, launching an interpreter, piped commands. Tier 4 means the payload is uninspectable: base64-encoded content, hex blobs, obfuscated arguments.

Tiers 1 and 2 get automatic policy decisions (ALLOW or DENY based on rules). Tier 3 defaults to DENY but is an approval candidate: the operator can review and approve specific Tier 3 operations. Tier 4 defaults to DENY with no override path in the standard policy.

The alternative would be binary (known/unknown) or no tiers at all (classify everything the same way). Tiers let the operator set different policies for different confidence levels, which matches how risk actually works.

## Why first-match declarative rules

Policy rules are a JSON array evaluated in order. The first rule whose conditions match the classification wins. The rule specifies ALLOW or DENY.

First-match ordering means the operator controls precedence explicitly. Sensitive-path denials come before general read-allows. Tier 4 denials come before everything. The operator reads the rules top to bottom and knows exactly how any given tool call will be evaluated.

The alternative would be weighted rules, scoring systems, or ML-based policy evaluation. All of those introduce non-determinism. Given the same tool call, a scoring system might produce different results depending on context. Atested's policy evaluation is deterministic: same inputs, same output, every time. You can replay a tool call against the policy rules and get the same decision the proxy made in production.

## Why the chain

Every decision (ALLOW and DENY) is recorded in an append-only JSONL file. Each record contains a SHA-256 hash of the previous record. Records are signed with Ed25519. The result is a tamper-evident log: modifying any record changes its hash, which breaks the chain from that point forward.

The chain is not a database. It's an evidence trail. You can export it, share it with an auditor, verify it on another machine with the public key. The verifier walks the chain and checks every hash and every signature. If everything passes, you know the chain hasn't been modified since the records were written.

The chain is also the reason Atested can make specific claims about what happened during an agent's operation. Without the chain, governance is assertion. With it, governance is evidence.

## Why the v2-to-v3 pivot

Atested v2 used an MCP-based mediation proxy. The agent called governed tools via MCP, and the proxy classified and evaluated each call. This worked for MCP-routed operations but left a coverage gap: native tool calls (Read, Write, Bash, Edit, Glob, Grep) bypassed MCP entirely because the agent runtime executed them directly.

The v3 pivot moved governance from the MCP layer to the HTTP transport layer. Instead of wrapping individual tools, the proxy intercepts the API response that contains all tool calls. This closed the coverage gap. The classifier and policy evaluator (95% of the v2 codebase) carried forward unchanged. The transport layer was the only new code.

## Honest limits

Atested governs requests, not execution. If a tool call is allowed and the agent executes it, whatever happens during execution is outside Atested's control. The chain records the decision, not the outcome.

Classification is limited by what's visible in the parameters. Tier 3 and Tier 4 operations are genuinely uncertain, and the system says so explicitly rather than guessing.

The chain proves integrity against after-the-fact tampering. It does not protect against a compromised proxy writing false records with valid signatures. The threat model assumes an honest proxy on an uncompromised machine.
