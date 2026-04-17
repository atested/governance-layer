/**
 * Atested Operator UI - Application entry point.
 *
 * Initializes the chrome bar, main page shell, and modal manager.
 * Triggers data loading for the main page via the data-access layer.
 */

import { renderChrome, updateNotificationCount, showBanner, updateIdentityZone } from './chrome.js';
import { renderMainPage, loadMainPageData } from './main-page.js';
import { modalManager } from './modal-manager.js';
import { openNotificationsWindow } from './windows/notifications.js';
import { openIdentitySetupWindow } from './windows/identity-setup.js';
import { openIdentitySessionWindow } from './windows/identity-session.js';
import * as api from './api.js';

// Verify adoptedStyleSheets support
if (!('adoptedStyleSheets' in Document.prototype)) {
  console.warn(
    'Atested: adoptedStyleSheets not supported in this browser. ' +
    'The operator UI requires Chrome 73+, Firefox 101+, or Safari 16.4+.'
  );
}

function init() {
  // Render chrome bar (fixed position, always visible)
  const chrome = renderChrome();
  document.body.appendChild(chrome);

  // Wire chrome zone clicks to window launches
  chrome.querySelector('.chrome-identity').addEventListener('click', (e) => {
    _openIdentityWindow(e.currentTarget);
  });
  chrome.querySelector('.chrome-license').addEventListener('click', (e) => {
    _chromeOpen('Licensing', e.currentTarget);
  });
  chrome.querySelector('.chrome-notif-indicator').addEventListener('click', (e) => {
    if (modalManager.depth > 0) {
      openNotificationsWindow(e.currentTarget);
    } else {
      openNotificationsWindow(e.currentTarget);
    }
  });

  // Render main page structure, then load live data
  const mainPage = renderMainPage();
  document.body.appendChild(mainPage);

  // Fetch data from the data-access layer (non-blocking)
  loadMainPageData().catch(err => {
    console.warn('Atested: main page data load failed:', err);
  });

  // Check first-run disclosure
  _checkDisclosure();

  // Load notification state into chrome
  _loadNotifications();

  // Load identity state into chrome
  _loadIdentityState();
}

/**
 * Chrome click handler: opens a window, replacing any existing depth-1 window.
 * Spec v2 section 3.6.
 */
function _chromeOpen(title, trigger) {
  if (modalManager.depth > 0) {
    modalManager.replaceChild({
      title,
      trigger,
      content: _chromePlaceholder(title),
    });
  } else {
    modalManager.open({
      title,
      trigger,
      content: _chromePlaceholder(title),
    });
  }
}

function _chromePlaceholder(title) {
  const el = document.createElement('div');
  el.innerHTML = `
    <p style="color: #8b919a; text-align: center; padding: 40px 0;">
      ${title} window (opened from chrome). Content built in later phases.
    </p>
  `;
  return el;
}

/**
 * Check if the first-run disclosure has been acknowledged.
 * If not, show a disclosure card that gates further interaction.
 */
async function _checkDisclosure() {
  try {
    const res = await api.getDisclosureStatus();
    if (res.ok && res.data.acknowledged) return; // Already acknowledged

    _showDisclosureCard();
  } catch {
    // If the endpoint is not available, skip disclosure
  }
}

function _showDisclosureCard() {
  const overlay = document.createElement('div');
  overlay.id = 'disclosure-overlay';
  Object.assign(overlay.style, {
    position: 'fixed',
    inset: '0',
    zIndex: '2000',
    background: 'rgba(0, 0, 0, 0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontFamily: '"Inter", system-ui, sans-serif',
  });

  const card = document.createElement('div');
  Object.assign(card.style, {
    background: '#22262e',
    border: '1px solid rgba(255, 255, 255, 0.08)',
    borderRadius: '12px',
    padding: '32px 40px',
    maxWidth: '520px',
    color: '#e4e6eb',
    textAlign: 'center',
  });

  card.innerHTML = `
    <h2 style="font-size:1.25rem; font-weight:700; margin:0 0 16px; color:#e4e6eb;">Atested Governance Dashboard</h2>
    <p style="font-size:0.88rem; color:#8b919a; line-height:1.6; margin:0 0 12px;">
      This dashboard provides visibility into the governance decisions made by
      the Atested system. All operations are recorded in a tamper-evident chain.
    </p>
    <p style="font-size:0.88rem; color:#8b919a; line-height:1.6; margin:0 0 24px;">
      By proceeding, you acknowledge that your activity in this dashboard will
      be recorded as governance events.
    </p>
  `;

  const btn = document.createElement('button');
  Object.assign(btn.style, {
    background: '#5b8af5',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    padding: '10px 28px',
    fontSize: '0.88rem',
    fontWeight: '600',
    cursor: 'pointer',
    fontFamily: '"Inter", system-ui, sans-serif',
  });
  btn.textContent = 'Acknowledge & Continue';
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    btn.textContent = 'Recording...';
    const res = await api.postDisclosureAcknowledge({});
    if (res.ok) {
      overlay.remove();
    } else {
      btn.disabled = false;
      btn.textContent = 'Acknowledge & Continue';
    }
  });

  card.appendChild(btn);
  overlay.appendChild(card);
  document.body.appendChild(overlay);
}

/** Cached identity state for routing chrome clicks */
let _identitySession = null;

/** Timer for refreshing identity state when unlocked */
let _identityRefreshTimer = null;

/**
 * Load identity state and update chrome identity zone.
 */
async function _loadIdentityState() {
  try {
    const res = await api.getIdentitySession();
    if (!res.ok) {
      _identitySession = null;
      updateIdentityZone(null);
      return;
    }
    _identitySession = res.data;
    updateIdentityZone(_identitySession);

    // If unlocked, refresh every 15 seconds to keep the timer accurate
    if (_identityRefreshTimer) { clearInterval(_identityRefreshTimer); _identityRefreshTimer = null; }
    if (_identitySession.configured && !_identitySession.locked) {
      _identityRefreshTimer = setInterval(() => _loadIdentityState(), 15000);
    }
  } catch {
    _identitySession = null;
    updateIdentityZone(null);
  }
}

/**
 * Open the correct identity window based on current state.
 */
function _openIdentityWindow(trigger) {
  if (_identitySession && _identitySession.configured) {
    openIdentitySessionWindow(trigger);
  } else {
    openIdentitySetupWindow(trigger);
  }
}

/**
 * Load notifications and update chrome indicator + banner.
 */
async function _loadNotifications() {
  try {
    const res = await api.getNotifications();
    if (!res.ok) return;

    const notifications = res.data.notifications || [];
    updateNotificationCount(notifications.length);

    // Show the highest-severity notification in the banner
    if (notifications.length > 0) {
      const SEVERITY_ORDER = { security: 0, critical: 1, routine: 2, informational: 3 };
      const sorted = [...notifications].sort(
        (a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9)
      );
      const top = sorted[0];
      showBanner(top, async (id) => {
        await api.postDismissNotification({ notification_id: id });
        _loadNotifications(); // Refresh after dismiss
      });
    } else {
      showBanner(null);
    }
  } catch {
    // Non-critical — leave indicator at 0
  }
}

// Boot
init();
