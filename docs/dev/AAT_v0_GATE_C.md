# AAT v0 Gate C

## Purpose
Gate C is an operational wrapper that composes:
1. Gate A admissibility validation (`system/scripts/aat-admissibility-gate.sh`)
2. Gate B ledger append integration (`system/scripts/aat-gate-b-append.sh`)

Gate C introduces no new validation logic. It standardizes one operator output contract.

## Command
```bash
system/scripts/aat-gate-c-wrapper.sh \
  --action-record <path/to/action_record.json> \
  --decision-record <path/to/decision_record.json> \
  --ledger <path/to/ledger.jsonl>
```

## Stable output contract
- `STATUS=PASS|NON_ADMISSIBLE|HARD_STOP`
- `REASON_CODE=<code>`
- `LEDGER_APPENDED=YES|NO`

Exit codes:
- `0` -> PASS
- `10` -> NON_ADMISSIBLE
- `20` -> HARD_STOP

## Composition semantics
- Gate A runs first using the action record directory as the action bundle.
- If Gate A returns hard stop, Gate C exits hard stop and does not append to ledger.
- Otherwise Gate B runs and appends deterministic action/decision events.
- Final Gate C status is mapped from Gate B output.
