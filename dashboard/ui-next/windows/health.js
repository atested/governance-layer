/**
 * Health window — child window (depth 1).
 * Spec v2 section 7.5.
 *
 * Infrastructure status: overall health, alerts, chain integrity,
 * deny rate, transparency, storage, users, license, recent events.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import '../components/status-card.js';
import '../components/status-grid.js';
import '../components/pill.js';
import '../components/loading-indicator.js';

/**
 * Open the Health window.
 * @param {HTMLElement|null} trigger
 */
export function openHealthWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Health', trigger, content);
  if (!result) return;
  _loadData(content);
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'hw-content';
  el.innerHTML = `
    <div class="hw-header">
      <span class="hw-eyebrow">Infrastructure</span>
      <span class="hw-heading">System Health</span>
      <span class="hw-overall" id="hw-overall">--</span>
    </div>
    <div id="hw-alerts"></div>
    <div id="hw-sections">
      <atd-loading-indicator label="Loading health data"></atd-loading-indicator>
    </div>
  `;
  return el;
}

async function _loadData(el) {
  const res = await api.getHealth();
  const sections = el.querySelector('#hw-sections');

  if (!res.ok) {
    sections.innerHTML = `<div class="hw-error">${_esc(res.error)}</div>`;
    return;
  }

  const h = res.data;

  // Overall status
  const overall = el.querySelector('#hw-overall');
  const status = h.overall_status || 'unknown';
  overall.textContent = status.toUpperCase();
  overall.className = `hw-overall hw-status-${status}`;

  // Alerts
  _renderAlerts(el.querySelector('#hw-alerts'), h.alerts || [], el);

  // Build all sections
  sections.innerHTML = '';

  // Chain integrity
  sections.appendChild(_buildSection('Chain Integrity', [
    { label: 'Status', value: h.chain?.status?.toUpperCase() || '--', variant: h.chain?.status === 'ok' ? 'success' : h.chain?.status === 'broken' ? 'danger' : 'warning' },
    { label: 'Event Count', value: String(h.chain?.chain_event_count ?? '--') },
    { label: 'Verified', value: h.chain?.checked ? 'Yes' : 'No' },
  ]));

  // Deny rate
  sections.appendChild(_buildSection('DENY Rate', [
    { label: 'Recent DENY Rate', value: h.deny_rate?.recent_deny_rate != null ? `${(h.deny_rate.recent_deny_rate * 100).toFixed(1)}%` : '--', variant: h.deny_rate?.anomaly ? 'danger' : undefined },
    { label: 'Historical Average', value: h.deny_rate?.historical_average != null ? `${(h.deny_rate.historical_average * 100).toFixed(1)}%` : '--' },
    { label: 'Anomaly', value: h.deny_rate?.anomaly ? 'DETECTED' : 'None', variant: h.deny_rate?.anomaly ? 'danger' : 'success' },
  ]));

  // Transparency
  sections.appendChild(_buildSection('Transparency', [
    { label: 'Hook Data', value: h.observations?.gap_detected === false ? 'Active' : h.observations?.gap_detected ? 'Gap Detected' : '--', variant: h.observations?.gap_detected ? 'warning' : 'success' },
    { label: 'Hours Since Last', value: h.observations?.hours_since_last != null ? String(Math.round(h.observations.hours_since_last)) : '--' },
    { label: 'Ungoverned Ops', value: String(h.observations?.ungoverned_operation_count ?? '--'), variant: (h.observations?.ungoverned_operation_count || 0) > 0 ? 'warning' : undefined },
  ]));

  // Storage
  sections.appendChild(_buildSection('Storage', [
    { label: 'Chain Size', value: _formatBytes(h.storage?.chain_size_bytes) },
    { label: 'Stability Log', value: _formatBytes(h.storage?.stability_log_size_bytes) },
    { label: 'Archive Size', value: _formatBytes(h.storage?.archive_size_bytes) },
    { label: 'Archive Count', value: String(h.storage?.archive_count ?? '--') },
  ]));

  // Users
  sections.appendChild(_buildSection('Users', [
    { label: 'Unique Users', value: String(h.users?.unique_users ?? '--') },
    { label: 'Anomalies', value: h.users?.anomalies?.length ? String(h.users.anomalies.length) : 'None', variant: h.users?.anomalies?.length ? 'warning' : 'success' },
  ]));

  // License
  sections.appendChild(_buildSection('License', [
    { label: 'Status', value: h.license?.status?.toUpperCase() || '--' },
  ]));

  // Recent stability events
  if (h.recent_stability_events?.length) {
    const evtSection = document.createElement('div');
    evtSection.className = 'hw-section';
    evtSection.innerHTML = '<h3 class="hw-section-title">Recent Health Events</h3>';
    const list = document.createElement('div');
    list.className = 'hw-event-list';
    for (const evt of h.recent_stability_events.slice(0, 10)) {
      const row = document.createElement('div');
      row.className = 'hw-event-row';
      row.innerHTML = `
        <span class="hw-event-time">${_esc(_formatTime(evt.timestamp))}</span>
        <span class="hw-event-type">${_esc(evt.event_type || '--')}</span>
        <span class="hw-event-detail">${_esc(typeof evt.payload === 'object' ? JSON.stringify(evt.payload) : String(evt.payload || '--'))}</span>
      `;
      list.appendChild(row);
    }
    evtSection.appendChild(list);
    sections.appendChild(evtSection);
  }
}

