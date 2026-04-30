# Atested Release Testing Implementation Plan v1

Status: Tier 0 approved  
Date: 2026-04-29  
Parent spec: `docs/specs/release-testing-spec.md`  
Scope: Execution plan for release qualification gates, evidence artifacts, and dispatch sequencing

## Purpose

This plan turns the release testing specification into executable work. It does
not authorize product changes by itself. Each build or investigate item should
be issued as a dispatch with the scope, acceptance criteria, and artifacts
listed here.

The plan assumes the release testing spec is the source of truth. If this plan
and the spec disagree, update this plan to match the spec before execution.

## Operating Rules

- Gate evidence references pre-rewrite commit SHAs. The git history rewrite
  runs after all gates pass, as the final step before public release. The
  release report records pre-rewrite SHAs as historical references and notes
  the rewrite as a post-gate step.
- Automated test work uses temporary runtime directories unless the dispatch is
  explicitly a dry run.
- Any critical or high finding stops progression until fixed or explicitly
  accepted by Tier 0.
- Accepted deferrals are not failures, but they must appear in the final
  release report and, where user-visible, in docs or release notes.
- Gate output is written into a named release evidence folder in the product
  repo, then referenced from the final release report.

## Evidence Folder Layout

Root: `governance-layer/release-evidence/rc-NNN/`

Release candidate identifier format: `rc-NNN` where NNN is the next dispatch
number at freeze time (e.g., `rc-162` if the RC freeze happens at dispatch
162).

Structure:

- `01-test-inventory/`
- `02-gate-0-security-blockers/`
- `03-gate-1-product-core/`
- `04-gate-2-dashboard-api/`
- `05-gate-3-website-worker/`
- `06-gate-4-adversarial-scan/`
- `07-gate-5-operational-dry-run/`
- `08-git-history-rewrite/`
- `dependency-scans/`
- `secret-scans/`
- `accepted-risks.md`
- `release-report.md`

## Resolved: Git History Rewrite Timing

**Decision: Option C — rewrite after all gates pass.**

All testing runs against the current codebase with pre-rewrite SHAs. After
Gates 0 through 5 pass and the release report is drafted, Cecil performs the
git history rewrite as the final step before public release. The release
report records pre-rewrite SHAs as historical references and is updated with
post-rewrite SHAs after the rewrite completes.

This avoids the risk of a destructive rewrite before the codebase is verified,
while ensuring private process docs are removed before the repo goes public.

See "Post-Gate: Git History Rewrite" below for execution details.

## Prerequisite: Trust-Surface Test Inventory

### Work

Produce a diagnostic inventory of existing test coverage. Do not write new
tests in this prerequisite.

Map:

- `INV-001` through `INV-010`.
- Classifier, policy evaluator, chain recorder, integrity monitor, approval
  store, export authorization, evidence package, external viewer, background
  verifier, archive system.
- D-139 integrity event types.
- Chain Walker phases.
- Existing commands, environment, test counts, pass/fail/skip profile, and
  known failures.

### Likely Files / Artifacts

- `release-evidence/<rc>/01-test-inventory/trust-surface-test-inventory.md`

### Likely Source Areas

- `tests/`
- `scripts/`
- `dashboard/`
- Existing dispatch result files
- `docs/INVARIANTS.md` for invariant definitions
- `docs/specs/chain-walker-spec.md` for Chain Walker phase definitions

### Dependencies

None. This is the first dispatch.

### Complexity

Medium. Mostly read-only analysis with a test baseline run.

### Notes

- Invariants are documented in `docs/INVARIANTS.md` (INV-001 through INV-010).
- The 27 skips and 2 pre-existing failures are Python 3.9 / MCP import
  compatibility issues, documented in STATE_CURRENT.md. These are known and
  not release-blocking.

## Gate 0: Security Blocker Verification

### Work

Write targeted adversarial tests for the four blocker areas:

- Integrity metadata deletion does not re-baseline at startup or runtime.
- Export tokens reject wrong-surface, expired, forged, and missing-token use.
- Evidence viewer detects ciphertext tamper, re-encrypted plaintext record
  tamper, manifest tamper, and server-side signature summary failure.
- Classifier treats process substitution and similar shell indirection as
  Tier 3 or stricter.

### Likely Files / Artifacts

