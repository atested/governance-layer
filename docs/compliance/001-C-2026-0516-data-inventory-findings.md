# 001-C-2026-0516: Data Inventory and Privacy Reconciliation Findings

**Dispatch**: 001-C-2026-0516 (C-series inaugural)
**Kind**: INVESTIGATE
**Date**: 2026-05-16
**Status**: COMPLETE
**Scope**: Atested hosted infrastructure data collection, retention, and reconciliation against deployed legal content

This document contains four parts:
1. Data Inventory
2. Reconciliation against deployed Privacy Policy, Terms, and Trust content
3. RoPA-input facts (structured for Records of Processing Activities)
4. Data-flow statement (customer-side vs. hosted)

---

## Part 1: Data Inventory

### 1.1 Deployed Workers

Two Cloudflare Workers are deployed on atested.com infrastructure. One Cloudflare Pages Functions middleware handles routing.

#### Worker 1: atested-license-worker

| Attribute | Value |
|---|---|
| Source file | `workers/license-worker.js` |
| wrangler.toml | `workers/wrangler.toml` |
| Routes | `atested.com/api/*`, `atested.com/license` |
| KV bindings | 7 (LICENSE_KV, CAPTURE_STORE, STRIPE_EVENTS, REVOCATION_LIST, PENDING_NOTIFICATIONS, PLUS_LICENSE_CACHE, SHARING_AUTHORIZATIONS) |
| Secrets | 5 (STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET, LICENSE_SIGNING_KEY, ADMIN_API_KEY) |
| Email binding | SEND_EMAIL (Cloudflare Email Workers) |
| Execution | Cloudflare global edge network |

Endpoints served:

| Method | Path | Function |
|---|---|---|
| POST | `/api/checkout` | Create Stripe Checkout session |
| POST | `/api/stripe/webhook` | Stripe webhook (license gen + event archival) |
| GET | `/license` | License key lookup by session_id |
| POST | `/api/replace-key` | Key replacement (email verification flow) |
| POST | `/api/personal-license` | Personal tier $0 license issuance |
| POST | `/api/feedback` | Signed feedback artifact ingestion |
| POST | `/api/telemetry` | Signed telemetry artifact ingestion |
| GET | `/api/stats` | Public aggregate stats |
| POST | `/api/capture` | Analytics event + contact form capture |
| POST | `/api/admin/modify-license` | Admin: modify license (ADMIN_API_KEY) |
| POST | `/api/admin/revoke-license` | Admin: revoke license (ADMIN_API_KEY) |
| GET | `/api/admin/license-status` | Admin: license status query (ADMIN_API_KEY) |
| POST | `/api/admin/update-plus-cache` | Admin: update Plus machine count cache (ADMIN_API_KEY) |
| POST | `/api/admin/authorize-sharing` | Admin: authorize machine sharing (ADMIN_API_KEY) |
| POST | `/api/admin/revoke-machine` | Admin: revoke machine authorization (ADMIN_API_KEY) |

#### Worker 2: atested-version-worker

| Attribute | Value |
|---|---|
| Source file | `workers/version-worker.js` |
| wrangler.toml | `workers/version-wrangler.toml` |
| Routes | `version.atested.com/*` |
| KV bindings | None |
| Secrets | None |
| Execution | Cloudflare global edge network |

Endpoints served:

| Method | Path | Function |
|---|---|---|
| GET | `/check?v=<semver>` | Returns latest version metadata, whether update is available |

This worker is stateless. It receives only a version string query parameter and returns static JSON. No data is stored.

#### Cloudflare Pages Functions middleware

| Attribute | Value |
|---|---|
| Source file | `functions/_middleware.js` |
| Function | Route-level 301 redirects and 410 Gone responses for deleted pages |
| Data collection | None |

### 1.2 KV Namespace Inventory

#### KV 1: LICENSE_KV (id: b88f1d0095b4413c82c0970b953dac10)