function _renderAlerts(container, alerts, rootEl) {
  container.innerHTML = '';
  if (!alerts.length) return;

  for (const alert of alerts) {
    const card = document.createElement('div');
    card.className = `hw-alert hw-alert-${alert.severity || 'info'}`;
    card.innerHTML = `
      <div class="hw-alert-header">
        <span class="hw-alert-severity">${_esc((alert.severity || 'info').toUpperCase())}</span>
        <span class="hw-alert-source">${_esc(alert.source || '')}</span>
      </div>
      <p class="hw-alert-message">${_esc(alert.message || '')}</p>
      ${alert.guidance ? `<p class="hw-alert-guidance">${_esc(alert.guidance)}</p>` : ''}
    `;
    const ackBtn = document.createElement('atd-pill');
    ackBtn.setAttribute('variant', 'outline');
    ackBtn.textContent = 'Acknowledge';
    ackBtn.addEventListener('click', async () => {
      const res = await api.postHealthAcknowledge({ source: alert.source, message: alert.message });
      if (res.ok) _loadData(rootEl);
    });
    card.appendChild(ackBtn);
    container.appendChild(card);
  }
}

function _buildSection(title, cards) {
  const section = document.createElement('div');
  section.className = 'hw-section';
  section.innerHTML = `<h3 class="hw-section-title">${_esc(title)}</h3>`;
  const grid = document.createElement('atd-status-grid');
  for (const c of cards) {
    const card = document.createElement('atd-status-card');
    card.setAttribute('label', c.label);
    card.setAttribute('value', c.value);
    if (c.variant) card.setAttribute('variant', c.variant);
    grid.appendChild(card);
  }
  section.appendChild(grid);
  return section;
}

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, trigger, content });
  return modalManager.open({ title, trigger, content });
}

function _formatBytes(bytes) {
  if (bytes == null) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function _formatTime(iso) {
  if (!iso) return '--';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// Styles
const hwStyles = document.createElement('style');
hwStyles.textContent = `
  .hw-content { font-family: "Inter", system-ui, sans-serif; }
  .hw-header { margin-bottom: 16px; }
  .hw-eyebrow {
    display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #8b919a; margin-bottom: 4px;
  }
  .hw-heading { font-size: 1.25rem; font-weight: 600; color: #e4e6eb; margin-right: 12px; }
  .hw-overall {
    display: inline-block; font-size: 0.82rem; font-weight: 600;
    padding: 2px 10px; border-radius: 999px;
  }
  .hw-status-healthy { background: rgba(74,222,128,0.10); color: #4ade80; }
  .hw-status-attention { background: rgba(245,158,66,0.10); color: #f59e42; }
  .hw-status-critical { background: rgba(239,68,68,0.10); color: #ef4444; }
  .hw-status-repaired { background: rgba(91,138,245,0.12); color: #5b8af5; }
  .hw-alert {
    border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;
    padding: 14px 18px; margin-bottom: 12px;
  }
  .hw-alert-critical { border-left: 3px solid #ef4444; background: rgba(239,68,68,0.06); }
  .hw-alert-attention { border-left: 3px solid #f59e42; background: rgba(245,158,66,0.06); }
  .hw-alert-info { border-left: 3px solid #5b8af5; background: rgba(91,138,245,0.06); }
  .hw-alert-header { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
  .hw-alert-severity { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; }
  .hw-alert-source { font-size: 0.72rem; color: #8b919a; }
  .hw-alert-message { font-size: 0.82rem; color: #e4e6eb; margin: 0 0 4px; }
  .hw-alert-guidance { font-size: 0.82rem; color: #8b919a; margin: 0 0 8px; font-style: italic; }
  .hw-section { margin-bottom: 20px; }
  .hw-section-title {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #5b8af5; margin: 0 0 10px; font-weight: 600;
  }
  .hw-loading { color: #8b919a; font-size: 0.82rem; text-align: center; padding: 40px 0; margin: 0; }
  .hw-error {
    color: #f59e42; background: rgba(245,158,66,0.10);
    padding: 12px 16px; border-radius: 8px; font-size: 0.82rem;
  }
  .hw-event-list { background: #22262e; border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; }
  .hw-event-row {
    display: flex; gap: 12px; padding: 8px 16px; font-size: 0.82rem;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .hw-event-row:last-child { border-bottom: none; }
  .hw-event-time { flex: 0 0 140px; font-family: "JetBrains Mono", monospace; font-size: 0.72rem; color: #8b919a; }
  .hw-event-type { flex: 0 0 160px; color: #e4e6eb; }
  .hw-event-detail { flex: 1; color: #8b919a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  @media (max-width: 600px) {
    .hw-event-row { flex-wrap: wrap; }
    .hw-event-time { flex: 0 0 auto; }
    .hw-event-type { flex: 0 0 auto; }
    .hw-event-detail { flex: 1 1 100%; white-space: normal; }
  }
`;
document.head.appendChild(hwStyles);