- `release-evidence/<rc>/02-gate-0-security-blockers/gate-0-results.md`
- New or updated tests under existing test layout.

### Likely Source Areas

- `scripts/integrity_monitor.py`
- `scripts/chain_archive.py`
- `scripts/evidence_package.py`
- `scripts/classifier.py`
- `dashboard/server.py`
- `dashboard/external-viewer/viewer.html`

### Dependencies

Trust-surface inventory complete.

### Complexity

Medium to large. The evidence package tamper harness may be the most complex
part because it must distinguish ciphertext authentication failure from
successful decryption followed by hash-linkage failure.

### Acceptance Artifacts

- Exact test commands.
- Pass/fail output.
- Notes tying each test back to the original attack scenario.

### Stop Conditions

Any blocker test fails.

## Gate 1: Product Core Testing

Gate 1 is split into five dispatches. Each dispatch closes gaps identified by
the inventory and records its own results.

### Dispatch 1A: Classifier and Policy Evaluator

#### Work

Add positive and negative tests for shell edge cases, path handling, opacity
floor, URL extraction order, base-directory enforcement, hidden paths,
executable output constraints, matched rule accuracy, and policy drift.

#### Likely Files

- `scripts/classifier.py`
- `scripts/policy_evaluator.py`
- Classifier and policy test files under `tests/`

#### Dependencies

Gate 0 classifier blocker tests passing.

#### Complexity

Medium.

#### Acceptance

Tier 3/Tier 4 operations cannot enter permissive policy paths through
misclassification.

### Dispatch 1B: Chain Recorder and Integrity Monitor

#### Work

Add tests for hash linkage, signatures, concurrent appends, mixed-chain
verification, malformed records, missing/truncated chain, metadata
deletion/tampering, startup verification, and runtime policy drift deny-all.

#### Likely Files

- `scripts/chain.py` or chain recorder module
- `scripts/integrity_monitor.py`
- Chain verifier tests

#### Dependencies

Gate 0 integrity metadata test passing.

#### Complexity

Large. Concurrency and tamper cases need careful temporary runtime isolation.

#### Acceptance

Every D-139 integrity event type has a trigger test.

### Dispatch 1C: Background Verifier and Archive System

#### Work

Add tests for usage-triggered verification, break detection/classification,
Health status reporting, archive creation, manifest accuracy, preserved chain
integrity, fresh-chain-after-archive events, sidecar fallback, archive listing,
and walker source selection.

#### Likely Files

- `scripts/background_verifier.py`
- `scripts/chain_archive.py`
- `scripts/chain_walker.py`
- Dashboard Health / archive endpoint tests if present

#### Dependencies

Dispatch 1B chain/integrity tests passing.

#### Complexity

Large.

#### Acceptance

Verification failures are visible and archive manifests match preserved chain
contents.

### Dispatch 1D: Approvals and Export Authorization

#### Work

Add tests for approval override, forged approval behavior or documented
limitation, stale approval detection, revocation, approval chain recording,
license-key validation, token creation, expiry, export-surface scope,
unauthorized export rejection, and export chain events.

#### Likely Files

- Approval store module
- `dashboard/server.py`
- Export authorization helpers
- API tests

#### Dependencies

Gate 0 export token tests passing.

#### Complexity

Medium to large.

#### Acceptance

Export cannot occur without valid operator authorization, and approval identity
limitations are covered by tests and documentation.

### Dispatch 1E: Evidence Package and External Viewer

#### Work

Add tests for PBKDF2 parameters, AES-256-GCM round trip, wrong password,
ciphertext tamper, re-encrypted plaintext tamper, manifest accuracy,
server-side verification summary accuracy, password non-disclosure, ZIP
contents, viewer decryption, hash linkage verification, rendering, and
view-only constraint.

#### Likely Files

- `scripts/evidence_package.py`
- `dashboard/external-viewer/viewer.html`
- Evidence package tests
- Viewer test harness

#### Dependencies

Gate 0 viewer/evidence tamper tests passing.

#### Complexity

Large.

#### Acceptance

Browser verification is cryptographically real for AES-GCM and hash linkage,
while Ed25519 remains server-side and accurately represented.

### Gate 1 Rollup (final step of Dispatch 1E)

As the last step of Dispatch 1E, run the full product test suite and record
the post-Gate-1 regression baseline.

