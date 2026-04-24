/**
 * Identity Session window — child window (depth 1).
 * Spec v2 section 7.11.
 *
 * Opens when identity is configured and operator clicks the chrome
 * identity zone. Shows session state, timers, and manual lock button.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { updateIdentityZone } from '../chrome.js';
import '../components/status-card.js';
import '../components/status-grid.js';
import '../components/pill.js';
import '../components/loading-indicator.js';

/** Timer interval reference for countdown */
let _timerInterval = null;

/**
 * Open the Identity Session window.
 * @param {HTMLElement|null} trigger
 */
export function openIdentitySessionWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Identity Session', 'Your active operator session', trigger, content);
  if (!result) return;

  const state = { el: content };
  _loadData(state);
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'ids-content';
  el.innerHTML = `
    <div class="ids-header">
      <span class="ids-eyebrow">Operator</span>
      <span class="ids-heading">Identity Session</span>
      <span class="ids-status" id="ids-status-badge"></span>
    </div>
    <div id="ids-sections">
      <atd-loading-indicator label="Loading session"></atd-loading-indicator>
    </div>
  `;
  return el;
}

async function _loadData(state) {
  // Clear any previous timer
  if (_timerInterval) { clearInterval(_timerInterval); _timerInterval = null; }

  const res = await api.getIdentitySession();
  const sections = state.el.querySelector('#ids-sections');

  if (!res.ok) {
    sections.innerHTML = `<div class="ids-error">${_esc(res.error)}</div>`;
    return;
  }

  const session = res.data;

  if (!session.configured) {
    _renderUnconfigured(state);
    return;
  }

  _renderConfigured(state, session);
}

function _renderUnconfigured(state) {
  const sections = state.el.querySelector('#ids-sections');
  const badge = state.el.querySelector('#ids-status-badge');
  badge.textContent = 'NOT CONFIGURED';
  badge.className = 'ids-status ids-status-unconfigured';

  sections.innerHTML = `
    <div class="ids-card">
      <p class="ids-text">Operator identity is not configured on this system.</p>
      <p class="ids-text ids-text-muted">
        Set up identity by running <code>atested activate &lt;license-key&gt;</code>
        in your terminal. See the Identity Setup window for detailed instructions.
      </p>
    </div>
  `;
}

function _renderConfigured(state, session) {
  const sections = state.el.querySelector('#ids-sections');
  const badge = state.el.querySelector('#ids-status-badge');

  if (session.locked) {
    badge.textContent = 'LOCKED';
    badge.className = 'ids-status ids-status-locked';
  } else {
    badge.textContent = 'UNLOCKED';
    badge.className = 'ids-status ids-status-unlocked';
  }

  sections.innerHTML = '';

  // Operator info section
  const infoGrid = document.createElement('atd-status-grid');
  const nameCard = document.createElement('atd-status-card');
  nameCard.setAttribute('label', 'Operator');
  nameCard.setAttribute('value', session.operator_name || '--');
  infoGrid.appendChild(nameCard);

  if (session.operator_email) {
    const emailCard = document.createElement('atd-status-card');
    emailCard.setAttribute('label', 'Email');
    emailCard.setAttribute('value', session.operator_email);
    infoGrid.appendChild(emailCard);
  }

  const stateCard = document.createElement('atd-status-card');
  stateCard.setAttribute('label', 'Session State');
  stateCard.setAttribute('value', session.locked ? 'Locked' : 'Unlocked');
  stateCard.setAttribute('variant', session.locked ? 'warning' : 'success');
  infoGrid.appendChild(stateCard);

  sections.appendChild(infoGrid);

  // Timers section (unlocked only)
  if (!session.locked) {
    const timerSection = document.createElement('div');
    timerSection.className = 'ids-section';
    timerSection.innerHTML = '<h3 class="ids-section-title">Session Timers</h3>';

    const timerGrid = document.createElement('atd-status-grid');

    const ceilingCard = document.createElement('atd-status-card');
    ceilingCard.setAttribute('label', 'Hard Ceiling');
    ceilingCard.setAttribute('value', _formatTime(session.ceiling_remaining_s));
    ceilingCard.id = 'ids-ceiling-card';
    if (session.ceiling_remaining_s != null && session.ceiling_remaining_s < 300) {
      ceilingCard.setAttribute('variant', 'warning');
    }
    timerGrid.appendChild(ceilingCard);

    const idleCard = document.createElement('atd-status-card');
    idleCard.setAttribute('label', 'Idle Timer');
    idleCard.setAttribute('value', _formatTime(session.idle_remaining_s));
    idleCard.id = 'ids-idle-card';
    if (session.idle_remaining_s != null && session.idle_remaining_s < 300) {
      idleCard.setAttribute('variant', 'warning');
    }
    timerGrid.appendChild(idleCard);

    timerSection.appendChild(timerGrid);
    sections.appendChild(timerSection);

    // Start countdown timer (updates every second)
    let ceiling = session.ceiling_remaining_s;
    let idle = session.idle_remaining_s;
    _timerInterval = setInterval(() => {
      if (ceiling != null && ceiling > 0) {
        ceiling--;
        const cc = state.el.querySelector('#ids-ceiling-card');
        if (cc) cc.setAttribute('value', _formatTime(ceiling));
        if (ceiling < 300 && cc) cc.setAttribute('variant', 'warning');
      }
      if (idle != null && idle > 0) {
        idle--;
        const ic = state.el.querySelector('#ids-idle-card');
        if (ic) ic.setAttribute('value', _formatTime(idle));
        if (idle < 300 && ic) ic.setAttribute('variant', 'warning');
      }
      // Auto-refresh if either timer hits zero
      if ((ceiling != null && ceiling <= 0) || (idle != null && idle <= 0)) {
        clearInterval(_timerInterval);
        _timerInterval = null;
        _loadData(state);
      }
    }, 1000);
  }

  // Actions section
  const actionsSection = document.createElement('div');
  actionsSection.className = 'ids-section';

  if (session.locked) {
    actionsSection.innerHTML = `
      <div class="ids-card">
        <p class="ids-text">Session is locked. To unlock, run <code>atested unlock</code>
        in your terminal and enter your TOTP code.</p>
      </div>
    `;
  } else {
    actionsSection.innerHTML = '<h3 class="ids-section-title">Actions</h3>';
    const lockBtn = document.createElement('atd-pill');
    lockBtn.setAttribute('variant', 'outline');
    lockBtn.textContent = 'Lock Session';
    lockBtn.addEventListener('click', async () => {
      lockBtn.textContent = 'Locking...';
      const res = await api.postIdentityLock();
      if (res.ok) {
        // Update chrome zone immediately
        updateIdentityZone({ configured: true, operator_name: session.operator_name, locked: true });
        // Refresh window content
        _loadData(state);
      } else {
        lockBtn.textContent = 'Lock Session';
      }
    });
    actionsSection.appendChild(lockBtn);
  }

  sections.appendChild(actionsSection);

  // Credential management section
  const credSection = document.createElement('div');
  credSection.className = 'ids-section';
  credSection.innerHTML = `
    <h3 class="ids-section-title">Credential Management</h3>
    <div class="ids-card">
      <div class="ids-cred-links">
        <div class="ids-cred-item">
          <strong>Re-enrollment</strong>
          <p>To re-enroll with a new TOTP seed, run <code>atested re-enroll</code></p>
        </div>
        <div class="ids-cred-item">
          <strong>Key Rotation</strong>
          <p>To rotate credentials after re-licensing, run <code>atested activate &lt;new-key&gt;</code></p>
        </div>
        <div class="ids-cred-item">
          <strong>Recovery</strong>
          <p>Lost your authenticator? Contact your organization admin for credential recovery.</p>
        </div>
      </div>
    </div>
  `;
  sections.appendChild(credSection);
}

