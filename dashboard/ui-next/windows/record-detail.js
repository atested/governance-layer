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
import { installWindowTooltips, setTooltip } from '../tooltip-utils.js';
import '../components/kv-list.js';
import '../components/code-block.js';
import '../components/decision-tag.js';
import '../components/tier-badge.js';
import '../components/pill.js';
import '../components/loading-indicator.js';

let _currentDetail = null;
let _loadToken = 0;

/**
 * Open Record Detail as a grandchild window.
 * @param {string} recordId - request_id, event_id, or record_hash
 * @param {HTMLElement} trigger - element for focus return
 */
export async function openRecordDetail(recordId, trigger, opts = {}) {
  const token = ++_loadToken;
  const shortId = (recordId || '').substring(0, 8);
  let result = _currentDetail;

  if (result?.frame?.isConnected) {
    result.frame.setAttribute('title', `Record ${shortId}`);
    result.frame.setAttribute('subtitle', 'Decision detail from your chain');
    _replaceContent(result.frame, _loadingEl());
  } else {
    result = modalManager.open({
      title: `Record ${shortId}`,
      subtitle: 'Decision detail from your chain',
      trigger,
      content: _loadingEl(),
      allowParentInteraction: true,
    });
    if (!result) return;
    _currentDetail = result;
  }

  modalManager.setOnClose(() => {
    _currentDetail = null;
    if (typeof opts.onClose === 'function') opts.onClose(recordId);
  });

  const res = await api.getAuditRecord(recordId);
  if (token !== _loadToken || !result.frame.isConnected) return;

  if (!res.ok) {
    _replaceContent(result.frame, _errorEl(res.error));
    return;
  }

  if (!res.data.found) {
    _replaceContent(result.frame, _errorEl('Record not found'));
    return;
  }

  const resolvedId = _resolvedRecordId(res.data, recordId);
  result.frame.setAttribute('title', `Record ${resolvedId.substring(0, 8)}`);
  result.frame.setAttribute('subtitle', 'Decision detail from your chain');
  _replaceContent(result.frame, _buildContent(res.data, resolvedId));
}

// ---------- Content builders ----------

