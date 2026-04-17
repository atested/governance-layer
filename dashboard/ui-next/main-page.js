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

// Import window modules
import { openActivityWindow } from './windows/activity.js';
import { openAuditWindow } from './windows/audit.js';
import { openApprovalsWindow } from './windows/approvals.js';
import { openHealthWindow } from './windows/health.js';
import { openReportsWindow } from './windows/reports.js';
import { openConfigWindow } from './windows/configuration.js';
import { openFeedbackWindow } from './windows/feedback.js';

/** Map launcher IDs to window open functions */
const WINDOW_OPENERS = {
  activity: openActivityWindow,
  approvals: openApprovalsWindow,
  audit: openAuditWindow,
  reports: openReportsWindow,
  health: openHealthWindow,
  configuration: openConfigWindow,
  feedback: openFeedbackWindow,
};

/** Launcher definitions for all workflow windows */
const LAUNCHERS = [
  { id: 'activity', label: 'Activity' },
  { id: 'approvals', label: 'Approvals' },
  { id: 'audit', label: 'Audit' },
  { id: 'reports', label: 'Reports' },
  { id: 'health', label: 'Health' },
  { id: 'configuration', label: 'Configuration' },
  { id: 'feedback', label: 'Feedback' },
  { id: 'notifications', label: 'Notifications' },
  { id: 'licensing', label: 'Licensing' },
];

/** DOM references populated during render */
let _page = null;

export function renderMainPage() {
  _page = document.createElement('div');
  _page.id = 'main-page';
  _page.innerHTML = `
    <section class="mp-section" id="mp-chain-health">
      <h2 class="mp-section-title">Chain Health</h2>
      <atd-status-grid id="health-grid">
        <atd-status-card label="Chain Events" value="--" id="card-chain-events"></atd-status-card>
        <atd-status-card label="Chain Integrity" value="--" id="card-chain-integrity"></atd-status-card>
      </atd-status-grid>
    </section>

    <section class="mp-section" id="mp-gov-activity">
      <h2 class="mp-section-title">Governance Activity</h2>
      <atd-status-grid id="activity-grid">
        <atd-status-card label="Mediated Operations" value="--" id="card-mediated" clickable></atd-status-card>
        <atd-status-card label="Actions Denied" value="--" id="card-denied" clickable></atd-status-card>
        <atd-status-card label="Approved Operations" value="--" id="card-approved" clickable></atd-status-card>
        <atd-status-card label="Approval-Gated" value="--" id="card-gated" clickable></atd-status-card>
      </atd-status-grid>
    </section>

    <section class="mp-section" id="mp-transparency">
      <h2 class="mp-section-title">Transparency & Coverage</h2>
      <atd-status-grid id="transparency-grid">
        <atd-status-card label="Governed Operations" value="--" id="card-governed"></atd-status-card>
        <atd-status-card label="Ungoverned Operations" value="--" id="card-ungoverned"></atd-status-card>
        <atd-status-card label="Transparency Rate" value="--" id="card-transparency"></atd-status-card>
        <atd-status-card label="Unique Users" value="--" id="card-users"></atd-status-card>
      </atd-status-grid>
    </section>

    <section class="mp-section" id="mp-recent">
      <h2 class="mp-section-title">Recent Activity</h2>
      <div class="mp-feed" id="recent-feed">
        <p class="mp-loading">Loading...</p>
      </div>
    </section>

    <section class="mp-section" id="mp-launchers">
      <h2 class="mp-section-title">Workflows</h2>
      <div class="mp-launchers" id="launcher-grid"></div>
    </section>
  `;

  // Render launcher buttons
  const grid = _page.querySelector('#launcher-grid');
  for (const launcher of LAUNCHERS) {
    const btn = document.createElement('button');
    btn.className = 'mp-launcher';
    btn.textContent = launcher.label;
    btn.dataset.windowId = launcher.id;
    btn.addEventListener('click', () => {
      const opener = WINDOW_OPENERS[launcher.id];
      if (opener) {
        opener(btn);
      } else {
        _openPlaceholderWindow(launcher.label, btn);
      }
    });
    grid.appendChild(btn);
  }

  // Wire card click handlers to open corresponding windows
  _page.querySelector('#card-mediated').addEventListener('card:click', () => {
    openActivityWindow(_page.querySelector('#card-mediated'));
  });
  _page.querySelector('#card-denied').addEventListener('card:click', () => {
    openActivityWindow(_page.querySelector('#card-denied'));
  });
  _page.querySelector('#card-approved').addEventListener('card:click', () => {
    openApprovalsWindow(_page.querySelector('#card-approved'));
  });
  _page.querySelector('#card-gated').addEventListener('card:click', () => {
    openApprovalsWindow(_page.querySelector('#card-gated'));
  });

  return _page;
}

