# Example Proof Packet: Team (5 Users, Licensed)

This example shows a usage attestation for a team of 5 developers with an
active team license.

## Scenario

- **Organization**: acme-engineering
- **Users**: 5 developers sharing a governed HTTP deployment
- **License activated**: 2026-05-01 (during trial period)
- **License key tier**: `team`
- **License expiry**: 2027-06-01
- **Total operations**: 2,104 governed tool calls over 83 sessions
- **Recommended tier**: `team`

## Files

| File | Description |
|---|---|
| `attestation.json` | Usage attestation artifact with SHA-256 hash |
| `decision-chain-excerpt.jsonl` | Sample chain entries showing team license |

## Key observations

1. `license_status` is `licensed` with tier `team` — activated before trial expiry.
2. `organization_id` is set to `acme-engineering` (provided at activation).
3. Five distinct `user_identity` values appear across chain records (bearer tokens).
4. The `recommended_tier` matches the actual tier: `team` (2-10 users).
5. Operations span filesystem and messaging categories, all governed.
