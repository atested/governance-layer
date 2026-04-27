/**
 * Audit window — child window (depth 1).
 * D-039 redesign: chain verification summary, dual filter panes,
 * data table with column toggles (Standard/Advanced), pagination,
 * CSV + JSON export, Record Detail drill-down.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { openRecordDetail } from './record-detail.js';

// ---------- Column definitions ----------

const COLUMNS = [
  // Standard columns
  { key: 'timestamp_utc',   label: 'Time',      standard: true,  width: '90px'  },
  { key: 'tool_name',       label: 'Tool',      standard: true  },
  { key: 'target',          label: 'Target',    standard: true  },
  { key: 'policy_decision', label: 'Decision',  standard: true,  width: '80px'  },
  { key: 'event_category',  label: 'Category',  standard: true,  width: '110px' },
  // Advanced columns
  { key: 'sequence_position', label: '#',        standard: false, width: '50px'  },
  { key: 'user_identity',   label: 'User',      standard: false, width: '120px' },
  { key: 'confidence_tier', label: 'Tier',      standard: false, width: '50px'  },
  { key: 'record_hash',     label: 'Record Hash', standard: false, width: '120px' },
];

const DEFAULT_PAGE_SIZE = 20;

/**
 * Open the Audit window.
 * @param {HTMLElement|null} trigger
 */
export function openAuditWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'au-root';

  const result = _openAsChild('Audit', 'Verify and export your chain records', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    // Filters
    startTime: '',
    endTime: '',
    userFilter: '',
    toolFilter: '',
    decisionFilter: '',
    categoryFilter: '',
    // Pagination
    currentPage: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    totalMatching: 0,
    // Data
    data: [],
    summary: { allow_count: 0, deny_count: 0, tool_categories: 0 },
    verification: { status: 'unknown', checked: false, break_count: 0 },
    chainEventCount: 0,
    // Column visibility
    visibleColumns: {},
  };

  for (const col of COLUMNS) {
    state.visibleColumns[col.key] = col.standard;
  }

  _buildUI(state);
  _loadData(state);
}

// ---------- Build UI ----------

