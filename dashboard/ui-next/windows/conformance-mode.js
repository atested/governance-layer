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

// QS-047: a sentence or two on what the mode DOES (not a list of categories).
const MODE_DESCRIPTION = {
  environmental: 'Continuously verifies the governance environment is sound. These checks run before the system accepts its first decision and repeat throughout operation. All must pass for the system to remain operational.',
  post_hoc: 'Independently re-verifies every governance decision after it has been made and recorded. Verification happens after the fact so decisions aren\'t slowed by the inspection process, and the verification is truly independent of the decision-maker.',
  spc: 'Monitors the decision stream for statistically significant shifts that no single decision check would catch.',
  element: 'Continually verifies the running system conforms to its specifications at the structural level.',
  behavioral: 'Detects patterns across the decision stream that indicate drift, misconfiguration, or unexpected behavior.',
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
  ['Chain record schemas', ['CHAIN_RECORD_SCHEMA'], 'Each chain record carries its required fields.'],
  ['Hash linkage', ['HASH_LINKAGE'], 'Every record links to its predecessor by hash.'],
  ['Signatures', ['SIGNATURE_VALIDITY'], 'Signed records verify against the signing key.'],
  ['Configuration state', ['CONFIGURATION_STATE', 'TIER_REGISTRY_CONSISTENCY', 'NEGATIVE_CONSTRAINTS'], 'Policy, capability registry, and tier registry are well-formed.'],
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

// QS-047: one detail item, two lines — "ID/name — Status" then a
// description line. An optional extra line carries a failure reason or
// live value. Used consistently across all five windows.
function _item(id, statusText, statusToken, desc, extra) {
  return `
    <div class="cfm-item cfm-item-${_token(statusToken)}">
      <div class="cfm-item-head">
        <span class="cfm-item-id">${_esc(id)}</span>
        <span class="cfm-item-dash">—</span>
        <span class="cfm-item-status">${_esc(statusText)}</span>
      </div>
      <div class="cfm-item-desc">${_esc(desc)}</div>
      ${extra ? `<div class="cfm-item-extra">${_esc(extra)}</div>` : ''}
    </div>`;
}

function _itemList(items) {
  return `<div class="cfm-items">${items.join('')}</div>`;
}

// Pass/Fail/Warning-style label + color token from a raw check status.
function _checkStatus(raw, fallback) {
  const s = String(raw || '').toLowerCase();
  if (!s) return [fallback || 'No data', 'idle'];
  if (/fail|critical|flag/.test(s)) return ['Fail', 'attention'];
  if (/warn|high/.test(s)) return ['Warning', 'warning'];
  if (/pass|ok|healthy/.test(s)) return ['Pass', 'ok'];
  return [raw, 'idle'];
}

function _environmental(data) {
  const checks = (data.latest_snapshot && data.latest_snapshot.checks)
    || (data.modes && data.modes.environmental && data.modes.environmental.checks)
    || {};
  const ids = Object.keys(ENV_DESCRIPTION);
  for (const k of Object.keys(checks)) if (!ids.includes(k)) ids.push(k);
  const items = ids.map((id) => {
    const check = checks[id] || {};
    const [stText, stTok] = _checkStatus(check.status, 'No data');
    return _item(id, stText, stTok, ENV_DESCRIPTION[id] || '', check.detail || '');
  });
  return _itemList(items);
}

function _postHoc(mode) {
  const s = String(mode.status || '').toLowerCase();
  const idle = s === 'idle' || s === 'unavailable';
  const findings = Array.isArray(mode.findings) ? mode.findings : [];
  const items = POSTHOC_CATEGORIES.map(([name, what]) => {
    let stText = idle ? 'Awaiting decisions' : 'Verified';
    let stTok = idle ? 'idle' : 'ok';
    if (!idle && findings.length) { stText = 'See findings'; stTok = 'warning'; }
    return _item(name, stText, stTok, what);
  });
  let body = _itemList(items);
  body += _findings(findings, (f) => `${_esc(f.check || f.type || 'finding')}: ${_esc(f.detail || '')}`);
  return body;
}

function _spc(mode) {
  const s = String(mode.status || '').toLowerCase();
  const warming = s === 'warming_up' || s === 'learning';
  const idle = s === 'idle' || s === 'unavailable';
  const activeName = String(mode.metric_name || mode.metric_id || '').toLowerCase();
  const items = SPC_METRICS.map(([name, what]) => {
    let stText; let stTok; let extra = '';
    if (warming) {
      stText = `Warming up (${mode.decisions_collected ?? 0}/${mode.minimum_required ?? 100})`;
      stTok = 'idle';
    } else if (activeName && name.toLowerCase() === activeName) {
      stText = mode.status || 'Active'; stTok = 'attention';
      const lim = (mode.lcl != null || mode.ucl != null) ? ` · limits ${mode.lcl ?? '--'} … ${mode.ucl ?? '--'}` : '';
      extra = `current ${mode.current_value ?? '--'}${lim}`;
    } else if (idle) {
      stText = 'Awaiting decisions'; stTok = 'idle';
    } else {
      stText = 'Within limits'; stTok = 'ok';
    }
    return _item(name, stText, stTok, what, extra);
  });
  return _itemList(items);
}

function _element(mode) {
  const s = String(mode.status || '').toLowerCase();
  const idle = s === 'idle' || s === 'unavailable';
  const findings = Array.isArray(mode.findings) ? mode.findings : [];
  let summary = '';
  if (!idle && mode.elements_checked != null) {
    summary = `<div class="cfm-kvs">${_kv('Elements', `${mode.elements_checked} checked · ${mode.elements_passed ?? '?'} passed · ${mode.elements_flagged ?? 0} flagged · ${mode.elements_skipped ?? 0} skipped`)}</div>`;
  }
  const items = ELEMENT_CATEGORIES.map(([name, ids, what]) => {
    const hits = findings.filter((f) => ids.includes(String(f.element_id || '').toUpperCase()));
    let stText; let stTok;
    if (idle) { stText = 'Awaiting verification'; stTok = 'idle'; }
    else if (hits.length) { stText = `${hits.length} flagged`; stTok = 'attention'; }
    else { stText = 'Pass'; stTok = 'ok'; }
    const extra = hits.map((f) => `${f.severity || ''}: ${f.detail || ''}`).join('; ');
    return _item(name, stText, stTok, what || '', extra);
  });
  return summary + _itemList(items);
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
  const items = BEHAVIORAL_CATEGORIES.map(([name, types, what]) => {
    const hits = findings.filter((f) => types.includes(String(f.type || f.finding_type || '')));
    let stText; let stTok;
    if (warming) { stText = 'Warming up'; stTok = 'idle'; }
    else if (idle) { stText = 'Awaiting decisions'; stTok = 'idle'; }
    else if (hits.length) { stText = `${hits.length} finding(s)`; stTok = 'attention'; }
    else { stText = 'Clear'; stTok = 'ok'; }
    const extra = hits.map((f) => f.subtype || f.detail || 'anomaly').join('; ');
    return _item(name, stText, stTok, what, extra);
  });
  return summary + _itemList(items);
}

function _findings(findings, fmt) {
  if (!Array.isArray(findings) || !findings.length) return '';
  const items = findings.map((f) => `<li>${fmt(f)}</li>`).join('');
  return `<h4>Findings</h4><ul class="cfm-findings">${items}</ul>`;
}

// QS-047: Active Conditions detail window — one item per condition in the
// same two-line format (condition id — severity, then detail; guidance below).
export function openConformanceConditionsWindow(conditions, trigger) {
  const list = Array.isArray(conditions) ? conditions : [];
  const content = document.createElement('div');
  content.className = 'cfm-root';
  const parts = [];
  parts.push('<p class="cfm-desc">Active conditions are findings from the quality service that affect how the system operates. When a condition is detected, the proxy responds according to its built-in procedures.</p>');
  if (!list.length) {
    parts.push('<div class="cfm-empty">No active conditions.</div>');
  } else {
    const items = list.map((c) => {
      const id = c.condition_id || c.condition_type || 'condition';
      const sev = String(c.severity || 'medium');
      const tok = /critical|fail/.test(sev.toLowerCase()) ? 'attention'
        : /high|warn/.test(sev.toLowerCase()) ? 'warning' : 'idle';
      const desc = c.detail || c.condition_type || '';
      const when = c.detected_at ? `detected ${c.detected_at}` : '';
      const extra = [c.guidance || '', when].filter(Boolean).join(' · ');
      return _item(id, sev, tok, desc, extra);
    });
    parts.push(_itemList(items));
  }
  content.innerHTML = parts.join('');
  _openAsChild('Active Conditions', 'Quality service findings', trigger, content);
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
  .cfm-root { padding: 4px 2px; font-size: 0.84rem; color: #c9d1d9; max-width: 540px; }
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

  /* QS-047: consistent two-line item — "ID — Status" then description.
     A status-colored left accent and status text carry the color. */
  .cfm-items { display: flex; flex-direction: column; gap: 6px; }
  .cfm-item {
    padding: 8px 10px; border-radius: 3px;
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-left: 3px solid rgba(255,255,255,0.14);
  }
  .cfm-item-head { display: flex; align-items: baseline; gap: 6px; }
  .cfm-item-id { color: #e4e6eb; font-family: "JetBrains Mono", monospace; font-size: 0.76rem; font-weight: 600; }
  .cfm-item-dash { color: #6e7681; }
  .cfm-item-status { font-family: "JetBrains Mono", monospace; font-size: 0.72rem; }
  .cfm-item-desc { color: #9aa3ad; font-size: 0.74rem; line-height: 1.4; margin-top: 3px; }
  .cfm-item-extra { color: #6e7681; font-size: 0.71rem; line-height: 1.35; margin-top: 3px; }
  .cfm-item-ok { border-left-color: #3fb950; }
  .cfm-item-ok .cfm-item-status { color: #3fb950; }
  .cfm-item-attention { border-left-color: #f85149; }
  .cfm-item-attention .cfm-item-status { color: #f85149; }
  .cfm-item-warning { border-left-color: #d29922; }
  .cfm-item-warning .cfm-item-status { color: #d29922; }
  .cfm-item-idle { border-left-color: #6699cc; }
  .cfm-item-idle .cfm-item-status { color: #8b9bb0; }

  .cfm-kvs { display: flex; flex-direction: column; gap: 4px; margin-bottom: 10px; }
  .cfm-kv { display: grid; grid-template-columns: minmax(120px, max-content) 1fr; gap: 10px; padding: 2px 0; }
  .cfm-kv span { color: #8b919a; }
  .cfm-kv strong { color: #e4e6eb; font-family: "JetBrains Mono", monospace; font-size: 0.74rem; }
  .cfm-findings { margin: 8px 0 0; padding-left: 18px; color: #d29922; }
  .cfm-findings li { margin: 3px 0; }
  .cfm-empty { color: #8b919a; padding: 8px 10px; }
`;
document.head.appendChild(cfmStyles);
