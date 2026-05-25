/**
 * Conformance mode detail window (QS-044).
 *
 * Opens a child window for one of the five quality-service verification
 * modes, rendering that mode's detail from the /api/conformance payload
 * the main page already holds. Follows the existing window convention:
 * build a content element and hand it to modalManager.
 *
 * Presentation only — reads the conformance payload, never the API logic.
 */

import { modalManager } from '../modal-manager.js';

const MODE_LABEL = {
  environmental: 'Environmental',
  post_hoc: 'Post-hoc verification',
  spc: 'SPC',
  element: 'Element verification',
  behavioral: 'Behavioral analysis',
};

const MODE_DESCRIPTION = {
  environmental: 'Pre-flight checks that the governance environment is sound before any decision is governed.',
  post_hoc: 'Re-verifies recorded decisions against current policy to catch drift between what was decided and what the rules now say.',
  spc: 'Statistical Process Control — tracks decision-stream metrics (ALLOW rate, classification mix) and flags statistically significant shifts.',
  element: 'Verifies chain record schemas, hash linkage, signatures, and configuration state.',
  behavioral: 'Looks for behavioral anomalies across recent decisions.',
};

const ENV_DESCRIPTION = {
  'ENV-001': 'Policy rules match what the proxy loaded',
  'ENV-002': 'Signing key present and valid',
  'ENV-003': 'Chain files writable',
  'ENV-004': 'Capability registry current',
  'ENV-005': 'QA chain integrity (hash linkage)',
  'ENV-006': 'Governance chain integrity',
  'ENV-007': 'Disk space adequate',
  'ENV-008': 'Proxy process running',
  'ENV-009': 'Dashboard process running',
  'ENV-010': 'Configuration integrity',
};

// Behavioral analysis categories the mode evaluates (static — describes what
// the mode does even when idle/warming up).
const BEHAVIORAL_CATEGORIES = [
  ['Classification consistency', 'Same tool reclassified differently without a visible cause.'],
  ['Decision reversals', 'A tool flips ALLOW/DENY with no intervening policy or approval change.'],
  ['Temporal patterns', 'Off-hours activity relative to the historical baseline.'],
  ['Approval provenance', 'Aged approvals or operators with no prior approval history.'],
  ['Policy rule coverage', 'Dead rules (never matched) or overly broad rules (match everything).'],
];

const STATUS_LABEL = {
  healthy: 'healthy', verified: 'verified', active: 'active', idle: 'idle',
  warming_up: 'warming up', learning: 'warming up', finding: 'finding',
  behind: 'behind', attention: 'attention', unavailable: 'unavailable',
  condition_detected: 'condition', not_active: 'idle',
};

export function openConformanceModeWindow(modeKey, conformanceData, trigger) {
  const data = conformanceData || {};
  const mode = (data.modes || {})[modeKey] || { status: 'idle' };
  const content = document.createElement('div');
  content.className = 'cfm-root';

  const parts = [];
  parts.push(`<p class="cfm-desc">${_esc(MODE_DESCRIPTION[modeKey] || '')}</p>`);
  parts.push(_statusBlock(mode));
  parts.push(_modeDetail(modeKey, mode, data));
  content.innerHTML = parts.join('');

  const title = `${MODE_LABEL[modeKey] || modeKey}`;
  _openAsChild(title, 'Quality service verification mode', trigger, content);
}

function _statusBlock(mode) {
  const status = STATUS_LABEL[String(mode.status || 'idle').toLowerCase()] || mode.status || 'idle';
  const detail = mode.detail || mode.note || '';
  return `
    <div class="cfm-status">
      <span class="cfm-status-label">Status</span>
      <strong>${_esc(status)}</strong>
      ${detail ? `<span class="cfm-status-detail">${_esc(detail)}</span>` : ''}
    </div>`;
}

function _modeDetail(modeKey, mode, data) {
  switch (modeKey) {
    case 'environmental': return _environmental(data);
    case 'post_hoc': return _postHoc(mode);
    case 'spc': return _spc(mode);
    case 'element': return _element(mode);
    case 'behavioral': return _behavioral(mode);
    default: return '';
  }
}

