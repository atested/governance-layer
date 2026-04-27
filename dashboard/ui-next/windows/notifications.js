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
import { openLicensingWindow } from './licensing.js';
import { openCommunicationsWindowWithCompose } from './communications.js';
import '../components/pill.js';
import '../components/loading-indicator.js';

/** Severity display order (highest first) */
const SEVERITY_ORDER = { security: 0, critical: 1, routine: 2, informational: 3 };

/** Severity colors */
const SEVERITY_COLORS = {
  security: '#f85149',
  critical: '#d29922',
  routine: '#6699cc',
  informational: '#8b919a',
};

/**
 * Open the Notifications window.
 * @param {HTMLElement|null} trigger
 */
export function openNotificationsWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Notifications', 'Security alerts and system notices', trigger, content);
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
      <atd-loading-indicator label="Loading notifications"></atd-loading-indicator>
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

const LICENSE_NOTIFICATION_TYPES = new Set([
  'license_revoked', 'license_delivered',
  'license_expiration_warning', 'license_modified',
]);

function _isLicenseNotification(notif) {
  return LICENSE_NOTIFICATION_TYPES.has(notif.type);
}

function _licenseMessage(notif) {
  const p = notif.payload || {};
  switch (notif.type) {
    case 'license_revoked':
      return `Your license has been revoked. Reason: ${p.reason || 'N/A'}. Your installation has reverted to Personal tier. All governance functions continue normally.`;
    case 'license_expiration_warning':
      return `Your ${p.tier || 'N/A'} license expires on ${(p.expiry || '').slice(0, 10) || 'N/A'}. Without renewal, your installation will revert to Personal tier. Governance continues fully \u2014 proxy still governs, chain still records, all safety features remain active.`;
    case 'license_delivered':
      return `Your license has been updated. You now have a ${p.tier || 'N/A'} license, valid until ${(p.expiry || '').slice(0, 10) || 'N/A'}.`;
    case 'license_modified':
      return `Your license has been modified. Previous tier: ${p.previous_tier || 'N/A'}. New tier: ${p.new_tier || 'N/A'}. Reason: ${p.reason || 'N/A'}.`;
    default:
      return notif.message || '';
  }
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

    // License notifications get type-specific rendering
    if (_isLicenseNotification(notif)) {
      card.innerHTML = `
        <div class="nf-card-header">
          <span class="nf-severity-label" style="color:${color}">${_esc((notif.severity || 'info').toUpperCase())}</span>
          <span class="nf-card-title">${_esc(notif.title || '--')}</span>
        </div>
        <p class="nf-card-message">${_esc(_licenseMessage(notif))}</p>
      `;

      const actions = document.createElement('div');
      actions.className = 'nf-card-actions';
      const p = notif.payload || {};

      // Reply button — revoked, expiration_warning, modified
      if (['license_revoked', 'license_expiration_warning', 'license_modified'].includes(notif.type)) {
        const replyBtn = document.createElement('atd-pill');
        replyBtn.setAttribute('variant', 'outline');
        replyBtn.textContent = 'Reply';
        replyBtn.addEventListener('click', () => {
          const subjectMap = {
            license_revoked: `License revocation \u2014 ${p.license_id || 'N/A'}`,
            license_expiration_warning: `License renewal \u2014 ${p.license_id || 'N/A'}`,
            license_modified: `License modification \u2014 ${p.license_id || 'N/A'}`,
          };
          openCommunicationsWindowWithCompose(card, {
            subject: subjectMap[notif.type] || 'License inquiry',
            context: [
              `License ID: ${p.license_id || 'N/A'}`,
              `Tier: ${p.tier || p.new_tier || 'N/A'}`,
              `Timestamp: ${p.timestamp_utc || 'N/A'}`,
              p.reason ? `Reason: ${p.reason}` : '',
            ].filter(Boolean).join('\n'),
          });
        });
        actions.appendChild(replyBtn);
      }

      // Renew button — expiration_warning only
      if (notif.type === 'license_expiration_warning') {
        const renewBtn = document.createElement('atd-pill');
        renewBtn.setAttribute('variant', 'outline');
        renewBtn.textContent = 'Renew';
        renewBtn.addEventListener('click', () => {
          openLicensingWindow(card);
        });
        actions.appendChild(renewBtn);
      }

      // Dismiss button — non-persistent only
      if (!notif.persistent) {
        const dismissBtn = document.createElement('atd-pill');
        dismissBtn.setAttribute('variant', 'outline');
        dismissBtn.textContent = 'Dismiss';
        dismissBtn.addEventListener('click', async () => {
          const res = await api.postDismissNotification({ notification_id: notif.id });
          if (res.ok) {
            card.remove();
            if (!list.querySelector('.nf-card')) {
              list.innerHTML = '<p class="nf-empty">No active notifications</p>';
            }
          }
        });
        actions.appendChild(dismissBtn);
      }

      if (actions.children.length > 0) {
        card.appendChild(actions);
      }
      if (notif.persistent && actions.children.length === 0) {
        const note = document.createElement('p');
        note.className = 'nf-persistent-note';
        note.textContent = 'This notification cannot be dismissed.';
        card.appendChild(note);
      }

      list.appendChild(card);
      continue;  // skip generic path
    }

    // Generic notifications
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
    background: #22262e; border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px; padding: 14px 18px; margin-bottom: 10px;
  }
  .nf-severity-security { border-left: 3px solid #f85149; }
  .nf-severity-critical { border-left: 3px solid #d29922; }
  .nf-severity-routine { border-left: 3px solid #6699cc; }
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
    color: #d29922;
    padding: 12px 16px; border-radius: 2px; font-size: 0.82rem;
  }
`;
document.head.appendChild(nfStyles);
