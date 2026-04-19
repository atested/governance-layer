/**
 * Activity window — child window (depth 1).
 * D-035 redesign: stat cards, dual filter panes, data-rich table with
 * column toggles (Standard/Advanced), pagination, CSV export, and
 * drill-down to Record Detail.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { openRecordDetail } from './record-detail.js';

// ---------- Column definitions ----------

const COLUMNS = [
  // Standard columns (shown by default)
  { key: 'timestamp_utc', label: 'Time',       standard: true,  width: '90px'  },
  { key: 'event_category', label: 'Event',     standard: true,  width: '140px' },
  { key: 'policy_decision', label: 'Decision', standard: true,  width: '80px'  },
  { key: 'tool_name',   label: 'Tool',         standard: true  },
  // Advanced columns (hidden by default)
  { key: 'sequence_position', label: '#',       standard: false, width: '50px'  },
  { key: 'action_type', label: 'Category',     standard: false, width: '100px' },
  { key: 'confidence_tier', label: 'Tier',     standard: false, width: '50px'  },
  { key: 'target',      label: 'Target',       standard: false },
  { key: 'user_identity', label: 'User',       standard: false, width: '120px' },
];

const DEFAULT_PAGE_SIZE = 20;

/**
 * Open the Activity window.
 * @param {HTMLElement|null} trigger
 * @param {object} opts - { scrollToRecord?, startTime?, endTime?,
 *                          toolFilter?, eventTypeFilter?, decisionFilter? }
 */
export function openActivityWindow(trigger, opts = {}) {
  const content = document.createElement('div');
  content.className = 'aw-root';

  const result = _openAsChild('Activity', 'Decision log for all Atested operations', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    // Filters — accept pre-set values from opts (for cross-window navigation)
    startTime: opts.startTime || '',
    endTime: opts.endTime || '',
    decisionFilter: opts.decisionFilter || '',       // '', 'ALLOW', 'DENY'
    eventTypeFilter: opts.eventTypeFilter || '',
    toolFilter: opts.toolFilter || '',
    // Pagination
    currentPage: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    totalMatching: 0,
    // Data
    data: [],
    summary: { allow_count: 0, deny_count: 0, tool_categories: 0 },
    // Column visibility (keyed by column key)
    visibleColumns: {},
    // Options
    scrollToRecord: opts.scrollToRecord || null,
  };

  // Initialize column visibility to Standard preset
  for (const col of COLUMNS) {
    state.visibleColumns[col.key] = col.standard;
  }

  _buildUI(state);

  // Apply pre-set filters to UI controls
  if (state.startTime) {
    const fromEl = state.el.querySelector('#aw-from');
    if (fromEl) fromEl.value = _isoToLocal(state.startTime);
  }
  if (state.endTime) {
    const toEl = state.el.querySelector('#aw-to');
    if (toEl) toEl.value = _isoToLocal(state.endTime);
  }
  if (state.toolFilter) {
    const toolEl = state.el.querySelector('#aw-tool-filter');
    if (toolEl) toolEl.value = state.toolFilter;
  }
  if (state.eventTypeFilter) {
    const etEl = state.el.querySelector('#aw-event-type');
    if (etEl) etEl.value = state.eventTypeFilter;
  }
  if (state.decisionFilter) {
    const toggles = state.el.querySelectorAll('.aw-dtoggle');
    toggles.forEach(b => {
      b.classList.toggle('aw-dtoggle-active', b.dataset.decision === state.decisionFilter);
    });
  }

  _loadData(state);
}

// ---------- Build UI ----------

