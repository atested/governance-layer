## Failure Mode Catalog

Audit date: 2026-04-24  
Repo: `/tmp/governance-layer-audit-20260424-2`  
Commit: `9f98a9ec295d2cdefe88e54be975a1883192ff69`

### Summary Table
| # | Failure mode | Verdict | Current behavior |
|---|---|---|---|
| 1 | Signing key file corrupted on disk (loads but bad signatures) | PARTIAL | Signature validity is enforced by verifiers, but no runtime self-test loop in proxy. |
| 2 | Signing key file permissions change while proxy runs | UNHANDLED | Proxy never re-checks key file permissions post-startup. |
| 3 | Chain file truncated | PARTIAL | MCP detects truncation; proxy append path has no truncation guard. |
| 4 | External record appended to chain | PARTIAL | MCP verify path can quarantine; proxy-only runtime may continue appending on compromised tail. |
| 5 | Chain file deleted while proxy runs | PARTIAL | Proxy recreates file and continues; MCP may later detect via chain meta/truncation checks. |
| 6 | Two proxy instances write same chain | HANDLED | Cross-process lock + read-head-inside-lock append protocol implemented. |
| 7 | System clock jumps backward | PARTIAL | License posture detects clock anomaly; chain timestamp monotonicity is not enforced globally. |
| 8 | Chain grows very large (100K+) | UNHANDLED | Hot paths repeatedly scan full chain; verify-on-operation scales poorly. |
| 9 | Stale lock dir after crash | HANDLED | Lock owner PID check removes stale lock on timeout. |
|10 | Proxy crash mid-stream tool response | UNHANDLED | No transactional recovery for partially emitted stream/decision boundary. |
|11 | Network partition proxy↔provider mid-request | PARTIAL | Request-level error returns 502; no retry/resume strategy. |
|12 | Provider returns malformed JSON | HANDLED | Proxy passes malformed payload through without crashing governance loop. |
|13 | Provider returns truncated streaming response | PARTIAL | Stream ends without explicit integrity/error envelope to client. |
|14 | Provider returns 429/503 | PARTIAL | Status/body passed through; no retry/backoff/circuit-breaker. |
|15 | Agent sends malformed request to proxy | PARTIAL | Some malformed requests are dropped/closed; no consistent structured error contract. |
|16 | Tool call has no matching capability in registry | NOT APPLICABLE | API proxy path does not use capability-registry matching. |
|17 | `GOV_RUNTIME_DIR` becomes unwritable during run | PARTIAL | Chain append errors propagate to request failure (typically 502). |
|18 | Proxy port already in use at startup | UNHANDLED | Startup throws OSError; no friendly preflight or fallback. |
|19 | `policy-rules.json` malformed | UNHANDLED | Lazy policy load can raise and break request path without controlled fallback. |
|20 | `policy-rules.json` deleted while running | PARTIAL | Already-cached policy keeps working; first-load-after-delete fails hard. |
|21 | `capability-registry.json` tampered (hash mismatch) | HANDLED | Integrity verifier fails closed and logs suspicious event. |
|22 | Tool call matches multiple policy rules | HANDLED | Evaluator applies deterministic first-match-wins semantics. |
|23 | Bash uses expansion/pipes/subshell/command chaining | PARTIAL | Pipes/subshell become Tier 3; `&&`/`;` chaining can be misclassified. |
|24 | Stripe webhook delivers license but Cloudflare KV unreachable | PARTIAL | Write failure aborts webhook; relies on Stripe retries, no local compensating flow. |
|25 | License validation fails mid-session (expiry during run) | HANDLED | Posture re-evaluates and falls to unlicensed without halting governance. |
|26 | Notification delivery fails (telemetry endpoint unreachable) | PARTIAL | Submission failure surfaced but no retry queue/backoff policy. |

### Detailed Analysis

#### 1) Signing key file corrupted on disk (loads but invalid signatures) — PARTIAL
- Proxy signs using in-memory key loaded once at startup (`proxy/server.py:79-96`, `143-149`).
- Signature integrity is enforced by verification tools (`scripts/verify-record.py:313-360`, `418-432`).
- Gap: proxy has no periodic self-verification or startup sign/verify probe against active verifier key material.

