/**
 * Reports window — child window (depth 1).
 * D-040 redesign: dual filter panes, toggle-based grouping, clickable
 * bar chart rows with atomic navigation to Activity, CSV export.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';

const GROUP_OPTIONS = [
  { key: 'tool',     label: 'Tool' },
  { key: 'category', label: 'Category' },
  { key: 'decision', label: 'Decision' },
  { key: 'user',     label: 'User' },
  { key: 'hour',     label: 'Hour' },
];

const GROUP_LABELS = {
  tool: 'By tool', category: 'By category', decision: 'By decision',
  user: 'By user', hour: 'By hour',
};

const GROUP_COUNT_LABELS = {
  tool: 'tools', category: 'categories', decision: 'decisions',
  user: 'users', hour: 'hours',
};

/**
 * Open the Reports window.
 * @param {HTMLElement|null} trigger
 */
export function openReportsWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'rp-root';

  const result = _openAsChild('Reports', 'Atested metrics and trends over time', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    startTime: '',
    endTime: '',
    groupBy: 'tool',
    data: null,
  };

  _buildUI(state);
  _wireControls(state);
  _loadReport(state);
}

// ---------- Build UI ----------

function _buildUI(state) {
  const el = state.el;
  el.innerHTML = `
    <!-- Filter panes -->
    <div class="rp-filter-row">
      <div class="rp-filter-pane">
        <div class="rp-fp-accent"></div>
        <div class="rp-fp-header">Time range</div>
        <div class="rp-fp-body">
          <div class="rp-fp-fields">
            <label class="rp-fp-label">
              From
              <input type="datetime-local" class="rp-input" id="rp-from">
            </label>
            <label class="rp-fp-label">
              To
              <input type="datetime-local" class="rp-input" id="rp-to">
            </label>
          </div>
          <div class="rp-fp-quick" id="rp-quick-btns">
            <button class="rp-quick-btn" data-range="1h">Last hour</button>
            <button class="rp-quick-btn" data-range="today">Today</button>
            <button class="rp-quick-btn" data-range="7d">Last 7 days</button>
            <button class="rp-quick-btn" data-range="30d">Last 30 days</button>
            <button class="rp-quick-btn" data-range="all">All time</button>
          </div>
        </div>
      </div>
      <div class="rp-filter-pane">
        <div class="rp-fp-accent"></div>
        <div class="rp-fp-header">Report options</div>
        <div class="rp-fp-body">
          <div class="rp-group-section">
            <span class="rp-fp-mini-label">Group by</span>
            <div class="rp-group-toggles" id="rp-group-toggles">
              ${GROUP_OPTIONS.map(o =>
                `<button class="rp-gtoggle${o.key === 'tool' ? ' rp-gtoggle-active' : ''}" data-group="${o.key}">${o.label}</button>`
              ).join('')}
            </div>
          </div>
          <div class="rp-fp-actions">
            <button class="rp-btn rp-btn-primary" id="rp-generate">Generate</button>
            <button class="rp-btn rp-btn-export" id="rp-export">Export CSV</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Stat cards -->
    <div class="rp-stats">
      <div class="rp-stat-card">
        <span class="rp-stat-label">Total records</span>
        <span class="rp-stat-value" id="rp-stat-total">\u2014</span>
      </div>
      <div class="rp-stat-card rp-stat-green">
        <span class="rp-stat-label">Allow</span>
        <span class="rp-stat-value rp-val-green" id="rp-stat-allow">\u2014</span>
      </div>
      <div class="rp-stat-card rp-stat-amber">
        <span class="rp-stat-label">Deny</span>
        <span class="rp-stat-value rp-val-amber" id="rp-stat-deny">\u2014</span>
      </div>
      <div class="rp-stat-card">
        <span class="rp-stat-label">Deny rate</span>
        <span class="rp-stat-value" id="rp-stat-rate">\u2014</span>
      </div>
    </div>

    <!-- Grouping pane -->
    <div class="rp-group-pane" id="rp-group-pane">
      <div class="rp-gp-accent"></div>
      <div class="rp-gp-header">
        <span id="rp-gp-title">By tool</span>
        <span class="rp-gp-count" id="rp-gp-count"></span>
      </div>
      <div class="rp-gp-body" id="rp-gp-body">
        <div class="rp-loading">Loading\u2026</div>
      </div>
    </div>
  `;
}