| Key pattern | Fields stored | Source | Retention | Readers |
|---|---|---|---|---|
| `<stripe_session_id>` | license_key, license_id, tier, organization, origin, email | Stripe webhook (checkout.session.completed) | 30-day TTL | `/license` lookup |
| `license:<license_id>` | license_key, license_id, tier, organization, origin, customer_id, email, issued_at, exp, modification_type, reason, notes | Stripe webhook, `/api/personal-license`, `/api/admin/modify-license` | No TTL (permanent) | Admin status, telemetry handler, revocation handler |
| `email:<email>` | license_key, license_id, tier, organization, origin, issued_at, customer_id, stripe_session_id | Stripe webhook, `/api/personal-license`, `/api/replace-key` | No TTL (permanent) | Checkout upgrade check, Personal reinstall, Key replacement |
| `feedback:<artifact_hash>` | `"1"` (presence flag) | `/api/feedback` | 30-day TTL | Feedback handler (replay protection) |
| `note:<artifact_id>` | note (text), timestamp, tier | `/api/feedback` (only when permission_to_use is true) | 365-day TTL | Not exposed via any endpoint |
| `telemetry:<chain_hash>:<date>` | `"1"` (presence flag) | `/api/telemetry` | 2-day TTL | Telemetry handler (period dedup) |
| `telemetry:hash:<artifact_hash>` | `"1"` (presence flag) | `/api/telemetry` | 30-day TTL | Telemetry handler (exact dedup) |
| `telemetry:latest:<chain_hash>` | allow, deny, deterministic, judgment (integers), license_id, version, last_seen (ISO timestamp), unique_users | `/api/telemetry` | No TTL (permanent) | Telemetry handler (delta calculation) |
| `stats:total_allow` | Integer string | `/api/telemetry` aggregation | No TTL (permanent) | `/api/stats` (public) |
| `stats:total_deny` | Integer string | `/api/telemetry` aggregation | No TTL (permanent) | `/api/stats` (public) |
| `stats:total_deterministic` | Integer string | `/api/telemetry` aggregation | No TTL (permanent) | `/api/stats` (public) |
| `stats:total_judgment` | Integer string | `/api/telemetry` aggregation | No TTL (permanent) | `/api/stats` (public) |
| `stats:installations` | Integer string | `/api/telemetry` (new chain_hash) | No TTL (permanent) | `/api/stats` (public) |
| `stats:feedback_count` | Integer string | `/api/feedback` | No TTL (permanent) | `/api/stats` (public) |
| `stats:telemetry_count` | Integer string | `/api/telemetry` | No TTL (permanent) | Not exposed via endpoint |
| `replace-verify:<email>` | code (6-digit string), created_at (epoch ms), attempts (integer) | `/api/replace-key` step 1 | 15-minute TTL | `/api/replace-key` step 2 |
| `admin:dedup:<request_hash>` | Full license result JSON | `/api/admin/modify-license` | 60-second TTL | Admin modify (idempotency) |

#### KV 2: CAPTURE_STORE (id: 986ca4c926674f85b9b1564eb19acee1)

All entries stored with 90-day TTL. Key pattern: `events:<date>:<seq>`.

**Pageview events** (source: `capture.js` on every atested.com page):

| Field | Description |
|---|---|
| type | `"pageview"` |
| visitor_id | First-party cookie (`atested_vid`), 365-day lifetime, generated client-side |
| session_id | sessionStorage value (`atested_sid`), per-tab lifetime |
| path | URL pathname (e.g., `/pricing/`) |
| referrer_class | Classified referrer: direct, internal, search, social, external, unknown |
| referrer_raw | Full `document.referrer` string or null |
| page_index | Integer, page count in session sequence |
| timestamp | ISO 8601 UTC |
| returning | Boolean, true if `atested_vid` cookie existed before this pageview |
| screen_width | `window.innerWidth` in pixels |

**Page exit events** (source: `capture.js` on `beforeunload` / `visibilitychange`):

| Field | Description |
|---|---|
| type | `"pageexit"` |
| visitor_id | Same as above |
| session_id | Same as above |
| path | Same as above |
| duration_ms | Milliseconds spent on page |
| timestamp | ISO 8601 UTC |

**Outbound click events** (source: `capture.js` on external link clicks):

| Field | Description |
|---|---|
| type | `"outbound_click"` |
| visitor_id | Same as above |
| session_id | Same as above |
| path | Page where click occurred |
| target_url | Full URL of the external link |
| timestamp | ISO 8601 UTC |

**Contact form submissions** (source: `/contact/index.html` form handler):

| Field | Description |
|---|---|
| event_type | `"contact_submission"` |
| timestamp | ISO 8601 UTC |
| topic | One of: support, sales, enterprise, journalist, researcher, partner, investor, security, other |
| topic_data | Object, varies by topic (see below) |
| contact.name | Submitter name (required) |
| contact.email | Submitter email (required) |
| contact.organization | Organization name (optional) |
| contact.role | Role/title (optional) |
| contact.prior_contact | `"first_time"` or `"returning"` |
| contact.copy_requested | Boolean |
| enrichment_hints.email_domain | Extracted from email |
| additional_context | Freeform text (optional) |

Topic-specific data within `topic_data`:
- **support**: message, priority
- **sales**: company, size, industry, timeline, challenges, website
- **enterprise**: company, size, industry, process, notes
- **journalist**: outlet, topics[], needs[], format, deadline, link
- **researcher**: institution, field, focus, link
- **partner**: company, category[], description
- **investor**: focus, notes
- **security**: description
- **other**: message, interest[]

#### KV 3: STRIPE_EVENTS (id: d402be72e1554a7db847f37727ac61ff)

