/**
 * Feedback window — child window (depth 1).
 * Spec v2 section 7.7.
 *
 * Submit feedback, manage telemetry opt-in, view feedback
 * and telemetry history tables.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import '../components/data-table.js';
import '../components/pill.js';

/**
 * Open the Feedback window.
 * @param {HTMLElement|null} trigger
 */
export function openFeedbackWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Feedback', trigger, content);
  if (!result) return;

  const state = { el: content };
  _wireControls(state);
  _loadData(state);
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'fb-content';
  el.innerHTML = `
    <div class="fb-header">
      <span class="fb-eyebrow">Community</span>
      <span class="fb-heading">Feedback & Telemetry</span>
    </div>

    <div class="fb-card">
      <h3 class="fb-section-title">Send Feedback</h3>
      <div class="fb-form">
        <textarea class="fb-textarea" id="fb-message" placeholder="Your feedback" rows="3"></textarea>
        <textarea class="fb-textarea" id="fb-experience" placeholder="What has Atested helped you avoid or improve? (optional)" rows="2"></textarea>
        <div class="fb-checkboxes">
          <label class="fb-checkbox">
            <input type="checkbox" id="fb-permission"> Atested may use this feedback anonymously in product materials
          </label>
          <label class="fb-checkbox">
            <input type="checkbox" id="fb-remote"> Send to Atested team (via signed artifact)
          </label>
        </div>
        <atd-pill variant="primary" id="fb-submit-btn">Submit Feedback</atd-pill>
        <div id="fb-submit-result"></div>
      </div>
    </div>

    <div class="fb-card">
      <h3 class="fb-section-title">Telemetry Controls</h3>
      <div class="fb-telemetry-controls">
        <label class="fb-checkbox">
          <input type="checkbox" id="fb-optin"> Share anonymous usage data
        </label>
        <atd-pill variant="outline" id="fb-send-telemetry">Send Telemetry Now</atd-pill>
        <div id="fb-telemetry-result"></div>
      </div>
    </div>

    <div class="fb-section">
      <h3 class="fb-section-title">Feedback History</h3>
      <div id="fb-feedback-table">
        <p class="fb-loading">Loading...</p>
      </div>
    </div>

    <div class="fb-section">
      <h3 class="fb-section-title">Telemetry History</h3>
      <div id="fb-telemetry-table">
        <p class="fb-loading">Loading...</p>
      </div>
    </div>
  `;
  return el;
}

function _wireControls(state) {
  const el = state.el;
  el.querySelector('#fb-submit-btn').addEventListener('click', () => _submitFeedback(state));
  el.querySelector('#fb-send-telemetry').addEventListener('click', () => _sendTelemetry(state));
  el.querySelector('#fb-optin').addEventListener('change', (e) => _toggleOptIn(state, e.target.checked));
}

async function _loadData(state) {
  const [feedbackRes, telemetryRes, statusRes] = await Promise.all([
    api.getFeedback(),
    api.getTelemetry(),
    api.getTelemetryStatus(),
  ]);

  // Opt-in status
  if (statusRes.ok) {
    state.el.querySelector('#fb-optin').checked = statusRes.data.opted_in || false;
  }

  // Feedback history
  _renderFeedbackHistory(state.el.querySelector('#fb-feedback-table'), feedbackRes);

  // Telemetry history
  _renderTelemetryHistory(state.el.querySelector('#fb-telemetry-table'), telemetryRes);
}

function _renderFeedbackHistory(wrap, res) {
  wrap.innerHTML = '';
  if (!res.ok) {
    wrap.innerHTML = `<div class="fb-error">${_esc(res.error)}</div>`;
    return;
  }

  const artifacts = res.data.artifacts || [];
  if (!artifacts.length) {
    wrap.innerHTML = '<p class="fb-empty">No feedback submitted yet</p>';
    return;
  }

  const table = document.createElement('atd-data-table');
  table.setAttribute('columns', JSON.stringify([
    { key: 'timestamp', label: 'Timestamp', sortable: false, width: '160px' },
    { key: 'message', label: 'Message', sortable: false },
    { key: 'has_experience', label: 'Experience', sortable: false, width: '80px' },
    { key: 'signed', label: 'Signed', sortable: false, width: '70px' },
    { key: 'hash', label: 'Hash', sortable: false, width: '160px' },
  ]));
  table.setAttribute('sortable', 'false');
  table.setAttribute('page-size', '20');

  table.data = artifacts.map(a => ({
    timestamp: _formatTime(a.timestamp || a.created_at),
    message: _truncate(a.message || a.feedback_message || '--', 80),
    has_experience: (a.experience_note || a.experience) ? 'Yes' : '--',
    signed: a.signed ? 'Yes' : '--',
    hash: _truncate(a.artifact_hash || a.hash || '--', 20),
  }));
  table.totalCount = artifacts.length;

  wrap.appendChild(table);
}

