/**
 * Activity window — child window (depth 1).
 * D-035 redesign: stat cards, dual filter panes, data-rich table with
 * column toggles, pagination, CSV export, and
 * drill-down to Record Detail.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { openRecordDetail } from './record-detail.js';
import { installWindowTooltips, setTooltip, setTooltips } from '../tooltip-utils.js';
import { authorizeExport, downloadExport } from '../export-utils.js';
import { setTitleMessage } from '../window-messaging.js';
import { REPORT_RANGE_LIMITS, tierLabel } from '../tier-definitions.js';

// ---------- Column definitions ----------

const COLUMNS = [
  { key: 'sequence_position', label: '#',       width: '50px'  },
  { key: 'timestamp_utc', label: 'Time',       width: '120px' },
  { key: 'machine_id', label: 'Machine',       width: '120px' },
  { key: 'user_identity', label: 'User',       width: '120px' },
  { key: 'event_category', label: 'Event',     width: '110px' },
  { key: 'policy_decision', label: 'Decision', width: '80px'  },
  { key: 'matched_rule', label: 'Rule',        width: '140px' },
  { key: 'tool_name',   label: 'Action',       width: '140px' },
  { key: 'confidence_tier', label: 'Tier',     width: '50px'  },
  { key: 'action_type', label: 'Category',     width: '100px' },
  { key: 'target',      label: 'Target',       width: 'minmax(100px, 1fr)' },
];

const COLUMN_TOOLTIPS = {
  timestamp_utc: 'When the chain record was written.',
  machine_id: 'Machine that produced the governance record.',
  event_category: 'The kind of chain event: mediated action, approval, revocation, or observation.',
  policy_decision: 'The policy outcome recorded for this operation.',
  tool_name: 'The governed action name observed by Atested.',
  sequence_position: 'The record position in the hash-linked chain.',
  action_type: 'The evidence-based operation category assigned by the classifier.',
  confidence_tier: 'Classifier confidence tier for the operation evidence.',
  target: 'The file, command, URL, or artifact the operation acted on.',
  user_identity: 'The operator identity recorded with the chain event.',
  matched_rule: 'The policy rule that produced the decision for this operation.',
};

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
    ruleFilter: '',
    userFilter: '',
    machineFilter: opts.machineFilter || '',
    // Pagination
    currentPage: 1,
    pageSize: DEFAULT_PAGE_SIZE,
    totalMatching: 0,
    // Data
    data: [],
    summary: { allow_count: 0, deny_count: 0, tool_categories: 0 },
    // Column visibility (keyed by column key)
    visibleColumns: {},
    // Sort state
    sortKey: null,
    sortDir: 'asc',
    // Archive toggle
    includeArchives: false,
    // Options
    scrollToRecord: opts.scrollToRecord || null,
    selectedRecordId: null,
    // Tier
    tier: 'personal',
    _licensingStatus: '',
  };

  // Initialize column visibility — all columns visible by default
  for (const col of COLUMNS) {
    state.visibleColumns[col.key] = true;
  }

  _buildUI(state);
  installWindowTooltips(content);
  _applyStaticTooltips(state);

  // Fetch tier for range restrictions
  api.getLicensingMode().then(res => {
    if (res.ok) {
      state.tier = res.data.license_tier || 'personal';
      state._licensingStatus = res.data.license_status || '';
    }
    _enforceRangeTier(state);
  }).catch(() => {});

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
  state.refreshTimer = setInterval(() => {
    if (!document.body.contains(state.el)) {
      clearInterval(state.refreshTimer);
      return;
    }
    _loadData(state, { silent: true });
  }, 5000);
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
        <span class="aw-stat-label">Action Categories</span>
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
          <div class="aw-fp-decision-row">
            <span class="aw-fp-mini-label">Source</span>
            <div class="aw-decision-toggles" id="aw-source-toggles">
              <button class="aw-dtoggle aw-dtoggle-active" data-source="live">Live</button>
              <button class="aw-dtoggle" data-source="all">+ Archives</button>
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
              </select>
            </label>
            <label class="aw-fp-label">
              Action
              <select class="aw-select" id="aw-tool-filter">
                <option value="">All actions</option>
              </select>
            </label>
          </div>
          <div class="aw-fp-selects">
            <label class="aw-fp-label">
              Rule
              <select class="aw-select" id="aw-rule-filter">
                <option value="">All rules</option>
              </select>
            </label>
            <label class="aw-fp-label">
              User
              <select class="aw-select" id="aw-user-filter">
                <option value="">All users</option>
              </select>
            </label>
            <label class="aw-fp-label">
              Machine
              <select class="aw-select" id="aw-machine-filter">
                <option value="">All machines</option>
              </select>
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
        <div class="aw-export-control">
          <select class="aw-select aw-export-format" id="aw-export-format" aria-label="Export format">
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
            <option value="excel">Excel</option>
          </select>
          <button class="aw-btn aw-btn-export" id="aw-export">Export</button>
        </div>
      </div>
    </div>

    <!-- Column toggles -->
    <div class="aw-col-bar" id="aw-col-bar">
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
    setTooltip(btn, `Show or hide the ${col.label} column.`);
    btn.addEventListener('click', () => {
      state.visibleColumns[col.key] = !state.visibleColumns[col.key];
      btn.classList.toggle('aw-col-toggle-on', state.visibleColumns[col.key]);
      _renderTable(state);
    });
    container.appendChild(btn);
  }
}

function _applyStaticTooltips(state) {
  setTooltips(state.el, [
    ['#aw-stat-total', 'Total records matching the current Activity filters.'],
    ['#aw-stat-allow', 'Operations that policy allowed after classification.'],
    ['#aw-stat-deny', 'Operations denied before execution by Atested policy.'],
    ['#aw-stat-tools', 'Distinct action categories seen in the matching activity.'],
    ['#aw-from', 'Start of the Activity time filter.'],
    ['#aw-to', 'End of the Activity time filter.'],
    ['#aw-event-type', 'Limit the list to one kind of chain event.'],
    ['#aw-tool-filter', 'Filter by governed action name.'],
    ['#aw-rule-filter', 'Filter by the policy rule that matched.'],
    ['#aw-user-filter', 'Filter by user or agent identity.'],
    ['#aw-machine-filter', 'Filter by the machine that produced the record.'],
    ['#aw-apply', 'Apply the selected filters to the Activity list.'],
    ['#aw-clear', 'Clear all Activity filters.'],
    ['#aw-export-format', 'Choose JSON, CSV, or Excel-compatible export format.'],
    ['#aw-export', 'Export matching Activity records in the selected format.'],
  ]);
  state.el.querySelectorAll('.aw-quick-btn').forEach(btn => {
    setTooltip(btn, `Set the time range to ${btn.textContent.trim()}.`);
  });
  state.el.querySelectorAll('#aw-decision-toggles .aw-dtoggle').forEach(btn => {
    const label = btn.textContent.trim();
    setTooltip(btn, label === 'All' ? 'Show both allowed and denied decisions.' : `Show only ${label} decisions.`);
  });
  state.el.querySelectorAll('#aw-source-toggles .aw-dtoggle').forEach(btn => {
    const label = btn.textContent.trim();
    setTooltip(btn, label === 'Live' ? 'Show only live chain data.' : 'Include archived chain data.');
  });
  state.el.querySelectorAll('.aw-ps-btn').forEach(btn => {
    setTooltip(btn, `Show ${btn.dataset.size} records per page.`);
  });
}

// ---------- Wire controls ----------

function _wireControls(state) {
  const el = state.el;

  // Quick-select time buttons
  el.querySelector('#aw-quick-btns').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-range]');
    if (!btn) return;
    if (btn.classList.contains('aw-range-restricted')) {
      _showTierRestriction(state, btn.dataset.range);
      return;
    }
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
    el.querySelector('#aw-rule-filter').value = '';
    el.querySelector('#aw-user-filter').value = '';
    // Reset decision toggles
    el.querySelectorAll('#aw-decision-toggles .aw-dtoggle').forEach(b => b.classList.remove('aw-dtoggle-active'));
    el.querySelector('[data-decision=""]').classList.add('aw-dtoggle-active');
    // Reset source toggles
    el.querySelectorAll('#aw-source-toggles .aw-dtoggle').forEach(b => b.classList.remove('aw-dtoggle-active'));
    el.querySelector('[data-source="live"]').classList.add('aw-dtoggle-active');
    state.startTime = '';
    state.endTime = '';
    state.decisionFilter = '';
    state.eventTypeFilter = '';
    state.toolFilter = '';
    state.ruleFilter = '';
    state.userFilter = '';
    state.includeArchives = false;
    state.currentPage = 1;
    _loadData(state);
  });

  // Decision toggles
  el.querySelector('#aw-decision-toggles').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-decision]');
    if (!btn) return;
    el.querySelectorAll('#aw-decision-toggles .aw-dtoggle').forEach(b => b.classList.remove('aw-dtoggle-active'));
    btn.classList.add('aw-dtoggle-active');
    state.decisionFilter = btn.dataset.decision;
    state.currentPage = 1;
    _loadData(state);
  });

  // Archive source toggle
  el.querySelector('#aw-source-toggles').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-source]');
    if (!btn) return;
    el.querySelectorAll('#aw-source-toggles .aw-dtoggle').forEach(b => b.classList.remove('aw-dtoggle-active'));
    btn.classList.add('aw-dtoggle-active');
    state.includeArchives = btn.dataset.source === 'all';
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
  el.querySelector('#aw-export').addEventListener('click', () => _exportActivity(state));

}

function _readFilters(state) {
  const el = state.el;
  const fromVal = el.querySelector('#aw-from').value;
  const toVal = el.querySelector('#aw-to').value;
  state.startTime = fromVal ? new Date(fromVal).toISOString() : '';
  state.endTime = toVal ? new Date(toVal).toISOString() : '';
  state.eventTypeFilter = el.querySelector('#aw-event-type').value;
  state.toolFilter = el.querySelector('#aw-tool-filter').value;
  state.ruleFilter = el.querySelector('#aw-rule-filter').value;
  state.userFilter = el.querySelector('#aw-user-filter').value;
  state.machineFilter = el.querySelector('#aw-machine-filter').value;
}

// ---------- Data loading ----------

async function _loadData(state, options = {}) {
  const wrap = state.el.querySelector('#aw-table-wrap');
  if (!options.silent) {
    wrap.innerHTML = '<div class="aw-loading">Loading events...</div>';
  }

  const params = {
    limit: state.pageSize,
    offset: (state.currentPage - 1) * state.pageSize,
  };
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;
  if (state.decisionFilter) params.policy_decision = state.decisionFilter;
  if (state.eventTypeFilter) params.event_category = state.eventTypeFilter;
  if (state.toolFilter) params.tool_name = state.toolFilter;
  _applyMachineParams(params, state.machineFilter);
  if (state.includeArchives) params.include_archives = '1';

  const res = await api.getActivity(params);
  if (!res.ok) {
    wrap.innerHTML = `<div class="aw-error">${_esc(res.error)}</div>`;
    return;
  }

  state.data = res.data.entries || [];
  state.lastResponse = res.data || {};
  state.totalMatching = res.data.total_matching || state.data.length;
  state.summary = res.data.summary || { allow_count: 0, deny_count: 0, tool_categories: 0 };

  _populateFilterDropdowns(state);
  _updateStats(state);
  _renderTable(state);
  _renderPagination(state);

  // Handle scrollToRecord on first load
  if (state.scrollToRecord) {
    const recordId = state.scrollToRecord;
    state.scrollToRecord = null;
    const entry = state.data.find(e => _recordIdForEntry(e) === recordId);
    if (entry) {
      setTimeout(() => {
        const id = _recordIdForEntry(entry);
        if (id) _showRecordDetail(state, id, state.el);
      }, 100);
    }
  }
}

// ---------- Filter dropdowns ----------

function _populateFilterDropdowns(state) {
  const el = state.el;
  const data = state.data;

  // Collect unique values from loaded data
  const actions = new Set(), rules = new Set(), users = new Set(), machines = new Map();
  for (const entry of data) {
    const detail = entry.detail || {};
    if (detail.tool_name) actions.add(detail.tool_name);
    if (detail.matched_rule) rules.add(detail.matched_rule);
    if (entry.user_identity) users.add(entry.user_identity);
    if (entry.machine_id) machines.set(entry.machine_id, _machineLabel(entry));
  }
  const registryMachines = state.lastResponse?.unified_view?.machine_registry?.machines || [];
  for (const machine of registryMachines) {
    if (machine?.machine_id) machines.set(machine.machine_id, _machineLabel(machine));
  }

  _fillSelect(el.querySelector('#aw-tool-filter'), 'All actions', actions, state.toolFilter);
  _fillSelect(el.querySelector('#aw-rule-filter'), 'All rules', rules, state.ruleFilter);
  _fillSelect(el.querySelector('#aw-user-filter'), 'All users', users, state.userFilter);
  _fillMachineSelect(el.querySelector('#aw-machine-filter'), machines, state.machineFilter);
}

function _fillSelect(select, defaultLabel, values, currentValue) {
  if (!select) return;
  const sorted = [...values].sort();
  const opts = [`<option value="">${defaultLabel}</option>`];
  for (const v of sorted) {
    const sel = v === currentValue ? ' selected' : '';
    opts.push(`<option value="${_escAttr(v)}"${sel}>${_esc(v)}</option>`);
  }
  select.innerHTML = opts.join('');
}

function _fillMachineSelect(select, machines, currentValue) {
  if (!select) return;
  const opts = [
    '<option value="">All machines</option>',
    '<option value="__primary__">Primary only</option>',
  ];
  for (const [machineId, label] of [...machines.entries()].sort((a, b) => a[1].localeCompare(b[1]))) {
    const sel = machineId === currentValue ? ' selected' : '';
    opts.push(`<option value="${_escAttr(machineId)}"${sel}>${_esc(label)}</option>`);
  }
  select.innerHTML = opts.join('');
}

// ---------- Stats ----------

function _fmtNum(n) {
  return typeof n === 'number' ? n.toLocaleString() : String(n);
}

function _updateStats(state) {
  const el = state.el;
  el.querySelector('#aw-stat-total').textContent = _fmtNum(state.totalMatching);
  el.querySelector('#aw-stat-allow').textContent = _fmtNum(state.summary.allow_count);
  el.querySelector('#aw-stat-deny').textContent = _fmtNum(state.summary.deny_count);
  el.querySelector('#aw-stat-tools').textContent = _fmtNum(state.summary.tool_categories);

  // Update results bar
  const showing = state.data.length;
  el.querySelector('#aw-results-showing').textContent =
    `Showing ${_fmtNum(showing)} of ${_fmtNum(state.totalMatching)} matching events`;
}

// ---------- Table ----------

function _renderTable(state) {
  const wrap = state.el.querySelector('#aw-table-wrap');
  wrap.innerHTML = '';

  // Apply client-side filters (rule, user)
  let filteredData = state.data;
  if (state.ruleFilter) {
    filteredData = filteredData.filter(e => (e.detail || {}).matched_rule === state.ruleFilter);
  }
  if (state.userFilter) {
    filteredData = filteredData.filter(e => e.user_identity === state.userFilter);
  }

  if (!filteredData.length) {
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
    th.className = 'aw-th-sortable';
    const arrow = state.sortKey === col.key ? (state.sortDir === 'asc' ? ' \u25B2' : ' \u25BC') : '';
    th.textContent = col.label + arrow;
    if (col.width) th.style.width = col.width;
    if (state.sortKey === col.key) th.classList.add('aw-th-sorted');
    setTooltip(th, COLUMN_TOOLTIPS[col.key]);
    th.addEventListener('click', () => {
      if (state.sortKey === col.key) {
        state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        state.sortKey = col.key;
        state.sortDir = 'asc';
      }
      _renderTable(state);
    });
    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  table.appendChild(thead);

  // Sort data if a sort key is active
  let sortedData = filteredData;
  if (state.sortKey) {
    sortedData = [...filteredData].sort((a, b) => {
      const av = _getCellValue(state.sortKey, a, a.detail || {});
      const bv = _getCellValue(state.sortKey, b, b.detail || {});
      const cmp = av < bv ? -1 : av > bv ? 1 : 0;
      return state.sortDir === 'asc' ? cmp : -cmp;
    });
  }

  // Body
  const tbody = document.createElement('tbody');
  for (const entry of sortedData) {
    const tr = document.createElement('tr');
    tr.className = 'aw-row';
    tr.tabIndex = 0;

    const detail = entry.detail || {};
    const decision = detail.policy_decision || '';

    // DENY row tint
    if (decision === 'DENY') tr.classList.add('aw-row-deny');
    setTooltip(tr, _rowTooltip(entry, detail));

    for (const col of visibleCols) {
      const td = document.createElement('td');
      td.innerHTML = _renderCell(col.key, entry, detail);
      tr.appendChild(td);
    }

    // Click → Record Detail
    const recordId = _recordIdForEntry(entry);
    tr.dataset.recordId = recordId;
    tr.classList.toggle('aw-row-selected', recordId && recordId === state.selectedRecordId);
    tr.addEventListener('click', () => {
      if (recordId) _showRecordDetail(state, recordId, tr);
    });
    tr.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && recordId) _showRecordDetail(state, recordId, tr);
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

    case 'machine_id':
      return `<span class="aw-cell-tool">${_esc(_machineLabel(entry))}</span>`;

    case 'event_category': {
      const cat = entry.event_category || '';
      const display = _EVENT_LABELS[cat] || cat || '\u2014';
      return _esc(display);
    }

    case 'policy_decision': {
      const d = detail.policy_decision || '';
      if (d === 'ALLOW') return '<span class="aw-decision-allow">[ALLOW]</span>';
      if (d === 'DENY') return '<span class="aw-decision-deny">[DENY]</span>';
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
      return `<span class="aw-cell-target" data-tooltip="${_escAttr(target)}">${_esc(display)}</span>`;
    }

    case 'user_identity':
      return _esc(entry.user_identity || 'unknown');

    case 'matched_rule': {
      const rule = detail.matched_rule || '';
      return rule ? `<span class="aw-cell-tool">${_esc(rule)}</span>` : '<span class="aw-decision-muted">\u2014</span>';
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
  policy_rules_changed: 'Policy Change',
};

function _rowTooltip(entry, detail) {
  const parts = [];
  if (detail.policy_decision) parts.push(`Decision: ${detail.policy_decision}`);
  if (detail.tool_name) parts.push(`Action: ${detail.tool_name}`);
  if (entry.machine_id) parts.push(`Machine: ${_machineLabel(entry)}`);
  if (detail.action_type) parts.push(`Category: ${detail.action_type}`);
  if (detail.matched_rule) parts.push(`Rule: ${detail.matched_rule}`);
  if (detail.response) parts.push(`Response: ${detail.response}`);
  if (entry.event_category) parts.push(`Event: ${_EVENT_LABELS[entry.event_category] || entry.event_category}`);
  return parts.join(' | ') || 'Open this chain record.';
}

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

async function _exportActivity(state) {
  // Fetch up to 10000 rows with current filters (no pagination)
  const params = { limit: 10000, offset: 0 };
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;
  if (state.decisionFilter) params.policy_decision = state.decisionFilter;
  if (state.eventTypeFilter) params.event_category = state.eventTypeFilter;
  if (state.toolFilter) params.tool_name = state.toolFilter;
  _applyMachineParams(params, state.machineFilter);

  const format = state.el.querySelector('#aw-export-format')?.value || 'json';
  const auth = await authorizeExport({
    surface: 'activity',
    format,
    filters: { ...params },
    record_count: state.totalMatching || 0,
    chain_source: 'live',
  });
  if (!auth.ok) return;
  params.export_mode = '1';
  params.export_token = auth.token;

  const res = await api.getActivity(params);
  if (!res.ok) return;

  const entries = res.data.entries || [];
  const date = new Date().toISOString().slice(0, 10);
  const rows = entries.map(entry => {
    const detail = entry.detail || {};
    const out = {};
    for (const col of COLUMNS) out[col.key] = _getCellValue(col.key, entry, detail);
    return out;
  });
  const note = entries.length >= 10000 && (res.data.total_matching || 0) > 10000
    ? `Export limited to first 10,000 rows. Total matching: ${res.data.total_matching}`
    : '';
  downloadExport(format, `atested-activity-${date}`, COLUMNS, rows, {
    sheetName: 'Activity Export',
    note,
    jsonData: () => ({
      export_timestamp: new Date().toISOString(),
      filters: params,
      total_matching: res.data.total_matching || entries.length,
      entries,
    }),
  });
}

function _getCellValue(key, entry, detail) {
  switch (key) {
    case 'timestamp_utc': return entry.timestamp_utc || '';
    case 'machine_id': return _machineLabel(entry);
    case 'event_category': return entry.event_category || '';
    case 'policy_decision': return detail.policy_decision || '';
    case 'tool_name': return detail.tool_name || '';
    case 'sequence_position': return String(entry.sequence_position || '');
    case 'action_type': return detail.action_type || '';
    case 'confidence_tier': return detail.confidence_tier != null ? String(detail.confidence_tier) : '';
    case 'target': return detail.target || '';
    case 'user_identity': return entry.user_identity || '';
    case 'matched_rule': return detail.matched_rule || '';
    default: return '';
  }
}

function _applyMachineParams(params, machineFilter) {
  if (!machineFilter) return;
  if (machineFilter === '__primary__') params.machine_scope = 'primary';
  else params.machine_ids = machineFilter;
}

function _machineLabel(entry) {
  const id = entry?.machine_id || '';
  if (!id) return 'unknown';
  const name = entry?.display_name || entry?.machine_name || '';
  const role = entry?.machine_role || entry?.role || '';
  const shortId = id.length > 12 ? `${id.slice(0, 8)}...` : id;
  if (name && name !== id) return `${name} (${role || shortId})`;
  return role ? `${role}:${shortId}` : shortId;
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

function _showRecordDetail(state, recordId, trigger) {
  state.selectedRecordId = recordId;
  _applySelectedRow(state);
  openRecordDetail(recordId, trigger, {
    onClose: () => {
      state.selectedRecordId = null;
      _applySelectedRow(state);
    },
  });
}

function _applySelectedRow(state) {
  state.el.querySelectorAll('.aw-row').forEach(row => {
    const selected = !!state.selectedRecordId && row.dataset.recordId === state.selectedRecordId;
    row.classList.toggle('aw-row-selected', selected);
    if (selected) row.setAttribute('aria-current', 'true');
    else row.removeAttribute('aria-current');
  });
}

// ---------- Tier enforcement ----------

function _enforceRangeTier(state) {
  const config = REPORT_RANGE_LIMITS[state.tier];
  const restrictedSet = config ? new Set(config.restrictedRanges || []) : new Set();
  state.el.querySelectorAll('.aw-quick-btn').forEach(btn => {
    const isRestricted = restrictedSet.has(btn.dataset.range);
    btn.classList.toggle('aw-range-restricted', isRestricted);
    btn.disabled = false;
  });
}

function _showTierRestriction(state, rangeKey) {
  const config = REPORT_RANGE_LIMITS[state.tier];
  if (!config) return;
  const isDemo = typeof api.getScenario === 'function';
  const label = rangeKey === '30d' ? 'Last 30 days' : 'All time';
  const labelForTier = state.tier === 'personal' ? 'Personal tier' : tierLabel(state.tier);
  const text = `${labelForTier} includes a ${config.maxDays}-day rolling history. ${label} is available on ${config.unlocksAt} and above.`;
  let action;
  if (!isDemo) {
    const actionLabel = state._licensingStatus === 'licensed' ? 'See Licensing to upgrade.' : 'See Licensing to choose a plan.';
    action = { label: actionLabel, onClick: () => { import('./licensing.js').then(m => m.openLicensingWindow && m.openLicensingWindow(state.el)); } };
  }
  setTitleMessage(state.el, text, 'amber', { duration: 6000, dismissable: true, action });
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
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const mon = months[d.getMonth()];
    const day = d.getDate();
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${mon} ${day} ${hh}:${mm}`;
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
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    padding: 14px 16px;
    text-align: center;
  }
  .aw-stat-green { border-color: rgba(63,185,80,0.25); }
  .aw-stat-amber { border-color: rgba(210,153,34,0.25); }
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
  .aw-val-green { color: #3fb950; }
  .aw-val-amber { color: #d29922; }

  /* ---- Filter panes ---- */
  .aw-filter-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 12px;
  }
  .aw-filter-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
  }
  .aw-fp-accent {
    height: 6px;
    background: #3fb950;
  }
  .aw-fp-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
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
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    padding: 5px 8px;
    width: 100%;
    box-sizing: border-box;
  }
  .aw-input:focus, .aw-select:focus {
    outline: 2px solid #6699cc;
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
    border-radius: 2px;
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
  .aw-range-restricted {
    opacity: 0.45;
    border-style: dashed;
    border-color: rgba(210, 153, 34, 0.25);
    color: #6b7280;
  }
  .aw-range-restricted:hover {
    opacity: 0.7;
    border-color: rgba(210, 153, 34, 0.4);
    color: #d29922;
    background: rgba(210, 153, 34, 0.06);
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
    border-radius: 2px;
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
    border-color: rgba(102,153,204,0.4);
    background: rgba(102,153,204,0.1);
  }
  .aw-dtoggle-allow.aw-dtoggle-active {
    border-color: rgba(63,185,80,0.5);
    background: rgba(63,185,80,0.08);
    color: #3fb950;
  }
  .aw-dtoggle-deny.aw-dtoggle-active {
    border-color: rgba(248,81,73,0.5);
    background: rgba(248,81,73,0.08);
    color: #f85149;
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
    border-radius: 2px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 6px 16px;
    cursor: pointer;
    transition: background 0.1s;
  }
  .aw-btn-primary {
    background: #6699cc;
    color: #fff;
  }
  .aw-btn-primary:hover { background: #5580aa; }
  .aw-btn-muted {
    background: rgba(255,255,255,0.06);
    color: #8b919a;
  }
  .aw-btn-muted:hover { background: rgba(255,255,255,0.10); color: #e4e6eb; }
  .aw-btn-export {
    background: rgba(210,153,34,0.12);
    color: #d29922;
    border: 1px solid rgba(210,153,34,0.3);
  }
  .aw-btn-export:hover { background: rgba(210,153,34,0.2); }
  .aw-export-control {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .aw-export-format {
    min-width: 90px;
  }

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
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 2px 8px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .aw-ps-btn:hover { color: #e4e6eb; }
  .aw-ps-active {
    color: #6699cc;
    border-color: rgba(102,153,204,0.4);
    background: rgba(102,153,204,0.08);
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
    border-radius: 2px;
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
    color: #6699cc;
    border-color: rgba(102,153,204,0.4);
    background: rgba(102,153,204,0.08);
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
    border-radius: 2px;
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
  .aw-th-sortable {
    cursor: pointer;
    user-select: none;
    transition: color 0.1s;
  }
  .aw-th-sortable:hover { color: #e4e6eb; }
  .aw-th-sorted { color: #6699cc; }
  .aw-table tbody td {
    padding: 7px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 250px;
  }
  .aw-row {
    cursor: pointer;
    transition: background 0.1s;
  }
  .aw-row:hover {
    background: rgba(102,153,204,0.06);
  }
  .aw-row:focus-visible {
    outline: 2px solid #6699cc;
    outline-offset: -2px;
  }
  .aw-row-selected,
  .aw-row-selected:hover,
  .aw-row-deny.aw-row-selected,
  .aw-row-deny.aw-row-selected:hover {
    background: rgba(102,153,204,0.16);
    box-shadow: inset 4px 0 0 #6699cc;
  }
  .aw-row-deny {
    background: rgba(210,153,34,0.04);
  }
  .aw-row-deny:hover {
    background: rgba(210,153,34,0.10);
  }

  /* Cell styles */
  .aw-cell-time {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .aw-cell-tool {
    font-family: "JetBrains Mono", monospace;
    color: #6699cc;
  }
  .aw-cell-target {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .aw-decision-allow {
    font-size: 0.68rem;
    font-weight: 600;
    color: #3fb950;
    letter-spacing: 0.03em;
  }
  .aw-decision-deny {
    font-size: 0.68rem;
    font-weight: 600;
    color: #f85149;
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
    border-radius: 2px;
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
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 3px 8px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .aw-pag-num:hover { color: #e4e6eb; }
  .aw-pag-num-active {
    color: #6699cc;
    border-color: rgba(102,153,204,0.3);
    background: rgba(102,153,204,0.08);
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
    color: #d29922;
    background: rgba(210,153,34,0.10);
    padding: 12px 16px;
    border-radius: 2px;
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