| Key pattern | Fields stored | Source | Retention | Readers |
|---|---|---|---|---|
| `stripe:<timestamp>:<event_id>` | Raw Stripe webhook event JSON | Stripe webhook (customer.created, customer.updated, customer.subscription.created/updated/deleted, invoice.paid, invoice.payment_failed, charge.succeeded, charge.failed) | 90-day TTL | Not exposed via endpoint; ingested by atested-dashboard scripts |

Stripe events contain Stripe-managed fields including customer email, name, subscription details, invoice amounts, and charge outcomes. The raw event JSON is stored as-is from Stripe.

#### KV 4: REVOCATION_LIST (id: 90bb24a855ab4459abf7f862711ae16a)

| Key pattern | Fields stored | Source | Retention | Readers |
|---|---|---|---|---|
| `<license_id>` | license_id, reason, reason_category, revoked_at | Admin revoke, upgrade path, reinstall | No TTL (permanent) | Telemetry handler (notification delivery), sharing authorization handler |

#### KV 5: PENDING_NOTIFICATIONS (id: 1fb77dd9a299473298d27eb18645dd42)

| Key pattern | Fields stored | Source | Retention | Readers |
|---|---|---|---|---|
| `<license_id>` | JSON array of notification objects. Each: type, notification_id, timestamp, priority, payload (license_id, token, tier, origin, effective_date, expires, modification_type, reason, previous_tier, new_tier, revoked_at — fields vary by notification type) | License generation, admin modify/revoke, upgrade, reinstall | No TTL (cleared when acknowledged via telemetry) | Telemetry handler (delivery channel) |

#### KV 6: PLUS_LICENSE_CACHE (id: 7bd69c048e654358b06627cd8ef26f63)

| Key pattern | Fields stored | Source | Retention | Readers |
|---|---|---|---|---|
| `<license_id>` | license_id, active_machine_count, machine_limit, updated_at, warmed_from | Admin update-plus-cache, sharing authorization (auto-increment), dashboard warm | No TTL (permanent) | Sharing authorization handler |

#### KV 7: SHARING_AUTHORIZATIONS (id: 49e47a64334748478cb01b4556b1518e)

| Key pattern | Fields stored | Source | Retention | Readers |
|---|---|---|---|---|
| `<license_id>:<fingerprint>` | license_id, fingerprint (machine identity hash), tier, authorized_at | Admin authorize-sharing | No TTL (permanent) | Admin revoke-machine |

### 1.3 Stripe Integration Boundary

**What the Worker sends to Stripe (Stripe becomes data controller for PCI data):**

| Data | Endpoint | Context |
|---|---|---|
| Customer name | `POST /v1/customers` | Personal tier registration |
| Customer email | `POST /v1/customers` | Personal tier registration |
| Customer phone (optional) | `POST /v1/customers` | Personal tier registration |
| Tier metadata (`metadata[tier]`) | `POST /v1/customers` | Personal tier registration |
| Subscription creation | `POST /v1/subscriptions` | $0 Personal or paid tier |
| Subscription cancellation | `DELETE /v1/subscriptions/<id>` | On upgrade from Personal |
| Checkout session parameters | `POST /v1/checkout/sessions` | Paid tier purchase (includes success/cancel URLs, org name custom field, price ID) |

**What Stripe holds that the Worker never receives:**

| Data | Notes |
|---|---|
| Payment card number (PAN) | Entered on Stripe-hosted checkout page |
| CVV/CVC | Never leaves Stripe checkout |
| Card expiry date | Never leaves Stripe checkout |
| Billing address | Collected by Stripe if configured |
| Bank account details | N/A for card payments |

**What the Worker receives back from Stripe:**

| Data | Via | Context |
|---|---|---|
| `session.id` | Webhook payload | Checkout session completed |
| `session.customer_details.email` | Webhook payload | Customer email from checkout |
| `session.custom_fields[0].text.value` | Webhook payload | Organization name entered in checkout |
| `session.customer` | Webhook payload | Stripe customer ID |
| Line item price IDs | API call to `GET /v1/checkout/sessions/<id>/line_items` | Tier determination |
| Customer search results | API call to `GET /v1/customers/search` | Key replacement verification |
| Customer list by email | API call to `GET /v1/customers?email=<email>` | Personal reinstall detection |

The PCI boundary is clean: payment card data is entered exclusively on Stripe's hosted checkout page and never transits Atested infrastructure.

### 1.4 Google Fonts

All pages on atested.com include:
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

The browser makes direct requests to Google servers. Atested does not proxy, cache, or intermediate font requests. Google receives the visitor's IP address, user agent, and referrer header as part of normal HTTP requests.

### 1.5 Email Sending

