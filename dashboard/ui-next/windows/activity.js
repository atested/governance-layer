/**
 * Activity window — child window (depth 1).
 * Spec v2 section 7.1.
 *
 * Chronological feed of governance decisions with sorting, filtering,
 * pagination, and drill-down to Record Detail.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { openRecordDetail } from './record-detail.js';
import '../components/data-table.js';
import '../components/decision-tag.js';
import '../components/tier-badge.js';
import '../components/loading-indicator.js';

const PAGE_SIZE = 50;

const COLUMNS = [
  { key: 'sequence_position', label: '#', sortable: true, width: '60px' },
  { key: 'timestamp_utc', label: 'Time', sortable: true, width: '160px' },
  { key: 'event_type', label: 'Event Type', sortable: true },
  { key: 'policy_decision', label: 'Decision', sortable: true, width: '120px' },
  { key: 'summary', label: 'Summary', sortable: false },
  { key: 'governed_family', label: 'Category', sortable: true, width: '120px' },
];

/**
 * Open the Activity window.
 * @param {HTMLElement|null} trigger
 * @param {object} opts - { scrollToRecord?: string } for main page feed entry
 */
export function openActivityWindow(trigger, opts = {}) {
  const content = _buildContent();
  const result = _openAsChild('Activity', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    sortColumn: 'sequence_position',
    sortDirection: 'desc',
    currentPage: 1,
    startTime: '',
    endTime: '',
    totalCount: 0,
    data: [],
    scrollToRecord: opts.scrollToRecord || null,
  };

  _wireControls(state);
  _loadData(state);
}

// ---------- Build ----------

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'aw-content';
  el.innerHTML = `
    <div class="aw-header">
      <div class="aw-header-text">
        <span class="aw-eyebrow">Governance Activity</span>
        <span class="aw-heading" id="aw-heading">All Events</span>
      </div>
    </div>
    <div class="aw-filters">
      <label class="aw-filter-label">
        From
        <input type="datetime-local" class="aw-input" id="aw-start">
      </label>
      <label class="aw-filter-label">
        To
        <input type="datetime-local" class="aw-input" id="aw-end">
      </label>
      <atd-pill variant="primary" id="aw-apply">Apply</atd-pill>
      <atd-pill variant="outline" id="aw-clear">Clear</atd-pill>
    </div>
    <div id="aw-table-wrap">
      <atd-loading-indicator label="Loading events"></atd-loading-indicator>
    </div>
  `;
  return el;
}

function _wireControls(state) {
  const el = state.el;

  el.querySelector('#aw-apply').addEventListener('click', () => {
    state.startTime = el.querySelector('#aw-start').value;
    state.endTime = el.querySelector('#aw-end').value;
    state.currentPage = 1;
    _loadData(state);
  });

  el.querySelector('#aw-clear').addEventListener('click', () => {
    el.querySelector('#aw-start').value = '';
    el.querySelector('#aw-end').value = '';
    state.startTime = '';
    state.endTime = '';
    state.currentPage = 1;
    _loadData(state);
  });
}

async function _loadData(state) {
  const wrap = state.el.querySelector('#aw-table-wrap');
  wrap.innerHTML = '<atd-loading-indicator label="Loading events"></atd-loading-indicator>';

  const params = {
    limit: PAGE_SIZE,
    offset: (state.currentPage - 1) * PAGE_SIZE,
  };
  if (state.startTime) params.start_time = new Date(state.startTime).toISOString();
  if (state.endTime) params.end_time = new Date(state.endTime).toISOString();

  const res = await api.getActivity(params);
  if (!res.ok) {
    wrap.innerHTML = `<div class="aw-error">${_esc(res.error)}</div>`;
    return;
  }

  state.data = res.data.entries || [];
  state.totalCount = res.data.total_entries || state.data.length;

  // Update heading
  state.el.querySelector('#aw-heading').textContent = `All Events (${state.totalCount} total)`;

  _renderTable(state);

  // Handle scrollToRecord on first load
  if (state.scrollToRecord) {
    const recordId = state.scrollToRecord;
    state.scrollToRecord = null;
    // Find the entry and open Record Detail
    const entry = state.data.find(e =>
      e.request_id === recordId || e.event_id === recordId
    );
    if (entry) {
      setTimeout(() => {
        openRecordDetail(recordId, state.el);
      }, 100);
    }
  }
}

