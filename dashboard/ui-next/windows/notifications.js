/**
 * Notifications window — child window (depth 1).
 * Spec v2 section 7.8.
 *
 * Lists active notifications with severity styling. Operators can
 * dismiss individual notifications. Opening the window records a
 * notifications_viewed event.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import '../components/pill.js';

/** Severity display order (highest first) */
const SEVERITY_ORDER = { security: 0, critical: 1, routine: 2, informational: 3 };

/** Severity colors */
const SEVERITY_COLORS = {
  security: '#ef4444',
  critical: '#f59e42',
  routine: '#5b8af5',
  informational: '#8b919a',
};

/**
 * Open the Notifications window.
 * @param {HTMLElement|null} trigger
 */
export function openNotificationsWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Notifications', trigger, content);
  if (!result) return;

  const state = { el: content };
  _loadData(state);
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'nf-content';
  el.innerHTML = `
    <div class="nf-header">
      <span class="nf-eyebrow">System</span>
      <span class="nf-heading">Notifications</span>
    </div>
    <div id="nf-list">
      <p class="nf-loading">Loading...</p>
    </div>
  `;
  return el;
}

async function _loadData(state) {
  const res = await api.getNotifications();
  const list = state.el.querySelector('#nf-list');

  if (!res.ok) {
    list.innerHTML = `<div class="nf-error">${_esc(res.error)}</div>`;
    return;
  }

  const notifications = res.data.notifications || [];

  // Record that notifications were viewed
  if (notifications.length > 0) {
    api.postNotificationsViewed({ count: notifications.length }).catch(() => {});
  }

  _renderNotifications(list, notifications, state);
}

function _renderNotifications(list, notifications, state) {
  list.innerHTML = '';

  if (!notifications.length) {
    list.innerHTML = '<p class="nf-empty">No active notifications</p>';
    return;
  }

  // Sort by severity
  const sorted = [...notifications].sort(
    (a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9)
  );

  for (const notif of sorted) {
    const card = document.createElement('div');
    card.className = `nf-card nf-severity-${notif.severity || 'informational'}`;

    const color = SEVERITY_COLORS[notif.severity] || SEVERITY_COLORS.informational;
    card.innerHTML = `
      <div class="nf-card-header">
        <span class="nf-severity-label" style="color:${color}">${_esc((notif.severity || 'info').toUpperCase())}</span>
        <span class="nf-card-title">${_esc(notif.title || '--')}</span>
      </div>
      <p class="nf-card-message">${_esc(notif.message || '')}</p>
    `;

    if (!notif.persistent) {
      const actions = document.createElement('div');
      actions.className = 'nf-card-actions';
      const dismissBtn = document.createElement('atd-pill');
      dismissBtn.setAttribute('variant', 'outline');
      dismissBtn.textContent = 'Dismiss';
      dismissBtn.addEventListener('click', async () => {
        const res = await api.postDismissNotification({ notification_id: notif.id });
        if (res.ok) {
          card.remove();
          // Check if list is now empty
          if (!list.querySelector('.nf-card')) {
            list.innerHTML = '<p class="nf-empty">No active notifications</p>';
          }
        }
      });
      actions.appendChild(dismissBtn);
      card.appendChild(actions);
    } else {
      const note = document.createElement('p');
      note.className = 'nf-persistent-note';
      note.textContent = 'This notification cannot be dismissed.';
      card.appendChild(note);
    }

    list.appendChild(card);
  }
}

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, trigger, content });
  return modalManager.open({ title, trigger, content });
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// Styles
const nfStyles = document.createElement('style');
nfStyles.textContent = `
  .nf-content { font-family: "Inter", system-ui, sans-serif; }
  .nf-header { margin-bottom: 16px; }
  .nf-eyebrow {
    display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #8b919a; margin-bottom: 4px;
  }
  .nf-heading { font-size: 1.25rem; font-weight: 600; color: #e4e6eb; }
  .nf-card {
    background: #22262e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 14px 18px; margin-bottom: 10px;
  }
  .nf-severity-security { border-left: 3px solid #ef4444; }
  .nf-severity-critical { border-left: 3px solid #f59e42; }
  .nf-severity-routine { border-left: 3px solid #5b8af5; }
  .nf-severity-informational { border-left: 3px solid #8b919a; }
  .nf-card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
  .nf-severity-label { font-size: 0.72rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
  .nf-card-title { font-size: 0.88rem; font-weight: 600; color: #e4e6eb; }
  .nf-card-message { font-size: 0.82rem; color: #8b919a; margin: 0 0 8px; }
  .nf-card-actions { display: flex; gap: 8px; }
  .nf-persistent-note { font-size: 0.72rem; color: #8b919a; font-style: italic; margin: 0; }
  .nf-loading, .nf-empty {
    color: #8b919a; font-size: 0.82rem; text-align: center; padding: 40px 0;
    margin: 0; font-style: italic;
  }
  .nf-error {
    color: #f59e42; background: rgba(245,158,66,0.10);
    padding: 12px 16px; border-radius: 8px; font-size: 0.82rem;
  }
`;
document.head.appendChild(nfStyles);
