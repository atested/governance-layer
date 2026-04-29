/**
 * Approvals window — child window (depth 1).
 * D-038 redesign: stat cards, approve pane with improved copy,
 * active approvals table with staleness detection, bulk revocation,
 * filter toggles, export.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { installWindowTooltips, setTooltip, setTooltips } from '../tooltip-utils.js';
import { downloadExport } from '../export-utils.js';
import '../components/pill.js';
import '../components/confirmation-dialog.js';
import '../components/loading-indicator.js';

/**
 * Open the Approvals window.
 * @param {HTMLElement|null} trigger
 * @param {string} [prefillOperation] - Operation to pre-fill from Record Detail
 */
export function openApprovalsWindow(trigger, prefillOperation) {
  const content = document.createElement('div');
  content.className = 'ap-root';

  const result = _openAsChild('Approvals', 'Manage your exceptions to Atested policy rules', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    approvals: [],
    staleCount: 0,
    stalenessDays: 30,
    latestApproval: '',
    filter: 'all', // 'all', 'active', 'stale'
    prefillOperation: prefillOperation || '',
  };

  _buildUI(state);
  installWindowTooltips(content);
  _applyStaticTooltips(state);
  _loadData(state);
}

// ---------- Build UI ----------

function _buildUI(state) {
  const el = state.el;
  el.innerHTML = `
    <!-- Stat cards -->
    <div class="ap-stats">
      <div class="ap-stat-card">
        <span class="ap-stat-label">Active Approvals</span>
        <span class="ap-stat-value" id="ap-stat-active">0</span>
      </div>
      <div class="ap-stat-card" id="ap-stat-stale-card">
        <span class="ap-stat-label">Recommended for Revocation</span>
        <span class="ap-stat-value" id="ap-stat-stale">0</span>
      </div>
      <div class="ap-stat-card">
        <span class="ap-stat-label">Last Approved</span>
        <span class="ap-stat-value ap-stat-date" id="ap-stat-latest">\u2014</span>
      </div>
    </div>

    <!-- Approve operation pane -->
    <div class="ap-pane">
      <div class="ap-pane-accent ap-accent-amber"></div>
      <div class="ap-pane-header">Approve operation</div>
      <div class="ap-pane-body">
        <p class="ap-pane-copy">Approving an operation means you are authorizing an override of an Atested rule. The easiest way to do this is from the Activity screen \u2014 find the denied operation and approve it directly from the record detail.</p>
        <div class="ap-approve-form">
          <input type="text" class="ap-input ap-approve-input" id="ap-operation"
                 placeholder="Operation name, file path, or SHA-256 hash">
          <button class="ap-btn ap-btn-primary" id="ap-approve-btn">Approve</button>
        </div>
        <div id="ap-form-result"></div>
      </div>
    </div>

    <!-- Revocation guidance pane -->
    <div class="ap-pane ap-revocation-guidance">
      <div class="ap-pane-accent ap-accent-purple"></div>
      <div class="ap-pane-header">Revocation guidance</div>
      <div class="ap-pane-body">
        <p class="ap-pane-copy">Approvals should be reviewed periodically. A stale approval keeps an exception open after the operational reason may have expired, which widens the path around policy controls. Use the <strong>Recommended for revocation</strong> filter below to review the stale set Atested has already flagged for you.</p>
        <div class="ap-guidance-grid">
          <div class="ap-guidance-item">
            <span class="ap-guidance-label">Governance risk</span>
            <span class="ap-guidance-copy">Unused approvals can become standing permissions no one intended to keep.</span>
          </div>
          <div class="ap-guidance-item">
            <span class="ap-guidance-label">Chain evidence</span>
            <span class="ap-guidance-copy">Every revocation is recorded as a governance-chain event for later review.</span>
          </div>
          <div class="ap-guidance-item">
            <span class="ap-guidance-label">After revocation</span>
            <span class="ap-guidance-copy">The operation returns to denied status until an operator approves it again.</span>
          </div>
        </div>
        <button class="ap-btn ap-btn-muted ap-guidance-action" id="ap-guidance-filter">Open recommended filter</button>
      </div>
    </div>

    <!-- Active approvals pane -->
    <div class="ap-pane">
      <div class="ap-pane-accent ap-accent-green"></div>
      <div class="ap-pane-header-row">
        <span class="ap-pane-header">Active approvals</span>
        <span class="ap-pane-count" id="ap-count">0</span>
      </div>
      <div class="ap-pane-body">
        <div class="ap-filter-bar" id="ap-filter-bar">
          <span class="ap-filter-label">Show:</span>
          <button class="ap-filter-btn ap-filter-active" data-filter="all">All</button>
          <button class="ap-filter-btn" data-filter="active">Active</button>
          <button class="ap-filter-btn" data-filter="stale">Recommended for revocation</button>
        </div>
        <div id="ap-table-wrap">
          <div class="ap-loading">Loading approvals...</div>
        </div>
        <div id="ap-bulk-section"></div>
      </div>
    </div>

    <!-- Footer -->
    <div class="ap-footer">
      <div class="ap-export-control">
        <select class="ap-select ap-export-format" id="ap-export-format" aria-label="Export format">
          <option value="json">JSON</option>
          <option value="csv">CSV</option>
          <option value="excel">Excel</option>
        </select>
        <button class="ap-btn ap-btn-export" id="ap-export">Export</button>
      </div>
    </div>
  `;

  // Pre-fill
  if (state.prefillOperation) {
    el.querySelector('#ap-operation').value = state.prefillOperation;
  }

  _wireControls(state);
}