/**
 * Load all main page data from the data-access layer.
 * Called by app.js after the page is in the DOM.
 * Fetches in parallel and renders whatever succeeds.
 */
export async function loadMainPageData() {
  if (!_page) return;

  const [healthRes, statusRes, transparencyRes, activityRes] = await Promise.all([
    api.getHealth(),
    api.getStatus(),
    api.getTransparency(),
    api.getActivity({ limit: 8 }),
  ]);

  // Chain Health section
  if (healthRes.ok) {
    const h = healthRes.data;
    _setCard('card-chain-events', String(h.chain?.chain_event_count ?? '--'));
    const integrity = h.chain?.status ?? '--';
    const integrityCard = _page.querySelector('#card-chain-integrity');
    integrityCard.setAttribute('value', integrity.toUpperCase());
    if (integrity === 'ok') {
      integrityCard.setAttribute('variant', 'success');
    } else if (integrity === 'broken') {
      integrityCard.setAttribute('variant', 'danger');
    } else if (integrity === 'repaired') {
      integrityCard.setAttribute('variant', 'warning');
    }
  } else {
    _showError('mp-chain-health', healthRes.error);
  }

  // Governance Activity section — derives from status + health
  if (statusRes.ok) {
    const s = statusRes.data;
    // Mediated ops from opacity_posture or runtime data
    const mediated = s.opacity_posture?.transparent_count ?? '--';
    _setCard('card-mediated', String(mediated));
  }
  if (healthRes.ok) {
    const h = healthRes.data;
    // Deny rate — show count from audit report or deny_rate info
    const denyRate = h.deny_rate;
    if (denyRate) {
      const pct = denyRate.recent_deny_rate;
      const card = _page.querySelector('#card-denied');
      card.setAttribute('value', pct != null ? `${(pct * 100).toFixed(1)}%` : '--');
      if (pct > 0.05) card.setAttribute('variant', 'danger');
      else if (pct > 0) card.setAttribute('variant', 'warning');
    }
  }

  // Approved operations from approvals endpoint (already fetched via status)
  if (statusRes.ok) {
    const s = statusRes.data;
    const approved = s.approval_snapshot?.active_approvals ?? '--';
    _setCard('card-approved', String(approved));

    // Approval-gated from runtime outcome summary
    const opaque = s.opacity_posture?.opaque_count ?? '--';
    _setCard('card-gated', String(opaque));
  }

  // Transparency section
  if (transparencyRes.ok) {
    const t = transparencyRes.data;
    _setCard('card-governed', String(t.governed_operations ?? '--'));
    const ungov = t.ungoverned_observations ?? 0;
    const ungovCard = _page.querySelector('#card-ungoverned');
    ungovCard.setAttribute('value', String(ungov));
    if (ungov > 0) ungovCard.setAttribute('variant', 'warning');

    const pct = t.transparency_pct;
    const transpCard = _page.querySelector('#card-transparency');
    transpCard.setAttribute('value', pct != null ? `${pct.toFixed(1)}%` : '--');
    if (pct != null && pct >= 90) transpCard.setAttribute('variant', 'success');
    else if (pct != null && pct >= 70) transpCard.setAttribute('variant', 'warning');
    else if (pct != null) transpCard.setAttribute('variant', 'danger');
  } else {
    _showError('mp-transparency', transparencyRes.error);
  }

  // Unique users from health
  if (healthRes.ok) {
    const users = healthRes.data.users?.unique_users ?? '--';
    _setCard('card-users', String(users));
  }

  // Recent Activity feed
  _renderRecentActivity(activityRes);
}