function _buildContent(data, recordId) {
  const el = document.createElement('div');
  el.className = 'rd-content';
  installWindowTooltips(el);

  const chain = data.chain_record || {};
  const sidecar = data.sidecar_record;
  const eventType = chain.event_type || sidecar?.event_type || '';
  const decision = chain.policy_decision || sidecar?.policy_decision || '';

  // Determine accent color based on decision
  let accentClass = 'rd-accent-muted';
  if (decision === 'ALLOW') accentClass = 'rd-accent-green';
  else if (decision === 'DENY') accentClass = 'rd-accent-red';

  // Top accent bar reflecting decision
  const topAccent = document.createElement('div');
  topAccent.className = `rd-top-accent ${accentClass}`;
  el.appendChild(topAccent);

  // Record ID subtitle (full ID in muted text below the window title)
  const subtitle = document.createElement('div');
  subtitle.className = 'rd-subtitle';
  subtitle.innerHTML = `<span class="rd-subtitle-id">${_esc(recordId)}</span>`;
  el.appendChild(subtitle);

  if ((chain.machine_role || '').toLowerCase() === 'remote' || chain.primary_import_timestamp_utc) {
    const machine = document.createElement('div');
    machine.className = 'rd-machine-banner';
    machine.innerHTML = `
      <div class="rd-machine-title">Remote machine record</div>
      <div class="rd-machine-grid">
        <span>Machine</span><code>${_esc(chain.machine_id || 'unknown')}</code>
        <span>Event time</span><code>${_esc(chain.event_timestamp_utc || chain.timestamp_utc || '\u2014')}</code>
        <span>Primary import</span><code>${_esc(chain.primary_import_timestamp_utc || '\u2014')}</code>
      </div>
    `;
    setTooltip(machine, 'This record originated on a remote machine and was accepted by the primary during sync.');
    el.appendChild(machine);
  }

  // Record pane — context card with kv fields
  const recordPane = document.createElement('div');
  recordPane.className = 'rd-pane';
  const recordAccent = document.createElement('div');
  recordAccent.className = `rd-pane-accent ${accentClass}`;
  recordPane.appendChild(recordAccent);
  const recordHeader = document.createElement('div');
  recordHeader.className = 'rd-pane-header';
  recordHeader.textContent = 'Record';
  setTooltip(recordHeader, 'Normalized evidence fields for this chain record.');
  recordPane.appendChild(recordHeader);
  const recordBody = document.createElement('div');
  recordBody.className = 'rd-pane-body';
  recordBody.appendChild(_buildContextCard(chain, sidecar, eventType, decision));
  recordPane.appendChild(recordBody);
  el.appendChild(recordPane);

  // DENY: "Approve this operation" button
  if (decision === 'DENY') {
    const approveSection = document.createElement('div');
    approveSection.className = 'rd-approve-section';
    const btn = document.createElement('atd-pill');
    btn.setAttribute('variant', 'primary');
    btn.textContent = 'Approve this operation';
    setTooltip(btn, 'Open Approvals with this denied operation prefilled.');
    btn.addEventListener('click', () => {
      // QS-062: prefer the operation_description so an approval is scoped
      // to the specific phrase the operator just read — "Push commits to
      // origin/main", not "Bash". Fall back to the older identifiers in
      // the same order they were used previously when no description is
      // available (legacy records, edge cases).
      const operation = (
        chain.operation_description
        || sidecar?.operation_description
        || sidecar?.tool_name
        || chain.original_tool
        || chain.tool
        || chain.capability_class
        || chain.artifact_identity
        || chain.record_hash
        || ''
      );
      modalManager.closeAll();
      setTimeout(() => {
        import('./approvals.js').then(mod => {
          mod.openApprovalsWindow(null, operation);
        });
      }, 0);
    });
    approveSection.appendChild(btn);
    el.appendChild(approveSection);
  }

  // Chain Record pane — raw JSON
  const chainPane = document.createElement('div');
  chainPane.className = 'rd-pane';
  const chainAccent = document.createElement('div');
  chainAccent.className = 'rd-pane-accent rd-accent-muted';
  chainPane.appendChild(chainAccent);
  const chainHeader = document.createElement('div');
  chainHeader.className = 'rd-pane-header';
  chainHeader.textContent = 'Chain record';
  setTooltip(chainHeader, 'Raw hash-linked chain record, including record hash and signature fields.');
  chainPane.appendChild(chainHeader);
  const chainBody = document.createElement('div');
  chainBody.className = 'rd-pane-body';
  const chainBlock = document.createElement('atd-code-block');
  chainBlock.setAttribute('language', 'json');
  chainBlock.content = chain;
  chainBody.appendChild(chainBlock);
  chainPane.appendChild(chainBody);
  el.appendChild(chainPane);

  // Sidecar record pane (conditional)
  if (sidecar) {
    const sidecarPane = document.createElement('div');
    sidecarPane.className = 'rd-pane';
    const sidecarAccent = document.createElement('div');
    sidecarAccent.className = 'rd-pane-accent rd-accent-muted';
    sidecarPane.appendChild(sidecarAccent);
    const sidecarHeader = document.createElement('div');
    sidecarHeader.className = 'rd-pane-header';
    sidecarHeader.textContent = 'Sidecar record';
    setTooltip(sidecarHeader, 'Expanded companion record used for display and audit context.');
    sidecarPane.appendChild(sidecarHeader);
    const sidecarBody = document.createElement('div');
    sidecarBody.className = 'rd-pane-body';
    const sidecarBlock = document.createElement('atd-code-block');
    sidecarBlock.setAttribute('language', 'json');
    sidecarBlock.content = sidecar;
    sidecarBody.appendChild(sidecarBlock);
    sidecarPane.appendChild(sidecarBody);
    el.appendChild(sidecarPane);
  }

  return el;
}