function _environmental(data) {
  const checks = (data.latest_snapshot && data.latest_snapshot.checks)
    || (data.modes && data.modes.environmental && data.modes.environmental.checks)
    || {};
  const ids = Object.keys(ENV_DESCRIPTION);
  // include any extra checks present in the payload beyond the known 10
  for (const k of Object.keys(checks)) if (!ids.includes(k)) ids.push(k);
  if (!ids.length) return '<div class="cfm-empty">No environmental snapshot available.</div>';
  const rows = ids.map((id) => {
    const check = checks[id] || {};
    const status = String(check.status || 'unknown');
    const desc = ENV_DESCRIPTION[id] || '';
    const reason = check.detail ? `<span class="cfm-check-detail">${_esc(check.detail)}</span>` : '';
    return `
      <div class="cfm-check cfm-status-${_token(status)}">
        <span class="cfm-check-id">${_esc(id)}</span>
        <strong class="cfm-check-status">${_esc(status)}</strong>
        <span class="cfm-check-desc">${_esc(desc)}</span>
        ${reason}
      </div>`;
  }).join('');
  return `<h4>Checks</h4><div class="cfm-checks">${rows}</div>`;
}

function _postHoc(mode) {
  const rows = [];
  if (mode.decisions_verified != null) rows.push(_kv('Decisions verified', mode.decisions_verified));
  if (mode.skipped != null) rows.push(_kv('Skipped', mode.skipped));
  if (mode.queue_depth != null) rows.push(_kv('Verification queue', `${mode.queue_depth} of ${mode.queue_capacity ?? '?'}`));
  let body = rows.length ? `<div class="cfm-kvs">${rows.join('')}</div>` : '';
  body += _findings(mode.findings, (f) => `${_esc(f.check || f.type || 'finding')}: ${_esc(f.detail || '')}`);
  if (!body) body = '<div class="cfm-empty">No governance decisions to verify yet.</div>';
  return body;
}

function _spc(mode) {
  const s = String(mode.status || '').toLowerCase();
  if (s === 'warming_up' || s === 'learning') {
    return `<div class="cfm-kvs">${_kv('Baseline progress', `${mode.decisions_collected ?? 0} / ${mode.minimum_required ?? 100} decisions`)}</div>`;
  }
  if (s === 'attention' || mode.metric_id) {
    return `<div class="cfm-kvs">
      ${_kv('Metric', `${_esc(mode.metric_name || mode.metric_id || '')}`)}
      ${mode.current_value != null ? _kv('Current value', mode.current_value) : ''}
      ${mode.ucl != null ? _kv('Upper control limit', mode.ucl) : ''}
      ${mode.lcl != null ? _kv('Lower control limit', mode.lcl) : ''}
    </div>`;
  }
  return '<div class="cfm-empty">No decisions yet to baseline. Metrics tracked: ALLOW rate, classification mix.</div>';
}

function _element(mode) {
  const rows = [];
  if (mode.elements_checked != null) rows.push(_kv('Elements checked', mode.elements_checked));
  if (mode.elements_passed != null) rows.push(_kv('Passed', mode.elements_passed));
  if (mode.elements_flagged != null) rows.push(_kv('Flagged', mode.elements_flagged));
  if (mode.elements_skipped != null) rows.push(_kv('Skipped', mode.elements_skipped));
  let body = rows.length ? `<div class="cfm-kvs">${rows.join('')}</div>` : '';
  body += _findings(mode.findings, (f) => `${_esc(f.element_id || 'element')} (${_esc(f.severity || '')}): ${_esc(f.detail || '')}`);
  if (!body) body = '<div class="cfm-empty">No element verification run yet. Checks chain schemas, hash linkage, signatures, configuration state.</div>';
  return body;
}

