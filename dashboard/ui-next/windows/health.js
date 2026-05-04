/**
 * Health window — child window (depth 1).
 * D-041 redesign: accent bars reflecting state, critical alert pane,
 * six data panes in 3x2 grid, clickable drill-downs for Chain Integrity
 * and Deny Rate, recent health events table with grandchild drill-down.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { openRecordDetail } from './record-detail.js';
import { installWindowTooltips, setTooltip } from '../tooltip-utils.js';

/**
 * Open the Health window.
 * @param {HTMLElement|null} trigger
 */
export function openHealthWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'hw-root';

  const result = _openAsChild('Health', 'System diagnostics and chain integrity', trigger, content);
  if (!result) return;

  const state = { el: content, data: null };
  _loadData(state);
}

// ---------- Data loading ----------

async function _loadData(state) {
  state.el.innerHTML = '<div class="hw-loading">Loading health data\u2026</div>';

  const res = await api.getHealth();
  if (!res.ok) {
    state.el.innerHTML = `<div class="hw-error">${_esc(res.error)}</div>`;
    return;
  }

  state.data = res.data;
  _renderAll(state);
  installWindowTooltips(state.el);
}

// ---------- Render ----------

function _renderAll(state) {
  const h = state.data;
  const el = state.el;
  el.innerHTML = '';

  const overall = h.overall_status || 'healthy';

  // Title accent bar
  const accentBar = document.createElement('div');
  accentBar.className = `hw-title-accent hw-accent-${_statusColor(overall)}`;
  el.appendChild(accentBar);

  // Overall status pill
  const statusRow = document.createElement('div');
  statusRow.className = 'hw-status-row';
  statusRow.innerHTML = `<span class="hw-status-pill hw-pill-${_statusColor(overall)}">${_esc(_statusLabel(overall))}</span>`;
  el.appendChild(statusRow);

  // Critical alert pane (conditional)
  _renderAlertPane(state, h.alerts || []);

  // Six data panes in 3 rows of 2
  const grid = document.createElement('div');
  grid.className = 'hw-pane-grid';

  grid.appendChild(_buildChainPane(state, h));
  grid.appendChild(_buildDenyRatePane(state, h));
  grid.appendChild(_buildIntegrityPane(h));
  grid.appendChild(_buildStoragePane(h));
  grid.appendChild(_buildUsersPane(h));
  grid.appendChild(_buildLicensePane(h));

  el.appendChild(grid);

  // Recent health events table
  _renderEventsTable(state, h);
}

// ---------- Alert pane ----------

function _renderAlertPane(state, alerts) {
  if (!alerts.length) return;

  for (const alert of alerts) {
    const severity = alert.severity || 'info';
    const pane = document.createElement('div');
    pane.className = `hw-alert-pane hw-alert-${severity === 'critical' ? 'red' : severity === 'attention' ? 'amber' : 'blue'}`;

    pane.innerHTML = `
      <div class="hw-alert-top">
        <span class="hw-alert-badge hw-badge-${severity === 'critical' ? 'red' : 'amber'}">${_esc(severity === 'critical' ? 'Critical' : 'Warning')}</span>
      </div>
      <p class="hw-alert-desc">${_esc(alert.message || '')}</p>
      ${alert.guidance ? `<p class="hw-alert-guidance">${_esc(alert.guidance)}</p>` : ''}
    `;

    const ackBtn = document.createElement('button');
    ackBtn.className = 'hw-alert-ack';
    ackBtn.textContent = 'Acknowledge';
    setTooltip(ackBtn, 'Records that you have seen this health alert.');
    ackBtn.addEventListener('click', async () => {
      const res = await api.postHealthAcknowledge({ source: alert.source, message: alert.message });
      if (res.ok) _loadData(state);
    });
    pane.appendChild(ackBtn);

    state.el.appendChild(pane);
  }
}

// ---------- Data panes ----------

function _buildChainPane(state, h) {
  const chain = h.chain || {};
  const bgv = h.background_verification || {};
  const chainStatus = chain.status || 'healthy';

  const pane = _pane('green', 'Chain integrity', true);
  const body = pane.querySelector('.hw-pane-body');
  const statusColor = chainStatus === 'critical' ? 'red' : chainStatus === 'attention' ? 'amber' : 'green';

  body.appendChild(_kvRow('Status', _statusLabel(chainStatus), statusColor));
  body.appendChild(_kvRow('Event count', _fmtNum(chain.chain_event_count ?? 0)));
  body.appendChild(_kvRow('Verified', chain.checked ? 'Yes' : 'No', chain.checked ? 'green' : 'amber'));
  body.appendChild(_kvRow('Background verifier', _verificationLabel(bgv), _verificationColor(bgv)));

  pane.addEventListener('click', () => _openChainDetail(state, h));
  setTooltip(pane, 'Open chain integrity details: hash linkage, break status, and repair evidence.');
  return pane;
}