function _renderTable(state) {
  const wrap = state.el.querySelector('#aw-table-wrap');
  wrap.innerHTML = '';

  if (!state.data.length) {
    wrap.innerHTML = '<p class="aw-empty">No events found</p>';
    return;
  }

  const table = document.createElement('atd-data-table');
  table.setAttribute('columns', JSON.stringify(COLUMNS));
  table.setAttribute('page-size', String(PAGE_SIZE));

  // Map rows with variants and summary
  const rows = state.data.map(entry => ({
    ...entry,
    summary: _buildSummary(entry),
    _variant: entry.policy_decision === 'DENY' ? 'deny' :
              /observ|ungoverned/i.test(entry.event_category || entry.event_type || '') ? 'ungoverned' : undefined,
  }));

  table.data = rows;
  table.totalCount = state.totalCount;
  table.currentPage = state.currentPage;

  // Custom cell renderer for decision column
  table.cellRenderer = (row, col) => {
    if (col.key === 'policy_decision') {
      const d = row.policy_decision;
      if (d === 'ALLOW' || d === 'DENY') {
        return `<atd-decision-tag decision="${d}"></atd-decision-tag>`;
      }
      return _esc(d || '--');
    }
    if (col.key === 'timestamp_utc') {
      return _esc(_formatTime(row.timestamp_utc));
    }
    return null;
  };

  // Events
  table.addEventListener('table:sort', (e) => {
    state.sortColumn = e.detail.column;
    state.sortDirection = e.detail.direction;
    // Client-side sort for now (server sort params would need mapping)
    _renderTable(state);
  });

  table.addEventListener('table:page', (e) => {
    state.currentPage = e.detail.page;
    _loadData(state);
  });

  table.addEventListener('table:row-click', (e) => {
    const row = e.detail.row;
    const id = row.request_id || row.event_id || '';
    if (id) openRecordDetail(id, table);
  });

  wrap.appendChild(table);
}

function _buildSummary(entry) {
  const tool = entry.tool || '';
  const target = entry.target || '';
  if (tool && target) return `${tool}: ${target}`;
  if (tool) return tool;
  return entry.event_type || '--';
}

// ---------- Helpers ----------

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) {
    return modalManager.replaceChild({ title, trigger, content });
  }
  return modalManager.open({ title, trigger, content });
}

function _formatTime(iso) {
  if (!iso) return '--';
  try {
    return new Date(iso).toLocaleString();
  } catch { return iso; }
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// Inject styles
const awStyles = document.createElement('style');
awStyles.textContent = `
  .aw-content { font-family: "Inter", system-ui, sans-serif; }
  .aw-header { margin-bottom: 16px; }
  .aw-eyebrow {
    display: block;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    margin-bottom: 4px;
  }
  .aw-heading {
    font-size: 1.25rem;
    font-weight: 600;
    color: #e4e6eb;
  }
  .aw-filters {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
  }
  .aw-filter-label {
    display: flex;
    flex-direction: column;
    font-size: 0.72rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    gap: 4px;
  }
  .aw-input {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 6px 10px;
  }
  .aw-input:focus {
    outline: 2px solid #5b8af5;
    outline-offset: 1px;
  }
  .aw-loading, .aw-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
    margin: 0;
  }
  .aw-error {
    color: #f59e42;
    background: rgba(245,158,66,0.10);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 0.82rem;
  }
  @media (max-width: 600px) {
    .aw-filters { flex-direction: column; align-items: stretch; }
    .aw-filter-label { width: 100%; }
  }
`;
document.head.appendChild(awStyles);
