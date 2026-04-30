# Atested Release Testing Specification v1

Status: Tier 0 reviewed, returning to Codex for implementation planning  
Date: 2026-04-29  
Scope: Atested product code, dashboard, evidence package flow, public website, and Cloudflare Workers  
Primary repos: `atested/governance-layer`, `atested/atested.com`, `GregKeeter/Gregs-dev-code`

## Purpose

Atested is entering release qualification. The release process must verify both
the product code and the public website against the product's core promise:
governed AI actions are controlled, recorded, exportable, and tamper-evident.

This specification defines a staged release qualification process for a solo
founder operating on a single development machine. Each gate has an executor,
scope, acceptance criteria, and required evidence.

## Product Context

This spec reflects the product state after the D-139 through D-161 release
hardening arc:

- Runtime integrity protection for chain file, proxy source, and policy rules.
- Chain Walker implemented through readout, live walker, playback, background
  verification, archive support, export authorization, encrypted evidence
  packages, and external viewer.
- Export authorization with license-key authentication and scoped tokens.
- Evidence packages using PBKDF2-HMAC-SHA-256 and AES-256-GCM.
- Self-contained external evidence viewer.
- Background chain verification sidecar.
- Archive manifests, preserved chains, and fresh-chain events.
- Classifier opacity floor enforcing Tier 3 minimum on pipes, subshells, and
  variable expansion.
- Matched policy rule visibility across decision surfaces.
- Current docs pass through D-160.

## Open Decision

Tier 0 must keep this boundary visible before gate work begins:

1. **Viewer verification claim boundary.** Browser viewer verification is
   limited to AES-GCM ciphertext integrity and chain hash linkage. Ed25519
   signature verification is server-side for this release and represented in
   the package verification summary. Browser UI and docs must not claim
   in-browser signature verification.

## Resolved Decision: Dashboard Local Read Boundary

Unauthenticated local read-only dashboard endpoints are accepted for this
release under three conditions that Gate 2 must verify:

1. Dashboard server binds to loopback (`127.0.0.1`) by default.
2. CORS permits only local dashboard origins.
3. Read-only endpoints cannot mutate chain state, runtime state, telemetry
   state, trouble reports, exports, or configuration.

If any condition is not met, Gate 2 must either fix the implementation or
escalate to Tier 0. This is an explicit design decision: the operator
dashboard is a local tool, and requiring authentication for every read
endpoint on a loopback-bound server adds friction without meaningful security
benefit.

Threat boundary:

- This release model assumes the dashboard is used by the local operator on
  their own machine.
- Local malware, hostile browser extensions, and other local OS users with
  access to the same loopback services are outside the release threat model
  unless separately mitigated.
- Gate 2 verifies loopback binding, local-only CORS, and no-mutate read
  behavior so the accepted local-read model is explicit rather than implicit.

## Resolved Decision: Git History Rewrite Timing

Outstanding Issue #8 covers removing private process documents from commit
history and rewriting non-target author emails across historical commits. This
operation invalidates existing commit SHAs.

Tier 0 approved Option C: run all release gates against the current codebase
using pre-rewrite SHAs, then perform the git history rewrite after all gates
pass and before public release. The release report records pre-rewrite SHAs as
historical references and is updated with post-rewrite SHAs after the rewrite
completes.

This avoids destructive rewrite risk before the codebase is verified while
still ensuring private process docs are removed before the repo goes public.

Required safeguards for the post-gate rewrite:

- Create a full mirror backup before rewriting.
- Run `git-filter-repo` on a disposable clone first.
- Record old HEAD to new HEAD mapping for all affected repos.
- Document the force-push plan.
- Re-clone or hard-refresh local working copies after rewrite.
- Confirm Cloudflare Pages, GitHub branch protections, and deployment settings
  point to the intended post-rewrite branch.
- Preserve the rewrite log as a release evidence artifact.