function _buildDenyRatePane(state, h) {
  const dr = h.deny_rate || {};

  const pane = _pane('blue', 'Deny rate', true);
  const body = pane.querySelector('.hw-pane-body');

  const recentPct = dr.deny_rate != null ? (dr.deny_rate * 100).toFixed(1) + '%' : '0%';
  const histPct = dr.historical_average != null ? (dr.historical_average * 100).toFixed(1) + '%' : '0%';

  body.appendChild(_kvRow('Recent', recentPct, dr.anomaly ? 'amber' : undefined));
  body.appendChild(_kvRow('Historical avg', histPct));
  body.appendChild(_kvRow('Anomaly', dr.anomaly ? 'Detected' : 'None', dr.anomaly ? 'amber' : 'green'));

  pane.addEventListener('click', () => _openDenyRateDetail(state, h));
  setTooltip(pane, 'Open deny-rate details and recent denied operation context.');
  return pane;
}

function _buildIntegrityPane(h) {
  const integrity = h.integrity || {};
  const pane = _pane('purple', 'Integrity', false);
  const body = pane.querySelector('.hw-pane-body');

  // Product version
  if (h.version) {
    body.appendChild(_kvRow('Version', `v${h.version}`, 'green'));
  }

  if (!integrity.available) {
    body.appendChild(_kvRow('Proxy code hash', 'Not available', 'amber'));
    body.appendChild(_kvRow('Policy rules hash', 'Not available', 'amber'));
    body.appendChild(_kvRow('Chain file status', 'Not available', 'amber'));
    return pane;
  }

  body.appendChild(_kvRow('Proxy code hash', _truncHash(integrity.proxy_code_hash)));
  const policyStatus = integrity.policy_rules_status === 'changed' ? 'Changed' : 'Verified';
  body.appendChild(_kvRow('Policy rules hash', `${_truncHash(integrity.policy_rules_hash)} (${policyStatus})`, policyStatus === 'Changed' ? 'amber' : 'green'));
  const chainStatus = _chainFileStatusLabel(integrity.chain_file_status);
  const chainColor = chainStatus === 'Intact' ? 'green' : chainStatus === 'Not available' ? 'amber' : 'red';
  body.appendChild(_kvRow('Chain file status', chainStatus, chainColor));
  return pane;
}

function _buildStoragePane(h) {
  const s = h.storage || {};
  const pane = _pane('dark-blue', 'Storage', false);
  const body = pane.querySelector('.hw-pane-body');

  body.appendChild(_kvRow('Chain size', _formatBytes(s.chain_size_bytes)));
  body.appendChild(_kvRow('Stability log', _formatBytes(s.stability_log_size_bytes)));
  body.appendChild(_kvRow('Archive size', _formatBytes(s.archive_size_bytes)));
  body.appendChild(_kvRow('Archives', _fmtNum(s.archive_count ?? 0)));

  return pane;
}

function _buildUsersPane(h) {
  const u = h.users || {};
  const pane = _pane('amber', 'Users', false);
  const body = pane.querySelector('.hw-pane-body');

  body.appendChild(_kvRow('Unique users', _fmtNum(u.unique_users ?? 0)));
  body.appendChild(_kvRow('Anomalies', u.anomalies?.length ? String(u.anomalies.length) : 'None', u.anomalies?.length ? 'amber' : 'green'));

  return pane;
}

function _buildLicensePane(h) {
  const lic = h.license || {};
  const rawStatus = lic.status || 'unknown';
  // Map internal status to human-readable labels
  const labelMap = { unknown: 'Trial', trial: 'Trial', active: 'Licensed', expired: 'Expired' };
  const label = labelMap[rawStatus.toLowerCase()] || rawStatus;
  const color = rawStatus.toLowerCase() === 'active' ? 'green' : 'amber';

  const pane = _pane('dark-blue', 'License', false);
  const body = pane.querySelector('.hw-pane-body');

  body.appendChild(_kvRow('Status', label, color));

  // Show trial days remaining if available
  if (lic.trial_days_remaining != null) {
    body.appendChild(_kvRow('Trial days left', String(lic.trial_days_remaining)));
  }
  if (lic.tier) {
    body.appendChild(_kvRow('Tier', lic.tier));
  }

  return pane;
}

