/**
 * Communications window — child window (depth 1).
 * D-043 redesign: priority request slots, telemetry management,
 * request history. Grandchild windows for slot detail and telemetry traffic.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';

let _pendingCompose = null;

/**
 * Open the Communications window with a pre-populated compose context.
 * @param {HTMLElement|null} trigger
 * @param {{ subject: string, context: string }} composeData
 */
export function openCommunicationsWindowWithCompose(trigger, composeData) {
  _pendingCompose = composeData;
  openCommunicationsWindow(trigger);
}

const SLOT_ALLOC = {
  personal:      { medium: 0, high: 0 },
  personal_plus: { medium: 2, high: 0 },
  crew:          { medium: 4, high: 2 },
  team:          { medium: 8, high: 4 },
  institution:   { medium: 16, high: 8 },
};

/**
 * Open the Communications window.
 * @param {HTMLElement|null} trigger
 */
export function openCommunicationsWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'cm-root';

  const result = _openAsChild('Communications', 'Submit requests and manage your telemetry', trigger, content);
  if (!result) return;

  const state = { el: content, data: null };
  _loadData(state);
}

// Keep backward compat export name for main-page
export { openCommunicationsWindow as openFeedbackWindow };

// ---------- Data ----------

async function _loadData(state) {
  state.el.innerHTML = '<div class="cm-loading">Loading communications\u2026</div>';

  const res = await api.getCommunications();
  if (!res.ok) {
    state.el.innerHTML = `<div class="cm-error">${_esc(res.error)}</div>`;
    return;
  }

  state.data = res.data;
  _renderAll(state);
}

// ---------- Render ----------

function _renderAll(state) {
  const d = state.data;
  const el = state.el;
  el.innerHTML = '';

  const slots = d.slots || { medium: 0, high: 0 };
  const activeMedium = d.active_medium || [];
  const activeHigh = d.active_high || [];
  const medAvail = Math.max(0, slots.medium - activeMedium.length);
  const highAvail = Math.max(0, slots.high - activeHigh.length);

  // Summary stat cards
  const stats = document.createElement('div');
  stats.className = 'cm-stats';
  stats.innerHTML = `
    <div class="cm-stat-card">
      <span class="cm-stat-label">Telemetry</span>
      <span class="cm-stat-value ${d.telemetry_opted_in ? 'cm-val-green' : 'cm-val-amber'}">${d.telemetry_opted_in ? 'Active' : 'Inactive'}</span>
    </div>
    <div class="cm-stat-card">
      <span class="cm-stat-label">Medium Slots</span>
      <span class="cm-stat-value">${medAvail} of ${slots.medium}</span>
    </div>
    <div class="cm-stat-card">
      <span class="cm-stat-label">High Slots</span>
      <span class="cm-stat-value">${highAvail} of ${slots.high}</span>
    </div>
    <div class="cm-stat-card">
      <span class="cm-stat-label">Last Exchange</span>
      <span class="cm-stat-value cm-stat-date">${d.last_exchange ? _formatHumanDate(d.last_exchange) : 'N/A'}</span>
    </div>
  `;
  el.appendChild(stats);

  // Submit a request pane
  const submitPane = _buildSubmitPane(state, medAvail, highAvail);
  el.appendChild(submitPane);

  // Apply pending compose data if set
  if (_pendingCompose) {
    const textarea = submitPane.querySelector('#cm-request-text');
    if (textarea) {
      const ctx = _pendingCompose;
      let text = '';
      if (ctx.subject) text += `Subject: ${ctx.subject}\n`;
      if (ctx.context) text += `\n${ctx.context}\n`;
      text += '\n--- Your message below ---\n';
      textarea.value = text;
      // Place cursor at end
      setTimeout(() => {
        textarea.focus();
        textarea.selectionStart = textarea.selectionEnd = textarea.value.length;
      }, 50);
    }
    _pendingCompose = null;
  }

  // Priority slot panes — side by side
  const slotRow = document.createElement('div');
  slotRow.className = 'cm-slot-row';
  slotRow.appendChild(_buildSlotPane(state, 'medium', 'Medium priority', activeMedium, slots.medium,
    'Medium slots move your request ahead of standard requests. Slots are occupied until the request is resolved.'));
  slotRow.appendChild(_buildSlotPane(state, 'high', 'High priority', activeHigh, slots.high,
    'High slots move to the front of the queue ahead of Medium. Use these for issues that are blocking your work.'));
  el.appendChild(slotRow);

  // Bottom row — Telemetry + Request History
  const bottomRow = document.createElement('div');
  bottomRow.className = 'cm-bottom-row';
  bottomRow.appendChild(_buildTelemetryPane(state, d));
  bottomRow.appendChild(_buildHistoryPane(state, d));
  el.appendChild(bottomRow);
}

