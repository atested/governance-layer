## License Lifecycle Scenario Verification

Audit date: 2026-04-24  
Repo: `/tmp/governance-layer-audit-20260424-2`  
Commit: `9f98a9ec295d2cdefe88e54be975a1883192ff69`

Design/invariant references:
- `state/atested/licensing-app-design-capture-v3.md`
- `state/atested/product-design/tier-structure.md`
- `state/atested/product-design/license-signal-system.md`
- `state/atested/product-design/customer-relationship-model.md`
- `docs/INVARIANTS.md`
- `docs/design/atested-v3-design.md`

### Summary Table
| # | Scenario | Verdict | Key finding |
|---|---|---|---|
| 1 | New install → trial | VERIFIED | Trial auto-initializes with 30-day expiry. |
| 2 | Trial → Personal | DEFECT | Transition is local mock write, not server-issued signed Personal license. |
| 3 | Personal → Personal Plus | DEFECT | Uses mock purchase ref + local write; no Stripe/licensing-server transaction. |
| 4 | Personal Plus → Crew | DEFECT | Same local mock purchase path. |
| 5 | Crew → Team | DEFECT | Same local mock purchase path. |
| 6 | Team → Institution | DEFECT | Institution inquiry path throws (`unknown non-action event_type`) and never transitions tier. |
| 7 | Institution → Team | DEFECT | Downgrade is only scheduled (`pending_downgrade`), never applied. |
| 8 | Team → Crew | DEFECT | Same as #7. |
| 9 | Crew → Personal Plus | DEFECT | Same as #7. |
|10 | Personal Plus → Personal | DEFECT | Same as #7. |
|11 | License purchase full flow (Stripe→webhook→delivery→local activation) | GAP | Website flow exists, but product purchase flow is not wired to it. |
|12 | Renewal — Personal Plus auto-renew | DEFECT | No renewal mutation pipeline; webhook invoice events only archived. |
|13 | Renewal — Crew+ active decision | DEFECT | No implemented renewal decision/processing path. |
|14 | License expiry runtime behavior | DEFECT | Status fallback works, but operator expiry warning pipeline is broken (`chain_health` license probe). |
|15 | License revocation explicit | UNTESTABLE | End-to-end depends on Cloudflare telemetry path; local processing path exists. |
|16 | First machine activation | DEFECT | Missing fingerprint regenerates from license-key hash, not per-machine random identity. |
|17 | Second machine activation same license | DEFECT | Sharing path exists, but direct key activation bypasses machine-count controls. |
|18 | Revoke first machine; second continues | VERIFIED | Sharing revoke targets one fingerprint; other active fingerprints remain. |
|19 | Max machine limit reached | DEFECT | Enforced only in sharing flow; bypassable through direct key activation path. |
|20 | Lost license key recovery | GAP | Recovery endpoint exists in website worker, but no product integration flow. |
|21 | Corrupted `license.json` | VERIFIED | Fails closed to unlicensed/error without stopping governance runtime. |
|22 | Missing `install_fingerprint` | DEFECT | Regeneration path can collapse multiple installs to same fingerprint. |
|23 | Trial experience (access/restrictions) | VERIFIED | Trial mode remains fully governed with no execution lockout. |
|24 | Trial completion trigger | VERIFIED | Implemented trigger is explicit (`ALLOW>=1`, `DENY>=1`, `categories>=3`, `decisions>=20`). |
|25 | Trial → purchase decision (case doc + recommendation) | VERIFIED | Case-document assembly and deterministic recommendation are implemented. |

### Detailed Trace

#### 1) New install → trial (no license key)
- Code path: `resolve_posture()` auto-creates trial when no `license.json` exists (`mcp/licensing.py:311-335`), using `initialize_trial()` (`mcp/licensing.py:266-280`).
- Decision-chain records: no standalone license event at creation; subsequent governed records carry posture in MCP path (`mcp/server.py:1218-1223`, `1327-1331`). Proxy records stay signed trust-grade when key is present (`proxy/server.py:143-149`, `1518-1527`).
- State changes:
  - `license.json` created with `license_status=trial`, `license_tier=personal`, `license_expiry` (+30 days), blank key (`mcp/licensing.py:270-278`).
  - No KV changes in product repo path.
  - No install fingerprint yet.
