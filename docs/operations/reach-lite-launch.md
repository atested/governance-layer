# Reach Lite Operator Application — Durable Launch Instructions

Authoritative, reproducible launch instructions for the self-hosted Reach Lite
operator application. A reviewer can follow this document end to end without
undocumented knowledge: every command and referenced file resolves inside this
delivery.

The authoritative activation profile that these instructions drive is the JSON
document at `reach_lite/activation_profile.json` (schema SCH-ATL-009). The
application module it launches is `reach_lite/operator_app.py`.

## Prerequisites

- Python 3.9 or newer is available on the host as `python3`.
- No third-party Python packages are required: the operator application is built
  on the Python standard library only (it uses `http.server`, so no network
  dependency installation is needed).
- No credentials, tokens, or external services are required. The application is
  self-hosted and binds to the loopback interface only.
- The host can open a TCP listener on the configured port (default 9700).

## Configuration

The operator application is configured by the profile in
`reach_lite/activation_profile.json` and by one optional input:

- `OPERATOR_UI_PORT` — the TCP port the application binds. It defaults to
  9700. It can be set in two equivalent ways:
  - the `--port` command-line argument, or
  - the `OPERATOR_UI_PORT` environment variable.
- The bind host is fixed to the loopback address `127.0.0.1` (not configurable
  to a non-loopback host by the operator application).

There are no secrets to configure. If a deployment later needs one, it must be
declared in the profile's `configuration_inputs` as a secret referenced by name
(never embedded as a value).

## Activation

Launch the operator application from the repository root (the resolved working
context) using the authoritative activation operation:

```
python3 -m reach_lite.operator_app --port 9700
```

The process runs in the foreground and serves the operator surface until it is
stopped. For background operation, run it under a supervisor or shell and record
the PID for the cleanup step below.

## Browser URL

Once active, open the operator surface in a browser at the absolute URL resolved
from the profile:

- Scheme: `http`
- Host: `127.0.0.1`
- Port: the configured port (default 9700)
- Path: `/`

So the default browser URL is `http://127.0.0.1:9700/`. The surface exposes the
five operator destinations (chat, agents, approvals, results, settings) behind
that root.

## Readiness

The application is ready when the readiness signal returns successfully:

- Request: `GET /api/health`
- Expected result: HTTP status `200` and a JSON body whose `app` field equals
  `reach-lite-operator`.
- Wait up to `20` seconds for this signal. Polling the endpoint until it returns
  200 is the readiness check; the operator surface is considered active only
  after the signal succeeds.

## Cleanup

To stop the application and release the port:

1. Send `SIGTERM` to the operator application process (e.g. `kill <PID>`).
2. Wait up to 5 seconds for it to exit.
3. If it has not exited, send `SIGKILL` (e.g. `kill -9 <PID>`).

The application holds no persistent state and starts no external services, so
no database, cache, or service teardown is required after the process exits.

## Failure Behavior

Observable, deterministic failure behavior when the activation does not succeed:

- If the port is already in use, the process fails to bind and exits non-zero
  with a bind error on stderr; the readiness signal never returns 200.
- If `GET /api/health` does not return 200 within the 20-second readiness
  window, treat the launch as failed: do not open the browser URL, stop the
  process via the Cleanup step, and report the failure rather than claiming the
  surface is active.
- The readiness endpoint is the single source of truth for liveness; a missing
  or non-200 readiness response means the operator surface is NOT available.
