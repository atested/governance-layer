/**
 * Approvals window — child window (depth 1).
 * Spec v2 section 7.2.
 *
 * Manage operator approvals: view active list, approve new operations,
 * revoke existing approvals with confirmation dialog.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import '../components/data-table.js';
import '../components/pill.js';
import '../components/confirmation-dialog.js';
import '../components/loading-indicator.js';

const COLUMNS = [
  { key: 'artifact_identity', label: 'Operation', sortable: false },
  { key: 'approving_operator', label: 'Operator', sortable: false, width: '120px' },
  { key: 'governed_family', label: 'Scope', sortable: false, width: '120px' },
  { key: 'timestamp_utc', label: 'Approved', sortable: false, width: '160px' },
  { key: '_action', label: 'Action', sortable: false, width: '100px' },
];

/**
 * Open the Approvals window.
 * @param {HTMLElement|null} trigger
 * @param {string} [prefillOperation] - Operation to pre-fill from Record Detail atomic nav
 */
export function openApprovalsWindow(trigger, prefillOperation) {
  const content = _buildContent();
  const result = _openAsChild('Approvals', trigger, content);
  if (!result) return;

  const state = { el: content, approvals: [] };
  _wireControls(state);
  _loadData(state);

  // Pre-fill from Record Detail atomic navigation
  if (prefillOperation) {
    const input = content.querySelector('#ap-operation');
    if (input) input.value = prefillOperation;
  }
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'ap-content';
  el.innerHTML = `
    <div class="ap-header">
      <span class="ap-eyebrow">Operations</span>
      <span class="ap-heading">Approvals</span>
    </div>

    <div class="ap-form-card">
      <h3 class="ap-section-title">Approve Operation</h3>
      <div class="ap-form">
        <label class="ap-field">
          Operation
          <input type="text" class="ap-input" id="ap-operation"
                 placeholder="e.g. EnterPlanMode, /path/to/file.py, or SHA-256 hash">
        </label>
        <label class="ap-field">
          Operator
          <input type="text" class="ap-input" id="ap-operator" placeholder="your name">
        </label>
      </div>
      <div class="ap-form-actions">
        <atd-pill variant="primary" id="ap-approve-btn">Approve</atd-pill>
      </div>
      <div id="ap-form-result"></div>
    </div>

    <div class="ap-list-section">
      <h3 class="ap-section-title">Active Approvals</h3>
      <div id="ap-table-wrap">
        <atd-loading-indicator label="Loading approvals"></atd-loading-indicator>
      </div>
    </div>
  `;
  return el;
}

function _wireControls(state) {
  state.el.querySelector('#ap-approve-btn').addEventListener('click', () => _handleApprove(state));
}

async function _handleApprove(state) {
  const operation = state.el.querySelector('#ap-operation').value.trim();
  const operator = state.el.querySelector('#ap-operator').value.trim() || 'dashboard_operator';
  const resultEl = state.el.querySelector('#ap-form-result');

  if (!operation) {
    _showFormResult(resultEl, 'Please enter an operation to approve.', 'error');
    return;
  }

  const res = await api.postApprovalAdd({ artifact_identity: operation, operator });
  if (res.ok) {
    _showFormResult(resultEl, `Approved: ${operation}`, 'success');
    state.el.querySelector('#ap-operation').value = '';
    _loadData(state);
  } else {
    _showFormResult(resultEl, res.error, 'error');
  }
}

function _showFormResult(el, msg, type) {
  el.className = type === 'success' ? 'ap-result-success' : 'ap-result-error';
  el.textContent = msg;
  setTimeout(() => { el.textContent = ''; el.className = ''; }, 5000);
}

async function _loadData(state) {
  const wrap = state.el.querySelector('#ap-table-wrap');
  wrap.innerHTML = '<atd-loading-indicator label="Loading approvals"></atd-loading-indicator>';

  const res = await api.getApprovals();
  if (!res.ok) {
    wrap.innerHTML = `<div class="ap-error">${_esc(res.error)}</div>`;
    return;
  }

  state.approvals = res.data.active_approvals || [];
  _renderTable(state);
}