function _behavioral(mode) {
  const s = String(mode.status || '').toLowerCase();
  let body = '';
  if (s === 'warming_up') {
    body += `<div class="cfm-kvs">${_kv('Warm-up progress', `${mode.decisions_analyzed ?? 0} / ${mode.minimum_required ?? 100} decisions`)}</div>`;
  } else if (mode.anomaly_count != null) {
    body += `<div class="cfm-kvs">${_kv('Anomalies', mode.anomaly_count)}</div>`;
  }
  body += _findings(mode.findings, (f) => `${_esc(f.subtype || f.type || 'finding')}: ${_esc(f.detail || '')}`);
  const cats = BEHAVIORAL_CATEGORIES.map(
    ([name, desc]) => `<div class="cfm-cat"><strong>${_esc(name)}</strong><span>${_esc(desc)}</span></div>`
  ).join('');
  body += `<h4>Analysis categories</h4><div class="cfm-cats">${cats}</div>`;
  return body;
}

function _findings(findings, fmt) {
  if (!Array.isArray(findings) || !findings.length) return '';
  const items = findings.map((f) => `<li>${fmt(f)}</li>`).join('');
  return `<h4>Findings</h4><ul class="cfm-findings">${items}</ul>`;
}

function _kv(label, value) {
  return `<div class="cfm-kv"><span>${_esc(label)}</span><strong>${_esc(String(value))}</strong></div>`;
}

function _token(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]+/g, '-');
}

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, subtitle, trigger, content });
  return modalManager.open({ title, subtitle, trigger, content });
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str == null ? '' : String(str);
  return el.innerHTML;
}

const cfmStyles = document.createElement('style');
cfmStyles.textContent = `
  .cfm-root { padding: 4px 2px; font-size: 0.84rem; color: #c9d1d9; }
  .cfm-root h4 {
    color: #6699cc; font-size: 0.72rem; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase; margin: 16px 0 8px;
  }
  .cfm-desc { color: #8b919a; margin: 0 0 12px; line-height: 1.4; }
  .cfm-status {
    display: flex; align-items: baseline; gap: 10px;
    background: rgba(255,255,255,0.03);
    border: 1px dashed rgba(255,255,255,0.08);
    border-radius: 2px; padding: 8px 10px;
  }
  .cfm-status-label { color: #8b919a; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; }
  .cfm-status strong { color: #e4e6eb; font-family: "JetBrains Mono", monospace; }
  .cfm-status-detail { color: #8b919a; }
  .cfm-checks { display: flex; flex-direction: column; gap: 6px; }
  .cfm-check {
    display: grid; grid-template-columns: 90px 80px 1fr; gap: 8px;
    align-items: start; padding: 7px 10px; font-size: 0.78rem;
    background: rgba(255,255,255,0.03);
    border: 1px dashed rgba(255,255,255,0.08); border-radius: 2px;
  }
  .cfm-check-id { color: #8b919a; font-family: "JetBrains Mono", monospace; }
  .cfm-check-status { color: #e4e6eb; font-family: "JetBrains Mono", monospace; font-size: 0.72rem; }
  .cfm-check-desc { color: #c9d1d9; }
  .cfm-check-detail { grid-column: 1 / -1; color: #6e7681; font-size: 0.72rem; }
  .cfm-check.cfm-status-pass .cfm-check-status { color: #3fb950; }
  .cfm-check.cfm-status-fail .cfm-check-status { color: #f85149; }
  .cfm-check.cfm-status-warning .cfm-check-status { color: #d29922; }
  .cfm-kvs { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; }
  .cfm-kv { display: grid; grid-template-columns: 200px 1fr; gap: 8px; padding: 4px 0; }
  .cfm-kv span { color: #8b919a; }
  .cfm-kv strong { color: #e4e6eb; font-family: "JetBrains Mono", monospace; font-size: 0.74rem; }
  .cfm-findings { margin: 0; padding-left: 18px; color: #d29922; }
  .cfm-findings li { margin: 3px 0; }
  .cfm-cats { display: flex; flex-direction: column; gap: 6px; }
  .cfm-cat {
    padding: 7px 10px; background: rgba(255,255,255,0.03);
    border: 1px dashed rgba(255,255,255,0.08); border-radius: 2px;
  }
  .cfm-cat strong { display: block; color: #e4e6eb; font-size: 0.78rem; margin-bottom: 2px; }
  .cfm-cat span { color: #8b919a; font-size: 0.76rem; }
  .cfm-empty { color: #8b919a; padding: 8px 10px; }
`;
document.head.appendChild(cfmStyles);
