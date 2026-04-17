/**
 * Main page shell for the Atested operator UI.
 * Renders the home state below the chrome bar with designated areas
 * for display elements and launchers.
 * Spec v2 section 5.
 *
 * Phase 1: placeholder content in each area. Real data comes in Phase 3.
 */

import { modalManager } from './modal-manager.js';

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

export function renderMainPage() {
  const page = document.createElement('div');
  page.id = 'main-page';
  page.innerHTML = `
    <section class="mp-section">
      <h2 class="mp-section-title">Chain Health</h2>
      <div class="mp-card-grid">
        <div class="mp-card">
          <span class="mp-card-label">Chain Events</span>
          <span class="mp-card-value">--</span>
        </div>
        <div class="mp-card">
          <span class="mp-card-label">Chain Integrity</span>
          <span class="mp-card-value mp-card-ok">OK</span>
        </div>
      </div>
    </section>

    <section class="mp-section">
      <h2 class="mp-section-title">Governance Activity</h2>
      <div class="mp-card-grid">
        <div class="mp-card">
          <span class="mp-card-label">Mediated Operations</span>
          <span class="mp-card-value">--</span>
        </div>
        <div class="mp-card">
          <span class="mp-card-label">Actions Denied</span>
          <span class="mp-card-value">--</span>
        </div>
        <div class="mp-card">
          <span class="mp-card-label">Approved Operations</span>
          <span class="mp-card-value">--</span>
        </div>
        <div class="mp-card">
          <span class="mp-card-label">Approval-Gated</span>
          <span class="mp-card-value">--</span>
        </div>
      </div>
    </section>

    <section class="mp-section">
      <h2 class="mp-section-title">Transparency & Coverage</h2>
      <div class="mp-card-grid">
        <div class="mp-card">
          <span class="mp-card-label">Governed Operations</span>
          <span class="mp-card-value">--</span>
        </div>
        <div class="mp-card">
          <span class="mp-card-label">Ungoverned Operations</span>
          <span class="mp-card-value">--</span>
        </div>
        <div class="mp-card">
          <span class="mp-card-label">Transparency Rate</span>
          <span class="mp-card-value">--</span>
        </div>
        <div class="mp-card">
          <span class="mp-card-label">Unique Users</span>
          <span class="mp-card-value">--</span>
        </div>
      </div>
    </section>

    <section class="mp-section">
      <h2 class="mp-section-title">Recent Activity</h2>
      <div class="mp-feed">
        <p class="mp-placeholder">No activity data loaded. Data layer connects in Phase 3.</p>
      </div>
    </section>

    <section class="mp-section">
      <h2 class="mp-section-title">Workflows</h2>
      <div class="mp-launchers" id="launcher-grid"></div>
    </section>
  `;

  // Render launcher buttons
  const grid = page.querySelector('#launcher-grid');
  for (const launcher of LAUNCHERS) {
    const btn = document.createElement('button');
    btn.className = 'mp-launcher';
    btn.textContent = launcher.label;
    btn.dataset.windowId = launcher.id;
    btn.addEventListener('click', () => {
      _openWindow(launcher.label, btn);
    });
    grid.appendChild(btn);
  }

  return page;
}

function _openWindow(title, trigger) {
  // If a window is already open at depth 1, replace it (chrome-level behavior).
  // For launcher clicks from main page, just open normally.
  if (modalManager.depth > 0) {
    modalManager.replaceChild({
      title,
      trigger,
      content: _placeholderContent(title),
    });
  } else {
    modalManager.open({
      title,
      trigger,
      content: _placeholderContent(title),
    });
  }
}

function _placeholderContent(title) {
  const el = document.createElement('div');
  el.innerHTML = `
    <p style="color: #8b919a; text-align: center; padding: 40px 0;">
      ${title} window content. Built in Phase 4.
    </p>
    <button class="test-grandchild-btn" style="
      display: block; margin: 0 auto; padding: 8px 16px;
      background: none; border: 1px solid rgba(255,255,255,0.08);
      color: #8b919a; border-radius: 8px; cursor: pointer;
      font-family: inherit; font-size: 0.82rem;
    ">Test: Open grandchild</button>
  `;
  el.querySelector('.test-grandchild-btn').addEventListener('click', (e) => {
    modalManager.open({
      title: `Record Detail (test)`,
      trigger: e.target,
      content: _grandchildPlaceholder(),
    });
  });
  return el;
}

function _grandchildPlaceholder() {
  const el = document.createElement('div');
  el.innerHTML = `
    <p style="color: #8b919a; text-align: center; padding: 40px 0;">
      Grandchild window (depth 2). Record Detail lives here in Phase 4.
    </p>
    <p style="color: #5b8af5; text-align: center; font-size: 0.82rem;">
      Press Esc to close this grandchild, then Esc again to close the parent.
    </p>
  `;
  return el;
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
  .mp-card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
  }
  .mp-card {
    background: #22262e;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .mp-card-label {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
  }
  .mp-card-value {
    font-size: 1.5rem;
    font-weight: 600;
    color: #e4e6eb;
  }
  .mp-card-ok {
    color: #4ade80;
  }
  .mp-feed {
    background: #22262e;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 20px;
    min-height: 60px;
  }
  .mp-placeholder {
    color: #8b919a;
    font-size: 0.82rem;
    margin: 0;
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