Executor: Cecil  
Classification: BUILD  
Prerequisite: `git-filter-repo` installed

## Prerequisite 2: Trust-Surface Test Inventory

Before gate work begins, produce an inventory of existing test coverage mapped
against invariants and trust surfaces. This is diagnostic work. It does not
write new tests.

The inventory must map:

- Each invariant, `INV-001` through `INV-010`, to covering tests.
- Whether each invariant has positive and negative coverage.
- Each trust surface to covering tests:
  classifier, policy evaluator, chain recorder, integrity monitor, approval
  store, export authorization, evidence package, external viewer, background
  verifier, archive system.
- Each D-139 integrity event type to tests that trigger it.
- Each Chain Walker phase to tests that cover it.

Acceptance:

- Inventory document exists at a known path in the product repo.
- Every invariant and trust surface has an entry.
- Gaps are explicitly named, not implied by absence.
- Inventory records exact test commands, Python version, environment variables,
  runtime isolation method, test count, pass/fail/skip profile, and known
  pre-existing failures.

Executor: Cecil  
Classification: INVESTIGATE

## Gate 0: Security Blocker Verification

Gate 0 verifies that known security fixes survive the original adversarial
attack scenarios. If any blocker test fails, remediation is required before
proceeding.

### 0.1 Integrity Metadata Re-Baseline Prevention

Required test:

- Create or use a chain with integrity metadata.
- Delete integrity metadata.
- Restart the proxy or startup integrity sequence.
- Confirm the system detects the violation rather than silently re-baselining.
- Repeat the deletion during runtime and confirm normal operation cannot use
  missing metadata to suppress tamper detection.

Acceptance:

- Test is automated and repeatable.
- Test proves metadata deletion does not suppress chain tamper detection at
  startup or during runtime.

### 0.2 Export Token Scope Enforcement

D-155 implemented license-key export authorization with short-lived scoped
tokens and server-side enforcement on export-mode data pulls.

Required negative tests against the implemented scope:

- Token scoped to one export surface used against a different export surface.
- Expired token.
- Forged token (invalid signature or structure).
- Request with no token to a token-required endpoint.

Future token hardening (not in scope for this release):

The following scope dimensions are not currently enforced by the token
implementation and are documented here as future feature requests, not
release-blocking test items:

- Token binding to specific export format.
- Token binding to specific chain source (live vs. archive).
- Token binding to specific archive ID.
- Token binding to specific record range.
- Token binding to specific filter set.
- Single-use token enforcement (replay prevention).

If gate work discovers that any of these dimensions are already enforced
in the implementation, add corresponding negative tests at that time.

Accepted release limitation:

- During the token TTL, a token scoped to a valid export surface may authorize
  broader same-surface behavior than a future exact-scope token would allow
  unless the endpoint separately constrains format, chain source, archive ID,
  record range, and filter set. This is accepted for this release only if it
  is documented in the release report as future hardening rather than
  accidentally treated as a verified property.

Acceptance:

- Wrong-surface, expired, forged, and missing tokens are rejected.
- Successful export records the correct chain event.

### 0.3 Evidence Viewer Tamper Modes

Browser viewer scope:

- Independently verifies AES-GCM ciphertext integrity.
- Independently verifies chain hash linkage.
- Does not independently verify Ed25519 signatures in this release.
- Displays server-produced signature verification summary where available.
- Does not claim in-browser signature verification.

Required tests:

- Ciphertext tamper: modify encrypted payload bytes and confirm AES-GCM
  authentication failure.
- Plaintext record tamper: in a test harness, decrypt a valid package, modify a
  plaintext record, re-encrypt successfully with a valid password, and confirm
  the viewer detects record hash/linkage failure after successful decryption.
- Manifest tamper: modify manifest fields and confirm consistency checks fail
  where applicable.
- Server-side signature summary proof: tamper a signed record before package
  creation and confirm the package builder's verification path either refuses
  to produce a clean package or records a failed signature verification summary.

