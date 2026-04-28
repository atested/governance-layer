/**
 * Reports window — child window (depth 1).
 * D-141/D-142 redesign: predefined report cards, default time ranges,
 * formatted report views, Activity drill-through, and JSON export.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { installWindowTooltips, setTooltip, setTooltips } from '../tooltip-utils.js';
import { recordUiAggregate, flushTelemetrySummary } from '../summary-telemetry.js';

const REPORT_TEMPLATES = [
  {
    id: 'governance-summary',
    title: 'Governance Summary',
    subtitle: 'What happened in the selected period',
    accent: 'green',
    defaultRange: '7d',
    groups: ['decision', 'tool', 'category'],
  },
  {
    id: 'denial-patterns',
    title: 'Denial Patterns',
    subtitle: 'Where policy is stopping risky activity',
    accent: 'amber',
    defaultRange: '30d',
    groups: ['tool', 'category', 'user'],
  },
  {
    id: 'operator-comparison',
    title: 'Operator Comparison',
    subtitle: 'Compare activity by user or agent identity',
    accent: 'blue',
    defaultRange: '30d',
    groups: ['user', 'decision', 'tool'],
  },
  {
    id: 'audit-evidence',
    title: 'Audit Evidence Pack',
    subtitle: 'Evidence summary for external review',
    accent: 'purple',
    defaultRange: 'all',
    groups: ['decision', 'category', 'tool'],
  },
  {
    id: 'unusual-activity',
    title: 'Unusual Activity Watch',
    subtitle: 'Low-frequency and high-denial signals',
    accent: 'red',
    defaultRange: '7d',
    groups: ['tool', 'category', 'hour', 'user'],
  },
  {
    id: 'telemetry-summary',
    title: 'Telemetry Transparency',
    subtitle: 'Exactly what anonymous summary telemetry contains',
    accent: 'purple',
    defaultRange: '30d',
    groups: [],
  },
  {
    id: 'trouble-history',
    title: 'Trouble History',
    subtitle: 'Support requests and captured page context',
    accent: 'amber',
    defaultRange: '30d',
    groups: [],
  },
];

const REPORT_BY_ID = Object.fromEntries(REPORT_TEMPLATES.map(r => [r.id, r]));

const TELEMETRY_PURPOSE =
  'Atested telemetry helps Atested deliver proactive support and improve the product. The data is minimal, anonymous, and optional.';

const TELEMETRY_PRIVACY_TEXT =
  'Atested telemetry is anonymous by design. Atested counts interactions in memory and periodically writes a summary, never individual events. The summary is what gets transmitted. No click logs, no event order, no timestamps, no session IDs, no file paths, no user identities. Session reconstruction is not possible because the raw data never exists. Not on your machine, not on ours.';

const TELEMETRY_CATEGORIES = [
  {
    key: 'ui_interactions',
    title: 'UI Interactions',
    accent: 'blue',
    copy: 'Summarized counts of how you use the dashboard. Which windows you open, which reports you run. Anonymous, no session detail.',
  },
  {
    key: 'governance_usage_data',
    title: 'Governance Usage Data',
    accent: 'green',
    copy: 'Aggregated decision counts. Total operations, allow/deny breakdown, action categories. The same data that powers your reports, summarized for Atested.',
  },
  {
    key: 'trouble_submissions',
    title: 'Trouble Submissions',
    accent: 'amber',
    copy: "Support requests you've sent through the Trouble button.",
  },
  {
    key: 'system_health',
    title: 'System Health',
    accent: 'purple',
    copy: "Chain size, integrity status, version checks. Keeps us aware of your installation's health so we can reach out if something needs attention.",
  },
];

/**
 * Open the Reports window.
 * @param {HTMLElement|null} trigger
 */
export function openReportsWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'rp-root';

  const result = _openAsChild('Reports', 'Atested metrics and trends over time', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    startTime: '',
    endTime: '',
    activeRange: REPORT_BY_ID['governance-summary'].defaultRange,
    reportId: 'governance-summary',
    data: null,
  };

  _buildUI(state);
  _applyRange(state, state.activeRange, { load: false });
  installWindowTooltips(content);
  _applyStaticTooltips(state);
  _wireControls(state);
  _loadReport(state);
}

function _applyStaticTooltips(state) {
  setTooltips(state.el, [
    ['#rp-from', 'Start of the reporting time range.'],
    ['#rp-to', 'End of the reporting time range.'],
    ['#rp-export', 'Export the current formatted report as clean JSON.'],
    ['#rp-stat-total', 'Total records included in this report.'],
    ['#rp-stat-allow', 'Allowed operations in the report range.'],
    ['#rp-stat-deny', 'Denied operations in the report range.'],
    ['#rp-stat-rate', 'Denied records divided by total records.'],
  ]);
  state.el.querySelectorAll('.rp-quick-btn').forEach(btn => {
    setTooltip(btn, `Set the report range to ${btn.textContent.trim()}.`);
  });
  state.el.querySelectorAll('.rp-report-card').forEach(card => {
    const report = REPORT_BY_ID[card.dataset.report];
    if (report) setTooltip(card, `${report.title}: ${report.subtitle}.`);
  });
}

// ---------- Build UI ----------

function _buildUI(state) {
  const el = state.el;
  el.innerHTML = `
    <div class="rp-report-picker" id="rp-report-picker">
      ${REPORT_TEMPLATES.map(report => `
        <button class="rp-report-card rp-report-${report.accent}${report.id === state.reportId ? ' rp-report-active' : ''}" data-report="${report.id}">
          <span class="rp-report-accent"></span>
          <span class="rp-report-title">${_esc(report.title)}</span>
          <span class="rp-report-subtitle">${_esc(report.subtitle)}</span>
        </button>
      `).join('')}
    </div>

    <!-- Filter panes -->
    <div class="rp-filter-row">
      <div class="rp-filter-pane">
        <div class="rp-fp-accent"></div>
        <div class="rp-fp-header">Time range</div>
        <div class="rp-fp-body">
          <div class="rp-fp-fields">
            <label class="rp-fp-label">
              From
              <input type="datetime-local" class="rp-input" id="rp-from">
            </label>
            <label class="rp-fp-label">
              To
              <input type="datetime-local" class="rp-input" id="rp-to">
            </label>
          </div>
          <div class="rp-fp-quick" id="rp-quick-btns">
            <button class="rp-quick-btn" data-range="1h">Last hour</button>
            <button class="rp-quick-btn" data-range="today">Today</button>
            <button class="rp-quick-btn" data-range="7d">Last 7 days</button>
            <button class="rp-quick-btn" data-range="30d">Last 30 days</button>
            <button class="rp-quick-btn" data-range="all">All time</button>
          </div>
        </div>
      </div>
      <div class="rp-filter-pane">
        <div class="rp-fp-accent"></div>
        <div class="rp-fp-header">Report options</div>
        <div class="rp-fp-body">
          <div class="rp-selected-report">
            <span class="rp-fp-mini-label">Selected report</span>
            <span class="rp-selected-title" id="rp-selected-title">${_esc(REPORT_BY_ID[state.reportId].title)}</span>
            <span class="rp-selected-subtitle" id="rp-selected-subtitle">${_esc(REPORT_BY_ID[state.reportId].subtitle)}</span>
          </div>
          <div class="rp-fp-actions">
            <button class="rp-btn rp-btn-export" id="rp-export">Export JSON</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Stat cards -->
    <div class="rp-stats">
      <div class="rp-stat-card">
        <span class="rp-stat-label">Total records</span>
        <span class="rp-stat-value" id="rp-stat-total">\u2014</span>
      </div>
      <div class="rp-stat-card rp-stat-green">
        <span class="rp-stat-label">Allow</span>
        <span class="rp-stat-value rp-val-green" id="rp-stat-allow">\u2014</span>
      </div>
      <div class="rp-stat-card rp-stat-amber">
        <span class="rp-stat-label">Deny</span>
        <span class="rp-stat-value rp-val-amber" id="rp-stat-deny">\u2014</span>
      </div>
      <div class="rp-stat-card">
        <span class="rp-stat-label">Deny rate</span>
        <span class="rp-stat-value" id="rp-stat-rate">\u2014</span>
      </div>
    </div>

    <!-- Report pane -->
    <div class="rp-group-pane" id="rp-group-pane">
      <div class="rp-gp-accent"></div>
      <div class="rp-gp-header">
        <span id="rp-gp-title">Governance Summary</span>
        <span class="rp-gp-count" id="rp-gp-count"></span>
      </div>
      <div class="rp-gp-body" id="rp-gp-body">
        <div class="rp-loading">Loading\u2026</div>
      </div>
    </div>
  `;
}

