/**
 * Data-access layer for the Atested operator UI.
 * Spec v2 sections 10, 12.
 *
 * This module is the ONLY code that calls fetch() or knows about API URLs
 * and auth tokens. The rendering layer imports from here and never touches
 * the network directly.
 *
 * The interface is designed so a simulation data provider can implement the
 * same exports with fixture data and no network calls.
 *
 * Error handling: all functions return { ok, data?, error? }. The rendering
 * layer checks ok and handles errors inline per spec v2 section 10.3.
 */

// ---------- Auth token ----------

let _token = null;

function _getToken() {
  if (_token) return _token;
  const meta = document.querySelector('meta[name="dashboard-token"]');
  _token = meta ? meta.getAttribute('content') : '';
  return _token;
}

// ---------- Base request ----------

/**
 * Make an authenticated request to the dashboard API.
 * Returns { ok: true, data } on success or { ok: false, error } on failure.
 */
async function _request(method, path, { params, body } = {}) {
  let url = `/api${path}`;

  if (params) {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v != null && v !== '') qs.set(k, String(v));
    }
    const qsStr = qs.toString();
    if (qsStr) url += `?${qsStr}`;
  }

  const opts = {
    method,
    headers: {
      'Authorization': `Bearer ${_getToken()}`,
    },
  };

  if (body != null) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }

  try {
    const res = await fetch(url, opts);
    if (!res.ok) {
      const text = await res.text().catch(() => '');
      return { ok: false, error: `${res.status}: ${text || res.statusText}` };
    }
    const data = await res.json();
    return { ok: true, data };
  } catch (err) {
    return {
      ok: false,
      error: 'Unable to reach the Atested server. Check that the dashboard server is running.',
    };
  }
}

// ---------- GET endpoints ----------

/**
 * Governance status overview.
 * GET /api/status
 */
export function getStatus(opts = {}) {
  return _request('GET', '/status', { params: opts });
}

/**
 * System health.
 * GET /api/health
 */
export function getHealth() {
  return _request('GET', '/health');
}

/**
 * Governance activity feed.
 * GET /api/activity
 * @param {Object} opts - { limit, offset, governed_family, event_category, resolution, start_time, end_time }
 */
export function getActivity(opts = {}) {
  return _request('GET', '/activity', { params: opts });
}

/**
 * Active approvals.
 * GET /api/approvals
 */
export function getApprovals() {
  return _request('GET', '/approvals');
}

/**
 * Audit query.
 * GET /api/audit/query
 * @param {Object} opts - { start_time, end_time, user_identity, tool_name, policy_decision, event_category, limit, offset }
 */
export function getAuditQuery(opts = {}) {
  return _request('GET', '/audit/query', { params: opts });
}

/**
 * Single audit record detail.
 * GET /api/audit/record
 * @param {string} recordId
 */
export function getAuditRecord(recordId) {
  return _request('GET', '/audit/record', { params: { record_id: recordId } });
}

/**
 * Audit summary report.
 * GET /api/audit/report
 * @param {Object} opts - { start_time, end_time, group_by }
 */
export function getAuditReport(opts = {}) {
  return _request('GET', '/audit/report', { params: opts });
}

/**
 * Transparency metrics.
 * GET /api/transparency
 * @param {Object} opts - { start_time, end_time }
 */
export function getTransparency(opts = {}) {
  return _request('GET', '/transparency', { params: opts });
}

/**
 * Verification state.
 * GET /api/verification
 * @param {Object} opts - { governed_family }
 */
export function getVerification(opts = {}) {
  return _request('GET', '/verification', { params: opts });
}

/**
 * User report.
 * GET /api/users
 */
export function getUsers() {
  return _request('GET', '/users');
}

/**
 * Configuration and registry.
 * GET /api/config
 */
export function getConfig() {
  return _request('GET', '/config');
}

/**
 * Feedback artifacts.
 * GET /api/feedback
 */
export function getFeedback() {
  return _request('GET', '/feedback');
}

/**
 * Telemetry artifacts.
 * GET /api/telemetry
 */
export function getTelemetry() {
  return _request('GET', '/telemetry');
}

/**
 * Telemetry opt-in status.
 * GET /api/telemetry/status
 */
export function getTelemetryStatus() {
  return _request('GET', '/telemetry/status');
}

// ---------- POST endpoints ----------

/**
 * Record ungoverned operation observation.
 * POST /api/observe
 */
export function postObserve({ operation_type, target, source, observed_at } = {}) {
  return _request('POST', '/observe', { body: { operation_type, target, source, observed_at } });
}

/**
 * Add an approval.
 * POST /api/approvals/add
 */
