# What Atested can and can't do

Atested makes specific claims about what it verifies and records. This page states those claims precisely, including their limits.

## What's deterministically verified

Tier 1 classifications are deterministic. The tool call specifies a file path, and the classifier reads the path. The policy evaluator checks whether the path is within allowed directories, whether it targets a hidden file, whether the action type is permitted. The decision (ALLOW or DENY) follows from the evidence and the rules with no ambiguity. Two operators running the same tool call against the same policy get the same answer.

Tier 2 classifications are high-confidence inferences from known patterns. When the agent runs `git push origin main`, the classifier recognizes `git push` as a network-scope execute operation. This inference is reliable for well-known commands (git, curl, npm, pip, docker, make, pytest, and about 40 others in the classifier). The accuracy depends on the command being what it looks like. An adversarial binary named `git` that does something else would be classified as the real `git`. In practice this doesn't happen in normal agent operation, but it's a theoretical gap.

## What's uncertain

Tier 3 operations are opaque. The classifier sees the entry point (a script path, an interpreter invocation, a piped command) but not the behavior. Running `python3 deploy.py` produces a Tier 3 classification: the classifier knows it's executing Python but doesn't know what the script does. These operations default to DENY in the standard policy. The operator can approve specific Tier 3 operations after reviewing what they do.

Tier 4 operations are uninspectable. The parameters contain encoded content (base64, hex blobs, or obfuscated arguments) that the classifier can't parse. These are flat DENY in the standard policy with no approval override.

The gap between "classified" and "understood" is real. Atested tells you which tier each operation landed in. The tier is the honest statement of how much the classifier knows.

## What the chain proves

The chain proves that a specific tool call was proposed by the model, classified at a specific tier, evaluated against a specific policy rule, and resulted in a specific decision (ALLOW or DENY) at a specific time. The record includes the classification evidence, the matched rule, and the reason code.

If the chain has Ed25519 signatures, it also proves the records were written by a machine holding the signing key. The verifier checks every hash and every signature. If the chain verifies, the records haven't been tampered with since they were written.

## What the chain doesn't prove

The chain doesn't prove what actually happened during execution. If Atested allows a `Bash("npm install")` and npm's post-install script does something unexpected, the chain records the ALLOW decision for `npm install`. It doesn't know what npm did afterward.

The chain doesn't prove who was operating the machine. Signatures prove the machine, not the human. Operator identity (binding approvals to authenticated humans via TOTP) is a separate layer described in the operator identity design. Until that ships, the chain attributes actions to machine identity.

The chain doesn't protect against a compromised proxy. If an attacker has code execution on the machine running Atested, they could modify the proxy to write false records with valid signatures. The chain's integrity guarantee assumes the proxy is honest. This is the boundary of what software-only governance can claim.

## What telemetry collects and excludes

Atested's telemetry is opt-in. When enabled, it sends aggregated counts: total ALLOW decisions, total DENY decisions, deterministic vs. judgment-tier counts. No file paths, no command strings, no conversation content, no user identities. The telemetry payload is a small JSON object with numbers, signed by the same Ed25519 key that signs the chain.

The aggregation happens on the operator's machine. The counts are computed from the local chain. The aggregation code is in the repository, readable, auditable. But the aggregation layer is trusted code, not cryptographically enforced. The chain is verifiable; the aggregation is not. If the aggregation code had a bug that miscounted, the telemetry would report wrong numbers while the chain remained correct.

## What the proxy can and can't see

The proxy sees API traffic between the agent and the model provider. It can read tool call proposals in model responses and classify them. It cannot see what the agent does with the response locally. If the agent receives an ALLOW decision and then modifies the tool call before executing it, the proxy doesn't know. In practice, agent runtimes execute tool calls as received, but the boundary is worth stating.

The proxy does not see the agent's internal state, local file operations that bypass the model, or interactions between the agent and other local processes. Governance covers the model-to-agent communication channel. Direct local-tool governance requires a pre-execution integration.