// ---------- Wire controls ----------

function _wireControls(state) {
  const el = state.el;

  el.querySelector('#rp-report-picker').addEventListener('click', (e) => {
    const card = e.target.closest('[data-report]');
    if (!card) return;
    state.reportId = card.dataset.report;
    el.querySelectorAll('.rp-report-card').forEach(c => c.classList.remove('rp-report-active'));
    card.classList.add('rp-report-active');
    const report = REPORT_BY_ID[state.reportId];
    el.querySelector('#rp-selected-title').textContent = report.title;
    el.querySelector('#rp-selected-subtitle').textContent = report.subtitle;
    recordUiAggregate('report_runs', state.reportId);
    _applyRange(state, report.defaultRange || '7d');
  });

  // Quick-select time buttons
  el.querySelector('#rp-quick-btns').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-range]');
    if (!btn) return;
    recordUiAggregate('range_shortcuts', btn.dataset.range);
    _applyRange(state, btn.dataset.range);
  });

  const onCustomRange = () => {
    _setActiveRange(state, 'custom');
    if (!_readTimeFilters(state)) return;
    recordUiAggregate('report_runs', state.reportId);
    _loadReport(state);
  };
  el.querySelector('#rp-from').addEventListener('change', onCustomRange);
  el.querySelector('#rp-to').addEventListener('change', onCustomRange);

  // Export button
  el.querySelector('#rp-export').addEventListener('click', () => _exportJSON(state));
}

function _readTimeFilters(state) {
  const fromVal = state.el.querySelector('#rp-from').value;
  const toVal = state.el.querySelector('#rp-to').value;
  if (!fromVal && !toVal) {
    state.startTime = '';
    state.endTime = '';
    state.rangeError = '';
    return true;
  }
  if (!fromVal || !toVal) {
    state.rangeError = 'Enter both From and To, or use All time.';
    _renderRangeError(state);
    return false;
  }
  const start = new Date(fromVal);
  const end = new Date(toVal);
  if (!Number.isFinite(start.getTime()) || !Number.isFinite(end.getTime())) {
    state.rangeError = 'Enter valid From and To dates.';
    _renderRangeError(state);
    return false;
  }
  if (end.getTime() < start.getTime()) {
    state.rangeError = 'End date must be after start date.';
    _renderRangeError(state);
    return false;
  }
  state.startTime = start.toISOString();
  state.endTime = end.toISOString();
  state.rangeError = '';
  return true;
}

function _applyRange(state, range, opts = {}) {
  const now = new Date();
  let from = '';
  if (range === '1h') {
    from = new Date(now.getTime() - 3600000).toISOString();
  } else if (range === 'today') {
    const d = new Date(now);
    d.setHours(0, 0, 0, 0);
    from = d.toISOString();
  } else if (range === '7d') {
    from = new Date(now.getTime() - 7 * 86400000).toISOString();
  } else if (range === '30d') {
    from = new Date(now.getTime() - 30 * 86400000).toISOString();
  }
  state.startTime = from;
  state.endTime = range === 'all' ? '' : now.toISOString();
  state.el.querySelector('#rp-from').value = from ? _isoToLocal(from) : '';
  state.el.querySelector('#rp-to').value = state.endTime ? _isoToLocal(state.endTime) : '';
  _setActiveRange(state, range);
  if (opts.load !== false) _loadReport(state);
}

function _setActiveRange(state, range) {
  state.activeRange = range;
  state.el.querySelectorAll('.rp-quick-btn').forEach(btn => {
    btn.classList.toggle('rp-quick-active', btn.dataset.range === range);
  });
}

// ---------- Load report ----------

async function _loadReport(state) {
  const body = state.el.querySelector('#rp-gp-body');
  body.innerHTML = '<div class="rp-loading">Loading\u2026</div>';
  if (state.rangeError) {
    _renderRangeError(state);
    return;
  }

  const template = REPORT_BY_ID[state.reportId] || REPORT_TEMPLATES[0];
  const params = {};
  if (state.startTime) params.start_time = state.startTime;
  if (state.endTime) params.end_time = state.endTime;

  if (template.id === 'telemetry-summary') {
    await flushTelemetrySummary();
    const res = await api.getTelemetrySummary();
    if (!res.ok) {
      body.innerHTML = `<div class="rp-error">${_esc(res.error)}</div>`;
      return;
    }
    state.data = _composeTelemetryReportData(template, res.data, params);
    _renderStats(state);
    _renderReportView(state);
    return;
  }
  if (template.id === 'trouble-history') {
    const res = await api.getTroubleReports();
    if (!res.ok) {
      body.innerHTML = `<div class="rp-error">${_esc(res.error)}</div>`;
      return;
    }
    state.data = _composeTroubleReportData(template, res.data, params);
    _renderStats(state);
    _renderReportView(state);
    return;
  }

  const groupKeys = Array.from(new Set(template.groups));
  const results = await Promise.all(groupKeys.map(async group => {
    const res = await api.getAuditReport({ ...params, group_by: group });
    return [group, res];
  }));

  const failed = results.find(([, res]) => !res.ok);
  if (failed) {
    body.innerHTML = `<div class="rp-error">${_esc(failed[1].error)}</div>`;
    return;
  }

  const grouped = {};
  for (const [group, res] of results) grouped[group] = res.data;

  const base = grouped[groupKeys[0]] || {};
  state.data = _composeReportData(template, grouped, base, params);
  _renderStats(state);
  _renderReportView(state);
}