#### 2) Signing key file permissions change while proxy is running — UNHANDLED
- Proxy does not monitor file permission drift after initial load (`proxy/server.py:79-96`).
- Expected hardening: periodic permission checks or file-watch alarm for trust key assets.

#### 3) Chain file truncated — PARTIAL
- MCP path detects truncation via `chain_meta` length comparison (`mcp/server.py:810-822`) before chain verify (`1064-1066`).
- Proxy append path does not perform truncation detection and can continue from truncated head (`proxy/server.py:165-179`, `153-160`).

#### 4) External record appended by another tool — PARTIAL
- MCP verifies chain with `verify-chain.py` and quarantines on failure (`mcp/server.py:1066-1074`, `1045-1057`).
- Proxy path does not verify chain before append and can continue writing on externally modified chain.

#### 5) Chain deleted while proxy runs — PARTIAL
- Proxy append uses `O_CREAT`, recreating missing chain file (`proxy/server.py:153-156`), with `prev_record_hash=None` if file absent (`165-169`).
- MCP may detect effective truncation later (`mcp/server.py:810-822`), but proxy runtime itself does not.

#### 6) Two proxy instances against same chain — HANDLED
- Cross-process lock protocol is in place (`proxy/server.py:182-227`), with read-head-inside-lock append (`136-143`).
- This aligns with `INV-010` locking invariant intent (`docs/INVARIANTS.md:14`).

#### 7) System clock jumps backward — PARTIAL
- Licensing posture detects backward jump vs last chain timestamp and emits `clock_anomaly` (`mcp/licensing.py:342-351`).
- Chain timestamp monotonicity is not globally enforced in proxy/MCP append paths.

#### 8) Chain grows very large (100K+ records) — UNHANDLED
- Hot paths read full file tails by linear scan (`proxy/server.py:171-176`, `mcp/server.py:828-833`).
- MCP does full verify subprocess on governed operations (`mcp/server.py:1066-1074`), leading to high O(n) overhead.
- No chunked index/checkpoint strategy present.

#### 9) Stale lock file from crashed process — HANDLED
- Both MCP and proxy lock implementations check holder PID and clear stale lock on timeout (`mcp/server.py:871-900`, `proxy/server.py:200-225`).

#### 10) Proxy crash mid-stream during tool response — UNHANDLED
- Streaming decisions are committed only when tool call completes (`proxy/server.py:934-951`).
- If process exits mid-stream, client may get partial SSE output (`848-856`) and no explicit recovery marker.

#### 11) Network partition to upstream provider — PARTIAL
- Request exceptions are caught and surfaced as `502 Bad Gateway` (`proxy/server.py:1446-1455`).
- No retry/jitter/backoff or resumable streaming strategy.

#### 12) Provider returns malformed JSON — HANDLED
- Non-streaming: invalid JSON is passed through as raw upstream body (`proxy/server.py:993-997`, `1059-1063`).
- Streaming: non-JSON data frames are forwarded as-is (`proxy/server.py:921-927`, `1229-1235`).

#### 13) Provider returns truncated streaming response — PARTIAL
- Stream loops end when upstream ends; no explicit incomplete-stream error is synthesized (`proxy/server.py:900-975`, `1211-1269`).
- Client can receive partial output without final completion semantics.

#### 14) Upstream 429 / 503 — PARTIAL
- Streaming and buffered paths pass through non-200 responses (`proxy/server.py:875-887`, `1116-1118`, `1206-1208`).
- No retry policy or provider-level overload handling.

#### 15) Malformed request from agent (bad JSON/missing fields) — PARTIAL
- Invalid request line (<3 parts) is dropped by closing socket (`proxy/server.py:1307-1310`).
- Invalid body JSON for streaming detection logs warning and falls back (`1417-1421`), then forwards upstream.
- No uniform structured local error envelope across malformed request classes.

