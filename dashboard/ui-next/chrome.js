/**
 * Chrome bar for the Atested operator UI.
 * Fixed-position horizontal bar above all other content.
 * Spec v2 section 3.
 *
 * Zones: Identity (left), Brand (center-left), License + Notification indicator + Banner (right).
 * Phase 1: all zones render placeholder content.
 * Chrome interactions are system-level and exempt from the strict launcher rule.
 */

import { Z_INDEX } from './modal-manager.js';

export function renderChrome() {
  const chrome = document.createElement('div');
  chrome.id = 'chrome-bar';
  chrome.innerHTML = `
    <div class="chrome-zone chrome-identity" tabindex="0" role="button" aria-label="Identity">
      <span class="chrome-identity-text">Set up identity</span>
    </div>
    <div class="chrome-brand">Atested</div>
    <div class="chrome-right">
      <div class="chrome-zone chrome-license" tabindex="0" role="button" aria-label="License">
        <span class="chrome-license-tier">Trial</span>
        <span class="chrome-license-dot" style="background: var(--ok)"></span>
      </div>
      <div class="chrome-zone chrome-notif-indicator" tabindex="0" role="button" aria-label="Notifications">
        <span class="chrome-notif-icon">&#x1F514;</span>
        <span class="chrome-notif-count" style="display:none"></span>
      </div>
      <div class="chrome-banner"></div>
    </div>
  `;

  // Style the chrome bar
  Object.assign(chrome.style, {
    position: 'fixed',
    top: '0',
    left: '0',
    right: '0',
    height: '48px',
    zIndex: String(Z_INDEX.CHROME),
    background: '#2a2f38',
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    display: 'flex',
    alignItems: 'center',
    padding: '0 20px',
    fontFamily: '"Inter", system-ui, sans-serif',
    color: '#e4e6eb',
    fontSize: '0.88rem',
    userSelect: 'none',
  });

  return chrome;
}

/**
 * Update the notification indicator count badge.
 * @param {number} count
 */
export function updateNotificationCount(count) {
  const badge = document.querySelector('.chrome-notif-count');
  const indicator = document.querySelector('.chrome-notif-indicator');
  if (!badge || !indicator) return;
  if (count > 0) {
    badge.textContent = count > 99 ? '99+' : String(count);
    badge.style.display = 'flex';
    indicator.classList.add('has-notifications');
  } else {
    badge.style.display = 'none';
    indicator.classList.remove('has-notifications');
  }
}

/**
 * Show the highest-severity notification in the chrome banner.
 * @param {Object|null} notification - { id, severity, title, message } or null to hide
 * @param {Function} onDismiss - callback when dismiss is clicked
 */
export function showBanner(notification, onDismiss) {
  const banner = document.querySelector('.chrome-banner');
  if (!banner) return;
  banner.innerHTML = '';
  if (!notification) return;

  const bar = document.createElement('div');
  bar.className = `chrome-banner-bar severity-${notification.severity || 'routine'}`;
  bar.innerHTML = `<span class="chrome-banner-text"><strong>${_escChrome(notification.title)}</strong> — ${_escChrome(notification.message)}</span>`;

  if (!notification.persistent) {
    const dismiss = document.createElement('button');
    dismiss.className = 'chrome-banner-dismiss';
    dismiss.textContent = '\u2715';
    dismiss.setAttribute('aria-label', 'Dismiss');
    dismiss.addEventListener('click', (e) => {
      e.stopPropagation();
      banner.innerHTML = '';
      if (onDismiss) onDismiss(notification.id);
    });
    bar.appendChild(dismiss);
  }
  banner.appendChild(bar);
}

/**
 * Update the chrome identity zone to reflect operator identity state.
 * @param {Object} session - { configured, operator_name, locked, ceiling_remaining_s }
 */