// ---------- Internal helpers ----------

function _setCard(id, value) {
  const card = _page?.querySelector(`#${id}`);
  if (card) card.setAttribute('value', value);
}

function _showError(sectionId, error) {
  const section = _page?.querySelector(`#${sectionId}`);
  if (!section) return;
  const existing = section.querySelector('.mp-error');
  if (existing) return; // don't stack errors
  const el = document.createElement('div');
  el.className = 'mp-error';
  el.textContent = error || 'An error occurred';
  section.appendChild(el);
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

  feed.innerHTML = '';
  for (const entry of entries) {
    const row = document.createElement('div');
    row.className = 'mp-feed-row';
    row.tabIndex = 0;

    const time = _formatTime(entry.timestamp_utc);
    const decision = entry.policy_decision || entry.event_category || '';
    const tool = entry.tool || entry.event_type || '';
    const user = entry.user_identity || '';

    // Build row content
    row.innerHTML = `
      <span class="mp-feed-time">${_esc(time)}</span>
      <span class="mp-feed-decision"></span>
      <span class="mp-feed-tool">${_esc(tool)}</span>
      <span class="mp-feed-user">${_esc(user)}</span>
    `;

    // Insert decision tag if applicable
    const decisionSlot = row.querySelector('.mp-feed-decision');
    if (decision === 'ALLOW' || decision === 'DENY') {
      const tag = document.createElement('atd-decision-tag');
      tag.setAttribute('decision', decision);
      decisionSlot.appendChild(tag);
    } else if (decision) {
      decisionSlot.textContent = decision;
    }

    // Click handler — opens Activity with Record Detail for this entry
    const recordId = entry.request_id || entry.event_id || '';
    row.addEventListener('click', () => {
      openActivityWindow(row, { scrollToRecord: recordId });
    });
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') openActivityWindow(row, { scrollToRecord: recordId });
    });

    feed.appendChild(row);
  }
}

function _formatTime(isoStr) {
  if (!isoStr) return '--';
  try {
    const d = new Date(isoStr);
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch {
    return isoStr;
  }
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

/**
 * Open a placeholder window for windows not yet built (Notifications, Licensing).
 */
function _openPlaceholderWindow(title, trigger) {
  const el = document.createElement('div');
  el.innerHTML = `
    <p style="color: #8b919a; text-align: center; padding: 40px 0;">
      ${_esc(title)} window. Built in a later phase.
    </p>
  `;
  if (modalManager.depth > 0) {
    modalManager.replaceChild({ title, trigger, content: el });
  } else {
    modalManager.open({ title, trigger, content: el });
  }
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
  .mp-section {
    margin-bottom: 24px;
  }
  .mp-section-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5b8af5;
    margin: 0 0 12px 0;
    font-weight: 600;
  }
  .mp-feed {
    background: #22262e;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 4px 0;
    min-height: 60px;
  }
  .mp-feed-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
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
    flex: 0 0 80px;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .mp-feed-decision {
    flex: 0 0 70px;
  }
  .mp-feed-tool {
    flex: 1;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .mp-feed-user {
    flex: 0 0 80px;
    color: #8b919a;
    text-align: right;
  }
  .mp-loading {
    color: #8b919a;
    font-size: 0.82rem;
    margin: 0;
    padding: 16px;
    text-align: center;
  }
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
  .mp-launchers {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .mp-launcher {
    background: none;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    color: #5b8af5;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.88rem;
    font-weight: 500;
    padding: 8px 16px;
    transition: background 0.15s, border-color 0.15s;
  }
  .mp-launcher:hover {
    background: rgba(91, 138, 245, 0.12);
    border-color: #5b8af5;
  }
  .mp-launcher:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
`;
document.head.appendChild(mpStyles);