#### Artifact

- `release-evidence/<rc>/03-gate-1-product-core/gate-1-rollup.md`

#### Stop Conditions

Any critical or high trust-surface failure remains unaccepted.

## Gate 2: Dashboard and API Testing

### Work

Enumerate every `/api/*` endpoint and test the dashboard server trust boundary:

- Read-only endpoints work unauthenticated from localhost.
- Mutation endpoints reject unauthenticated access.
- License-key endpoints reject invalid access.
- Token-required export data pulls reject missing, expired, forged, and
  wrong-surface tokens.
- Chain Walker live/archive endpoints return correct windows.
- Export/evidence endpoints record required chain events.
- Telemetry and trouble stay outside the governance chain.
- Record detail resolves all event types.

### Browser Verification (manual — Greg)

Greg drives the dashboard through a browser with the dashboard server
running against a chain with real governance data. These checks hedge against
rendering failures, JavaScript errors, and interaction bugs that API-level
tests cannot see. Browser verification is additive — API tests remain the
acceptance criteria.

Browser checks:

- Main page loads, all nine launcher cards are visible and clickable.
- Activity window loads, rows render, clicking a row opens Record Detail.
- Record Detail displays decision-colored accents, chain metadata, and
  hash/signature status.
- Audit window loads in Search mode, switching to Walker mode renders the
  11-slot data/narrative panes.
- Chain Walker step forward/back, play, and alert jump controls function.
- Chain Walker archive source selection switches to archived chain data.
- Approvals window shows active approvals with staleness indicators.
- Health window displays chain integrity, background verifier status, and
  recent health events.
- Reports window generates at least one predefined report and the output
  renders with formatted data.
- Configuration window shows policy rule cards and base directory panes.
- Export gate: clicking an export action triggers the license-key auth
  dialog. Invalid key is rejected.
- Trouble button opens from operator chrome and captures window context.
- Communications window renders slot accounting and telemetry controls.
- No JavaScript console errors during the walkthrough.

### Likely Files / Artifacts

- `release-evidence/<rc>/04-gate-2-dashboard-api/api-endpoint-inventory.md`
- `release-evidence/<rc>/04-gate-2-dashboard-api/gate-2-results.md`
- `release-evidence/<rc>/04-gate-2-dashboard-api/gate-2-browser-results.md`
- API tests under existing dashboard test layout.

### Likely Source Areas

- `dashboard/server.py`
- `dashboard/ui-next/`
- `dashboard/external-viewer/`
- Runtime log directories for telemetry/trouble fixtures

### Dependencies

Gate 1 baseline recorded.

### Complexity

Large. The endpoint inventory is straightforward; the server authorization and
record-detail matrix is broader. Manual browser verification requires the dashboard
server running with a populated chain.

### Stop Conditions

- Dashboard server does not bind to loopback by default.
- Local CORS boundary is not enforceable.
- Any read-only endpoint mutates chain/runtime/export/config/telemetry/trouble
  state.
- Export data can be pulled without valid scoped token.
- Critical UI rendering failures (windows don't open, data doesn't display,
  JavaScript errors block interaction).

Executor: Cecil for API tests and endpoint inventory; Greg for manual browser
verification  
Classification: BUILD / browser verification

## Gate 3: Website and Worker Testing

### Work

Run website and Worker checks against a Cloudflare Pages preview first, then
run live smoke after preview passes.

Automated checks (Cecil):

- Route/redirect behavior.
- Orphaned page scan.
- Terminology sweep.
- Security header presence.
- Worker endpoint exposure and auth checks.
- Malformed/oversized telemetry payload rejection.

### Browser Verification (manual — Greg)

Greg navigates the preview deployment through a browser. These checks catch
rendering issues, broken interactions, and asset failures that automated
crawls miss. Browser verification is additive — automated checks and manual
review remain the acceptance criteria.

Browser checks against preview:

- Navigate every page in the primary nav (Product, Demo, Pricing, Docs,
  Blog) and confirm each loads without errors.
- Pricing simulation: select each of the five tiers and confirm the
  display updates.
- Demo: load at least two persona scenarios and confirm the simulation
  renders with data.
