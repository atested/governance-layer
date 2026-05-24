/**
 * Communications window — child window (depth 1).
 * D-043 redesign: priority request slots, telemetry management,
 * request history. Grandchild windows for slot detail and telemetry traffic.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { applyGenericWindowTooltips, installWindowTooltips, setTooltip } from '../tooltip-utils.js';

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

/**
 * Open the Communications window.
 * @param {HTMLElement|null} trigger
 */
export function openCommunicationsWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'cm-root';

  const result = _openAsChild('Communications', 'Submit requests and manage Atested telemetry', trigger, content);
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
  installWindowTooltips(state.el);
  applyGenericWindowTooltips(state.el);
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

  // Update notifications (version updates)
  const updateNotifs = d.update_notifications || [];
  if (updateNotifs.length > 0) {
    const updateSection = document.createElement('div');
    updateSection.className = 'cm-pane cm-update-pane';
    updateSection.innerHTML = `
      <div class="cm-pane-accent cm-accent-green"></div>
      <div class="cm-pane-header">Software Updates</div>
      <div class="cm-pane-body cm-update-list"></div>
    `;
    const list = updateSection.querySelector('.cm-update-list');
    for (const notif of updateNotifs) {
      const card = document.createElement('div');
      card.className = 'cm-update-card';
      card.innerHTML = `
        <div class="cm-update-msg">${_esc(notif.message)}</div>
        <div class="cm-update-meta">
          <span class="cm-update-date">${notif.timestamp_utc ? _formatHumanDate(notif.timestamp_utc) : ''}</span>
          <button class="cm-btn cm-btn-dismiss" data-nid="${_esc(notif.notification_id)}">Dismiss</button>
        </div>
      `;
      list.appendChild(card);
    }
    // Dismiss handler
    list.addEventListener('click', async (e) => {
      const btn = e.target.closest('.cm-btn-dismiss');
      if (!btn) return;
      const nid = btn.dataset.nid;
      btn.disabled = true;
      btn.textContent = 'Dismissing\u2026';
      await api.postDismissUpdateNotification({ notification_id: nid });
      _loadData(state);
    });
    el.appendChild(updateSection);
  }

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
    'Medium priority requests are acknowledged on receipt. Once acknowledged, the slot is available again while resolution continues in request history.'));
  slotRow.appendChild(_buildSlotPane(state, 'high', 'High priority', activeHigh, slots.high,
    'High priority requests are acknowledged on receipt. Use them when the issue is blocking work and you need direct help quickly.'));
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
      <p class="cm-pane-copy">Describe your issue, question, or suggestion. For a screen-specific problem, use the Trouble button instead — it captures the current context automatically. This form is for general requests, questions, and suggestions. Priority is available to any operator when a slot is free; choose the level that matches urgency.</p>
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
      resultEl.textContent = selectedPriority === 'standard'
        ? 'Request submitted. Recorded in the governance chain.'
        : 'Request received. Resolution continues in request history; the priority slot is available again.';
      pane.querySelector('#cm-request-text').value = '';
      // Refresh to show the new request in history
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
    <div class="cm-pane-header">${_esc(title)}</div>
    <div class="cm-pane-body">
      <div class="cm-slot-count">${inUse} of ${totalSlots} slots in use</div>
      <div class="cm-slot-cards"></div>
    </div>
  `;
  setTooltip(pane.querySelector('.cm-pane-header'), tooltip);

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
    const statusLabel = _statusLabel(status);
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
  const tooltip = 'Shows current telemetry participation and recent summary transmissions. Payload content stays out of the governance chain; remote submissions record destination, payload hash, and payload size.';

  const traffic = d.telemetry_traffic || [];
  const lastSent = traffic.find(t => t.direction !== 'inbound');
  const lastRecv = traffic.find(t => t.direction === 'inbound');

  pane.innerHTML = `
    <div class="cm-pane-accent cm-accent-green"></div>
    <div class="cm-pane-header">Telemetry</div>
    <div class="cm-pane-body">
      <div class="cm-kv-list">
        <div class="cm-kv"><span class="cm-kv-label">Status</span><span class="cm-kv-value ${d.telemetry_opted_in ? 'cm-val-green' : 'cm-val-amber'}">${d.telemetry_opted_in ? 'Participating' : 'Declined'}</span></div>
        <div class="cm-kv"><span class="cm-kv-label">Last sent</span><span class="cm-kv-value">${lastSent ? _formatHumanDate(lastSent.timestamp_utc) : 'N/A'}</span></div>
        <div class="cm-kv"><span class="cm-kv-label">Last received</span><span class="cm-kv-value">${lastRecv ? _formatHumanDate(lastRecv.timestamp_utc) : 'N/A'}</span></div>
      </div>
      <p class="cm-pane-note">${d.telemetry_opted_in ? 'Bidirectional channel active.' : 'Channel inactive.'} You can change your preference at any time.</p>
    </div>
  `;
  setTooltip(pane.querySelector('.cm-pane-header'), tooltip);

  pane.addEventListener('click', () => _openTelemetryDetail(state, d));
  return pane;
}

// ---------- Request history pane ----------

function _buildHistoryPane(state, d) {
  const allHistory = _historyRequests(d).sort((a, b) =>
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
      const statusClass = status === 'resolved' ? 'cm-status-green' : status === 'in_progress' ? 'cm-status-amber' : 'cm-status-muted';
      tr.innerHTML = `
        <td class="cm-hist-date">${_esc(_formatHumanDate(req.timestamp_utc))}</td>
        <td>${_esc(summary)}</td>
        <td><span class="${statusClass}">${_esc(_statusLabel(status))}</span></td>
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
  const statusLabel = _statusLabel(status);

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
        <span class="cm-response-text">${status === 'acknowledged' || status === 'received' ? 'Request acknowledged. Resolution will continue separately; this slot is already available for another request.' : 'Request received and queued.'}</span>
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
        <td><span class="${statusClass}">${_esc(_statusLabel(status))}</span></td>
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