The Worker uses Cloudflare Email Workers (`SEND_EMAIL` binding) to send verification emails for key replacement. Emails are sent from `noreply@atested.com` to the customer's email address. Content is a 6-digit verification code with a 15-minute expiry. Cloudflare Email Routing processes the email delivery.

### 1.6 Data Residency and Execution Region

| Component | Execution location | Data storage location |
|---|---|---|
| Cloudflare Workers | Nearest edge PoP to requesting client | N/A (stateless compute) |
| Cloudflare KV | N/A (accessed via Workers) | Globally replicated; no region pinning available on standard KV |
| Cloudflare Pages | Nearest edge PoP | N/A (static assets cached at edge) |
| Stripe | Stripe's infrastructure (US-based, with global presence) | US (Stripe's primary data center) |
| Google Fonts | Google's CDN | Google's infrastructure |

For EU-origin requests: Workers execute at EU edge locations. KV data is globally replicated across Cloudflare's network with no available region restriction on the standard KV product. Stripe stores customer and payment data primarily in the US.

### 1.7 Cloudflare Platform-Level Collection

Cloudflare, as the infrastructure provider, collects its own operational data independently of Atested application code:
- HTTP request metadata (IP addresses, user agents, timestamps, request/response sizes)
- Web Analytics (if enabled in dashboard)
- Security event logs (WAF, DDoS mitigation, bot management)
- Workers Analytics (invocation counts, CPU time, errors)

This data is controlled by Cloudflare under their own privacy policy and data processing agreement.

---

## Part 2: Reconciliation

### 2.1 Deployed Legal Content Inventory

| Page | URL path | Last updated | Status |
|---|---|---|---|
| Privacy Policy | `/legal/privacy/` | April 13, 2026 | Draft pending legal review |
| Terms of Service | `/legal/terms/` | April 13, 2026 | Draft pending legal review |
| Acceptable Use Policy | `/legal/acceptable-use/` | April 14, 2026 | Draft pending legal review |
| DMCA Policy | `/legal/dmca/` | Not checked | Draft |
| Legal Contact | `/legal/contact/` | Not checked | Informational |
| License (BSL 1.1) | `/legal/license/` | Not checked | Software license |
| Trust page | `/trust/` | Not dated | Product marketing / factual claims |

All legal documents carry a prominent "draft document pending legal review" disclaimer.

### 2.2 Category (a): Policy Discloses Collection That Does Not Occur

| # | Policy passage | Cited location | Finding |
|---|---|---|---|
| a-1 | "name, email, message content, and any **attachments**" | Privacy Policy, "What we collect", paragraph 4 | The contact form at `/contact/index.html` has no file upload input, no attachment handler, and no multipart form encoding. The word "attachments" describes a capability that does not exist. |

### 2.3 Category (b): Collection Occurs That the Policy Does Not Disclose

| # | Collection behavior | Worker/KV source | Policy gap |
|---|---|---|---|
| b-1 | **Stripe named as payment processor**: Customer name, email, phone, org metadata sent to Stripe; Stripe Customer object created; $0 subscriptions for Personal tier | `license-worker.js` lines 381-401 (Personal), 295-310 (Checkout) -> Stripe API | Privacy Policy mentions "payment processing" generically under "Who can see your info" but does not name Stripe, does not list what data is sent to Stripe, does not disclose $0 subscription creation for free tier |
| b-2 | **License records stored indefinitely**: license_key, license_id, tier, organization, customer email, Stripe customer_id, issue date, expiry | LICENSE_KV `license:<id>` keys, no TTL | Privacy Policy does not disclose that license purchase/activation creates a permanent record in Cloudflare KV |
| b-3 | **Email-to-license mappings stored indefinitely**: email -> license_key, license_id, tier, organization, customer_id | LICENSE_KV `email:<email>` keys, no TTL | Not disclosed |
| b-4 | **Machine fingerprints stored indefinitely**: machine identity hash linked to license_id | SHARING_AUTHORIZATIONS `<license_id>:<fingerprint>` keys, no TTL | Not disclosed. Machine fingerprints are a form of device identifier |
| b-5 | **Feedback experience notes stored 365 days**: operator-written text, timestamp, tier | LICENSE_KV `note:<artifact_id>` keys, 365-day TTL | Privacy Policy does not describe feedback collection or its retention. Feedback is submitted from the installed product, not the website |
| b-6 | **Per-chain telemetry aggregation stored indefinitely**: aggregate counters, license_id, version, last_seen timestamp, unique_users | LICENSE_KV `telemetry:latest:<chain_hash>` keys, no TTL | Privacy Policy describes telemetry as "summary-only" (accurate for content) but does not describe server-side storage or retention of aggregated data |
| b-7 | **Contact form collects more fields than disclosed**: organization, role, topic classification, topic-specific structured data (varies by inquiry type), prior_contact status, copy_requested, enrichment_hints.email_domain, additional_context | CAPTURE_STORE via `/api/capture`, 90-day TTL | Privacy Policy says "name, email, message content" — omits organization, role, topic classification, prior_contact, and structured topic-specific fields |
| b-8 | **Contact submissions stored in analytics KV for 90 days**: same CAPTURE_STORE as page analytics | CAPTURE_STORE `events:<date>:<seq>` keys, 90-day TTL | Not disclosed that contact form data goes to the same storage as analytics events. The 90-day retention is not stated |
| b-9 | **Verification email for key replacement**: email address and 6-digit code stored 15 minutes; brute-force attempt counter | LICENSE_KV `replace-verify:<email>` keys, 15-minute TTL; Cloudflare Email Workers sends email to customer | Not disclosed |
| b-10 | **Telemetry serves as bidirectional notification channel**: pending license modifications, revocations, and delivery confirmations returned in telemetry response | PENDING_NOTIFICATIONS KV -> telemetry response `notifications` array | Not disclosed. Operators may not know telemetry endpoint also delivers administrative notifications |
| b-11 | **Stripe webhook events archived 90 days**: raw JSON for customer, subscription, invoice, and charge events | STRIPE_EVENTS KV, 90-day TTL | Not disclosed. Contains Stripe-originated personal data (email, name, payment metadata) |