// ---------- Wire controls ----------

function _wireControls(state) {
  const el = state.el;

  // Quick-select time buttons
  el.querySelector('#rp-quick-btns').addEventListener('click', (e) => {
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
    el.querySelector('#rp-from').value = from ? _isoToLocal(from) : '';
    el.querySelector('#rp-to').value = state.endTime ? _isoToLocal(state.endTime) : '';
  });

  // Group by toggles
  el.querySelector('#rp-group-toggles').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-group]');
    if (!btn) return;
    el.querySelectorAll('.rp-gtoggle').forEach(b => b.classList.remove('rp-gtoggle-active'));
    btn.classList.add('rp-gtoggle-active');
    state.groupBy = btn.dataset.group;
  });

  // Generate button
  el.querySelector('#rp-generate').addEventListener('click', () => {
    _readTimeFilters(state);
    _loadReport(state);
  });

  // Export button
  el.querySelector('#rp-export').addEventListener('click', () => _exportCSV(state));
}

function _readTimeFilters(state) {
  const fromVal = state.el.querySelector('#rp-from').value;
  const toVal = state.el.querySelector('#rp-to').value;
  state.startTime = fromVal ? new Date(fromVal).toISOString() : '';
  state.endTime = toVal ? new Date(toVal).toISOString() : '';
}

// ---------- Load report ----------

async function _loadReport(state) {
  const body = state.el.querySelector('#rp-gp-body');
  body.innerHTML = '<div class="rp-loading">Loading\u2026</div>';

  const params = { group_by: state.groupBy };
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;

  const res = await api.getAuditReport(params);
  if (!res.ok) {
    body.innerHTML = `<div class="rp-error">${_esc(res.error)}</div>`;
    return;
  }

  state.data = res.data;
  _renderStats(state);
  _renderBars(state);
}

// ---------- Render stats ----------

function _renderStats(state) {
  const d = state.data;
  const summary = d.decision_summary || {};
  const total = d.total_records || 0;
  const allow = summary.ALLOW || 0;
  const deny = summary.DENY || 0;
  const rate = total > 0 ? ((deny / total) * 100).toFixed(1) + '%' : '0%';

  state.el.querySelector('#rp-stat-total').textContent = _fmtNum(total);
  state.el.querySelector('#rp-stat-allow').textContent = _fmtNum(allow);
  state.el.querySelector('#rp-stat-deny').textContent = _fmtNum(deny);
  state.el.querySelector('#rp-stat-rate').textContent = rate;
}

// ---------- Render bars ----------

function _renderBars(state) {
  const d = state.data;
  const groups = d.groups || [];
  const groupBy = d.group_by || state.groupBy;

  // Update header
  state.el.querySelector('#rp-gp-title').textContent = GROUP_LABELS[groupBy] || `By ${groupBy}`;
  const countLabel = GROUP_COUNT_LABELS[groupBy] || 'groups';
  state.el.querySelector('#rp-gp-count').textContent = `${groups.length} ${countLabel}`;

  const body = state.el.querySelector('#rp-gp-body');
  body.innerHTML = '';

  if (!groups.length) {
    body.innerHTML = '<div class="rp-empty">No data for the selected time range.</div>';
    return;
  }

  const maxCount = Math.max(...groups.map(g => g.count || 0), 1);

  // Compute average deny rate for amber-bar highlighting
  const totalDeny = groups.reduce((sum, g) => sum + (g.deny_count || 0), 0);
  const totalCount = groups.reduce((sum, g) => sum + (g.count || 0), 0);
  const avgDenyRate = totalCount > 0 ? totalDeny / totalCount : 0;

  for (const group of groups) {
    const pct = ((group.count || 0) / maxCount * 100).toFixed(1);
    const denyCount = group.deny_count || 0;
    const denyRate = group.count > 0 ? denyCount / group.count : 0;
    // Amber bar if this group's deny rate is >2x the average and has at least 1 deny
    const isAmber = denyCount > 0 && avgDenyRate > 0 && denyRate > avgDenyRate * 2;

    const row = document.createElement('div');
    row.className = 'rp-bar-row';
    row.title = `Click to view in Activity`;
    row.innerHTML = `
      <span class="rp-bar-label">${_esc(group.key || '\u2014')}</span>
      <div class="rp-bar-track">
        <div class="rp-bar-fill${isAmber ? ' rp-bar-amber' : ''}" style="width: ${pct}%"></div>
      </div>
      <span class="rp-bar-count">${_fmtNum(group.count || 0)}</span>
    `;

    // Click handler — atomic navigation to Activity
    row.addEventListener('click', () => {
      _navigateToActivity(state, groupBy, group.key);
    });

    body.appendChild(row);
  }
}

