/**
 * Alerts window — child window (depth 1).
 * D-044 redesign: replaces Notifications with tiered monitoring panes
 * that visually communicate plan differentiation. Five monitoring levels
 * stacked in priority order, with active/inactive state driven by the
 * operator's plan tier.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';

// ---------- Constants ----------

/** Tier ordering for pane activation */
const TIER_LEVELS = {
  personal: 0,
  personal_plus: 1,
  crew: 2,
  team: 3,
  institution: 4,
  business: 4,
  enterprise: 4,
};

/** Human-readable tier names */
const TIER_NAMES = {
  personal: 'Personal', personal_plus: 'Personal Plus',
  crew: 'Crew', team: 'Team', business: 'Business',
  enterprise: 'Enterprise', institution: 'Institution',
};

/** Monitoring pane definitions in priority order */
const MONITORING_PANES = [
  {
    id: 'safety',
    title: 'Safety Alerts',
    activeTier: 'personal',
    description: 'Security vulnerability notifications, chain integrity alerts, emergency notifications.',
    severities: ['security', 'critical'],
    categories: ['chain_integrity', 'security', 'emergency'],
  },
  {
    id: 'operational',
    title: 'Operational Monitoring',
    activeTier: 'personal_plus',
    description: 'DENY rate anomalies, chain health degradation, version updates, stale approval notices.',
    severities: ['critical', 'routine'],
    categories: ['deny_rate', 'health', 'version', 'stale_approval', 'observation_gap'],
  },
  {
    id: 'usage',
    title: 'Usage Pattern Detection',
    activeTier: 'crew',
    description: 'Cross-user DENY pattern alerts, classifier confidence distribution shifts, unusual tool usage patterns.',
    severities: ['routine'],
    categories: ['usage_pattern', 'classifier', 'tool_usage'],
  },
  {
    id: 'governance',
    title: 'Governance Health Monitoring',
    activeTier: 'team',
    description: 'Compliance drift detection, policy rule analysis, unacknowledged alert follow-up.',
    severities: ['routine', 'informational'],
    categories: ['compliance', 'policy_analysis', 'followup'],
  },
  {
    id: 'oversight',
    title: 'Continuous Oversight',
    activeTier: 'institution',
    description: 'Custom alert thresholds, scheduled governance reviews, named contact.',
    severities: ['informational'],
    categories: ['scheduled_review', 'custom_threshold', 'named_contact'],
  },
];

/** Severity display colors */
const SEVERITY_COLORS = {
  security: '#ef4444',
  critical: '#ef4444',
  routine: '#f5a623',
  informational: '#8b919a',
};

/** Map severity to display label */
const SEVERITY_LABELS = {
  security: 'CRITICAL',
  critical: 'WARNING',
  routine: 'WARNING',
  informational: 'INFO',
};

/** Map severity to card border color */
const SEVERITY_BORDER = {
  security: '#ef4444',
  critical: '#ef4444',
  routine: '#f5a623',
  informational: '#22c55e',
};

// ---------- Window entry ----------

/**
 * Open the Alerts window.
 * @param {HTMLElement|null} trigger
 */
export function openAlertsWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'al-root';

  const result = _openAsChild('Alerts', trigger, content);
  if (!result) return;

  const state = { el: content, data: null, tierLevel: 0, tierName: 'Personal' };
  _loadData(state);
}

/** Backward compatibility alias */
export { openAlertsWindow as openNotificationsWindow };

// ---------- Data loading ----------

async function _loadData(state) {
  state.el.innerHTML = '<div class="al-loading">Loading alerts\u2026</div>';

  const [notifRes, modeRes] = await Promise.all([
    api.getNotifications(),
    api.getLicensingMode(),
  ]);

  // Determine operator's tier
  if (modeRes.ok) {
    const tier = modeRes.data.license_tier || 'personal';
    const status = modeRes.data.license_status || '';
    // Trial and unlicensed default to personal
    if (status === 'trial' || status === 'unlicensed') {
      state.tierLevel = 0;
      state.tierName = 'Personal';
    } else {
      state.tierLevel = TIER_LEVELS[tier] ?? 0;
      state.tierName = TIER_NAMES[tier] || 'Personal';
    }
  }

  if (!notifRes.ok) {
    state.el.innerHTML = `<div class="al-error">${_esc(notifRes.error)}</div>`;
    return;
  }

  state.data = notifRes.data;

  // Record that alerts were viewed
  const notifications = state.data.notifications || [];
  if (notifications.length > 0) {
    api.postNotificationsViewed({ count: notifications.length }).catch(() => {});
  }

  _renderAll(state);
}

