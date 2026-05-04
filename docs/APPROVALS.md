# Approvals Workflow

Approvals let operators explicitly authorize specific artifacts (identified by
SHA-256 hash) so that otherwise-denied operations can proceed. The approval
store is derived entirely from chain events.

## Adding an Approval

1. Navigate to the Approvals window in the dashboard.
2. Click "Add Approval."
3. Enter the artifact identity (the SHA-256 hash of the artifact you want to authorize).
4. Enter the operator name (who is granting the approval).
5. Submit. The dashboard records an `opaque_artifact_approval` event in the chain.

The proxy reads the approval store on every request. If a tool call would
otherwise be denied but the target artifact has an active approval, the proxy
allows it.

## Revoking an Approval

1. Navigate to the Approvals window.
2. Find the active approval you want to revoke.
3. Click "Revoke."
4. Confirm. The dashboard records an `opaque_artifact_revocation` event.

Once revoked, subsequent operations against that artifact are subject to normal
policy evaluation again.

## Staleness Detection

Approvals age. The dashboard marks approvals as stale based on time elapsed
since they were granted. Stale approvals are still active (they still allow
operations) but the staleness indicator alerts operators that the approval may
warrant review.

Staleness does not automatically revoke an approval. It is a visual signal.
The operator decides whether to leave it active or revoke it.

## Opaque Actions and Approvals

Atested classifies high-confidence operations (Tier 3 and above) as opaque
actions. These are operations where the classifier has high confidence that
the action affects files or resources beyond the immediate tool call.

The Audit Evidence Export report pairs opaque actions with their approval
status:

- If an opaque action was allowed and a matching approval exists, it is marked
  as "Approved" with the operator name and date.
- If an opaque action was denied, it is marked as "Denied" with a note that no
  approval covered it.
- If an opaque action was allowed but no matching approval exists, it is marked
  as an anomaly. This does not necessarily indicate a problem (the action may
  have been allowed by policy without needing an approval) but it warrants
  investigation in audit contexts.

## Chain Events

| Action | Event Type |
|---|---|
| Grant approval | `opaque_artifact_approval` |
| Revoke approval | `opaque_artifact_revocation` |
| Opaque action evaluated | `opaque_invocation_decision` |

All events are signed if the proxy has a signing key loaded.