- Design alignment: matches trial default and “governance continues fully” posture (`licensing-app-design-capture-v3.md:125,148-155`).

#### 2) Trial → Personal (free tier activation)
- Code path: dashboard registration handler (`dashboard/server.py:1770-1887`) writes local file + chain event.
- Decision-chain records: `license_registered` (+ optional telemetry/research opt-in events) via `build_non_action_event` (`dashboard/server.py:1843-1876`), unsigned non-action events (record-hash only).
- State changes:
  - `license.json` updated with `license_status=personal`, `registered=true`, operator metadata, 1-year expiry (`dashboard/server.py:1821-1835`).
  - No install fingerprint mutation.
  - No website KV/Stripe interaction.
- Design mismatch:
  - Design requires Personal registration to receive a real signed license from licensing server (`licensing-app-design-capture-v3.md:194-195`, `521-522`).
  - Implementation is local mock write only.
- Verdict rationale: code path exists but violates intended cryptographic issuance flow.

#### 3) Personal → Personal Plus ($99/yr)
- Code path:
  - UI purchase uses mock licensing API (`dashboard/ui-next/windows/licensing.js:1934-1948`, `dashboard/ui-next/licensing-api.js:100-106`).
  - Local purchase endpoint writes file/events (`dashboard/server.py:1896-2093`).
- Decision-chain records: `license_purchased` or `license_upgraded` (`dashboard/server.py:2042-2068`), unsigned non-action event.
- State changes:
  - `license.json` set to `license_status=licensed`, `license_tier=personal_plus`, term dates, `auto_renewal=true` (`dashboard/server.py:1992-2005`).
  - No Stripe checkout/webhook in product flow.
- Design mismatch: intended Stripe-backed licensing-server transaction (`licensing-app-design-capture-v3.md:62`, `204-207`).

#### 4) Personal Plus → Crew
- Code path: same purchase path as #3 with `tier=crew` (`dashboard/server.py:1914-1937`).
- Decision-chain records: usually `license_upgraded` when prior tier is licensed and lower (`dashboard/server.py:1984-1990`, `2042-2054`).
- State changes: `license_tier=crew`, recalculated term (`dashboard/server.py:1954-1969`, `1992-1999`).
- Design mismatch: same mock/local transaction gap as #3.

#### 5) Crew → Team
- Code path: same purchase path as #4 with `tier=team`.
- Decision-chain records: `license_upgraded` (`dashboard/server.py:2042-2054`).
- State changes: `license_tier=team`, term recalculated (`dashboard/server.py:1954-1969`, `1992-1999`).
- Design mismatch: still bypasses licensing server + Stripe flow.

#### 6) Team → Institution (negotiated)
- Code path: institution inquiry endpoint (`dashboard/server.py:2116-2187`).
- Decision-chain records: intended `institution_inquiry_submitted` event (`dashboard/server.py:2166-2171`).
- Observed defect:
  - `institution_inquiry_submitted` is not an allowed non-action type (`scripts/event_model.py:37-71`), so `build_non_action_event` raises.
  - Repro confirms `ValueError: unknown non-action event_type: institution_inquiry_submitted`.
- State changes: no tier/license transition is implemented here even if event succeeded.
- Design mismatch: Institution should be handoff path, but current implementation fails before even recording inquiry (`licensing-app-design-capture-v3.md:208`, `486-487`).

#### 7) Institution → Team
- Code path: downgrade endpoint (`dashboard/server.py:2646-2726`).
- Decision-chain records: `license_downgraded` (`dashboard/server.py:2706-2715`).
- State changes:
  - Writes `pending_downgrade` in `license.json` only (`dashboard/server.py:2694-2703`).
  - Does not mutate current `license_tier`.