function _buildUI(state) {
  const el = state.el;
  el.innerHTML = `
    <!-- Chain verification pane -->
    <div class="au-pane au-verify-pane" id="au-verify-pane">
      <div class="au-pane-accent au-accent-muted" id="au-verify-accent"></div>
      <div class="au-pane-header">Chain verification</div>
      <div class="au-pane-body">
        <div class="au-verify-metrics">
          <div class="au-verify-metric">
            <span class="au-vm-label">Records</span>
            <span class="au-vm-value" id="au-v-records">0</span>
          </div>
          <div class="au-verify-metric">
            <span class="au-vm-label">Integrity</span>
            <span class="au-vm-value" id="au-v-integrity">N/A</span>
          </div>
          <div class="au-verify-metric">
            <span class="au-vm-label">Breaks</span>
            <span class="au-vm-value" id="au-v-breaks">0</span>
          </div>
          <div class="au-verify-metric">
            <span class="au-vm-label">Status</span>
            <span class="au-vm-value" id="au-v-status">Checking...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Filter panes -->
    <div class="au-filter-row">
      <div class="au-pane">
        <div class="au-pane-accent au-accent-green"></div>
        <div class="au-pane-header">Time range</div>
        <div class="au-pane-body">
          <div class="au-fp-fields">
            <label class="au-fp-label">
              From
              <input type="datetime-local" class="au-input" id="au-from">
            </label>
            <label class="au-fp-label">
              To
              <input type="datetime-local" class="au-input" id="au-to">
            </label>
          </div>
          <div class="au-fp-quick" id="au-quick-btns">
            <button class="au-quick-btn" data-range="1h">Last hour</button>
            <button class="au-quick-btn" data-range="today">Today</button>
            <button class="au-quick-btn" data-range="7d">Last 7 days</button>
            <button class="au-quick-btn" data-range="30d">Last 30 days</button>
            <button class="au-quick-btn" data-range="all">All time</button>
          </div>
        </div>
      </div>
      <div class="au-pane">
        <div class="au-pane-accent au-accent-green"></div>
        <div class="au-pane-header">Filters</div>
        <div class="au-pane-body">
          <div class="au-fp-decision-row">
            <span class="au-fp-mini-label">Decision</span>
            <div class="au-decision-toggles" id="au-decision-toggles">
              <button class="au-dtoggle au-dtoggle-active" data-decision="">All</button>
              <button class="au-dtoggle au-dtoggle-allow" data-decision="ALLOW">Allow</button>
              <button class="au-dtoggle au-dtoggle-deny" data-decision="DENY">Deny</button>
            </div>
          </div>
          <div class="au-fp-fields">
            <label class="au-fp-label">
              User identity
              <input type="text" class="au-input" id="au-user" placeholder="e.g. cecil">
            </label>
            <label class="au-fp-label">
              Tool name
              <input type="text" class="au-input" id="au-tool" placeholder="e.g. FS_WRITE">
            </label>
          </div>
          <div class="au-fp-fields">
            <label class="au-fp-label">
              Category
              <select class="au-select" id="au-category">
                <option value="">All categories</option>
                <option value="action_decision">Action decision</option>
                <option value="verification_transition">Verification</option>
                <option value="opaque_approval">Approval</option>
                <option value="opaque_revocation">Revocation</option>
                <option value="ungoverned_observation">Ungoverned</option>
                <option value="opaque_invocation_decision">Opaque invocation</option>
              </select>
            </label>
          </div>
          <div class="au-fp-actions">
            <button class="au-btn au-btn-primary" id="au-search">Apply</button>
            <button class="au-btn au-btn-muted" id="au-clear">Clear</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Results bar -->
    <div class="au-results-bar">
      <span class="au-results-showing" id="au-results-showing">Apply to view records</span>
      <div class="au-results-controls">
        <div class="au-page-size" id="au-page-size">
          <span class="au-ps-label">Per page:</span>
          <button class="au-ps-btn au-ps-active" data-size="20">20</button>
          <button class="au-ps-btn" data-size="50">50</button>
          <button class="au-ps-btn" data-size="100">100</button>
        </div>
        <button class="au-btn au-btn-export" id="au-export-csv">Export filtered</button>
        <button class="au-btn au-btn-export" id="au-export-json">Export JSON</button>
      </div>
    </div>

    <!-- Column toggles -->
    <div class="au-col-bar" id="au-col-bar">
      <button class="au-col-preset au-col-preset-active" id="au-preset-standard">Standard</button>
      <button class="au-col-preset" id="au-preset-advanced">Advanced</button>
      <span class="au-col-sep"></span>
      <div class="au-col-toggles" id="au-col-toggles"></div>
    </div>

    <!-- Table -->
    <div class="au-table-wrap" id="au-table-wrap">
      <div class="au-empty">Use the filters above and click Apply to query the chain.</div>
    </div>

    <!-- Pagination -->
    <div class="au-pagination" id="au-pagination"></div>
  `;

  _buildColumnToggles(state);
  _wireControls(state);
}

// ---------- Column toggles ----------

function _buildColumnToggles(state) {
  const container = state.el.querySelector('#au-col-toggles');
  container.innerHTML = '';
  for (const col of COLUMNS) {
    const btn = document.createElement('button');
    btn.className = 'au-col-toggle' + (state.visibleColumns[col.key] ? ' au-col-toggle-on' : '');
    btn.textContent = col.label;
    btn.dataset.col = col.key;
    btn.addEventListener('click', () => {
      state.visibleColumns[col.key] = !state.visibleColumns[col.key];
      btn.classList.toggle('au-col-toggle-on', state.visibleColumns[col.key]);
      _updatePresetHighlight(state);
      _renderTable(state);
    });
    container.appendChild(btn);
  }
}

function _updatePresetHighlight(state) {
  const isStandard = COLUMNS.every(c => state.visibleColumns[c.key] === c.standard);
  const isAdvanced = COLUMNS.every(c => state.visibleColumns[c.key] === true);
  state.el.querySelector('#au-preset-standard').classList.toggle('au-col-preset-active', isStandard);
  state.el.querySelector('#au-preset-advanced').classList.toggle('au-col-preset-active', isAdvanced);
}

// ---------- Wire controls ----------