function _buildUI(state) {
  const el = state.el;
  el.innerHTML = `
    <!-- Stat cards -->
    <div class="aw-stats">
      <div class="aw-stat-card">
        <span class="aw-stat-label">Total Events</span>
        <span class="aw-stat-value" id="aw-stat-total">0</span>
      </div>
      <div class="aw-stat-card aw-stat-green">
        <span class="aw-stat-label">Allow</span>
        <span class="aw-stat-value aw-val-green" id="aw-stat-allow">0</span>
      </div>
      <div class="aw-stat-card aw-stat-amber">
        <span class="aw-stat-label">Deny</span>
        <span class="aw-stat-value aw-val-amber" id="aw-stat-deny">0</span>
      </div>
      <div class="aw-stat-card">
        <span class="aw-stat-label">Tool Categories</span>
        <span class="aw-stat-value" id="aw-stat-tools">0</span>
      </div>
    </div>

    <!-- Filter panes -->
    <div class="aw-filter-row">
      <div class="aw-filter-pane">
        <div class="aw-fp-accent"></div>
        <div class="aw-fp-header">Time range</div>
        <div class="aw-fp-body">
          <div class="aw-fp-fields">
            <label class="aw-fp-label">
              From
              <input type="datetime-local" class="aw-input" id="aw-from">
            </label>
            <label class="aw-fp-label">
              To
              <input type="datetime-local" class="aw-input" id="aw-to">
            </label>
          </div>
          <div class="aw-fp-quick" id="aw-quick-btns">
            <button class="aw-quick-btn" data-range="1h">Last hour</button>
            <button class="aw-quick-btn" data-range="today">Today</button>
            <button class="aw-quick-btn" data-range="7d">Last 7 days</button>
            <button class="aw-quick-btn" data-range="30d">Last 30 days</button>
            <button class="aw-quick-btn" data-range="all">All time</button>
          </div>
        </div>
      </div>
      <div class="aw-filter-pane">
        <div class="aw-fp-accent"></div>
        <div class="aw-fp-header">Filters</div>
        <div class="aw-fp-body">
          <div class="aw-fp-decision-row">
            <span class="aw-fp-mini-label">Decision</span>
            <div class="aw-decision-toggles" id="aw-decision-toggles">
              <button class="aw-dtoggle aw-dtoggle-active" data-decision="">All</button>
              <button class="aw-dtoggle aw-dtoggle-allow" data-decision="ALLOW">Allow</button>
              <button class="aw-dtoggle aw-dtoggle-deny" data-decision="DENY">Deny</button>
            </div>
          </div>
          <div class="aw-fp-selects">
            <label class="aw-fp-label">
              Event type
              <select class="aw-select" id="aw-event-type">
                <option value="">All event types</option>
                <option value="action_decision">Action decision</option>
                <option value="verification_transition">Verification</option>
                <option value="opaque_approval">Approval</option>
                <option value="opaque_revocation">Revocation</option>
                <option value="ungoverned_observation">Ungoverned</option>
                <option value="opaque_invocation_decision">Opaque invocation</option>
              </select>
            </label>
            <label class="aw-fp-label">
              Tool
              <input type="text" class="aw-input" id="aw-tool-filter" placeholder="All tools">
            </label>
          </div>
          <div class="aw-fp-actions">
            <button class="aw-btn aw-btn-primary" id="aw-apply">Apply</button>
            <button class="aw-btn aw-btn-muted" id="aw-clear">Clear</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Results bar -->
    <div class="aw-results-bar">
      <span class="aw-results-showing" id="aw-results-showing">Loading...</span>
      <div class="aw-results-controls">
        <div class="aw-page-size" id="aw-page-size">
          <span class="aw-ps-label">Per page:</span>
          <button class="aw-ps-btn aw-ps-active" data-size="20">20</button>
          <button class="aw-ps-btn" data-size="50">50</button>
          <button class="aw-ps-btn" data-size="100">100</button>
        </div>
        <button class="aw-btn aw-btn-export" id="aw-export">Export filtered</button>
      </div>
    </div>

    <!-- Column toggles -->
    <div class="aw-col-bar" id="aw-col-bar">
      <button class="aw-col-preset aw-col-preset-active" id="aw-preset-standard">Standard</button>
      <button class="aw-col-preset" id="aw-preset-advanced">Advanced</button>
      <span class="aw-col-sep"></span>
      <div class="aw-col-toggles" id="aw-col-toggles"></div>
    </div>

    <!-- Table -->
    <div class="aw-table-wrap" id="aw-table-wrap">
      <div class="aw-loading">Loading events...</div>
    </div>

    <!-- Pagination -->
    <div class="aw-pagination" id="aw-pagination"></div>
  `;

  _buildColumnToggles(state);
  _wireControls(state);
}