function _applyStaticTooltips(state) {
  setTooltips(state.el, [
    ['#ap-stat-active', 'Currently active policy exceptions.'],
    ['#ap-stat-stale', 'Approvals that have not been used recently and should be reviewed.'],
    ['#ap-stat-latest', 'Most recent approval recorded in the chain.'],
    ['#ap-operation', 'Enter an action name, path, opaque artifact hash, or operation identity to approve.'],
    ['#ap-approve-btn', 'Create an approval event in the chain.'],
    ['#ap-export-format', 'Choose JSON, CSV, or Excel-compatible export format.'],
    ['#ap-export', 'Export the active approvals table in the selected format.'],
    ['.ap-revocation-guidance', 'Explains when and why to revoke approvals.'],
  ]);
  state.el.querySelectorAll('.ap-filter-btn').forEach(btn => {
    const label = btn.textContent.trim();
    setTooltip(btn, `Show ${label.toLowerCase()} approvals.`);
  });
}

// ---------- Wire controls ----------

function _wireControls(state) {
  const el = state.el;

  // Approve button
  el.querySelector('#ap-approve-btn').addEventListener('click', () => _handleApprove(state));

  // Enter key on input
  el.querySelector('#ap-operation').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') _handleApprove(state);
  });

  // Filter toggles
  el.querySelector('#ap-filter-bar').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-filter]');
    if (!btn) return;
    el.querySelectorAll('.ap-filter-btn').forEach(b => b.classList.remove('ap-filter-active'));
    btn.classList.add('ap-filter-active');
    state.filter = btn.dataset.filter;
    _renderTable(state);
  });

  el.querySelector('#ap-guidance-filter').addEventListener('click', () => {
    el.querySelector('.ap-filter-btn[data-filter="stale"]')?.click();
  });

  // Export
  el.querySelector('#ap-export').addEventListener('click', () => _exportApprovals(state));
}

// ---------- Data ----------

async function _loadData(state) {
  const wrap = state.el.querySelector('#ap-table-wrap');
  wrap.innerHTML = '<div class="ap-loading">Loading approvals...</div>';

  const res = await api.getApprovals();
  if (!res.ok) {
    wrap.innerHTML = `<div class="ap-error">${_esc(res.error)}</div>`;
    return;
  }

  state.approvals = res.data.active_approvals || [];
  state.staleCount = res.data.stale_count || 0;
  state.stalenessDays = res.data.staleness_days || 30;
  state.latestApproval = res.data.latest_approval_utc || '';

  _updateStats(state);
  _renderTable(state);
  _renderBulkSection(state);
}

