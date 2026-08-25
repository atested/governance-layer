# Reach-Lite Operator Application — WP-RL-008 spike

## What was built

One directly runnable operator application behind the five-destination
dashboard: `reach_lite/operator_app.py`, started with a single activation
operation:

    python3 -m reach_lite.operator_app --port 9700

## Design decisions (spike write-up)

- **Framework: Python standard library `http.server` (ThreadingHTTPServer).**
  Zero new dependencies: `requirements.txt` and `requirements-dev.txt` stay
  untouched, the prepared self-host environment needs nothing beyond
  `python3`. A third-party web framework would add install, pinning, and
  sandbox-egress surface for no scope benefit.
- **Single module, `python3 -m` packaging.** The app is one importable module
  so the declared activation operation is exactly one process start from the
  repo root. `run-operator-ui.sh` already documents port 9700; the module
  matches it as the default (`--port` override, `OPERATOR_UI_PORT` env
  fallback).
- **Transport: HTTP/1.1, HTML views + JSON API on one port.** One browser
  entry point (`/`) renders the five-destination nav (Chat, Agents,
  Approvals, Results, Settings); each `/api/<destination>` returns the same
  state the view renders, so navigation evidence is machine-checkable.
- **One supervised foreground process with a readiness contract.**
  `GET /api/health` returns `{"status":"ok","app","entry_point":"/",
  "destinations":[...]}`; readiness is polled until that 200, making the
  "one activation starts one application" claim directly verifiable.
- **State: in-memory seed from the domain package.** `seed_state()` builds
  agents, a reconciled run, opportunities, pending drafts, a connection, and
  a person from `reach_lite.domain` factories — no storage service. All
  mutations (agent transitions, approval actions) go through the accepted
  domain functions (`transition_agent`, `apply_approval_action`, ...), so
  the app cannot drift from WP-RL-001…007 semantics.
- **Scope guard.** Settings exposes only current-scope capabilities;
  deferred capabilities are listed disabled; no prohibited operator controls,
  pipeline stage names, analyst control-room surfaces, or attestation
  capabilities are exposed anywhere in the rendered surfaces.

## Validator

`reach_lite/operator_validator.py` implements
`RunnableOperatorApplicationValidator` (VALCAT v1.1 / REQ-ATL-036): it
validates the delivered target inventory, prepared self-host environment,
declared activation operation, running-process evidence, and browser-rendered
navigation, with finding classes non-runnable-target, fragmented-surface,
missing-destination, component-only. `build_live_inventory()` collects that
evidence over live HTTP. It is deliberately kept out of the pinned
43/44 catalog structures and `reach_lite/__init__.py` re-exports: it is a
target-level validator, not a fixture-level one.

## Tests

`tests/reach_lite/test_wp_rl_008.py` starts the application as a real
subprocess on a free port (prepared self-host environment), drives every
destination over HTTP, and runs the validator against the live target;
negative tests cover each finding class.