function _buildContextCard(chain, sidecar, eventType, decision) {
  const frag = document.createDocumentFragment();

  const rec = sidecar || chain;

  if (_isMediatedDecision(eventType)) {
    const kv = document.createElement('atd-kv-list');
    const items = [
      { key: 'Decision', value: decision || '\u2014', tooltip: 'Policy outcome recorded for this operation.' },
      // QS-062: lead the detail card with the plain-English description so
      // an operator reading a denied record sees what the agent tried to
      // do before they see the raw tool name. Both fields are surfaced \u2014
      // Action is kept because the tool name is still useful context.
      { key: 'Operation', value: rec.operation_description || '\u2014', tooltip: 'Plain-English description of what the operation does. Approvals can be scoped to this exact phrase.' },
      { key: 'Matched Rule', value: rec.matched_rule || '\u2014', variant: 'code', tooltip: 'Policy rule that produced the decision.' },
      { key: 'Action', value: rec.tool_name || rec.tool || rec.original_tool || '\u2014', variant: 'code', tooltip: 'Raw tool name the AI application invoked.' },
      { key: 'Target', value: rec.target || '\u2014', variant: 'code', tooltip: 'Path, command, URL, or artifact the operation acted on.' },
      { key: 'User', value: rec.user_identity || '\u2014', tooltip: 'Operator identity recorded with the event.' },
      { key: 'Confidence Tier', value: rec.classification?.tier != null ? `Tier ${rec.classification.tier}` : '\u2014', tooltip: 'Classifier evidence confidence used during policy evaluation.' },
      { key: 'Action Type', value: rec.action_type || rec.event_type || '\u2014', tooltip: 'Evidence-based operation category.' },
      { key: 'Scope', value: rec.governed_family || rec.scope || '\u2014', tooltip: 'Governance family or policy scope for the record.' },
      { key: 'Machine', value: _machineLabel(chain || rec), variant: 'code', tooltip: 'Machine that produced the governance record.' },
    ];
    if (decision === 'DENY') {
      items.push({ key: 'Denial Reason', value: rec.denial_reason || rec.deny_reason || 'Policy denied', variant: 'danger', tooltip: 'Evidence or policy reason Atested used to deny the operation.' });
    }
    items.push({ key: 'Verification State', value: rec.verification_state || '\u2014', variant: rec.verification_state === 'verified' ? 'success' : undefined, tooltip: 'Whether this record has been independently verified.' });
    items.push({ key: 'Record Hash', value: chain.record_hash || rec.record_hash || '\u2014', variant: 'code', tooltip: 'SHA-256 chain hash for this record.' });
    items.push({ key: 'Signature Status', value: (chain.signature || rec.signature) ? 'Signed' : 'Unsigned', tooltip: 'Whether this chain record carries an Ed25519 signature.' });
    items.push({ key: 'Event Time', value: _formatTimestamp(rec.event_timestamp_utc || chain.event_timestamp_utc || rec.timestamp_utc || chain.timestamp_utc), tooltip: 'Timestamp claimed by the originating machine.' });
    if (chain.primary_import_timestamp_utc) {
      items.push({ key: 'Primary Import', value: _formatTimestamp(chain.primary_import_timestamp_utc), tooltip: 'Timestamp when the primary accepted this remote record.' });
    }
    kv.items = items;
    frag.appendChild(kv);

  } else if (_isBoundaryObservation(eventType)) {
    const isProxyObservation = eventType === 'proxy_request_observed';
    const banner = document.createElement('div');
    banner.className = 'rd-warning-banner';
    banner.textContent = isProxyObservation
      ? 'This request was examined by the proxy. No tool calls were present in the response — no policy evaluation was needed.'
      : 'This operation was observed outside the mediation boundary and was not policy-evaluated.';
    frag.appendChild(banner);

    const kv = document.createElement('atd-kv-list');
    kv.items = [
      { key: 'Operation', value: rec.operation_type || rec.event_type || '\u2014', tooltip: isProxyObservation ? 'Proxy-observed request type.' : 'Observed operation type outside the mediation boundary.' },
      { key: 'Target', value: rec.target || '\u2014', variant: 'code', tooltip: isProxyObservation ? 'Observed provider endpoint.' : 'Observed path, command, URL, or artifact.' },
      { key: 'Source', value: rec.source || '\u2014', tooltip: isProxyObservation ? 'Runtime source that recorded the proxy observation.' : 'Runtime source that reported the observation.' },
      { key: 'Machine', value: _machineLabel(chain || rec), variant: 'code', tooltip: 'Machine that produced the governance record.' },
      { key: 'Record Hash', value: chain.record_hash || rec.record_hash || '\u2014', variant: 'code', tooltip: 'SHA-256 chain hash for this record.' },
      { key: 'Recorded', value: _formatTimestamp(rec.timestamp_utc || chain.timestamp_utc), tooltip: 'Timestamp written into the chain record.' },
    ];
    frag.appendChild(kv);

  } else if (_isApproval(eventType)) {
    const label = document.createElement('div');
    label.className = 'rd-context-label';
    label.textContent = eventType.includes('revoc') ? 'Operation Revocation' : 'Operation Approval';
    frag.appendChild(label);

    const kv = document.createElement('atd-kv-list');
    kv.items = [
      { key: 'Operation', value: rec.artifact_identity || rec.operation || '\u2014', variant: 'code', tooltip: 'Approved or revoked operation identity.' },
      { key: 'Operator', value: rec.operator_identity || rec.approving_operator || rec.operator || '\u2014', tooltip: 'Operator who approved or revoked the exception.' },
      { key: 'Scope', value: rec.governed_family || rec.scope || '\u2014', tooltip: 'Governance family the approval applies to.' },
      { key: 'Context', value: rec.deployment_context || rec.context || '\u2014', tooltip: 'Deployment context for this approval event.' },
      { key: 'Machine', value: _machineLabel(chain || rec), variant: 'code', tooltip: 'Machine that produced the governance record.' },
      { key: 'Record Hash', value: chain.record_hash || rec.record_hash || '\u2014', variant: 'code', tooltip: 'SHA-256 chain hash for this record.' },
      { key: 'Recorded', value: _formatTimestamp(rec.timestamp_utc || chain.timestamp_utc), tooltip: 'Timestamp written into the chain record.' },
    ];
    frag.appendChild(kv);

  } else if (_isVerificationChange(eventType)) {
    const label = document.createElement('div');
    label.className = 'rd-context-label';
    label.textContent = 'Verification Change';
    frag.appendChild(label);

    const kv = document.createElement('atd-kv-list');
    kv.items = [
      { key: 'Surface', value: rec.governed_family || '\u2014', tooltip: 'Governance surface whose verification state changed.' },
      { key: 'Previous State', value: rec.previous_state || '\u2014', tooltip: 'Verification state before this event.' },
      { key: 'New State', value: rec.new_state || rec.current_state || '\u2014', tooltip: 'Verification state after this event.' },
      { key: 'Machine', value: _machineLabel(chain || rec), variant: 'code', tooltip: 'Machine that produced the governance record.' },
      { key: 'Record Hash', value: chain.record_hash || rec.record_hash || '\u2014', variant: 'code', tooltip: 'SHA-256 chain hash for this record.' },
      { key: 'Recorded', value: _formatTimestamp(rec.timestamp_utc || chain.timestamp_utc), tooltip: 'Timestamp written into the chain record.' },
    ];
    frag.appendChild(kv);

  } else {
    // Generic fallback
    const label = document.createElement('div');
    label.className = 'rd-context-label';
    label.textContent = eventType || 'Record';
    frag.appendChild(label);

    const kv = document.createElement('atd-kv-list');
    const items = Object.entries(rec).slice(0, 12).map(([k, v]) => ({
      key: k,
      value: typeof v === 'object' ? JSON.stringify(v) : String(v ?? '\u2014'),
      tooltip: _genericFieldTooltip(k),
    }));
    kv.items = items;
    frag.appendChild(kv);
  }

  return frag;
}