// ---------- Column toggles ----------

function _buildColumnToggles(state) {
  const container = state.el.querySelector('#aw-col-toggles');
  container.innerHTML = '';
  for (const col of COLUMNS) {
    const btn = document.createElement('button');
    btn.className = 'aw-col-toggle' + (state.visibleColumns[col.key] ? ' aw-col-toggle-on' : '');
    btn.textContent = col.label;
    btn.dataset.col = col.key;
    btn.addEventListener('click', () => {
      state.visibleColumns[col.key] = !state.visibleColumns[col.key];
      btn.classList.toggle('aw-col-toggle-on', state.visibleColumns[col.key]);
      _updatePresetHighlight(state);
      _renderTable(state);
    });
    container.appendChild(btn);
  }
}

function _updatePresetHighlight(state) {
  const isStandard = COLUMNS.every(c => state.visibleColumns[c.key] === c.standard);
  const isAdvanced = COLUMNS.every(c => state.visibleColumns[c.key] === true);
  state.el.querySelector('#aw-preset-standard').classList.toggle('aw-col-preset-active', isStandard);
  state.el.querySelector('#aw-preset-advanced').classList.toggle('aw-col-preset-active', isAdvanced);
}

// ---------- Wire controls ----------

function _wireControls(state) {
  const el = state.el;

  // Quick-select time buttons
  el.querySelector('#aw-quick-btns').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-range]');
    if (!btn) return;
    const range = btn.dataset.range;
    const now = new Date();
    let from = '';
    if (range === '1h') {
      from = new Date(now.getTime() - 3600000).toISOString();
    } else if (range === 'today') {
      const d = new Date(now); d.setHours(0, 0, 0, 0);
      from = d.toISOString();
    } else if (range === '7d') {
      from = new Date(now.getTime() - 7 * 86400000).toISOString();
    } else if (range === '30d') {
      from = new Date(now.getTime() - 30 * 86400000).toISOString();
    } else {
      from = '';
    }
    state.startTime = from;
    state.endTime = range === 'all' ? '' : now.toISOString();
    // Update the From/To inputs to reflect the selection
    el.querySelector('#aw-from').value = from ? _isoToLocal(from) : '';
    el.querySelector('#aw-to').value = state.endTime ? _isoToLocal(state.endTime) : '';
    state.currentPage = 1;
    _loadData(state);
  });

  // Apply button
  el.querySelector('#aw-apply').addEventListener('click', () => {
    _readFilters(state);
    state.currentPage = 1;
    _loadData(state);
  });

  // Clear button
  el.querySelector('#aw-clear').addEventListener('click', () => {
    el.querySelector('#aw-from').value = '';
    el.querySelector('#aw-to').value = '';
    el.querySelector('#aw-event-type').value = '';
    el.querySelector('#aw-tool-filter').value = '';
    // Reset decision toggles
    el.querySelectorAll('.aw-dtoggle').forEach(b => b.classList.remove('aw-dtoggle-active'));
    el.querySelector('[data-decision=""]').classList.add('aw-dtoggle-active');
    state.startTime = '';
    state.endTime = '';
    state.decisionFilter = '';
    state.eventTypeFilter = '';
    state.toolFilter = '';
    state.currentPage = 1;
    _loadData(state);
  });

  // Decision toggles
  el.querySelector('#aw-decision-toggles').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-decision]');
    if (!btn) return;
    el.querySelectorAll('.aw-dtoggle').forEach(b => b.classList.remove('aw-dtoggle-active'));
    btn.classList.add('aw-dtoggle-active');
    state.decisionFilter = btn.dataset.decision;
    state.currentPage = 1;
    _loadData(state);
  });

  // Per-page size
  el.querySelector('#aw-page-size').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-size]');
    if (!btn) return;
    el.querySelectorAll('.aw-ps-btn').forEach(b => b.classList.remove('aw-ps-active'));
    btn.classList.add('aw-ps-active');
    state.pageSize = parseInt(btn.dataset.size, 10);
    state.currentPage = 1;
    _loadData(state);
  });

  // Export
  el.querySelector('#aw-export').addEventListener('click', () => _exportCSV(state));

  // Column presets
  el.querySelector('#aw-preset-standard').addEventListener('click', () => {
    for (const col of COLUMNS) state.visibleColumns[col.key] = col.standard;
    _buildColumnToggles(state);
    _updatePresetHighlight(state);
    _renderTable(state);
  });
  el.querySelector('#aw-preset-advanced').addEventListener('click', () => {
    for (const col of COLUMNS) state.visibleColumns[col.key] = true;
    _buildColumnToggles(state);
    _updatePresetHighlight(state);
    _renderTable(state);
  });
}