- Gap evidence: `pending_downgrade` is never applied anywhere (only write/read locations: `dashboard/server.py:2694`, `3434`, cleared on purchase at `2015`).
- Verdict rationale: transition path exists but never executes actual downgrade.

#### 8) Team → Crew
- Code path, records, and state behavior identical to #7.
- Verdict rationale: same unimplemented execution of scheduled downgrade.

#### 9) Crew → Personal Plus
- Code path, records, and state behavior identical to #7.
- Verdict rationale: same unimplemented execution of scheduled downgrade.

#### 10) Personal Plus → Personal
- Code path, records, and state behavior identical to #7.
- Verdict rationale: same unimplemented execution of scheduled downgrade.

#### 11) License purchase full flow (Stripe checkout → webhook → license delivery → local activation)
- Website-side flow (implemented):
  - Checkout session creation (`license-worker.js:202-308`).
  - Stripe webhook verification + license issuance (`license-worker.js:555-651`).
  - Pending `license_delivered` notification queued (`license-worker.js:634-651`).
- Local activation path (implemented):
  - Telemetry submit receives notifications and can activate delivered token (`dashboard/server.py:1015-1056`).
  - MCP equivalent path also activates delivered token (`mcp/server.py:3745-3813`).
- Product integration gap:
  - Licensing UI currently uses mock purchase helper (`dashboard/ui-next/licensing-api.js:5-7`, `100-106`) and then local purchase write (`dashboard/ui-next/windows/licensing.js:1934-1948`).
- Verdict rationale: components exist, but intended end-to-end flow is not wired in product path.

#### 12) Renewal — Personal Plus auto-renewal
- Code path observed:
  - Local auto-renew toggle: `POST /api/licensing/auto-renewal` (`dashboard/server.py:2593-2644`).
  - Website webhook accepts `invoice.paid`/`invoice.payment_failed` but archives only (`license-worker.js:61-72`, `656-665`).
- Decision-chain records: local toggle logs `auto_renewal_opted_in/out` (`dashboard/server.py:2625-2637`).
- Missing behavior:
  - No renewal processor that issues replacement token/license or updates expiry.
  - No automatic “same tier vs recommended tier” renewal logic from design (`license-signal-system.md:94-101`).

#### 13) Renewal — Crew and above (active decision, no auto-renewal)
- Code path observed: no dedicated renewal-decision workflow in dashboard or worker.
- State behavior:
  - Purchase flow sets `auto_renewal=true` for all paid tiers (`dashboard/server.py:1999`), despite UI showing auto-renew controls only for Personal Plus (`dashboard/ui-next/windows/licensing.js:2012-2013`, `2059-2067`).
- Design mismatch:
  - Design expects non-Personal-Plus renewal behavior to be explicit/active and tier-aware.
- Verdict rationale: renewal intent is represented only in copy/toggles; transactional behavior missing.

#### 14) License expiry behavior (governance/proxy/signing/operator warning)
- Code path:
  - Expired licensed posture downgrades to `unlicensed` (`mcp/licensing.py:371-377`).
  - Governance continues; records keep appending.
  - Proxy signing remains required and independent of license (`proxy/server.py:1518-1527`).
- Decision-chain records:
  - MCP-governed records include updated posture fields (`mcp/server.py:1218-1223`).
  - Proxy records remain signed mediated decisions (`proxy/server.py:140-149`).
- Warning path defect:
  - Notifications rely on `collect_health_signals` (`dashboard/server.py:1279-1345`).
  - `chain_health._license_health()` tries loading non-existent `scripts/licensing.py` and returns unknown (`scripts/chain_health.py:820-836`), so expiry warning signal is not reliable.
- Design alignment: governance continuity is correct; operator-facing warning reliability is not.