function _updateStats(state) {
  const el = state.el;
  el.querySelector('#ap-stat-active').textContent = String(state.approvals.length);

  const staleEl = el.querySelector('#ap-stat-stale');
  staleEl.textContent = String(state.staleCount);

  // Color the stale card
  const staleCard = el.querySelector('#ap-stat-stale-card');
  staleCard.className = 'ap-stat-card' + (state.staleCount > 0 ? ' ap-stat-amber' : ' ap-stat-green');
  staleEl.className = 'ap-stat-value' + (state.staleCount > 0 ? ' ap-val-amber' : ' ap-val-green');

  // Latest approval date
  el.querySelector('#ap-stat-latest').textContent = state.latestApproval
    ? _formatHumanDate(state.latestApproval)
    : '\u2014';

  // Count in header
  el.querySelector('#ap-count').textContent = String(state.approvals.length);
}

// ---------- Table ----------

function _renderTable(state) {
  const wrap = state.el.querySelector('#ap-table-wrap');
  wrap.innerHTML = '';

  let filtered = state.approvals;
  if (state.filter === 'active') {
    filtered = filtered.filter(a => !a.stale);
  } else if (state.filter === 'stale') {
    filtered = filtered.filter(a => a.stale);
  }

  if (!filtered.length) {
    const msg = state.filter === 'stale'
      ? 'No approvals recommended for revocation.'
      : state.filter === 'active'
        ? 'No active approvals in this view.'
        : 'No active approvals. Use the form above to approve an operation.';
    wrap.innerHTML = `<div class="ap-empty">${_esc(msg)}</div>`;
    return;
  }

  const table = document.createElement('table');
  table.className = 'ap-table';

  // Header
  const thead = document.createElement('thead');
  thead.innerHTML = `
    <tr>
      <th>Operation</th>
      <th style="width:110px">Approved</th>
      <th style="width:110px">Last used</th>
      <th style="width:60px">Uses</th>
      <th style="width:140px">Status</th>
      <th style="width:80px">Action</th>
    </tr>
  `;
  thead.querySelectorAll('th').forEach((th, idx) => {
    setTooltip(th, [
      'Approved operation, path, or artifact identity.',
      'When the approval was recorded.',
      'When this approval was last used.',
      'How many times this approval has been used.',
      'Whether the approval is active or recommended for revocation.',
      'Revoke writes a revocation event to the chain.',
    ][idx]);
  });
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const approval of filtered) {
    const tr = document.createElement('tr');
    tr.className = 'ap-row' + (approval.stale ? ' ap-row-stale' : '');

    const operation = approval.artifact_identity || '';
    const truncOp = operation.length > 50 ? operation.substring(0, 47) + '\u2026' : operation;
    const approvedDate = _formatHumanDate(approval.timestamp_utc);
    const ageDays = approval.age_days || 0;

    // Status
    let statusHtml;
    if (approval.stale) {
      statusHtml = '<span class="ap-status-stale">[Recommend revoking]</span>';
    } else {
      statusHtml = '<span class="ap-status-active">[Active]</span>';
    }

    setTooltip(
      tr,
      approval.stale
        ? `This approval has not been used in ${ageDays} days. Keeping unused approvals active increases your attack surface.`
        : `Approval for ${operation || 'this operation'} is active.`
    );

    tr.innerHTML = `
      <td><span class="ap-cell-op" data-tooltip="${_escAttr(operation)}">${_esc(truncOp)}</span></td>
      <td>${_esc(approvedDate)}</td>
      <td><span class="ap-cell-muted">\u2014</span></td>
      <td><span class="ap-cell-muted">\u2014</span></td>
      <td>${statusHtml}</td>
      <td><button class="ap-revoke-btn" data-identity="${_escAttr(operation)}">Revoke</button></td>
    `;

    // Revoke click
    tr.querySelector('.ap-revoke-btn').addEventListener('click', (e) => {
      e.stopPropagation();
      _confirmRevoke(state, approval);
    });
    setTooltip(tr.querySelector('.ap-revoke-btn'), 'Revocation is recorded in the chain.');

    tbody.appendChild(tr);
  }

  table.appendChild(tbody);
  wrap.appendChild(table);
}