- Contact form renders and all fields are interactable.
- Navigate to `/about/trusting-us/` and confirm redirect to `/trust/`.
- Navigate to a known 410 Gone route and confirm the response.
- Docs pages: open at least three docs pages and confirm content renders
  with no broken images or missing CSS.
- No JavaScript console errors across the walkthrough.

Manual checks (Greg):

- License purchase / personal license flow or documented Stripe gap.
- License replacement cannot be triggered by email knowledge alone.
- Feedback/contact/communications flows.
- Docs accuracy against current product behavior.

### Likely Files / Artifacts

- `release-evidence/<rc>/05-gate-3-website-worker/gate-3-preview-results.md`
- `release-evidence/<rc>/05-gate-3-website-worker/gate-3-browser-results.md`
- `release-evidence/<rc>/05-gate-3-website-worker/gate-3-live-smoke.md`
- Optional crawl/redirect output files.

### Likely Source Areas

- `atested.com/`
- Cloudflare Worker source and config
- `_redirects`
- Website docs pages

### Dependencies

Release candidate preview deployment available.

### Complexity

Medium to large. Cloudflare preview setup and Stripe status may be the most
operationally sensitive parts.

### Stop Conditions

- License replacement remains abusable by email knowledge alone.
- Admin endpoints are publicly callable.
- Docs contain release-blocking stale claims about chain integrity, telemetry,
  exports, or evidence verification.
- Critical browser rendering failures on primary pages.

Executor: Cecil for automated checks; Greg
for manual flow and docs review  
Classification: BUILD / browser verification / manual verification

## Gate 4: Release Candidate Adversarial Scan

### Work

Freeze exact product and website commits, then run an independent adversarial
scan:

- Secret scan.
- Dependency audit.
- Static trust-surface review against inventory.
- Dashboard API abuse.
- Worker abuse.
- Classifier bypass matrix.
- Chain tamper matrix.
- Evidence package tamper matrix.
- External viewer tamper matrix.
- Export token abuse for implemented scope.

### Likely Files / Artifacts

- `release-evidence/<rc>/06-gate-4-adversarial-scan/gate-4-results.md`
- Dependency scan outputs.
- Secret scan outputs.
- Accepted or remediated findings log.

### Likely Tools

- Existing test runner.
- `pip-audit` or equivalent.
- JS dependency audit tooling available in the website/dashboard projects.
- Secret scanning tool chosen by executor.
- Manual source review.

### Dependencies

Gates 0 through 3 complete, RC frozen.

### Complexity

Large.

### Stop Conditions

Any critical or high finding not fixed or explicitly accepted by Tier 0.

## Gate 5: Operational Dry Run

### Work

Greg runs Atested as a real operator using a clean runtime directory:

- Fresh install.
- Trial license.
- Personal license or documented Stripe gap.
- Real proxy traffic through at least one provider.
- At least 50 chain records across sessions.
- Normal restart continuity.
- Simulated integrity violation and restart.
- Runtime policy rules change.
- Evidence package export.
- Clean-browser-profile viewer test.
- Trouble reports from multiple windows.
- Telemetry opt-in/opt-out.
- Archived chain walking.
- Seven predefined reports.
- Configuration unlock and policy viewing.

### Browser Verification of Evidence Viewer (manual — Greg)

After Greg creates an evidence package during the dry run, Greg opens the
extracted `viewer.html` in a browser and verifies:

- File picker or drag-and-drop accepts companion files.
- Password entry dialog appears.
- Wrong password is rejected with a clear error.
- Correct password triggers decryption and verification.
- Non-technical view renders plain-language explanations.
- Technical view renders manifest, encryption parameters, public key
  fingerprint, and record-level hash linkage table.
- No download controls for decrypted data are present.
- No JavaScript console errors.

This is the dry-run browser-driven viewer check.

### Likely Files / Artifacts

- `release-evidence/<rc>/07-gate-5-operational-dry-run/gate-5-dry-run.md`
- `release-evidence/<rc>/07-gate-5-operational-dry-run/gate-5-viewer-browser-results.md`
- Preserved dry-run `gov_runtime/`.
- Sample evidence package.
- Viewer verification notes/screenshots if available.

### Dependencies

Gate 4 complete or no blocking findings remain.

### Complexity

Medium. Mostly manual execution, but thorough.

### Stop Conditions