#### 16) Tool call with no matching capability in registry — NOT APPLICABLE
- API proxy mediation uses classifier + policy evaluator, not capability-registry lookup (`proxy/server.py:339-347`).
- Registry tamper checks are MCP governed-tool concerns, not proxy tool-call mediation.

#### 17) `GOV_RUNTIME_DIR` unwritable during run — PARTIAL
- Chain append writes can throw (`proxy/server.py:153-160`) and propagate to request error handling (`1446-1455`).
- Behavior is fail-closed per request but lacks dedicated runtime-health degradation signaling.

#### 18) Proxy port already in use at startup — UNHANDLED
- Startup calls `asyncio.start_server()` directly (`proxy/server.py:1466-1468`) with no user-friendly intercept/fallback.

#### 19) `policy-rules.json` malformed — UNHANDLED
- Policy loader raises on malformed structure (`scripts/policy_eval_v2.py:45-52`).
- `_v2_policy()` lazy-load has no protective wrapper (`mcp/server.py:114-121`); request path can fail without controlled error class.

#### 20) `policy-rules.json` deleted while running — PARTIAL
- If already cached, MCP continues using `_V2_POLICY_RULES` (`mcp/server.py:110-121`).
- If first load occurs after deletion, request path faults (same load failure behavior as #19).

#### 21) `capability-registry.json` tampered — HANDLED
- Integrity verifier detects hash mismatch and fails closed with explicit error (`mcp/registry_integrity.py:308-347`).
- `governed_tool()` and `_cap_registry()` call `verify_or_fail()` before operation (`mcp/server.py:529-533`, `1095-1100`).

#### 22) Multiple policy rules match one tool call — HANDLED
- Evaluator loops rules in file order and exits on first match (`scripts/policy_eval_v2.py:251-257`).
- Behavior is deterministic and explicit.

#### 23) Bash command complexity (expansion/pipes/subshell/chaining) — PARTIAL
- Pipes/subshell are classified Tier 3 (`scripts/classifier.py:236-239`, `311-319`).
- Parser is first-command oriented (`scripts/classifier.py:204-212`) and can mis-handle chained semantics.
- Empirical repro (executed during audit): `git status && rm /tmp/x` classified as Tier-2 read and policy-`ALLOW` (`execute-tier2-allow`) instead of guaranteed deny/escalation.

#### 24) Stripe webhook license delivery while KV unreachable — PARTIAL
- Webhook writes multiple KV records for checkout completion (`license-worker.js:597-618`, `620-632`, `634-651`) without local compensating write queue.
- Failure returns non-2xx to Stripe; eventual recovery depends on Stripe retry behavior.

#### 25) License validation fails mid-session (expires during run) — HANDLED
- Posture resolution enforces expiry transitions on read (`mcp/licensing.py:371-377`).
- Governance path remains active by design (evidentiary licensing, not execution lockout).

#### 26) Notification delivery fails (telemetry endpoint unreachable) — PARTIAL
- Remote send failure is surfaced (`mcp/feedback_signing.py:276-305`), and caller returns error context (`dashboard/server.py:1009-1014`).
- No durable retry queue or backoff orchestration exists.

### Prioritized Conditions To Fix Before Release

#### Must-fix before release
1. Implement real renewal engine (plus auto-renew and Crew+ decision paths), not metadata-only toggles.
2. Eliminate classifier chain-command blind spot (`&&`/`;`) that can permit destructive tails under benign-leading commands.
3. Add controlled startup/request handling for malformed/missing policy rules with explicit fail-closed diagnostics.
4. Add robust chain integrity controls to proxy runtime (pre-append verify/truncation checks, or verified append checkpoints).

#### Should-fix before release
1. Replace full-file chain scans with indexed/checkpointed head and incremental verification for large-chain performance.
2. Standardize malformed request responses (structured 4xx) instead of silent close for parse failures.
3. Add retry/backoff or queueing for telemetry/notification delivery failures.
4. Harden webhook write-path resilience for KV outages (idempotent replay queue or explicit dead-letter handling).

#### Nice-to-have hardening
1. Add runtime key-file health checks (permissions drift, key mismatch probes).
2. Add friendly startup handling for port collisions with clear remediation hints.