#### 15) License revocation — explicit revocation
- External revoke path:
  - Admin revoke endpoint writes revocation list + pending notification (`license-worker.js:1480-1544`).
- Local processing path:
  - Telemetry notification handler writes `license_revoked` chain event and reverts local config to Personal (`dashboard/server.py:1036-1065`; `mcp/server.py:3778-3823`).
- Decision-chain records: `license_revoked` non-action event with notification payload.
- State changes:
  - `license.json` forced to `license_status=personal`, `license_tier=personal` after processing.
  - KV updates occur in worker-side stores (`REVOCATION_LIST`, `PENDING_NOTIFICATIONS`).
- Verdict rationale: code path exists but true end-to-end requires external Worker+telemetry transport.

#### 16) First machine activation (`install_fingerprint`)
- Code path: `_get_install_fingerprint()` (`dashboard/server.py:62-86`).
- State changes:
  - If no fingerprint file:
    - with existing `license_key`: sets fingerprint to `sha256(license_key)[:16]` (`dashboard/server.py:72-75`),
    - else random token (`dashboard/server.py:76-80`).
  - Persists `runtime/install_fingerprint` with 0600 best-effort (`dashboard/server.py:81-85`).
- Design mismatch:
  - Design describes random install fingerprint during trial (`licensing-app-design-capture-v3.md:148`).
  - Deterministic key-derived fingerprint can collide across machines for same key.

#### 17) Second machine activation on same license
- Sharing-based path:
  - Host starts sharing (`dashboard/server.py:2314-2347`), join request approved (`2360-2448`), machine event recorded.
- Direct key path:
  - Second machine can activate same key through `activate-with-key` (`dashboard/server.py:2235-2309`) with no global machine-limit check.
- Decision-chain records:
  - Sharing path logs `machine_added`.
  - Direct key activation logs `license_activated`, not machine-count event.
- Verdict rationale: machine governance exists only for sharing flow, not for direct key activation.

#### 18) Revoke first machine — does second continue?
- Code path: `POST /api/sharing/revoke-machine` verifies active machine set from chain, writes `machine_revoked` (`dashboard/server.py:2517-2590`).
- State behavior:
  - Revocation targets one fingerprint only (`dashboard/server.py:2578-2584`).
  - Other active fingerprints remain in chain-derived active set (`dashboard/server.py:93-123`).
- Verdict rationale: for sharing-managed machines, second machine continues as expected.

#### 19) Maximum machine limit reached — next activation attempt
- Enforced path:
  - Sharing start/approve checks cap via `MACHINE_CAPS` and active machine count (`dashboard/server.py:56-59`, `2329-2337`, `2383-2391`).
  - Worker admin authorize-sharing enforces Personal Plus cap (`license-worker.js:1708-1736`).
- Bypass path:
  - Direct `activate-with-key` path has no machine cap check (`dashboard/server.py:2235-2309`).