// ---------- Render ----------

function _renderAll(state) {
  const el = state.el;
  el.innerHTML = '';

  const notifications = state.data.notifications || [];

  // Classify alerts
  const alertsByPane = _classifyAlerts(notifications);

  // Determine overall alert state
  const overallState = _computeOverallState(notifications);

  // Title accent bar
  const accent = document.createElement('div');
  accent.className = `al-title-accent al-accent-${overallState}`;
  el.appendChild(accent);

  // Summary cards
  _renderSummaryCards(el, notifications, state);

  // Tiered monitoring panes
  for (const paneDef of MONITORING_PANES) {
    const paneLevel = TIER_LEVELS[paneDef.activeTier] ?? 0;
    const isActive = state.tierLevel >= paneLevel;
    const alerts = alertsByPane[paneDef.id] || [];
    _renderMonitoringPane(el, paneDef, isActive, alerts, state);
  }
}

function _computeOverallState(notifications) {
  if (!notifications.length) return 'green';
  const hasCritical = notifications.some(n =>
    n.severity === 'security' || n.severity === 'critical'
  );
  return hasCritical ? 'red' : 'amber';
}

function _classifyAlerts(notifications) {
  const result = {};
  for (const pane of MONITORING_PANES) result[pane.id] = [];

  for (const notif of notifications) {
    // Classify by category first, then severity fallback
    const cat = notif.category || '';
    let placed = false;

    for (const pane of MONITORING_PANES) {
      if (cat && pane.categories.includes(cat)) {
        result[pane.id].push(notif);
        placed = true;
        break;
      }
    }

    if (!placed) {
      // Fallback: classify by severity
      const sev = notif.severity || 'informational';
      if (sev === 'security') {
        result.safety.push(notif);
      } else if (sev === 'critical') {
        // Check if it's operational-type
        const msg = (notif.message || '').toLowerCase();
        if (msg.includes('deny') || msg.includes('observation') || msg.includes('stale')) {
          result.operational.push(notif);
        } else {
          result.safety.push(notif);
        }
      } else if (sev === 'routine') {
        result.operational.push(notif);
      } else {
        result.operational.push(notif);
      }
    }
  }

  return result;
}

// ---------- Summary cards ----------

function _renderSummaryCards(el, notifications, state) {
  const active = notifications.length;
  const unacked = notifications.filter(n => !n.acknowledged).length;

  const row = document.createElement('div');
  row.className = 'al-summary-row';

  row.appendChild(_buildSummaryCard(
    'Active alerts', String(active),
    active > 0 ? 'red' : 'green'
  ));
  row.appendChild(_buildSummaryCard(
    'Unacknowledged', String(unacked),
    unacked > 0 ? 'amber' : 'green'
  ));
  row.appendChild(_buildSummaryCard(
    'Monitoring level', state.tierName, 'blue'
  ));

  el.appendChild(row);
}

function _buildSummaryCard(label, value, color) {
  const card = document.createElement('div');
  card.className = 'al-summary-card';
  card.innerHTML = `
    <span class="al-sc-label">${_esc(label)}</span>
    <span class="al-sc-value al-sc-${color}">${_esc(value)}</span>
  `;
  return card;
}

// ---------- Monitoring panes ----------