function _renderRangeError(state) {
  const body = state.el.querySelector('#rp-gp-body');
  if (!body) return;
  const title = state.el.querySelector('#rp-gp-title');
  const count = state.el.querySelector('#rp-gp-count');
  const template = REPORT_BY_ID[state.reportId] || REPORT_TEMPLATES[0];
  if (title) title.textContent = template.title;
  if (count) count.textContent = 'Invalid range';
  body.innerHTML = `<div class="rp-error">${_esc(state.rangeError || 'Invalid report time range.')}</div>`;
}

function _composeReportData(template, grouped, base, params) {
  const summary = base.decision_summary || {};
  const total = base.total_records || 0;
  const allow = summary.ALLOW || 0;
  const deny = summary.DENY || 0;
  const denyRate = total > 0 ? deny / total : 0;
  return {
    generated_at: new Date().toISOString(),
    report_id: template.id,
    report_title: template.title,
    report_subtitle: template.subtitle,
    time_range: base.time_range || { start: params.start_time || null, end: params.end_time || null },
    total_records: total,
    decision_summary: summary,
    deny_rate: denyRate,
    groups: grouped,
    findings: _buildFindings(template.id, grouped, { total, allow, deny, denyRate }),
  };
}

function _composeTelemetryReportData(template, payload, params = {}) {
  const summary = payload.summary || {};
  const categories = payload.categories || summary.categories || {};
  const transmissions = summary.transmissions || [];
  return {
    generated_at: new Date().toISOString(),
    report_id: template.id,
    report_title: template.title,
    report_subtitle: template.subtitle,
    time_range: { start: params.start_time || null, end: params.end_time || null },
    total_records: 0,
    decision_summary: {},
    deny_rate: null,
    groups: {},
    telemetry: {
      opted_in: !!payload.opted_in,
      summary,
      categories,
      transmissions,
      period_count: Object.keys(summary.periods || {}).length,
    },
    findings: [],
  };
}

function _composeTroubleReportData(template, payload, params = {}) {
  const startMs = params.start_time ? new Date(params.start_time).getTime() : null;
  const endMs = params.end_time ? new Date(params.end_time).getTime() : null;
  const reports = (payload.reports || []).filter(report => {
    const ts = new Date(report.timestamp_utc || report.timestamp || '').getTime();
    if (!Number.isFinite(ts)) return true;
    if (startMs && ts < startMs) return false;
    if (endMs && ts > endMs) return false;
    return true;
  }).slice().sort((a, b) =>
    String(b.timestamp_utc || b.timestamp || '').localeCompare(String(a.timestamp_utc || a.timestamp || ''))
  );
  const priorityCounts = {};
  for (const report of reports) {
    const priority = report.priority || 'normal';
    priorityCounts[priority] = (priorityCounts[priority] || 0) + 1;
  }
  const latest = reports[0] || null;
  return {
    generated_at: new Date().toISOString(),
    report_id: template.id,
    report_title: template.title,
    report_subtitle: template.subtitle,
    time_range: { start: params.start_time || null, end: params.end_time || null },
    total_records: reports.length,
    decision_summary: { ALLOW: 0, DENY: 0 },
    deny_rate: 0,
    groups: {},
    trouble: { reports, priority_counts: priorityCounts },
    findings: [
      { label: 'Trouble reports', value: _fmtNum(reports.length), tone: 'amber', detail: 'Support requests stored locally for operator review.' },
      { label: 'High or urgent', value: _fmtNum((priorityCounts.high || 0) + (priorityCounts.urgent || 0)), tone: 'red', detail: 'Reports marked high or urgent priority.' },
      { label: 'Latest context', value: latest?.context?.current_window || 'None', tone: 'blue', detail: latest ? 'Most recent captured window context.' : 'No trouble reports submitted yet.' },
      { label: 'Chain storage', value: 'No', tone: 'green', detail: 'Trouble reports are support artifacts, not governance chain records.' },
    ],
  };
}

// ---------- Render stats ----------

function _renderStats(state) {
  const d = state.data;
  const stats = state.el.querySelector('.rp-stats');
  if (stats) stats.style.display = d.report_id === 'telemetry-summary' ? 'none' : '';
  if (d.report_id === 'telemetry-summary') return;

  const summary = d.decision_summary || {};
  const total = d.total_records || 0;
  const allow = summary.ALLOW || 0;
  const deny = summary.DENY || 0;
  const rate = total > 0 ? ((deny / total) * 100).toFixed(1) + '%' : '0%';

  state.el.querySelector('#rp-stat-total').textContent = _fmtNum(total);
  state.el.querySelector('#rp-stat-allow').textContent = _fmtNum(allow);
  state.el.querySelector('#rp-stat-deny').textContent = _fmtNum(deny);
  state.el.querySelector('#rp-stat-rate').textContent = rate;
}

// ---------- Render predefined reports ----------

function _renderReportView(state) {
  const d = state.data;
  const template = REPORT_BY_ID[d.report_id] || REPORT_TEMPLATES[0];
  const body = state.el.querySelector('#rp-gp-body');
  const title = state.el.querySelector('#rp-gp-title');
  const count = state.el.querySelector('#rp-gp-count');

  title.textContent = template.title;
  count.textContent = _rangeLabel(d.time_range);
  body.innerHTML = '';

  if (d.report_id === 'telemetry-summary') {
    _renderTelemetryReport(body, d);
    return;
  }

  const summary = document.createElement('div');
  summary.className = `rp-report-summary rp-report-${template.accent}`;
  summary.innerHTML = `
    <div>
      <div class="rp-report-summary-title">${_esc(template.subtitle)}</div>
      <div class="rp-report-summary-copy">${_esc(_headlineForReport(d))}</div>
    </div>
    <div class="rp-report-summary-rate">
      <span>${((d.deny_rate || 0) * 100).toFixed(1)}%</span>
      <small>deny rate</small>
    </div>
  `;
  body.appendChild(summary);

  const findings = document.createElement('div');
  findings.className = 'rp-finding-grid';
  for (const item of d.findings.slice(0, 4)) {
    findings.appendChild(_findingCard(item));
  }
  body.appendChild(findings);

  if (d.report_id === 'governance-summary') {
    body.appendChild(_section('Decision mix', _barList(state, d.groups.decision?.groups || [], 'decision')));
    body.appendChild(_section('Most active actions', _barList(state, d.groups.tool?.groups || [], 'tool')));
    body.appendChild(_section('Activity categories', _compactTable(d.groups.category?.groups || [], ['Category', 'Records', 'DENY'])));
  } else if (d.report_id === 'denial-patterns') {
    body.appendChild(_section('Highest-risk actions', _compactTable(_groupsWithDenies(d.groups.tool), ['Action', 'Records', 'DENY', 'Deny rate'])));
    body.appendChild(_section('Denied categories', _barList(state, _groupsWithDenies(d.groups.category), 'category')));
    body.appendChild(_section('Operators with denials', _compactTable(_groupsWithDenies(d.groups.user), ['Operator', 'Records', 'DENY', 'Deny rate'])));
  } else if (d.report_id === 'operator-comparison') {
    body.appendChild(_section('Operator activity', _compactTable(d.groups.user?.groups || [], ['Operator', 'Records', 'DENY', 'Deny rate'])));
    body.appendChild(_section('Decision balance', _barList(state, d.groups.decision?.groups || [], 'decision')));
    body.appendChild(_section('Action distribution', _barList(state, d.groups.tool?.groups || [], 'tool')));
  } else if (d.report_id === 'audit-evidence') {
    body.appendChild(_section('Evidence checklist', _auditChecklist(d)));
    body.appendChild(_section('Decision summary', _compactTable(d.groups.decision?.groups || [], ['Decision/Event', 'Records', 'DENY'])));
    body.appendChild(_section('Evidence categories', _compactTable(d.groups.category?.groups || [], ['Category', 'Records', 'DENY'])));
  } else if (d.report_id === 'trouble-history') {
    body.appendChild(_section('Support request history', _troubleHistoryTable(d.trouble.reports)));
    body.appendChild(_section('Captured context', _troubleContextList(d.trouble.reports)));
  } else {
    body.appendChild(_section('High-denial signals', _compactTable(_highDenyGroups(d.groups.tool), ['Signal', 'Records', 'DENY', 'Deny rate'])));
    body.appendChild(_section('Low-frequency activity', _compactTable(_lowFrequencyGroups(d.groups.tool), ['Action', 'Records', 'DENY', 'Deny rate'])));
    body.appendChild(_section('Hourly concentration', _barList(state, d.groups.hour?.groups || [], 'hour')));
  }
}