function _formatTime(seconds) {
  if (seconds == null) return '--';
  if (seconds <= 0) return '0:00';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, subtitle, trigger, content });
  return modalManager.open({ title, subtitle, trigger, content });
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// Styles
const idsStyles = document.createElement('style');
idsStyles.textContent = `
  .ids-content { font-family: "Inter", system-ui, sans-serif; }
  .ids-header { margin-bottom: 16px; }
  .ids-eyebrow {
    display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #8b919a; margin-bottom: 4px;
  }
  .ids-heading { font-size: 1.25rem; font-weight: 600; color: #e4e6eb; margin-right: 12px; }
  .ids-status {
    display: inline-block; font-size: 0.72rem; font-weight: 600;
    padding: 2px 10px; border-radius: 2px;
  }
  .ids-status-locked { color: #f5a623; }
  .ids-status-unlocked { color: #22c55e; }
  .ids-status-unconfigured { color: #8b919a; }
  .ids-section { margin-top: 20px; }
  .ids-section-title {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #60a5fa; margin: 0 0 10px; font-weight: 600;
  }
  .ids-card {
    background: #22262e; border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px; padding: 14px 18px; margin-bottom: 10px;
  }
  .ids-text { font-size: 0.82rem; color: #e4e6eb; line-height: 1.6; margin: 0 0 8px; }
  .ids-text:last-child { margin-bottom: 0; }
  .ids-text-muted { color: #8b919a; }
  .ids-text code {
    background: #1a1d23; padding: 2px 6px; border-radius: 2px;
    font-family: "JetBrains Mono", monospace; font-size: 0.78rem; color: #60a5fa;
  }
  .ids-loading { color: #8b919a; font-size: 0.82rem; text-align: center; padding: 40px 0; margin: 0; }
  .ids-error {
    color: #f5a623;
    padding: 12px 16px; border-radius: 2px; font-size: 0.82rem;
  }
  .ids-cred-links { display: flex; flex-direction: column; gap: 12px; }
  .ids-cred-item strong { display: block; font-size: 0.82rem; color: #e4e6eb; margin-bottom: 2px; }
  .ids-cred-item p { font-size: 0.78rem; color: #8b919a; margin: 0; }
  .ids-cred-item code {
    background: #1a1d23; padding: 2px 6px; border-radius: 2px;
    font-family: "JetBrains Mono", monospace; font-size: 0.72rem; color: #60a5fa;
  }
`;
document.head.appendChild(idsStyles);