function _renderMonitoringPane(el, paneDef, isActive, alerts, state) {
  const pane = document.createElement('div');
  pane.className = `al-monitor-pane${isActive ? '' : ' al-pane-inactive'}`;

  // Accent bar color
  let accentColor;
  if (!isActive) {
    accentColor = 'gray';
  } else if (alerts.length > 0) {
    const hasCrit = alerts.some(a => a.severity === 'security' || a.severity === 'critical');
    accentColor = paneDef.id === 'safety' ? (hasCrit ? 'red' : 'green')
                : (alerts.length > 0 ? 'amber' : 'green');
  } else {
    accentColor = 'green';
  }

  const accentBar = document.createElement('div');
  accentBar.className = `al-pane-accent al-accent-${accentColor}`;
  pane.appendChild(accentBar);

  // Header row with title and badge
  const header = document.createElement('div');
  header.className = 'al-pane-header';

  const title = document.createElement('h3');
  title.className = 'al-pane-title';
  title.textContent = paneDef.title;
  header.appendChild(title);

  const badgeTierName = TIER_NAMES[paneDef.activeTier] || paneDef.activeTier;
  const badge = document.createElement('span');
  badge.className = `al-plan-badge ${isActive ? 'al-badge-active' : 'al-badge-inactive'}`;
  badge.textContent = `Active at ${badgeTierName}`;
  header.appendChild(badge);

  pane.appendChild(header);

  if (!isActive) {
    // Inactive pane — show description only
    const desc = document.createElement('p');
    desc.className = 'al-pane-desc';
    desc.textContent = paneDef.description;
    pane.appendChild(desc);

    // Tooltip on hover
    pane.title = `This monitoring level is available on ${badgeTierName} plans. Your current plan is ${state.tierName}.`;
  } else {
    // Active pane — show alert cards or empty state
    if (alerts.length === 0) {
      const empty = document.createElement('p');
      empty.className = 'al-pane-empty';
      empty.textContent = 'No alerts';
      pane.appendChild(empty);
    } else {
      const cardList = document.createElement('div');
      cardList.className = 'al-card-list';
      for (const alert of alerts) {
        cardList.appendChild(_buildAlertCard(alert, state));
      }
      pane.appendChild(cardList);
    }
  }

  el.appendChild(pane);
}

// ---------- Alert cards ----------

function _buildAlertCard(alert, state) {
  const card = document.createElement('div');
  card.className = 'al-alert-card';
  card.tabIndex = 0;
  card.setAttribute('role', 'button');

  const borderColor = SEVERITY_BORDER[alert.severity] || SEVERITY_BORDER.informational;
  card.style.borderLeftColor = borderColor;

  const sevLabel = SEVERITY_LABELS[alert.severity] || 'INFO';
  const sevColor = SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.informational;
  const timestamp = _formatTimestamp(alert.timestamp || alert.created_at);
  const isUnread = !alert.acknowledged && !alert.dismissed;

  card.innerHTML = `
    <div class="al-card-top">
      <div class="al-card-left">
        ${isUnread ? '<span class="al-unread-dot"></span>' : ''}
        <span class="al-card-sev" style="color:${sevColor}">${sevLabel}</span>
        <span class="al-card-title">${_esc(alert.title || '--')}</span>
      </div>
      <span class="al-card-time">${_esc(timestamp)}</span>
    </div>
    <p class="al-card-desc">${_esc(alert.message || '')}</p>
  `;

  // Click opens grandchild detail
  card.addEventListener('click', () => _openAlertDetail(alert, state));
  card.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      _openAlertDetail(alert, state);
    }
  });

  return card;
}

// ---------- Alert detail grandchild ----------

