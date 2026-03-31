// Atested Dashboard — live API-backed UI

const API = "";  // relative to current origin
const pageSize = 20;

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
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
  });
}

function truncate(s, n = 24) {
  if (!s) return "—";
  return s.length > n ? s.slice(0, n) + "…" : s;
}

function decisionTag(decision) {
  if (decision === "ALLOW") return '<span class="det-tag">ALLOW</span>';
  if (decision === "DENY") return '<span class="judgment-tag">DENY</span>';
  return `<span class="step-tag determined">${decision || "—"}</span>`;
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
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
    cached("activity", () => api("activity", { limit: 5 })),
    cached("users", () => api("users")),
  ]);

  const integ = status.chain_integrity === "ok"
    ? '<span class="status-ok">OK</span>'
    : '<span class="status-warn">BROKEN</span>';

  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Governance Status</span>
        <h2>System Overview</h2>
      </div>
      <div class="status-grid">
        <div class="status-card">
          <span class="eyebrow">Chain Events</span>
          <span class="status-value">${status.chain_event_count}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">Chain Integrity</span>
          <span class="status-value">${integ}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">Active Approvals</span>
          <span class="status-value">${status.active_approvals_count}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">Surfaces in Drift</span>
          <span class="status-value ${status.surfaces_in_drift.length ? "status-warn" : "status-ok"}">${status.surfaces_in_drift.length}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">Unique Users</span>
          <span class="status-value">${users.unique_users}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">Transparent Actions</span>
          <span class="status-value">${status.opacity_posture.transparent_count}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">Opaque Actions</span>
          <span class="status-value">${status.opacity_posture.opaque_count}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">Transparency %</span>
          <span class="status-value">${status.transparency_metric && status.transparency_metric.observation_data
            ? Math.round(status.transparency_metric.transparency_pct * 100) + "%"
            : '<span class="muted" style="font-size:0.75rem">No observation data</span>'}</span>
        </div>
      </div>

      ${status.transparency_metric ? `
        <div class="card">
          <h3>Transparency Metric</h3>
          <p class="muted" style="margin-bottom:12px">Ratio of governed operations to total observed operations (governed + ungoverned).</p>
          <div class="status-grid">
            <div class="status-card">
              <span class="eyebrow">Governed Ops</span>
              <span class="status-value">${status.transparency_metric.governed_operations}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">Ungoverned Obs.</span>
              <span class="status-value">${status.transparency_metric.ungoverned_observations}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">Total Observed</span>
              <span class="status-value">${status.transparency_metric.total_observed}</span>
            </div>
            <div class="status-card">
              <span class="eyebrow">Has Hook Data</span>
              <span class="status-value">${status.transparency_metric.observation_data
                ? '<span class="status-ok">Yes</span>'
                : '<span class="muted">No</span>'}</span>
            </div>
          </div>
        </div>
      ` : ""}

      ${status.verification_state && Object.keys(status.verification_state).length ? `
        <div class="card">
          <h3>Verification State</h3>
          <table class="audit-results-table">
            <thead><tr><th>Surface</th><th>State</th></tr></thead>
            <tbody>
              ${Object.entries(status.verification_state).map(([f, s]) => `
                <tr><td>${escapeHtml(f)}</td><td>${s === "drift_detected" ? '<span class="status-warn">drift_detected</span>' : escapeHtml(s)}</td></tr>
              `).join("")}
            </tbody>
          </table>
        </div>
      ` : ""}

      ${users.users.length ? `
        <div class="card">
          <h3>Users</h3>
          <table class="audit-results-table">
            <thead><tr><th>Identity</th><th>Actions</th></tr></thead>
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
        ${activity.entries.length ? activity.entries.map(e => `
          <div class="activity-entry">
            <strong>${escapeHtml(e.summary)}</strong>
            <span class="muted"> · ${e.event_category} · ${formatTime(e.timestamp_utc)}</span>
          </div>
        `).join("") : '<p class="muted">No activity recorded yet.</p>'}
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
              <tr><th>#</th><th>Time</th><th>Category</th><th>Summary</th><th>Family</th></tr>
            </thead>
            <tbody>
              ${data.entries.map(e => `
                <tr>
                  <td>${e.sequence_position}</td>
                  <td>${formatTime(e.timestamp_utc)}</td>
                  <td>${escapeHtml(e.event_category)}</td>
                  <td>${escapeHtml(e.summary)}</td>
                  <td>${escapeHtml(e.governed_family || "—")}</td>
                </tr>
              `).join("")}
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
      </div>
      ${data.active_approvals.length ? `
        <div class="approval-grid">
          ${data.active_approvals.map(a => `
            <div class="approval-card">
              <span class="eyebrow">Active approval</span>
              <h3>${truncate(a.artifact_identity, 40)}</h3>
              <ul class="kv">
                <li><span>Family</span><strong>${escapeHtml(a.governed_family || "—")}</strong></li>
                <li><span>Operator</span><strong>${escapeHtml(a.approving_operator)}</strong></li>
                <li><span>Context</span><strong>${escapeHtml(a.deployment_context || "—")}</strong></li>
                <li><span>Policy</span><strong>${escapeHtml(a.policy_version || "—")}</strong></li>
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
              <tr><th>#</th><th>Time</th><th>Category</th><th>Summary</th><th>User</th><th>Detail</th></tr>
            </thead>
            <tbody>
              ${data.entries.map(e => {
                const rid = e.evidence?.request_id || e.evidence?.event_id || e.evidence?.record_hash || "";
                return `
                  <tr>
                    <td>${e.sequence_position}</td>
                    <td>${formatTime(e.timestamp_utc)}</td>
                    <td>${escapeHtml(e.event_category)}</td>
                    <td>${escapeHtml(e.summary)}</td>
                    <td>${escapeHtml(e.user_identity || "—")}</td>
                    <td>${rid ? `<a href="${navHref("/record", { record_id: rid })}">View</a>` : "—"}</td>
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
        <form class="audit-form" id="audit-form" onsubmit="return handleAuditSubmit(event)">
          <label>Start time<input type="datetime-local" name="start_time" value="${ctx.startTime ? ctx.startTime.replace("Z","").replace("+00:00","") : ""}"></label>
          <label>End time<input type="datetime-local" name="end_time" value="${ctx.endTime ? ctx.endTime.replace("Z","").replace("+00:00","") : ""}"></label>
          <label>User identity<input type="text" name="user" value="${escapeHtml(ctx.user)}" placeholder="e.g. gkeeter"></label>
          <label>Tool name<input type="text" name="tool" value="${escapeHtml(ctx.tool)}" placeholder="e.g. FS_WRITE"></label>
          <label>Decision
            <select name="decision">
              <option value="">All</option>
              <option value="ALLOW" ${ctx.decision === "ALLOW" ? "selected" : ""}>ALLOW</option>
              <option value="DENY" ${ctx.decision === "DENY" ? "selected" : ""}>DENY</option>
            </select>
          </label>
          <label>Category
            <select name="category">
              <option value="">All</option>
              <option value="action_decision" ${ctx.category === "action_decision" ? "selected" : ""}>Action Decision</option>
              <option value="verification_transition" ${ctx.category === "verification_transition" ? "selected" : ""}>Verification</option>
              <option value="opaque_approval" ${ctx.category === "opaque_approval" ? "selected" : ""}>Approval</option>
              <option value="opaque_revocation" ${ctx.category === "opaque_revocation" ? "selected" : ""}>Revocation</option>
              <option value="opaque_invocation_decision" ${ctx.category === "opaque_invocation_decision" ? "selected" : ""}>Opaque Invocation</option>
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
        <pre style="overflow-x:auto;font-size:0.85rem;line-height:1.5">${escapeHtml(JSON.stringify(data.chain_record, null, 2))}</pre>
      </div>
      ${data.sidecar_record ? `
        <div class="card">
          <h3>Sidecar Record</h3>
          <pre style="overflow-x:auto;font-size:0.85rem;line-height:1.5">${escapeHtml(JSON.stringify(data.sidecar_record, null, 2))}</pre>
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
        <form class="audit-form" id="report-form" onsubmit="return handleReportSubmit(event)">
          <label>Start time<input type="datetime-local" name="start_time" value="${ctx.startTime ? ctx.startTime.replace("Z","").replace("+00:00","") : ""}"></label>
          <label>End time<input type="datetime-local" name="end_time" value="${ctx.endTime ? ctx.endTime.replace("Z","").replace("+00:00","") : ""}"></label>
          <label>Group by
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
        <h3>Decision Summary (${data.total_records} records)</h3>
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
// Render dispatcher
// ---------------------------------------------------------------------------

const contentMap = {
  "/overview": renderOverview,
  "/activity": renderActivity,
  "/approvals": renderApprovals,
  "/audit": renderAudit,
  "/record": renderRecordDetail,
  "/report": renderReport,
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
  const data = await api("audit/query", {
    start_time: ctx.startTime || null,
    end_time: ctx.endTime || null,
    user_identity: ctx.user || null,
    tool_name: ctx.tool || null,
    policy_decision: ctx.decision || null,
    event_category: ctx.category || null,
    limit: 10000,
    offset: 0,
  });
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `audit-export-${new Date().toISOString().slice(0,19).replace(/:/g,"-")}.json`;
  a.click();
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