// ---------- Submit a request pane ----------

function _buildSubmitPane(state, medAvail, highAvail) {
  const pane = document.createElement('div');
  pane.className = 'cm-pane';
  pane.innerHTML = `
    <div class="cm-pane-accent cm-accent-amber"></div>
    <div class="cm-pane-header">Submit a request</div>
    <div class="cm-pane-body">
      <p class="cm-pane-copy">Describe your issue, question, or suggestion. Standard requests are always available. Medium and High use your allocated slots and receive faster response. Choose the level that matches the urgency. We depend on your judgment to set it appropriately.</p>
      <textarea class="cm-textarea" id="cm-request-text" rows="4" placeholder="Describe your request\u2026"></textarea>
      <div class="cm-priority-row">
        <div class="cm-priority-toggles" id="cm-priority-toggles">
          <button class="cm-pri-btn cm-pri-active" data-priority="standard">Standard</button>
          <button class="cm-pri-btn cm-pri-medium${medAvail === 0 ? ' cm-pri-disabled' : ''}" data-priority="medium" ${medAvail === 0 ? 'disabled' : ''}>Medium (${medAvail} avail)</button>
          <button class="cm-pri-btn cm-pri-high${highAvail === 0 ? ' cm-pri-disabled' : ''}" data-priority="high" ${highAvail === 0 ? 'disabled' : ''}>High (${highAvail} avail)</button>
        </div>
        <button class="cm-btn cm-btn-submit" id="cm-submit-btn">Submit</button>
      </div>
      <div id="cm-submit-result"></div>
    </div>
  `;

  // Priority toggle
  let selectedPriority = 'standard';
  pane.querySelector('#cm-priority-toggles').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-priority]');
    if (!btn || btn.disabled) return;
    pane.querySelectorAll('.cm-pri-btn').forEach(b => b.classList.remove('cm-pri-active'));
    btn.classList.add('cm-pri-active');
    selectedPriority = btn.dataset.priority;
  });

  // Submit
  pane.querySelector('#cm-submit-btn').addEventListener('click', async () => {
    const text = pane.querySelector('#cm-request-text').value.trim();
    const resultEl = pane.querySelector('#cm-submit-result');
    if (!text) {
      resultEl.className = 'cm-result-error';
      resultEl.textContent = 'Please describe your request.';
      return;
    }

    resultEl.className = '';
    resultEl.textContent = 'Submitting\u2026';

    const res = await api.postCommunicationsRequest({ message: text, priority: selectedPriority });
    if (res.ok) {
      resultEl.className = 'cm-result-success';
      resultEl.textContent = 'Request submitted. Recorded in the governance chain.';
      pane.querySelector('#cm-request-text').value = '';
      // Refresh to show the new request in slots
      setTimeout(() => _loadData(state), 1000);
    } else {
      resultEl.className = 'cm-result-error';
      resultEl.textContent = res.error || 'Submission failed.';
    }
  });

  return pane;
}

// ---------- Slot panes ----------