function _renderTable(state) {
  const wrap = state.el.querySelector('#ap-table-wrap');
  wrap.innerHTML = '';

  if (!state.approvals.length) {
    wrap.innerHTML = '<p class="ap-empty">No active approvals. Use the form above to approve an operation.</p>';
    return;
  }

  const table = document.createElement('atd-data-table');
  table.setAttribute('columns', JSON.stringify(COLUMNS));
  table.setAttribute('page-size', '50');
  table.setAttribute('sortable', 'false');

  table.data = state.approvals.map(a => ({
    ...a,
    _action: 'revoke',
  }));

  table.cellRenderer = (row, col) => {
    if (col.key === 'artifact_identity') {
      const full = row.artifact_identity || '--';
      const truncated = full.length > 50 ? full.substring(0, 50) + '...' : full;
      return `<span title="${_esc(full)}" style="font-family:var(--font-mono,monospace);font-size:0.82rem">${_esc(truncated)}</span>`;
    }
    if (col.key === 'timestamp_utc') {
      return _esc(_formatTime(row.timestamp_utc));
    }
    if (col.key === '_action') {
      return '<atd-pill variant="danger" class="revoke-btn">Revoke</atd-pill>';
    }
    return null;
  };

  table.totalCount = state.approvals.length;

  // Handle revoke clicks
  table.addEventListener('click', (e) => {
    const pill = e.target.closest('atd-pill.revoke-btn');
    if (!pill) return;
    // Find which row
    const tr = pill.closest('tr');
    if (!tr) return;
    const idx = parseInt(tr.dataset.index, 10);
    const approval = state.approvals[idx];
    if (!approval) return;
    _confirmRevoke(state, approval);
  });

  wrap.appendChild(table);
}

function _confirmRevoke(state, approval) {
  const dialog = document.createElement('atd-confirmation-dialog');
  dialog.setAttribute('title', 'Revoke Approval');
  dialog.setAttribute('message', `Revoke approval for "${approval.artifact_identity}"? This will remove the active approval and record a revocation event.`);
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
      const resultEl = state.el.querySelector('#ap-form-result');
      _showFormResult(resultEl, `Revoke failed: ${res.error}`, 'error');
    }
  });

  document.body.appendChild(dialog);
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
const apStyles = document.createElement('style');
apStyles.textContent = `
  .ap-content { font-family: "Inter", system-ui, sans-serif; }
  .ap-header { margin-bottom: 16px; }
  .ap-eyebrow {
    display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #8b919a; margin-bottom: 4px;
  }
  .ap-heading { font-size: 1.25rem; font-weight: 600; color: #e4e6eb; }
  .ap-section-title {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #5b8af5; margin: 0 0 12px; font-weight: 600;
  }
  .ap-form-card {
    background: #22262e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 16px 20px; margin-bottom: 24px;
  }
  .ap-form {
    display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px;
  }
  .ap-field {
    display: flex; flex-direction: column; font-size: 0.72rem;
    color: #8b919a; text-transform: uppercase; letter-spacing: 0.04em; gap: 4px;
  }
  .ap-input {
    background: #1a1d23; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px; color: #e4e6eb; font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem; padding: 6px 10px;
  }
  .ap-input:focus { outline: 2px solid #5b8af5; outline-offset: 1px; }
  .ap-form-actions { margin-bottom: 8px; }
  .ap-result-success { color: #4ade80; font-size: 0.82rem; margin-top: 8px; }
  .ap-result-error { color: #f59e42; font-size: 0.82rem; margin-top: 8px; }
  .ap-list-section { margin-bottom: 24px; }
  .ap-loading, .ap-empty {
    color: #8b919a; font-size: 0.82rem; text-align: center;
    padding: 24px 0; margin: 0; font-style: italic;
  }
  .ap-error {
    color: #f59e42; background: rgba(245,158,66,0.10);
    padding: 12px 16px; border-radius: 8px; font-size: 0.82rem;
  }
  @media (max-width: 600px) {
    .ap-form { grid-template-columns: 1fr; }
  }
`;
document.head.appendChild(apStyles);
