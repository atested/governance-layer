/**
 * Audit window — child window (depth 1).
 * Spec v2 section 7.3.
 *
 * Query and search the governance chain with 6-filter form,
 * results table, Record Detail drill-down, and JSON export.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { openRecordDetail } from './record-detail.js';
import '../components/data-table.js';
import '../components/decision-tag.js';
import '../components/pill.js';
import '../components/loading-indicator.js';

const PAGE_SIZE = 50;

const COLUMNS = [
  { key: 'sequence', label: '#', sortable: true, width: '60px' },
  { key: 'timestamp_utc', label: 'Time', sortable: true, width: '160px' },
  { key: 'event_type', label: 'Event Type', sortable: true },
  { key: 'summary', label: 'Summary', sortable: false },
  { key: 'user_identity', label: 'User', sortable: true, width: '100px' },
];

/**
 * Open the Audit window.
 * @param {HTMLElement|null} trigger
 */
export function openAuditWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Audit', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    currentPage: 1,
    totalCount: 0,
    data: [],
    hasQueried: false,
  };

  _wireControls(state);
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'au-content';
  el.innerHTML = `
    <div class="au-header">
      <span class="au-eyebrow">Governance Chain</span>
      <span class="au-heading">Audit Query</span>
    </div>
    <div class="au-form">
      <label class="au-field">
        Start Time
        <input type="datetime-local" class="au-input" id="au-start">
      </label>
      <label class="au-field">
        End Time
        <input type="datetime-local" class="au-input" id="au-end">
      </label>
      <label class="au-field">
        User Identity
        <input type="text" class="au-input" id="au-user" placeholder="e.g. cecil">
      </label>
      <label class="au-field">
        Tool Name
        <input type="text" class="au-input" id="au-tool" placeholder="e.g. FS_WRITE">
      </label>
      <label class="au-field">
        Decision
        <select class="au-input" id="au-decision">
          <option value="">All</option>
          <option value="ALLOW">ALLOW</option>
          <option value="DENY">DENY</option>
        </select>
      </label>
      <label class="au-field">
        Category
        <select class="au-input" id="au-category">
          <option value="">All</option>
          <option value="mediated_decision">Mediated Decision</option>
          <option value="verification_change">Verification Change</option>
          <option value="operation_approval">Operation Approval</option>
          <option value="operation_revocation">Operation Revocation</option>
          <option value="invocation_decision">Invocation Decision</option>
          <option value="boundary_observation">Boundary Observation</option>
        </select>
      </label>
    </div>
    <div class="au-actions">
      <atd-pill variant="primary" id="au-search">Search</atd-pill>
      <atd-pill variant="outline" id="au-export">Export JSON</atd-pill>
    </div>
    <div id="au-results"></div>
  `;
  return el;
}

function _wireControls(state) {
  const el = state.el;

  el.querySelector('#au-search').addEventListener('click', () => {
    state.currentPage = 1;
    state.hasQueried = true;
    _loadData(state);
  });

  el.querySelector('#au-export').addEventListener('click', () => _exportJSON(state));
}

function _getFilters(el) {
  const params = {};
  const start = el.querySelector('#au-start').value;
  const end = el.querySelector('#au-end').value;
  const user = el.querySelector('#au-user').value.trim();
  const tool = el.querySelector('#au-tool').value.trim();
  const decision = el.querySelector('#au-decision').value;
  const category = el.querySelector('#au-category').value;

  if (start) params.start_time = new Date(start).toISOString();
  if (end) params.end_time = new Date(end).toISOString();
  if (user) params.user_identity = user;
  if (tool) params.tool_name = tool;
  if (decision) params.policy_decision = decision;
  if (category) params.event_category = category;

  return params;
}