Acceptance:

- Ciphertext tamper fails at decryption.
- Re-encrypted plaintext tamper fails at record/linkage verification, not at
  AES-GCM.
- Signature summary is proven to come from the server-side verifier, not from
  copied or caller-supplied package metadata.
- UI language accurately states what the viewer verified.

### 0.4 Classifier Shell Indirection

Required tests:

- Original D-161 attack scenarios.
- Reconstructed scenarios if originals are not documented.
- Process substitution input: `<(command)`.
- Process substitution output: `>(command)`.
- Process substitution combined with redirects.
- Process substitution inside chained commands.
- Here-docs where they affect target or action classification.

Acceptance:

- All opaque shell indirection cases classify at Tier 3 or stricter.
- Policy evaluator denies Tier 3 where operator approval is required.

Gate 0 acceptance:

- Every blocker has a targeted adversarial test.
- Every test is automated and repeatable.
- No blocker test fails.
- Results document references exact tests and commands.

Executor: Cecil  
Classification: BUILD

## Gate 1: Product Core Testing

Gate 1 closes trust-surface test gaps identified by the inventory. It is split
into five dispatch groups.

### Dispatch 1A: Classifier and Policy Evaluator

Scope:

- Shell edge cases.
- Opacity floor.
- Path handling.
- URL extraction order.
- Base-directory enforcement.
- Hidden path enforcement.
- Executable output constraints.
- Matched rule accuracy.
- Policy drift detection.

Acceptance:

- Positive and negative tests exist for classifier and policy evaluator
  invariants.
- Tier 3/Tier 4 operations cannot be misclassified into permissive paths.

### Dispatch 1B: Chain Recorder and Integrity Monitor

Scope:

- Hash linkage.
- Ed25519 signatures.
- Concurrent appends.
- Mixed-chain verification: unsigned old records and signed new records.
- Malformed records.
- Missing/truncated chain.
- Metadata deletion.
- Metadata tampering.
- Startup verification sequence.
- Runtime policy drift and deny-all behavior.

Acceptance:

- Chain integrity survives startup and runtime tamper tests.
- Every D-139 integrity event type has a test that triggers it.

### Dispatch 1C: Background Verifier and Archive System

Scope:

- Usage-triggered verification frequency.
- Break detection.
- Break classification.
- Health status reporting.
- Archive creation on integrity violation.
- Manifest accuracy.
- Preserved chain integrity.
- Fresh-chain-after-archive event.
- Sidecar terminal fallback.
- Archive listing and walker source selection.

Acceptance:

- Verification failures are visible and linkable.
- Archive manifests match preserved chain contents.

### Dispatch 1D: Approvals and Export Authorization

Scope:

- Approval override of DENY.
- Forged approval rejection or documented limitation (see Accepted Deferrals:
  operator identity verification is not implemented for this release, so
  forged approval detection is limited to what the current unverified-identity
  model can support).
- Stale approval detection.
- Revocation behavior.
- Approval chain recording.
- License-key validation.
- Token creation.
- Token expiry.
- Export-surface token scope enforcement.
- Export event chain recording.
- Unauthorized export rejection.

Acceptance:

- Export cannot occur without valid operator authorization.
- Approval behavior and limitations are covered by tests and documentation.

### Dispatch 1E: Evidence Package and External Viewer

Scope:

- PBKDF2 parameter correctness.
- AES-256-GCM encryption round trip.
- Wrong-password rejection.
- Ciphertext tamper rejection.
- Re-encrypted plaintext record tamper detection.
- Manifest accuracy.
- Verification summary accuracy.
- Verification summary is generated by the server-side verifier and fails when
  signed records are tampered before packaging.
- Password never in package, logs, event records, or returned metadata.
- ZIP package completeness.
- Viewer decryption.
- Hash linkage verification.
- Non-technical and technical view rendering.
- View-only constraint: no unencrypted download controls.

