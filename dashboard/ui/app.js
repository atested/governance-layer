// Atested Dashboard — live API-backed UI

const API = "";  // relative to current origin
const pageSize = 20;

// ---------------------------------------------------------------------------
// Tooltip helper
// ---------------------------------------------------------------------------

function tip(label, tooltipText) {
  return `<span class="has-tooltip">${escapeHtml(label)}<span class="tooltip-text">${escapeHtml(tooltipText)}</span></span>`;
}

function tipHtml(labelHtml, tooltipText) {
  return `<span class="has-tooltip">${labelHtml}<span class="tooltip-text">${escapeHtml(tooltipText)}</span></span>`;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function api(endpoint, params = {}) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") qs.set(k, String(v));
  }
  const url = `${API}/api/${endpoint}${qs.toString() ? "?" + qs : ""}`;
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`API ${resp.status}: ${endpoint}`);
  return resp.json();
}

// Cache to avoid redundant fetches within a render cycle
let _cache = {};
let _cacheTs = 0;
function clearCache() { _cache = {}; _cacheTs = Date.now(); }

async function cached(key, fn) {
  if (Date.now() - _cacheTs > 10000) clearCache();
  if (!(key in _cache)) _cache[key] = fn();
  return _cache[key];
}

// ---------------------------------------------------------------------------
// Routing
// ---------------------------------------------------------------------------

function routeFromHash() {
  const raw = window.location.hash.slice(1) || "/overview";
  const [pathPart, queryPart] = raw.split("?");
  const params = new URLSearchParams(queryPart || "");
  return { path: pathPart || "/overview", params };
}

