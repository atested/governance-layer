/**
 * Atested License Worker — Cloudflare Worker
 *
 * Handles:
 *   POST /webhook    — Stripe webhook endpoint (payment confirmation)
 *   GET  /license    — License key lookup by session_id
 *
 * Secrets (set via `wrangler secret put`):
 *   STRIPE_WEBHOOK_SECRET    — Stripe webhook signing secret (whsec_...)
 *   LICENSE_ISSUER_PRIVATE_KEY — Ed25519 private key in base64 (raw 32 bytes)
 *   STRIPE_SECRET_KEY        — Stripe API secret key (sk_live_...)
 *
 * KV Namespace (bound as LICENSE_KV):
 *   Stores session_id -> license_key mappings with 30-day TTL.
 *
 * SETUP:
 *   1. wrangler secret put STRIPE_WEBHOOK_SECRET
 *   2. wrangler secret put LICENSE_ISSUER_PRIVATE_KEY
 *   3. wrangler secret put STRIPE_SECRET_KEY
 *   4. Create KV namespace: wrangler kv:namespace create LICENSE_STORE
 *   5. Bind it in wrangler.toml as LICENSE_KV
 */

const TIER_MAP = {
  'price_REPLACE_WITH_TEAM_PRICE_ID': 'team',
  'price_REPLACE_WITH_BUSINESS_PRICE_ID': 'business',
};

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === 'POST' && url.pathname === '/webhook') {
      return handleWebhook(request, env);
    }

    if (request.method === 'GET' && url.pathname === '/license') {
      return handleLicenseLookup(url, env);
    }

    return new Response('Not Found', { status: 404 });
  },
};

// ------------------------------------------------------------------
// Stripe webhook handler
// ------------------------------------------------------------------

async function handleWebhook(request, env) {
  const body = await request.text();
  const signature = request.headers.get('stripe-signature');

  // Verify Stripe webhook signature
  const isValid = await verifyStripeSignature(body, signature, env.STRIPE_WEBHOOK_SECRET);
  if (!isValid) {
    return new Response('Invalid signature', { status: 400 });
  }

  const event = JSON.parse(body);

  if (event.type !== 'checkout.session.completed') {
    return new Response('OK', { status: 200 });
  }

  const session = event.data.object;
  const sessionId = session.id;
  const customerEmail = session.customer_details?.email || '';
  const orgName = session.custom_fields?.[0]?.text?.value || customerEmail;

  // Determine tier from line items
  const lineItems = await fetchLineItems(sessionId, env.STRIPE_SECRET_KEY);
  let tier = 'team'; // default
  for (const item of lineItems) {
    const mapped = TIER_MAP[item.price?.id];
    if (mapped) {
      tier = mapped;
      break;
    }
  }

  // Generate license key
  const licenseKey = await generateLicenseKey(env.LICENSE_ISSUER_PRIVATE_KEY, {
    tier,
    organization: orgName,
    email: customerEmail,
    issued_at: new Date().toISOString(),
    expires_at: new Date(Date.now() + 365 * 24 * 60 * 60 * 1000).toISOString(),
  });

  // Store in KV (30-day TTL for lookup)
  await env.LICENSE_KV.put(sessionId, JSON.stringify({
    license_key: licenseKey,
    tier,
    organization: orgName,
  }), { expirationTtl: 30 * 24 * 60 * 60 });

  return new Response('OK', { status: 200 });
}

// ------------------------------------------------------------------
// License lookup handler
// ------------------------------------------------------------------

async function handleLicenseLookup(url, env) {
  const sessionId = url.searchParams.get('session_id');
  if (!sessionId) {
    return jsonResponse({ error: 'session_id required' }, 400);
  }

  const stored = await env.LICENSE_KV.get(sessionId);
  if (!stored) {
    return jsonResponse({ error: 'not_ready' }, 404);
  }

  return jsonResponse(JSON.parse(stored), 200, {
    'Access-Control-Allow-Origin': 'https://atested.com',
  });
}

// ------------------------------------------------------------------
// License key generation (Ed25519)
// ------------------------------------------------------------------

async function generateLicenseKey(privateKeyB64, claims) {
  // Import the Ed25519 private key.
  // The secret is the raw 32-byte seed, base64-encoded.
  const seed = base64ToArrayBuffer(privateKeyB64);

  // Build the license payload
  const payload = JSON.stringify(claims, Object.keys(claims).sort());
  const payloadB64 = arrayBufferToBase64Url(new TextEncoder().encode(payload));

  // Sign with Ed25519 using the Web Crypto API
  const keyPair = await crypto.subtle.importKey(
    'raw',
    seed,
    { name: 'Ed25519' },
    false,
    ['sign']
  );

  const signature = await crypto.subtle.sign('Ed25519', keyPair, new TextEncoder().encode(payload));
  const signatureB64 = arrayBufferToBase64Url(new Uint8Array(signature));

  // License key format: <payload-b64url>.<signature-b64url>
  return payloadB64 + '.' + signatureB64;
}

// ------------------------------------------------------------------
// Stripe helpers
// ------------------------------------------------------------------

async function verifyStripeSignature(body, signatureHeader, secret) {
  if (!signatureHeader) return false;

  const parts = {};
  signatureHeader.split(',').forEach((part) => {
    const [key, value] = part.split('=');
    parts[key.trim()] = value;
  });

  const timestamp = parts['t'];
  const expectedSig = parts['v1'];
  if (!timestamp || !expectedSig) return false;

  // Reject if timestamp is more than 5 minutes old
  const age = Math.abs(Date.now() / 1000 - parseInt(timestamp));
  if (age > 300) return false;

  const signedPayload = timestamp + '.' + body;
  const key = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const mac = await crypto.subtle.sign('HMAC', key, new TextEncoder().encode(signedPayload));
  const computed = arrayBufferToHex(new Uint8Array(mac));

  return timingSafeEqual(computed, expectedSig);
}

async function fetchLineItems(sessionId, stripeSecretKey) {
  const resp = await fetch(
    `https://api.stripe.com/v1/checkout/sessions/${sessionId}/line_items`,
    {
      headers: {
        'Authorization': `Bearer ${stripeSecretKey}`,
      },
    }
  );
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.data || [];
}

// ------------------------------------------------------------------
// Utility functions
// ------------------------------------------------------------------

function jsonResponse(data, status, extraHeaders) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      ...extraHeaders,
    },
  });
}

function base64ToArrayBuffer(b64) {
  // Handle both standard and URL-safe base64
  const standardB64 = b64.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(standardB64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

function arrayBufferToBase64Url(bytes) {
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function arrayBufferToHex(bytes) {
  return Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
}

function timingSafeEqual(a, b) {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}