export function updateIdentityZone(session) {
  const zone = document.querySelector('.chrome-identity');
  if (!zone) return;
  const text = zone.querySelector('.chrome-identity-text');
  if (!text) return;

  zone.classList.remove('identity-configured', 'identity-locked', 'identity-unlocked');

  if (!session || !session.configured) {
    text.textContent = 'Set up identity';
    return;
  }

  zone.classList.add('identity-configured');
  const name = session.operator_name || 'Operator';

  if (session.locked) {
    zone.classList.add('identity-locked');
    text.innerHTML = `<span class="chrome-id-lock">\u{1F512}</span> ${_escChrome(name)}`;
  } else {
    zone.classList.add('identity-unlocked');
    const remaining = _formatRemaining(session.ceiling_remaining_s);
    text.innerHTML = `<span class="chrome-id-unlock">\u{1F513}</span> ${_escChrome(name)} <span class="chrome-id-timer">${_escChrome(remaining)}</span>`;
  }
}

function _formatRemaining(seconds) {
  if (seconds == null || seconds <= 0) return '';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function _escChrome(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// Inject chrome-specific styles into the document
const chromeStyles = document.createElement('style');
chromeStyles.textContent = `
  .chrome-zone {
    cursor: pointer;
    padding: 4px 10px;
    border-radius: 6px;
    transition: background 0.15s;
  }
  .chrome-zone:hover {
    background: rgba(255, 255, 255, 0.06);
  }
  .chrome-zone:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .chrome-identity {
    margin-right: auto;
  }
  .chrome-identity-text {
    color: #8b919a;
    font-size: 0.82rem;
  }
  .chrome-identity:hover .chrome-identity-text {
    color: #5b8af5;
  }
  .chrome-identity.identity-configured .chrome-identity-text {
    color: #e4e6eb;
  }
  .chrome-id-lock {
    font-size: 0.72rem;
    margin-right: 2px;
    filter: grayscale(100%) brightness(0.8);
  }
  .chrome-id-unlock {
    font-size: 0.72rem;
    margin-right: 2px;
  }
  .chrome-id-timer {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
    margin-left: 6px;
  }
  .chrome-brand {
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: -0.02em;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
  }
  .chrome-right {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: auto;
  }
  .chrome-license {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
  }
  .chrome-license-tier {
    color: #8b919a;
  }
  .chrome-license-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }
  .chrome-notif-indicator {
    font-size: 0.9rem;
    position: relative;
  }
  .chrome-notif-icon {
    filter: grayscale(100%) brightness(0.7);
    font-size: 0.85rem;
  }
  .chrome-notif-count {
    position: absolute;
    top: -2px;
    right: -4px;
    background: #ef4444;
    color: #fff;
    font-size: 0.6rem;
    font-weight: 700;
    min-width: 16px;
    height: 16px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 0 4px;
    line-height: 1;
  }
  .chrome-notif-indicator.has-notifications .chrome-notif-icon {
    filter: none;
  }
  .chrome-banner {
    /* Empty and invisible when no notifications */
  }
  .chrome-banner:empty {
    display: none;
  }
  .chrome-banner-bar {
    position: fixed;
    top: 48px;
    left: 0;
    right: 0;
    padding: 6px 20px;
    font-size: 0.82rem;
    font-family: "Inter", system-ui, sans-serif;
    display: flex;
    align-items: center;
    gap: 10px;
    z-index: 999;
  }
  .chrome-banner-bar.severity-security {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border-bottom: 1px solid rgba(239, 68, 68, 0.3);
  }
  .chrome-banner-bar.severity-critical {
    background: rgba(245, 158, 66, 0.15);
    color: #f59e42;
    border-bottom: 1px solid rgba(245, 158, 66, 0.3);
  }
  .chrome-banner-bar.severity-routine {
    background: rgba(91, 138, 245, 0.12);
    color: #5b8af5;
    border-bottom: 1px solid rgba(91, 138, 245, 0.3);
  }
  .chrome-banner-text {
    flex: 1;
  }
  .chrome-banner-dismiss {
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    font-size: 1rem;
    padding: 0 4px;
    opacity: 0.7;
  }
  .chrome-banner-dismiss:hover {
    opacity: 1;
  }
`;
document.head.appendChild(chromeStyles);