// ---------- Pane builder ----------

function _pane(accentColor, title, clickable) {
  const pane = document.createElement('div');
  pane.className = 'hw-pane' + (clickable ? ' hw-pane-clickable' : '');
  const tooltip = _paneTooltip(title);

  pane.innerHTML = `
    <div class="hw-pane-accent hw-accent-${accentColor}"></div>
    <div class="hw-pane-header">${_esc(title)}</div>
    <div class="hw-pane-body"></div>
  `;
  setTooltip(pane, tooltip);
  setTooltip(pane.querySelector('.hw-pane-header'), tooltip);
  return pane;
}

function _kvRow(label, value, color) {
  const row = document.createElement('div');
  row.className = 'hw-kv-row';
  row.innerHTML = `
    <span class="hw-kv-label">${_esc(label)}</span>
    <span class="hw-kv-value${color ? ` hw-kv-${color}` : ''}">${_esc(value)}</span>
  `;
  setTooltip(row.querySelector('.hw-kv-label'), _healthMetricTooltip(label));
  return row;
}

function _paneTooltip(title) {
  const tips = {
    'Chain integrity': 'Whether the hash-linked chain is structurally valid.',
    'Deny rate': 'How often policy denies recent mediated operations.',
    'Integrity': 'D-139 protection status for proxy code, policy rules, and chain file durability.',
    'Storage': 'Local storage footprint for chain, stability log, and archives.',
    'Users': 'Operator identities and activity anomalies in recent records.',
    'License': 'Current license or trial status for this installation.',
    'Recent health events': 'Recent stability, integrity, version, and anomaly events emitted by health monitoring.',
  };
  return tips[title] || `${title} health metric.`;
}

function _healthMetricTooltip(label) {
  const tips = {
    'Status': 'Current status for this health area.',
    'Event count': 'Number of chain events currently known to the dashboard.',
    'Verified': 'Whether chain verification has run and passed.',
    'Recent': 'Deny rate in the recent decision window.',
    'Historical avg': 'Baseline deny rate from prior records.',
    'Anomaly': 'Whether recent deny behavior differs from historical behavior.',
    'Proxy code hash': 'Hash of the critical proxy source files recorded at startup.',
    'Policy rules hash': 'Hash of the loaded policy rules and whether the runtime still verifies them.',
    'Chain file status': 'Whether the chain file matches D-139 integrity metadata.',
    'Chain size': 'Size of the decision chain file.',
    'Stability log': 'Size of the chain health stability log.',
    'Archive size': 'Storage used by archived chain segments.',
    'Archives': 'Number of retained chain archive files.',
    'Unique users': 'Distinct operator identities in recent chain records.',
    'Trial days left': 'Remaining trial period, when available.',
    'Tier': 'Current commercial tier.',
  };
  return tips[label] || `${label} health field.`;
}

// ---------- Grandchild: Chain Integrity Detail ----------

