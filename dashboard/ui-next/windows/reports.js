/**
 * Reports window — child window (depth 1).
 * Spec v2 section 7.4.
 *
 * Aggregate views of governance activity with grouped bar charts.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import '../components/status-card.js';
import '../components/status-grid.js';
import '../components/pill.js';
import '../components/loading-indicator.js';

/**
 * Open the Reports window.
 * @param {HTMLElement|null} trigger
 */
export function openReportsWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Reports', trigger, content);
  if (!result) return;

  const state = { el: content };
  _wireControls(state);
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'rp-content';
  el.innerHTML = `
    <div class="rp-header">
      <span class="rp-eyebrow">Analytics</span>
      <span class="rp-heading">Reports</span>
    </div>
    <div class="rp-form">
      <label class="rp-field">
        Start Time
        <input type="datetime-local" class="rp-input" id="rp-start">
      </label>
      <label class="rp-field">
        End Time
        <input type="datetime-local" class="rp-input" id="rp-end">
      </label>
      <label class="rp-field">
        Group By
        <select class="rp-input" id="rp-group">
          <option value="tool">Tool</option>
          <option value="user">User</option>
          <option value="decision">Decision</option>
          <option value="category">Category</option>
        </select>
      </label>
      <div class="rp-field rp-field-btn">
        <atd-pill variant="primary" id="rp-generate">Generate</atd-pill>
      </div>
    </div>
    <div id="rp-results"></div>
  `;
  return el;
}

function _wireControls(state) {
  state.el.querySelector('#rp-generate').addEventListener('click', () => _loadReport(state));
  // Auto-generate on open with defaults
  _loadReport(state);
}

async function _loadReport(state) {
  const el = state.el;
  const results = el.querySelector('#rp-results');
  results.innerHTML = '<atd-loading-indicator label="Generating report"></atd-loading-indicator>';

  const params = {};
  const start = el.querySelector('#rp-start').value;
  const end = el.querySelector('#rp-end').value;
  const groupBy = el.querySelector('#rp-group').value;

  if (start) params.start_time = new Date(start).toISOString();
  if (end) params.end_time = new Date(end).toISOString();
  params.group_by = groupBy;

  const res = await api.getAuditReport(params);
  if (!res.ok) {
    results.innerHTML = `<div class="rp-error">${_esc(res.error)}</div>`;
    return;
  }

  results.innerHTML = '';

  // Decision summary cards
  const summary = res.data.decision_summary || {};
  const summarySection = document.createElement('div');
  summarySection.className = 'rp-section';
  summarySection.innerHTML = '<h3 class="rp-section-title">Decision Summary</h3>';
  const grid = document.createElement('atd-status-grid');

  const totalCard = document.createElement('atd-status-card');
  totalCard.setAttribute('label', 'Total Records');
  totalCard.setAttribute('value', String(res.data.total_records ?? 0));
  grid.appendChild(totalCard);

  const allowCard = document.createElement('atd-status-card');
  allowCard.setAttribute('label', 'ALLOW');
  allowCard.setAttribute('value', String(summary.ALLOW ?? 0));
  allowCard.setAttribute('variant', 'success');
  grid.appendChild(allowCard);

  const denyCard = document.createElement('atd-status-card');
  denyCard.setAttribute('label', 'DENY');
  denyCard.setAttribute('value', String(summary.DENY ?? 0));
  if ((summary.DENY ?? 0) > 0) denyCard.setAttribute('variant', 'danger');
  grid.appendChild(denyCard);

  summarySection.appendChild(grid);
  results.appendChild(summarySection);

  // Grouped results as bar chart
  const groups = res.data.groups || [];
  if (groups.length) {
    const groupSection = document.createElement('div');
    groupSection.className = 'rp-section';
    groupSection.innerHTML = `<h3 class="rp-section-title">By ${_esc(groupBy)}</h3>`;

    const maxCount = Math.max(...groups.map(g => g.count || 0), 1);
    const barList = document.createElement('div');
    barList.className = 'rp-bars';

    for (const group of groups) {
      const pct = ((group.count || 0) / maxCount * 100).toFixed(1);
      const bar = document.createElement('div');
      bar.className = 'rp-bar-row';
      bar.innerHTML = `
        <span class="rp-bar-label">${_esc(group.key || '--')}</span>
        <div class="rp-bar-track">
          <div class="rp-bar-fill" style="width: ${pct}%"></div>
        </div>
        <span class="rp-bar-count">${group.count || 0}</span>
      `;
      barList.appendChild(bar);
    }

    groupSection.appendChild(barList);
    results.appendChild(groupSection);
  }
}

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, trigger, content });
  return modalManager.open({ title, trigger, content });
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// Styles
const rpStyles = document.createElement('style');
rpStyles.textContent = `
  .rp-content { font-family: "Inter", system-ui, sans-serif; }
  .rp-header { margin-bottom: 16px; }
  .rp-eyebrow {
    display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #8b919a; margin-bottom: 4px;
  }
  .rp-heading { font-size: 1.25rem; font-weight: 600; color: #e4e6eb; }
  .rp-form {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 12px; margin-bottom: 20px;
  }
  .rp-field {
    display: flex; flex-direction: column; font-size: 0.72rem; color: #8b919a;
    text-transform: uppercase; letter-spacing: 0.04em; gap: 4px;
  }
  .rp-field-btn { justify-content: flex-end; }
  .rp-input {
    background: #1a1d23; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px; color: #e4e6eb; font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem; padding: 6px 10px;
  }
  .rp-input:focus { outline: 2px solid #5b8af5; outline-offset: 1px; }
  .rp-section { margin-bottom: 24px; }
  .rp-section-title {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #5b8af5; margin: 0 0 10px; font-weight: 600;
  }
  .rp-bars {
    background: #22262e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 8px 0;
  }
  .rp-bar-row {
    display: flex; align-items: center; gap: 12px; padding: 6px 16px;
  }
  .rp-bar-label { flex: 0 0 140px; font-size: 0.82rem; color: #e4e6eb; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .rp-bar-track { flex: 1; height: 16px; background: rgba(255,255,255,0.04); border-radius: 8px; overflow: hidden; }
  .rp-bar-fill { height: 100%; background: #5b8af5; border-radius: 8px; transition: width 0.3s; }
  .rp-bar-count { flex: 0 0 50px; text-align: right; font-family: "JetBrains Mono", monospace; font-size: 0.82rem; color: #8b919a; }
  .rp-loading { color: #8b919a; font-size: 0.82rem; text-align: center; padding: 40px 0; margin: 0; }
  .rp-error {
    color: #f59e42; background: rgba(245,158,66,0.10);
    padding: 12px 16px; border-radius: 8px; font-size: 0.82rem;
  }
  @media (max-width: 600px) {
    .rp-form { grid-template-columns: 1fr; }
    .rp-bar-label { flex: 0 0 80px; font-size: 0.72rem; }
  }
`;
document.head.appendChild(rpStyles);