- Product requires code edits or manual patching to complete core flows.
- Evidence package cannot be opened and verified in clean browser profile.
- Integrity failures are not visible/actionable.

Executor: Greg for operational scenarios and browser-based viewer
verification  
Classification: manual verification / browser verification

## Post-Gate: Git History Rewrite

### Work

After all gates pass and the release report draft exists, Cecil performs the
git history rewrite with the safeguards from the spec:

- Create a full mirror backup before rewriting.
- Run `git-filter-repo` on a disposable clone first.
- Record old HEAD to new HEAD mapping for all affected repos.
- Document the force-push plan.
- Re-clone or hard-refresh local working copies after rewrite.
- Confirm Cloudflare Pages, GitHub branch protections, and deployment settings
  point to the intended post-rewrite branch.
- Preserve the rewrite log as a release evidence artifact.

After the rewrite completes, run post-rewrite verification, then update the
release report with post-rewrite SHAs.

### Post-Rewrite Verification

These checks run after the rewrite but before the release report is finalized.

**Local verification (before force-push):**

- Confirm private file removal: `git log --all --diff-filter=A -- <file>`
  for each of the 7 private process-doc files must return empty. If any
  file appears in any commit, the rewrite is incomplete.
- Confirm author email rewrite: `git log --format='%ae' | sort -u` must
  show only intended email addresses. Any non-target email means the
  rewrite filter was incomplete.
- Re-run secret scan (`trufflehog` or `gitleaks`) against the full
  rewritten history. The rewrite changes commit contents, so the scan
  must run again — secrets could exist in files outside the seven
  targeted for removal.

**Remote verification (after force-push):**

- Clone the repo fresh from GitHub into a new directory (not a fetch into
  the existing clone). Verify the fresh clone does not contain the private
  files in any commit.
- Attempt to fetch old pre-rewrite commit SHAs by URL
  (`https://github.com/atested/governance-layer/commit/<old-sha>`). If
  GitHub still serves the old objects, document this and evaluate whether
  GitHub support contact is needed to trigger garbage collection. If the
  repo is still private at this point, the exposure is limited to existing
  collaborators.
- Verify Cloudflare Pages deployment triggered successfully from the
  rewritten branch and the site is serving correctly.

### Likely Files / Artifacts

- `release-evidence/<rc>/08-git-history-rewrite/rewrite-plan.md`
- `release-evidence/<rc>/08-git-history-rewrite/old-to-new-sha-map.md`
- `release-evidence/<rc>/08-git-history-rewrite/rewrite-log.txt`
- `release-evidence/<rc>/08-git-history-rewrite/post-rewrite-verification.md`
- `release-evidence/<rc>/08-git-history-rewrite/post-rewrite-secret-scan.txt`
- Mirror backup outside the working clone

### Dependencies

All gates passed. Release report draft exists.

### Complexity

Large. Destructive history rewrite, force-push coordination, deployment
checks, and local clone refresh.

### Stop Conditions

- Rewrite fails.
- Any private file appears in any commit of the rewritten history.
- Any non-target author email survives the rewrite.
- Post-rewrite secret scan finds secrets in the rewritten history.
- Cloudflare/GitHub deployment configuration points to the wrong branch after
  rewrite.
- Local repos cannot be refreshed cleanly.
- Fresh clone from GitHub contains private files (remote verification failure).

Executor: Cecil  
Classification: BUILD  
Prerequisite: `git-filter-repo` installed

## Final Release Report

### Work

Produce a final release report that records:

- Pre-rewrite and post-rewrite product, website, and state repo SHAs.
- Git rewrite outcome and evidence.
- Test inventory summary.
- Gate 0 through Gate 5 results.
- Dependency and secret scan status.
- Critical/high findings and dispositions.
- Accepted risks and deferrals.
- Evidence artifact index.
- Release recommendation: ready / not ready.

### Likely File

- `release-evidence/<rc>/release-report.md`

### Dependencies

All gates complete.

### Complexity

Medium.

## Dispatch Sequence

1. `RELEASE-PREQ-TEST-INVENTORY` — Cecil  
   Cecil investigates current coverage and writes the trust-surface inventory.

2. `RELEASE-G0-BLOCKER-TESTS` — Cecil  
   Cecil writes and runs targeted adversarial blocker tests.

3. `RELEASE-G1A-CLASSIFIER-POLICY-TESTS` — Cecil