function _buildFindings(reportId, grouped, totals) {
  const topTool = _topGroup(grouped.tool);
  const topDeniedTool = _topDenied(grouped.tool);
  const topUser = _topGroup(grouped.user);
  const topCategory = _topGroup(grouped.category);
  const denyPct = (totals.denyRate * 100).toFixed(1) + '%';

  if (reportId === 'denial-patterns') {
    return [
      { label: 'Denied records', value: _fmtNum(totals.deny), tone: 'amber', detail: `${denyPct} of selected records were denied.` },
      { label: 'Most denied action', value: topDeniedTool?.key || 'None', tone: topDeniedTool ? 'amber' : 'green', detail: topDeniedTool ? `${_fmtNum(topDeniedTool.deny_count || 0)} denied records.` : 'No denied action activity in range.' },
      { label: 'Primary category', value: topCategory?.key || 'N/A', tone: 'blue', detail: 'Largest evidence category in the range.' },
      { label: 'Operator signal', value: topUser?.key || 'N/A', tone: 'purple', detail: 'Most active identity in this report.' },
    ];
  }
  if (reportId === 'operator-comparison') {
    return [
      { label: 'Active identities', value: _fmtNum((grouped.user?.groups || []).length), tone: 'blue', detail: 'Distinct users or agents with records.' },
      { label: 'Most active', value: topUser?.key || 'N/A', tone: 'amber', detail: topUser ? `${_fmtNum(topUser.count || 0)} records.` : 'No operator data available.' },
      { label: 'Denied records', value: _fmtNum(totals.deny), tone: totals.deny ? 'amber' : 'green', detail: `${denyPct} deny rate.` },
      { label: 'Dominant action', value: topTool?.key || 'N/A', tone: 'blue', detail: 'Most used operation path.' },
    ];
  }
  if (reportId === 'audit-evidence') {
    return [
      { label: 'Records in scope', value: _fmtNum(totals.total), tone: 'purple', detail: 'Chain records covered by this evidence pack.' },
      { label: 'ALLOW', value: _fmtNum(totals.allow), tone: 'green', detail: 'Operations allowed by policy.' },
      { label: 'DENY', value: _fmtNum(totals.deny), tone: totals.deny ? 'amber' : 'green', detail: 'Operations blocked by policy.' },
      { label: 'Top category', value: topCategory?.key || 'N/A', tone: 'blue', detail: 'Largest record category.' },
    ];
  }
  if (reportId === 'unusual-activity') {
    const highDeny = _highDenyGroups(grouped.tool)[0];
    const lowFreq = _lowFrequencyGroups(grouped.tool)[0];
    return [
      { label: 'High-denial signal', value: highDeny?.key || 'None', tone: highDeny ? 'red' : 'green', detail: highDeny ? `${_groupDenyRate(highDeny)} deny rate.` : 'No high-denial group found.' },
      { label: 'Low-frequency action', value: lowFreq?.key || 'None', tone: lowFreq ? 'amber' : 'green', detail: lowFreq ? `${_fmtNum(lowFreq.count || 0)} record(s).` : 'No low-frequency group found.' },
      { label: 'Total records', value: _fmtNum(totals.total), tone: 'blue', detail: 'Records analyzed for unusual activity.' },
      { label: 'Denied records', value: _fmtNum(totals.deny), tone: totals.deny ? 'amber' : 'green', detail: `${denyPct} deny rate.` },
    ];
  }
  return [
    { label: 'Records in scope', value: _fmtNum(totals.total), tone: 'green', detail: 'Total records in the selected timeframe.' },
    { label: 'ALLOW', value: _fmtNum(totals.allow), tone: 'green', detail: 'Operations allowed by policy.' },
    { label: 'DENY', value: _fmtNum(totals.deny), tone: totals.deny ? 'amber' : 'green', detail: `${denyPct} deny rate.` },
    { label: 'Top action', value: topTool?.key || 'N/A', tone: 'blue', detail: topTool ? `${_fmtNum(topTool.count || 0)} records.` : 'No action data available.' },
  ];
}

function _findingCard(item) {
  const card = document.createElement('div');
  card.className = `rp-finding-card rp-finding-${item.tone || 'blue'}`;
  card.innerHTML = `
    <span class="rp-finding-label">${_esc(item.label)}</span>
    <span class="rp-finding-value">${_esc(item.value)}</span>
    <span class="rp-finding-detail">${_esc(item.detail)}</span>
  `;
  setTooltip(card, item.detail);
  return card;
}

function _section(title, content) {
  const section = document.createElement('div');
  section.className = 'rp-report-section';
  const h = document.createElement('div');
  h.className = 'rp-report-section-title';
  h.textContent = title;
  section.appendChild(h);
  section.appendChild(content);
  return section;
}

function _barList(state, groups, groupBy) {
  const wrap = document.createElement('div');
  wrap.className = 'rp-report-bars';
  const maxCount = Math.max(...groups.map(g => g.count || 0), 1);
  for (const group of groups.slice(0, 8)) {
    const pct = ((group.count || 0) / maxCount * 100).toFixed(1);
    const row = document.createElement('div');
    row.className = 'rp-bar-row';
    setTooltip(row, `${group.key || 'Group'}: ${_fmtNum(group.count || 0)} records. Click to view in Activity.`);
    row.innerHTML = `
      <span class="rp-bar-label">${_esc(group.key || '\u2014')}</span>
      <div class="rp-bar-track"><div class="rp-bar-fill${(group.deny_count || 0) > 0 ? ' rp-bar-amber' : ''}" style="width: ${pct}%"></div></div>
      <span class="rp-bar-count">${_fmtNum(group.count || 0)}</span>
    `;
    row.addEventListener('click', () => _navigateToActivity(state, groupBy, group.key));
    wrap.appendChild(row);
  }
  return wrap;
}

