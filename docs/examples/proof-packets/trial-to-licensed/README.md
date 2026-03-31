# Example Proof Packet: Trial-to-Licensed Transition

This example shows the governance trail of a team that started with a trial,
then activated a team license mid-trial.

## Scenario

- **Organization**: startup-co
- **Users**: 3 developers
- **Trial started**: 2026-03-11
- **License activated**: 2026-04-05 (day 25 of trial, before expiry)
- **License key tier**: `team`
- **License expiry**: 2027-04-20
- **Total operations**: 512 governed tool calls over 28 sessions
- **Recommended tier**: `team`

## Files

| File | Description |
|---|---|
| `attestation.json` | Usage attestation artifact with SHA-256 hash |
| `decision-chain-excerpt.jsonl` | Sample chain entries showing trial → licensed transition |

## Key observations

1. Early chain records show `license_status: trial` — the default for new installations.
2. After activation on 2026-04-05, all subsequent records show `license_status: licensed`.
3. The chain itself is the evidence of the transition — no external audit log needed.
4. `organization_id` appears only after activation (set to `startup-co`).
5. The governance layer continued operating identically through the transition.