function _openAlertDetail(alert, state) {
  const content = document.createElement('div');
  content.className = 'al-gc';

  const sevLabel = SEVERITY_LABELS[alert.severity] || 'INFO';
  const sevColor = SEVERITY_COLORS[alert.severity] || SEVERITY_COLORS.informational;
  const timestamp = _formatTimestamp(alert.timestamp || alert.created_at);
  const isUnread = !alert.acknowledged && !alert.dismissed;

  content.innerHTML = `
    <div class="al-gc-accent al-accent-${alert.severity === 'security' || alert.severity === 'critical' ? 'red' : 'amber'}"></div>
    <div class="al-gc-header">
      <span class="al-gc-sev" style="color:${sevColor}">${sevLabel}</span>
      ${isUnread ? '<span class="al-gc-unread">UNACKNOWLEDGED</span>' : '<span class="al-gc-acked">ACKNOWLEDGED</span>'}
    </div>

    <h3 class="al-gc-title">${_esc(alert.title || '--')}</h3>

    <div class="al-gc-section">
      <h4 class="al-gc-section-head">DESCRIPTION</h4>
      <p class="al-gc-text">${_esc(alert.message || 'No additional detail.')}</p>
    </div>

    <div class="al-gc-section">
      <h4 class="al-gc-section-head">GENERATED</h4>
      <p class="al-gc-text">${_esc(timestamp)}</p>
    </div>

    <div class="al-gc-section">
      <h4 class="al-gc-section-head">TRIGGER</h4>
      <p class="al-gc-text">${_esc(_describeTrigger(alert))}</p>
    </div>

    <div class="al-gc-section">
      <h4 class="al-gc-section-head">GUIDANCE</h4>
      <p class="al-gc-text">${_esc(_describeGuidance(alert))}</p>
    </div>

    <div class="al-gc-actions" id="al-gc-actions"></div>
  `;

  const actions = content.querySelector('#al-gc-actions');

  // Acknowledge button (if not already acknowledged/dismissed)
  if (!alert.acknowledged && !alert.dismissed && !alert.persistent) {
    const ackBtn = document.createElement('button');
    ackBtn.className = 'al-gc-btn al-gc-btn-primary';
    ackBtn.textContent = 'Acknowledge';
    ackBtn.addEventListener('click', async () => {
      const res = await api.postDismissNotification({ notification_id: alert.id });
      if (res.ok) {
        alert.acknowledged = true;
        ackBtn.textContent = 'Acknowledged';
        ackBtn.disabled = true;
        ackBtn.classList.add('al-gc-btn-done');
      }
    });
    actions.appendChild(ackBtn);
  }

  // Cross-window navigation links
  const links = _getCrossWindowLinks(alert);
  for (const link of links) {
    const btn = document.createElement('button');
    btn.className = 'al-gc-btn al-gc-btn-link';
    btn.textContent = link.label;
    btn.addEventListener('click', () => {
      modalManager.closeAll();
      setTimeout(() => {
        import(link.module).then(mod => {
          const opener = mod[link.fn];
          if (opener) opener(null, link.opts || {});
        });
      }, 0);
    });
    actions.appendChild(btn);
  }

  modalManager.open({ title: 'Alert Detail', trigger: state.el, content });
}

function _describeTrigger(alert) {
  const msg = (alert.message || '').toLowerCase();
  const cat = alert.category || '';

  if (cat === 'chain_integrity' || msg.includes('chain integrity') || msg.includes('hash mismatch')) {
    return 'Chain integrity verification detected a hash mismatch or structural break in the governance decision chain.';
  }
  if (cat === 'deny_rate' || msg.includes('deny rate') || msg.includes('deny count')) {
    return 'The DENY rate exceeded the historical average threshold, indicating an anomalous pattern of denied operations.';
  }
  if (cat === 'observation_gap' || msg.includes('observation gap') || msg.includes('ungoverned')) {
    return 'A gap in governance observations was detected. Operations may be occurring outside the governed tool boundary.';
  }
  if (cat === 'security' || msg.includes('vulnerability') || msg.includes('security')) {
    return 'A security-relevant condition was detected that may require immediate attention.';
  }
  if (msg.includes('trial') || msg.includes('license') || msg.includes('expir')) {
    return 'License or trial state changed — governance coverage may be affected.';
  }
  if (msg.includes('stale') || msg.includes('approval')) {
    return 'An approval has been inactive for an extended period, creating an open exception with no current purpose.';
  }
  return alert.trigger || 'Automated monitoring detected this condition from system health signals.';
}

