# Atested Website — Deployment Instructions

## Overview

- **Static site** hosted on Cloudflare Pages (atested.com)
- **License worker** hosted on Cloudflare Workers (license.atested.com)
- **Payments** via Stripe Checkout

---

## 1. Cloudflare Pages (Static Site)

### Create the project

1. Log in to the Cloudflare dashboard.
2. Go to **Workers & Pages** > **Create** > **Pages** > **Connect to Git**.
3. Select the `governance-layer` repository.
4. Set the build configuration:
   - **Build command**: (leave empty — static files, no build step)
   - **Build output directory**: `website`
   - **Root directory**: `/` (repo root)
5. Deploy.

### Custom domain

1. In the Pages project settings, go to **Custom domains**.
2. Add `atested.com` and `www.atested.com`.
3. Cloudflare will provide DNS records to add. If atested.com is already on Cloudflare DNS, this is automatic.
4. SSL is automatic via Cloudflare.

---

## 2. Stripe Setup

### Create products and prices

1. In the [Stripe Dashboard](https://dashboard.stripe.com), create two products:
   - **Atested Team** — annual, $999/year
   - **Atested Business** — annual, $4,999/year
2. Note the Price IDs (e.g., `price_1Abc...`).

### Add custom fields to Checkout

1. In each product's Checkout settings, add a custom text field:
   - Label: "Organization name"
   - Required: Yes
2. This collects the organization name for the license key.

### Update the website code

1. In `website/assets/js/stripe-checkout.js`:
   - Replace `STRIPE_PUBLISHABLE_KEY` with your Stripe publishable key (`pk_live_...`).
   - Replace the Price IDs in `PRICE_IDS`.

2. In `website/workers/license-worker.js`:
   - Replace the Price IDs in `TIER_MAP`.

### Create webhook

1. In Stripe Dashboard > **Developers** > **Webhooks**.
2. Add endpoint: `https://license.atested.com/webhook`
3. Select event: `checkout.session.completed`
4. Note the webhook signing secret (`whsec_...`).

---

## 3. Cloudflare Worker (License Generation)

### Generate the license issuer key pair

**Do this on your local machine. Never commit the private key.**

```bash
# Generate Ed25519 key pair
python3 -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
import base64

priv = Ed25519PrivateKey.generate()
pub = priv.public_key()

# Raw 32-byte seed for the Worker secret
seed = priv.private_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PrivateFormat.Raw,
    encryption_algorithm=serialization.NoEncryption(),
)
print('PRIVATE KEY (base64, for Worker secret):')
print(base64.b64encode(seed).decode())
print()

# PEM public key for the governance layer verifier
pub_pem = pub.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)
print('PUBLIC KEY (PEM, for governance layer):')
print(pub_pem.decode())
"
```

Save the public key PEM to your governance layer deployment (e.g., as the license verification key).

### Deploy the Worker

```bash
cd website/workers

# Install wrangler if needed
npm install -g wrangler

# Authenticate
wrangler login

# Create KV namespace
wrangler kv:namespace create LICENSE_STORE
# Copy the output ID into wrangler.toml

# Set secrets
wrangler secret put STRIPE_WEBHOOK_SECRET
wrangler secret put STRIPE_SECRET_KEY
wrangler secret put LICENSE_ISSUER_PRIVATE_KEY

# Deploy
wrangler deploy
```

### Custom domain for the Worker

1. In the Cloudflare dashboard, go to the Worker settings.
2. Add a custom domain: `license.atested.com`.
3. This routes requests to the Worker.

---

## 4. Post-Deployment Checklist

- [ ] atested.com loads the landing page
- [ ] All 5 pages render correctly
- [ ] Mobile responsive layout works
- [ ] Stripe Checkout redirects for Team and Business tiers
- [ ] Stripe webhook fires on test payment
- [ ] License key appears on success page after test payment
- [ ] license.atested.com/license?session_id=... returns license key
- [ ] Enterprise contact form sends email
- [ ] GitHub link works in footer and landing page CTA
- [ ] SSL working on both atested.com and license.atested.com

---

## 5. Testing with Stripe Test Mode

Before going live:

1. Use Stripe test mode keys (`pk_test_...`, `sk_test_...`) in the code.
2. Use Stripe test card: `4242 4242 4242 4242`, any future expiry, any CVC.
3. Verify the full flow: checkout > webhook > license key generation > success page.
4. Switch to live keys when ready.

---

## Files Reference

| File | Purpose |
|---|---|
| `website/index.html` | Landing page |
| `website/how-it-works.html` | Governance flow walkthrough |
| `website/pricing.html` | Tier cards + Stripe checkout |
| `website/explainer.html` | Business case for governance |
| `website/terms.html` | Terms of service + liability |
| `website/success.html` | Post-payment license delivery |
| `website/assets/css/style.css` | Global styles |
| `website/assets/js/nav.js` | Mobile nav toggle |
| `website/assets/js/tabs.js` | Proof packet tabs |
| `website/assets/js/stripe-checkout.js` | Stripe Checkout integration |
| `website/workers/license-worker.js` | Cloudflare Worker for license generation |
| `website/workers/wrangler.toml` | Worker configuration |