// ---------- Bulk revocation ----------

function _renderBulkSection(state) {
  const section = state.el.querySelector('#ap-bulk-section');
  section.innerHTML = '';

  if (state.staleCount === 0) return;

  const div = document.createElement('div');
  div.className = 'ap-bulk';
  div.innerHTML = `
    <div class="ap-bulk-content">
      <span class="ap-bulk-text">${state.staleCount} approval${state.staleCount === 1 ? ' has' : 's have'} not been used in ${state.stalenessDays} or more days.</span>
      <p class="ap-bulk-explain">Approvals that haven\u2019t been used in 30 days are open exceptions to your rules with no current purpose. Revoking them reduces your exposure without affecting your operations. You can always easily re-approve if you need to.</p>
    </div>
    <button class="ap-btn ap-btn-bulk" id="ap-bulk-revoke">Revoke all recommended</button>
  `;

  div.querySelector('#ap-bulk-revoke').addEventListener('click', () => _confirmBulkRevoke(state));
  section.appendChild(div);
}

// ---------- Revocation ----------

function _confirmRevoke(state, approval) {
  const dialog = document.createElement('atd-confirmation-dialog');
  dialog.setAttribute('title', 'Revoke Approval');
  dialog.setAttribute('message', `Revoke approval for "${approval.artifact_identity}"? This will remove the active approval and record a revocation event in the governance chain.`);
  dialog.setAttribute('confirm-label', 'Revoke');
  dialog.setAttribute('cancel-label', 'Cancel');
  dialog.setAttribute('variant', 'danger');

  dialog.addEventListener('dialog:confirm', async () => {
    const res = await api.postApprovalRevoke({
      artifact_identity: approval.artifact_identity,
      operator: approval.approving_operator || 'dashboard_operator',
    });
    if (res.ok) {
      _loadData(state);
    } else {
      _showFormResult(state.el.querySelector('#ap-form-result'), `Revoke failed: ${res.error}`, 'error');
    }
  });

  document.body.appendChild(dialog);
}

function _confirmBulkRevoke(state) {
  const stale = state.approvals.filter(a => a.stale);
  const dialog = document.createElement('atd-confirmation-dialog');
  dialog.setAttribute('title', 'Revoke All Recommended');
  dialog.setAttribute('message', `Revoke ${stale.length} approval${stale.length === 1 ? '' : 's'} that have not been used in ${state.stalenessDays}+ days? Each revocation will be recorded as a separate chain event.`);
  dialog.setAttribute('confirm-label', `Revoke ${stale.length}`);
  dialog.setAttribute('cancel-label', 'Cancel');
  dialog.setAttribute('variant', 'danger');

  dialog.addEventListener('dialog:confirm', async () => {
    for (const approval of stale) {
      await api.postApprovalRevoke({
        artifact_identity: approval.artifact_identity,
        operator: approval.approving_operator || 'dashboard_operator',
      });
    }
    _loadData(state);
  });

  document.body.appendChild(dialog);
}

// ---------- Approve ----------

async function _handleApprove(state) {
  const input = state.el.querySelector('#ap-operation');
  const operation = input.value.trim();
  const resultEl = state.el.querySelector('#ap-form-result');

  if (!operation) {
    _showFormResult(resultEl, 'Please enter an operation to approve.', 'error');
    return;
  }

  const res = await api.postApprovalAdd({
    artifact_identity: operation,
    operator: 'dashboard_operator',
  });
  if (res.ok) {
    _showFormResult(resultEl, `Approved: ${operation}`, 'success');
    input.value = '';
    _loadData(state);
  } else {
    _showFormResult(resultEl, res.error, 'error');
  }
}

function _showFormResult(el, msg, type) {
  if (!el) return;
  el.className = type === 'success' ? 'ap-result-success' : 'ap-result-error';
  el.textContent = msg;
  setTimeout(() => { el.textContent = ''; el.className = ''; }, 5000);
}

