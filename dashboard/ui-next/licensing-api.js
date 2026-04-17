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
  return _mockOk({
    tiers: [
      { id: 'personal', name: 'Personal', price: 'Free', description: 'Single operator, full governance.' },
      { id: 'personal_plus', name: 'Personal Plus', price: '$9/mo', description: 'Single operator, priority features.' },
      { id: 'crew', name: 'Crew', price: '$29/mo', description: '2-5 operators, shared governance.' },
      { id: 'team', name: 'Team', price: '$79/mo', description: '6-20 operators, team governance.' },
      { id: 'institution', name: 'Institution', price: 'Contact us', description: '20+ operators, enterprise governance.' },
    ],
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

/**
 * Initiate a purchase flow.
 * Spec v1 section 6.
 * Mock: returns a successful purchase with a mock payment reference.
 * Replace with real Stripe integration when the licensing server exists.
 */
export function initiatePurchase({ tier } = {}) {
  return _mockOk({
    payment_ref: `mock_pay_${Date.now()}`,
    tier: tier || 'personal_plus',
    status: 'completed',
  });
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
