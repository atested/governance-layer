# Atested: Operator Identity Layer

## Design — Cryptographic Binding of Approvals to Authenticated Humans

**Date:** 2026-04-09
**Author:** Atested
**Status:** Design — pre-implementation
**Classification:** Architecture extension
**Companion docs:** [atested-v3-design.md](atested-v3-design.md) (v3 proxy architecture), [INVARIANTS.md](../INVARIANTS.md) (chain integrity invariants INV-001 through INV-010)

---

## 1. Purpose

This document defines the operator identity layer for Atested: the mechanism
by which approvals in the governance chain are bound to authenticated humans.

The v3 architecture design (atested-v3-design.md) specifies how tool calls are
classified, policy-evaluated, and recorded. It does not specify who is behind
an approval when an operator overrides a DENY decision. This document fills
that gap. It defines how operators are identified, how their identity is
cryptographically bound to their approvals, how identity is established at
license issuance, how credentials are protected on the dashboard machine, how
the chain records identity, and how recovery works when credentials are lost.

---

## 2. Problem Statement

D-035 closed the governance loop end-to-end: approvals issued in the dashboard
now override prior DENY decisions in the live proxy. This made operator
identity load-bearing for the first time. An approval is no longer just an
audit annotation — it is an authoritative override of policy.

Both the dashboard and the Atested CLI currently accept arbitrary operator
strings with no authentication. The chain records `operator: <whatever was
typed>` as if it were a real identity. Outstanding Issues 1 (per-agent approval
scoping) and 2 (operator identity verification) in STATE_CURRENT.md identify
this as a foundational gap that must be closed before the product can credibly
market provable governance.

This design addresses Issue 2 directly. It specifies: identity establishment,
cryptographic binding, credential storage, session management, chain schema,
re-licensing, recovery, and honest limits.

---

## 3. Design Principles

1. **Every approval is cryptographically bound to a registered, authenticated
   human.** No anonymous approvals. No approvals attributed to unverified
   strings.

2. **The chain tells the truth about who decided what.** Pre-identity
   decisions are not laundered into post-identity attribution. Trial approvals
   carry a "trial" sentinel, not an operator name.

3. **Identity is a property of the licensing relationship, not the install.**
   Operator identity is established at license issuance and follows the
   license. A reinstall does not require re-enrollment. A new machine does not
   invalidate operator credentials.

4. **Single product, single auth flow.** Personal tier and paid tiers use the
   same mechanism. There is no "lite" auth for free users. Consistency of the
   chain across all users is more important than reducing friction for one
   tier.

5. **Standard cryptographic primitives only.** TOTP (RFC 6238) for the
   authentication factor, OS-native secure storage for the seed at rest. No
   invented protocols.

6. **Honest about limits.** This design protects against external attackers
   who lack OS-level access. It does not protect against an attacker with code
   execution as the dashboard user during an active unlock session. This is
   the boundary of any software-only credential storage.

---

## 4. Roles

### Signatory

The legal counterparty to Atested for a license. The signatory provides their
own name and email at purchase, receives the license file and contractual
communications. The signatory does not necessarily have approval authority.

On Personal tier, signatory and operator are the same person.

### Operator

The human who actually issues approvals. Named in the chain when an approval
is recorded. Has their own name and email, distinct from the signatory's —
except on Personal tier, where they are identical.

### Operator count

Paid tiers allow a maximum of two operators per license: primary and backup.
Personal tier allows exactly one. The schema represents operators as a list to
permit future expansion, but the current product enforces these limits.

### Trial users

Anyone who has installed Atested but has not registered with atested.com.
Trial users have no signatory and no operator. They can issue a small number
of trial approvals for evaluation purposes (see §6).

---

## 5. License Lifecycle

### Install

User downloads and runs Atested. The dashboard starts in trial state (§6).

### License purchase

Signatory registers on atested.com, providing their name and email. Personal
tier registration is free and enforces signatory == operator. Paid tiers may
collect operator information at purchase or defer it to a later step.

### License delivery

Signatory receives the license file and contract. If operators were specified
at purchase, enrollment links are sent to them immediately. Otherwise no
enrollment links are sent yet.

### License activation

User points the running dashboard at the downloaded license file. The
dashboard:

1. Validates the licensing infrastructure's signature on the bundle.
2. Identifies registered operators (if any).
3. Contacts Cloudflare Workers to fetch each operator's TOTP seed material.
4. Stores the seeds locally (§8).

The dashboard transitions from trial state to one of two licensed states:

- **Awaiting operator enrollment** — no operators registered yet.
- **Fully licensed** — at least one operator is registered.

### Operator addition