4. `RELEASE-G1B-CHAIN-INTEGRITY-TESTS` — Cecil

5. `RELEASE-G1C-VERIFIER-ARCHIVE-TESTS` — Cecil

6. `RELEASE-G1D-APPROVAL-EXPORT-AUTH-TESTS` — Cecil

7. `RELEASE-G1E-EVIDENCE-VIEWER-TESTS` — Cecil  
   Final step: run full product suite and record post-Gate-1 regression
   baseline in `release-evidence/<rc>/03-gate-1-product-core/gate-1-rollup.md`.

8. `RELEASE-G2-DASHBOARD-API-TESTS` — Cecil  
   Cecil: API tests and endpoint inventory.  
   Browser verification: Greg manual during Gate 5 dry run.

9. `RELEASE-G3-WEBSITE-WORKER-PREVIEW` — Cecil + Greg  
   Cecil: automated checks (redirects, headers, terminology, Worker endpoints).  
   Greg: manual flow verification, docs accuracy review, and browser
   walkthrough of preview site.

10. RC freeze (Tier 0 tags the commit — not a dispatch).

11. `RELEASE-G4-ADVERSARIAL-SCAN` — Codex  
    Independent adversarial review. Codex did not write the code under
    review. This is Codex's sole dispatch — prioritize it when capacity
    is available. If Codex capacity is constrained mid-scan, focus on:
    trust-surface review, secret scan, and classifier bypass matrix first;
    API/Worker abuse tests second (Cecil's Gate 0–2 tests already cover
    those surfaces).

12. `RELEASE-G5-OPERATIONAL-DRY-RUN` — Greg  
    Greg: manual operator scenarios including dashboard UI walkthrough
    and evidence viewer browser verification.

13. `RELEASE-REPORT-DRAFT` — Cecil  
    Cecil assembles from gate artifacts. Records pre-rewrite SHAs.

14. `RELEASE-GIT-HISTORY-REWRITE` — Cecil  
    Cecil performs the rewrite, runs post-rewrite verification, updates
    release report with post-rewrite SHAs.

Dispatches 1–9 and 13–14 are Cecil. Dispatch 11 is Codex — the only
dispatch that requires an independent executor. Dispatch 12 is Greg.
Browser verification checks described in Gates 2, 3, and 5 are covered
by Greg's manual work during Gate 5 (dashboard) and Gate 3 (website).
If Codex browser tools become available for supplementary checks in
future releases, they can be added back without changing the gate
structure.

Gates 2 and 3 may overlap after Gate 1 baseline if executor capacity exists.
Gate 4 must wait for RC freeze. Gate 5 should wait until Gate 4 has no
unresolved critical/high findings. Git rewrite runs only after all gates pass.

Secret scanning tool: `trufflehog` (or `gitleaks` if unavailable in Cecil's
environment). Executor installs at Gate 4 time.

## Resolved Planning Questions

- **RC identifier format**: `rc-NNN` where NNN is the dispatch number at
  freeze time.
- **Evidence location**: `governance-layer/release-evidence/<rc>/` in the
  product repo.
- **Secret scanning tool**: `trufflehog` preferred, `gitleaks` fallback.
- **Cloudflare preview**: Pages generates preview URLs automatically for
  non-main branches. Cecil can run Gate 3 automated checks against the
  preview URL if Cecil has push access to the `atested.com` repo. Greg
  handles live smoke and manual flow checks.
- **Accepted-risk log location**: `release-evidence/<rc>/accepted-risks.md`.
  Each release has its own risk log.
- **Test inventory format**: Markdown only for first release.
- **Git history rewrite timing**: after all gates pass, before public release.

## Definition of Done

This plan is complete. All planning questions are resolved. The dispatch
sequence is approved. Execution begins with `RELEASE-PREQ-TEST-INVENTORY`.

Executors:

- Dispatches 1–9, 13–14: Cecil.
- Dispatch 11 (Gate 4): Codex — sole independent executor dispatch.
- Dispatch 12 (Gate 5): Greg.
- RC freeze (step 10): Tier 0, not a dispatch.

Browser verification from Gates 2, 3, and 5 is covered by Greg's manual
work. Codex browser tools can be added as supplementary checks in future
releases without changing the gate structure.