### 2.4 Category (c): Accurate

| # | Policy passage | Cited location | Worker/KV verification |
|---|---|---|---|
| c-1 | "standard web server logs (IP address, user agent, pages visited, timestamps)" | Privacy Policy, "What we collect", paragraph 1 | Cloudflare platform-level collection; accurate |
| c-2 | "first-party analytics script... page views, page durations, referral sources, outbound link clicks, screen width, and returning-visitor status... visitor ID... session identifier... own endpoint on Cloudflare infrastructure. No data is sent to third-party analytics providers." | Privacy Policy, "What we collect", paragraph 2 | Matches `capture.js` exactly: `atested_vid` cookie (365-day, first-party), `atested_sid` (sessionStorage), POST to `/api/capture` on same domain |
| c-3 | "atested.com loads fonts from Google Fonts... Google's privacy policy governs their handling" | Privacy Policy, "What we collect", paragraph 3 | All pages include `fonts.googleapis.com` and `fonts.gstatic.com` preconnect + stylesheet links |
| c-4 | "Product telemetry is on by default... summary-only and does not include chain content, raw interaction events, file paths, user identities, organization names, or session event order" | Privacy Policy, "What we collect", paragraph 5 | Verified against telemetry handler and product-side submission code. Payload contains only: aggregate counters, unique_users count, version, chain_hash, license_id, artifact metadata. No chain content, events, paths, identities, or org names |
| c-5 | "We do not use third-party analytics services, advertising trackers, or behavioral profiling tools on atested.com" | Privacy Policy, "What we collect", paragraph 6 | No third-party analytics scripts found. Only third-party resource is Google Fonts (CDN, not analytics) |
| c-6 | "We do not sell personal information. We do not share personal information with advertisers. We do not build profiles for marketing purposes." | Privacy Policy, "How we use information", paragraph 2 | No evidence of any such activity in code |
| c-7 | "We may share information with service providers who help us operate the business (email hosting, payment processing, cloud infrastructure)" | Privacy Policy, "Who can see your information", paragraph 1 | Directionally accurate. Service providers are Stripe (payment), Cloudflare (infrastructure + email), Google (fonts). Specific names not given |

### 2.5 Trust Page Verification

| # | Claim | Location | Verification |
|---|---|---|---|
| t-1 | "YOUR KEY, YOUR CHAIN, YOUR DATA -- We can never see your data" | Trust page, Section 2, card 2 | Accurate. Signing keys generated locally, chain stays on customer machine. No Worker endpoint receives chain content |
| t-2 | "Telemetry is summary-only: aggregate counters... No raw interaction events... No session ids, event order, file paths, user identities, organization names, or chain content" | Trust page, Section 3, card 3 | Accurate per telemetry payload structure verified in `feedback_signing.py` and `license-worker.js` telemetry handler |
| t-3 | "Only the primary transmits telemetry externally" | Trust page, Section 3, card 6 | Accurate per product architecture |
| t-4 | "Every external telemetry transmission is recorded in the primary governance chain with a SHA-256 hash of the payload and machine coverage" | Trust page, Section 3, card 6 | Accurate per product-side `telemetry_submitted` chain event |

---

## Part 3: RoPA-Input Facts

The following processing activities, data categories, recipients, retention, and transfer routes are structured as factual inputs for a Records of Processing Activities register. **No lawful basis or legal determinations are included** -- that is the human/legal layer.

### Processing Activity 1: Website Analytics