Signatory logs into atested.com at any time and adds an operator (name, email)
to a license slot. Cloudflare Workers generates a TOTP seed for the new
operator and sends an enrollment link to the operator's email.

### Operator enrollment

Operator clicks the enrollment link from their phone within the link's
validity window: one-time use, expires 15 minutes after first open or 24 hours
absolute, whichever is sooner. The page displays a TOTP QR code. Operator
scans it into their authenticator app. The link is invalidated on
confirmation.

### Dashboard operator refresh

The dashboard polls Cloudflare on a schedule, or the user runs an explicit
refresh command, or the dashboard checks on next start. When a new operator's
seed becomes available, the dashboard fetches and stores it.

### Operator removal

Signatory removes an operator on atested.com. The next dashboard refresh
detects the removal and writes an operator removal event to the chain, deleting
the local seed. Prior approvals attributed to the removed operator remain in
the chain as historical facts.

### Re-licensing

Same as initial licensing but produces a new license file with new `issued_at`
and potentially new operators or new seeds. Dashboard activation of the new
license writes a re-licensing event to the chain. Prior approvals remain in
force. See §11 for the full re-licensing protocol.

---

## 6. Trial State

Trial state is the state of an installed but unregistered Atested instance.
Every install begins in trial.

Trial state grants a small fixed budget of trial approvals — exact count to be
determined during build, on the order of one to two. The goal is enough to
demonstrate the full approval flow end-to-end, not enough to support sustained
commercial operation.

Trial approvals are written to the chain with attribution to `"trial"` as a
sentinel operator and with an explicit `is_trial: true` marker. They are
clearly distinguished from licensed approvals in the audit trail.

When trial approvals are exhausted, the dashboard refuses further approvals
until the user registers (Personal tier or paid). The refusal message directs
the user to atested.com.

This intentional limit is the urgency-to-license signal. Users see how the
product works, exhaust their trial, and either license or stop.

**Auto-invalidation on registration.** On license activation with operator
registration, all existing trial approvals are auto-invalidated via the Clear
All Approvals mechanism (§11). The dashboard surfaces the list of invalidated
approvals with a pre-activation warning so the user understands what will
require re-approval. The operator's first approval after registration is a
fresh, attributed decision under their authority — not a rubber-stamp of trial
decisions.

---

## 7. Authentication: TOTP

The authentication factor is TOTP (RFC 6238).

### Seed generation

TOTP seeds are generated by the Atested licensing infrastructure (Cloudflare
Workers) at the time of operator registration. The seed is 160 bits, encoded
as base32, and delivered to the operator as a QR code on a one-time enrollment
page on atested.com.

### Seed custody

The seed is held in two places:

1. **The operator's authenticator app** on their phone.
2. **Cloudflare Workers** (encrypted at rest, indexed by license key + operator
   email) for delivery to the dashboard at license activation time.

### Seed delivery

The seed is delivered to the dashboard exactly once per operator per license,
at license activation. After activation, the dashboard does not need to
contact Cloudflare for routine approval operations.

### Validation

TOTP validation on the dashboard is standard: HMAC-SHA1 of (seed, current
30-second time bucket), truncated to a 6-digit code, with ±1 time bucket
tolerance for clock skew.

---

## 8. Credential Storage on the Dashboard

### Encrypted seed files

The TOTP seed for each operator is encrypted at rest with AES-256 and stored
as a file inside Atested's runtime directory. One encrypted blob per operator.

### Key storage

The AES-256 encryption key is stored in the OS-native secure credential store:

- macOS: Keychain
- Windows: Credential Manager
- Linux: Secret Service

Access is via the Python `keyring` library. Service name:
`com.atested.dashboard.totp_seed`. Account name: the operator's email.

### Unlock flow

At unlock time, the dashboard requests the AES key from the OS keychain. The
OS may prompt the operator for biometric or login authentication depending on
OS configuration. On success, the OS releases the key to the dashboard process
for the duration of the unlock session.

The dashboard reads the encrypted seed file, decrypts the seed into memory,
holds it for the unlock session, and uses it to validate TOTP codes the
operator types.

### Lock flow

At lock time (idle timer expiry, hard ceiling expiry, manual lock, or process
exit), the dashboard zeros the plaintext seed in memory. The encrypted file
remains on disk. The key remains in the keychain. Next unlock repeats the
cycle from the keychain request.

### Threat model

This design protects against attackers with filesystem read access who do not
also have OS-level credential access. It does not protect against an attacker
with code execution as the dashboard user during an active unlock session.

---

## 9. Unlock Session Model

An unlock session is opened when an operator successfully presents a valid
TOTP code to the dashboard or CLI.