function _readFilters(state) {
  const el = state.el;
  const fromVal = el.querySelector('#aw-from').value;
  const toVal = el.querySelector('#aw-to').value;
  state.startTime = fromVal ? new Date(fromVal).toISOString() : '';
  state.endTime = toVal ? new Date(toVal).toISOString() : '';
  state.eventTypeFilter = el.querySelector('#aw-event-type').value;
  state.toolFilter = el.querySelector('#aw-tool-filter').value.trim();
}

// ---------- Data loading ----------

async function _loadData(state) {
  const wrap = state.el.querySelector('#aw-table-wrap');
  wrap.innerHTML = '<div class="aw-loading">Loading events...</div>';

  const params = {
    limit: state.pageSize,
    offset: (state.currentPage - 1) * state.pageSize,
  };
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;
  if (state.decisionFilter) params.policy_decision = state.decisionFilter;
  if (state.eventTypeFilter) params.event_category = state.eventTypeFilter;
  if (state.toolFilter) params.tool_name = state.toolFilter;

  const res = await api.getActivity(params);
  if (!res.ok) {
    wrap.innerHTML = `<div class="aw-error">${_esc(res.error)}</div>`;
    return;
  }

  state.data = res.data.entries || [];
  state.totalMatching = res.data.total_matching || state.data.length;
  state.summary = res.data.summary || { allow_count: 0, deny_count: 0, tool_categories: 0 };

  _updateStats(state);
  _renderTable(state);
  _renderPagination(state);

  // Handle scrollToRecord on first load
  if (state.scrollToRecord) {
    const recordId = state.scrollToRecord;
    state.scrollToRecord = null;
    const entry = state.data.find(e =>
      (e.evidence?.request_id === recordId) || (e.evidence?.event_id === recordId)
    );
    if (entry) {
      setTimeout(() => {
        const id = entry.evidence?.request_id || entry.evidence?.event_id || '';
        if (id) openRecordDetail(id, state.el);
      }, 100);
    }
  }
}

// ---------- Stats ----------

function _updateStats(state) {
  const el = state.el;
  el.querySelector('#aw-stat-total').textContent = String(state.totalMatching);
  el.querySelector('#aw-stat-allow').textContent = String(state.summary.allow_count);
  el.querySelector('#aw-stat-deny').textContent = String(state.summary.deny_count);
  el.querySelector('#aw-stat-tools').textContent = String(state.summary.tool_categories);

  // Update results bar
  const showing = state.data.length;
  el.querySelector('#aw-results-showing').textContent =
    `Showing ${showing} of ${state.totalMatching} matching events`;
}

// ---------- Table ----------