| Field | Value |
|---|---|
| Activity | Collection of page-level traffic data on atested.com |
| Purpose | Security, debugging, aggregate analytics, understanding visitor behavior |
| Data categories | Pseudonymous visitor ID (cookie), session ID, page paths, referrer URLs, screen width, page duration, outbound click URLs, timestamps, returning-visitor flag |
| Data subjects | Website visitors |
| Source | Client-side `capture.js` script on every atested.com page |
| Storage | CAPTURE_STORE KV (Cloudflare), globally replicated |
| Retention | 90-day TTL on KV entries |
| Recipients | Atested (internal analytics via atested-dashboard ingestion scripts) |
| Sub-processors | Cloudflare (infrastructure provider, KV storage) |
| Transfer route | EU visitor browser -> nearest Cloudflare edge PoP -> KV global replication. Data may transit or reside outside EU |

### Processing Activity 2: Contact Form Processing

| Field | Value |
|---|---|
| Activity | Collection and storage of contact form inquiries |
| Purpose | Respond to inquiries, understand user needs, route to appropriate internal team |
| Data categories | Name, email, organization, role, inquiry topic, topic-specific details, prior contact status, email domain, additional context |
| Data subjects | Contact form submitters (potential customers, journalists, researchers, partners, etc.) |
| Source | `/contact/index.html` form, POST to `/api/capture` |
| Storage | CAPTURE_STORE KV (Cloudflare), globally replicated |
| Retention | 90-day TTL on KV entries |
| Recipients | Atested (internal via atested-dashboard ingestion) |
| Sub-processors | Cloudflare (infrastructure provider) |
| Transfer route | Same as website analytics |

### Processing Activity 3: License Issuance and Management

| Field | Value |
|---|---|
| Activity | Creation, storage, replacement, and revocation of license records |
| Purpose | License key generation, delivery, verification, replacement, upgrade management |
| Data categories | Customer name, email, phone (optional), organization name, license key, license ID, tier, Stripe customer ID, issue date, expiry date, modification type/reason |
| Data subjects | License purchasers and Personal tier registrants |
| Source | Stripe webhook, `/api/personal-license`, `/api/replace-key`, admin endpoints |
| Storage | LICENSE_KV (Cloudflare), globally replicated |
| Retention | Permanent (no TTL) for license and email mapping records; 30-day TTL for session lookup; 15-minute TTL for verification codes |
| Recipients | Atested (internal license management) |
| Sub-processors | Cloudflare (infrastructure provider), Stripe (payment processor -- see Activity 4) |
| Transfer route | License purchaser browser -> Stripe checkout (US) -> Stripe webhook -> Cloudflare Worker -> LICENSE_KV global replication |

### Processing Activity 4: Payment Processing via Stripe

| Field | Value |
|---|---|
| Activity | Payment collection and subscription management for paid tiers |
| Purpose | Collect payment for license subscriptions, manage recurring billing |
| Data categories | Customer name, email, phone, organization metadata, payment card details (held by Stripe only), billing address (held by Stripe only), subscription status, invoice history |
| Data subjects | Paying customers (Personal Plus, Crew, Team tiers) and Personal tier registrants ($0 subscription) |
| Source | Stripe Checkout (hosted payment page), Atested Worker (customer creation) |
| Storage | Stripe's infrastructure (US-based primary); STRIPE_EVENTS KV (raw webhook events, 90-day TTL, globally replicated) |
| Retention | Per Stripe's data retention policies for payment data; 90-day TTL for webhook event copies in STRIPE_EVENTS KV |
| Recipients | Atested (license management), Stripe (payment processor) |
| Sub-processors | Stripe (independent data controller for PCI data), Cloudflare (KV storage for webhook archives) |
| Transfer route | Customer browser -> Stripe checkout page (US) -> Stripe webhook -> Cloudflare Worker -> KV. Payment card data never transits Atested infrastructure |

### Processing Activity 5: Product Telemetry

| Field | Value |
|---|---|
| Activity | Reception and aggregation of summary telemetry from product installations |
| Purpose | Aggregate usage statistics for public stats counter, installation health monitoring, tier-calibrated support, version tracking |
| Data categories | Aggregate decision counters (allow/deny/deterministic/judgment), unique_users count, product version, chain hash, license ID, Ed25519 public key and signature |
| Data subjects | Licensed product operators (telemetry is opt-out) |
| Source | Product installation telemetry submitter (POST to `/api/telemetry`) |
| Storage | LICENSE_KV (Cloudflare), globally replicated |
| Retention | Permanent (no TTL) for per-chain latest aggregation and global stats counters; 2-day and 30-day TTL for replay protection entries |
| Recipients | Atested (internal monitoring, public stats page) |
| Sub-processors | Cloudflare (infrastructure provider) |
| Transfer route | Customer machine -> Cloudflare Worker at nearest edge PoP -> LICENSE_KV global replication. For EU-origin: Worker executes at EU edge, but KV data replicates globally |