Acceptance:

- Evidence package verification is cryptographically real for AES-GCM
  ciphertext integrity and chain hash linkage.
- Ed25519 signature verification is server-side only for this release and
  represented in the verification summary.

Gate 1 acceptance:

- Automated tests cover positive and negative cases for each trust surface.
- Every invariant has at least one positive and one negative test.
- Every D-139 integrity event type has a trigger test.
- No critical or high trust-surface failures remain.
- Post-Gate-1 test baseline is recorded.

Executor: Cecil  
Classification: BUILD

## Gate 2: Dashboard and API Testing

Gate 2 verifies the operator dashboard, local dashboard server, and API
behavior.

### API Endpoint Inventory

Produce a complete list of all `/api/*` endpoints from `dashboard/server.py`.
For each endpoint, document:

- HTTP method.
- Authentication requirement.
- Whether it writes to the governance chain.
- Whether it writes outside the chain.
- Whether it returns governed data.
- Whether it can export data.

### Authentication and Authorization Boundary

The dashboard runs locally on the operator's machine. The local read boundary
decision is resolved above. Gate 2 must verify all three conditions hold in
the implementation:

1. Dashboard binds to `127.0.0.1` by default.
2. CORS allows only local dashboard origins.
3. Read-only endpoints cannot mutate chain state, runtime state, telemetry
   state, trouble reports, exports, or configuration.

If any condition is not met, fix the implementation or escalate to Tier 0.

Mutation endpoints require operator authentication. License-key and token-gated
endpoints must reject unauthenticated access.

Required checks:

- Read-only endpoints succeed without authentication from localhost.
- Mutation endpoints reject unauthenticated requests.
- Configuration update requires operator/license gate as designed.
- Export authorization requires license-key authentication.
- Evidence package creation requires a valid scoped export token.
- Export-mode data pulls require a valid scoped export token.

### Chain Walker Endpoints

Required checks:

- `/api/audit/walker` returns correct live-chain window data.
- `/api/audit/walker` returns correct archived-chain window data.
- `/api/audit/archives` returns accurate archive manifests.
- Walker filtering carries over from Search mode.
- Alert jump resolution returns valid positions.

### Export and Evidence Endpoints

Required checks:

- `POST /api/export/authorize` validates license key, creates scoped token,
  and records `chain_export_created`.
- `POST /api/export/package` requires scoped token, creates encrypted evidence
  package, records `encrypted_evidence_package_created`, and returns a valid
  ZIP.
- Expired, wrong-surface, forged, and missing tokens are rejected.

### Data Integrity

Required checks:

- Telemetry and trouble reports remain outside the governance chain.
- Summary telemetry reads from `gov_runtime/LOGS/telemetry/summary.json`, not
  from governance chain events.
- Raw telemetry events are never stored as individual rows.
- Record detail works for all event types, including D-139 integrity events,
  stability events, archive events, approvals, revocations, and export events.

### Dashboard UI

Manual checks:

- Chain Walker live and archive modes render correctly.
- Health reflects integrity and background verifier status accurately.
- Export gates are visible and functional across Activity, Audit, Approvals,
  Reports, and Configuration windows.
- Trouble button captures current window context.
- Reports auto-update on valid time range changes.

Gate 2 acceptance:

- API endpoint inventory exists with authentication and chain-write
  annotations.
- API-level tests cover authorization, validation, and chain recording for
  mutation and export endpoints.
- Dashboard behavior matches the trust model.

Executor: Cecil for API tests; Greg for manual UI verification  
Classification: BUILD / manual verification

## Gate 3: Website and Worker Testing

Gate 3 verifies `atested.com`, public flows, and Cloudflare Workers.

### Testing Strategy

1. **Preview deployment first.** Push release candidate to a Cloudflare Pages
   preview branch. Run functional, security, endpoint probing, and auth-bypass
   tests against preview.
