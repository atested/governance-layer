# Licensing Model

The governance layer includes licensing posture as evidentiary metadata in every
governance record.  Licensing does **not** gate functionality — a governed action
that would be ALLOW remains ALLOW regardless of license status.  Licensing records
the truth about the operator's status.

---

## License statuses

| Status | Meaning |
|---|---|
| `trial` | First 30 days after initial deployment.  Full functionality. |
| `licensed` | A valid license key has been activated. |
| `unlicensed` | Trial expired without activation.  Full functionality continues — records state the truth. |
| `personal` | Single-user installation after trial expiry.  Free tier, no license required. |

## License tiers

| Tier | Intended use |
|---|---|
| `personal` | Individual use, single operator |
| `team` | Small team (2–10 operators) |
| `business` | Organization-wide deployment |
| `enterprise` | Custom terms, SLA, support |

## How it works

### First governed operation

On the first governed tool call, if no `license.json` exists in the runtime
directory, the system creates one:

```json
{
  "license_status": "trial",
  "license_tier": "personal",
  "organization_id": "",
  "license_expiry": "2026-04-29T00:00:00Z",
  "trial_started": "2026-03-30T12:00:00Z",
  "license_key": ""
}
```

The trial runs for 30 days from this moment.

### During the trial

Every governance record includes these additive fields:

```json
{
  "license_status": "trial",
  "license_tier": "personal",
  "organization_id": "",
  "license_expiry": "2026-04-29T00:00:00Z"
}
```

These fields are in the sidecar record and API response.  They do not affect
policy evaluation — ALLOW/DENY decisions are unchanged.

### After trial expiry

If no license key has been activated:

- **Single user detected** (user identity tracking shows <= 1 unique user):
  transitions to `personal` status.  Free indefinitely.
- **Multiple users detected**: transitions to `unlicensed` status.
  Full functionality continues.  Records state the truth.

### After license activation

Call the `license_activate` tool with a valid key:

```
Tool: license_activate
Arguments: { "license_key": "<Ed25519-signed-v2-token>", "organization_id": "acme-corp" }
```

All subsequent governance records show `license_status: licensed` with the
activated tier and organization.

## Governance record fields

Every governance record (action and non-action) includes:

| Field | Type | Description |
|---|---|---|
| `license_status` | string | Current status: trial, licensed, unlicensed, personal |
| `license_tier` | string | Current tier: personal, team, business, enterprise |
| `organization_id` | string | Organization identifier (set at activation) |
| `license_expiry` | string | ISO 8601 expiry date of the license or trial |

## Governed tools

| Tool | Purpose |
|---|---|
| `license_status` | Report current licensing state, trial days remaining, unique users |
| `license_activate` | Accept a license key and update license configuration |

## License key format

### v2 tokens (current)

License tokens are Ed25519-signed JSON payloads. The signing private key is
held by the license issuer and is **not** shipped with the client code. The
client embeds only the public verification key.

Token format: `base64url(JSON-payload).base64url(Ed25519-signature)`

Payload fields: `{"tier": "team", "exp": "20271231", "org": "acme", "v": 2}`

### v1 keys (legacy, deprecated)

Keys follow the pattern: `GOV-<tier>-<expiry-YYYYMMDD>-<check8>`

Example: `GOV-team-20271231-a1b2c3d4`

The check suffix is a SHA-256 prefix derived from the tier and expiry.
v1 keys are accepted for backward compatibility but new activations should
use v2 tokens.

## Configuration file

License state is persisted in `$GOV_RUNTIME_DIR/license.json`.
This file is created automatically on first operation and updated
on activation.  It is gitignored (inside the runtime directory).

## Multi-user identity limitation (bearer mode)

In HTTP deployments using bearer token authentication, user identity is derived
from a SHA-256 prefix of the token. All clients sharing the same bearer token
are counted as one unique user. This affects:

- **Unique user counts** — will under-count if multiple people share a token.
- **Trial-to-personal transition** — checks unique users ≤ 1; may incorrectly
  trigger for multi-user deployments sharing a single token.

For accurate per-user tracking, issue distinct bearer tokens per user or use
OIDC mode.

## Design principles

1. **No lockout**: Licensing never prevents governance from functioning.
2. **Truth-telling**: Records state what the license status actually is.
3. **Additive only**: Licensing fields are new metadata — existing record
   schema is unchanged.
4. **Evidentiary enforcement**: The governance chain itself is evidence of
   usage.  A downstream auditor can read license_status from any record.