function _buildSlotPane(state, level, title, activeSlots, totalSlots, tooltip) {
  const inUse = activeSlots.length;
  const available = Math.max(0, totalSlots - inUse);
  const accentColor = inUse > 0 ? (level === 'high' ? 'red' : 'amber') : 'green';

  const pane = document.createElement('div');
  pane.className = 'cm-pane';
  pane.innerHTML = `
    <div class="cm-pane-accent cm-accent-${accentColor}"></div>
    <div class="cm-pane-header" title="${_escAttr(tooltip)}">${_esc(title)}</div>
    <div class="cm-pane-body">
      <div class="cm-slot-count">${inUse} of ${totalSlots} slots in use</div>
      <div class="cm-slot-cards"></div>
    </div>
  `;

  const cards = pane.querySelector('.cm-slot-cards');

  if (totalSlots === 0) {
    cards.innerHTML = '<div class="cm-slot-none">No slots available on your plan.</div>';
    return pane;
  }

  // Occupied slots
  for (const req of activeSlots) {
    const card = document.createElement('div');
    card.className = 'cm-slot-card cm-slot-occupied';

    const status = req.status || 'received';
    const statusLabel = status === 'in_progress' ? 'In progress' : status === 'awaiting_response' ? 'Awaiting response' : 'Received';
    const statusClass = status === 'in_progress' ? 'cm-status-amber' : 'cm-status-green';

    const summary = (req.message || '').length > 60 ? req.message.substring(0, 57) + '\u2026' : (req.message || '');

    card.innerHTML = `
      <div class="cm-slot-summary">${_esc(summary)}</div>
      <div class="cm-slot-meta">
        <span class="cm-slot-status ${statusClass}">${_esc(statusLabel)}</span>
        <span class="cm-slot-date">${_esc(_formatHumanDate(req.timestamp_utc))}</span>
      </div>
    `;

    card.addEventListener('click', () => _openSlotDetail(state, req, level));
    cards.appendChild(card);
  }

  // Available slots
  for (let i = 0; i < available; i++) {
    const card = document.createElement('div');
    card.className = 'cm-slot-card cm-slot-available';
    card.innerHTML = '<span class="cm-slot-avail-text">Available slot</span>';
    cards.appendChild(card);
  }

  return pane;
}

// ---------- Telemetry pane ----------

function _buildTelemetryPane(state, d) {
  const pane = document.createElement('div');
  pane.className = 'cm-pane cm-pane-clickable';
  const tooltip = 'Every transmission on this channel is recorded in your governance chain. You can audit what was sent and received at any time. This is our transparency commitment.';

  const traffic = d.telemetry_traffic || [];
  const lastSent = traffic.find(t => t.direction !== 'inbound');
  const lastRecv = traffic.find(t => t.direction === 'inbound');

  pane.innerHTML = `
    <div class="cm-pane-accent cm-accent-green"></div>
    <div class="cm-pane-header" title="${_escAttr(tooltip)}">Telemetry</div>
    <div class="cm-pane-body">
      <div class="cm-kv-list">
        <div class="cm-kv"><span class="cm-kv-label">Status</span><span class="cm-kv-value ${d.telemetry_opted_in ? 'cm-val-green' : 'cm-val-amber'}">${d.telemetry_opted_in ? 'Participating' : 'Declined'}</span></div>
        <div class="cm-kv"><span class="cm-kv-label">Last sent</span><span class="cm-kv-value">${lastSent ? _formatHumanDate(lastSent.timestamp_utc) : 'N/A'}</span></div>
        <div class="cm-kv"><span class="cm-kv-label">Last received</span><span class="cm-kv-value">${lastRecv ? _formatHumanDate(lastRecv.timestamp_utc) : 'N/A'}</span></div>
      </div>
      <p class="cm-pane-note">${d.telemetry_opted_in ? 'Bidirectional channel active.' : 'Channel inactive.'} You can change your preference at any time.</p>
    </div>
  `;

  pane.addEventListener('click', () => _openTelemetryDetail(state, d));
  return pane;
}

// ---------- Request history pane ----------