async function _openChainDetail(state, h) {
  const chain = h.chain || {};
  const bgv = h.background_verification || {};
  const chainStatus = chain.status || 'healthy';
  const color = chainStatus === 'critical' ? 'red' : chainStatus === 'attention' ? 'amber' : 'green';

  const content = document.createElement('div');
  content.className = 'hw-gc';

  // Accent bar
  const accent = document.createElement('div');
  accent.className = `hw-gc-accent hw-accent-${color}`;
  content.appendChild(accent);

  // Header
  const header = document.createElement('div');
  header.className = 'hw-gc-header';
  header.textContent = 'Chain integrity detail';
  content.appendChild(header);

  // Summary KV
  const kvSection = document.createElement('div');
  kvSection.className = 'hw-gc-section';
  kvSection.appendChild(_kvRow('Status', _statusLabel(chainStatus), color));
  kvSection.appendChild(_kvRow('Event count', _fmtNum(chain.chain_event_count ?? 0)));
  kvSection.appendChild(_kvRow('Verified', chain.checked ? 'Yes' : 'No'));
  kvSection.appendChild(_kvRow('Background verifier', _verificationLabel(bgv), _verificationColor(bgv)));
  if (bgv.last_verified_utc) kvSection.appendChild(_kvRow('Last background check', _formatHumanDate(bgv.last_verified_utc)));
  if (bgv.last_verified_count != null) kvSection.appendChild(_kvRow('Last verified count', _fmtNum(bgv.last_verified_count)));
  if (bgv.next_due_count != null) kvSection.appendChild(_kvRow('Next due count', _fmtNum(bgv.next_due_count)));

  if (chain.break_info) {
    const bi = chain.break_info;
    kvSection.appendChild(_kvRow('Break reason', bi.reason || 'Unknown', 'red'));
    if (bi.break_line != null) kvSection.appendChild(_kvRow('Break at line', String(bi.break_line)));
    if (bi.break_type) kvSection.appendChild(_kvRow('Break type', bi.break_type));
    if (bi.expected_hash) kvSection.appendChild(_kvRow('Expected hash', _truncHash(bi.expected_hash)));
    if (bi.actual_hash) kvSection.appendChild(_kvRow('Actual hash', _truncHash(bi.actual_hash)));
  }

  if (bgv.status === 'broken' || bgv.first_break_sequence != null) {
    const jumpSection = document.createElement('div');
    jumpSection.className = 'hw-gc-section';
    const jumpHeader = document.createElement('div');
    jumpHeader.className = 'hw-gc-sub-header';
    jumpHeader.textContent = 'Background verification';
    jumpSection.appendChild(jumpHeader);
    jumpSection.appendChild(_kvRow('Status', _verificationLabel(bgv), _verificationColor(bgv)));
    if (bgv.first_break_reason) jumpSection.appendChild(_kvRow('First break reason', bgv.first_break_reason, 'red'));
    if (bgv.first_break_sequence != null) jumpSection.appendChild(_kvRow('First break sequence', String(bgv.first_break_sequence), 'red'));
    const btn = document.createElement('button');
    btn.className = 'hw-jump-btn';
    btn.textContent = 'Open Chain Walker at break';
    btn.disabled = bgv.first_break_sequence == null;
    setTooltip(btn, 'Open Audit Walker centered on the first background verification break.');
    btn.addEventListener('click', () => {
      modalManager.closeAll();
      setTimeout(() => {
        import('./audit.js').then(mod => mod.openAuditWindow(null, {
          mode: 'walker',
          centerSequence: bgv.first_break_sequence,
        }));
      }, 0);
    });
    jumpSection.appendChild(btn);
    content.appendChild(jumpSection);
  }
  content.appendChild(kvSection);

  if (chain.repair_info) {
    const ri = chain.repair_info;
    const repairSection = document.createElement('div');
    repairSection.className = 'hw-gc-section';
    const repairHeader = document.createElement('div');
    repairHeader.className = 'hw-gc-sub-header';
    repairHeader.textContent = 'Repair information';
    repairSection.appendChild(repairHeader);
    repairSection.appendChild(_kvRow('Repaired', ri.repaired ? 'Yes' : 'No', ri.repaired ? 'green' : 'amber'));
    if (ri.repair_timestamp) repairSection.appendChild(_kvRow('Repaired at', _formatHumanDate(ri.repair_timestamp)));
    if (ri.repair_type) repairSection.appendChild(_kvRow('Repair type', ri.repair_type));
    content.appendChild(repairSection);
  }

  if (chain.pattern_alert) {
    const pa = chain.pattern_alert;
    const patternSection = document.createElement('div');
    patternSection.className = 'hw-gc-section';
    const patternHeader = document.createElement('div');
    patternHeader.className = 'hw-gc-sub-header';
    patternHeader.textContent = 'Pattern analysis';
    patternSection.appendChild(patternHeader);
    if (pa.pattern) patternSection.appendChild(_kvRow('Pattern', pa.pattern));
    if (pa.frequency) patternSection.appendChild(_kvRow('Frequency', pa.frequency));
    if (pa.assessment) patternSection.appendChild(_kvRow('Assessment', pa.assessment, 'amber'));
    content.appendChild(patternSection);
  }

  // Recent stability events related to chain
  const chainEvents = (h.recent_stability_events || []).filter(
    e => (e.event_type || '').includes('chain') || (e.event_type || '').includes('integrity') || (e.event_type || '').includes('break')
  ).slice(0, 5);
  if (chainEvents.length) {
    const evtSection = document.createElement('div');
    evtSection.className = 'hw-gc-section';
    const evtHeader = document.createElement('div');
    evtHeader.className = 'hw-gc-sub-header';
    evtHeader.textContent = 'Related events';
    evtSection.appendChild(evtHeader);
    for (const evt of chainEvents) {
      const row = document.createElement('div');
      row.className = 'hw-kv-row';
      row.innerHTML = `
        <span class="hw-kv-label">${_esc(_formatHumanDate(evt.timestamp))}</span>
        <span class="hw-kv-value">${_esc(evt.event_type || 'Unknown')}</span>
      `;
      evtSection.appendChild(row);
    }
    content.appendChild(evtSection);
  }

  modalManager.open({ title: 'Chain Integrity', subtitle: 'Chain verification detail', trigger: state.el, content });
}

