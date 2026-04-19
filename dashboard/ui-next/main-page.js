/**
 * Main page for the Atested operator UI.
 * Renders the home state below the chrome bar with live data
 * from the data-access layer, using Phase 2 components.
 * Spec v2 section 5.
 */

import { modalManager } from './modal-manager.js';
import * as api from './api.js';

// Import Phase 2 components (registers custom elements)
import './components/status-card.js';
import './components/status-grid.js';
import './components/decision-tag.js';
import './components/tier-badge.js';
import './components/loading-indicator.js';

// Import window modules
import { openActivityWindow } from './windows/activity.js';
import { openAuditWindow } from './windows/audit.js';
import { openApprovalsWindow } from './windows/approvals.js';
import { openHealthWindow } from './windows/health.js';
import { openReportsWindow } from './windows/reports.js';
import { openConfigWindow } from './windows/configuration.js';
import { openFeedbackWindow } from './windows/communications.js';
import { openAlertsWindow } from './windows/alerts.js';
import { openLicensingWindow } from './windows/licensing.js';

/** Map launcher IDs to window open functions */
const WINDOW_OPENERS = {
  activity: openActivityWindow,
  approvals: openApprovalsWindow,
  audit: openAuditWindow,
  reports: openReportsWindow,
  health: openHealthWindow,
  configuration: openConfigWindow,
  communications: openFeedbackWindow,
  alerts: openAlertsWindow,
  licensing: openLicensingWindow,
};

/** Workflow launcher definitions — nine pane cards in a 3x3 grid */
const LAUNCHERS = [
  { id: 'activity',       label: 'Activity',       desc: 'Full decision log with filtering and record detail',         accent: 'green' },
  { id: 'approvals',      label: 'Approvals',      desc: 'Manage your approvals for exceptions to rules',              accent: 'green' },
  { id: 'audit',          label: 'Audit',           desc: 'Searchable chain records for compliance and review',         accent: 'green' },
  { id: 'reports',        label: 'Reports',         desc: 'Atested metrics and trends over time',                      accent: 'green' },
  { id: 'health',         label: 'Health',          desc: 'Chain integrity, signing status, system diagnostics',        accent: 'amber' },
  { id: 'configuration',  label: 'Configuration',   desc: 'Policy rules, capability registry, base directories',       accent: 'green' },
  { id: 'communications', label: 'Communications',  desc: 'Telemetry, escalations, and priority requests',             accent: 'green' },
  { id: 'alerts',          label: 'Alerts',            desc: 'Proactive monitoring, security alerts, system notices',     accent: 'green' },
  { id: 'licensing',      label: 'Licensing',        desc: 'Pricing, survey, case document, purchase',                 accent: 'amber' },
];

/** DOM references populated during render */
let _page = null;

/** Cached state for dynamic accent colors */
let _healthState = 'unknown';  // 'healthy', 'degraded', 'critical', 'unknown'
let _licenseState = 'amber';   // 'green' or 'amber'