function _compactTable(groups, headers) {
  const table = document.createElement('table');
  table.className = 'rp-report-table';
  table.innerHTML = `<thead><tr>${headers.map(h => `<th>${_esc(h)}</th>`).join('')}</tr></thead>`;
  const tbody = document.createElement('tbody');
  for (const group of groups.slice(0, 8)) {
    const deny = group.deny_count || 0;
    const cols = headers.length > 3
      ? [group.key || 'N/A', _fmtNum(group.count || 0), _fmtNum(deny), _groupDenyRate(group)]
      : [group.key || 'N/A', _fmtNum(group.count || 0), _fmtNum(deny)];
    const tr = document.createElement('tr');
    tr.innerHTML = cols.map(c => `<td>${_esc(c)}</td>`).join('');
    tbody.appendChild(tr);
  }
  if (!groups.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="${headers.length}">No matching records.</td>`;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function _auditChecklist(d) {
  const list = document.createElement('div');
  list.className = 'rp-audit-checklist';
  const checks = [
    ['Records selected', _fmtNum(d.total_records), 'The records included in this generated evidence view.'],
    ['Policy decisions summarized', 'Yes', 'ALLOW and DENY counts are included.'],
    ['Evidence categories summarized', 'Yes', 'Record categories are grouped for review.'],
    ['Export format', 'JSON', 'Export produces structured data suitable for external review.'],
  ];
  for (const [label, value, detail] of checks) {
    const row = document.createElement('div');
    row.className = 'rp-audit-row';
    row.innerHTML = `<span>${_esc(label)}</span><strong>${_esc(value)}</strong><small>${_esc(detail)}</small>`;
    list.appendChild(row);
  }
  return list;
}

function _headlineForReport(d) {
  if (d.report_id === 'denial-patterns') return 'Policy denials are grouped by the actions, categories, and operators most useful for triage.';
  if (d.report_id === 'operator-comparison') return 'Activity is organized by user or agent identity so outliers are easy to spot.';
  if (d.report_id === 'audit-evidence') return 'This view packages the selected chain records into an auditor-ready summary.';
  if (d.report_id === 'unusual-activity') return 'This view highlights high-denial and low-frequency activity that deserves review.';
  if (d.report_id === 'telemetry-summary') return 'This report shows the same aggregate telemetry summary Atested can receive, with no raw event history.';
  if (d.report_id === 'trouble-history') return 'This view shows support reports submitted from the Trouble button and the page context captured with each report.';
  return 'This summary shows the selected period across decisions, actions, and activity categories.';
}

function _renderTelemetryReport(body, d) {
  body.appendChild(_telemetryFullCard('ATESTED TELEMETRY PURPOSE', TELEMETRY_PURPOSE, 'blue'));
  body.appendChild(_telemetryFullCard('PRIVACY MODEL', TELEMETRY_PRIVACY_TEXT, 'purple'));

  const categories = document.createElement('div');
  categories.className = 'rp-telemetry-section';
  categories.innerHTML = '<div class="rp-telemetry-section-title">CATEGORIES OF ATESTED TELEMETRY DATA</div>';
  const grid = document.createElement('div');
  grid.className = 'rp-telemetry-category-grid';
  for (const category of TELEMETRY_CATEGORIES) {
    grid.appendChild(_telemetryCategoryCard(category));
  }
  categories.appendChild(grid);
  body.appendChild(categories);

  body.appendChild(_section('Telemetry transmissions', _telemetryTransmissionsByCategory(d.telemetry, d.time_range)));
}

function _telemetryFullCard(title, copy, accent) {
  const card = document.createElement('div');
  card.className = `rp-telemetry-full rp-telemetry-${accent}`;
  card.innerHTML = `
    <div class="rp-telemetry-full-title">${_esc(title)}</div>
    <div class="rp-telemetry-full-copy">${_esc(copy)}</div>
  `;
  return card;
}

function _telemetryCategoryCard(category) {
  const card = document.createElement('div');
  card.className = `rp-telemetry-category rp-telemetry-${category.accent}`;
  card.innerHTML = `
    <div class="rp-telemetry-category-title">${_esc(category.title)}</div>
    <div class="rp-telemetry-category-copy">${_esc(category.copy)}</div>
  `;
  return card;
}

function _telemetryTransmissionsByCategory(telemetry, range) {
  const wrap = document.createElement('div');
  wrap.className = 'rp-telemetry-transmissions';
  const rows = _telemetryTransmissionRows(telemetry, range);
  if (!rows.length) {
    wrap.innerHTML = '<div class="rp-empty-note">No Atested telemetry transmissions in the selected range.</div>';
    return wrap;
  }

  for (const category of TELEMETRY_CATEGORIES) {
    const categoryRows = rows.filter(row => row.category === category.key);
    if (!categoryRows.length) continue;
    const block = document.createElement('div');
    block.className = 'rp-telemetry-category-block';
    block.innerHTML = `<div class="rp-telemetry-block-title">${_esc(category.title)}</div>`;
    block.appendChild(_simpleTable(['Period', 'Sent at', 'Artifact', 'What was sent'], categoryRows.map(row => [
      row.period,
      _formatShortDate(row.sent_at),
      _truncate(row.artifact_id, 22),
      row.summary,
    ])));
    wrap.appendChild(block);
  }
  return wrap;
}

function _telemetryTransmissionRows(telemetry, range) {
  const transmissions = telemetry?.transmissions || [];
  const startMs = range?.start ? new Date(range.start).getTime() : null;
  const endMs = range?.end ? new Date(range.end).getTime() : null;
  const rows = [];

  for (const tx of transmissions) {
    const sentMs = new Date(tx.timestamp_utc || tx.timestamp || '').getTime();
    if (Number.isFinite(sentMs)) {
      if (startMs && sentMs < startMs) continue;
      if (endMs && sentMs > endMs) continue;
    }
    const periods = tx.periods_sent?.length
      ? tx.periods_sent
      : (tx.categories?.periods?.length ? tx.categories.periods : []);
    if (!periods.length) {
      for (const category of TELEMETRY_CATEGORIES) {
        rows.push({
          category: category.key,
          period: _formatShortDate(tx.timestamp_utc || tx.timestamp || ''),
          sent_at: tx.timestamp_utc || tx.timestamp || '',
          artifact_id: tx.artifact_id || 'summary',
          summary: 'Legacy summary artifact; category detail was not recorded with this transmission.',
        });
      }
      continue;
    }
    for (const period of periods) {
      const cats = period.categories || {};
      for (const category of TELEMETRY_CATEGORIES) {
        rows.push({
          category: category.key,
          period: period.period || 'current',
          sent_at: tx.timestamp_utc || tx.timestamp || '',
          artifact_id: tx.artifact_id || 'summary',
          summary: _summarizeTelemetryCategory(category.key, cats[category.key]),
        });
      }
    }
  }
  return rows;
}

function _summarizeTelemetryCategory(key, data = {}) {
  if (key === 'ui_interactions') {
    const windows = _sumNested(data.window_opens);
    const reports = _sumNested(data.report_runs);
    const ranges = _sumNested(data.range_shortcuts);
    return `${_fmtNum(windows)} window opens, ${_fmtNum(reports)} report runs, ${_fmtNum(ranges)} range shortcuts`;
  }
  if (key === 'governance_usage_data') {
    return `${_fmtNum(data.total_operations || 0)} operations, ${_fmtNum(data.allow || 0)} allow, ${_fmtNum(data.deny || 0)} deny; actions: ${_topCounterSummary(data.action_categories)}`;
  }
  if (key === 'trouble_submissions') {
    return `${_fmtNum(data.submitted || 0)} trouble submissions; priorities: ${_topCounterSummary(data.priorities)}`;
  }
  if (key === 'system_health') {
    return `chain ${data.chain_status || 'unknown'}, integrity ${data.chain_file_status || 'unknown'}, policy ${data.policy_rules_status || 'unknown'}, size ${_fmtNum(data.chain_size_bytes || 0)} bytes`;
  }
  return 'Summary data';
}

function _topCounterSummary(counter) {
  const entries = Object.entries(counter || {}).sort((a, b) => (b[1] || 0) - (a[1] || 0)).slice(0, 3);
  if (!entries.length) return 'none';
  return entries.map(([k, v]) => `${k} ${_fmtNum(v)}`).join(', ');
}

function _simpleTable(headers, rows) {
  const table = document.createElement('table');
  table.className = 'rp-report-table';
  table.innerHTML = `<thead><tr>${headers.map(h => `<th>${_esc(h)}</th>`).join('')}</tr></thead>`;
  const tbody = document.createElement('tbody');
  for (const row of rows.slice(0, 12)) {
    const tr = document.createElement('tr');
    tr.innerHTML = row.map(c => `<td>${_esc(c)}</td>`).join('');
    tbody.appendChild(tr);
  }
  if (!rows.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="${headers.length}">No summary counters collected yet.</td>`;
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  return table;
}

function _troubleHistoryTable(reports) {
  const rows = (reports || []).map(report => [
    _formatShortDate(report.timestamp_utc || report.timestamp),
    _labelize(report.priority || 'normal'),
    report.context?.current_window || 'Main page',
    _truncate(report.description || '', 90),
    _truncate(report.artifact_hash || report.artifact_id || '', 24),
  ]);
  return _simpleTable(['Submitted', 'Priority', 'Window', 'Description', 'Artifact'], rows);
}

function _troubleContextList(reports) {
  const list = document.createElement('div');
  list.className = 'rp-audit-checklist';
  const latest = (reports || [])[0];
  if (!latest) {
    list.innerHTML = '<div class="rp-empty-note">No trouble report context has been captured yet.</div>';
    return list;
  }
  const context = latest.context || {};
  const checks = [
    ['Captured at', context.captured_at_utc || latest.timestamp_utc || 'N/A', 'When the UI context snapshot was created.'],
    ['Path', context.path || 'N/A', 'Browser path visible when the report was submitted.'],
    ['Window stack', (context.modal_stack || []).map(w => w.title).filter(Boolean).join(' > ') || context.current_window || 'Main page', 'Open window context attached to the report.'],
    ['License label', context.visible_state?.license || 'N/A', 'License state shown in the operator chrome at capture time.'],
  ];
  for (const [label, value, detail] of checks) {
    const row = document.createElement('div');
    row.className = 'rp-audit-row';
    row.innerHTML = `<span>${_esc(label)}</span><strong>${_esc(value)}</strong><small>${_esc(detail)}</small>`;
    list.appendChild(row);
  }
  return list;
}

function _topGroup(report) {
  return (report?.groups || [])[0];
}

function _topDenied(report) {
  return (report?.groups || []).filter(g => (g.deny_count || 0) > 0).sort((a, b) => (b.deny_count || 0) - (a.deny_count || 0))[0];
}

function _groupsWithDenies(report) {
  return (report?.groups || []).filter(g => (g.deny_count || 0) > 0).sort((a, b) => (b.deny_count || 0) - (a.deny_count || 0));
}

function _highDenyGroups(report) {
  return (report?.groups || []).filter(g => (g.deny_count || 0) > 0).sort((a, b) => (b.deny_count || 0) / Math.max(b.count || 1, 1) - (a.deny_count || 0) / Math.max(a.count || 1, 1));
}

function _lowFrequencyGroups(report) {
  return (report?.groups || []).filter(g => (g.count || 0) <= 2).sort((a, b) => (a.count || 0) - (b.count || 0));
}

function _groupDenyRate(group) {
  const rate = group.count > 0 ? (group.deny_count || 0) / group.count : 0;
  return (rate * 100).toFixed(1) + '%';
}

function _rangeLabel(range) {
  if (!range?.start && !range?.end) return 'All time';
  const start = range.start ? _formatShortDate(range.start) : 'Start';
  const end = range.end ? _formatShortDate(range.end) : 'Now';
  return `${start} to ${end}`;
}

function _formatShortDate(iso) {
  try {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()}/${String(d.getFullYear()).slice(2)}`;
  } catch {
    return iso || '';
  }
}

// ---------- Atomic navigation ----------

function _navigateToActivity(state, groupBy, groupKey) {
  // Build filter opts for Activity window
  const opts = {};
  if (state.startTime) opts.startTime = state.startTime;
  if (state.endTime) opts.endTime = state.endTime;

  if (groupBy === 'tool') {
    opts.toolFilter = groupKey;
  } else if (groupBy === 'category') {
    opts.eventTypeFilter = groupKey;
  } else if (groupBy === 'decision') {
    opts.decisionFilter = groupKey;
  } else if (groupBy === 'hour') {
    // Hour grouping: set time range to that specific hour
    // groupKey is like "14:00"
    const hourStr = groupKey.replace(':00', '');
    const hour = parseInt(hourStr, 10);
    if (!isNaN(hour)) {
      // Use the report's date context — find a date from start/end time or today
      const baseDate = state.startTime ? new Date(state.startTime) : new Date();
      const fromDate = new Date(baseDate);
      fromDate.setHours(hour, 0, 0, 0);
      const toDate = new Date(fromDate);
      toDate.setHours(hour + 1, 0, 0, 0);
      opts.startTime = fromDate.toISOString();
      opts.endTime = toDate.toISOString();
    }
  }
  // user grouping — no direct filter in Activity, just pass time range

  // Close Reports, open Activity with pre-set filters
  modalManager.closeAll();
  setTimeout(() => {
    import('./activity.js').then(mod => {
      mod.openActivityWindow(null, opts);
    });
  }, 0);
}

// ---------- JSON export ----------

function _exportJSON(state) {
  if (!state.data || state.rangeError) return;

  const exportData = {
    report_id: state.data.report_id,
    report_title: state.data.report_title,
    generated_at: state.data.generated_at,
    time_range: state.data.time_range,
    summary: {
      total_records: state.data.total_records,
      decision_summary: state.data.decision_summary,
      deny_rate: state.data.deny_rate,
    },
    findings: state.data.findings,
    telemetry: state.data.telemetry || undefined,
    trouble: state.data.trouble || undefined,
    groups: Object.fromEntries(Object.entries(state.data.groups || {}).map(([key, value]) => [
      key,
      value?.groups || [],
    ])),
  };

  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const dateStr = new Date().toISOString().slice(0, 10);
  a.download = `atested-${state.data.report_id}-${dateStr}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

// ---------- Utility ----------

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, subtitle, trigger, content });
  return modalManager.open({ title, subtitle, trigger, content });
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str == null ? '' : String(str);
  return el.innerHTML;
}

