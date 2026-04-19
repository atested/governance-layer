/**
 * Atested Operator UI - Application entry point.
 *
 * Initializes the chrome bar, main page shell, and modal manager.
 * Triggers data loading for the main page via the data-access layer.
 */

import { renderChrome, updateNotificationCount, showBanner, updateIdentityZone, updateLicenseZone, updateBreadcrumb } from './chrome.js';
import { renderMainPage, loadMainPageData, setLicenseMode } from './main-page.js';
import { modalManager } from './modal-manager.js';
import { openAlertsWindow } from './windows/alerts.js';
import { openIdentitySetupWindow } from './windows/identity-setup.js';
import { openIdentitySessionWindow } from './windows/identity-session.js';
import { openLicensingWindow } from './windows/licensing.js';
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

  // Wire chrome zone clicks and keyboard activation to window launches
  const identityZone = chrome.querySelector('.chrome-identity');
  identityZone.addEventListener('click', (e) => _openIdentityWindow(e.currentTarget));
  identityZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); _openIdentityWindow(e.currentTarget); }
  });

  const licenseZone = chrome.querySelector('.chrome-license');
  licenseZone.addEventListener('click', (e) => openLicensingWindow(e.currentTarget));
  licenseZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openLicensingWindow(e.currentTarget); }
  });

  const notifZone = chrome.querySelector('.chrome-notif-indicator');
  notifZone.addEventListener('click', (e) => openAlertsWindow(e.currentTarget));
  notifZone.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openAlertsWindow(e.currentTarget); }
  });

  // Wire chrome breadcrumb to modal manager
  modalManager.onChange(({ depth, title }) => {
    updateBreadcrumb(depth > 0 ? title : null);
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

  // Load license state into chrome and main page
  _loadLicenseState();
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

/**
 * Refresh license state across all surfaces (chrome, main page).
 * Exported so licensing actions (registration, trial completion) can
 * trigger immediate propagation.
 */
export async function refreshLicenseState() {
  return _loadLicenseState();
}

/**
 * Load licensing mode and update chrome license zone + main page.
 */
async function _loadLicenseState() {
  try {
    const res = await api.getLicensingMode();
    if (!res.ok) return;

    const { license_status, license_tier } = res.data;

    // Map status+tier to chrome display
    const TIER_NAMES = {
      personal: 'Personal', personal_plus: 'Personal Plus',
      crew: 'Crew', team: 'Team', business: 'Business',
      enterprise: 'Enterprise', institution: 'Institution',
    };

    let tierName, dotColor;
    if (license_status === 'trial') {
      tierName = 'Trial';
      dotColor = 'var(--ok, #22c55e)';
    } else if (license_status === 'licensed') {
      tierName = TIER_NAMES[license_tier] || license_tier;
      dotColor = 'var(--ok, #22c55e)';
    } else if (license_status === 'personal') {
      tierName = 'Personal';
      dotColor = 'var(--warning, #f59e42)';
    } else if (license_status === 'unlicensed') {
      tierName = 'Unlicensed';
      dotColor = 'var(--warning, #f59e42)';
    } else if (license_status === 'clock_anomaly') {
      tierName = 'Clock Issue';
      dotColor = 'var(--danger, #ef4444)';
    } else {
      tierName = 'Unknown';
      dotColor = 'var(--muted, #8b919a)';
    }

    updateLicenseZone(tierName, dotColor);
    setLicenseMode(res.data);
  } catch {
    // Non-critical — chrome stays at default static values
  }
}

// Boot
init();