async function _loadData(state) {
  const resultsEl = state.el.querySelector('#au-results');
  resultsEl.innerHTML = '<atd-loading-indicator label="Searching"></atd-loading-indicator>';

  const params = {
    ..._getFilters(state.el),
    limit: PAGE_SIZE,
    offset: (state.currentPage - 1) * PAGE_SIZE,
  };

  const res = await api.getAuditQuery(params);
  if (!res.ok) {
    resultsEl.innerHTML = `<div class="au-error">${_esc(res.error)}</div>`;
    return;
  }

  state.data = res.data.entries || [];
  state.totalCount = res.data.total_matching || state.data.length;

  _renderResults(state);
}

function _renderResults(state) {
  const resultsEl = state.el.querySelector('#au-results');
  resultsEl.innerHTML = '';

  if (!state.hasQueried) return;

  if (!state.data.length) {
    resultsEl.innerHTML = '<p class="au-empty">No matching records</p>';
    return;
  }

  const countLabel = document.createElement('p');
  countLabel.className = 'au-count';
  countLabel.textContent = `${state.totalCount} matching record${state.totalCount !== 1 ? 's' : ''}`;
  resultsEl.appendChild(countLabel);

  const table = document.createElement('atd-data-table');
  table.setAttribute('columns', JSON.stringify(COLUMNS));
  table.setAttribute('page-size', String(PAGE_SIZE));

  const rows = state.data.map(entry => ({
    ...entry,
    sequence: entry.sequence_position || entry.request_id?.substring(0, 8) || '--',
    summary: _buildSummary(entry),
  }));

  table.data = rows;
  table.totalCount = state.totalCount;
  table.currentPage = state.currentPage;

  table.cellRenderer = (row, col) => {
    if (col.key === 'timestamp_utc') return _esc(_formatTime(row.timestamp_utc));
    return null;
  };

  table.addEventListener('table:page', (e) => {
    state.currentPage = e.detail.page;
    _loadData(state);
  });

  table.addEventListener('table:row-click', (e) => {
    const row = e.detail.row;
    const id = row.request_id || row.event_id || '';
    if (id) openRecordDetail(id, table);
  });

  resultsEl.appendChild(table);
}

async function _exportJSON(state) {
  const params = {
    ..._getFilters(state.el),
    limit: 10000,
    offset: 0,
  };

  const res = await api.getAuditQuery(params);
  if (!res.ok) {
    alert('Export failed: ' + res.error);
    return;
  }

  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10);
  const envelope = {
    export_timestamp: now.toISOString(),
    query_parameters: params,
    total_records: res.data.total_matching || 0,
    records: res.data.entries || [],
  };

  const blob = new Blob([JSON.stringify(envelope, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `atested-audit-export-${dateStr}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function _buildSummary(entry) {
  const tool = entry.tool || '';
  const target = entry.target || '';
  if (tool && target) return `${tool}: ${target}`;
  if (tool) return tool;
  return entry.event_type || '--';
}

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) {
    return modalManager.replaceChild({ title, trigger, content });
  }
  return modalManager.open({ title, trigger, content });
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
const auStyles = document.createElement('style');
auStyles.textContent = `
  .au-content { font-family: "Inter", system-ui, sans-serif; }
  .au-header { margin-bottom: 16px; }
  .au-eyebrow {
    display: block;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    margin-bottom: 4px;
  }
  .au-heading {
    font-size: 1.25rem;
    font-weight: 600;
    color: #e4e6eb;
  }
  .au-form {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin-bottom: 16px;
  }
  .au-field {
    display: flex;
    flex-direction: column;
    font-size: 0.72rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    gap: 4px;
  }
  .au-input {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 6px 10px;
  }
  .au-input:focus {
    outline: 2px solid #5b8af5;
    outline-offset: 1px;
  }
  .au-actions {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }
  .au-loading, .au-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
    margin: 0;
  }
  .au-error {
    color: #f59e42;
    background: rgba(245,158,66,0.10);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 0.82rem;
  }
  .au-count {
    font-size: 0.82rem;
    color: #8b919a;
    margin: 0 0 8px;
  }
`;
document.head.appendChild(auStyles);