function _fmtNum(n) {
  return typeof n === 'number' ? n.toLocaleString() : String(n);
}

function _sumNested(obj) {
  if (!obj || typeof obj !== 'object') return 0;
  return Object.values(obj).reduce((sum, value) => sum + (Number(value) || 0), 0);
}

function _labelize(str) {
  return String(str || '').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function _truncate(str, len) {
  const text = str == null ? '' : String(str);
  return text.length > len ? text.slice(0, Math.max(0, len - 1)) + '\u2026' : text;
}

function _isoToLocal(iso) {
  if (!iso) return '';
  try {
    const d = new Date(iso);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const hh = String(d.getHours()).padStart(2, '0');
    const mi = String(d.getMinutes()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}T${hh}:${mi}`;
  } catch { return ''; }
}

// ---------- Styles ----------

const rpStyles = document.createElement('style');
rpStyles.textContent = `
  .rp-root { font-family: "Inter", system-ui, sans-serif; }

  /* ---- Report cards ---- */
  .rp-report-picker {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(145px, 1fr));
    gap: 10px;
    margin-bottom: 18px;
  }
  .rp-report-card {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: 5px;
    min-height: 104px;
    padding: 14px 12px 12px;
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    color: #e4e6eb;
    text-align: left;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s, transform 0.15s;
  }
  .rp-report-card:hover,
  .rp-report-active {
    background: #252a33;
    border-color: rgba(255,255,255,0.24);
    transform: translateY(-1px);
  }
  .rp-report-accent {
    position: absolute;
    left: 0;
    right: 0;
    top: 0;
    height: 6px;
  }
  .rp-report-title {
    margin-top: 6px;
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .rp-report-subtitle {
    font-size: 0.74rem;
    line-height: 1.35;
    color: #8b919a;
  }
  .rp-report-green .rp-report-accent { background: #3fb950; }
  .rp-report-amber .rp-report-accent { background: #d29922; }
  .rp-report-blue .rp-report-accent { background: #6699cc; }
  .rp-report-purple .rp-report-accent { background: #d2a8ff; }
  .rp-report-red .rp-report-accent { background: #f85149; }

  /* ---- Filter row ---- */
  .rp-filter-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 20px;
  }

  .rp-filter-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
  }
  .rp-fp-accent {
    height: 6px;
    background: #3fb950;
  }
  .rp-fp-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
    padding: 12px 20px 4px;
  }
  .rp-fp-body {
    padding: 8px 20px 16px;
  }
  .rp-selected-report {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 14px;
  }
  .rp-selected-title {
    color: #e4e6eb;
    font-size: 0.9rem;
    font-weight: 700;
  }
  .rp-selected-subtitle {
    color: #8b919a;
    font-size: 0.8rem;
    line-height: 1.35;
  }
  .rp-fp-fields {
    display: flex;
    gap: 12px;
    margin-bottom: 10px;
  }
  .rp-fp-label {
    display: flex;
    flex-direction: column;
    font-size: 0.72rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    gap: 4px;
    flex: 1;
  }
  .rp-input {
    background: #1a1d23;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 6px 10px;
  }
  .rp-input:focus { outline: 2px solid #6699cc; outline-offset: 1px; }

  /* Quick buttons */
  .rp-fp-quick {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .rp-quick-btn {
    background: rgba(255,255,255,0.04);
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    color: #8b919a;
    font-size: 0.72rem;
    padding: 4px 10px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .rp-quick-btn:hover {
    background: rgba(102,153,204,0.12);
    color: #6699cc;
    border-color: rgba(102,153,204,0.3);
  }
  .rp-quick-active {
    background: rgba(102,153,204,0.18);
    color: #e4e6eb;
    border-color: rgba(102,153,204,0.55);
    font-weight: 700;
  }

  /* Group by toggles */
  .rp-group-section { margin-bottom: 14px; }
  .rp-fp-mini-label {
    display: block;
    font-size: 0.68rem;
    color: #8b919a;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 6px;
  }
  .rp-group-toggles {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
  }
  .rp-gtoggle {
    background: rgba(255,255,255,0.04);
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    color: #8b919a;
    font-size: 0.78rem;
    padding: 5px 12px;
    cursor: pointer;
    transition: all 0.15s;
  }
  .rp-gtoggle:hover {
    background: rgba(102,153,204,0.08);
    color: #c4d0f0;
  }
  .rp-gtoggle-active {
    background: rgba(102,153,204,0.15);
    color: #6699cc;
    border-color: rgba(102,153,204,0.4);
    font-weight: 600;
  }

  /* Action buttons */
  .rp-fp-actions {
    display: flex;
    gap: 8px;
  }
  .rp-btn {
    border: none;
    border-radius: 2px;
    font-size: 0.82rem;
    padding: 7px 18px;
    cursor: pointer;
    font-weight: 500;
    transition: all 0.15s;
  }
  .rp-btn-primary {
    background: #6699cc;
    color: #fff;
  }
  .rp-btn-primary:hover { background: #5580aa; }
  .rp-btn-export {
    background: rgba(210,153,34,0.12);
    color: #d29922;
    border: 1px dashed rgba(210,153,34,0.3);
  }
  .rp-btn-export:hover {
    background: rgba(210,153,34,0.20);
  }

  /* ---- Stat cards ---- */
  .rp-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }
  .rp-stat-card {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    padding: 14px 16px;
    text-align: center;
  }
  .rp-stat-green { border-color: rgba(63,185,80,0.25); }
  .rp-stat-amber { border-color: rgba(210,153,34,0.25); }
  .rp-stat-label {
    display: block;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    margin-bottom: 4px;
  }
  .rp-stat-value {
    font-size: 1.4rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .rp-val-green { color: #3fb950; }
  .rp-val-amber { color: #d29922; }

  /* ---- Grouping pane ---- */
  .rp-group-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .rp-gp-accent {
    height: 6px;
    background: #3fb950;
  }
  .rp-gp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 20px 4px;
  }
  .rp-gp-header #rp-gp-title {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
  }
  .rp-gp-count {
    font-size: 0.72rem;
    color: #8b919a;
    font-weight: 500;
  }
  .rp-gp-body {
    padding: 8px 0;
  }

  /* ---- Formatted reports ---- */
  .rp-report-summary {
    display: grid;
    grid-template-columns: 1fr auto;
    gap: 16px;
    align-items: center;
    margin: 8px 20px 14px;
    padding: 16px;
    border: 1px dashed rgba(255,255,255,0.12);
    border-left: 6px solid #6699cc;
    border-radius: 2px;
    background: rgba(255,255,255,0.03);
  }
  .rp-report-summary.rp-report-green { border-left-color: #3fb950; }
  .rp-report-summary.rp-report-amber { border-left-color: #d29922; }
  .rp-report-summary.rp-report-blue { border-left-color: #6699cc; }
  .rp-report-summary.rp-report-purple { border-left-color: #d2a8ff; }
  .rp-report-summary.rp-report-red { border-left-color: #f85149; }
  .rp-report-summary-title {
    color: #e4e6eb;
    font-size: 0.94rem;
    font-weight: 700;
    margin-bottom: 4px;
  }
  .rp-report-summary-copy {
    color: #8b919a;
    font-size: 0.82rem;
    line-height: 1.45;
  }
  .rp-report-summary-rate {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    font-family: "JetBrains Mono", monospace;
  }
  .rp-report-summary-rate span {
    color: #e4e6eb;
    font-size: 1.6rem;
    font-weight: 700;
  }
  .rp-report-summary-rate small {
    color: #8b919a;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .rp-telemetry-full {
    margin: 8px 20px 14px;
    padding: 18px;
    background: rgba(255,255,255,0.025);
    border: 1px dashed rgba(255,255,255,0.14);
    border-left: 6px solid #6699cc;
    border-radius: 2px;
  }
  .rp-telemetry-full.rp-telemetry-purple { border-left-color: #d2a8ff; }
  .rp-telemetry-full-title,
  .rp-telemetry-section-title,
  .rp-telemetry-block-title {
    color: #e4e6eb;
    font-size: 0.74rem;
    font-weight: 800;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .rp-telemetry-full-copy {
    color: #c7cdd6;
    font-size: 0.86rem;
    line-height: 1.55;
  }
  .rp-telemetry-section {
    margin: 4px 20px 16px;
  }
  .rp-telemetry-category-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
  }
  .rp-telemetry-category {
    background: rgba(255,255,255,0.025);
    border: 1px dashed rgba(255,255,255,0.12);
    border-top: 4px solid #6699cc;
    border-radius: 2px;
    padding: 13px;
  }
  .rp-telemetry-category.rp-telemetry-green { border-top-color: #3fb950; }
  .rp-telemetry-category.rp-telemetry-amber { border-top-color: #d29922; }
  .rp-telemetry-category.rp-telemetry-purple { border-top-color: #d2a8ff; }
  .rp-telemetry-category-title {
    color: #e4e6eb;
    font-size: 0.82rem;
    font-weight: 700;
    margin-bottom: 6px;
  }
  .rp-telemetry-category-copy {
    color: #8b919a;
    font-size: 0.74rem;
    line-height: 1.4;
  }
  .rp-telemetry-transmissions {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .rp-telemetry-category-block {
    border: 1px dashed rgba(255,255,255,0.1);
    background: rgba(255,255,255,0.018);
    padding: 12px;
  }
  .rp-finding-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 0 20px 16px;
  }
  .rp-finding-card {
    border: 1px dashed rgba(255,255,255,0.12);
    border-top: 4px solid #6699cc;
    border-radius: 2px;
    padding: 12px;
    background: rgba(255,255,255,0.025);
  }
  .rp-finding-green { border-top-color: #3fb950; }
  .rp-finding-amber { border-top-color: #d29922; }
  .rp-finding-blue { border-top-color: #6699cc; }
  .rp-finding-purple { border-top-color: #d2a8ff; }
  .rp-finding-red { border-top-color: #f85149; }
  .rp-finding-label {
    display: block;
    color: #8b919a;
    font-size: 0.64rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin-bottom: 5px;
  }
  .rp-finding-value {
    display: block;
    color: #e4e6eb;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.94rem;
    font-weight: 700;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rp-finding-detail {
    display: block;
    color: #8b919a;
    font-size: 0.72rem;
    line-height: 1.35;
    margin-top: 5px;
  }
  .rp-report-section {
    margin: 0 20px 16px;
    border: 1px dashed rgba(255,255,255,0.10);
    border-radius: 2px;
    overflow: hidden;
  }
  .rp-report-section-title {
    padding: 10px 12px;
    color: #6699cc;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    border-bottom: 1px dashed rgba(255,255,255,0.08);
  }
  .rp-report-bars {
    padding: 6px 0;
  }
  .rp-report-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .rp-report-table th {
    color: #8b919a;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    text-align: left;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }
  .rp-report-table td {
    color: #e4e6eb;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .rp-report-table td:not(:first-child) {
    font-family: "JetBrains Mono", monospace;
    color: #8b919a;
  }
  .rp-audit-checklist {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    padding: 12px;
  }
  .rp-audit-row {
    display: grid;
    gap: 3px;
    padding: 10px;
    background: rgba(255,255,255,0.03);
    border-left: 4px solid #d2a8ff;
  }
  .rp-audit-row span {
    color: #8b919a;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .rp-audit-row strong {
    color: #e4e6eb;
    font-family: "JetBrains Mono", monospace;
  }
  .rp-audit-row small {
    color: #8b919a;
    font-size: 0.72rem;
    line-height: 1.35;
  }

  /* ---- Bar rows ---- */
  .rp-bar-row {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 7px 20px;
    cursor: pointer;
    transition: background 0.12s;
  }
  .rp-bar-row:hover {
    background: rgba(102,153,204,0.06);
  }
  .rp-bar-label {
    flex: 0 0 140px;
    font-size: 0.82rem;
    color: #e4e6eb;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: "JetBrains Mono", monospace;
  }
  .rp-bar-track {
    flex: 1;
    height: 18px;
    background: rgba(255,255,255,0.04);
    border-radius: 2px;
    overflow: hidden;
  }
  .rp-bar-fill {
    height: 100%;
    background: #6699cc;
    border-radius: 2px;
    transition: width 0.3s;
    min-width: 2px;
  }
  .rp-bar-fill.rp-bar-amber {
    background: #d29922;
  }
  .rp-bar-count {
    flex: 0 0 50px;
    text-align: right;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.82rem;
    color: #8b919a;
  }

  /* ---- States ---- */
  .rp-loading {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
  }
  .rp-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 30px 0;
  }
  .rp-error {
    color: #d29922;
    padding: 12px 16px;
    border-radius: 2px;
    font-size: 0.82rem;
    margin: 0 20px;
  }

  /* ---- Responsive ---- */
  @media (max-width: 600px) {
    .rp-report-picker { grid-template-columns: 1fr; }
    .rp-filter-row { grid-template-columns: 1fr; }
    .rp-stats { grid-template-columns: repeat(2, 1fr); }
    .rp-finding-grid { grid-template-columns: 1fr; }
    .rp-telemetry-category-grid { grid-template-columns: 1fr; }
    .rp-audit-checklist { grid-template-columns: 1fr; }
    .rp-bar-label { flex: 0 0 80px; font-size: 0.72rem; }
    .rp-fp-fields { flex-direction: column; }
  }
  @media (min-width: 601px) and (max-width: 900px) {
    .rp-report-picker { grid-template-columns: repeat(2, 1fr); }
    .rp-finding-grid { grid-template-columns: repeat(2, 1fr); }
    .rp-telemetry-category-grid { grid-template-columns: repeat(2, 1fr); }
  }
`;
document.head.appendChild(rpStyles);