function _renderTable(state) {
  const wrap = state.el.querySelector('#aw-table-wrap');
  wrap.innerHTML = '';

  if (!state.data.length) {
    wrap.innerHTML = '<div class="aw-empty">No events found</div>';
    return;
  }

  const visibleCols = COLUMNS.filter(c => state.visibleColumns[c.key]);

  // Build table
  const table = document.createElement('table');
  table.className = 'aw-table';

  // Grid template
  const colWidths = visibleCols.map(c => c.width || '1fr').join(' ');
  table.style.setProperty('--aw-col-template', colWidths);

  // Header
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  for (const col of visibleCols) {
    const th = document.createElement('th');
    th.textContent = col.label;
    if (col.width) th.style.width = col.width;
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  // Body
  const tbody = document.createElement('tbody');
  for (const entry of state.data) {
    const tr = document.createElement('tr');
    tr.className = 'aw-row';
    tr.tabIndex = 0;

    const detail = entry.detail || {};
    const decision = detail.policy_decision || '';

    // DENY row tint
    if (decision === 'DENY') tr.classList.add('aw-row-deny');

    for (const col of visibleCols) {
      const td = document.createElement('td');
      td.innerHTML = _renderCell(col.key, entry, detail);
      tr.appendChild(td);
    }

    // Click → Record Detail
    const recordId = entry.evidence?.request_id || entry.evidence?.event_id || '';
    tr.addEventListener('click', () => {
      if (recordId) openRecordDetail(recordId, tr);
    });
    tr.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && recordId) openRecordDetail(recordId, tr);
    });

    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  wrap.appendChild(table);
}

function _renderCell(key, entry, detail) {
  switch (key) {
    case 'timestamp_utc':
      return `<span class="aw-cell-time">${_esc(_formatTime24(entry.timestamp_utc))}</span>`;

    case 'event_category': {
      const cat = entry.event_category || '';
      const display = _EVENT_LABELS[cat] || cat || '\u2014';
      return _esc(display);
    }

    case 'policy_decision': {
      const d = detail.policy_decision || '';
      if (d === 'ALLOW') return '<span class="aw-decision-allow">ALLOW</span>';
      if (d === 'DENY') return '<span class="aw-decision-deny">DENY</span>';
      return '<span class="aw-decision-muted">\u2014</span>';
    }

    case 'tool_name': {
      const tool = detail.tool_name || '';
      return tool ? `<span class="aw-cell-tool">${_esc(tool)}</span>` : '<span class="aw-decision-muted">\u2014</span>';
    }

    case 'sequence_position':
      return _esc(String(entry.sequence_position || ''));

    case 'action_type':
      return _esc(detail.action_type || '\u2014');

    case 'confidence_tier': {
      const tier = detail.confidence_tier;
      return tier != null ? _esc(String(tier)) : '<span class="aw-decision-muted">\u2014</span>';
    }

    case 'target': {
      const target = detail.target || '';
      if (!target) return '<span class="aw-decision-muted">\u2014</span>';
      // Truncate long paths, full path in title
      const display = target.length > 50 ? '\u2026' + target.slice(-47) : target;
      return `<span class="aw-cell-target" title="${_escAttr(target)}">${_esc(display)}</span>`;
    }

    case 'user_identity':
      return _esc(entry.user_identity || '\u2014');

    default:
      return '\u2014';
  }
}

const _EVENT_LABELS = {
  action_decision: 'Action',
  verification_transition: 'Verification',
  opaque_approval: 'Approval',
  opaque_revocation: 'Revocation',
  opaque_invocation_decision: 'Invocation',
  ungoverned_observation: 'Ungoverned',
};

// ---------- Pagination ----------