export function renderMainPage() {
  _page = document.createElement('div');
  _page.id = 'main-page';
  _page.innerHTML = `
    <h1 class="mp-page-title">Atested AI Operations</h1>
    <div class="mp-top-panes">
      <div class="mp-pane mp-pane-clickable" id="mp-chain-health" tabindex="0" role="button">
        <div class="mp-pane-accent" id="mp-health-accent"></div>
        <div class="mp-pane-header">
          <h2 class="mp-pane-title">Chain health</h2>
        </div>
        <div class="mp-pane-metrics">
          <div class="mp-metric">
            <span class="mp-metric-label">Chain Events</span>
            <span class="mp-metric-value" id="mv-chain-events">0</span>
          </div>
          <div class="mp-metric">
            <span class="mp-metric-label">Integrity</span>
            <span class="mp-metric-value" id="mv-chain-integrity">N/A</span>
          </div>
          <div class="mp-metric">
            <span class="mp-metric-label">Chain Age</span>
            <span class="mp-metric-value" id="mv-chain-age">N/A</span>
          </div>
          <div class="mp-metric">
            <span class="mp-metric-label">Last Event</span>
            <span class="mp-metric-value" id="mv-last-event">N/A</span>
          </div>
        </div>
      </div>
      <div class="mp-pane mp-pane-clickable" id="mp-atested-activity" tabindex="0" role="button">
        <div class="mp-pane-accent mp-accent-green" id="mp-activity-accent"></div>
        <div class="mp-pane-header">
          <h2 class="mp-pane-title">Atested activity</h2>
        </div>
        <div class="mp-pane-metrics">
          <div class="mp-metric">
            <span class="mp-metric-label">Mediated</span>
            <span class="mp-metric-value" id="mv-mediated">0</span>
          </div>
          <div class="mp-metric">
            <span class="mp-metric-label">Denied</span>
            <span class="mp-metric-value" id="mv-denied">0</span>
          </div>
          <div class="mp-metric">
            <span class="mp-metric-label">Approved</span>
            <span class="mp-metric-value" id="mv-approved">0</span>
          </div>
          <div class="mp-metric">
            <span class="mp-metric-label">Users</span>
            <span class="mp-metric-value" id="mv-users">0</span>
          </div>
        </div>
      </div>
    </div>

    <div class="mp-pane mp-pane-clickable mp-pane-full" id="mp-recent" tabindex="0" role="button">
      <div class="mp-pane-accent mp-accent-green"></div>
      <div class="mp-pane-header">
        <h2 class="mp-pane-title">Recent activity</h2>
      </div>
      <div class="mp-feed" id="recent-feed">
        <div class="mp-feed-header">
          <span class="mp-feed-hcol">Time</span>
          <span class="mp-feed-hcol">Tool</span>
          <span class="mp-feed-hcol">Target</span>
          <span class="mp-feed-hcol mp-feed-hcol-right">Decision</span>
        </div>
        <atd-loading-indicator label="Loading activity"></atd-loading-indicator>
      </div>
    </div>

    <section class="mp-section" id="mp-launchers">
      <div class="mp-launcher-grid" id="launcher-grid"></div>
    </section>
  `;

  // Wire top pane clicks
  const healthPane = _page.querySelector('#mp-chain-health');
  healthPane.addEventListener('click', () => openHealthWindow(healthPane));
  healthPane.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openHealthWindow(healthPane); }
  });

  const activityPane = _page.querySelector('#mp-atested-activity');
  activityPane.addEventListener('click', () => openActivityWindow(activityPane));
  activityPane.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openActivityWindow(activityPane); }
  });

  // Wire recent activity pane click (on the pane itself, not individual rows)
  const recentPane = _page.querySelector('#mp-recent');
  recentPane.addEventListener('click', (e) => {
    // Only open if clicking the pane header area, not individual feed rows
    if (e.target.closest('.mp-feed-row')) return;
    openActivityWindow(recentPane);
  });
  recentPane.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openActivityWindow(recentPane); }
  });

  // Render workflow launcher pane cards
  const grid = _page.querySelector('#launcher-grid');
  for (const launcher of LAUNCHERS) {
    const card = document.createElement('div');
    card.className = 'mp-wf-card';
    card.tabIndex = 0;
    card.setAttribute('role', 'button');
    card.dataset.windowId = launcher.id;
    card.dataset.defaultAccent = launcher.accent;

    const accentColor = launcher.accent === 'amber' ? 'mp-wf-accent-amber' : 'mp-wf-accent-green';
    card.innerHTML = `
      <div class="mp-wf-accent ${accentColor}" data-accent-bar="${launcher.id}"></div>
      <div class="mp-wf-title">${_esc(launcher.label)}</div>
      <div class="mp-wf-desc">${_esc(launcher.desc)}</div>
    `;

    card.addEventListener('click', () => {
      const opener = WINDOW_OPENERS[launcher.id];
      if (opener) opener(card);
    });
    card.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        const opener = WINDOW_OPENERS[launcher.id];
        if (opener) opener(card);
      }
    });

    grid.appendChild(card);
  }

  return _page;
}

/**
 * Load all main page data from the data-access layer.
 * Called by app.js after the page is in the DOM.
 * Fetches in parallel and renders whatever succeeds.
 */
