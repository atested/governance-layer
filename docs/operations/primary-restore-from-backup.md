# Primary Restore From Backup

Status: v1 supported recovery path
Scope: Multi-machine governance primary restoration

Full remote promotion is deferred in v1. The supported v1 recovery path is to
restore the primary `gov_runtime` from backup onto a replacement primary.

## Required Backup Contents

The backup must include these `gov_runtime` contents:

- `LOGS/decision-chain.jsonl`
- `machines/registry.json`
- `.atested-signing-key.pem`
- `imports/` when remote material has been imported
- `LOGS/archives/` and archive manifests when chain archiving has run
- `LOGS/telemetry/` for primary and aggregated telemetry continuity
- `LOGS/update_notifications.jsonl` and Communications logs
- approval state derivable from the chain, plus any approval snapshots under `approvals/`
- license proof or cache files used by the installation

The replacement install must also have the matching product policy files,
especially `capabilities/policy-rules.json`.

## Restore Procedure

1. Install the same or newer Atested version on the replacement primary.
2. Stop Atested services on the replacement machine.
3. Restore the backed-up `gov_runtime` directory.
4. Preserve file permissions on `.atested-signing-key.pem`; it should be
   readable only by the operator account.
5. Run restore validation:

```bash
./atested restore verify --runtime /path/to/gov_runtime
```

6. Resolve any failed required checks before starting services.
7. Start the primary:

```bash
GOV_RUNTIME_DIR=/path/to/gov_runtime ./atested start --role primary
```

8. Remotes reconnect using the restored primary identity and registry.

If the primary signing key was not restored, remotes must be explicitly
re-paired. A changed primary key is treated as a new trust relationship.

## Verification Command

`atested restore verify` checks:

- required runtime files exist
- machine registry hash verifies
- governance chain integrity verifies
- optional restore components are present or reported absent

The command exits `0` only when the restored runtime is usable as a primary.
