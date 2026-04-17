/**
 * Record Detail — grandchild window (depth 2).
 * Always opens from Activity or Audit. Spec v2 section 8.
 *
 * Displays a single governance record with type-specific context card,
 * chain record JSON, and optional sidecar record JSON.
 *
 * DENY records include "Approve this operation" button that triggers
 * atomic navigation: close all windows, open Approvals with pre-fill.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import '../components/kv-list.js';
import '../components/code-block.js';
import '../components/decision-tag.js';
import '../components/tier-badge.js';
import '../components/pill.js';
import '../components/loading-indicator.js';

/**
 * Open Record Detail as a grandchild window.
 * @param {string} recordId - request_id, event_id, or record_hash
 * @param {HTMLElement} trigger - element for focus return
 */
export async function openRecordDetail(recordId, trigger) {
  const shortId = (recordId || '').substring(0, 8);
  const result = modalManager.open({
    title: `Record ${shortId}`,
    trigger,
    content: _loadingEl(),
  });
  if (!result) return;

  const res = await api.getAuditRecord(recordId);
  const container = result.frame.querySelector('.rd-loading')?.parentElement || result.frame;

  if (!res.ok) {
    _replaceContent(result.frame, _errorEl(res.error));
    return;
  }

  if (!res.data.found) {
    _replaceContent(result.frame, _errorEl('Record not found'));
    return;
  }

  _replaceContent(result.frame, _buildContent(res.data, recordId));
}

// ---------- Content builders ----------

function _buildContent(data, recordId) {
  const el = document.createElement('div');
  el.className = 'rd-content';

  const chain = data.chain_record || {};
  const sidecar = data.sidecar_record;
  const eventType = chain.event_type || sidecar?.event_type || '';
  const decision = chain.policy_decision || sidecar?.policy_decision || '';

  // Record header
  const header = document.createElement('div');
  header.className = 'rd-header';
  header.innerHTML = `
    <span class="rd-header-label">Record ID</span>
    <span class="rd-header-id">${_esc(recordId)}</span>
  `;
  el.appendChild(header);

  // Context card (type-specific)
  el.appendChild(_buildContextCard(chain, sidecar, eventType, decision));

  // DENY: "Approve this operation" button
  if (decision === 'DENY') {
    const approveSection = document.createElement('div');
    approveSection.className = 'rd-approve-section';
    const btn = document.createElement('atd-pill');
    btn.setAttribute('variant', 'primary');
    btn.textContent = 'Approve this operation';
    btn.addEventListener('click', () => {
      const operation = sidecar?.target || chain.target || sidecar?.tool_name || chain.tool || '';
      modalManager.closeAll();
      // Defer to next tick so closeAll finishes before opening Approvals
      setTimeout(() => {
        import('./approvals.js').then(mod => {
          mod.openApprovalsWindow(null, operation);
        });
      }, 0);
    });
    approveSection.appendChild(btn);
    el.appendChild(approveSection);
  }

  // Chain record JSON
  const chainSection = document.createElement('div');
  chainSection.className = 'rd-json-section';
  chainSection.innerHTML = '<h3 class="rd-section-title">Chain Record</h3>';
  const chainBlock = document.createElement('atd-code-block');
  chainBlock.setAttribute('language', 'json');
  chainBlock.content = chain;
  chainSection.appendChild(chainBlock);
  el.appendChild(chainSection);

  // Sidecar record JSON (conditional)
  if (sidecar) {
    const sidecarSection = document.createElement('div');
    sidecarSection.className = 'rd-json-section';
    sidecarSection.innerHTML = '<h3 class="rd-section-title">Sidecar Record</h3>';
    const sidecarBlock = document.createElement('atd-code-block');
    sidecarBlock.setAttribute('language', 'json');
    sidecarBlock.content = sidecar;
    sidecarSection.appendChild(sidecarBlock);
    el.appendChild(sidecarSection);
  }

  return el;
}