### Processing Activity 6: Product Feedback

| Field | Value |
|---|---|
| Activity | Reception and storage of operator feedback from product installations |
| Purpose | Product improvement, understanding operator experience |
| Data categories | Free-form message text, experience note (optional, with explicit permission), product version, tier, license status, Ed25519 public key and signature, artifact ID |
| Data subjects | Product operators who submit feedback |
| Source | Product installation feedback submitter (POST to `/api/feedback`) |
| Storage | LICENSE_KV (Cloudflare), globally replicated |
| Retention | 30-day TTL for replay hash; 365-day TTL for experience notes (only when permission_to_use is true); feedback counter permanent |
| Recipients | Atested (internal product improvement) |
| Sub-processors | Cloudflare (infrastructure provider) |
| Transfer route | Same as telemetry |

### Processing Activity 7: Machine Sharing Authorization

| Field | Value |
|---|---|
| Activity | Authorization and tracking of multi-machine license sharing |
| Purpose | Enforce machine caps per license tier, authorize peer-to-peer sharing |
| Data categories | License ID, machine fingerprint (hash of machine identity), tier, authorization timestamp |
| Data subjects | Licensed product operators using multi-machine sharing |
| Source | Admin authorize-sharing endpoint (triggered by product sharing flow) |
| Storage | SHARING_AUTHORIZATIONS KV and PLUS_LICENSE_CACHE KV (Cloudflare), globally replicated |
| Retention | Permanent (no TTL) |
| Recipients | Atested (internal license enforcement) |
| Sub-processors | Cloudflare (infrastructure provider) |
| Transfer route | Customer machine -> Worker -> KV global replication |

### Processing Activity 8: Key Replacement Verification

| Field | Value |
|---|---|
| Activity | Email-based verification for lost license key replacement |
| Purpose | Verify identity of license owner before issuing replacement key |
| Data categories | Customer email, 6-digit verification code, attempt counter |
| Data subjects | License holders requesting key replacement |
| Source | `/api/replace-key` endpoint |
| Storage | LICENSE_KV (Cloudflare, 15-minute TTL); email sent via Cloudflare Email Workers |
| Retention | 15-minute TTL for verification state |
| Recipients | Atested (key replacement flow), Cloudflare (email delivery) |
| Sub-processors | Cloudflare (infrastructure provider, email routing) |
| Transfer route | Customer browser -> Worker -> KV (15 min); Worker -> Cloudflare Email Workers -> customer email inbox |

### Processing Activity 9: Notification Delivery via Telemetry

| Field | Value |
|---|---|
| Activity | Delivery of administrative notifications (license changes, revocations) to product installations via telemetry response |
| Purpose | Inform product installations of license status changes |
| Data categories | Notification type, license ID, tier changes, modification reasons, revocation details |
| Data subjects | Licensed product operators |
| Source | Admin endpoints, upgrade/reinstall flows |
| Storage | PENDING_NOTIFICATIONS KV (Cloudflare), globally replicated |
| Retention | No TTL; entries cleared when acknowledged by product via telemetry |
| Recipients | Licensed product installation (via telemetry response) |
| Sub-processors | Cloudflare (infrastructure provider) |
| Transfer route | Admin action -> PENDING_NOTIFICATIONS KV -> next telemetry request from product -> response payload |

### Processing Activity 10: Google Fonts Loading

| Field | Value |
|---|---|
| Activity | Loading of web fonts from Google's CDN |
| Purpose | Typography rendering on atested.com |
| Data categories | Visitor IP address, user agent, referrer header (standard HTTP request metadata sent by browser) |
| Data subjects | Website visitors |
| Source | Browser requests to `fonts.googleapis.com` and `fonts.gstatic.com` |
| Storage | Google's infrastructure |
| Retention | Per Google's privacy policy |
| Recipients | Google (font CDN provider) |
| Sub-processors | Google |
| Transfer route | Visitor browser -> Google CDN. Independent of Atested infrastructure |

### Sub-Processor Summary

| Sub-processor | Role | Data received | Relevant DPA/SCCs |
|---|---|---|---|
| Cloudflare, Inc. | Infrastructure: Workers compute, KV storage, Pages hosting, Email routing, CDN, DNS | All data in Activities 1-9 transits or is stored on Cloudflare infrastructure | Cloudflare DPA (standard); no region-pinning on KV |
| Stripe, Inc. | Payment processor | Customer name, email, phone, org metadata, payment card details, billing address, subscription/invoice/charge data | Stripe DPA (standard); primary data storage in US |
| Google LLC | Font CDN | IP address, user agent, referrer (via browser font requests) | Google Privacy Policy; no Atested-side DPA for font loading |

