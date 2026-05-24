/**
 * Data-access layer for the Atested licensing server (Cloudflare Workers).
 * Licensing app spec v1 section 11.
 *
 * Phase 1: all functions return mock/placeholder responses. Real calls to
 * the licensing server will be wired in later phases when the server exists.
 *
 * Interface mirrors api.js conventions: all functions return
 * { ok: true, data } or { ok: false, error }.
 */

import { COMMERCIAL_TERMS, TIERS, TIER_LABELS } from './tier-feature-registry.js';

// ---------- Configuration ----------

/** Base URL for the licensing server. Set once the server exists. */
const _BASE_URL = null; // e.g. 'https://licensing.atested.com'

// ---------- Mock helpers ----------

function _mockOk(data) {
  return Promise.resolve({ ok: true, data });
}

function _mockNotReady() {
  return Promise.resolve({
    ok: false,
    error: 'Licensing server not yet available. Coming in a later phase.',
  });
}

// ---------- Tier information ----------

/**
 * Fetch tier definitions and pricing.
 * Spec v1 section 2 (tier display).
 */
export function getTierDefinitions() {
  // Phase 1 mock — not currently used. Canonical local fallback data comes
  // from the shared tier feature registry.
  return _mockOk({
    tiers: TIERS.map((id) => ({
      id,
      name: TIER_LABELS[id],
      price: COMMERCIAL_TERMS[id]?.price || '',
      description: COMMERCIAL_TERMS[id]?.summary || '',
    })),
  });
}

// ---------- Questionnaire ----------

/**
 * Submit a questionnaire step answer.
 * Spec v1 section 3 (questionnaire state machine).
 */
export function submitQuestionnaireStep({ step, answer } = {}) {
  return _mockNotReady();
}

/**
 * Retrieve current questionnaire state.
 */
export function getQuestionnaireState() {
  return _mockOk({
    state: 'EMPTY',
    steps_completed: 0,
    total_steps: 0,
  });
}

// ---------- Case document ----------

/**
 * Request a case document assembly.
 * Spec v1 section 4.
 */
export function assembleCaseDocument() {
  return _mockNotReady();
}

// ---------- Registration ----------

/**
 * Register an email for Personal or Personal Plus.
 * Spec v1 section 5.
 */
export function registerEmail({ email } = {}) {
  return _mockNotReady();
}

// ---------- Purchase ----------

import { PAYMENT_LINKS, CHARTER, CHARTER_ACTIVE } from './tier-definitions.js';

/**
 * Initiate a purchase flow via Stripe Payment Links.
 * Redirects the browser to Stripe Checkout. Never resolves on success.
 */
export function initiatePurchase({ tier, useCharter = false } = {}) {
  let url;

  if (useCharter && CHARTER_ACTIVE && CHARTER[tier]) {
    url = CHARTER[tier].link;
  } else {
    url = PAYMENT_LINKS[tier];
  }

  if (!url) {
    return Promise.resolve({ ok: false, error: 'No purchase link available for this tier.' });
  }

  window.location.href = url;
  return new Promise(() => {});
}

// ---------- License management ----------

/**
 * Check license renewal status.
 * Spec v1 section 7.
 */
export function getLicenseRenewalStatus() {
  return _mockNotReady();
}

/**
 * Request a trial extension.
 * Spec v1 section 13.
 */
export function requestTrialExtension() {
  return _mockNotReady();
}

/**
 * Check whether a remote trial extension is active.
 * Spec v1 section 12.
 * Mock: returns { extended: false } so trials complete normally.
 * Replace with real call when the licensing server exists.
 */
export function checkTrialExtension() {
  return _mockOk({ extended: false });
}