function _buildContextCard(chain, sidecar, eventType, decision) {
  const card = document.createElement('div');
  card.className = 'rd-context-card';

  const rec = sidecar || chain;

  // Determine record type and build appropriate kv-list
  if (_isMediatedDecision(eventType)) {
    card.innerHTML = '<h3 class="rd-section-title">Mediated Decision</h3>';
    const kv = document.createElement('atd-kv-list');
    const items = [
      { key: 'Decision', value: decision || '--' },
      { key: 'Tool', value: rec.tool_name || rec.tool || '--', variant: 'code' },
      { key: 'Target', value: rec.target || '--', variant: 'code' },
      { key: 'User', value: rec.user_identity || '--' },
      { key: 'Confidence Tier', value: rec.classification?.tier != null ? `Tier ${rec.classification.tier}` : '--' },
      { key: 'Action Type', value: rec.action_type || rec.event_type || '--' },
      { key: 'Scope', value: rec.governed_family || rec.scope || '--' },
      { key: 'Matched Rule', value: rec.matched_rule || '--' },
    ];
    if (decision === 'DENY') {
      items.push({ key: 'Denial Reason', value: rec.denial_reason || rec.deny_reason || 'Policy denied', variant: 'danger' });
    }
    items.push({ key: 'Verification State', value: rec.verification_state || '--', variant: rec.verification_state === 'verified' ? 'success' : undefined });
    items.push({ key: 'Recorded', value: _formatTimestamp(rec.timestamp_utc || chain.timestamp_utc) });
    kv.items = items;

    // Insert decision-tag and tier-badge as HTML in kv items
    card.appendChild(kv);

  } else if (_isBoundaryObservation(eventType)) {
    const banner = document.createElement('div');
    banner.className = 'rd-warning-banner';
    banner.textContent = 'This operation was observed outside the mediation boundary and was not policy-evaluated.';
    card.appendChild(banner);

    const kv = document.createElement('atd-kv-list');
    kv.items = [
      { key: 'Operation', value: rec.operation_type || rec.event_type || '--' },
      { key: 'Target', value: rec.target || '--', variant: 'code' },
      { key: 'Source', value: rec.source || '--' },
      { key: 'Recorded', value: _formatTimestamp(rec.timestamp_utc || chain.timestamp_utc) },
    ];
    card.appendChild(kv);

  } else if (_isApproval(eventType)) {
    card.innerHTML = `<h3 class="rd-section-title">${eventType.includes('revoc') ? 'Operation Revocation' : 'Operation Approval'}</h3>`;
    const kv = document.createElement('atd-kv-list');
    kv.items = [
      { key: 'Operation', value: rec.artifact_identity || rec.operation || '--', variant: 'code' },
      { key: 'Operator', value: rec.operator_identity || rec.approving_operator || rec.operator || '--' },
      { key: 'Scope', value: rec.governed_family || rec.scope || '--' },
      { key: 'Context', value: rec.deployment_context || rec.context || '--' },
      { key: 'Recorded', value: _formatTimestamp(rec.timestamp_utc || chain.timestamp_utc) },
    ];
    card.appendChild(kv);

  } else if (_isVerificationChange(eventType)) {
    card.innerHTML = '<h3 class="rd-section-title">Verification Change</h3>';
    const kv = document.createElement('atd-kv-list');
    kv.items = [
      { key: 'Surface', value: rec.governed_family || '--' },
      { key: 'Previous State', value: rec.previous_state || '--' },
      { key: 'New State', value: rec.new_state || rec.current_state || '--' },
      { key: 'Recorded', value: _formatTimestamp(rec.timestamp_utc || chain.timestamp_utc) },
    ];
    card.appendChild(kv);

  } else {
    // Generic fallback
    card.innerHTML = `<h3 class="rd-section-title">${_esc(eventType || 'Record')}</h3>`;
    const kv = document.createElement('atd-kv-list');
    const items = Object.entries(rec).slice(0, 12).map(([k, v]) => ({
      key: k,
      value: typeof v === 'object' ? JSON.stringify(v) : String(v ?? '--'),
    }));
    kv.items = items;
    card.appendChild(kv);
  }

  return card;
}

// ---------- Type detection helpers ----------

function _isMediatedDecision(type) {
  return /mediat|decision|action|invocation/i.test(type);
}

function _isBoundaryObservation(type) {
  return /observ|boundar|ungoverned/i.test(type);
}

function _isApproval(type) {
  return /approv|revoc/i.test(type);
}

function _isVerificationChange(type) {
  return /verif|certif|drift/i.test(type);
}

// ---------- Utility ----------

function _loadingEl() {
  const el = document.createElement('atd-loading-indicator');
  el.className = 'rd-loading';
  el.setAttribute('label', 'Loading record');
  return el;
}

function _errorEl(msg) {
  const el = document.createElement('div');
  el.className = 'rd-error';
  el.textContent = msg || 'An error occurred';
  return el;
}

function _replaceContent(frame, newContent) {
  // Clear slotted content inside the frame
  const slot = frame.querySelector('.rd-loading') || frame.querySelector('.rd-content') || frame.querySelector('.rd-error');
  if (slot) {
    slot.replaceWith(newContent);
  } else {
    // Fallback: append
    frame.appendChild(newContent);
  }
}

function _formatTimestamp(iso) {
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
const rdStyles = document.createElement('style');
rdStyles.textContent = `
  .rd-loading, .rd-error {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
  }
  .rd-error { color: #f59e42; }
  .rd-content {
    font-family: "Inter", system-ui, sans-serif;
  }
  .rd-header {
    margin-bottom: 16px;
  }
  .rd-header-label {
    display: block;
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    margin-bottom: 4px;
  }
  .rd-header-id {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.82rem;
    color: #e4e6eb;
    word-break: break-all;
  }
  .rd-context-card {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 20px;
  }
  .rd-section-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #5b8af5;
    margin: 0 0 12px;
    font-weight: 600;
  }
  .rd-warning-banner {
    background: rgba(245, 158, 66, 0.10);
    color: #f59e42;
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 0.82rem;
    margin-bottom: 12px;
  }
  .rd-approve-section {
    margin-bottom: 20px;
  }
  .rd-json-section {
    margin-bottom: 20px;
  }
`;
document.head.appendChild(rdStyles);