2. **Live smoke second.** After preview passes, deploy production and run a
   reduced smoke test: page loads, navigation, redirects, and critical flows.
   Do not run abuse or destructive tests against live production.

### Functional Flows

Required checks:

- License purchase flow. If Stripe is not integrated, document the gap rather
  than skipping it.
- Personal license flow.
- License replacement flow cannot be triggered with email knowledge alone.
- Feedback/contact/communications flows.

### Worker Security

Required checks:

- Admin endpoints require admin credentials.
- Telemetry ingestion rejects malformed and oversized payloads.
- Capture endpoint exposure decision is intentional and documented.

### Website Integrity

Required checks:

- `_redirects` and middleware handle legacy routes, including
  `/about/trusting-us/` redirect and 410 Gone routes.
- No orphaned pages exist unless intentionally preserved.
- Security headers are present.

### Documentation Accuracy

Required checks:

- Dashboard docs reflect Chain Walker, evidence packages, matched rule, export
  authorization, background verification, Communications, readable rule cards,
  and constraint badges.
- Chain docs reflect archives, background verification, evidence packages,
  external viewer, and current integrity capabilities.
- Install docs reflect current proxy startup, provider setup, and environment
  variables.
- User-facing docs do not contain stale v2 governed-tool framing.
- Internal/historical v2 docs are acceptable if intentionally preserved.
- Accepted deferrals for per-agent approval scoping and operator identity
  verification are stated plainly in user-facing docs or release notes.
- Viewer docs do not claim in-browser Ed25519 signature verification.

### Terminology Checks

Required checks:

- No stale v2 claims in user-facing pages unless intentionally documented as
  legacy.
- No misleading claims about telemetry, exports, chain integrity, or evidence
  verification.
- User-facing contexts use Action terminology, not Tool terminology, except
  where referring to model/provider tool calls as a technical object.

Gate 3 acceptance:

- Public endpoints have explicit exposure decisions.
- License replacement cannot be abused with email knowledge alone.
- Admin endpoints require admin authentication.
- Docs match current product behavior.
- No release-blocking stale claims remain.

Executor: Cecil for automated checks; Greg for manual flow and docs review  
Classification: BUILD / manual verification

## Gate 4: Release Candidate Adversarial Scan

Gate 4 freezes a release candidate and audits that exact commit. The auditor
must not be the executor who wrote the code under review.

Required scans:

- Git history secret scan.
- Dependency audit.
- Static review of trust surfaces against inventory.
- Dashboard API abuse tests:
  malformed requests, oversized payloads, authentication bypass attempts on
  mutation and export endpoints.
- Worker abuse tests:
  malformed telemetry payloads, capture endpoint abuse, admin endpoint access
  attempts.
- Classifier bypass matrix:
  opacity floor bypasses, novel shell indirection, encoded payloads, path
  manipulation.
- Chain integrity tamper matrix:
  metadata deletion, metadata modification, chain truncation, record insertion,
  hash manipulation.
- Evidence package tamper matrix:
  ciphertext modification, re-encrypted plaintext record modification, manifest
  modification, server-side signature summary manipulation, viewer
  substitution.
- External viewer tamper matrix:
  wrong password, tampered ciphertext, re-encrypted modified plaintext,
  tampered manifest, broken chain links.
- Export token abuse:
  expired tokens, wrong-surface tokens, forged tokens.

Same-surface broader-range export behavior is not a Gate 4 failure by itself
if it matches the documented release limitation in Gate 0.2. Gate 4 should
record it as accepted future hardening unless implementation claims exact
scope binding.

Gate 4 acceptance:

- Findings are documented against exact product and website commit SHAs.
- Critical/high findings are fixed or explicitly accepted by Tier 0.
- Release report records product, website, and state repo SHAs.

Executor: Codex preferred; Cecil allowed only with deviation noted  
Classification: INVESTIGATE

