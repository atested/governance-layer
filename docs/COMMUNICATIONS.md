# Communications

The Communications window provides a governed channel for priority support
requests. Slot allocation is tier-based and request submission is recorded in
the governance chain.

## Slot Allocation

Each tier includes a monthly allocation of priority request slots.

| Tier | Medium Priority | High Priority |
|---|---|---|
| Personal | 0 | 0 |
| Personal Plus | 2 | 0 |
| Crew | 4 | 2 |
| Team | 8 | 4 |
| Institution | 16 | 8 |

Slots reset each billing period. Unused slots do not carry over.

## Request Priority Levels

**Medium priority**: General operational questions, configuration guidance,
non-blocking issues. Feedback-system response.

**High priority**: Time-sensitive operational issues, potential security
concerns, blocking problems. Direct attention with SLA-backed response for
Team and above. Institution tier includes named support routing.

## Request Status States

After submission, requests progress through these states:

- **Submitted**: Request recorded in chain and sent to Atested support
- **Acknowledged**: Atested confirms receipt (delivered via telemetry response)
- **In Progress**: Work underway on the request
- **Resolved**: Response provided or issue addressed

Status updates arrive through the telemetry notification channel. Each status
change is recorded as a `notification_received` event in the chain.

## Multi-Machine Relay

In a multi-machine install, only the primary talks to Atested servers. The
primary receives Communications messages and stores them with stable message
IDs. Remotes receive pending messages during sync and deduplicate by message
ID.

Remote dashboards show relayed messages locally, but remotes do not contact
Atested servers for Communications. If a remote is offline, it receives pending
messages the next time sync succeeds.

## Submitting a Request

1. Open the Communications window.
2. Select priority level (medium or high).
3. Write the request description.
4. Submit. The dashboard:
   - Records a `communications_request_submitted` event in the chain
   - Sends the request to Atested support infrastructure
   - Decrements the slot count for the selected priority level

## Chain Events

| Action | Event Type |
|---|---|
| Request submitted | `communications_request_submitted` |
| Status update received | `notification_received` |