// ---------- Atomic navigation ----------

function _navigateToActivity(state, groupBy, groupKey) {
  // Build filter opts for Activity window
  const opts = {};
  if (state.startTime) opts.startTime = state.startTime;
  if (state.endTime) opts.endTime = state.endTime;

  if (groupBy === 'tool') {
    opts.toolFilter = groupKey;
  } else if (groupBy === 'category') {
    opts.eventTypeFilter = groupKey;
  } else if (groupBy === 'decision') {
    opts.decisionFilter = groupKey;
  } else if (groupBy === 'hour') {
    // Hour grouping: set time range to that specific hour
    // groupKey is like "14:00"
    const hourStr = groupKey.replace(':00', '');
    const hour = parseInt(hourStr, 10);
    if (!isNaN(hour)) {
      // Use the report's date context — find a date from start/end time or today
      const baseDate = state.startTime ? new Date(state.startTime) : new Date();
      const fromDate = new Date(baseDate);
      fromDate.setHours(hour, 0, 0, 0);
      const toDate = new Date(fromDate);
      toDate.setHours(hour + 1, 0, 0, 0);
      opts.startTime = fromDate.toISOString();
      opts.endTime = toDate.toISOString();
    }
  }
  // user grouping — no direct filter in Activity, just pass time range

  // Close Reports, open Activity with pre-set filters
  modalManager.closeAll();
  setTimeout(() => {
    import('./activity.js').then(mod => {
      mod.openActivityWindow(null, opts);
    });
  }, 0);
}

// ---------- CSV export ----------