function _wireControls(state) {
  const el = state.el;

  // Quick-select time buttons
  el.querySelector('#au-quick-btns').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-range]');
    if (!btn) return;
    const range = btn.dataset.range;
    const now = new Date();
    let from = '';
    if (range === '1h') from = new Date(now.getTime() - 3600000).toISOString();
    else if (range === 'today') { const d = new Date(now); d.setHours(0,0,0,0); from = d.toISOString(); }
    else if (range === '7d') from = new Date(now.getTime() - 7 * 86400000).toISOString();
    else if (range === '30d') from = new Date(now.getTime() - 30 * 86400000).toISOString();
    else from = '';
    state.startTime = from;
    state.endTime = range === 'all' ? '' : now.toISOString();
    el.querySelector('#au-from').value = from ? _isoToLocal(from) : '';
    el.querySelector('#au-to').value = state.endTime ? _isoToLocal(state.endTime) : '';
    state.currentPage = 1;
    _loadData(state);
  });

  // Search
  el.querySelector('#au-search').addEventListener('click', () => {
    _readFilters(state);
    state.currentPage = 1;
    _loadData(state);
  });

  // Clear
  el.querySelector('#au-clear').addEventListener('click', () => {
    el.querySelector('#au-from').value = '';
    el.querySelector('#au-to').value = '';
    el.querySelector('#au-user').value = '';
    el.querySelector('#au-tool').value = '';
    el.querySelector('#au-category').value = '';
    el.querySelectorAll('.au-dtoggle').forEach(b => b.classList.remove('au-dtoggle-active'));
    el.querySelector('[data-decision=""]').classList.add('au-dtoggle-active');
    state.startTime = '';
    state.endTime = '';
    state.userFilter = '';
    state.toolFilter = '';
    state.decisionFilter = '';
    state.categoryFilter = '';
    state.currentPage = 1;
    _loadData(state);
  });

  // Decision toggles
  el.querySelector('#au-decision-toggles').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-decision]');
    if (!btn) return;
    el.querySelectorAll('.au-dtoggle').forEach(b => b.classList.remove('au-dtoggle-active'));
    btn.classList.add('au-dtoggle-active');
    state.decisionFilter = btn.dataset.decision;
  });

  // Per-page
  el.querySelector('#au-page-size').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-size]');
    if (!btn) return;
    el.querySelectorAll('.au-ps-btn').forEach(b => b.classList.remove('au-ps-active'));
    btn.classList.add('au-ps-active');
    state.pageSize = parseInt(btn.dataset.size, 10);
    state.currentPage = 1;
    _loadData(state);
  });

  // Exports
  el.querySelector('#au-export-csv').addEventListener('click', () => _exportCSV(state));
  el.querySelector('#au-export-json').addEventListener('click', () => _exportJSON(state));

  // Column presets
  el.querySelector('#au-preset-standard').addEventListener('click', () => {
    for (const col of COLUMNS) state.visibleColumns[col.key] = col.standard;
    _buildColumnToggles(state);
    _updatePresetHighlight(state);
    _renderTable(state);
  });
  el.querySelector('#au-preset-advanced').addEventListener('click', () => {
    for (const col of COLUMNS) state.visibleColumns[col.key] = true;
    _buildColumnToggles(state);
    _updatePresetHighlight(state);
    _renderTable(state);
  });
}

function _readFilters(state) {
  const el = state.el;
  const fromVal = el.querySelector('#au-from').value;
  const toVal = el.querySelector('#au-to').value;
  state.startTime = fromVal ? new Date(fromVal).toISOString() : '';
  state.endTime = toVal ? new Date(toVal).toISOString() : '';
  state.userFilter = el.querySelector('#au-user').value.trim();
  state.toolFilter = el.querySelector('#au-tool').value.trim();
  state.categoryFilter = el.querySelector('#au-category').value;
}

// ---------- Data loading ----------

async function _loadData(state) {
  const wrap = state.el.querySelector('#au-table-wrap');
  wrap.innerHTML = '<div class="au-loading">Applying filters...</div>';

  const params = {
    limit: state.pageSize,
    offset: (state.currentPage - 1) * state.pageSize,
  };
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;
  if (state.userFilter) params.user_identity = state.userFilter;
  if (state.toolFilter) params.tool_name = state.toolFilter;
  if (state.decisionFilter) params.policy_decision = state.decisionFilter;
  if (state.categoryFilter) params.event_category = state.categoryFilter;

  const res = await api.getAuditQuery(params);
  if (!res.ok) {
    wrap.innerHTML = `<div class="au-error">${_esc(res.error)}</div>`;
    return;
  }

  state.data = res.data.entries || [];
  state.totalMatching = res.data.total_matching || state.data.length;
  state.summary = res.data.summary || { allow_count: 0, deny_count: 0, tool_categories: 0 };
  state.verification = res.data.verification || { status: 'unknown', checked: false, break_count: 0 };
  state.chainEventCount = res.data.chain_event_count || 0;

  _updateVerificationPane(state);
  _updateResultsBar(state);
  _renderTable(state);
  _renderPagination(state);
}