function _genericFieldTooltip(key) {
  if (key === 'record_hash') return 'SHA-256 chain hash for this record.';
  if (key === 'prev_record_hash') return 'Hash pointer to the previous chain record.';
  if (key === 'signature') return 'Ed25519 signature, when present.';
  if (key === 'signing_key_id') return 'Identifier for the signing public key.';
  if (key === 'timestamp_utc') return 'Timestamp written into the chain record.';
  return `Raw chain field: ${key}.`;
}

// ---------- Type detection helpers ----------

function _isMediatedDecision(type) {
  return /mediat|decision|action|invocation/i.test(type);
}

function _isBoundaryObservation(type) {
  return /observ|boundar/i.test(type);
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
  const slot = frame.querySelector('.rd-loading') || frame.querySelector('.rd-content') || frame.querySelector('.rd-error');
  if (slot) {
    slot.replaceWith(newContent);
  } else {
    frame.appendChild(newContent);
  }
}

function _formatTimestamp(iso) {
  if (!iso) return '\u2014';
  try {
    const d = new Date(iso);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    const date = d.toLocaleDateString();
    return `${date} ${hh}:${mm}:${ss}`;
  } catch { return iso; }
}

function _machineLabel(record) {
  const id = record?.machine_id || '';
  if (!id) return 'unknown';
  const role = record?.machine_role || '';
  const shortId = id.length > 12 ? `${id.slice(0, 8)}...` : id;
  return role ? `${role}:${shortId}` : shortId;
}