// ---------- Export ----------

function _exportApprovals(state) {
  if (!state.approvals.length) return;

  const date = new Date().toISOString().slice(0, 10);
  const columns = [
    { key: 'operation', label: 'Operation' },
    { key: 'approved', label: 'Approved' },
    { key: 'status', label: 'Status' },
    { key: 'age_days', label: 'Age (days)' },
    { key: 'operator', label: 'Operator' },
  ];
  const rows = state.approvals.map(a => ({
    operation: a.artifact_identity || '',
    approved: a.timestamp_utc || '',
    status: a.stale ? 'Recommended for revocation' : 'Active',
    age_days: String(a.age_days || 0),
    operator: a.approving_operator || '',
  }));
  const format = state.el.querySelector('#ap-export-format')?.value || 'json';
  downloadExport(format, `atested-approvals-${date}`, columns, rows, {
    sheetName: 'Approvals Export',
    jsonData: () => ({
      export_timestamp: new Date().toISOString(),
      filter: state.filter,
      approvals: state.approvals,
    }),
  });
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
    return `${mon} ${day}, ${hh}:${mm}`;
  } catch { return isoStr; }
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

const apStyles = document.createElement('style');
apStyles.textContent = `
  .ap-root {
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }

  /* ---- Stat cards ---- */
  .ap-stats {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }
  .ap-stat-card {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    padding: 14px 16px;
    text-align: center;
  }
  .ap-stat-green { border-color: rgba(63,185,80,0.25); }
  .ap-stat-amber { border-color: rgba(210,153,34,0.25); }
  .ap-stat-label {
    display: block;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    margin-bottom: 4px;
    font-weight: 500;
  }
  .ap-stat-value {
    font-size: 1.35rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .ap-stat-date {
    font-size: 1rem;
    font-family: "Inter", system-ui, sans-serif;
  }
  .ap-val-green { color: #3fb950; }
  .ap-val-amber { color: #d29922; }

  /* ---- Pane container ---- */
  .ap-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .ap-pane-accent {
    height: 6px;
  }
  .ap-accent-amber { background: #d29922; }
  .ap-accent-green { background: #3fb950; }
  .ap-accent-purple { background: #d2a8ff; }
  .ap-pane-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
    padding: 12px 20px 4px;
  }
  .ap-pane-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px 4px;
  }
  .ap-pane-header-row .ap-pane-header {
    padding: 0;
  }
  .ap-pane-count {
    font-size: 0.82rem;
    font-weight: 600;
    color: #8b919a;
    font-family: "JetBrains Mono", monospace;
  }
  .ap-pane-body {
    padding: 8px 20px 16px;
  }
  .ap-pane-copy {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.5;
    margin: 0 0 12px;
  }

  .ap-guidance-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }
  .ap-guidance-item {
    background: #1a1d23;
    border: 1px dashed rgba(210,168,255,0.22);
    border-radius: 2px;
    padding: 10px 12px;
  }
  .ap-guidance-label {
    display: block;
    font-size: 0.68rem;
    color: #d2a8ff;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: 600;
    margin-bottom: 5px;
  }
  .ap-guidance-copy {
    display: block;
    color: #8b919a;
    font-size: 0.78rem;
    line-height: 1.45;
  }

  /* ---- Approve form ---- */
  .ap-approve-form {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .ap-approve-input {
    flex: 1;
  }
  .ap-input {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 7px 12px;
    box-sizing: border-box;
  }
  .ap-select {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 7px 12px;
    box-sizing: border-box;
  }
  .ap-input:focus {
    outline: 2px solid #6699cc;
    outline-offset: 1px;
  }
  .ap-select:focus {
    outline: 2px solid #6699cc;
    outline-offset: 1px;
  }
  .ap-result-success { color: #3fb950; font-size: 0.82rem; margin-top: 8px; }
  .ap-result-error { color: #d29922; font-size: 0.82rem; margin-top: 8px; }

  /* ---- Buttons ---- */
  .ap-btn {
    border: none;
    border-radius: 2px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 7px 18px;
    cursor: pointer;
    transition: background 0.1s;
    white-space: nowrap;
  }
  .ap-btn-primary {
    background: #6699cc;
    color: #fff;
  }
  .ap-btn-primary:hover { background: #4f95ea; }
  .ap-btn-export {
    background: rgba(210,153,34,0.12);
    color: #d29922;
    border: 1px solid rgba(210,153,34,0.3);
  }
  .ap-btn-export:hover { background: rgba(210,153,34,0.2); }
  .ap-export-control {
    display: inline-flex;
    align-items: center;
    gap: 8px;
  }
  .ap-export-format {
    min-width: 90px;
  }
  .ap-btn-bulk {
    background: #3fb950;
    color: #fff;
  }
  .ap-btn-bulk:hover { background: #16a34a; }

  /* ---- Filter bar ---- */
  .ap-filter-bar {
    display: flex;
    align-items: center;
    gap: 6px;
    margin-bottom: 10px;
  }
  .ap-filter-label {
    font-size: 0.68rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 500;
    margin-right: 2px;
  }
  .ap-filter-btn {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #8b919a;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.72rem;
    padding: 3px 10px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .ap-filter-btn:hover { color: #e4e6eb; }
  .ap-filter-active {
    color: #6699cc;
    border-color: rgba(102,153,204,0.4);
    background: rgba(102,153,204,0.08);
  }

  /* ---- Table ---- */
  .ap-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .ap-table thead th {
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
  .ap-table tbody td {
    padding: 8px 10px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 300px;
  }
  .ap-row {
    transition: background 0.1s;
  }
  .ap-row:hover {
    background: rgba(102,153,204,0.06);
  }
  .ap-row-stale {
    background: rgba(210,153,34,0.04);
  }
  .ap-row-stale:hover {
    background: rgba(210,153,34,0.10);
  }

  /* Cell styles */
  .ap-cell-op {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.78rem;
    color: #e4e6eb;
  }
  .ap-cell-muted {
    color: #6b7280;
  }
  .ap-status-active {
    color: #3fb950;
    font-size: 0.72rem;
    font-weight: 600;
  }
  .ap-status-stale {
    color: #d29922;
    font-size: 0.72rem;
    font-weight: 600;
  }

  /* Revoke button */
  .ap-revoke-btn {
    background: none;
    border: 1px solid rgba(248,81,73,0.4);
    border-radius: 2px;
    color: #f85149;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.7rem;
    font-weight: 600;
    padding: 3px 10px;
    cursor: pointer;
    transition: all 0.1s;
  }
  .ap-revoke-btn:hover {
    background: rgba(248,81,73,0.1);
    border-color: rgba(248,81,73,0.6);
  }

  /* ---- Bulk section ---- */
  .ap-bulk {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 0 0;
    border-top: 1px solid rgba(255,255,255,0.06);
    margin-top: 12px;
  }
  .ap-bulk-content {
    flex: 1;
  }
  .ap-bulk-text {
    font-size: 0.78rem;
    color: #8b919a;
    display: block;
  }
  .ap-bulk-explain {
    font-size: 0.78rem;
    color: #6b7280;
    line-height: 1.5;
    margin: 6px 0 0;
  }

  /* ---- Footer ---- */
  .ap-footer {
    padding: 4px 0;
  }
  .ap-guidance-action {
    margin-top: 12px;
  }

  /* ---- Utility ---- */
  .ap-loading {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 24px 0;
    font-style: italic;
  }
  .ap-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 24px 0;
    font-style: italic;
  }
  .ap-error {
    color: #d29922;
    background: rgba(210,153,34,0.10);
    padding: 12px 16px;
    border-radius: 2px;
    font-size: 0.82rem;
  }

  /* ---- Responsive ---- */
  @media (max-width: 700px) {
    .ap-stats { grid-template-columns: 1fr; }
    .ap-approve-form { flex-direction: column; }
    .ap-guidance-grid { grid-template-columns: 1fr; }
    .ap-filter-bar { flex-wrap: wrap; }
  }
`;
document.head.appendChild(apStyles);
