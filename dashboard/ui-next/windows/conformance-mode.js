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
  environmental: 'Environmental Health',
  post_hoc: 'Decision Re-verification',
  spc: 'Statistical Process Control',
  element: 'Structural Verification',
  behavioral: 'Behavioral Anomalies',
};

const MODE_DESCRIPTION = {
  environmental: 'Pre-flight checks that the governance environment is sound: policy rules, signing keys, chain files, disk space, process health.',
  post_hoc: 'Re-verifies recorded decisions against current policy: structural integrity, classification consistency, approval provenance, negative constraints.',
  spc: 'Statistical Process Control over the decision stream: ALLOW rate, classification mix, rule concentration, decision throughput, tool diversity.',
  element: 'Structural verification of the governance chain: chain record schemas, hash linkage, signatures, configuration state.',
  behavioral: 'Behavioral anomaly detection: classification consistency, decision reversals, temporal patterns, approval provenance, policy-rule coverage.',
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

// QS-046: each mode's detail is organized around the categories its
// description names, so the description and the detail never disconnect.

// Environmental: the 10 ENV checks grouped under the 6 named categories.
const ENV_CATEGORIES = [
  ['Policy rules', ['ENV-001']],
  ['Signing keys', ['ENV-002']],
  ['Chain files', ['ENV-003', 'ENV-005', 'ENV-006']],
  ['Disk space', ['ENV-007']],
  ['Process health', ['ENV-008', 'ENV-009']],
  ['Configuration', ['ENV-004', 'ENV-010']],
];

// Decision Re-verification: four categories the post-hoc verifier covers.
// The API exposes only aggregate counts/findings (no per-category split),
// so each card shows the shared status + what it covers.
const POSTHOC_CATEGORIES = [
  ['Structural integrity', 'Record hash and prev-link of each verified decision.'],
  ['Classification consistency', 'Recorded classification matches the governed decision.'],
  ['Approval provenance', 'Approvals trace to a valid operator and approval event.'],
  ['Negative constraints', 'No plaintext secrets or disallowed content in the record.'],
];

// Statistical Process Control: five tracked metrics.
const SPC_METRICS = [
  ['ALLOW rate', 'Share of decisions resolving to ALLOW.'],
  ['Classification mix', 'Distribution across classification tiers.'],
  ['Rule concentration', 'Concentration of matches on individual policy rules.'],
  ['Decision throughput', 'Decisions processed per unit time.'],
  ['Tool diversity', 'Spread of distinct tools in the decision stream.'],
];

// Structural Verification: four categories, mapped to element_id prefixes
// the element verifier emits.
const ELEMENT_CATEGORIES = [
  ['Chain record schemas', ['CHAIN_RECORD_SCHEMA']],
  ['Hash linkage', ['HASH_LINKAGE']],
  ['Signatures', ['SIGNATURE_VALIDITY']],
  ['Configuration state', ['CONFIGURATION_STATE', 'TIER_REGISTRY_CONSISTENCY', 'NEGATIVE_CONSTRAINTS']],
];

// Behavioral Anomalies: five categories, mapped to behavioral finding types.
const BEHAVIORAL_CATEGORIES = [
  ['Classification consistency', ['classification_inconsistency'], 'Same tool reclassified without a visible cause.'],
  ['Decision reversals', ['decision_reversal'], 'A tool flips ALLOW/DENY with no intervening change.'],
  ['Temporal patterns', ['temporal_pattern'], 'Off-hours activity relative to the baseline.'],
  ['Approval provenance', ['approval_provenance'], 'Aged approvals or operators with no prior history.'],
  ['Policy-rule coverage', ['policy_rule_coverage'], 'Dead rules or overly broad rules.'],
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

// Worst-of status across a set of check statuses (fail > warning > pass).
function _worst(statuses) {
  if (statuses.some((s) => /fail|critical|flag/.test(s))) return ['fail', 'attention'];
  if (statuses.some((s) => /warn|high/.test(s))) return ['warning', 'warning'];
  if (statuses.some((s) => /pass|ok|healthy/.test(s))) return ['pass', 'ok'];
  return ['unknown', 'idle'];
}

// One category card: name, status pill, and a list of detail lines.
function _categoryCard(name, statusText, statusToken, lines) {
  const body = (lines && lines.length)
    ? lines.map((l) => `<div class="cfm-cat-line">${l}</div>`).join('')
    : '';
  return `
    <div class="cfm-cat cfm-cat-${_token(statusToken)}">
      <div class="cfm-cat-head">
        <strong>${_esc(name)}</strong>
        <span class="cfm-cat-status">${_esc(statusText)}</span>
      </div>
      ${body}
    </div>`;
}

function _grid(cards) {
  return `<div class="cfm-cat-grid">${cards.join('')}</div>`;
}

function _environmental(data) {
  const checks = (data.latest_snapshot && data.latest_snapshot.checks)
    || (data.modes && data.modes.environmental && data.modes.environmental.checks)
    || {};
  const haveSnapshot = Object.keys(checks).length > 0;
  const cards = ENV_CATEGORIES.map(([name, ids]) => {
    const lines = ids.map((id) => {
      const check = checks[id] || {};
      const status = String(check.status || (haveSnapshot ? 'unknown' : 'no data'));
      const reason = check.detail ? ` — ${_esc(check.detail)}` : '';
      return `<span class="cfm-check-id">${_esc(id)}</span> <span class="cfm-check-st cfm-status-${_token(status)}">${_esc(status)}</span> <span class="cfm-check-desc">${_esc(ENV_DESCRIPTION[id] || '')}</span>${reason}`;
    });
    const [stText, stTok] = haveSnapshot
      ? _worst(ids.map((id) => String((checks[id] || {}).status || 'unknown')))
      : ['no data', 'idle'];
    return _categoryCard(name, stText, stTok, lines);
  });
  return _grid(cards);
}

function _postHoc(mode) {
  const s = String(mode.status || '').toLowerCase();
  const idle = s === 'idle' || s === 'unavailable';
  const findings = Array.isArray(mode.findings) ? mode.findings : [];
  let summary = '';
  if (!idle) {
    const kvs = [];
    if (mode.decisions_verified != null) kvs.push(_kv('Decisions verified', mode.decisions_verified));
    if (mode.skipped != null) kvs.push(_kv('Skipped', mode.skipped));
    if (mode.queue_depth != null) kvs.push(_kv('Verification queue', `${mode.queue_depth} of ${mode.queue_capacity ?? '?'}`));
    if (kvs.length) summary = `<div class="cfm-kvs">${kvs.join('')}</div>`;
  }
  const cards = POSTHOC_CATEGORIES.map(([name, what]) => {
    const lines = [`<span class="cfm-cat-what">${_esc(what)}</span>`];
    let stText = idle ? 'awaiting decisions' : 'verified';
    let stTok = idle ? 'idle' : 'ok';
    // The API does not break findings down per category; surface any
    // findings as a window-level list below rather than per card.
    if (!idle && findings.length) { stText = 'see findings'; stTok = 'warning'; }
    return _categoryCard(name, stText, stTok, lines);
  });
  let body = summary + _grid(cards);
  body += _findings(findings, (f) => `${_esc(f.check || f.type || 'finding')}: ${_esc(f.detail || '')}`);
  return body;
}

function _spc(mode) {
  const s = String(mode.status || '').toLowerCase();
  const warming = s === 'warming_up' || s === 'learning';
  const activeName = String(mode.metric_name || mode.metric_id || '').toLowerCase();
  const cards = SPC_METRICS.map(([name, what]) => {
    const lines = [`<span class="cfm-cat-what">${_esc(what)}</span>`];
    let stText; let stTok;
    if (warming) {
      stText = `warming up (${mode.decisions_collected ?? 0}/${mode.minimum_required ?? 100})`;
      stTok = 'idle';
    } else if (activeName && name.toLowerCase() === activeName) {
      if (mode.current_value != null) lines.push(`<span class="cfm-cat-line">current ${_esc(mode.current_value)}</span>`);
      if (mode.ucl != null || mode.lcl != null) lines.push(`<span class="cfm-cat-line">limits ${_esc(mode.lcl ?? '--')} … ${_esc(mode.ucl ?? '--')}</span>`);
      stText = mode.status || 'active'; stTok = 'attention';
    } else if (s === 'idle' || s === 'unavailable') {
      stText = 'awaiting decisions'; stTok = 'idle';
    } else {
      stText = 'within limits'; stTok = 'ok';
    }
    return _categoryCard(name, stText, stTok, lines);
  });
  return _grid(cards);
}

function _element(mode) {
  const s = String(mode.status || '').toLowerCase();
  const idle = s === 'idle' || s === 'unavailable';
  const findings = Array.isArray(mode.findings) ? mode.findings : [];
  let summary = '';
  if (!idle && mode.elements_checked != null) {
    summary = `<div class="cfm-kvs">${_kv('Elements', `${mode.elements_checked} checked · ${mode.elements_passed ?? '?'} passed · ${mode.elements_flagged ?? 0} flagged · ${mode.elements_skipped ?? 0} skipped`)}</div>`;
  }
  const cards = ELEMENT_CATEGORIES.map(([name, ids]) => {
    const hits = findings.filter((f) => ids.includes(String(f.element_id || '').toUpperCase()));
    const lines = hits.map((f) => `<span class="cfm-cat-line">${_esc(f.severity || '')}: ${_esc(f.detail || '')}</span>`);
    let stText; let stTok;
    if (idle) { stText = 'awaiting verification'; stTok = 'idle'; }
    else if (hits.length) { stText = `${hits.length} flagged`; stTok = 'attention'; }
    else { stText = 'pass'; stTok = 'ok'; }
    return _categoryCard(name, stText, stTok, lines);
  });
  return summary + _grid(cards);
}

function _behavioral(mode) {
  const s = String(mode.status || '').toLowerCase();
  const warming = s === 'warming_up';
  const idle = s === 'idle' || s === 'unavailable';
  const findings = Array.isArray(mode.findings) ? mode.findings : [];
  let summary = '';
  if (warming) {
    summary = `<div class="cfm-kvs">${_kv('Warm-up progress', `${mode.decisions_analyzed ?? 0} / ${mode.minimum_required ?? 100} decisions`)}</div>`;
  } else if (mode.anomaly_count != null) {
    summary = `<div class="cfm-kvs">${_kv('Anomalies', mode.anomaly_count)}</div>`;
  }
  const cards = BEHAVIORAL_CATEGORIES.map(([name, types, what]) => {
    const hits = findings.filter((f) => types.includes(String(f.type || f.finding_type || '')));
    const lines = [`<span class="cfm-cat-what">${_esc(what)}</span>`];
    for (const f of hits) lines.push(`<span class="cfm-cat-line">${_esc(f.subtype || f.detail || 'anomaly')}</span>`);
    let stText; let stTok;
    if (warming) { stText = 'warming up'; stTok = 'idle'; }
    else if (idle) { stText = 'awaiting decisions'; stTok = 'idle'; }
    else if (hits.length) { stText = `${hits.length} finding(s)`; stTok = 'attention'; }
    else { stText = 'clear'; stTok = 'ok'; }
    return _categoryCard(name, stText, stTok, lines);
  });
  return summary + _grid(cards);
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
  /* QS-046: content-sized layout — the window content caps its width so it
     never floats in a vast empty frame, and categories tile in a grid. */
  .cfm-root { padding: 4px 2px; font-size: 0.84rem; color: #c9d1d9; max-width: 760px; }
  .cfm-root h4 {
    color: #6699cc; font-size: 0.72rem; font-weight: 600;
    letter-spacing: 0.08em; text-transform: uppercase; margin: 16px 0 8px;
  }
  .cfm-desc { color: #8b919a; margin: 0 0 12px; line-height: 1.4; }
  .cfm-status {
    display: flex; align-items: baseline; gap: 10px;
    background: rgba(255,255,255,0.03);
    border: 1px dashed rgba(255,255,255,0.08);
    border-radius: 2px; padding: 8px 10px; margin-bottom: 12px;
  }
  .cfm-status-label { color: #8b919a; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; }
  .cfm-status strong { color: #e4e6eb; font-family: "JetBrains Mono", monospace; }
  .cfm-status-detail { color: #8b919a; }

  /* Category grid: fills available width with content-sized columns. */
  .cfm-cat-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 8px;
  }
  .cfm-cat {
    padding: 8px 10px; border-radius: 2px;
    background: rgba(255,255,255,0.025);
    border: 1px solid rgba(255,255,255,0.06);
    border-left: 2px solid rgba(255,255,255,0.12);
  }
  .cfm-cat-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  .cfm-cat-head strong { color: #e4e6eb; font-size: 0.78rem; }
  .cfm-cat-status { color: #8b919a; font-family: "JetBrains Mono", monospace; font-size: 0.68rem; white-space: nowrap; }
  .cfm-cat-what { display: block; color: #8b919a; font-size: 0.72rem; line-height: 1.35; margin-top: 3px; }
  .cfm-cat-line { display: block; color: #c9d1d9; font-size: 0.72rem; margin-top: 3px; }
  .cfm-cat-line .cfm-check-id { color: #8b919a; font-family: "JetBrains Mono", monospace; }
  .cfm-cat-line .cfm-check-desc { color: #c9d1d9; }
  .cfm-cat-line .cfm-check-st { font-family: "JetBrains Mono", monospace; font-size: 0.68rem; }
  /* status accents on the left border + status pill */
  .cfm-cat-ok { border-left-color: #3fb950; }
  .cfm-cat-ok .cfm-cat-status { color: #3fb950; }
  .cfm-cat-attention { border-left-color: #f85149; }
  .cfm-cat-attention .cfm-cat-status { color: #f85149; }
  .cfm-cat-warning { border-left-color: #d29922; }
  .cfm-cat-warning .cfm-cat-status { color: #d29922; }
  .cfm-cat-idle { border-left-color: rgba(255,255,255,0.18); }
  .cfm-status-pass { color: #3fb950; }
  .cfm-status-fail { color: #f85149; }
  .cfm-status-warning { color: #d29922; }

  .cfm-kvs { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
  .cfm-kv { display: grid; grid-template-columns: minmax(120px, max-content) 1fr; gap: 10px; padding: 2px 0; }
  .cfm-kv span { color: #8b919a; }
  .cfm-kv strong { color: #e4e6eb; font-family: "JetBrains Mono", monospace; font-size: 0.74rem; }
  .cfm-findings { margin: 8px 0 0; padding-left: 18px; color: #d29922; }
  .cfm-findings li { margin: 3px 0; }
  .cfm-empty { color: #8b919a; padding: 8px 10px; }
`;
document.head.appendChild(cfmStyles);