export function postApprovalAdd({ artifact_identity, operator } = {}) {
  return _request('POST', '/approvals/add', { body: { artifact_identity, operator } });
}

/**
 * Revoke an approval.
 * POST /api/approvals/revoke
 */
export function postApprovalRevoke({ artifact_identity, operator } = {}) {
  return _request('POST', '/approvals/revoke', { body: { artifact_identity, operator } });
}

/**
 * Acknowledge a health alert.
 * POST /api/health/acknowledge
 */
export function postHealthAcknowledge({ source, message } = {}) {
  return _request('POST', '/health/acknowledge', { body: { source, message } });
}

/**
 * Update configuration.
 * POST /api/config/update
 */
export function postConfigUpdate({ registry, license_key } = {}) {
  return _request('POST', '/config/update', { body: { registry, license_key } });
}

/**
 * Verify a license key.
 * POST /api/config/verify-license
 */
export function postVerifyLicense({ license_key } = {}) {
  return _request('POST', '/config/verify-license', { body: { license_key } });
}

/**
 * Submit feedback.
 * POST /api/feedback/submit
 */
export function postFeedbackSubmit({ message, experience_note, permission_to_use, send_to_remote } = {}) {
  return _request('POST', '/feedback/submit', {
    body: { message, experience_note, permission_to_use, send_to_remote },
  });
}

/**
 * Submit telemetry.
 * POST /api/telemetry/submit
 */
export function postTelemetrySubmit({ send_to_remote } = {}) {
  return _request('POST', '/telemetry/submit', { body: { send_to_remote } });
}

/**
 * Set telemetry opt-in.
 * POST /api/telemetry/opt-in
 */
export function postTelemetryOptIn({ opted_in } = {}) {
  return _request('POST', '/telemetry/opt-in', { body: { opted_in } });
}

// ---------- Notification endpoints ----------

/**
 * Get active notifications.
 * GET /api/notifications
 */
export function getNotifications() {
  return _request('GET', '/notifications');
}

/**
 * Dismiss a notification.
 * POST /api/notifications/dismiss
 */
export function postDismissNotification({ notification_id } = {}) {
  return _request('POST', '/notifications/dismiss', { body: { notification_id } });
}

/**
 * Record that notifications were viewed.
 * POST /api/notifications/viewed
 */
export function postNotificationsViewed({ count } = {}) {
  return _request('POST', '/notifications/viewed', { body: { count } });
}

// ---------- Disclosure endpoints ----------

/**
 * Get disclosure acknowledgement status.
 * GET /api/disclosure/status
 */
export function getDisclosureStatus() {
  return _request('GET', '/disclosure/status');
}

/**
 * Acknowledge the first-run disclosure.
 * POST /api/disclosure/acknowledge
 */
export function postDisclosureAcknowledge({ operator } = {}) {
  return _request('POST', '/disclosure/acknowledge', { body: { operator } });
}

// ---------- Licensing endpoints ----------

/**
 * Get current licensing mode.
 * GET /api/licensing/mode
 * Returns { license_status, license_tier, organization_id, license_expiry, trial_days_remaining, registered }
 */
export function getLicensingMode() {
  return _request('GET', '/licensing/mode');
}

/**
 * Get questionnaire state from chain events.
 * GET /api/licensing/questionnaire
 * Returns { answers: [{question_id, answer_value, ...}], capacity: {user_count, machine_count, base_tier} | null }
 */
export function getQuestionnaireState() {
  return _request('GET', '/licensing/questionnaire');
}

/**
 * Persist a questionnaire answer to the chain.
 * POST /api/licensing/questionnaire/answer
 * @param {Object} opts - { question_id, answer_value, phase, tier_boundary }
 */
export function postQuestionnaireAnswer({ question_id, answer_value, phase, tier_boundary } = {}) {
  return _request('POST', '/licensing/questionnaire/answer', {
    body: { question_id, answer_value, phase, tier_boundary },
  });
}

/**
 * Persist capacity gate inputs to the chain.
 * POST /api/licensing/capacity
 * @param {Object} opts - { user_count, machine_count, base_tier }
 */
export function postCapacityInputs({ user_count, machine_count, base_tier } = {}) {
  return _request('POST', '/licensing/capacity', {
    body: { user_count, machine_count, base_tier },
  });
}

// ---------- Identity endpoints ----------

/**
 * Get operator identity session state.
 * GET /api/identity/session
 */
export function getIdentitySession() {
  return _request('GET', '/identity/session');
}

/**
 * Manually lock the operator session.
 * POST /api/identity/lock
 */
export function postIdentityLock() {
  return _request('POST', '/identity/lock', { body: {} });
}