function _describeGuidance(alert) {
  const msg = (alert.message || '').toLowerCase();
  const cat = alert.category || '';

  if (cat === 'chain_integrity' || msg.includes('chain integrity') || msg.includes('hash mismatch')) {
    return 'Open the Health window to review Chain Integrity details. If a break is confirmed, the system will record a repair event. Check that no external process is modifying the chain file.';
  }
  if (cat === 'deny_rate' || msg.includes('deny rate') || msg.includes('deny count')) {
    return 'Review the DENY pattern in the Activity log. Frequent DENYs to the same tool or path may indicate a policy rule that needs adjustment or an agent attempting unauthorized operations.';
  }
  if (cat === 'observation_gap' || msg.includes('observation gap') || msg.includes('ungoverned')) {
    return 'Check that observation hooks are installed and running. Ungoverned operations reduce the Transparency metric and may indicate tooling that bypasses governance.';
  }
  if (cat === 'security' || msg.includes('vulnerability') || msg.includes('security')) {
    return 'Review the alert details immediately. Security alerts may require changes to your policy rules or infrastructure configuration.';
  }
  if (msg.includes('trial') || msg.includes('license') || msg.includes('expir')) {
    return 'Open the Licensing window to review your current tier and registration status.';
  }
  if (msg.includes('stale') || msg.includes('approval')) {
    return 'Open the Approvals window to review and revoke stale approvals. Revoking unused approvals reduces exposure without affecting active operations.';
  }
  return 'Review the alert details and take appropriate action based on your organization\u2019s governance policies.';
}

function _getCrossWindowLinks(alert) {
  const links = [];
  const msg = (alert.message || '').toLowerCase();
  const cat = alert.category || '';

  if (cat === 'chain_integrity' || msg.includes('chain') || msg.includes('integrity') || msg.includes('hash')) {
    links.push({
      label: 'Open Health',
      module: './health.js',
      fn: 'openHealthWindow',
    });
  }
  if (cat === 'deny_rate' || msg.includes('deny')) {
    links.push({
      label: 'View in Activity',
      module: './activity.js',
      fn: 'openActivityWindow',
      opts: { decisionFilter: 'DENY' },
    });
  }
  if (msg.includes('stale') || msg.includes('approval') || cat === 'stale_approval') {
    links.push({
      label: 'Open Approvals',
      module: './approvals.js',
      fn: 'openApprovalsWindow',
    });
  }
  if (msg.includes('license') || msg.includes('trial') || msg.includes('expir')) {
    links.push({
      label: 'Open Licensing',
      module: './licensing.js',
      fn: 'openLicensingWindow',
    });
  }

  return links;
}

// ---------- Helpers ----------