// ---------- Grandchild: Deny Rate Detail ----------

async function _openDenyRateDetail(state, h) {
  const dr = h.deny_rate || {};
  const color = dr.anomaly ? 'amber' : 'green';

  const content = document.createElement('div');
  content.className = 'hw-gc';

  const accent = document.createElement('div');
  accent.className = `hw-gc-accent hw-accent-${color}`;
  content.appendChild(accent);

  const header = document.createElement('div');
  header.className = 'hw-gc-header';
  header.textContent = 'Deny rate detail';
  content.appendChild(header);

  // Summary
  const kvSection = document.createElement('div');
  kvSection.className = 'hw-gc-section';

  const recentPct = dr.deny_rate != null ? (dr.deny_rate * 100).toFixed(1) + '%' : '0%';
  const histPct = dr.historical_average != null ? (dr.historical_average * 100).toFixed(1) + '%' : '0%';

  kvSection.appendChild(_kvRow('Recent deny rate (last 100)', recentPct, dr.anomaly ? 'amber' : undefined));
  kvSection.appendChild(_kvRow('Historical average', histPct));
  kvSection.appendChild(_kvRow('DENY count (recent)', _fmtNum(dr.deny_count ?? 0), 'amber'));
  kvSection.appendChild(_kvRow('ALLOW count (recent)', _fmtNum(dr.allow_count ?? 0), 'green'));
  kvSection.appendChild(_kvRow('Total decisions (recent)', _fmtNum(dr.total ?? 0)));
  kvSection.appendChild(_kvRow('Anomaly detected', dr.anomaly ? 'Yes' : 'No', dr.anomaly ? 'amber' : 'green'));
  content.appendChild(kvSection);

  // Fetch recent DENYs for context
  const res = await api.getActivity({ policy_decision: 'DENY', limit: 10 });
  if (res.ok && res.data?.entries?.length) {
    const denySection = document.createElement('div');
    denySection.className = 'hw-gc-section';
    const denyHeader = document.createElement('div');
    denyHeader.className = 'hw-gc-sub-header';
    denyHeader.textContent = 'Recent denied operations';
    denySection.appendChild(denyHeader);

    const table = document.createElement('table');
    table.className = 'hw-deny-table';
    table.innerHTML = `<thead><tr>
      <th>Time</th><th>Action</th><th>Target</th>
    </tr></thead>`;
    const tbody = document.createElement('tbody');

    for (const entry of res.data.entries.slice(0, 10)) {
      const detail = entry.detail || {};
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${_esc(_formatHumanDate(entry.timestamp_utc))}</td>
        <td>${_esc(detail.tool_name || 'Unknown')}</td>
        <td class="hw-deny-target">${_esc(_truncTarget(detail.target || 'N/A'))}</td>
      `;
      // Click to open record detail
      const evidence = entry.evidence || {};
      const recordId = evidence.request_id || evidence.event_id || evidence.record_hash;
      if (recordId) {
        tr.className = 'hw-deny-row-click';
        tr.addEventListener('click', () => openRecordDetail(recordId, state.el));
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    denySection.appendChild(table);
    content.appendChild(denySection);
  }

  modalManager.open({ title: 'Deny Rate', subtitle: 'Recent deny patterns and context', trigger: state.el, content });
}

// ---------- Recent health events table ----------

function _renderEventsTable(state, h) {
  const events = h.recent_stability_events || [];
  if (!events.length) return;

  const pane = document.createElement('div');
  pane.className = 'hw-events-pane';
  setTooltip(pane, _paneTooltip('Recent health events'));
  pane.innerHTML = `
    <div class="hw-pane-accent hw-accent-blue"></div>
    <div class="hw-pane-header-row">
      <span class="hw-pane-header">Recent health events</span>
      <span class="hw-pane-count">${events.length > 10 ? '10 of ' + events.length : events.length} events</span>
    </div>
  `;
  setTooltip(pane.querySelector('.hw-pane-header'), _paneTooltip('Recent health events'));

  const table = document.createElement('table');
  table.className = 'hw-events-table';
  table.innerHTML = `<thead><tr>
    <th style="width:100px">Time</th>
    <th style="width:160px">Event</th>
    <th style="width:80px">Severity</th>
    <th style="width:90px">Source</th>
    <th>Details</th>
  </tr></thead>`;

  const tbody = document.createElement('tbody');
  for (const evt of events.slice(0, 10)) {
    const severity = _eventSeverity(evt);
    const source = _eventSource(evt);
    const details = _eventDetails(evt);
    const tr = document.createElement('tr');
    tr.className = `hw-evt-row hw-evt-${severity}`;
    tr.innerHTML = `
      <td class="hw-evt-time">${_esc(_formatHumanDate(evt.timestamp))}</td>
      <td>${_esc(evt.event_type || 'Unknown')}</td>
      <td><span class="hw-sev-badge hw-sev-${severity}">${_esc(_capitalize(severity))}</span></td>
      <td>${_esc(source)}</td>
      <td class="hw-evt-detail">${_esc(details)}</td>
    `;
    setTooltip(tr, `${evt.event_type || 'Health event'} from ${source}: ${details || 'open for detail'}`);

    // Stability-log events are not governance chain records; show their native detail.
    tr.addEventListener('click', () => _openRawEventDetail(state, evt));

    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  pane.appendChild(table);

  // View all in Audit link
  if (events.length > 10) {
    const viewAll = document.createElement('div');
    viewAll.className = 'hw-view-all';
    const link = document.createElement('button');
    link.className = 'hw-view-all-btn';
    link.textContent = 'View all in Audit';
    link.addEventListener('click', () => {
      modalManager.closeAll();
      setTimeout(() => {
        import('./audit.js').then(mod => mod.openAuditWindow(null));
      }, 0);
    });
    viewAll.appendChild(link);
    pane.appendChild(viewAll);
  }

  state.el.appendChild(pane);
}

function _openRawEventDetail(state, evt) {
  const content = document.createElement('div');
  content.className = 'hw-gc';

  const accent = document.createElement('div');
  accent.className = 'hw-gc-accent hw-accent-muted';
  content.appendChild(accent);

  const header = document.createElement('div');
  header.className = 'hw-gc-header';
  header.textContent = 'Health event detail';
  content.appendChild(header);

  const section = document.createElement('div');
  section.className = 'hw-gc-section';
  section.appendChild(_kvRow('Event type', evt.event_type || 'Unknown'));
  section.appendChild(_kvRow('Time', _formatHumanDate(evt.timestamp)));
  section.appendChild(_kvRow('Severity', _capitalize(_eventSeverity(evt))));
  section.appendChild(_kvRow('Source', _eventSource(evt)));

  if (evt.payload && typeof evt.payload === 'object') {
    for (const [k, v] of Object.entries(evt.payload)) {
      section.appendChild(_kvRow(k, typeof v === 'object' ? JSON.stringify(v) : String(v ?? 'N/A')));
    }
  }
  content.appendChild(section);

  modalManager.open({ title: 'Health Event', subtitle: 'Event detail from chain stability log', trigger: state.el, content });
}

// ---------- Event classification helpers ----------

function _eventSeverity(evt) {
  const type = (evt.event_type || '').toLowerCase();
  if (type.includes('break') || type.includes('critical') || type.includes('tamper')) return 'critical';
  if (type.includes('warn') || type.includes('attention') || type.includes('anomal') || type.includes('gap')) return 'warning';
  return 'info';
}

function _eventSource(evt) {
  const type = (evt.event_type || '').toLowerCase();
  if (type.includes('chain') || type.includes('integrity') || type.includes('hash')) return 'verifier';
  if (type.includes('sign')) return 'signing';
  if (type.includes('deny') || type.includes('policy')) return 'proxy';
  return 'system';
}

function _eventDetails(evt) {
  if (!evt.payload) return '';
  if (typeof evt.payload === 'string') return evt.payload;
  if (typeof evt.payload === 'object') {
    // Try to extract a meaningful summary
    const p = evt.payload;
    if (p.message) return p.message;
    if (p.reason) return p.reason;
    if (p.description) return p.description;
    // Compact JSON
    const json = JSON.stringify(p);
    return json.length > 120 ? json.substring(0, 117) + '\u2026' : json;
  }
  return String(evt.payload);
}

// ---------- Utility ----------

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, subtitle, trigger, content });
  return modalManager.open({ title, subtitle, trigger, content });
}

function _statusColor(status) {
  if (status === 'critical') return 'red';
  if (status === 'attention') return 'amber';
  if (status === 'healthy_auto_repaired' || status === 'repaired') return 'green';
  return 'green';
}

function _statusLabel(status) {
  const map = {
    healthy: 'Healthy',
    critical: 'Critical',
    attention: 'Attention',
    healthy_auto_repaired: 'Healthy (repaired)',
    repaired: 'Healthy (repaired)',
  };
  return map[status] || _capitalize(status);
}

function _formatBytes(bytes) {
  if (bytes == null) return 'N/A';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function _formatHumanDate(isoStr) {
  if (!isoStr) return 'N/A';
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    // Same day: just time. Different day: "Apr 18, 23:20"
    if (d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()) {
      return `${hh}:${mm}:${ss}`;
    }
    return `${months[d.getMonth()]} ${d.getDate()}, ${hh}:${mm}:${ss}`;
  } catch { return isoStr; }
}

function _fmtNum(n) {
  return typeof n === 'number' ? n.toLocaleString() : String(n);
}

function _truncHash(hash) {
  if (!hash) return 'N/A';
  return hash.length > 16 ? hash.substring(0, 8) + '\u2026' + hash.substring(hash.length - 8) : hash;
}

function _chainFileStatusLabel(status) {
  const map = {
    intact: 'Intact',
    missing: 'Missing',
    truncated: 'Truncated',
    changed: 'Changed',
    not_available: 'Not available',
  };
  return map[status] || 'Not available';
}

function _verificationLabel(status) {
  const value = status?.status || 'not_run';
  const map = {
    ok: 'Verified',
    broken: 'Break detected',
    error: 'Error',
    not_run: 'Not run',
    not_available: 'Not available',
  };
  return status?.running ? 'Running' : (map[value] || _capitalize(value));
}

function _verificationColor(status) {
  const value = status?.status || 'not_run';
  if (value === 'ok') return 'green';
  if (value === 'broken' || value === 'error') return 'red';
  return 'amber';
}

function _truncTarget(target) {
  if (!target || target.length <= 40) return target;
  return '\u2026' + target.substring(target.length - 37);
}

function _capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1);
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// ---------- Styles ----------

const hwStyles = document.createElement('style');
hwStyles.textContent = `
  .hw-root {
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
    overflow: visible;
  }

  /* ---- Title accent ---- */
  .hw-title-accent {
    height: 6px;
    border-radius: 2px 2px 0 0;
    margin: -24px -24px 0;
  }
  .hw-accent-green { background: #3fb950; }
  .hw-accent-blue { background: #6699cc; }
  .hw-accent-purple { background: #d2a8ff; }
  .hw-accent-dark-blue { background: #2b4a7a; }
  .hw-accent-amber { background: #d29922; }
  .hw-accent-red { background: #f85149; }
  .hw-accent-muted { background: #6b7280; }

  /* ---- Status pill ---- */
  .hw-status-row {
    padding: 14px 0 16px;
  }
  .hw-status-pill {
    display: inline-block;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 3px 14px;
    border-radius: 2px;
  }
  .hw-pill-green { color: #3fb950; }
  .hw-pill-amber { color: #d29922; }
  .hw-pill-red { color: #f85149; }

  /* ---- Alert pane ---- */
  .hw-alert-pane {
    border-radius: 2px;
    padding: 16px 20px;
    margin-bottom: 16px;
  }
  .hw-alert-red {
    background: rgba(248,81,73,0.06);
    border: 1px dashed rgba(248,81,73,0.25);
  }
  .hw-alert-amber {
    background: rgba(210,153,34,0.06);
    border: 1px dashed rgba(210,153,34,0.25);
  }
  .hw-alert-blue {
    background: rgba(102,153,204,0.06);
    border: 1px dashed rgba(102,153,204,0.25);
  }
  .hw-alert-top {
    margin-bottom: 8px;
  }
  .hw-alert-badge {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 2px 10px;
    border-radius: 2px;
  }
  .hw-badge-red { color: #f85149; }
  .hw-badge-amber { color: #d29922; }
  .hw-alert-desc {
    font-size: 0.85rem;
    color: #e4e6eb;
    margin: 0 0 4px;
    line-height: 1.5;
  }
  .hw-alert-guidance {
    font-size: 0.82rem;
    color: #8b919a;
    margin: 0 0 10px;
    line-height: 1.5;
  }
  .hw-alert-ack {
    background: none;
    border: 1px solid rgba(248,81,73,0.4);
    border-radius: 2px;
    color: #f85149;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 5px 14px;
    cursor: pointer;
    transition: all 0.12s;
  }
  .hw-alert-ack:hover {
    background: rgba(248,81,73,0.08);
    border-color: rgba(248,81,73,0.6);
  }
  .hw-jump-btn {
    background: rgba(210,168,255,0.10);
    border: 1px dashed rgba(210,168,255,0.38);
    border-radius: 2px;
    color: #d2a8ff;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    font-weight: 700;
    margin-top: 10px;
    padding: 7px 12px;
  }
  .hw-jump-btn:hover:not(:disabled) {
    background: rgba(210,168,255,0.16);
  }
  .hw-jump-btn:disabled {
    cursor: default;
    opacity: 0.45;
  }

  /* ---- Pane grid ---- */
  .hw-pane-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
    overflow: visible;
  }

  /* ---- Data pane ---- */
  .hw-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: visible;
  }
  .hw-pane-clickable {
    cursor: pointer;
    transition: border-color 0.12s;
  }
  .hw-pane-clickable:hover {
    border-color: rgba(102,153,204,0.3);
  }
  .hw-pane-accent {
    height: 6px;
  }
  .hw-pane-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
    padding: 12px 20px 4px;
  }
  .hw-pane-body {
    padding: 6px 20px 16px;
    overflow: visible;
  }

  /* ---- KV rows ---- */
  .hw-kv-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 4px 0;
  }
  .hw-kv-label {
    font-size: 0.78rem;
    color: #8b919a;
  }
  .hw-kv-value {
    font-size: 0.82rem;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .hw-kv-green { color: #3fb950; }
  .hw-kv-amber { color: #d29922; }
  .hw-kv-red { color: #f85149; }

  /* ---- Events pane ---- */
  .hw-events-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: visible;
    margin-bottom: 16px;
  }
  .hw-pane-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px 8px;
  }
  .hw-pane-header-row .hw-pane-header {
    padding: 0;
  }
  .hw-pane-count {
    font-size: 0.72rem;
    color: #8b919a;
  }

  /* Events table */
  .hw-events-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .hw-events-table thead th {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    font-weight: 600;
    text-align: left;
    padding: 4px 10px 6px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    white-space: nowrap;
  }
  .hw-events-table tbody td {
    padding: 7px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
  }
  .hw-evt-row {
    cursor: pointer;
    transition: background 0.1s;
  }
  .hw-evt-row:hover {
    background: rgba(102,153,204,0.06);
  }
  .hw-evt-critical {
    background: rgba(248,81,73,0.04);
  }
  .hw-evt-critical:hover {
    background: rgba(248,81,73,0.10);
  }
  .hw-evt-warning {
    background: rgba(210,153,34,0.04);
  }
  .hw-evt-warning:hover {
    background: rgba(210,153,34,0.08);
  }
  .hw-evt-time {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .hw-evt-detail {
    color: #8b919a;
  }

  /* Severity badges */
  .hw-sev-badge {
    display: inline-block;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 1px 8px;
    border-radius: 2px;
  }
  .hw-sev-critical { color: #f85149; }
  .hw-sev-warning { color: #d29922; }
  .hw-sev-info { color: #8b919a; }

  /* View all link */
  .hw-view-all {
    padding: 10px 20px 14px;
    text-align: center;
  }
  .hw-view-all-btn {
    background: none;
    border: none;
    color: #6699cc;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    text-decoration: underline;
    padding: 0;
  }
  .hw-view-all-btn:hover { color: #88aadd; }

  /* ---- Grandchild styles ---- */
  .hw-gc {
    font-family: "Inter", system-ui, sans-serif;
  }
  .hw-gc-accent {
    height: 6px;
    margin: -24px -24px 0;
    border-radius: 2px 2px 0 0;
  }
  .hw-gc-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
    padding: 14px 0 10px;
  }
  .hw-gc-sub-header {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    font-weight: 600;
    padding: 8px 0 6px;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin-top: 6px;
  }
  .hw-gc-section {
    margin-bottom: 10px;
  }

  /* Deny detail table in grandchild */
  .hw-deny-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
    margin-top: 6px;
  }
  .hw-deny-table thead th {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    font-weight: 600;
    text-align: left;
    padding: 4px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .hw-deny-table tbody td {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .hw-deny-row-click {
    cursor: pointer;
    transition: background 0.1s;
  }
  .hw-deny-row-click:hover {
    background: rgba(102,153,204,0.06);
  }
  .hw-deny-target {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
    max-width: 180px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* ---- Utility ---- */
  .hw-loading {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
  }
  .hw-error {
    color: #d29922;
    padding: 12px 16px;
    border-radius: 2px;
    font-size: 0.82rem;
  }

  /* ---- Responsive ---- */
  @media (max-width: 600px) {
    .hw-pane-grid { grid-template-columns: 1fr; }
    .hw-events-table thead th:nth-child(4),
    .hw-events-table tbody td:nth-child(4) { display: none; }
    .hw-deny-table thead th:nth-child(3),
    .hw-deny-table tbody td:nth-child(3) { display: none; }
  }
`;
document.head.appendChild(hwStyles);