export async function loadMainPageData() {
  if (!_page) return;

  const [healthRes, statusRes, activityRes] = await Promise.all([
    api.getHealth(),
    api.getStatus(),
    api.getActivity({ limit: 5 }),
  ]);

  // Chain Health pane
  if (healthRes.ok) {
    const h = healthRes.data;
    _setMetric('mv-chain-events', String(h.chain?.chain_event_count ?? 0));

    const integrity = h.chain?.status ?? 'N/A';
    const intEl = _page.querySelector('#mv-chain-integrity');
    intEl.textContent = integrity.toUpperCase();

    // Color the integrity value and set accent bar
    if (integrity === 'ok') {
      intEl.classList.add('mp-metric-green');
      _healthState = 'healthy';
    } else if (integrity === 'broken') {
      intEl.classList.add('mp-metric-red');
      _healthState = 'critical';
    } else if (integrity === 'repaired') {
      intEl.classList.add('mp-metric-amber');
      _healthState = 'degraded';
    } else {
      _healthState = 'unknown';
    }

    _updateHealthAccent();

    // Chain Age — compute from recent_stability_events or timestamp
    const chainTs = h.timestamp_utc;
    const recentEvents = h.recent_stability_events || [];
    let firstEventTs = null;
    // Find earliest stability event, or use current health timestamp as reference
    for (const evt of recentEvents) {
      const ts = evt.timestamp_utc || evt.timestamp;
      if (ts && (!firstEventTs || ts < firstEventTs)) firstEventTs = ts;
    }
    // Also check the chain file creation hint from storage
    if (firstEventTs) {
      const ageMs = Date.now() - new Date(firstEventTs).getTime();
      const ageDays = Math.max(0, Math.floor(ageMs / 86400000));
      _setMetric('mv-chain-age', ageDays === 1 ? '1 day' : `${ageDays} days`);
    }

    // Last Event — use health timestamp
    if (chainTs) {
      _setMetric('mv-last-event', _formatTime24(chainTs));
    }

    // Denied count from deny_rate
    const denyRate = h.deny_rate;
    if (denyRate) {
      const deniedEl = _page.querySelector('#mv-denied');
      const denyCount = denyRate.deny_count ?? 0;
      deniedEl.textContent = String(denyCount);
      if (denyCount > 5) deniedEl.classList.add('mp-metric-red');
      else if (denyCount > 0) deniedEl.classList.add('mp-metric-amber');
    }

    // Unique users
    const uniqueUsers = h.users?.unique_users ?? 0;
    _setMetric('mv-users', String(uniqueUsers));
  }

  // Atested Activity pane — derives from status
  if (statusRes.ok) {
    const s = statusRes.data;
    const mediated = s.opacity_posture?.transparent_count ?? 0;
    _setMetric('mv-mediated', String(mediated));

    const approved = s.approval_snapshot?.active_approvals ?? 0;
    _setMetric('mv-approved', String(approved));
  }

  // Recent Activity feed
  _renderRecentActivity(activityRes);

  // Update workflow card accent for Health based on integrity state
  _updateWorkflowAccent('health', _healthState === 'healthy' ? 'green' : 'amber');

  // Update Alerts workflow card accent based on notification state
  _updateAlertsAccent();
}

/**
 * Set the licensing mode and conditionally render the post-trial
 * unlicensed card on the main page.
 * Called by app.js after loading license state.
 * @param {{ license_status: string, license_tier: string }} modeData
 */
export function setLicenseMode(modeData) {
  if (!_page) return;
  const existing = _page.querySelector('#mp-license-card');
  if (existing) existing.remove();

  const status = modeData?.license_status;

  // Update licensing workflow card accent
  if (status === 'licensed' || status === 'trial') {
    _licenseState = 'green';
  } else {
    _licenseState = 'amber';
  }
  _updateWorkflowAccent('licensing', _licenseState === 'green' ? 'green' : 'amber');

  if (status === 'personal' || status === 'unlicensed') {
    const card = document.createElement('div');
    card.id = 'mp-license-card';
    card.className = 'mp-license-card';
    card.innerHTML = `
      <div class="mp-license-card-inner">
        <span class="mp-license-dot" style="background: var(--warning, #f59e42)"></span>
        <div class="mp-license-card-text">
          <strong>Personal (unlicensed)</strong>
          <span>Governance is active. Register or choose a tier to unlock full features.</span>
        </div>
        <button class="mp-license-card-btn">Open Licensing</button>
      </div>
    `;
    card.querySelector('.mp-license-card-btn').addEventListener('click', () => {
      openLicensingWindow(card);
    });
    // Insert before the launchers section
    const launchers = _page.querySelector('#mp-launchers');
    _page.insertBefore(card, launchers);
  }
}

// ---------- Internal helpers ----------

function _setMetric(id, value) {
  const el = _page?.querySelector(`#${id}`);
  if (el) el.textContent = value;
}

function _updateHealthAccent() {
  const accent = _page?.querySelector('#mp-health-accent');
  if (!accent) return;
  accent.className = 'mp-pane-accent';
  if (_healthState === 'critical') accent.classList.add('mp-accent-red');
  else if (_healthState === 'degraded') accent.classList.add('mp-accent-amber');
  else accent.classList.add('mp-accent-green');
}

async function _updateAlertsAccent() {
  try {
    const res = await api.getNotifications();
    if (!res.ok) return;
    const notifications = res.data.notifications || [];
    if (!notifications.length) {
      _updateWorkflowAccent('alerts', 'green');
      return;
    }
    const hasCritical = notifications.some(n =>
      n.severity === 'security' || n.severity === 'critical'
    );
    _updateWorkflowAccent('alerts', hasCritical ? 'red' : 'amber');
  } catch {
    // Non-critical
  }
}