function _formatTimestamp(isoStr) {
  if (!isoStr) return '--';
  try {
    const d = new Date(isoStr);
    const now = new Date();
    const sameDay = d.toDateString() === now.toDateString();

    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    const time = `${hh}:${mm}:${ss}`;

    if (sameDay) return time;

    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    return `${months[d.getMonth()]} ${d.getDate()}, ${time}`;
  } catch {
    return isoStr;
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

// ---------- Styles ----------

const alStyles = document.createElement('style');
alStyles.textContent = `
  .al-root { font-family: "Inter", system-ui, sans-serif; }
  .al-loading, .al-error {
    font-size: 0.82rem; padding: 40px 0; text-align: center;
  }
  .al-loading { color: #8b919a; }
  .al-error {
    color: #f59e42; background: rgba(245,158,66,0.10);
    padding: 12px 16px; border-radius: 8px;
  }

  /* Title accent bar */
  .al-title-accent { height: 6px; border-radius: 3px 3px 0 0; margin: -16px -24px 16px; }
  .al-accent-green { background: #22c55e; }
  .al-accent-amber { background: #f5a623; }
  .al-accent-red { background: #ef4444; }
  .al-accent-gray { background: #6b7280; }

  /* Summary cards */
  .al-summary-row {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 12px; margin-bottom: 20px;
  }
  .al-summary-card {
    background: #22262e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 14px 16px;
    display: flex; flex-direction: column; gap: 4px; text-align: center;
  }
  .al-sc-label {
    font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #6b7280; font-weight: 500;
  }
  .al-sc-value { font-size: 1.3rem; font-weight: 700; font-family: "JetBrains Mono", monospace; }
  .al-sc-red { color: #ef4444; }
  .al-sc-amber { color: #f5a623; }
  .al-sc-green { color: #22c55e; }
  .al-sc-blue { color: #5b8af5; }

  /* Monitoring panes */
  .al-monitor-pane {
    background: #22262e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; margin-bottom: 12px; overflow: hidden;
    position: relative;
  }
  .al-pane-inactive {
    opacity: 0.4;
  }
  .al-pane-accent { height: 6px; }
  .al-pane-header {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 18px 8px;
  }
  .al-pane-title {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em;
    color: #5b8af5; margin: 0; font-weight: 600;
  }
  .al-pane-inactive .al-pane-title { color: #8b919a; }

  .al-plan-badge {
    font-size: 0.62rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; padding: 2px 8px; border-radius: 4px;
  }
  .al-badge-active {
    background: rgba(34,197,94,0.15); color: #22c55e;
  }
  .al-badge-inactive {
    background: rgba(107,114,128,0.15); color: #6b7280;
  }

  .al-pane-desc {
    font-size: 0.82rem; color: #8b919a; margin: 0;
    padding: 0 18px 14px; line-height: 1.5;
  }
  .al-pane-empty {
    font-size: 0.82rem; color: #6b7280; font-style: italic;
    text-align: center; margin: 0; padding: 16px 18px;
  }

  /* Alert cards */
  .al-card-list { padding: 0 12px 12px; }
  .al-alert-card {
    background: #1a1d24; border: 1px solid rgba(255,255,255,0.06);
    border-left: 3px solid #8b919a; border-radius: 8px;
    padding: 12px 14px; margin-bottom: 8px;
    cursor: pointer; transition: background 0.12s;
  }
  .al-alert-card:hover { background: #20232b; }
  .al-alert-card:focus-visible {
    outline: 2px solid #5b8af5; outline-offset: 2px;
  }
  .al-alert-card:last-child { margin-bottom: 0; }

  .al-card-top {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 4px;
  }
  .al-card-left { display: flex; align-items: center; gap: 8px; }
  .al-unread-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: #5b8af5; flex-shrink: 0;
  }
  .al-card-sev {
    font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .al-card-title {
    font-size: 0.85rem; font-weight: 600; color: #e4e6eb;
  }
  .al-card-time {
    font-size: 0.72rem; color: #6b7280;
    font-family: "JetBrains Mono", monospace;
  }
  .al-card-desc {
    font-size: 0.78rem; color: #8b919a; margin: 0; line-height: 1.45;
  }

  /* Grandchild detail */
  .al-gc { font-family: "Inter", system-ui, sans-serif; }
  .al-gc-accent { height: 6px; margin: -16px -24px 16px; }
  .al-gc-header {
    display: flex; align-items: center; gap: 10px; margin-bottom: 12px;
  }
  .al-gc-sev {
    font-size: 0.72rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .al-gc-unread {
    font-size: 0.62rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; padding: 2px 8px; border-radius: 4px;
    background: rgba(245,166,35,0.15); color: #f5a623;
  }
  .al-gc-acked {
    font-size: 0.62rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.04em; padding: 2px 8px; border-radius: 4px;
    background: rgba(34,197,94,0.15); color: #22c55e;
  }
  .al-gc-title {
    font-size: 1.1rem; font-weight: 600; color: #e4e6eb;
    margin: 0 0 16px;
  }
  .al-gc-section { margin-bottom: 16px; }
  .al-gc-section-head {
    font-size: 0.65rem; text-transform: uppercase; letter-spacing: 0.08em;
    color: #5b8af5; font-weight: 600; margin: 0 0 6px;
  }
  .al-gc-text {
    font-size: 0.82rem; color: #c4c8d0; margin: 0; line-height: 1.55;
  }

  .al-gc-actions {
    display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px;
    padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.08);
  }
  .al-gc-btn {
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem; font-weight: 500; border-radius: 8px;
    padding: 8px 16px; cursor: pointer; border: none;
    transition: background 0.12s;
  }
  .al-gc-btn-primary {
    background: #22c55e; color: #0a0c10;
  }
  .al-gc-btn-primary:hover { background: #16a34a; }
  .al-gc-btn-primary:disabled {
    opacity: 0.5; cursor: default;
  }
  .al-gc-btn-done {
    background: rgba(34,197,94,0.15) !important; color: #22c55e !important;
  }
  .al-gc-btn-link {
    background: rgba(91,138,245,0.12); color: #5b8af5;
  }
  .al-gc-btn-link:hover { background: rgba(91,138,245,0.22); }

  /* Responsive */
  @media (max-width: 600px) {
    .al-summary-row { grid-template-columns: 1fr; }
    .al-card-top { flex-direction: column; align-items: flex-start; gap: 4px; }
  }
`;
document.head.appendChild(alStyles);
