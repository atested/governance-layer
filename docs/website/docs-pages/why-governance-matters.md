# Why governance matters

AI agents execute tool calls. That's what makes them useful. They write files, run commands, make network requests, modify configurations, install packages, and interact with external services. The tool calls are proposed by a language model and executed by the agent runtime with whatever permissions the agent has.

The model hallucinates. This is not a bug that will be fixed in the next release. It is a structural property of how large language models work. The model generates statistically plausible completions, and sometimes a statistically plausible completion is a tool call that does something wrong: writes to the wrong file, runs a destructive command, sends data to an unexpected endpoint.

The agent trusts the model. When the model says "call Bash with `rm -rf ./build`," the agent calls Bash with `rm -rf ./build`. The agent doesn't evaluate whether the command is safe, whether it targets the right directory, or whether the model meant `./build` or meant `./`. The agent is a faithful executor.

## What goes wrong without governance

Three things go wrong in practice.

First, the model proposes destructive operations and the agent executes them. File deletions, force-pushes, database modifications, package installations with post-install scripts. The operator trusts the agent because the agent worked correctly for the last 50 operations, and operation 51 deletes their uncommitted work.

Second, the model proposes operations outside the intended scope. The agent is supposed to be editing files in one directory, but the model proposes writing to a configuration file three directories up. Or the model proposes running `curl` to an endpoint the operator didn't expect. Scope drift happens gradually. Each individual tool call looks reasonable. The accumulated trajectory is off-target.

Third, when something does go wrong, there's no record of what happened. The operator knows their files are gone but doesn't know which tool call deleted them, what the model's reasoning was, or what policy would have prevented it. Debugging agent behavior after the fact is guesswork without a decision trail.

## What governance adds

Governance is a layer between the model's proposals and the agent's execution. Every tool call is classified by observable evidence (file paths, command strings, URLs, target patterns) and evaluated against declarative policy rules before the agent can act on it.

An ALLOW decision means the tool call matched a policy rule that permits it. The agent executes normally. A DENY decision means the tool call matched a rule that blocks it, or matched no rule at all (default deny). The agent receives a denial message instead of the tool call and adapts.

Every decision, ALLOW and DENY, is recorded in an append-only, hash-chained, signed log. The chain is the evidence trail. When something goes wrong, you can find the exact decision that permitted it, see the policy rule that matched, and understand whether the policy needs adjustment or the classification needs refinement. When things go right, the chain proves they went right.

## Deterministic verification over judgment

Atested's policy evaluation is deterministic. Given the same tool call and the same policy rules, the evaluator produces the same decision every time. There is no model in the policy path. No AI deciding whether a tool call "seems safe." The classifier extracts evidence from the tool call's parameters. The evaluator matches that evidence against rules. The rules are declarative JSON that the operator writes and can read.

This matters because the alternative is another model evaluating the first model's output, which introduces exactly the kind of unreliability the governance layer is supposed to address. A governance layer that might let a destructive operation through because its own model had a bad day is not governance. It's a prayer.

The tradeoff is that deterministic classification has limits. Some tool calls are opaque: a Bash command that runs a Python script, for example. The classifier can see the command string but not the script's behavior. These operations land at Tier 3 (opaque execution) and default to DENY unless the operator explicitly approves them. The system is honest about what it can and can't classify, and the operator makes the call on the uncertain cases.