function _exportCSV(state) {
  if (!state.data || !state.data.groups || !state.data.groups.length) return;

  const groupBy = state.data.group_by || state.groupBy;
  const lines = [`"${groupBy}","count","deny_count"`];
  for (const g of state.data.groups) {
    lines.push(`"${(g.key || '').replace(/"/g, '""')}",${g.count || 0},${g.deny_count || 0}`);
  }

  // Add summary
  const summary = state.data.decision_summary || {};
  lines.push('');
  lines.push('"Summary"');
  lines.push(`"Total records",${state.data.total_records || 0}`);
  lines.push(`"ALLOW",${summary.ALLOW || 0}`);
  lines.push(`"DENY",${summary.DENY || 0}`);

  const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const dateStr = new Date().toISOString().slice(0, 10);
  a.download = `atested-report-${groupBy}-${dateStr}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------- Utility ----------

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, subtitle, trigger, content });
  return modalManager.open({ title, subtitle, trigger, content });
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

function _fmtNum(n) {
  return typeof n === 'number' ? n.toLocaleString() : String(n);
}

function _isoToLocal(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
  } catch { return ''; }
}

// ---------- Styles ----------

const rpStyles = document.createElement('style');
rpStyles.textContent = `
  .rp-root { font-family: "Inter", system-ui, sans-serif; }

  /* ---- Filter row ---- */
  .rp-filter-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }

  .rp-filter-pane {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    overflow: hidden;
  }
  .rp-fp-accent {
    height: 6px;
    background: #22c55e;
  }
  .rp-fp-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #60a5fa;
    font-weight: 600;
    padding: 12px 20px 4px;
  }
  .rp-fp-body {
    padding: 8px 20px 16px;
  }
  .rp-fp-fields {
    display: flex;
    gap: 12px;
    margin-bottom: 10px;
  }
  .rp-fp-label {
    display: flex;
    flex-direction: column;
    font-size: 0.72rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    gap: 4px;
    flex: 1;
  }
  .rp-input {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 6px 10px;
  }
  .rp-input:focus { outline: 2px solid #60a5fa; outline-offset: 1px; }

  /* Quick buttons */
  .rp-fp-quick {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .rp-quick-btn {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #8b919a;
    font-size: 0.72rem;
    padding: 4px 10px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .rp-quick-btn:hover {
    background: rgba(96,165,250,0.12);
    color: #60a5fa;
    border-color: rgba(96,165,250,0.3);
  }

  /* Group by toggles */
  .rp-group-section { margin-bottom: 14px; }
  .rp-fp-mini-label {
    display: block;
    font-size: 0.68rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
  }
  .rp-group-toggles {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .rp-gtoggle {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #8b919a;
    font-size: 0.78rem;
    padding: 5px 12px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .rp-gtoggle:hover {
    background: rgba(96,165,250,0.08);
    color: #c4d0f0;
  }
  .rp-gtoggle-active {
    background: rgba(96,165,250,0.15);
    color: #60a5fa;
    border-color: rgba(96,165,250,0.4);
    font-weight: 600;
  }

  /* Action buttons */
  .rp-fp-actions {
    display: flex;
    gap: 8px;
  }
  .rp-btn {
    border: none;
    border-radius: 6px;
    font-size: 0.82rem;
    padding: 7px 18px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.15s;
  }
  .rp-btn-primary {
    background: #60a5fa;
    color: #fff;
  }
  .rp-btn-primary:hover { background: #4f95ea; }
  .rp-btn-export {
    background: rgba(245,166,35,0.12);
    color: #f5a623;
    border: 1px solid rgba(245,166,35,0.3);
  }
  .rp-btn-export:hover {
    background: rgba(245,166,35,0.20);
  }

  /* ---- Stat cards ---- */
  .rp-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }
  .rp-stat-card {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
  }
  .rp-stat-green { border-color: rgba(34,197,94,0.25); }
  .rp-stat-amber { border-color: rgba(245,166,35,0.25); }
  .rp-stat-label {
    display: block;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    margin-bottom: 4px;
  }
  .rp-stat-value {
    font-size: 1.4rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .rp-val-green { color: #22c55e; }
  .rp-val-amber { color: #f5a623; }

  /* ---- Grouping pane ---- */
  .rp-group-pane {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .rp-gp-accent {
    height: 6px;
    background: #22c55e;
  }
  .rp-gp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px 4px;
  }
  .rp-gp-header #rp-gp-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #60a5fa;
    font-weight: 600;
  }
  .rp-gp-count {
    font-size: 0.72rem;
    color: #8b919a;
    font-weight: 500;
  }
  .rp-gp-body {
    padding: 8px 0;
  }

  /* ---- Bar rows ---- */
  .rp-bar-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 7px 20px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .rp-bar-row:hover {
    background: rgba(96,165,250,0.06);
  }
  .rp-bar-label {
    flex: 0 0 140px;
    font-size: 0.82rem;
    color: #e4e6eb;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: "JetBrains Mono", monospace;
  }
  .rp-bar-track {
    flex: 1;
    height: 18px;
    background: rgba(255,255,255,0.04);
    border-radius: 9px;
    overflow: hidden;
  }
  .rp-bar-fill {
    height: 100%;
    background: #60a5fa;
    border-radius: 9px;
    transition: width 0.3s;
    min-width: 2px;
  }
  .rp-bar-fill.rp-bar-amber {
    background: #f5a623;
  }
  .rp-bar-count {
    flex: 0 0 50px;
    text-align: right;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.82rem;
    color: #8b919a;
  }

  /* ---- States ---- */
  .rp-loading {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
  }
  .rp-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 30px 0;
  }
  .rp-error {
    color: #f5a623;
    background: rgba(245,166,35,0.10);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 0.82rem;
    margin: 0 20px;
  }

  /* ---- Responsive ---- */
  @media (max-width: 600px) {
    .rp-filter-row { grid-template-columns: 1fr; }
    .rp-stats { grid-template-columns: repeat(2, 1fr); }
    .rp-bar-label { flex: 0 0 80px; font-size: 0.72rem; }
    .rp-fp-fields { flex-direction: column; }
  }
`;
document.head.appendChild(rpStyles);