### Session timers

Two timers govern session lifetime:

| Timer | Duration | Resets on activity? |
|---|---|---|
| Idle timer | 30 minutes | Yes — resets on each approval action |
| Hard ceiling | 1 hour from initial unlock | No |

Either expiry locks the session. Manual lock is also available at any time.

### Dashboard UI

The dashboard header displays the locked/unlocked state at all times. When
unlocked, it shows the operator's name and the time remaining on the hard
ceiling.

### CLI

The CLI mirrors the dashboard behavior:

- `atested unlock` opens a session.
- `atested lock` closes it.

CLI session state is stored in a local state file with restrictive permissions.
The state file holds only metadata: session ID, operator email, unlock time,
last activity time. The plaintext seed is never written to this state file —
it is decrypted from the encrypted seed file on each approval action and
discarded immediately after validation.

The CLI does not honor environment variables for TOTP codes. It does honor
`ATESTED_OPERATOR_EMAIL` for selecting which operator's session is being acted
on when multiple operators are configured.

Dashboard and CLI sessions are independent. Unlocking one does not unlock the
other.

---

## 10. Approval Record Schema

When an approval is issued during an unlock session, the chain record contains:

| Field | Source | Purpose |
|---|---|---|
| `operator_name` | License file (never user-typed) | Who approved |
| `operator_email` | License file | Operator contact identity |
| `signatory_name` | License file | Audit completeness |
| `license_key_fingerprint` | SHA-256 prefix of the license key | License binding |
| `seed_fingerprint` | SHA-256 prefix of the operator's TOTP seed | Credential rotation evidence |
| `source_ip` | HTTP request IP (dashboard) or `cli:local` (CLI) | Origin |
| `timestamp` | ISO-8601, server-side at write time | When |
| `unlock_session_id` | Random ID generated at unlock | Groups approvals by session |
| `validation_method` | `"totp"` (field exists for future flexibility) | How identity was verified |

**What is not stored in the chain:**

- The license key itself — only its fingerprint.
- The plaintext TOTP seed — only its fingerprint.

The `seed_fingerprint` changes on re-licensing if new seeds are issued,
providing visible evidence of credential rotation in the chain.

The approval record is written to the chain via the same INV-010 lock protocol
as all other writers.

---

## 11. Re-licensing and Clear All Approvals

### Re-licensing

Re-licensing produces a new license file with a new `issued_at` and
potentially new operators or new seeds. When the new license is activated, the
dashboard writes a re-licensing event to the chain recording:

- Previous license fingerprint
- New license fingerprint
- Previous operators
- New operators
- Timestamp

Prior approvals remain in force and remain attributed to whichever operator
made them at the time. Re-licensing does not invalidate prior approvals.

### Clear All Approvals

A deliberate, audited operation available to any unlocked operator via the
dashboard or CLI. It serves four use cases:

1. **Development test cleanup** — clear approvals accumulated during testing.
2. **Lockdown response** — revoke all standing approvals during a security
   incident.
3. **Periodic re-attestation** — force a fresh round of human review.
4. **Operator handoff** — incoming operator starts with a clean slate.

### Confirmation

The Clear All Approvals UX requires the operator to type a confirmation token
(the word "CLEAR" or the count of approvals being cleared) to prevent
muscle-memory accidents.

### Chain event

The operation writes a single clearance event to the chain naming:

- The operator who invoked it
- Timestamp
- Count of approvals invalidated
- Optional reason field

It does not delete chain records. It appends an invalidation marker that
subsequent policy evaluation respects. After the clearance event, all
previously-approved operations revert to their pre-approval policy state
(typically DENY) until re-approved.

### Bounded undo

For 15 minutes after a clearance event is written, any unlocked operator may
issue an "undo clearance" command that writes a reversal event to the chain.
The reversal restores the prior approval semantics for any operation that was
approved before the clearance.

After the 15-minute window expires, the clearance is permanent. The only path
to restoring prior approval state is to re-approve manually.

The dashboard surfaces the undo option prominently during the 15-minute window
with the absolute expiry time displayed. No live countdown timer.

### Chain completeness

Every state change in this flow — the original clearance, an undo if it
occurs, the expiration of the undo window if it occurs without undo — is a
chain event with full attribution and timestamp. The chain history is fully
recoverable at any point.

### Trial auto-invalidation

The trial-approval auto-invalidation described in §6 uses this exact
mechanism, triggered automatically at the moment of operator registration
rather than by an explicit operator command.

---

## 12. Recovery

The signatory is responsible for managing operator credentials.

### Design rationale