// ---------- Verification pane ----------

function _updateVerificationPane(state) {
  const el = state.el;
  const v = state.verification;

  el.querySelector('#au-v-records').textContent = String(state.chainEventCount);

  const intEl = el.querySelector('#au-v-integrity');
  const status = v.status || 'unknown';
  intEl.textContent = status.toUpperCase();

  const breakEl = el.querySelector('#au-v-breaks');
  breakEl.textContent = String(v.break_count || 0);

  const statusEl = el.querySelector('#au-v-status');

  // Determine overall state
  let accentClass, statusText;
  if (status === 'ok' && v.checked) {
    accentClass = 'au-accent-green';
    statusText = 'Verified';
    intEl.className = 'au-vm-value au-vm-green';
    breakEl.className = 'au-vm-value au-vm-green';
    statusEl.className = 'au-vm-value au-vm-green';
  } else if (status === 'broken') {
    accentClass = 'au-accent-red';
    statusText = 'Breaks detected';
    intEl.className = 'au-vm-value au-vm-red';
    breakEl.className = 'au-vm-value au-vm-red';
    statusEl.className = 'au-vm-value au-vm-red';
  } else {
    accentClass = 'au-accent-muted';
    statusText = v.checked ? 'Unknown' : 'Not checked';
    intEl.className = 'au-vm-value';
    breakEl.className = 'au-vm-value';
    statusEl.className = 'au-vm-value';
  }

  statusEl.textContent = statusText;

  const accent = el.querySelector('#au-verify-accent');
  accent.className = 'au-pane-accent ' + accentClass;
}

// ---------- Results bar ----------

function _updateResultsBar(state) {
  const showing = state.data.length;
  state.el.querySelector('#au-results-showing').textContent =
    `Showing ${showing} of ${state.totalMatching} matching records`;
}

// ---------- Table ----------

function _renderTable(state) {
  const wrap = state.el.querySelector('#au-table-wrap');
  wrap.innerHTML = '';

  if (!state.data.length) {
    wrap.innerHTML = '<div class="au-empty">No matching records</div>';
    return;
  }

  const visibleCols = COLUMNS.filter(c => state.visibleColumns[c.key]);

  const table = document.createElement('table');
  table.className = 'au-table';

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
    tr.className = 'au-row';
    tr.tabIndex = 0;

    const detail = entry.detail || {};
    const decision = detail.policy_decision || '';
    if (decision === 'DENY') tr.classList.add('au-row-deny');

    for (const col of visibleCols) {
      const td = document.createElement('td');
      td.innerHTML = _renderCell(col.key, entry, detail);
      tr.appendChild(td);
    }

    const recordId = _recordIdForEntry(entry);
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
      return `<span class="au-cell-time">${_esc(_formatHumanDate(entry.timestamp_utc))}</span>`;
    case 'tool_name': {
      const tool = detail.tool_name || '';
      return tool ? `<span class="au-cell-tool">${_esc(tool)}</span>` : '<span class="au-cell-muted">\u2014</span>';
    }
    case 'target': {
      const target = detail.target || '';
      if (!target) return '<span class="au-cell-muted">\u2014</span>';
      const display = target.length > 50 ? '\u2026' + target.slice(-47) : target;
      return `<span class="au-cell-target" title="${_escAttr(target)}">${_esc(display)}</span>`;
    }
    case 'policy_decision': {
      const d = detail.policy_decision || '';
      if (d === 'ALLOW') return '<span class="au-decision-allow">[ALLOW]</span>';
      if (d === 'DENY') return '<span class="au-decision-deny">[DENY]</span>';
      return '<span class="au-cell-muted">\u2014</span>';
    }
    case 'event_category': {
      const cat = entry.event_category || '';
      return _esc(_EVENT_LABELS[cat] || cat || '\u2014');
    }
    case 'sequence_position':
      return _esc(String(entry.sequence_position || ''));
    case 'user_identity':
      return _esc(entry.user_identity || '\u2014');
    case 'confidence_tier': {
      const tier = detail.confidence_tier;
      return tier != null ? _esc(String(tier)) : '<span class="au-cell-muted">\u2014</span>';
    }
    case 'record_hash': {
      const hash = entry.evidence?.record_hash || '';
      if (!hash) return '<span class="au-cell-muted">\u2014</span>';
      return `<span class="au-cell-hash" title="${_escAttr(hash)}">${_esc(hash.substring(0, 12))}\u2026</span>`;
    }
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
  const container = state.el.querySelector('#au-pagination');
  container.innerHTML = '';

  const totalPages = Math.max(1, Math.ceil(state.totalMatching / state.pageSize));
  if (totalPages <= 1) return;

  const page = state.currentPage;
  const info = document.createElement('span');
  info.className = 'au-pag-info';
  info.textContent = `Page ${page} of ${totalPages}`;
  container.appendChild(info);

  const nav = document.createElement('div');
  nav.className = 'au-pag-nav';

  const prev = document.createElement('button');
  prev.className = 'au-pag-btn';
  prev.textContent = 'Previous';
  prev.disabled = page <= 1;
  prev.addEventListener('click', () => { state.currentPage--; _loadData(state); });
  nav.appendChild(prev);

  const pages = _computePageNumbers(page, totalPages);
  for (const p of pages) {
    if (p === '...') {
      const ell = document.createElement('span');
      ell.className = 'au-pag-ellipsis';
      ell.textContent = '\u2026';
      nav.appendChild(ell);
    } else {
      const btn = document.createElement('button');
      btn.className = 'au-pag-num' + (p === page ? ' au-pag-num-active' : '');
      btn.textContent = String(p);
      btn.addEventListener('click', () => { state.currentPage = p; _loadData(state); });
      nav.appendChild(btn);
    }
  }

  const next = document.createElement('button');
  next.className = 'au-pag-btn';
  next.textContent = 'Next';
  next.disabled = page >= totalPages;
  next.addEventListener('click', () => { state.currentPage++; _loadData(state); });
  nav.appendChild(next);

  container.appendChild(nav);
}