function _renderPagination(state) {
  const container = state.el.querySelector('#aw-pagination');
  container.innerHTML = '';

  const totalPages = Math.max(1, Math.ceil(state.totalMatching / state.pageSize));
  if (totalPages <= 1) return;

  const page = state.currentPage;

  // Info
  const info = document.createElement('span');
  info.className = 'aw-pag-info';
  info.textContent = `Page ${page} of ${totalPages}`;
  container.appendChild(info);

  const nav = document.createElement('div');
  nav.className = 'aw-pag-nav';

  // Previous
  const prev = document.createElement('button');
  prev.className = 'aw-pag-btn';
  prev.textContent = 'Previous';
  prev.disabled = page <= 1;
  prev.addEventListener('click', () => { state.currentPage--; _loadData(state); });
  nav.appendChild(prev);

  // Page numbers
  const pages = _computePageNumbers(page, totalPages);
  for (const p of pages) {
    if (p === '...') {
      const ell = document.createElement('span');
      ell.className = 'aw-pag-ellipsis';
      ell.textContent = '\u2026';
      nav.appendChild(ell);
    } else {
      const btn = document.createElement('button');
      btn.className = 'aw-pag-num' + (p === page ? ' aw-pag-num-active' : '');
      btn.textContent = String(p);
      btn.addEventListener('click', () => { state.currentPage = p; _loadData(state); });
      nav.appendChild(btn);
    }
  }

  // Next
  const next = document.createElement('button');
  next.className = 'aw-pag-btn';
  next.textContent = 'Next';
  next.disabled = page >= totalPages;
  next.addEventListener('click', () => { state.currentPage++; _loadData(state); });
  nav.appendChild(next);

  container.appendChild(nav);
}

function _computePageNumbers(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = [];
  pages.push(1);
  if (current > 3) pages.push('...');
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    pages.push(i);
  }
  if (current < total - 2) pages.push('...');
  pages.push(total);
  return pages;
}

// ---------- Export ----------

