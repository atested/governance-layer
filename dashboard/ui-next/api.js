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
 * @param {Object} opts - { limit, offset, governed_family, event_category, resolution, start_time, end_time, policy_decision, tool_name }
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
 * Audit Chain Walker live-chain window.
 * GET /api/audit/walker
 * @param {Object} opts - audit filters plus center_record_id, center_sequence, or center_index
 */
export function getAuditWalker(opts = {}) {
  return _request('GET', '/audit/walker', { params: opts });
}

/**
 * Audit Chain Walker archives.
 * GET /api/audit/archives
 */
export function getAuditArchives() {
  return _request('GET', '/audit/archives');
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
 * Trouble report history.
 * GET /api/trouble
 */
export function getTroubleReports() {
  return _request('GET', '/trouble');
}

/**
 * Telemetry artifacts.
 * GET /api/telemetry
 */
export function getTelemetry() {
  return _request('GET', '/telemetry');
}

/**
 * Anonymous summary telemetry state.
 * GET /api/telemetry/summary
 */
export function getTelemetrySummary() {
  return _request('GET', '/telemetry/summary');
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
 * Record runtime operation observation.
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
 * Authorize and record an export.
 * POST /api/export/authorize
 */
export function postExportAuthorize({ license_key, metadata } = {}) {
  return _request('POST', '/export/authorize', { body: { license_key, metadata } });
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
 * Merge anonymous summary telemetry counters.
 * POST /api/telemetry/summary
 */
export function postTelemetrySummary({ increments } = {}) {
  return _request('POST', '/telemetry/summary', { body: { increments } });
}

/**
 * Set telemetry opt-in.
 * POST /api/telemetry/opt-in
 */
export function postTelemetryOptIn({ opted_in } = {}) {
  return _request('POST', '/telemetry/opt-in', { body: { opted_in } });
}

/**
 * Submit contextual support report. Works regardless of telemetry opt-out.
 * POST /api/trouble/report
 */
export function postTroubleReport({ description, priority, context } = {}) {
  return _request('POST', '/trouble/report', { body: { description, priority, context } });
}

/**
 * Communications state: slots, requests, telemetry status, plan tier.
 * GET /api/communications
 */
export function getCommunications() {
  return _request('GET', '/communications');
}

/**
 * Submit a priority request.
 * POST /api/communications/request
 */
export function postCommunicationsRequest({ message, priority } = {}) {
  return _request('POST', '/communications/request', { body: { message, priority } });
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
 * Reset the questionnaire (clears all answers and capacity in the chain).
 * POST /api/licensing/questionnaire/reset
 */
export function postQuestionnaireReset() {
  return _request('POST', '/licensing/questionnaire/reset', { body: {} });
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

/**
 * Get assembled case document from chain data.
 * GET /api/licensing/case-document
 * Returns { document: CaseDocument }
 */
export function getCaseDocument() {
  return _request('GET', '/licensing/case-document');
}

/**
 * Register for Personal license.
 * POST /api/licensing/register
 * @param {Object} opts - { operator_name, context_note, telemetry_opted_in, operator_role, how_found, deciding_factor, biggest_insight, research_opted_in }
 */
export function postRegister(opts = {}) {
  return _request('POST', '/licensing/register', { body: opts });
}

/**
 * Purchase a paid tier license.
 * POST /api/licensing/purchase
 * @param {Object} opts - { tier, payment_ref, operator_name, operator_role, how_found, deciding_factor, biggest_insight, research_opted_in, organization_name, industry_sector, billing_contact, primary_operator }
 */
export function postPurchase(opts = {}) {
  return _request('POST', '/licensing/purchase', { body: opts });
}

/**
 * Submit institution inquiry.
 * POST /api/licensing/institution-inquiry
 */
export function postInstitutionInquiry(opts = {}) {
  return _request('POST', '/licensing/institution-inquiry', { body: opts });
}

/**
 * Change research program opt-in.
 * POST /api/licensing/research-opt-in
 * @param {Object} opts - { opted_in }
 */
export function postResearchOptIn({ opted_in } = {}) {
  return _request('POST', '/licensing/research-opt-in', { body: { opted_in } });
}

/**
 * Toggle auto-renewal state.
 * POST /api/licensing/auto-renewal
 * @param {Object} opts - { auto_renewal }
 */
export function postAutoRenewal({ auto_renewal } = {}) {
  return _request('POST', '/licensing/auto-renewal', {
    body: { auto_renewal },
  });
}

/**
 * Schedule a downgrade for next renewal.
 * POST /api/licensing/downgrade
 * @param {Object} opts - { to_tier }
 */
export function postDowngrade({ to_tier } = {}) {
  return _request('POST', '/licensing/downgrade', {
    body: { to_tier },
  });
}

/**
 * Acknowledge licensing terms.
 * POST /api/licensing/terms-acknowledge
 */
export function postTermsAcknowledge() {
  return _request('POST', '/licensing/terms-acknowledge', {
    body: {},
  });
}

/**
 * Activate a license from a pasted/uploaded key.
 * POST /api/licensing/activate-with-key
 */
export function postActivateWithKey({ license_key } = {}) {
  return _request('POST', '/licensing/activate-with-key', { body: { license_key } });
}

/**
 * Create an encrypted evidence package.
 * POST /api/export/package
 * Returns the raw response (binary ZIP).
 */
export async function postExportPackage(opts = {}) {
  const url = '/api/export/package';
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${_getToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(opts),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    let error = `${res.status}: ${text || res.statusText}`;
    try { const j = JSON.parse(text); error = j.error || error; } catch {}
    return { ok: false, error };
  }
  const blob = await res.blob();
  const packageId = res.headers.get('X-Package-Id') || '';
  const manifestHash = res.headers.get('X-Package-Manifest-Hash') || '';
  const eventHash = res.headers.get('X-Package-Event-Hash') || '';
  return { ok: true, blob, packageId, manifestHash, eventHash };
}

// ---------- Sharing & Machine Management ----------
export function postStartSharing() { return _request('POST', '/sharing/start', { body: {} }); }
export function postStopSharing() { return _request('POST', '/sharing/stop', { body: {} }); }
export function getSharingStatus() { return _request('GET', '/sharing/status'); }
export function postApproveShare({ request_id } = {}) { return _request('POST', '/sharing/approve', { body: { request_id } }); }
export function postDenyShare({ request_id } = {}) { return _request('POST', '/sharing/deny', { body: { request_id } }); }
export function postJoinLicense({ address } = {}) { return _request('POST', '/sharing/join', { body: { address } }); }
export function postStartDiscovery() { return _request('POST', '/sharing/discover', { body: {} }); }
export function getJoinStatus() { return _request('GET', '/sharing/join-status'); }
export function getMachines() { return _request('GET', '/sharing/machines'); }
export function postRevokeMachine({ fingerprint } = {}) { return _request('POST', '/sharing/revoke-machine', { body: { fingerprint } }); }

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