function _statusLabel(status) {
  if (status === 'in_progress') return 'In progress';
  if (status === 'awaiting_response') return 'Awaiting response';
  if (status === 'acknowledged') return 'Acknowledged';
  if (status === 'resolved') return 'Resolved';
  return 'Received';
}

function _historyRequests(data) {
  if (Array.isArray(data.history) && data.history.length) return data.history;
  const resolved = data.resolved || [];
  const standard = data.standard || [];
  const activeMedium = data.active_medium || [];
  const activeHigh = data.active_high || [];
  return [...activeHigh, ...activeMedium, ...resolved, ...standard];
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
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
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
  .cm-val-green { color: #3fb950; }
  .cm-val-amber { color: #d29922; }

  /* ---- Pane ---- */
  .cm-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .cm-pane-clickable {
    cursor: pointer;
    transition: border-color 0.12s;
  }
  .cm-pane-clickable:hover {
    border-color: rgba(102,153,204,0.3);
  }
  .cm-pane-accent { height: 6px; }
  .cm-accent-green { background: #3fb950; }
  .cm-accent-amber { background: #d29922; }
  .cm-accent-red { background: #f85149; }
  .cm-pane-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
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
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 10px 12px;
    resize: vertical;
    box-sizing: border-box;
    margin-bottom: 10px;
  }
  .cm-textarea:focus { outline: 2px solid #6699cc; outline-offset: 1px; }
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
    border-radius: 2px;
    color: #8b919a;
    font-size: 0.75rem;
    padding: 5px 12px;
    cursor: pointer;
    transition: all 0.12s;
    font-family: "Inter", system-ui, sans-serif;
  }
  .cm-pri-btn:hover:not(:disabled) { color: #e4e6eb; }
  .cm-pri-active {
    background: rgba(102,153,204,0.12);
    color: #6699cc;
    border-color: rgba(102,153,204,0.4);
    font-weight: 600;
  }
  .cm-pri-medium { border-color: rgba(210,153,34,0.3); }
  .cm-pri-medium.cm-pri-active { background: rgba(210,153,34,0.12); color: #d29922; border-color: rgba(210,153,34,0.5); }
  .cm-pri-high { border-color: rgba(248,81,73,0.3); }
  .cm-pri-high.cm-pri-active { background: rgba(248,81,73,0.12); color: #f85149; border-color: rgba(248,81,73,0.5); }
  .cm-pri-disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .cm-btn {
    border: none;
    border-radius: 2px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 7px 20px;
    cursor: pointer;
    transition: background 0.1s;
    white-space: nowrap;
  }
  .cm-btn-submit { background: #3fb950; color: #fff; }
  .cm-btn-submit:hover { background: #16a34a; }
  .cm-btn-toggle {
    background: rgba(102,153,204,0.12);
    color: #6699cc;
    border: 1px solid rgba(102,153,204,0.3);
  }
  .cm-btn-toggle:hover { background: rgba(102,153,204,0.20); }
  .cm-result-success { color: #3fb950; font-size: 0.82rem; margin-top: 8px; }
  .cm-result-error { color: #d29922; font-size: 0.82rem; margin-top: 8px; }
  .cm-btn-dismiss {
    background: rgba(255,255,255,0.06);
    color: #8b919a;
    border: 1px solid rgba(255,255,255,0.10);
    padding: 4px 10px;
    font-size: 0.75rem;
    border-radius: 2px;
    cursor: pointer;
  }
  .cm-btn-dismiss:hover { color: #e4e6eb; background: rgba(255,255,255,0.10); }

  /* ---- Update notifications ---- */
  .cm-update-pane { margin-bottom: 16px; }
  .cm-update-card {
    padding: 12px 14px;
    background: rgba(34, 197, 94, 0.04);
    border: 1px dashed rgba(34, 197, 94, 0.15);
    border-radius: 2px;
    margin-bottom: 8px;
  }
  .cm-update-msg { font-size: 0.85rem; color: #e4e6eb; line-height: 1.5; margin-bottom: 8px; }
  .cm-update-meta { display: flex; justify-content: space-between; align-items: center; }
  .cm-update-date { font-size: 0.75rem; color: #6b7280; }

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
    border-radius: 2px;
    padding: 12px 14px;
  }
  .cm-slot-occupied {
    background: #1a1d23;
    border: 1px dashed rgba(255,255,255,0.12);
    cursor: pointer;
    transition: border-color 0.12s;
  }
  .cm-slot-occupied:hover {
    border-color: rgba(102,153,204,0.3);
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
  .cm-status-green { color: #3fb950; }
  .cm-status-amber { color: #d29922; }
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
  .cm-hist-clickable:hover { background: rgba(102,153,204,0.06); }

  /* Priority tags */
  .cm-pri-tag {
    display: inline-block;
    font-size: 0.62rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 1px 8px;
  }
  .cm-pri-tag-standard { color: #8b919a; }
  .cm-pri-tag-medium { color: #d29922; }
  .cm-pri-tag-high { color: #f85149; }

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
    border-radius: 2px 2px 0 0;
  }
  .cm-gc-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
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
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
  }
  .cm-paired-header {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6699cc;
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
  }
  .cm-dir-out { color: #6699cc; }
  .cm-dir-in { color: #3fb950; }

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
    color: #d29922;
    background: rgba(210,153,34,0.10);
    padding: 12px 16px;
    border-radius: 2px;
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