function _buildHistoryPane(state, d) {
  const resolved = d.resolved || [];
  const standard = d.standard || [];
  const allHistory = [...resolved, ...standard].sort((a, b) =>
    (b.timestamp_utc || '').localeCompare(a.timestamp_utc || '')
  );

  const pane = document.createElement('div');
  pane.className = 'cm-pane cm-pane-clickable';

  pane.innerHTML = `
    <div class="cm-pane-accent cm-accent-green"></div>
    <div class="cm-pane-header">Request history</div>
    <div class="cm-pane-body">
      ${allHistory.length ? '' : '<div class="cm-empty">No requests yet.</div>'}
    </div>
  `;

  if (allHistory.length) {
    const body = pane.querySelector('.cm-pane-body');
    const table = document.createElement('table');
    table.className = 'cm-history-table';
    table.innerHTML = '<thead><tr><th>Date</th><th>Summary</th><th>Status</th></tr></thead>';
    const tbody = document.createElement('tbody');

    for (const req of allHistory.slice(0, 5)) {
      const tr = document.createElement('tr');
      const summary = (req.message || '').length > 40 ? req.message.substring(0, 37) + '\u2026' : (req.message || '');
      const status = req.status || 'submitted';
      const statusClass = status === 'resolved' ? 'cm-status-green' : 'cm-status-muted';
      tr.innerHTML = `
        <td class="cm-hist-date">${_esc(_formatHumanDate(req.timestamp_utc))}</td>
        <td>${_esc(summary)}</td>
        <td><span class="${statusClass}">${_esc(_capitalize(status))}</span></td>
      `;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    body.appendChild(table);

    if (allHistory.length > 5) {
      const more = document.createElement('div');
      more.className = 'cm-preview-note';
      more.textContent = `${allHistory.length - 5} more\u2026`;
      body.appendChild(more);
    }
  }

  pane.addEventListener('click', () => _openHistoryDetail(state, d));
  return pane;
}

// ================================================================
// GRANDCHILD WINDOWS
// ================================================================

// ---------- Slot detail grandchild ----------

function _openSlotDetail(state, req, level) {
  const accentColor = level === 'high' ? 'red' : 'amber';
  const content = document.createElement('div');
  content.className = 'cm-gc';

  content.innerHTML = `
    <div class="cm-gc-accent cm-accent-${accentColor}"></div>
    <div class="cm-gc-header">${_esc(_capitalize(level))} priority request</div>
  `;

  // Paired pane layout
  const paired = document.createElement('div');
  paired.className = 'cm-paired';

  // Left: Your request
  const leftPane = document.createElement('div');
  leftPane.className = 'cm-paired-pane';
  const status = req.status || 'received';
  const statusLabel = status === 'in_progress' ? 'In progress' : status === 'awaiting_response' ? 'Awaiting response' : 'Received';

  leftPane.innerHTML = `
    <div class="cm-paired-header">Your request</div>
    <div class="cm-paired-body">
      <div class="cm-paired-message">${_esc(req.message || '')}</div>
      <div class="cm-paired-meta">
        <div class="cm-kv"><span class="cm-kv-label">Submitted</span><span class="cm-kv-value">${_esc(_formatHumanDate(req.timestamp_utc))}</span></div>
        <div class="cm-kv"><span class="cm-kv-label">Priority</span><span class="cm-kv-value">${_esc(_capitalize(level))}</span></div>
        <div class="cm-kv"><span class="cm-kv-label">Status</span><span class="cm-kv-value">${_esc(statusLabel)}</span></div>
        <div class="cm-kv"><span class="cm-kv-label">Request ID</span><span class="cm-kv-value cm-kv-mono">${_esc((req.request_id || '').substring(0, 8))}</span></div>
      </div>
    </div>
  `;

  // Right: Atested response
  const rightPane = document.createElement('div');
  rightPane.className = 'cm-paired-pane';
  rightPane.innerHTML = `
    <div class="cm-paired-header">Atested response</div>
    <div class="cm-paired-body">
      <div class="cm-response-entry">
        <span class="cm-response-time">${_esc(_formatHumanDate(req.timestamp_utc))}</span>
        <span class="cm-response-text">Request received and queued.</span>
      </div>
      ${(req.responses || []).map(r => `
        <div class="cm-response-entry">
          <span class="cm-response-time">${_esc(_formatHumanDate(r.timestamp_utc))}</span>
          <span class="cm-response-text">${_esc(r.message || '')}</span>
        </div>
      `).join('')}
      ${!req.responses?.length ? '<div class="cm-response-waiting">Awaiting investigation. Updates will appear here.</div>' : ''}
    </div>
  `;

  paired.appendChild(leftPane);
  paired.appendChild(rightPane);
  content.appendChild(paired);

  modalManager.open({ title: `Request ${(req.request_id || '').substring(0, 8)}`, subtitle: 'Priority request exchange detail', trigger: state.el, content });
}

// ---------- Telemetry grandchild ----------

function _openTelemetryDetail(state, d) {
  const content = document.createElement('div');
  content.className = 'cm-gc';

  content.innerHTML = `
    <div class="cm-gc-accent cm-accent-green"></div>
    <div class="cm-gc-header">Telemetry management</div>
  `;

  // Participation toggle
  const toggleSection = document.createElement('div');
  toggleSection.className = 'cm-gc-section';
  toggleSection.innerHTML = `
    <div class="cm-gc-sub-header">Participation</div>
    <div class="cm-toggle-row">
      <span class="cm-toggle-status ${d.telemetry_opted_in ? 'cm-val-green' : 'cm-val-amber'}">${d.telemetry_opted_in ? 'Participating' : 'Declined'}</span>
      <button class="cm-btn cm-btn-toggle" id="cm-telemetry-toggle">${d.telemetry_opted_in ? 'Opt out' : 'Opt in'}</button>
    </div>
    <p class="cm-gc-explain">You can opt out at any time. Opting out reduces our ability to deliver version updates and operational intelligence. Emergency communications are never affected.</p>
  `;

  toggleSection.querySelector('#cm-telemetry-toggle').addEventListener('click', async () => {
    const newState = !d.telemetry_opted_in;
    const res = await api.postTelemetryOptIn({ opted_in: newState });
    if (res.ok) {
      d.telemetry_opted_in = newState;
      modalManager.closeTopmost();
      _loadData(state);
    }
  });
  content.appendChild(toggleSection);

  // Traffic history
  const traffic = d.telemetry_traffic || [];
  if (traffic.length) {
    const trafficSection = document.createElement('div');
    trafficSection.className = 'cm-gc-section';
    trafficSection.innerHTML = '<div class="cm-gc-sub-header">Traffic history</div>';

    const table = document.createElement('table');
    table.className = 'cm-traffic-table';
    table.innerHTML = `<thead><tr>
      <th style="width:80px">Direction</th>
      <th style="width:120px">Time</th>
      <th>Content</th>
      <th style="width:100px">Fingerprint</th>
    </tr></thead>`;

    const tbody = document.createElement('tbody');
    for (const t of traffic) {
      const direction = t.direction === 'inbound' ? 'Inbound' : 'Outbound';
      const dirClass = t.direction === 'inbound' ? 'cm-dir-in' : 'cm-dir-out';

      // Build content summary
      let contentSummary = '';
      if (t.total_allow != null) {
        contentSummary = `Allow: ${t.total_allow}, Deny: ${t.total_deny}`;
      } else if (t.content_type) {
        contentSummary = t.content_type;
      } else if (t.summary) {
        contentSummary = t.summary;
      } else {
        contentSummary = 'Aggregated counts';
      }

      const hash = t.artifact_hash || t.hash || '';
      const fpShort = hash.length > 12 ? hash.substring(0, 8) + '\u2026' : (hash || 'N/A');

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td><span class="cm-dir-badge ${dirClass}">${_esc(direction)}</span></td>
        <td class="cm-traffic-time">${_esc(_formatHumanDate(t.timestamp_utc))}</td>
        <td>${_esc(contentSummary)}</td>
        <td class="cm-traffic-fp" title="${_escAttr(hash)}">${_esc(fpShort)}</td>
      `;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    trafficSection.appendChild(table);

    const verifyNote = document.createElement('p');
    verifyNote.className = 'cm-gc-note';
    verifyNote.textContent = 'Each entry is verifiable against your governance chain. The fingerprint matches the chain record hash.';
    trafficSection.appendChild(verifyNote);

    content.appendChild(trafficSection);
  } else {
    const emptySection = document.createElement('div');
    emptySection.className = 'cm-gc-section';
    emptySection.innerHTML = '<div class="cm-gc-sub-header">Traffic history</div><p class="cm-gc-note">No telemetry transmissions recorded yet.</p>';
    content.appendChild(emptySection);
  }

  modalManager.open({ title: 'Telemetry', subtitle: 'Participation and traffic history', trigger: state.el, content });
}

// ---------- Request history grandchild ----------

function _openHistoryDetail(state, d) {
  const resolved = d.resolved || [];
  const standard = d.standard || [];
  const activeMedium = d.active_medium || [];
  const activeHigh = d.active_high || [];
  const allRequests = [...activeHigh, ...activeMedium, ...resolved, ...standard].sort((a, b) =>
    (b.timestamp_utc || '').localeCompare(a.timestamp_utc || '')
  );

  const content = document.createElement('div');
  content.className = 'cm-gc';

  content.innerHTML = `
    <div class="cm-gc-accent cm-accent-green"></div>
    <div class="cm-gc-header">Request history</div>
  `;

  if (!allRequests.length) {
    const empty = document.createElement('div');
    empty.className = 'cm-gc-section';
    empty.innerHTML = '<p class="cm-gc-note">No requests submitted yet. Use the form above to submit your first request.</p>';
    content.appendChild(empty);
  } else {
    const tableSection = document.createElement('div');
    tableSection.className = 'cm-gc-section';

    const table = document.createElement('table');
    table.className = 'cm-history-full-table';
    table.innerHTML = `<thead><tr>
      <th style="width:120px">Date</th>
      <th>Summary</th>
      <th style="width:70px">Priority</th>
      <th style="width:90px">Status</th>
    </tr></thead>`;

    const tbody = document.createElement('tbody');
    for (const req of allRequests) {
      const tr = document.createElement('tr');
      const summary = (req.message || '').length > 50 ? req.message.substring(0, 47) + '\u2026' : (req.message || '');
      const priority = req.priority || 'standard';
      const status = req.status || 'submitted';
      const statusClass = status === 'resolved' ? 'cm-status-green' : status === 'in_progress' ? 'cm-status-amber' : 'cm-status-muted';
      const priClass = priority === 'high' ? 'cm-pri-tag-high' : priority === 'medium' ? 'cm-pri-tag-medium' : 'cm-pri-tag-standard';

      tr.innerHTML = `
        <td class="cm-hist-date">${_esc(_formatHumanDate(req.timestamp_utc))}</td>
        <td>${_esc(summary)}</td>
        <td><span class="cm-pri-tag ${priClass}">${_esc(_capitalize(priority))}</span></td>
        <td><span class="${statusClass}">${_esc(_capitalize(status))}</span></td>
      `;

      // Click to open slot detail for priority requests
      if (priority !== 'standard') {
        tr.className = 'cm-hist-clickable';
        tr.addEventListener('click', () => {
          modalManager.closeTopmost();
          setTimeout(() => _openSlotDetail(state, req, priority), 0);
        });
      }
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    tableSection.appendChild(table);
    content.appendChild(tableSection);
  }

  modalManager.open({ title: 'Request History', subtitle: 'All submitted requests', trigger: state.el, content });
}

// ---------- Utility ----------

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, subtitle, trigger, content });
  return modalManager.open({ title, subtitle, trigger, content });
}

function _formatHumanDate(isoStr) {
  if (!isoStr) return 'N/A';
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    if (d.getDate() === now.getDate() && d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear()) {
      return `${hh}:${mm}`;
    }
    return `${months[d.getMonth()]} ${d.getDate()}, ${hh}:${mm}`;
  } catch { return isoStr; }
}

function _capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
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

const cmStyles = document.createElement('style');
cmStyles.textContent = `
  .cm-root {
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }

  /* ---- Stat cards ---- */
  .cm-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }
  .cm-stat-card {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
  }
  .cm-stat-label {
    display: block;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    margin-bottom: 4px;
    font-weight: 500;
  }
  .cm-stat-value {
    font-size: 1.2rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .cm-stat-date {
    font-size: 0.9rem;
    font-family: "Inter", system-ui, sans-serif;
  }
  .cm-val-green { color: #22c55e; }
  .cm-val-amber { color: #f5a623; }

  /* ---- Pane ---- */
  .cm-pane {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .cm-pane-clickable {
    cursor: pointer;
    transition: border-color 0.12s, box-shadow 0.12s;
  }
  .cm-pane-clickable:hover {
    border-color: rgba(96,165,250,0.3);
    box-shadow: 0 0 0 1px rgba(96,165,250,0.15);
  }
  .cm-pane-accent { height: 6px; }
  .cm-accent-green { background: #22c55e; }
  .cm-accent-amber { background: #f5a623; }
  .cm-accent-red { background: #ef4444; }
  .cm-pane-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #60a5fa;
    font-weight: 600;
    padding: 12px 20px 4px;
  }
  .cm-pane-body { padding: 8px 20px 16px; }
  .cm-pane-copy {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.5;
    margin: 0 0 12px;
  }
  .cm-pane-note {
    font-size: 0.78rem;
    color: #6b7280;
    margin: 8px 0 0;
    line-height: 1.4;
  }

  /* ---- Submit form ---- */
  .cm-textarea {
    width: 100%;
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 10px 12px;
    resize: vertical;
    box-sizing: border-box;
    margin-bottom: 10px;
  }
  .cm-textarea:focus { outline: 2px solid #60a5fa; outline-offset: 1px; }
  .cm-priority-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }
  .cm-priority-toggles { display: flex; gap: 4px; }
  .cm-pri-btn {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    color: #8b919a;
    font-size: 0.75rem;
    padding: 5px 12px;
    cursor: pointer;
    transition: all 0.12s;
    font-family: "Inter", system-ui, sans-serif;
  }
  .cm-pri-btn:hover:not(:disabled) { color: #e4e6eb; }
  .cm-pri-active {
    background: rgba(96,165,250,0.12);
    color: #60a5fa;
    border-color: rgba(96,165,250,0.4);
    font-weight: 600;
  }
  .cm-pri-medium { border-color: rgba(245,166,35,0.3); }
  .cm-pri-medium.cm-pri-active { background: rgba(245,166,35,0.12); color: #f5a623; border-color: rgba(245,166,35,0.5); }
  .cm-pri-high { border-color: rgba(239,68,68,0.3); }
  .cm-pri-high.cm-pri-active { background: rgba(239,68,68,0.12); color: #ef4444; border-color: rgba(239,68,68,0.5); }
  .cm-pri-disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .cm-btn {
    border: none;
    border-radius: 6px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 7px 20px;
    cursor: pointer;
    transition: background 0.1s;
    white-space: nowrap;
  }
  .cm-btn-submit { background: #22c55e; color: #fff; }
  .cm-btn-submit:hover { background: #16a34a; }
  .cm-btn-toggle {
    background: rgba(96,165,250,0.12);
    color: #60a5fa;
    border: 1px solid rgba(96,165,250,0.3);
  }
  .cm-btn-toggle:hover { background: rgba(96,165,250,0.20); }
  .cm-result-success { color: #22c55e; font-size: 0.82rem; margin-top: 8px; }
  .cm-result-error { color: #f5a623; font-size: 0.82rem; margin-top: 8px; }

  /* ---- Slot row ---- */
  .cm-slot-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
  }
  .cm-slot-count {
    font-size: 0.75rem;
    color: #6b7280;
    margin-bottom: 10px;
  }
  .cm-slot-cards { display: flex; flex-direction: column; gap: 8px; }
  .cm-slot-card {
    border-radius: 8px;
    padding: 12px 14px;
  }
  .cm-slot-occupied {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    cursor: pointer;
    transition: border-color 0.12s;
  }
  .cm-slot-occupied:hover {
    border-color: rgba(96,165,250,0.3);
  }
  .cm-slot-available {
    background: transparent;
    border: 1px dashed rgba(255,255,255,0.10);
    text-align: center;
  }
  .cm-slot-avail-text {
    font-size: 0.78rem;
    color: #4b5563;
  }
  .cm-slot-summary {
    font-size: 0.82rem;
    font-weight: 500;
    color: #e4e6eb;
    margin-bottom: 6px;
  }
  .cm-slot-meta { display: flex; justify-content: space-between; align-items: center; }
  .cm-slot-status { font-size: 0.72rem; font-weight: 600; }
  .cm-status-green { color: #22c55e; }
  .cm-status-amber { color: #f5a623; }
  .cm-status-muted { color: #8b919a; }
  .cm-slot-date { font-size: 0.72rem; color: #6b7280; }
  .cm-slot-none {
    font-size: 0.78rem;
    color: #4b5563;
    text-align: center;
    padding: 12px 0;
    font-style: italic;
  }

  /* ---- Bottom row ---- */
  .cm-bottom-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  /* ---- KV list ---- */
  .cm-kv-list { display: flex; flex-direction: column; }
  .cm-kv { display: flex; justify-content: space-between; align-items: center; padding: 4px 0; }
  .cm-kv-label { font-size: 0.78rem; color: #8b919a; }
  .cm-kv-value { font-size: 0.82rem; color: #e4e6eb; }
  .cm-kv-mono { font-family: "JetBrains Mono", monospace; font-size: 0.75rem; }

  /* ---- History table (preview) ---- */
  .cm-history-table, .cm-history-full-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .cm-history-table thead th, .cm-history-full-table thead th {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    font-weight: 600;
    text-align: left;
    padding: 4px 8px 6px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .cm-history-table tbody td, .cm-history-full-table tbody td {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .cm-hist-date { font-size: 0.72rem; color: #8b919a; white-space: nowrap; }
  .cm-hist-clickable { cursor: pointer; transition: background 0.1s; }
  .cm-hist-clickable:hover { background: rgba(96,165,250,0.06); }

  /* Priority tags */
  .cm-pri-tag {
    display: inline-block;
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 1px 8px;
    border-radius: 999px;
  }
  .cm-pri-tag-standard { background: rgba(107,114,128,0.12); color: #8b919a; }
  .cm-pri-tag-medium { background: rgba(245,166,35,0.12); color: #f5a623; }
  .cm-pri-tag-high { background: rgba(239,68,68,0.12); color: #ef4444; }

  .cm-preview-note {
    font-size: 0.75rem;
    color: #6b7280;
    padding: 6px 0 0;
    font-style: italic;
  }

  /* ---- Grandchild ---- */
  .cm-gc { font-family: "Inter", system-ui, sans-serif; }
  .cm-gc-accent {
    height: 6px;
    margin: -24px -24px 0;
    border-radius: 4px 4px 0 0;
  }
  .cm-gc-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #60a5fa;
    font-weight: 600;
    padding: 14px 0 10px;
  }
  .cm-gc-sub-header {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    font-weight: 600;
    padding: 6px 0;
  }
  .cm-gc-section { margin-bottom: 14px; }
  .cm-gc-explain {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.6;
    margin: 0 0 8px;
  }
  .cm-gc-note {
    font-size: 0.78rem;
    color: #6b7280;
    font-style: italic;
    margin: 8px 0 0;
  }

  /* ---- Paired pane layout ---- */
  .cm-paired {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 8px;
  }
  .cm-paired-pane {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 10px;
    overflow: hidden;
  }
  .cm-paired-header {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #60a5fa;
    font-weight: 600;
    padding: 12px 16px 4px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .cm-paired-body { padding: 12px 16px; }
  .cm-paired-message {
    font-size: 0.85rem;
    color: #e4e6eb;
    line-height: 1.5;
    margin-bottom: 12px;
    white-space: pre-wrap;
  }
  .cm-paired-meta { border-top: 1px solid rgba(255,255,255,0.04); padding-top: 8px; }

  /* Response entries */
  .cm-response-entry {
    padding: 8px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .cm-response-entry:last-child { border-bottom: none; }
  .cm-response-time {
    display: block;
    font-size: 0.68rem;
    color: #6b7280;
    margin-bottom: 3px;
    font-family: "JetBrains Mono", monospace;
  }
  .cm-response-text {
    font-size: 0.82rem;
    color: #e4e6eb;
    line-height: 1.4;
  }
  .cm-response-waiting {
    font-size: 0.82rem;
    color: #6b7280;
    font-style: italic;
    padding: 16px 0;
    text-align: center;
  }

  /* ---- Telemetry toggle ---- */
  .cm-toggle-row {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 10px;
  }
  .cm-toggle-status {
    font-size: 0.85rem;
    font-weight: 600;
  }

  /* ---- Traffic table ---- */
  .cm-traffic-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .cm-traffic-table thead th {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    font-weight: 600;
    text-align: left;
    padding: 4px 8px 6px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .cm-traffic-table tbody td {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .cm-traffic-time { font-size: 0.72rem; color: #8b919a; white-space: nowrap; }
  .cm-traffic-fp { font-family: "JetBrains Mono", monospace; font-size: 0.68rem; color: #6b7280; }
  .cm-dir-badge {
    display: inline-block;
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 1px 8px;
    border-radius: 999px;
  }
  .cm-dir-out { background: rgba(96,165,250,0.12); color: #60a5fa; }
  .cm-dir-in { background: rgba(34,197,94,0.12); color: #22c55e; }

  /* ---- Utility ---- */
  .cm-loading {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
  }
  .cm-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 16px 0;
    font-style: italic;
  }
  .cm-error {
    color: #f5a623;
    background: rgba(245,166,35,0.10);
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 0.82rem;
  }

  /* ---- Responsive ---- */
  @media (max-width: 600px) {
    .cm-stats { grid-template-columns: repeat(2, 1fr); }
    .cm-slot-row { grid-template-columns: 1fr; }
    .cm-bottom-row { grid-template-columns: 1fr; }
    .cm-paired { grid-template-columns: 1fr; }
    .cm-priority-row { flex-direction: column; align-items: stretch; }
  }
`;
document.head.appendChild(cmStyles);