function _updateWorkflowAccent(id, color) {
  const bar = _page?.querySelector(`[data-accent-bar="${id}"]`);
  if (!bar) return;
  bar.className = 'mp-wf-accent';
  if (color === 'red') bar.classList.add('mp-wf-accent-red');
  else if (color === 'amber') bar.classList.add('mp-wf-accent-amber');
  else bar.classList.add('mp-wf-accent-green');
}

function _renderRecentActivity(result) {
  const feed = _page?.querySelector('#recent-feed');
  if (!feed) return;

  if (!result.ok) {
    feed.innerHTML = `<div class="mp-error">${_esc(result.error)}</div>`;
    return;
  }

  const entries = result.data?.entries || [];
  if (!entries.length) {
    feed.innerHTML = '<p class="mp-placeholder">No recent activity</p>';
    return;
  }

  // Keep the column header, clear the rest
  const header = feed.querySelector('.mp-feed-header');
  feed.innerHTML = '';
  if (header) feed.appendChild(header);

  for (const entry of entries) {
    const row = document.createElement('div');
    row.className = 'mp-feed-row';
    row.tabIndex = 0;

    const time = _formatTime24(entry.timestamp_utc);
    const detail = entry.detail || {};
    const tool = detail.tool_name || entry.tool || entry.event_type || '';
    const target = detail.target || '';
    const decision = detail.policy_decision || entry.policy_decision || entry.event_category || '';

    // Four columns: time, tool, target, decision
    let decisionHtml;
    if (decision === 'ALLOW') {
      decisionHtml = '<span class="mp-decision-allow">ALLOW</span>';
    } else if (decision === 'DENY') {
      decisionHtml = '<span class="mp-decision-deny">DENY</span>';
    } else {
      decisionHtml = '<span class="mp-decision-muted">\u2014</span>';
    }

    row.innerHTML = `
      <span class="mp-feed-time">${_esc(time)}</span>
      <span class="mp-feed-tool">${_esc(tool)}</span>
      <span class="mp-feed-target">${_esc(target)}</span>
      <span class="mp-feed-decision">${decisionHtml}</span>
    `;

    // Click handler — opens Activity with Record Detail for this entry
    const recordId = entry.request_id || entry.event_id || '';
    row.addEventListener('click', (e) => {
      e.stopPropagation();
      openActivityWindow(row, { scrollToRecord: recordId });
    });
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.stopPropagation();
        openActivityWindow(row, { scrollToRecord: recordId });
      }
    });

    feed.appendChild(row);
  }
}