function navHref(path, nextParams = {}) {
  const route = routeFromHash();
  const params = new URLSearchParams(route.params.toString());
  for (const [key, value] of Object.entries(nextParams)) {
    if (value === null || value === undefined || value === "") {
      params.delete(key);
    } else {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  return `#${path}${query ? "?" + query : ""}`;
}

function getContext() {
  const { path, params } = routeFromHash();
  return {
    path,
    params,
    page: Number(params.get("page") || "1"),
    recordId: params.get("record_id") || "",
    // Audit filters
    startTime: params.get("start_time") || "",
    endTime: params.get("end_time") || "",
    user: params.get("user") || "",
    tool: params.get("tool") || "",
    decision: params.get("decision") || "",
    category: params.get("category") || "",
    groupBy: params.get("group_by") || "tool",
  };
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatTime(iso) {
  if (!iso) return "\u2014";
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
  });
}

function truncate(s, n = 24) {
  if (!s) return "\u2014";
  return s.length > n ? s.slice(0, n) + "\u2026" : s;
}

function decisionTag(decision) {
  if (decision === "ALLOW") return '<span class="det-tag">ALLOW</span>';
  if (decision === "DENY") return '<span class="judgment-tag">DENY</span>';
  return `<span class="step-tag determined">${decision || "\u2014"}</span>`;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

// Human-readable category names
function categoryLabel(cat) {
  const map = {
    "action_decision": "Governed Action",
    "verification_transition": "Verification Change",
    "opaque_approval": "Artifact Approval",
    "opaque_revocation": "Artifact Revocation",
    "opaque_invocation_decision": "Invocation Decision",
    "ungoverned_observation": "Ungoverned Observation",
    "usage_attestation": "Usage Attestation",
  };
  return map[cat] || cat || "\u2014";
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

function globalNav(currentPath) {
  const tabs = [
    { path: "/overview", label: "Overview" },
    { path: "/activity", label: "Activity" },
    { path: "/approvals", label: "Approvals" },
    { path: "/audit", label: "Audit" },
    { path: "/report", label: "Reports" },
    { path: "/health", label: "Health" },
  ];
  return `
    <nav class="nav">
      ${tabs.map(t => `
        <a class="${currentPath === t.path ? "active" : ""}"
           href="${navHref(t.path, { page: null, record_id: null })}">${t.label}</a>
      `).join("")}
    </nav>
  `;
}

// ---------------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------------

async function renderOverview() {
  const [status, approvals, activity, users] = await Promise.all([
    cached("status", () => api("status")),
    cached("approvals", () => api("approvals")),
    cached("activity", () => api("activity", { limit: 8 })),
    cached("users", () => api("users")),
  ]);

  const integ = status.chain_integrity === "ok"
    ? '<span class="status-ok">OK</span>'
    : '<span class="status-warn">BROKEN</span>';

  const transparencyVal = status.transparency_metric && status.transparency_metric.observation_data
    ? Math.round(status.transparency_metric.transparency_pct * 100) + "%"
    : '<span class="muted" style="font-size:0.75rem">No observation data</span>';

  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Governance Status</span>
        <h2>System Overview</h2>
        <p class="explainer">
          This dashboard provides real-time visibility into your governance chain \u2014
          the tamper-evident log of every governed operation, approval, and verification event.
          Each metric below reflects the current state of the chain and connected systems.
        </p>
      </div>
      <div class="status-grid">
        <div class="status-card">
          <span class="eyebrow">${tip("Chain Events", "Total number of records in the governance chain, including governed actions, approvals, verifications, and observations.")}</span>
          <span class="status-value">${status.chain_event_count}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Chain Integrity", "Whether the hash-linked chain is structurally valid. OK means every record's hash links correctly to its predecessor.")}</span>
          <span class="status-value">${integ}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Active Approvals", "Number of artifact approvals currently in effect. Approvals authorize specific artifacts for use within governed families.")}</span>
          <span class="status-value">${status.active_approvals_count}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Surfaces with Drift", "Proof surfaces whose current state has diverged from their last certified configuration. Drift may indicate unauthorized changes.")}</span>
          <span class="status-value ${status.surfaces_in_drift.length ? "status-warn" : "status-ok"}">${status.surfaces_in_drift.length}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Unique Users", "Distinct user identities that have generated governed actions or events in the chain.")}</span>
          <span class="status-value">${users.unique_users}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Governed Actions", "Actions that were evaluated by the governance policy engine and recorded with a full decision trail.")}</span>
          <span class="status-value">${status.opacity_posture.transparent_count}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Opaque Invocations", "Actions that were invoked through opaque (non-transparent) resolution paths, such as operator intervention or approved lookups.")}</span>
          <span class="status-value">${status.opacity_posture.opaque_count}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Transparency", "Percentage of total observed operations that flowed through governance. Higher is better. Requires observation hooks to be configured.")}</span>
          <span class="status-value">${transparencyVal}</span>
        </div>
      </div>

      ${status.transparency_metric ? `
        <div class="card">
          <h3>${tip("Transparency Metric", "Measures how much of your AI tool usage is captured by the governance chain. transparency% = governed / (governed + ungoverned).")}</h3>
          <p class="explainer">Ratio of governed operations to total observed operations (governed + ungoverned). Configure observation hooks to start collecting data.</p>
          <div class="status-grid">
            <div class="status-card">
              <span class="eyebrow">${tip("Governed Ops", "Operations that passed through governance policy evaluation and were recorded in the chain.")}</span>
              <span class="status-value">${status.transparency_metric.governed_operations}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Ungoverned Obs.", "Operations reported by observation hooks that bypassed governance. These were detected but not policy-evaluated.")}</span>
              <span class="status-value">${status.transparency_metric.ungoverned_observations}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Total Observed", "Sum of governed operations and ungoverned observations. The denominator for the transparency percentage.")}</span>
              <span class="status-value">${status.transparency_metric.total_observed}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Hook Data", "Whether any ungoverned operation observations have been received. No means observation hooks are not yet configured.")}</span>
              <span class="status-value">${status.transparency_metric.observation_data
                ? '<span class="status-ok">Yes</span>'
                : '<span class="muted">No</span>'}</span>
            </div>
          </div>
        </div>
      ` : ""}

      ${status.verification_state && Object.keys(status.verification_state).length ? `
        <div class="card">
          <h3>${tip("Verification State", "Current verification status of registered proof surfaces. Verified means the surface matches its certified configuration.")}</h3>
          <table class="audit-results-table">
            <thead><tr>
              <th>${tip("Surface", "The proof surface identifier (e.g. a governed category or deployment context).")}</th>
              <th>${tip("State", "Current verification state: verified, unverified, or drift_detected.")}</th>
            </tr></thead>
            <tbody>
              ${Object.entries(status.verification_state).map(([f, s]) => `
                <tr><td>${escapeHtml(f)}</td><td>${s === "drift_detected" ? '<span class="status-warn">drift detected</span>' : escapeHtml(s)}</td></tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      ` : ""}

      ${users.users.length ? `
        <div class="card">
          <h3>${tip("Users", "All user identities that appear in the governance chain, with their action counts.")}</h3>
          <table class="audit-results-table">
            <thead><tr>
              <th>${tip("Identity", "The user identity string recorded with each governed action.")}</th>
              <th>${tip("Actions", "Total number of governed actions and events attributed to this user.")}</th>
            </tr></thead>
            <tbody>
              ${users.users.map(u => `
                <tr><td>${escapeHtml(u.identity)}</td><td>${u.count}</td></tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      ` : ""}

      <div class="card">
        <h3>Recent Activity</h3>
        ${activity.entries.length ? activity.entries.map(e => {
          const rid = e.evidence?.request_id || e.evidence?.event_id || e.evidence?.record_hash || "";
          const href = rid ? navHref("/record", { record_id: rid }) : "";
          return `
            <div class="activity-entry${href ? " clickable" : ""}" ${href ? `onclick="window.location.hash='${href}'"` : ""}>
              <strong>${escapeHtml(e.summary)}</strong>
              <span class="muted"> \u00b7 ${categoryLabel(e.event_category)} \u00b7 ${formatTime(e.timestamp_utc)}</span>
            </div>
          `;
        }).join("") : '<p class="muted">No activity recorded yet.</p>'}
      </div>
    </section>
  `;
}

async function renderActivity() {
  const ctx = getContext();
  const offset = (ctx.page - 1) * pageSize;
  const data = await api("activity", { limit: pageSize, offset });
  const totalPages = Math.ceil(data.total_matching / pageSize) || 1;

  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Governance Activity</span>
        <h2>All Events (${data.total_matching} total)</h2>
      </div>
      <div class="card">
        ${data.entries.length ? `
          <table class="audit-results-table">
            <thead>
              <tr>
                <th>${tip("#", "Sequence position in the governance chain.")}</th>
                <th>${tip("Time", "UTC timestamp when the event was recorded.")}</th>
                <th>${tip("Category", "The type of governance event: governed action, approval, verification change, etc.")}</th>
                <th>${tip("Summary", "Human-readable description of what happened.")}</th>
                <th>${tip("Category", "The governed category this event belongs to, if applicable.")}</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              ${data.entries.map(e => {
                const rid = e.evidence?.request_id || e.evidence?.event_id || e.evidence?.record_hash || "";
                return `
                  <tr class="${rid ? "clickable-row" : ""}" ${rid ? `onclick="window.location.hash='${navHref("/record", { record_id: rid })}'"` : ""}>
                    <td>${e.sequence_position}</td>
                    <td>${formatTime(e.timestamp_utc)}</td>
                    <td>${categoryLabel(e.event_category)}</td>
                    <td>${escapeHtml(e.summary)}</td>
                    <td>${escapeHtml(e.governed_family || "\u2014")}</td>
                    <td>${rid ? `<a href="${navHref("/record", { record_id: rid })}">View</a>` : "\u2014"}</td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
          <div class="toolbar" style="margin-top:14px">
            ${ctx.page > 1 ? `<a class="pill" href="${navHref("/activity", { page: ctx.page - 1 })}">Previous</a>` : '<span class="pill">Previous</span>'}
            <span class="muted">Page ${ctx.page} of ${totalPages}</span>
            ${ctx.page < totalPages ? `<a class="pill" href="${navHref("/activity", { page: ctx.page + 1 })}">Next</a>` : '<span class="pill">Next</span>'}
          </div>
        ` : '<p class="muted">No activity recorded yet.</p>'}
      </div>
    </section>
  `;
}

async function renderApprovals() {
  const data = await cached("approvals", () => api("approvals"));
  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Approvals</span>
        <h2>Active Approvals (${data.total_count})</h2>
        <p class="explainer">Artifact approvals authorize specific artifacts for use within a governed category. Approvals can be revoked at any time.</p>
      </div>
      ${data.active_approvals.length ? `
        <div class="approval-grid">
          ${data.active_approvals.map(a => `
            <div class="approval-card">
              <span class="eyebrow">Active approval</span>
              <h3>${truncate(a.artifact_identity, 40)}</h3>
              <ul class="kv">
                <li><span>Category</span><strong>${escapeHtml(a.governed_family || "\u2014")}</strong></li>
                <li><span>Operator</span><strong>${escapeHtml(a.approving_operator)}</strong></li>
                <li><span>Context</span><strong>${escapeHtml(a.deployment_context || "\u2014")}</strong></li>
                <li><span>Policy</span><strong>${escapeHtml(a.policy_version || "\u2014")}</strong></li>
                <li><span>Approved</span><strong>${formatTime(a.timestamp_utc)}</strong></li>
              </ul>
            </div>
          `).join("")}
        </div>
      ` : '<div class="card"><p class="muted">No active approvals.</p></div>'}
    </section>
  `;
}

async function renderAudit() {
  const ctx = getContext();
  let resultsHtml = "";
  let data = null;

  const hasFilters = ctx.startTime || ctx.endTime || ctx.user || ctx.tool || ctx.decision || ctx.category;
  if (hasFilters) {
    const offset = (ctx.page - 1) * pageSize;
    data = await api("audit/query", {
      start_time: ctx.startTime || null,
      end_time: ctx.endTime || null,
      user_identity: ctx.user || null,
      tool_name: ctx.tool || null,
      policy_decision: ctx.decision || null,
      event_category: ctx.category || null,
      limit: pageSize,
      offset,
    });
    const totalPages = Math.ceil(data.total_matching / pageSize) || 1;

    resultsHtml = `
      <div class="card">
        <h3>Results (${data.total_matching} matching)</h3>
        ${data.entries.length ? `
          <table class="audit-results-table">
            <thead>
              <tr>
                <th>${tip("#", "Sequence position in the chain.")}</th>
                <th>${tip("Time", "When the event was recorded.")}</th>
                <th>${tip("Category", "Type of governance event.")}</th>
                <th>${tip("Summary", "What happened.")}</th>
                <th>${tip("User", "Identity of the user who triggered the action.")}</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              ${data.entries.map(e => {
                const rid = e.evidence?.request_id || e.evidence?.event_id || e.evidence?.record_hash || "";
                return `
                  <tr class="${rid ? "clickable-row" : ""}" ${rid ? `onclick="window.location.hash='${navHref("/record", { record_id: rid })}'"` : ""}>
                    <td>${e.sequence_position}</td>
                    <td>${formatTime(e.timestamp_utc)}</td>
                    <td>${categoryLabel(e.event_category)}</td>
                    <td>${escapeHtml(e.summary)}</td>
                    <td>${escapeHtml(e.user_identity || "\u2014")}</td>
                    <td>${rid ? `<a href="${navHref("/record", { record_id: rid })}">View</a>` : "\u2014"}</td>
                  </tr>
                `;
              }).join("")}
            </tbody>
          </table>
          <div class="toolbar" style="margin-top:14px">
            ${ctx.page > 1 ? `<a class="pill" href="${navHref("/audit", { page: ctx.page - 1 })}">Previous</a>` : '<span class="pill">Previous</span>'}
            <span class="muted">Page ${ctx.page} of ${totalPages}</span>
            ${ctx.page < totalPages ? `<a class="pill" href="${navHref("/audit", { page: ctx.page + 1 })}">Next</a>` : '<span class="pill">Next</span>'}
          </div>
          <div style="margin-top:14px">
            <button class="export-link" onclick="exportAuditJson()">Export JSON</button>
          </div>
        ` : '<p class="muted">No matching records.</p>'}
      </div>
    `;
  }

  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Audit</span>
        <h2>Query Governance Records</h2>
        <p class="explainer">Search the governance chain by time range, user, tool, decision outcome, or event category. Each result links to the full record detail.</p>
        <form class="audit-form" id="audit-form" onsubmit="return handleAuditSubmit(event)">
          <label>${tip("Start time", "Filter to events on or after this time.")}<input type="datetime-local" name="start_time" value="${ctx.startTime ? ctx.startTime.replace("Z","").replace("+00:00","") : ""}"></label>
          <label>${tip("End time", "Filter to events on or before this time.")}<input type="datetime-local" name="end_time" value="${ctx.endTime ? ctx.endTime.replace("Z","").replace("+00:00","") : ""}"></label>
          <label>${tip("User identity", "Filter by the user who triggered the action.")}<input type="text" name="user" value="${escapeHtml(ctx.user)}" placeholder="e.g. gkeeter"></label>
          <label>${tip("Tool name", "Filter by the governed tool that was invoked.")}<input type="text" name="tool" value="${escapeHtml(ctx.tool)}" placeholder="e.g. FS_WRITE"></label>
          <label>${tip("Decision", "Filter by policy outcome: ALLOW or DENY.")}
            <select name="decision">
              <option value="">All</option>
              <option value="ALLOW" ${ctx.decision === "ALLOW" ? "selected" : ""}>ALLOW</option>
              <option value="DENY" ${ctx.decision === "DENY" ? "selected" : ""}>DENY</option>
            </select>
          </label>
          <label>${tip("Category", "Filter by event type.")}
            <select name="category">
              <option value="">All</option>
              <option value="action_decision" ${ctx.category === "action_decision" ? "selected" : ""}>Governed Action</option>
              <option value="verification_transition" ${ctx.category === "verification_transition" ? "selected" : ""}>Verification Change</option>
              <option value="opaque_approval" ${ctx.category === "opaque_approval" ? "selected" : ""}>Artifact Approval</option>
              <option value="opaque_revocation" ${ctx.category === "opaque_revocation" ? "selected" : ""}>Artifact Revocation</option>
              <option value="opaque_invocation_decision" ${ctx.category === "opaque_invocation_decision" ? "selected" : ""}>Invocation Decision</option>
              <option value="ungoverned_observation" ${ctx.category === "ungoverned_observation" ? "selected" : ""}>Ungoverned Observation</option>
            </select>
          </label>
          <button type="submit">Search</button>
        </form>
      </div>
      ${resultsHtml}
    </section>
  `;
}

async function renderRecordDetail() {
  const ctx = getContext();
  if (!ctx.recordId) {
    return '<div class="card"><p class="muted">No record_id specified.</p></div>';
  }
  const data = await api("audit/record", { record_id: ctx.recordId });
  if (!data.found) {
    return `<div class="card"><p class="muted">Record not found: ${escapeHtml(ctx.recordId)}</p></div>`;
  }
  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Record Detail</span>
        <h2>${escapeHtml(truncate(ctx.recordId, 48))}</h2>
        <a class="pill" href="${navHref("/audit")}">Back to Audit</a>
      </div>
      <div class="card">
        <h3>Chain Record</h3>
        <pre>${escapeHtml(JSON.stringify(data.chain_record, null, 2))}</pre>
      </div>
      ${data.sidecar_record ? `
        <div class="card">
          <h3>Sidecar Record</h3>
          <pre>${escapeHtml(JSON.stringify(data.sidecar_record, null, 2))}</pre>
        </div>
      ` : ""}
    </section>
  `;
}

async function renderReport() {
  const ctx = getContext();
  const data = await api("audit/report", {
    start_time: ctx.startTime || null,
    end_time: ctx.endTime || null,
    group_by: ctx.groupBy,
  });
  const maxCount = data.groups.length ? Math.max(...data.groups.map(g => g.count)) : 1;

  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Reports</span>
        <h2>Audit Summary</h2>
        <p class="explainer">Aggregate view of governance activity. Group by tool, user, decision, or event category to identify patterns.</p>
        <form class="audit-form" id="report-form" onsubmit="return handleReportSubmit(event)">
          <label>${tip("Start time", "Beginning of the reporting window.")}<input type="datetime-local" name="start_time" value="${ctx.startTime ? ctx.startTime.replace("Z","").replace("+00:00","") : ""}"></label>
          <label>${tip("End time", "End of the reporting window.")}<input type="datetime-local" name="end_time" value="${ctx.endTime ? ctx.endTime.replace("Z","").replace("+00:00","") : ""}"></label>
          <label>${tip("Group by", "How to aggregate the results.")}
            <select name="group_by">
              <option value="tool" ${ctx.groupBy === "tool" ? "selected" : ""}>Tool</option>
              <option value="user" ${ctx.groupBy === "user" ? "selected" : ""}>User</option>
              <option value="decision" ${ctx.groupBy === "decision" ? "selected" : ""}>Decision</option>
              <option value="category" ${ctx.groupBy === "category" ? "selected" : ""}>Category</option>
            </select>
          </label>
          <button type="submit">Generate</button>
        </form>
      </div>

      <div class="card">
        <h3>${tip("Decision Summary", "Breakdown of policy decisions across all records in the selected time range.")} (${data.total_records} records)</h3>
        <div class="status-grid">
          ${Object.entries(data.decision_summary).map(([k, v]) => `
            <div class="status-card">
              <span class="eyebrow">${escapeHtml(k)}</span>
              <span class="status-value">${v}</span>
            </div>
          `).join("") || '<p class="muted">No decisions in range.</p>'}
        </div>
      </div>

      <div class="card">
        <h3>Grouped by ${escapeHtml(ctx.groupBy)}</h3>
        ${data.groups.length ? data.groups.map(g => `
          <div class="report-bar">
            <span class="report-bar-label">${escapeHtml(g.key)}</span>
            <div class="report-bar-fill" style="width:${Math.max(Math.round(g.count / maxCount * 100), 2)}%"></div>
            <span class="report-bar-count">${g.count}</span>
          </div>
        `).join("") : '<p class="muted">No data in range.</p>'}
      </div>
    </section>
  `;
}

// ---------------------------------------------------------------------------
// System Health page
// ---------------------------------------------------------------------------

function healthStatusBadge(status) {
  const map = {
    "healthy": '<span class="status-ok">Healthy</span>',
    "healthy_auto_repaired": '<span class="status-ok">Healthy (auto-repaired)</span>',
    "attention": '<span class="status-warn">Attention</span>',
    "critical": '<span class="status-danger">Critical</span>',
  };
  return map[status] || `<span class="muted">${escapeHtml(status)}</span>`;
}

function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return (bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0) + " " + units[i];
}

async function renderHealth() {
  const data = await api("health");

  const alertsHtml = data.alerts && data.alerts.length ? `
    <div class="card">
      <h3>Active Alerts</h3>
      ${data.alerts.map(a => `
        <div class="health-alert health-alert--${a.severity}">
          <div class="health-alert-header">
            <strong>${escapeHtml(a.source)}</strong>
            <span class="health-alert-severity">${a.severity === "critical" ? "CRITICAL" : a.severity === "attention" ? "ATTENTION" : "INFO"}</span>
          </div>
          <p>${escapeHtml(a.message)}</p>
          ${a.guidance ? `<p class="muted" style="font-size:0.85rem">${escapeHtml(a.guidance)}</p>` : ""}
          <button class="export-link" style="margin-top:8px" onclick="acknowledgeAlert('${escapeHtml(a.source)}', '${escapeHtml(a.message)}')">Acknowledge</button>
        </div>
      `).join("")}
    </div>
  ` : "";

  const chain = data.chain || {};
  const chainStatusHtml = chain.break_info ? `
    <div style="margin-top:8px">
      <span class="eyebrow">Break Details</span>
      <ul class="kv" style="margin-top:4px">
        <li><span>Break at</span><strong>Line ${chain.break_info.break_at_line}</strong></li>
        <li><span>Reason</span><strong>${escapeHtml(chain.break_info.reason)}</strong></li>
        ${chain.break_info.classification ? `
          <li><span>Classification</span><strong>${escapeHtml(chain.break_info.classification.classification)}</strong></li>
          ${chain.break_info.classification.pattern ? `<li><span>Pattern</span><strong>${escapeHtml(chain.break_info.classification.pattern)}</strong></li>` : ""}
          <li><span>Description</span><strong>${escapeHtml(chain.break_info.classification.description)}</strong></li>
        ` : ""}
      </ul>
    </div>
  ` : "";

  const repairHtml = chain.repair_info && chain.repair_info.repaired ? `
    <div style="margin-top:8px">
      <span class="eyebrow">Auto-Repair Applied</span>
      <ul class="kv" style="margin-top:4px">
        <li><span>Strategy</span><strong>${escapeHtml(chain.repair_info.strategy)}</strong></li>
        <li><span>Event ID</span><strong>${truncate(chain.repair_info.stability_event_id, 20)}</strong></li>
      </ul>
    </div>
  ` : "";

  const deny = data.deny_rate || {};
  const storage = data.storage || {};
  const obs = data.observations || {};
  const users = data.users || {};
  const license = data.license || {};
  const retention = data.retention || {};

  const stabilityEvents = data.recent_stability_events || [];

  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">System Health</span>
        <h2>Atested Infrastructure Status</h2>
        <p class="explainer">
          Monitors the health of your governance infrastructure: chain integrity, policy trends,
          storage, observation coverage, and license status. Issues are classified and, where safe,
          auto-repaired.
        </p>
        <div class="status-grid" style="margin-top:12px">
          <div class="status-card">
            <span class="eyebrow">${tip("Overall Status", "Aggregate health derived from all monitored signals. Healthy means everything is normal. Attention means something needs review. Critical requires immediate action.")}</span>
            <span class="status-value">${healthStatusBadge(data.overall_status)}</span>
          </div>
        </div>
      </div>

      ${alertsHtml}

      <div class="card">
        <h3>${tip("Chain Integrity", "Structural health of the governance chain. Verifies hash linkage and record validity. Breaks are classified as known (auto-repairable) or suspicious (requires investigation).")}</h3>
        <div class="status-grid">
          <div class="status-card">
            <span class="eyebrow">Status</span>
            <span class="status-value">${healthStatusBadge(chain.status || "unknown")}</span>
          </div>
          <div class="status-card">
            <span class="eyebrow">${tip("Records", "Total number of records in the active governance chain.")}</span>
            <span class="status-value">${chain.chain_event_count || 0}</span>
          </div>
          <div class="status-card">
            <span class="eyebrow">${tip("Verified", "Whether the chain has been checked during this health assessment.")}</span>
            <span class="status-value">${chain.checked ? '<span class="status-ok">Yes</span>' : '<span class="muted">No</span>'}</span>
          </div>
        </div>
        ${chainStatusHtml}
        ${repairHtml}
      </div>

      <div class="status-grid">
        <div class="card">
          <h3>${tip("Policy Trends", "ALLOW vs DENY ratio from recent governance decisions. A sudden spike in DENY rate may indicate misconfigured policy or a compromised agent.")}</h3>
          <div class="status-grid">
            <div class="status-card">
              <span class="eyebrow">ALLOW</span>
              <span class="status-value status-ok">${deny.allow_count || 0}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">DENY</span>
              <span class="status-value ${deny.deny_count > 0 ? "status-warn" : ""}">${deny.deny_count || 0}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("DENY Rate", "Percentage of recent policy decisions that resulted in DENY.")}</span>
              <span class="status-value">${deny.total > 0 ? Math.round(deny.deny_rate * 100) + "%" : "\u2014"}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Anomaly", "Whether the recent DENY rate is significantly above the historical average.")}</span>
              <span class="status-value">${deny.anomaly ? '<span class="status-warn">Detected</span>' : '<span class="status-ok">None</span>'}</span>
            </div>
          </div>
        </div>

        <div class="card">
          <h3>${tip("Observations", "Status of ungoverned operation observation hooks. Gap detection flags when governed operations continue but observations stop.")}</h3>
          <div class="status-grid">
            <div class="status-card">
              <span class="eyebrow">${tip("Hook Data", "Whether any observation hooks are reporting ungoverned operations.")}</span>
              <span class="status-value">${obs.has_observations ? '<span class="status-ok">Active</span>' : '<span class="muted">None</span>'}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Gap Detected", "A gap means governed operations are happening but no observations are being reported. Hooks may have stopped.")}</span>
              <span class="status-value">${obs.gap_detected ? '<span class="status-warn">Yes</span>' : '<span class="status-ok">No</span>'}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">Governed</span>
              <span class="status-value">${obs.governed_count || 0}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">Observed</span>
              <span class="status-value">${obs.observation_count || 0}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="status-grid">
        <div class="card">
          <h3>${tip("Storage", "Disk usage of governance data files. Monitor to ensure the system has adequate storage for the configured retention window.")}</h3>
          <div class="status-grid">
            <div class="status-card">
              <span class="eyebrow">${tip("Chain Size", "Size of the active governance chain file.")}</span>
              <span class="status-value">${formatBytes(storage.chain_size_bytes || 0)}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Stability Log", "Size of the chain stability/health log.")}</span>
              <span class="status-value">${formatBytes(storage.stability_log_size_bytes || 0)}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Archive", "Size of archived chain segments from rolling retention.")}</span>
              <span class="status-value">${formatBytes(storage.archive_size_bytes || 0)}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Archives", "Number of archived chain segment files.")}</span>
              <span class="status-value">${storage.archive_count || 0}</span>
            </div>
          </div>
          <p class="muted" style="margin-top:8px;font-size:0.82rem">Retention: ${retention.active_window_days || 90} days active, ${retention.archive_window_days || 90} days archive</p>
        </div>

        <div class="card">
          <h3>${tip("Users", "User activity summary from the governance chain. Anomalies flag users with unusually high action counts.")}</h3>
          <div class="status-grid">
            <div class="status-card">
              <span class="eyebrow">Unique Users</span>
              <span class="status-value">${users.unique_users || 0}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">${tip("Anomalies", "Users with action counts significantly above average. Could be normal for power users or indicate a compromised agent.")}</span>
              <span class="status-value">${users.anomalies && users.anomalies.length ? '<span class="status-warn">' + users.anomalies.length + '</span>' : '<span class="status-ok">0</span>'}</span>
            </div>
          </div>
          ${users.anomalies && users.anomalies.length ? `
            <div style="margin-top:8px">
              ${users.anomalies.map(a => `<p class="muted" style="font-size:0.82rem">${escapeHtml(a.description)}</p>`).join("")}
            </div>
          ` : ""}
        </div>
      </div>

      <div class="card">
        <h3>${tip("License", "Current license status. Trial expiry and tier information.")}</h3>
        <div class="status-grid">
          <div class="status-card">
            <span class="eyebrow">Status</span>
            <span class="status-value">${escapeHtml(license.status || "unknown")}</span>
          </div>
          ${license.tier ? `
            <div class="status-card">
              <span class="eyebrow">Tier</span>
              <span class="status-value">${escapeHtml(license.tier)}</span>
            </div>
          ` : ""}
          ${license.trial_days_remaining !== undefined ? `
            <div class="status-card">
              <span class="eyebrow">Trial Days</span>
              <span class="status-value ${license.trial_days_remaining < 7 ? "status-warn" : ""}">${license.trial_days_remaining}</span>
            </div>
          ` : ""}
          ${license.expiry ? `
            <div class="status-card">
              <span class="eyebrow">Expires</span>
              <span class="status-value">${formatTime(license.expiry)}</span>
            </div>
          ` : ""}
        </div>
      </div>

      ${stabilityEvents.length ? `
        <div class="card">
          <h3>${tip("Recent Health Events", "Stability log entries showing auto-repairs, checkpoints, break detections, and other health-related events.")}</h3>
          <table class="audit-results-table">
            <thead>
              <tr>
                <th>${tip("Time", "When the health event occurred.")}</th>
                <th>${tip("Type", "Category of health event.")}</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              ${stabilityEvents.map(e => `
                <tr>
                  <td>${formatTime(e.timestamp_utc)}</td>
                  <td>${escapeHtml(e.event_type)}</td>
                  <td>${escapeHtml(e.detail ? (e.detail.description || e.detail.strategy || e.detail.source || JSON.stringify(e.detail).slice(0, 80)) : "\u2014")}</td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      ` : ""}
    </section>
  `;
}

// ---------------------------------------------------------------------------
// Render dispatcher
// ---------------------------------------------------------------------------

const contentMap = {
  "/overview": renderOverview,
  "/activity": renderActivity,
  "/approvals": renderApprovals,
  "/audit": renderAudit,
  "/record": renderRecordDetail,
  "/report": renderReport,
  "/health": renderHealth,
};

async function render() {
  const context = getContext();
  const app = document.querySelector("#app");
  const renderFn = contentMap[context.path] || renderOverview;

  let content;
  try {
    content = await renderFn();
  } catch (err) {
    content = `<div class="card"><p class="status-warn">Error loading data: ${escapeHtml(err.message)}</p></div>`;
  }

  app.innerHTML = `
    <div class="shell">
      <header class="topbar">
        <div class="brand">
          <h1>Atested Dashboard</h1>
        </div>
        ${globalNav(context.path)}
      </header>
      ${content}
    </div>
  `;
}

// ---------------------------------------------------------------------------
// Form handlers (global — called via inline onsubmit)
// ---------------------------------------------------------------------------

window.handleAuditSubmit = function(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const startVal = fd.get("start_time");
  const endVal = fd.get("end_time");
  window.location.hash = navHref("/audit", {
    start_time: startVal ? startVal + ":00Z" : null,
    end_time: endVal ? endVal + ":00Z" : null,
    user: fd.get("user") || null,
    tool: fd.get("tool") || null,
    decision: fd.get("decision") || null,
    category: fd.get("category") || null,
    page: 1,
  });
  return false;
};

window.handleReportSubmit = function(e) {
  e.preventDefault();
  const fd = new FormData(e.target);
  const startVal = fd.get("start_time");
  const endVal = fd.get("end_time");
  window.location.hash = navHref("/report", {
    start_time: startVal ? startVal + ":00Z" : null,
    end_time: endVal ? endVal + ":00Z" : null,
    group_by: fd.get("group_by") || "tool",
  });
  return false;
};

window.exportAuditJson = async function() {
  const ctx = getContext();
  const queryParams = {
    start_time: ctx.startTime || null,
    end_time: ctx.endTime || null,
    user_identity: ctx.user || null,
    tool_name: ctx.tool || null,
    policy_decision: ctx.decision || null,
    event_category: ctx.category || null,
  };
  const [data, health] = await Promise.all([
    api("audit/query", { ...queryParams, limit: 10000, offset: 0 }),
    api("health").catch(() => null),
  ]);
  const exportPayload = {
    export_metadata: {
      exported_at: new Date().toISOString(),
      export_source: "atested-dashboard",
      format_version: "1.0",
    },
    query_parameters: Object.fromEntries(
      Object.entries(queryParams).filter(([, v]) => v != null)
    ),
    chain_integrity: health ? {
      status: health.chain?.status || "unknown",
      total_records: health.chain?.total_records ?? null,
      verified_at: health.chain?.last_verified || null,
    } : { status: "unavailable" },
    total_matching: data.total_matching,
    records: data.entries || [],
  };
  const blob = new Blob([JSON.stringify(exportPayload, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  const dateStr = new Date().toISOString().slice(0, 10);
  a.download = `atested-audit-export-${dateStr}.json`;
  a.click();
};

window.acknowledgeAlert = async function(source, message) {
  try {
    await fetch(`${API}/api/health/acknowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source, message }),
    });
    clearCache();
    render();
  } catch (err) {
    console.error("Failed to acknowledge alert:", err);
  }
};

// ---------------------------------------------------------------------------
// Bootstrap
// ---------------------------------------------------------------------------

window.addEventListener("hashchange", () => { clearCache(); render(); });

if (!window.location.hash) {
  window.location.hash = "/overview";
} else {
  render();
}