function _resolvedRecordId(data, fallback) {
  const chain = data?.chain_record || {};
  const sidecar = data?.sidecar_record || {};
  return chain.request_id
    || chain.event_id
    || chain.record_hash
    || sidecar.request_id
    || sidecar.event_id
    || sidecar.record_hash
    || data?.record_id
    || fallback
    || '';
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
  .rd-error { color: #d29922; }
  .rd-content {
    font-family: "Inter", system-ui, sans-serif;
  }

  /* ---- Top accent bar ---- */
  .rd-top-accent {
    height: 6px;
    border-radius: 2px 2px 0 0;
    margin: -24px -24px 0;
    /* Stretch to fill the content padding */
  }
  .rd-accent-green { background: #3fb950; }
  .rd-accent-red { background: #f85149; }
  .rd-accent-muted { background: #6b7280; }

  /* ---- Record ID subtitle ---- */
  .rd-subtitle {
    padding: 14px 0 16px;
  }
  .rd-subtitle-id {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.75rem;
    color: #6b7280;
    word-break: break-all;
  }

  .rd-machine-banner {
    border: 1px solid rgba(102,153,204,0.28);
    background: rgba(102,153,204,0.08);
    border-radius: 2px;
    padding: 12px 14px;
    margin: 0 0 16px;
  }
  .rd-machine-title {
    color: #9cc9ff;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .rd-machine-grid {
    display: grid;
    grid-template-columns: max-content minmax(0, 1fr);
    gap: 6px 12px;
    align-items: start;
  }
  .rd-machine-grid span {
    color: #8b919a;
    font-size: 0.76rem;
  }
  .rd-machine-grid code {
    color: #e4e6eb;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.76rem;
    word-break: break-all;
  }

  /* ---- Pane container ---- */
  .rd-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .rd-pane-accent {
    height: 6px;
  }
  .rd-pane-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
    padding: 12px 20px 4px;
  }
  .rd-pane-body {
    padding: 8px 20px 16px;
  }

  /* ---- Context label (sub-type within Record pane) ---- */
  .rd-context-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    margin-bottom: 8px;
    font-weight: 500;
  }

  /* ---- Warning banner ---- */
  .rd-warning-banner {
    color: #d29922;
    padding: 10px 14px;
    border-radius: 2px;
    font-size: 0.82rem;
    margin-bottom: 12px;
  }

  /* ---- Approve button ---- */
  .rd-approve-section {
    margin-bottom: 16px;
  }
`;
document.head.appendChild(rdStyles);