The system does not have an automated self-service recovery flow. Email-based
self-service recovery would shift the security anchor from the licensing
relationship to the operator's email account, creating a new attack vector:
compromised operator email = compromised credential. The signatory-mediated
recovery model preserves the principle that the licensing entity controls the
security of the operator layer.

This puts a real dependency on signatory responsiveness for credential
recovery. For Personal tier users, where signatory and operator are the same
person, this means: "I lost my phone, now I have to contact Atested support
and wait for a response before I can issue any approvals." Free-tier support is
the limit of recovery responsiveness for free users. Users who find this
unacceptable should upgrade to a paid tier with SLA-backed support.

### Recovery scenarios

**Lost phone (authenticator app data lost).**
Signatory contacts Atested support. Support authorizes re-enrollment.
Cloudflare generates a new seed. New enrollment link sent to operator. Operator
scans new QR code. New seed propagates to dashboard on next refresh.
Re-licensing event written to chain.

**Lost OS keychain (machine wipe, OS reinstall).**
User reinstalls Atested, re-activates license. Dashboard re-fetches the
existing seed from Cloudflare (same seed, no re-enrollment needed). Keychain
entries are re-created. Operator's phone is unchanged.

**Lost license file.**
Signatory re-downloads from atested.com using their account credentials. No
re-enrollment needed.

**Lost everything (phone, keychain, license file).**
Full re-licensing from scratch.

---

## 13. Honest Limits

- The design protects against attackers with filesystem read access. It does
  not protect against attackers with code execution as the dashboard user
  during an active unlock session.

- The cryptographic binding ensures whoever holds the TOTP credential can only
  ever approve as the named operator in the license. It does not verify that
  the named operator corresponds to a real human with that legal name. Identity
  verification beyond self-asserted name + email is deferred until a
  regulated-industry buyer requires it.

- Defending against a compromised dashboard process, a compromised licensing
  infrastructure, or a compromised authenticator app on the operator's phone is
  out of scope. Each would require additional layers (hardware security
  modules, secure boot, attested execution environments) that are not part of
  this design.

- The operator identity layer is one layer of defense. The chain integrity
  layer (INV-004, INV-010), the policy layer, and the classifier layer are
  independent and continue to function regardless of operator identity status.

---

## 14. Telemetry

This design does not specify telemetry from the dashboard back to atested.com.
Telemetry — including aggregate Approve/Deny counts feeding the public-facing
counters — is anticipated as a future feature consuming the chain data. Its
design (what is reported, how it is anonymized, opt-out behavior, privacy
considerations) is out of scope for this document and will be addressed in a
separate design conversation.

---

## 15. Build Sequence

This section is informational only. It describes the anticipated dispatch
sequence to implement this design. The actual dispatches are not authorized
by this document.

**L-1: Licensing infrastructure** (atested.com + Cloudflare Workers + Stripe).
Add signatory and operator field collection to checkout. Add the standalone
"register operator" flow on atested.com for operators added after purchase.
Generate TOTP seeds at issuance and at operator addition. Sign license bundles
with the licensing infrastructure private key. Implement the enrollment link
flow with one-time use and time limits. Implement the seed delivery endpoint
authenticated by license key.

**L-2: License file format and validator** (governance-layer). Define the
signed license file format. Implement local validation. Implement license
activation in the dashboard and CLI. Implement seed fetch from Cloudflare.
Implement encrypted seed storage and OS keychain integration via the `keyring`
library.

**L-3: TOTP unlock and session management** (governance-layer). Implement
unlock and lock flow in dashboard. Implement idle and hard-ceiling timers.
Implement locked/unlocked header indicator. Implement CLI `atested unlock` and
`atested lock` commands.

**L-4: Approval store and chain schema update** (governance-layer). Update
chain record schema for the new approval fields. Update approval store to
require unlocked session. Implement seed and license fingerprint computation.
Wire approval flow through unlock session. Update INVARIANTS.md if any new
invariants are introduced.

**L-5: Re-licensing, Clear All Approvals, bounded undo, and trial mode**
(governance-layer). Implement re-licensing detection on license activation.
Implement Clear All Approvals UX in dashboard and CLI. Implement bounded undo
with 15-minute window. Implement trial state, trial approval budget, and
auto-invalidation on operator registration.

**L-6: End-to-end test pass** (governance-layer). Comprehensive test of the
full flow from license purchase through enrollment, activation, unlock,
approval, re-licensing, clearance, undo, and recovery.

L-1 must land first — it is the dependency for everything else and lives in a
different repo. L-2 through L-5 are governance-layer work and may be sequenced
or parallelized depending on the operating mode at the time. L-6 lands last.