---

## Part 4: Data-Flow Statement

### What never leaves the customer machine

The following data is processed exclusively on the customer's own infrastructure by the locally-installed Atested product. None of it is transmitted to Atested-operated servers, Cloudflare Workers, or any third party:

| Data | Component | Notes |
|---|---|---|
| Governance chain (`decision-chain.jsonl`) | `gov_runtime/LOGS/` | Append-only JSONL file containing all governance decisions. Never transmitted |
| Ed25519 signing key | `gov_runtime/signing_key/` | Generated locally, never exported. Used for chain record signing and artifact signing |
| Policy rules (`policy-rules.json`) | `capabilities/` | Declarative governance policy. Evaluated locally by the proxy |
| Tool call arguments | Proxy (`proxy/server.py`) | The actual arguments to tools (file paths, code content, shell commands) are classified and governed locally. Only the classification outcome (allow/deny) is counted in telemetry aggregates |
| File paths | Classifier (`scripts/classifier.py`) | All file path inspection, pattern matching, and base-dir validation happens locally |
| Model content | Proxy | Model responses containing tool_use blocks are parsed locally. The model content itself is between the user's AI agent and their chosen AI provider |
| User identities | Local configuration | Operator identity, machine identity, and all identity configuration remain local |
| Organization names | Local configuration | Organization names from local license configuration are not included in telemetry |
| Session event order | Local chain | The sequence and timing of individual governance decisions are recorded in the local chain only. Telemetry transmits only aggregate totals, not per-event data |
| Chain archives | `gov_runtime/LOGS/archives/` | Archived chain segments and their SQLite artifacts remain local |
| Dashboard state | `dashboard/` | All dashboard UI state, configuration, and runtime data are local |
| Evidence packages | Local export | Encrypted evidence packages are created locally and shared by the operator at their discretion |

### What the hosted Workers receive

| Data | Endpoint | Frequency | Contains PII |
|---|---|---|---|
| Aggregate telemetry counters (allow/deny/deterministic/judgment totals, unique_users count) | `/api/telemetry` | Periodic (operator-configurable; opt-out available) | No (aggregate counters only) |
| Product version string | `/api/telemetry` and `version.atested.com/check` | With each telemetry submission / version check | No |
| Chain hash (hash of last record) | `/api/telemetry` | With each telemetry submission | No (cryptographic hash, not content) |
| License ID | `/api/telemetry` | With each telemetry submission | Pseudonymous identifier |
| Ed25519 public key | `/api/telemetry`, `/api/feedback` (via X-Signing-Public-Key header) | With each artifact submission | No (public key, not identity) |
| Feedback message text | `/api/feedback` | Operator-initiated only | May contain PII if operator includes it |
| Experience note (with explicit permission) | `/api/feedback` | Operator-initiated, permission required | May contain PII if operator includes it |
| Contact form data (name, email, org, role, topic, details) | `/api/capture` | Visitor-initiated | Yes |
| Page view analytics (visitor_id, session_id, path, referrer, screen_width) | `/api/capture` | Automatic on every page load | Pseudonymous |
| License activation data (name, email, phone, org) | `/api/personal-license`, `/api/checkout` | At purchase/registration | Yes |
| Key replacement email | `/api/replace-key` | Operator-initiated | Yes (email address) |

### Statement for /trust use

The Atested product runs entirely on your infrastructure. The governance chain, signing keys, policy rules, tool call arguments, file paths, model content, user identities, organization names, and the complete sequence of governance decisions never leave your machine. Telemetry, when enabled, transmits only aggregate counters -- total allow/deny/deterministic/judgment decisions, unique user count, and product version. No chain content, raw interaction events, file paths, user identities, organization names, or session event order are included. Telemetry is opt-out. Every external telemetry transmission is recorded in the governance chain with a SHA-256 hash of the payload.

---

## Document Metadata

- **Produced by**: Cecil (Dispatch 001-C-2026-0516)
- **Source repos examined**: `atested.com` (HEAD `ced3066`), `governance-layer` (HEAD `c85120a`)
- **Files examined**: `workers/license-worker.js`, `workers/version-worker.js`, `workers/wrangler.toml`, `workers/version-wrangler.toml`, `functions/_middleware.js`, `assets/js/capture.js`, `legal/privacy/index.html`, `legal/terms/index.html`, `legal/acceptable-use/index.html`, `legal/index.html`, `trust/index.html`, `contact/index.html`, `_headers`, `DEPLOYMENT.md`, `scripts/feedback_signing.py` (product repo)
- **Boundaries respected**: No edits to any deployed Privacy Policy, Terms, Trust, or legal content. No public-facing changes. No corrected-policy redline. No AI Act mapping. Output is this internal findings document only.