## Gate 5: Operational Dry Run

Gate 5 runs Atested as a real operator before public release. This is manual
work performed by Greg on the development machine.

### Runtime Setup

- Create a fresh dry-run `gov_runtime/` directory.
- Keep it separate from development chain/runtime state.
- Preserve the dry-run directory as a release artifact.

### Required Scenarios

- Fresh install from clean runtime.
- Trial license state.
- Personal license state, or documented gap if Stripe/integration status
  prevents it.
- Real proxy traffic through at least one provider route.
- Chain growth over at least 50 records across multiple sessions.
- Normal restart and chain continuity.
- Restart after simulated integrity violation.
- Policy rules change during runtime.
- Evidence package export from Walker with range selection.
- Evidence package opened in a clean browser profile.
- Trouble report submission from multiple windows.
- Telemetry opt-in and opt-out with summary verification.
- Archived chain walking in Audit.
- Reports generation across all seven predefined reports.
- Configuration unlock and policy viewing.

### Evidence Package Round Trip

Clean-browser-profile substitute for multi-machine test:

1. Create evidence package from Walker.
2. Extract ZIP.
3. Open `viewer.html` in incognito or a separate browser profile.
4. Load companion files.
5. Enter password.
6. Verify decryption, chain verification results, non-technical view,
   technical view, and absence of unencrypted download controls.

Gate 5 acceptance:

- Product works end-to-end without code edits.
- Evidence exports can be independently opened and verified within the
  documented viewer scope.
- Integrity failures are visible and actionable.
- Operator workflows are understandable without developer intervention.
- Any incomplete scenario is documented as a known gap with a remediation plan.

Executor: Greg  
Classification: manual verification

## Test Environment

The release process uses one development machine. Isolation comes from clean
runtime state, temporary directories, and preview deployments, not separate
hardware.

Runtime isolation:

- Automated tests use temporary directories created by the test framework.
- Dry run uses a clean persistent `gov_runtime/` dedicated to Gate 5.
- Website verification uses Cloudflare Pages preview first; production receives
  smoke tests only.

If a result could be affected by environment contamination, the test report
must document the isolation method.

## Regression Baseline

Record test baseline at two points:

1. After trust-surface test inventory:
   current test count, pass/fail/skip profile, exact commands, and known
   pre-existing failures.
2. After Gate 1:
   updated test count and pass/fail profile. This becomes the baseline for
   Gate 4 release-candidate comparison.

No test that passed after Gate 1 may fail in the release candidate without
explicit explanation and Tier 0 acceptance.

## Gate Sequencing

Recommended sequence:

1. Trust-surface test inventory.
2. Gate 0: security blocker verification.
3. Gate 1: product core testing, dispatches 1A through 1E.
4. Regression baseline lock.
5. Gate 2: dashboard and API testing.
6. Gate 3: website and Worker testing, preview first and live smoke second.
7. Gate 4: release candidate adversarial scan after RC freeze.
8. Gate 5: operational dry run.
9. Release report draft with pre-rewrite SHAs.
10. Git history rewrite.
11. Post-rewrite verification.
12. Final release report with pre-rewrite and post-rewrite SHAs.

Gates 2 and 3 may overlap if executor capacity exists. Gates 0 and 1 are
strictly sequential because Gate 0 findings may change Gate 1 scope.

## Release Exit Criteria

Atested is not release-ready until:

- Trust-surface test inventory exists and all gaps are closed or explicitly
  accepted by Tier 0.
- All Gate 0 blockers are adversarially verified.
- All trust-surface tests pass.
- Every invariant has positive and negative test coverage.
- Evidence package verification is cryptographically real for AES-GCM
  ciphertext integrity and chain hash linkage in the browser viewer.
- Ed25519 signature verification is performed server-side before package
  creation and represented in the package verification summary.
- Browser viewer UI and docs do not claim in-browser Ed25519 signature
  verification.