async function _exportCSV(state) {
  // Fetch up to 10000 rows with current filters (no pagination)
  const params = { limit: 10000, offset: 0 };
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;
  if (state.decisionFilter) params.policy_decision = state.decisionFilter;
  if (state.eventTypeFilter) params.event_category = state.eventTypeFilter;
  if (state.toolFilter) params.tool_name = state.toolFilter;

  const res = await api.getActivity(params);
  if (!res.ok) return;

  const entries = res.data.entries || [];
  const allCols = COLUMNS; // export all columns regardless of visibility

  // Build CSV
  const header = allCols.map(c => c.label).join(',');
  const rows = entries.map(entry => {
    const detail = entry.detail || {};
    return allCols.map(col => {
      const val = _getCellValue(col.key, entry, detail);
      // Escape CSV value
      if (val.includes(',') || val.includes('"') || val.includes('\n')) {
        return '"' + val.replace(/"/g, '""') + '"';
      }
      return val;
    }).join(',');
  });

  let csv = header + '\n' + rows.join('\n');
  if (entries.length >= 10000 && (res.data.total_matching || 0) > 10000) {
    csv += '\n# Note: Export limited to first 10,000 rows. Total matching: ' + res.data.total_matching;
  }

  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const date = new Date().toISOString().slice(0, 10);
  a.download = `atested-activity-${date}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function _getCellValue(key, entry, detail) {
  switch (key) {
    case 'timestamp_utc': return entry.timestamp_utc || '';
    case 'event_category': return entry.event_category || '';
    case 'policy_decision': return detail.policy_decision || '';
    case 'tool_name': return detail.tool_name || '';
    case 'sequence_position': return String(entry.sequence_position || '');
    case 'action_type': return detail.action_type || '';
    case 'confidence_tier': return detail.confidence_tier != null ? String(detail.confidence_tier) : '';
    case 'target': return detail.target || '';
    case 'user_identity': return entry.user_identity || '';
    default: return '';
  }
}

// ---------- Helpers ----------

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) {
    return modalManager.replaceChild({ title, subtitle, trigger, content });
  }
  return modalManager.open({ title, subtitle, trigger, content });
}

function _formatTime24(isoStr) {
  if (!isoStr) return '\u2014';
  try {
    const d = new Date(isoStr);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  } catch { return isoStr; }
}

function _isoToLocal(isoStr) {
  try {
    const d = new Date(isoStr);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch { return ''; }
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

function _escAttr(str) {
  return (str || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ---------- Styles ----------

const awStyles = document.createElement('style');
awStyles.textContent = `
  .aw-root {
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }

  /* ---- Stat cards ---- */
  .aw-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }
  .aw-stat-card {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
  }
  .aw-stat-green { border-color: rgba(34,197,94,0.25); }
  .aw-stat-amber { border-color: rgba(245,158,66,0.25); }
  .aw-stat-label {
    display: block;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    margin-bottom: 4px;
    font-weight: 500;
  }
  .aw-stat-value {
    font-size: 1.35rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .aw-val-green { color: #22c55e; }
  .aw-val-amber { color: #f5a623; }

  /* ---- Filter panes ---- */
  .aw-filter-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }
  .aw-filter-pane {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    overflow: hidden;
  }
  .aw-fp-accent {
    height: 6px;
    background: #22c55e;
  }
  .aw-fp-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5b8af5;
    font-weight: 600;
    padding: 12px 16px 6px;
  }
  .aw-fp-body {
    padding: 6px 16px 14px;
  }
  .aw-fp-fields {
    display: flex;
    gap: 10px;
    margin-bottom: 8px;
  }
  .aw-fp-label {
    display: flex;
    flex-direction: column;
    font-size: 0.68rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    gap: 3px;
    flex: 1;
    font-weight: 500;
  }
  .aw-input, .aw-select {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    padding: 5px 8px;
    width: 100%;
    box-sizing: border-box;
  }
  .aw-input:focus, .aw-select:focus {
    outline: 2px solid #5b8af5;
    outline-offset: 1px;
  }
  .aw-select {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%236b7280'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    padding-right: 24px;
  }

  /* Quick-select buttons */
  .aw-fp-quick {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .aw-quick-btn {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.7rem;
    padding: 4px 10px;
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
  }
  .aw-quick-btn:hover {
    background: #272b34;
    color: #e4e6eb;
  }

  /* Decision toggles */
  .aw-fp-decision-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .aw-fp-mini-label {
    font-size: 0.68rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 500;
  }
  .aw-decision-toggles {
    display: flex;
    gap: 4px;
  }
  .aw-dtoggle {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 3px 12px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .aw-dtoggle:hover { color: #e4e6eb; }
  .aw-dtoggle-active {
    color: #e4e6eb;
    border-color: rgba(91,138,245,0.4);
    background: rgba(91,138,245,0.1);
  }
  .aw-dtoggle-allow.aw-dtoggle-active {
    border-color: rgba(34,197,94,0.5);
    background: rgba(34,197,94,0.08);
    color: #22c55e;
  }
  .aw-dtoggle-deny.aw-dtoggle-active {
    border-color: rgba(239,68,68,0.5);
    background: rgba(239,68,68,0.08);
    color: #ef4444;
  }
  .aw-fp-selects {
    display: flex;
    gap: 10px;
    margin-bottom: 10px;
  }
  .aw-fp-actions {
    display: flex;
    gap: 8px;
  }

  /* Buttons */
  .aw-btn {
    border: none;
    border-radius: 6px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 6px 16px;
    cursor: pointer;
    transition: background 0.1s;
  }
  .aw-btn-primary {
    background: #5b8af5;
    color: #fff;
  }
  .aw-btn-primary:hover { background: #4a7ae5; }
  .aw-btn-muted {
    background: rgba(255,255,255,0.06);
    color: #8b919a;
  }
  .aw-btn-muted:hover { background: rgba(255,255,255,0.10); color: #e4e6eb; }
  .aw-btn-export {
    background: rgba(245,158,66,0.12);
    color: #f5a623;
    border: 1px solid rgba(245,158,66,0.3);
  }
  .aw-btn-export:hover { background: rgba(245,158,66,0.2); }

  /* ---- Results bar ---- */
  .aw-results-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    margin-bottom: 4px;
  }
  .aw-results-showing {
    font-size: 0.78rem;
    color: #8b919a;
  }
  .aw-results-controls {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .aw-page-size {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .aw-ps-label {
    font-size: 0.68rem;
    color: #6b7280;
    margin-right: 2px;
  }
  .aw-ps-btn {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 5px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 2px 8px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .aw-ps-btn:hover { color: #e4e6eb; }
  .aw-ps-active {
    color: #5b8af5;
    border-color: rgba(91,138,245,0.4);
    background: rgba(91,138,245,0.08);
  }

  /* ---- Column bar ---- */
  .aw-col-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }
  .aw-col-preset {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 3px 10px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .aw-col-preset:hover { color: #e4e6eb; }
  .aw-col-preset-active {
    color: #5b8af5;
    border-color: rgba(91,138,245,0.4);
    background: rgba(91,138,245,0.08);
  }
  .aw-col-sep {
    width: 1px;
    height: 16px;
    background: rgba(255,255,255,0.08);
    margin: 0 4px;
  }
  .aw-col-toggles {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .aw-col-toggle {
    background: none;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 4px;
    color: #6b7280;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.65rem;
    padding: 2px 7px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .aw-col-toggle:hover { color: #8b919a; }
  .aw-col-toggle-on {
    color: #e4e6eb;
    border-color: rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.04);
  }

  /* ---- Table ---- */
  .aw-table-wrap {
    overflow-x: auto;
    margin-bottom: 8px;
  }
  .aw-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .aw-table thead th {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    font-weight: 600;
    text-align: left;
    padding: 6px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    white-space: nowrap;
  }
  .aw-table tbody td {
    padding: 7px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 300px;
  }
  .aw-row {
    cursor: pointer;
    transition: background 0.1s;
  }
  .aw-row:hover {
    background: rgba(91,138,245,0.06);
  }
  .aw-row:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: -2px;
  }
  .aw-row-deny {
    background: rgba(245,158,66,0.04);
  }
  .aw-row-deny:hover {
    background: rgba(245,158,66,0.10);
  }

  /* Cell styles */
  .aw-cell-time {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .aw-cell-tool {
    font-family: "JetBrains Mono", monospace;
    color: #5b8af5;
  }
  .aw-cell-target {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .aw-decision-allow {
    font-size: 0.68rem;
    font-weight: 600;
    color: #22c55e;
    letter-spacing: 0.03em;
  }
  .aw-decision-deny {
    font-size: 0.68rem;
    font-weight: 600;
    color: #ef4444;
    letter-spacing: 0.03em;
  }
  .aw-decision-muted {
    color: #6b7280;
  }

  /* ---- Pagination ---- */
  .aw-pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0 4px;
  }
  .aw-pag-info {
    font-size: 0.75rem;
    color: #8b919a;
  }
  .aw-pag-nav {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .aw-pag-btn {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 4px 12px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .aw-pag-btn:hover:not(:disabled) { color: #e4e6eb; background: rgba(255,255,255,0.10); }
  .aw-pag-btn:disabled { opacity: 0.4; cursor: default; }
  .aw-pag-num {
    background: none;
    border: 1px solid transparent;
    border-radius: 5px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 3px 8px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .aw-pag-num:hover { color: #e4e6eb; }
  .aw-pag-num-active {
    color: #5b8af5;
    border-color: rgba(91,138,245,0.3);
    background: rgba(91,138,245,0.08);
  }
  .aw-pag-ellipsis {
    color: #6b7280;
    font-size: 0.72rem;
    padding: 0 4px;
  }

  /* ---- Utility ---- */
  .aw-loading {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
    font-style: italic;
  }
  .aw-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
    font-style: italic;
  }
  .aw-error {
    color: #f59e42;
    background: rgba(245,158,66,0.10);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 0.82rem;
  }

  /* ---- Responsive ---- */
  @media (max-width: 700px) {
    .aw-stats { grid-template-columns: repeat(2, 1fr); }
    .aw-filter-row { grid-template-columns: 1fr; }
    .aw-results-bar { flex-direction: column; gap: 8px; align-items: flex-start; }
    .aw-fp-fields { flex-direction: column; }
    .aw-fp-selects { flex-direction: column; }
  }
`;
document.head.appendChild(awStyles);
