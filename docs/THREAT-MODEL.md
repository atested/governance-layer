# Threat Model (v0.1)
Updated: 2026-04-04

> **v3 note:** Atested now operates as an API governance proxy that intercepts
> tool calls at the HTTP transport layer, eliminating the "native tool bypass"
> threat from v1/v2. The threat model below is updated to reflect this.
> See [docs/design/atested-v3-design.md](design/atested-v3-design.md).

## Assets to protect
1. Integrity of privileged actions (no unauthorized execution).
2. Integrity of decision records (no forgery, no deletion, no edits).
3. Integrity of logs (append-only, tamper-evident).
4. Integrity of policy evaluation (deterministic, reproducible).
5. Integrity of tool capability registry (no stealth privilege expansion).

## Adversary capabilities (assume)
1. Prompt injection attempts through untrusted text.
2. Parameter smuggling / schema confusion.
3. Tool name spoofing or aliasing.
4. Confused deputy attacks (broker tricked into doing more than intended).
5. Attempted direct tool invocation outside broker (integration boundary).
6. Attempted log tampering (edit, truncate, reorder).
7. Attempted key misuse (use wrong key, replace key, bypass signing).

## In-scope attacks
1. Any bypass of the tool chokepoint within the broker’s control.
2. Any attempt to produce a privileged action without a decision record.
3. Any attempt to forge a decision record or tamper with logs.
4. Any attempt to exploit nondeterminism to hide policy outcomes.

## Out-of-scope (explicit for now)
1. Kernel-level compromise / full host takeover.
2. Attacks occurring entirely outside the broker boundary (unless boundary is expanded).
3. Side-channel exfiltration not mediated by governed tools.

## Security invariants (must always hold)
See `INVARIANTS.md`.