- Export authorization is enforced server-side with expiring tokens scoped to
  export surface. Additional scope dimensions (format, chain source, archive
  ID, filters, record range, replay prevention) are documented as an accepted
  release limitation and future hardening.
- Chain integrity protections survive metadata deletion and tampering tests.
- Metadata deletion tests cover both startup and runtime behavior.
- Dashboard server binds only to loopback by default, read-only endpoints do
  not mutate state, and CORS permits only local dashboard origins (resolved
  decision, verified in Gate 2).
- Website license, telemetry, and capture endpoints have explicit exposure
  decisions.
- Docs match current product.
- No critical or high findings remain unless Tier 0 explicitly accepts them.
- Git history rewrite is either complete or explicitly deferred with risk
  documented. For the approved release plan, rewrite runs after all gates pass
  and before public release.
- Release evidence artifacts are preserved.
- Final release report records exact commit SHAs, test results, known gaps, and
  accepted risks.

## Accepted Deferrals

The following are known gaps that are not release-blocking if documented in
the release report and, where user-visible, in docs or release notes:

- Stripe integration: if incomplete, paid tiers are documented as coming soon.
- Customer database.
- Internal management dashboard.
- Per-agent approval scoping. Current behavior: approvals apply to all agents
  and sessions; per-agent scoping is planned.
- Operator identity verification. Current behavior: dashboard accepts any
  operator name without verification; identity verification is planned.
- Claude Code deny-list bug. Documented as upstream/tooling issue, not Atested
  product behavior.
- Retroactive signing. Mixed-chain verifier handles unsigned old / signed new
  boundary.
- Browser Ed25519 signature verification. Server-side verification summary is
  used for this release.
- Exact export-token binding beyond export surface. Format, chain source,
  archive ID, record range, filter set, and single-use replay prevention are
  future hardening unless already implemented.
- Multi-machine evidence round trip. Clean-browser-profile test substitutes for
  release qualification.

## Release Evidence Artifacts

Preserve these artifacts in a named release evidence folder:

- Trust-surface test inventory.
- Gate 0 through Gate 5 reports.
- RC commit SHAs for product, website, and state repo.
- Dependency scan output.
- Secret scan output.
- Focused security/adversarial scan output.
- Post-Gate-1 regression baseline.
- Gate 5 dry-run runtime directory.
- Sample evidence packages.
- Sample external viewer verification notes/screenshots if available.
- Accepted-risk log.
- Git rewrite log and old-to-new SHA mapping, if rewrite was performed.
- Final release report.

## Tier 0 Review Notes

Changes from Codex's draft:

1. **Export token scope narrowed to implemented dimensions.** D-155 implemented
   surface-level token scoping. The six additional dimensions (format, chain
   source, archive ID, record range, filter set, replay prevention) are
   documented as future feature requests in Gate 0.2, not release-blocking
   test items. If implementation planning reveals any are already enforced,
   add tests at that time.

2. **Dashboard local read boundary resolved.** Moved from Open Decisions to
   a Resolved Decision. The three conditions (loopback binding, local CORS,
   no-mutate read endpoints) are accepted as the design. Gate 2 verifies the
   implementation meets them. Rationale: the conditions are clearly right for
   a local operator tool, and leaving this open would block Gate 2 scoping.

3. **Dispatch 1D forged approval cross-reference added.** The "or documented
   limitation" hedge now explicitly references the Accepted Deferrals section
   and explains why forged approval detection is limited (no operator identity
   verification in this release).

4. **Open Decision reduced to viewer claim boundary.** Git rewrite timing and
   dashboard read boundary are resolved. Browser viewer verification remains
   limited to AES-GCM ciphertext integrity and chain hash linkage; Ed25519 is
   server-side for this release.

## Guiding Principle

The release process should produce the same kind of evidence Atested promises
its users: clear records, explicit decisions, reproducible checks, and no
hidden trust assumptions.