function _computePageNumbers(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = [1];
  if (current > 3) pages.push('...');
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) pages.push(i);
  if (current < total - 2) pages.push('...');
  pages.push(total);
  return pages;
}

// ---------- Export ----------

async function _exportCSV(state) {
  const params = { limit: 10000, offset: 0 };
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;
  if (state.userFilter) params.user_identity = state.userFilter;
  if (state.toolFilter) params.tool_name = state.toolFilter;
  if (state.decisionFilter) params.policy_decision = state.decisionFilter;
  if (state.categoryFilter) params.event_category = state.categoryFilter;

  const res = await api.getAuditQuery(params);
  if (!res.ok) return;

  const entries = res.data.entries || [];
  const allCols = COLUMNS;
  const header = allCols.map(c => c.label).join(',');
  const rows = entries.map(entry => {
    const detail = entry.detail || {};
    return allCols.map(col => {
      const val = _getCellValue(col.key, entry, detail);
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

  _downloadFile(csv, 'text/csv', `atested-audit-${_dateStr()}.csv`);
}

async function _exportJSON(state) {
  const params = { limit: 10000, offset: 0 };
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;
  if (state.userFilter) params.user_identity = state.userFilter;
  if (state.toolFilter) params.tool_name = state.toolFilter;
  if (state.decisionFilter) params.policy_decision = state.decisionFilter;
  if (state.categoryFilter) params.event_category = state.categoryFilter;

  const res = await api.getAuditQuery(params);
  if (!res.ok) return;

  const envelope = {
    export_timestamp: new Date().toISOString(),
    query_parameters: params,
    total_records: res.data.total_matching || 0,
    records: res.data.entries || [],
  };

  _downloadFile(JSON.stringify(envelope, null, 2), 'application/json', `atested-audit-${_dateStr()}.json`);
}

function _getCellValue(key, entry, detail) {
  switch (key) {
    case 'timestamp_utc': return entry.timestamp_utc || '';
    case 'tool_name': return detail.tool_name || '';
    case 'target': return detail.target || '';
    case 'policy_decision': return detail.policy_decision || '';
    case 'event_category': return entry.event_category || '';
    case 'sequence_position': return String(entry.sequence_position || '');
    case 'user_identity': return entry.user_identity || '';
    case 'confidence_tier': return detail.confidence_tier != null ? String(detail.confidence_tier) : '';
    case 'record_hash': return entry.evidence?.record_hash || '';
    default: return '';
  }
}

function _downloadFile(content, mime, filename) {
  const blob = new Blob([content], { type: mime + ';charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function _recordIdForEntry(entry) {
  const evidence = entry?.evidence || {};
  const category = entry?.event_category || '';
  if (category === 'action_decision') {
    return evidence.request_id || evidence.event_id || evidence.record_hash
      || entry?.request_id || entry?.event_id || entry?.record_hash || '';
  }
  return evidence.event_id || evidence.record_hash || evidence.request_id
    || entry?.event_id || entry?.record_hash || entry?.request_id || '';
}

// ---------- Helpers ----------

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) {
    return modalManager.replaceChild({ title, subtitle, trigger, content });
  }
  return modalManager.open({ title, subtitle, trigger, content });
}

function _formatHumanDate(isoStr) {
  if (!isoStr) return '\u2014';
  try {
    const d = new Date(isoStr);
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const mon = months[d.getMonth()];
    const day = d.getDate();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${mon} ${day}, ${hh}:${mm}:${ss}`;
  } catch { return isoStr; }
}

function _isoToLocal(isoStr) {
  try {
    const d = new Date(isoStr);
    const pad = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch { return ''; }
}

function _dateStr() {
  return new Date().toISOString().slice(0, 10);
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

const auStyles = document.createElement('style');
auStyles.textContent = `
  .au-root {
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }

  /* ---- Pane container ---- */
  .au-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 12px;
  }
  .au-pane-accent { height: 6px; }
  .au-accent-green { background: #3fb950; }
  .au-accent-red { background: #f85149; }
  .au-accent-muted { background: #6b7280; }
  .au-pane-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
    padding: 12px 20px 4px;
  }
  .au-pane-body {
    padding: 8px 20px 16px;
  }

  /* ---- Verification pane ---- */
  .au-verify-metrics {
    display: flex;
    gap: 32px;
  }
  .au-verify-metric {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .au-vm-label {
    font-size: 0.68rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 500;
  }
  .au-vm-value {
    font-size: 1.1rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .au-vm-green { color: #3fb950; }
  .au-vm-red { color: #f85149; }

  /* ---- Filter panes ---- */
  .au-filter-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 8px;
  }
  .au-fp-fields {
    display: flex;
    gap: 10px;
    margin-bottom: 8px;
  }
  .au-fp-label {
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
  .au-input, .au-select {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    padding: 5px 8px;
    width: 100%;
    box-sizing: border-box;
  }
  .au-input:focus, .au-select:focus {
    outline: 2px solid #6699cc;
    outline-offset: 1px;
  }
  .au-select {
    appearance: none;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%236b7280'/%3E%3C/svg%3E");
    background-repeat: no-repeat;
    background-position: right 8px center;
    padding-right: 24px;
  }

  /* Quick-select */
  .au-fp-quick {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .au-quick-btn {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.7rem;
    padding: 4px 10px;
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
  }
  .au-quick-btn:hover { background: #272b34; color: #e4e6eb; }

  /* Decision toggles */
  .au-fp-decision-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .au-fp-mini-label {
    font-size: 0.68rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 500;
  }
  .au-decision-toggles {
    display: flex;
    gap: 4px;
  }
  .au-dtoggle {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 3px 12px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .au-dtoggle:hover { color: #e4e6eb; }
  .au-dtoggle-active {
    color: #e4e6eb;
    border-color: rgba(102,153,204,0.4);
    background: rgba(102,153,204,0.1);
  }
  .au-dtoggle-allow.au-dtoggle-active {
    border-color: rgba(63,185,80,0.5);
    background: rgba(63,185,80,0.08);
    color: #3fb950;
  }
  .au-dtoggle-deny.au-dtoggle-active {
    border-color: rgba(248,81,73,0.5);
    background: rgba(248,81,73,0.08);
    color: #f85149;
  }
  .au-fp-actions {
    display: flex;
    gap: 8px;
  }

  /* Buttons */
  .au-btn {
    border: none;
    border-radius: 2px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 6px 16px;
    cursor: pointer;
    transition: background 0.1s;
  }
  .au-btn-primary { background: #6699cc; color: #fff; }
  .au-btn-primary:hover { background: #4f95ea; }
  .au-btn-muted { background: rgba(255,255,255,0.06); color: #8b919a; }
  .au-btn-muted:hover { background: rgba(255,255,255,0.10); color: #e4e6eb; }
  .au-btn-export {
    background: rgba(210,153,34,0.12);
    color: #d29922;
    border: 1px solid rgba(210,153,34,0.3);
  }
  .au-btn-export:hover { background: rgba(210,153,34,0.2); }

  /* ---- Results bar ---- */
  .au-results-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0;
    margin-bottom: 4px;
  }
  .au-results-showing {
    font-size: 0.78rem;
    color: #8b919a;
  }
  .au-results-controls {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .au-page-size {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  .au-ps-label {
    font-size: 0.68rem;
    color: #6b7280;
    margin-right: 2px;
  }
  .au-ps-btn {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 2px 8px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .au-ps-btn:hover { color: #e4e6eb; }
  .au-ps-active {
    color: #6699cc;
    border-color: rgba(102,153,204,0.4);
    background: rgba(102,153,204,0.08);
  }

  /* ---- Column bar ---- */
  .au-col-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 4px;
    flex-wrap: wrap;
  }
  .au-col-preset {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 3px 10px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .au-col-preset:hover { color: #e4e6eb; }
  .au-col-preset-active {
    color: #6699cc;
    border-color: rgba(102,153,204,0.4);
    background: rgba(102,153,204,0.08);
  }
  .au-col-sep {
    width: 1px;
    height: 16px;
    background: rgba(255,255,255,0.08);
    margin: 0 4px;
  }
  .au-col-toggles {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .au-col-toggle {
    background: none;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 2px;
    color: #6b7280;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.65rem;
    padding: 2px 7px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .au-col-toggle:hover { color: #8b919a; }
  .au-col-toggle-on {
    color: #e4e6eb;
    border-color: rgba(255,255,255,0.15);
    background: rgba(255,255,255,0.04);
  }

  /* ---- Table ---- */
  .au-table-wrap {
    overflow-x: auto;
    margin-bottom: 8px;
  }
  .au-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .au-table thead th {
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
  .au-table tbody td {
    padding: 7px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 300px;
  }
  .au-row {
    cursor: pointer;
    transition: background 0.1s;
  }
  .au-row:hover { background: rgba(102,153,204,0.06); }
  .au-row:focus-visible {
    outline: 2px solid #6699cc;
    outline-offset: -2px;
  }
  .au-row-deny { background: rgba(210,153,34,0.04); }
  .au-row-deny:hover { background: rgba(210,153,34,0.10); }

  /* Cell styles */
  .au-cell-time {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .au-cell-tool {
    font-family: "JetBrains Mono", monospace;
    color: #6699cc;
  }
  .au-cell-target {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .au-cell-hash {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .au-cell-muted { color: #6b7280; }
  .au-decision-allow {
    font-size: 0.68rem;
    font-weight: 600;
    color: #3fb950;
    letter-spacing: 0.03em;
  }
  .au-decision-deny {
    font-size: 0.68rem;
    font-weight: 600;
    color: #f85149;
    letter-spacing: 0.03em;
  }

  /* ---- Pagination ---- */
  .au-pagination {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 0 4px;
  }
  .au-pag-info { font-size: 0.75rem; color: #8b919a; }
  .au-pag-nav { display: flex; align-items: center; gap: 4px; }
  .au-pag-btn {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 4px 12px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .au-pag-btn:hover:not(:disabled) { color: #e4e6eb; background: rgba(255,255,255,0.10); }
  .au-pag-btn:disabled { opacity: 0.4; cursor: default; }
  .au-pag-num {
    background: none;
    border: 1px solid transparent;
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 3px 8px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .au-pag-num:hover { color: #e4e6eb; }
  .au-pag-num-active {
    color: #6699cc;
    border-color: rgba(102,153,204,0.3);
    background: rgba(102,153,204,0.08);
  }
  .au-pag-ellipsis { color: #6b7280; font-size: 0.72rem; padding: 0 4px; }

  /* ---- Utility ---- */
  .au-loading {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
    font-style: italic;
  }
  .au-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
    font-style: italic;
  }
  .au-error {
    color: #d29922;
    background: rgba(210,153,34,0.10);
    padding: 12px 16px;
    border-radius: 2px;
    font-size: 0.82rem;
  }

  /* ---- Responsive ---- */
  @media (max-width: 700px) {
    .au-filter-row { grid-template-columns: 1fr; }
    .au-results-bar { flex-direction: column; gap: 8px; align-items: flex-start; }
    .au-fp-fields { flex-direction: column; }
    .au-verify-metrics { flex-wrap: wrap; gap: 16px; }
  }
`;
document.head.appendChild(auStyles);