function _renderTelemetryHistory(wrap, res) {
  wrap.innerHTML = '';
  if (!res.ok) {
    wrap.innerHTML = `<div class="fb-error">${_esc(res.error)}</div>`;
    return;
  }

  const artifacts = res.data.artifacts || [];
  if (!artifacts.length) {
    wrap.innerHTML = '<p class="fb-empty">No telemetry submitted yet</p>';
    return;
  }

  const table = document.createElement('atd-data-table');
  table.setAttribute('columns', JSON.stringify([
    { key: 'timestamp', label: 'Timestamp', sortable: false, width: '160px' },
    { key: 'allow', label: 'ALLOW', sortable: false, width: '70px' },
    { key: 'deny', label: 'DENY', sortable: false, width: '70px' },
    { key: 'deterministic', label: 'Deterministic', sortable: false, width: '100px' },
    { key: 'judgment', label: 'Judgment', sortable: false, width: '80px' },
    { key: 'signed', label: 'Signed', sortable: false, width: '70px' },
    { key: 'hash', label: 'Hash', sortable: false, width: '160px' },
  ]));
  table.setAttribute('sortable', 'false');
  table.setAttribute('page-size', '20');

  table.data = artifacts.map(a => ({
    timestamp: _formatTime(a.timestamp || a.created_at),
    allow: String(a.total_allow ?? a.allow_count ?? '--'),
    deny: String(a.total_deny ?? a.deny_count ?? '--'),
    deterministic: String(a.total_deterministic ?? a.deterministic_count ?? '--'),
    judgment: String(a.total_judgment ?? a.judgment_count ?? '--'),
    signed: a.signed ? 'Yes' : '--',
    hash: _truncate(a.artifact_hash || a.hash || '--', 20),
  }));
  table.totalCount = artifacts.length;

  wrap.appendChild(table);
}

async function _submitFeedback(state) {
  const el = state.el;
  const message = el.querySelector('#fb-message').value.trim();
  const resultEl = el.querySelector('#fb-submit-result');

  if (!message) {
    _showResult(resultEl, 'Please enter feedback', 'error');
    return;
  }

  const res = await api.postFeedbackSubmit({
    message,
    experience_note: el.querySelector('#fb-experience').value.trim() || undefined,
    permission_to_use: el.querySelector('#fb-permission').checked,
    send_to_remote: el.querySelector('#fb-remote').checked,
  });

  if (res.ok) {
    _showResult(resultEl, 'Feedback submitted', 'success');
    el.querySelector('#fb-message').value = '';
    el.querySelector('#fb-experience').value = '';
    _loadData(state);
  } else {
    _showResult(resultEl, res.error, 'error');
  }
}

async function _sendTelemetry(state) {
  const resultEl = state.el.querySelector('#fb-telemetry-result');
  resultEl.textContent = 'Sending...';

  const res = await api.postTelemetrySubmit({ send_to_remote: true });
  if (res.ok) {
    _showResult(resultEl, 'Telemetry submitted', 'success');
    _loadData(state);
  } else {
    _showResult(resultEl, res.error, 'error');
  }
}

async function _toggleOptIn(state, optedIn) {
  const resultEl = state.el.querySelector('#fb-telemetry-result');
  const res = await api.postTelemetryOptIn({ opted_in: optedIn });
  if (res.ok) {
    _showResult(resultEl, `Telemetry ${optedIn ? 'enabled' : 'disabled'}`, 'success');
  } else {
    _showResult(resultEl, res.error, 'error');
    // Revert checkbox
    state.el.querySelector('#fb-optin').checked = !optedIn;
  }
}

function _showResult(el, msg, type) {
  el.className = type === 'success' ? 'fb-result-success' : 'fb-result-error';
  el.textContent = msg;
  setTimeout(() => { el.textContent = ''; el.className = ''; }, 5000);
}

function _truncate(str, len) {
  if (!str) return '--';
  return str.length > len ? str.substring(0, len) + '...' : str;
}

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, trigger, content });
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
const fbStyles = document.createElement('style');
fbStyles.textContent = `
  .fb-content { font-family: "Inter", system-ui, sans-serif; }
  .fb-header { margin-bottom: 16px; }
  .fb-eyebrow {
    display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #8b919a; margin-bottom: 4px;
  }
  .fb-heading { font-size: 1.25rem; font-weight: 600; color: #e4e6eb; }
  .fb-section-title {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #5b8af5; margin: 0 0 10px; font-weight: 600;
  }
  .fb-card {
    background: #22262e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 16px 20px; margin-bottom: 20px;
  }
  .fb-form { display: flex; flex-direction: column; gap: 10px; }
  .fb-textarea {
    background: #1a1d23; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px; color: #e4e6eb; font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem; padding: 8px 10px; resize: vertical;
  }
  .fb-textarea:focus { outline: 2px solid #5b8af5; outline-offset: 1px; }
  .fb-checkboxes { display: flex; flex-direction: column; gap: 6px; }
  .fb-checkbox { font-size: 0.82rem; color: #e4e6eb; display: flex; align-items: center; gap: 6px; cursor: pointer; }
  .fb-checkbox input { accent-color: #5b8af5; }
  .fb-telemetry-controls { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
  .fb-result-success { color: #4ade80; font-size: 0.82rem; margin-top: 6px; }
  .fb-result-error { color: #f59e42; font-size: 0.82rem; margin-top: 6px; }
  .fb-section { margin-bottom: 20px; }
  .fb-loading, .fb-empty {
    color: #8b919a; font-size: 0.82rem; text-align: center; padding: 24px 0; margin: 0; font-style: italic;
  }
  .fb-error {
    color: #f59e42; background: rgba(245,158,66,0.10);
    padding: 12px 16px; border-radius: 8px; font-size: 0.82rem;
  }
`;
document.head.appendChild(fbStyles);