function _formatTime24(isoStr) {
  if (!isoStr) return '--';
  try {
    const d = new Date(isoStr);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  } catch {
    return isoStr;
  }
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// Inject main page styles
const mpStyles = document.createElement('style');
mpStyles.textContent = `
  #main-page {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
    padding-top: calc(48px + 20px); /* chrome height + gap */
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }
  #main-page[aria-hidden="true"] {
    pointer-events: none;
  }

  /* ---- Page title ---- */
  .mp-page-title {
    font-size: 32px;
    font-weight: 500;
    color: #e4e6eb;
    text-align: center;
    margin: 0 0 20px;
  }

  /* ---- Top display panes ---- */
  .mp-top-panes {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }
  .mp-pane {
    background: #22262e;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    position: relative;
    overflow: hidden;
  }
  .mp-pane-full {
    margin-bottom: 20px;
  }
  .mp-pane-clickable {
    cursor: pointer;
    transition: background 0.15s;
  }
  .mp-pane-clickable:hover {
    background: #272b34;
  }
  .mp-pane-clickable:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }

  /* Accent bars — 6px top */
  .mp-pane-accent {
    height: 6px;
    background: #6b7280;
  }
  .mp-accent-green { background: #22c55e; }
  .mp-accent-amber { background: #f5a623; }
  .mp-accent-red { background: #ef4444; }

  /* Pane header */
  .mp-pane-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 18px 8px;
  }
  .mp-pane-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5b8af5;
    margin: 0;
    font-weight: 600;
  }
  /* Pane metrics */
  .mp-pane-metrics {
    display: flex;
    gap: 24px;
    padding: 4px 18px 16px;
  }
  .mp-metric {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .mp-metric-label {
    font-size: 0.68rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 500;
  }
  .mp-metric-value {
    font-size: 1.1rem;
    font-weight: 700;
    color: #e4e6eb;
    font-family: "JetBrains Mono", monospace;
  }
  .mp-metric-green { color: #22c55e; }
  .mp-metric-amber { color: #f5a623; }
  .mp-metric-red { color: #ef4444; }

  /* ---- Recent activity feed ---- */
  .mp-feed {
    padding: 4px 0;
    min-height: 48px;
  }
  .mp-feed-header {
    display: grid;
    grid-template-columns: 80px 100px 1fr 70px;
    align-items: center;
    gap: 12px;
    padding: 4px 18px 2px;
  }
  .mp-feed-hcol {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    font-weight: 600;
  }
  .mp-feed-hcol-right {
    text-align: right;
  }
  .mp-feed-row {
    display: grid;
    grid-template-columns: 80px 100px 1fr 70px;
    align-items: center;
    gap: 12px;
    padding: 7px 18px;
    cursor: pointer;
    transition: background 0.1s;
    font-size: 0.82rem;
  }
  .mp-feed-row:hover {
    background: rgba(91, 138, 245, 0.08);
  }
  .mp-feed-row:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: -2px;
    border-radius: 6px;
  }
  .mp-feed-time {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .mp-feed-tool {
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mp-feed-target {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .mp-feed-decision {
    text-align: right;
  }
  .mp-decision-allow {
    font-size: 0.68rem;
    font-weight: 600;
    color: #22c55e;
    letter-spacing: 0.03em;
  }
  .mp-decision-deny {
    font-size: 0.68rem;
    font-weight: 600;
    color: #ef4444;
    letter-spacing: 0.03em;
  }
  .mp-decision-muted {
    font-size: 0.72rem;
    color: #6b7280;
  }

  /* ---- Workflow launcher grid ---- */
  .mp-section {
    margin-bottom: 24px;
  }
  .mp-launcher-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  .mp-wf-card {
    background: #22262e;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    position: relative;
    overflow: hidden;
    cursor: pointer;
    transition: background 0.15s;
    padding: 0;
    text-align: center;
  }
  .mp-wf-card:hover {
    background: #272b34;
  }
  .mp-wf-card:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }

  /* Workflow accent bar — 6px top */
  .mp-wf-accent {
    height: 6px;
  }
  .mp-wf-accent-green { background: #22c55e; }
  .mp-wf-accent-amber { background: #f5a623; }
  .mp-wf-accent-red { background: #ef4444; }

  .mp-wf-title {
    font-size: 0.95rem;
    font-weight: 700;
    color: #e4e6eb;
    margin: 14px 16px 6px;
  }
  .mp-wf-desc {
    font-size: 0.75rem;
    color: #8b919a;
    line-height: 1.4;
    margin: 0 16px 12px;
    min-height: 32px;
  }

  /* ---- License card ---- */
  .mp-license-card {
    margin-bottom: 20px;
  }
  .mp-license-card-inner {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    background: rgba(245, 158, 66, 0.06);
    border: 1px solid rgba(245, 158, 66, 0.3);
    border-radius: 10px;
  }
  .mp-license-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .mp-license-card-text {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 0.82rem;
  }
  .mp-license-card-text strong {
    color: #f59e42;
    font-weight: 600;
  }
  .mp-license-card-text span {
    color: #8b919a;
  }
  .mp-license-card-btn {
    background: none;
    border: 1px solid rgba(245, 158, 66, 0.4);
    border-radius: 8px;
    color: #f59e42;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 6px 14px;
    white-space: nowrap;
    transition: background 0.15s;
  }
  .mp-license-card-btn:hover {
    background: rgba(245, 158, 66, 0.12);
  }

  /* ---- Utility ---- */
  .mp-placeholder {
    color: #8b919a;
    font-size: 0.82rem;
    margin: 0;
    padding: 16px;
    text-align: center;
    font-style: italic;
  }
  .mp-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 12px 16px;
    border-radius: 8px;
    margin-top: 8px;
  }

  /* ---- Responsive ---- */
  @media (max-width: 900px) {
    .mp-launcher-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }
  @media (max-width: 600px) {
    #main-page {
      padding: 12px;
      padding-top: calc(48px + 12px);
    }
    .mp-top-panes {
      grid-template-columns: 1fr;
    }
    .mp-launcher-grid {
      grid-template-columns: 1fr;
    }
    .mp-feed-header,
    .mp-feed-row {
      grid-template-columns: 60px 80px 1fr auto;
      gap: 6px;
    }
    .mp-pane-metrics {
      flex-wrap: wrap;
      gap: 12px;
    }
  }
`;
document.head.appendChild(mpStyles);
