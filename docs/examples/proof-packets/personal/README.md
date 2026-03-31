# Example Proof Packet: Personal (Single User)

This example shows a usage attestation for a single-user installation that
transitioned from trial to personal (free) status after the 30-day trial.

## Scenario

- **User**: One developer using governance-layer locally via Claude Code
- **Trial started**: 2026-03-16
- **Trial expired**: 2026-04-15
- **Status after expiry**: `personal` (single user detected, free tier)
- **Total operations**: 347 governed tool calls over 12 sessions
- **Recommended tier**: `personal`

## Files

| File | Description |
|---|---|
| `attestation.json` | Usage attestation artifact with SHA-256 hash |
| `decision-chain-excerpt.jsonl` | Sample chain entries showing personal status |

## Key observations

1. `license_status` is `personal` — the system detected a single user and
   transitioned automatically after trial expiry.
2. All operations continue to function identically — no lockout.
3. The `recommended_tier` matches the actual tier: `personal`.
4. Every chain record includes the same `user_identity`, confirming single-user.