- Additional defect interaction: deterministic license-key-derived fingerprint (#16) can collapse machine identity.

#### 20) Lost license key — recovery path
- Recovery implementation exists in website worker:
  - `/api/replace-key` two-step email verification + Stripe purchase verification + replacement key issue (`license-worker.js:700-878`).
- Product gap:
  - No wiring from dashboard licensing UI/API to `/api/replace-key`; product surface only supports manual “activate with key” (`dashboard/ui-next/windows/licensing.js:2086-2089`, `dashboard/ui-next/api.js:459-460`).
- Verdict rationale: recovery backend exists, operator-facing product flow is missing.

#### 21) Corrupted `license.json` — proxy startup behavior
- Proxy behavior:
  - Proxy does not load `license.json` at startup; startup gate is signing key only (`proxy/server.py:79-96`, `1518-1527`).
- Licensing posture behavior in MCP/dashboard paths:
  - Corrupted file causes fail-closed posture to unlicensed (`mcp/licensing.py:321-331`).
  - `license_status` tool returns controlled `license_status=error` payload (`mcp/server.py:1611-1623`).
- Verdict rationale: no governance crash; fail-closed behavior is present.

#### 22) Missing `install_fingerprint` — proxy startup behavior
- Proxy behavior: unaffected (no fingerprint dependency in proxy startup path).
- Dashboard behavior:
  - Missing fingerprint triggers regeneration (`dashboard/server.py:62-86`).
  - Regeneration may be deterministic from key hash (collision risk, see #16).
- Verdict rationale: recovery path exists but identity semantics are flawed.

#### 23) Trial experience — access and restrictions
- Code path:
  - Trial posture returned by licensing mode endpoint (`dashboard/server.py:3411-3464`).
  - UI maps trial as green/active state and keeps governance features available (`dashboard/ui-next/app.js:268-274`, `main-page.js:340-345`).
- Decision-chain behavior:
  - Governance remains active; no policy lockout path tied to trial status (`mcp/licensing.py:6-8`, `125`; `docs/design/atested-v3-design.md:47-50`).
- Verdict rationale: trial remains full-governance operational as designed.

#### 24) Trial completion trigger — representative ALLOW/DENY demonstration
- Code path: `_check_trial_completion()` computes evidence and threshold (`dashboard/server.py:2810-2827`).
- Current implemented trigger:
  - `allow_count >= 1`
  - `deny_count >= 1`
  - `tool_category_count >= 3`
  - `total_decisions >= 20`
  (`dashboard/server.py:2818-2823`)
- Chain records: writes `trial_complete` once (`dashboard/server.py:2849-2869`); extension check currently hardcoded false (`2843-2847`).
- Design note: design keeps exact threshold as open question (`licensing-app-design-capture-v3.md:162-163`, `585`).

#### 25) Trial → purchase decision — case document + recommendation
- Code path:
  - Case document assembly from chain + questionnaire (`dashboard/server.py:2898-3097`).
  - Deterministic climb procedure and recommendation status (`2975-3015`, `3044-3054`).
- Decision-chain records:
  - Questionnaire/capacity inputs persisted as non-action events (`dashboard/server.py:1745-1758`, `2926-2941`).
  - Trial completion evidence can be embedded (`2859-2866`).
- Verdict rationale: recommendation/case-document behavior is implemented and deterministic.

### Gaps and Defects (Severity Ranked)

#### Critical
1. Institution transition path is broken: inquiry event type is not registered, causing runtime failure before handoff (`dashboard/server.py:2166-2171`, `scripts/event_model.py:37-71`).
2. Downgrade transitions are non-functional beyond scheduling; no mechanism applies `pending_downgrade` at renewal (`dashboard/server.py:2694-2703`, `3434`; no apply path).
3. Renewal lifecycle is incomplete: no operational renewal processing for Personal Plus or Crew+ (worker archives invoice events only: `license-worker.js:61-72`, `656-665`).
4. Product purchase path is still mock/local and not integrated to Stripe/webhook/license-delivery lifecycle (`dashboard/ui-next/licensing-api.js:5-7`, `100-106`; `windows/licensing.js:1934-1948`).

#### Notable
1. Expiry warning pipeline is unreliable because `chain_health` license probe points at a non-existent module (`scripts/chain_health.py:820-836`), reducing operator visibility for lapsed state.
2. Machine identity model is flawed: missing fingerprint regenerates from license key hash (`dashboard/server.py:72-75`), creating cross-machine collisions.
3. Machine limits are enforced only in sharing workflow; direct key activation bypasses cap checks (`dashboard/server.py:2235-2309` vs `2329-2337`, `2383-2391`).
4. Lost-key recovery exists only in worker backend and is not integrated into product UI flow (`license-worker.js:700-878`; no dashboard client call path).

#### Minor
1. Trial extension path is hardcoded false (`dashboard/server.py:2843-2847`), so remote extension contract is placeholder-only.
2. Local non-action licensing events are unsigned (record-hash only), while trust-grade signature enforcement is concentrated in proxy-mediated decisions.
