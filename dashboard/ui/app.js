// Atested Dashboard — live API-backed UI

const API = "";  // relative to current origin
const pageSize = 20;
const ATESTED_VERSION = "1.0.0";
let _updateDismissed = false;

// Bearer token injected by the server into the HTML meta tag at startup
function _getAuthToken() {
  const meta = document.querySelector('meta[name="dashboard-token"]');
  return meta ? meta.getAttribute("content") : null;
}

function _authHeaders() {
  const token = _getAuthToken();
  return token ? { "Authorization": `Bearer ${token}` } : {};
}

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
  const resp = await fetch(url, { headers: _authHeaders() });
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
  if (s == null) return "";
  const div = document.createElement("div");
  div.textContent = String(s);
  return div.innerHTML.replace(/'/g, "&#39;");
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
    { path: "/overview", label: "Overview", tip: "High-level governance posture: chain health, user counts, transparency, and denied actions." },
    { path: "/activity", label: "Activity", tip: "Chronological feed of every governed event — actions, approvals, verifications, and observations." },
    { path: "/approvals", label: "Approvals", tip: "Active artifact approvals and their governed categories, operators, and contexts." },
    { path: "/audit", label: "Audit", tip: "Query the governance chain by time, user, tool, decision, or event category. Export results as JSON." },
    { path: "/report", label: "Reports", tip: "Aggregate views of governance activity grouped by tool, user, decision, or category." },
    { path: "/health", label: "Health", tip: "Infrastructure status: chain integrity, policy trends, storage, observation coverage, and license." },
    { path: "/configuration", label: "Configuration", tip: "View and manage the capability registry — governed tool directories, constraints, and hard caps." },
    { path: "/feedback", label: "Feedback", tip: "Send feedback, view telemetry history, and control what data leaves your installation." },
  ];
  return `
    <nav class="nav">
      ${tabs.map(t => {
        const isActive = currentPath === t.path;
        const cls = isActive ? "active" : "";
        return `<a class="${cls}"
           href="${navHref(t.path, { page: null, record_id: null })}"><span class="tab-tip-wrap">${t.label}<span class="tab-tip-text">${escapeHtml(t.tip)}</span></span></a>`;
      }).join("")}
    </nav>
  `;
}

// ---------------------------------------------------------------------------
// Configuration edit state
// ---------------------------------------------------------------------------

let _configEditMode = false;
let _configLicenseKey = "";
let _configData = null;

// ---------------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------------

async function renderOverview() {
  const [status, approvals, activity, users, health, updateInfo] = await Promise.all([
    cached("status", () => api("status")),
    cached("approvals", () => api("approvals")),
    cached("activity", () => api("activity", { limit: 8 })),
    cached("users", () => api("users")),
    cached("health", () => api("health")).catch(() => null),
    cached("update-check", () => api("update-check")).catch(() => null),
  ]);

  const integ = status.chain_integrity === "ok"
    ? '<span class="status-ok">OK</span>'
    : '<span class="status-warn">BROKEN</span>';

  const transparencyVal = status.transparency_metric && status.transparency_metric.observation_data
    ? Math.round(status.transparency_metric.transparency_pct * 100) + "%"
    : '<span class="muted" style="font-size:0.75rem">No observation data</span>';

  const updateBanner = (updateInfo && updateInfo.update_available && !_updateDismissed)
    ? `<div class="update-banner">
         <span>Atested <strong>v${escapeHtml(updateInfo.latest_version)}</strong> is available. You are running v${escapeHtml(ATESTED_VERSION)}.</span>
         <span>
           <a href="${escapeHtml(updateInfo.release_url)}" target="_blank" rel="noopener"><button>View release</button></a>
           <button class="dismiss-btn" onclick="_updateDismissed=true;clearCache();render();">&times;</button>
         </span>
       </div>`
    : "";

  return `
    <section class="page">
      ${updateBanner}
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
        <div class="status-card denied-highlight">
          <span class="eyebrow">${tip("Actions Denied Before Execution", "Every DENY is a prevented action — stopped before it could execute because required conditions were not met. This is governance working as intended.")}</span>
          <span class="status-value status-danger">${health?.deny_rate?.deny_count || 0}</span>
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
        <div id="overview-recent-activity">
        ${activity.entries.length ? activity.entries.map(e => {
          const rid = e.evidence?.request_id || e.evidence?.event_id || e.evidence?.record_hash || "";
          const href = rid ? navHref("/record", { record_id: rid }) : "";
          return `
            <div class="activity-entry${href ? " clickable" : ""}" ${href ? `data-nav-href="${escapeHtml(href)}"` : ""}>
              <strong>${escapeHtml(e.summary)}</strong>
              <span class="muted"> \u00b7 ${categoryLabel(e.event_category)} \u00b7 ${formatTime(e.timestamp_utc)}</span>
            </div>
          `;
        }).join("") : '<p class="muted">No activity recorded yet.</p>'}
        </div>
      </div>
    </section>
  `;
}

function _attachOverviewActivityListeners() {
  const container = document.getElementById("overview-recent-activity");
  if (!container) return;
  container.querySelectorAll(".activity-entry[data-nav-href]").forEach(el => {
    el.addEventListener("click", () => {
      window.location.hash = el.getAttribute("data-nav-href");
    });
  });
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
                <th>${tip("Event Type", "The type of governance event: governed action, approval, verification change, observation, etc.")}</th>
                <th>${tip("Decision", "Whether the action was allowed or denied. Only applies to governed action events.")}</th>
                <th>${tip("Summary", "Human-readable description of what happened.")}</th>
                <th>${tip("Category", "The governed category this event belongs to, if applicable.")}</th>
                <th>${tip("Detail", "Link to the full record in the governance chain.")}</th>
              </tr>
            </thead>
            <tbody id="activity-tbody">
              ${data.entries.map(e => {
                const rid = e.evidence?.request_id || e.evidence?.event_id || e.evidence?.record_hash || "";
                const decision = e.evidence?.policy_decision || "";
                const isDeny = decision === "DENY" || e.summary?.includes("DENY");
                const rowCls = [rid ? "clickable-row" : "", isDeny ? "deny-row" : ""].filter(Boolean).join(" ");
                return `
                  <tr class="${rowCls}" ${rid ? `data-nav-href="${escapeHtml(navHref("/record", { record_id: rid }))}"` : ""}>
                    <td>${e.sequence_position}</td>
                    <td>${formatTime(e.timestamp_utc)}</td>
                    <td>${categoryLabel(e.event_category)}</td>
                    <td>${decision ? (isDeny ? '<span class="deny-badge">PREVENTED</span>' : `<span class="status-ok">${decision}</span>`) : "\u2014"}</td>
                    <td>${escapeHtml(e.summary)}</td>
                    <td>${escapeHtml(e.governed_family || "\u2014")}</td>
                    <td>${rid ? `<a href="${escapeHtml(navHref("/record", { record_id: rid }))}">View</a>` : "\u2014"}</td>
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

function _attachActivityListeners() {
  const tbody = document.getElementById("activity-tbody");
  if (!tbody) return;
  tbody.querySelectorAll("tr[data-nav-href]").forEach(row => {
    row.addEventListener("click", () => {
      window.location.hash = row.getAttribute("data-nav-href");
    });
  });
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
                <th>${tip("Event Type", "Type of governance event: governed action, approval, verification, observation.")}</th>
                <th>${tip("Summary", "What happened.")}</th>
                <th>${tip("User", "Identity of the user who triggered the action.")}</th>
                <th>${tip("Detail", "Link to the full record in the governance chain.")}</th>
              </tr>
            </thead>
            <tbody id="audit-tbody">
              ${data.entries.map(e => {
                const rid = e.evidence?.request_id || e.evidence?.event_id || e.evidence?.record_hash || "";
                return `
                  <tr class="${rid ? "clickable-row" : ""}" ${rid ? `data-nav-href="${escapeHtml(navHref("/record", { record_id: rid }))}"` : ""}>
                    <td>${e.sequence_position}</td>
                    <td>${formatTime(e.timestamp_utc)}</td>
                    <td>${categoryLabel(e.event_category)}</td>
                    <td>${escapeHtml(e.summary)}</td>
                    <td>${escapeHtml(e.user_identity || "\u2014")}</td>
                    <td>${rid ? `<a href="${escapeHtml(navHref("/record", { record_id: rid }))}">View</a>` : "\u2014"}</td>
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
          <label>${tip("User identity", "Filter by the user who triggered the action.")}<input type="text" name="user" value="${escapeHtml(ctx.user)}" placeholder="e.g. operator-1"></label>
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

function _attachAuditListeners() {
  const tbody = document.getElementById("audit-tbody");
  if (!tbody) return;
  tbody.querySelectorAll("tr[data-nav-href]").forEach(row => {
    row.addEventListener("click", () => {
      window.location.hash = row.getAttribute("data-nav-href");
    });
  });
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
    <div class="card" id="health-alerts-container">
      <h3>Active Alerts</h3>
      ${data.alerts.map(a => `
        <div class="health-alert health-alert--${a.severity}">
          <div class="health-alert-header">
            <strong>${escapeHtml(a.source)}</strong>
            <span class="health-alert-severity">${a.severity === "critical" ? "CRITICAL" : a.severity === "attention" ? "ATTENTION" : "INFO"}</span>
          </div>
          <p>${escapeHtml(a.message)}</p>
          ${a.guidance ? `<p class="muted" style="font-size:0.85rem">${escapeHtml(a.guidance)}</p>` : ""}
          <button class="export-link ack-alert-btn" style="margin-top:8px"
            data-alert-source="${escapeHtml(a.source)}"
            data-alert-message="${escapeHtml(a.message)}">Acknowledge</button>
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
        <h3>${tip("Chain Integrity", "Structural health of the governance chain. Chain breaks are classified and handled automatically. Known issues are self-repaired. Suspicious or repeated breaks trigger an alert for your review.")}</h3>
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
          <h3>${tip("DENY Rate Trend", "Rate of denied actions over time. A sudden spike may indicate a misconfigured scope, a compromised agent, or an unusual workflow change.")}</h3>
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
          <h3>${tip("Transparency Trend", "Ratio of governed operations to total observed AI activity over time. Higher means more of your operations are under governance.")}</h3>
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
          <h3>${tip("Storage", "Governance chain size, archive size, and retention window status.")}</h3>
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
                <th>${tip("Type", "Category of health event: checkpoint, break_detected, auto_repair, etc.")}</th>
                <th>${tip("Detail", "Summary of the health event — repair strategy, break source, or checkpoint info.")}</th>
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

function _attachHealthListeners() {
  const container = document.getElementById("health-alerts-container");
  if (!container) return;
  container.querySelectorAll(".ack-alert-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      window.acknowledgeAlert(
        btn.getAttribute("data-alert-source"),
        btn.getAttribute("data-alert-message")
      );
    });
  });
}

// ---------------------------------------------------------------------------
// Configuration page
// ---------------------------------------------------------------------------

async function renderConfiguration() {
  let data;
  try {
    data = await cached("config", () => api("config"));
    _configData = data;
  } catch (err) {
    return `
      <section class="page">
        <div class="card">
          <span class="eyebrow">Configuration</span>
          <h2>Capability Registry</h2>
          <p class="status-warn">Unable to load configuration: ${escapeHtml(err.message)}</p>
        </div>
      </section>
    `;
  }

  const registry = data.registry || {};
  const tools = registry.tools || data.tools || [];
  const integrity = data.integrity || {};
  const license = data.license || {};
  const isTrial = license.status === "trial" || license.tier === "personal";

  const integrityBadge = integrity.status === "ok"
    ? '<span class="status-ok">OK</span>'
    : (integrity.status ? `<span class="status-warn">${escapeHtml(integrity.status)}</span>` : '<span class="muted">\u2014</span>');

  const toolRowsView = tools.map((t, idx) => {
    const name = t.name || t.tool_name || t.id || "\u2014";
    const risk = t.risk_level || t.risk || "\u2014";
    const dirs = (t.allow_base_dirs || t.allowed_dirs || []).join(", ") || "\u2014";
    const denyHidden = t.deny_hidden_paths !== undefined ? t.deny_hidden_paths : (t.constraints?.deny_hidden ?? "\u2014");
    const denyOverwrite = t.deny_overwrite_by_default !== undefined ? t.deny_overwrite_by_default : (t.constraints?.deny_overwrite ?? "\u2014");
    const denyExec = t.deny_executable_outputs !== undefined ? t.deny_executable_outputs : (t.constraints?.deny_executable ?? "\u2014");
    const maxBytes = t.max_bytes_hard !== undefined ? t.max_bytes_hard : (t.hard_caps?.max_bytes ?? "\u2014");

    function boolBadge(val) {
      if (val === true) return '<span class="status-ok">Yes</span>';
      if (val === false) return '<span class="muted">No</span>';
      return `<span class="muted">${escapeHtml(String(val))}</span>`;
    }

    return `
      <tr>
        <td><strong>${escapeHtml(name)}</strong></td>
        <td>${escapeHtml(String(risk))}</td>
        <td style="font-size:0.82rem;word-break:break-all">${escapeHtml(dirs)}</td>
        <td>${boolBadge(denyHidden)}</td>
        <td>${boolBadge(denyOverwrite)}</td>
        <td>${boolBadge(denyExec)}</td>
        <td>${escapeHtml(String(maxBytes))}</td>
      </tr>
    `;
  }).join("");

  const toolRowsEdit = tools.map((t, idx) => {
    const name = t.name || t.tool_name || t.id || "";
    const risk = t.risk_level || t.risk || "";
    const dirs = t.allow_base_dirs || t.allowed_dirs || [];
    const denyHidden = t.deny_hidden_paths !== undefined ? t.deny_hidden_paths : (t.constraints?.deny_hidden ?? false);
    const denyOverwrite = t.deny_overwrite_by_default !== undefined ? t.deny_overwrite_by_default : (t.constraints?.deny_overwrite ?? false);
    const denyExec = t.deny_executable_outputs !== undefined ? t.deny_executable_outputs : (t.constraints?.deny_executable ?? false);
    const maxBytes = t.max_bytes_hard !== undefined ? t.max_bytes_hard : (t.hard_caps?.max_bytes ?? "");

    const dirInputs = dirs.map((d, di) => `
      <div class="config-dir-row" data-tool-idx="${idx}" data-dir-idx="${di}">
        <input type="text" class="config-dir-input" value="${escapeHtml(d)}"
          data-tool-idx="${idx}" data-dir-idx="${di}"
          style="width:280px;font-size:0.82rem">
        <button class="pill" onclick="window.removeDirectory(${idx}, ${di})" style="margin-left:4px">Remove</button>
      </div>
    `).join("");

    return `
      <tr>
        <td><strong>${escapeHtml(name)}</strong><input type="hidden" name="tool_name_${idx}" value="${escapeHtml(name)}"></td>
        <td><span class="muted" style="font-size:0.82rem">${escapeHtml(risk)}</span></td>
        <td>
          <div id="config-dirs-${idx}">${dirInputs}</div>
          <button class="pill" onclick="window.addDirectory(${idx})" style="margin-top:4px;font-size:0.8rem">+ Add Directory</button>
        </td>
        <td><label><input type="checkbox" name="deny_hidden_${idx}" ${denyHidden ? "checked" : ""}> deny_hidden</label></td>
        <td><label><input type="checkbox" name="deny_overwrite_${idx}" ${denyOverwrite ? "checked" : ""}> deny_overwrite</label></td>
        <td><label><input type="checkbox" name="deny_exec_${idx}" ${denyExec ? "checked" : ""}> deny_exec</label></td>
        <td><input type="number" name="max_bytes_${idx}" value="${escapeHtml(String(maxBytes))}" style="width:90px"></td>
      </tr>
    `;
  }).join("");

  const trialBanner = isTrial ? `
    <div class="card" style="border-left:3px solid var(--warn,#e8a000);padding-left:16px">
      <span class="eyebrow">Trial License</span>
      <p style="margin:4px 0 0">
        Configuration editing requires a paid license.
        You are currently on the <strong>${escapeHtml(license.tier || "trial")}</strong> tier.
        ${license.trial_days_remaining !== undefined
          ? `<span class="status-warn">${license.trial_days_remaining} days remaining.</span>`
          : ""}
        Unlock editing by entering a valid license key below.
      </p>
    </div>
  ` : "";

  const lockSection = !_configEditMode ? `
    <div class="card">
      <h3>${tip("Unlock Editing", "Configuration editing requires a valid license key. Enter your key to enable edit mode.")}</h3>
      ${trialBanner}
      <form class="audit-form" id="config-unlock-form" onsubmit="return false">
        <label>${tip("License Key", "Your Atested license key. Starts with atested-.")}
          <input type="text" id="config-license-key-input" placeholder="atested-xxxx-xxxx-xxxx"
            style="width:320px" value="${escapeHtml(_configLicenseKey)}">
        </label>
        <button type="button" onclick="window.unlockConfigEditing()">Unlock Editing</button>
      </form>
      <p id="config-unlock-error" class="status-warn" style="display:none;margin-top:8px"></p>
    </div>
  ` : "";

  const viewTable = !_configEditMode ? `
    <div class="card">
      <h3>${tip("Governed Tools", "All tools registered in the capability registry with their current constraints and hard caps.")}</h3>
      ${tools.length ? `
        <table class="audit-results-table">
          <thead>
            <tr>
              <th>${tip("Tool", "The governed tool name (e.g. FS_READ, FS_WRITE).")}</th>
              <th>${tip("Risk Level", "The risk classification for this tool: low, medium, or high.")}</th>
              <th>${tip("Allowed Directories", "Base directories this tool is permitted to operate within.")}</th>
              <th>${tip("deny_hidden", "Whether access to hidden paths (dot-files) is denied.")}</th>
              <th>${tip("deny_overwrite", "Whether overwriting existing files is denied by default.")}</th>
              <th>${tip("deny_exec", "Whether producing executable output files is denied.")}</th>
              <th>${tip("Max Bytes (hard cap)", "Hard cap on bytes read or written in a single operation.")}</th>
            </tr>
          </thead>
          <tbody>
            ${toolRowsView}
          </tbody>
        </table>
      ` : '<p class="muted">No tools registered in the capability registry.</p>'}
    </div>
  ` : "";

  const editForm = _configEditMode ? `
    <div class="card">
      <h3>Edit Configuration <span class="status-ok" style="font-size:0.8rem;margin-left:8px">Edit Mode Active</span></h3>
      <p class="explainer">Changes are applied immediately when you click Save Configuration. Each tool's directories, constraint flags, and hard caps can be adjusted below.</p>
      <form id="config-edit-form" onsubmit="return false">
        <table class="audit-results-table" id="config-tools-table">
          <thead>
            <tr>
              <th>${tip("Tool", "The governed tool name.")}</th>
              <th>${tip("Risk Level", "Risk classification (read-only).")}</th>
              <th>${tip("Allowed Directories", "Directories this tool may access. Add or remove entries.")}</th>
              <th>${tip("deny_hidden", "Deny hidden path access.")}</th>
              <th>${tip("deny_overwrite", "Deny overwriting files by default.")}</th>
              <th>${tip("deny_exec", "Deny executable output.")}</th>
              <th>${tip("Max Bytes", "Hard cap on bytes per operation.")}</th>
            </tr>
          </thead>
          <tbody id="config-tools-tbody">
            ${toolRowsEdit}
          </tbody>
        </table>
        <div style="margin-top:16px">
          <button type="button" onclick="window.saveConfiguration()">Save Configuration</button>
          <button type="button" class="pill" onclick="window._configEditMode=false;clearCache();render()" style="margin-left:8px">Cancel</button>
        </div>
        <p id="config-save-status" style="margin-top:8px;display:none"></p>
      </form>
    </div>
  ` : "";

  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Configuration</span>
        <h2>Capability Registry</h2>
        <p class="explainer">
          The capability registry defines which governed tools are active, what directories they may
          access, and what constraint flags and hard caps are enforced. The registry hash is included
          in every governance chain record for tamper-evidence.
        </p>
      </div>

      <div class="status-grid">
        <div class="status-card">
          <span class="eyebrow">${tip("Registry Hash", "SHA-256 of the capability registry at last load. Included in every governance decision record.")}</span>
          <span class="status-value" style="font-size:0.75rem;word-break:break-all">${escapeHtml(truncate(integrity.hash || data.registry_hash || "\u2014", 20))}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Integrity", "Whether the registry file matches its expected hash.")}</span>
          <span class="status-value">${integrityBadge}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Last Verified", "When the registry integrity was last checked.")}</span>
          <span class="status-value" style="font-size:0.85rem">${formatTime(integrity.last_verified || data.last_verified || null)}</span>
        </div>
        <div class="status-card">
          <span class="eyebrow">${tip("Governed Tools", "Total number of tools registered in the capability registry.")}</span>
          <span class="status-value">${tools.length}</span>
        </div>
      </div>

      ${lockSection}
      ${viewTable}
      ${editForm}
    </section>
  `;
}

function _attachConfigListeners() {
  // No delegated-event listeners needed for configuration page;
  // all interactions use window.* handlers attached inline.
}

// ---------------------------------------------------------------------------
// Feedback & Telemetry page
// ---------------------------------------------------------------------------

async function renderFeedback() {
  const [fbResp, tmResp, optResp] = await Promise.all([
    apiFetch("/api/feedback"),
    apiFetch("/api/telemetry"),
    apiFetch("/api/telemetry/status"),
  ]);

  const fbArtifacts = (fbResp.artifacts || []);
  const tmArtifacts = (tmResp.artifacts || []);
  const optedIn = optResp.opted_in || false;

  const feedbackRows = fbArtifacts.map(a => `
    <tr>
      <td class="mono">${escapeHtml(a.timestamp || "")}</td>
      <td>${escapeHtml((a.message || "").slice(0, 80))}${(a.message || "").length > 80 ? "..." : ""}</td>
      <td>${a.experience_note ? "Yes" : ""}</td>
      <td><span class="badge ${a.signed ? "badge-ok" : "badge-warn"}">${a.signed ? "Signed" : "Unsigned"}</span></td>
      <td class="mono" title="${escapeHtml(a.artifact_hash || "")}">${escapeHtml((a.artifact_hash || "").slice(0, 20))}...</td>
    </tr>
  `).join("") || '<tr><td colspan="5" class="muted">No feedback artifacts yet.</td></tr>';

  const telemetryRows = tmArtifacts.map(a => `
    <tr>
      <td class="mono">${escapeHtml(a.timestamp || "")}</td>
      <td>${a.total_allow ?? 0}</td>
      <td>${a.total_deny ?? 0}</td>
      <td>${a.total_deterministic ?? 0}</td>
      <td>${a.total_judgment ?? 0}</td>
      <td><span class="badge ${a.signed ? "badge-ok" : "badge-warn"}">${a.signed ? "Signed" : "Unsigned"}</span></td>
      <td class="mono" title="${escapeHtml(a.artifact_hash || "")}">${escapeHtml((a.artifact_hash || "").slice(0, 20))}...</td>
    </tr>
  `).join("") || '<tr><td colspan="7" class="muted">No telemetry artifacts yet.</td></tr>';

  return `
    <section class="page-section">
      <h2>Send Feedback</h2>
      <p class="section-note">Feedback is signed with your installation's Ed25519 key. Only real Atested installations can submit feedback.</p>
      <form id="feedback-form" class="feedback-form">
        <label for="fb-message">Your feedback</label>
        <textarea id="fb-message" name="message" rows="3" placeholder="What's working? What could be better?" required></textarea>

        <label for="fb-experience">What has Atested helped you avoid or improve? <span class="muted">(optional — for case studies)</span></label>
        <textarea id="fb-experience" name="experience_note" rows="2" placeholder="e.g. Caught a staging path write before it hit production"></textarea>

        <div class="feedback-options">
          <label class="checkbox-label">
            <input type="checkbox" name="permission_to_use" id="fb-permission">
            Atested may use this feedback anonymously in product materials
          </label>
          <label class="checkbox-label">
            <input type="checkbox" name="send_to_remote" id="fb-send-remote">
            Send to Atested team (via signed artifact to atested.com)
          </label>
        </div>

        <button type="submit" class="btn btn-primary">Submit Feedback</button>
        <div id="feedback-result" class="feedback-result"></div>
      </form>
    </section>

    <section class="page-section">
      <h2>Telemetry Controls</h2>
      <p class="section-note">
        Telemetry shares anonymous, aggregated usage counts only. No user identities, file paths, action targets, or organization names are sent.
        You can see exactly what is sent below.
      </p>
      <div class="telemetry-opt-in">
        <label class="checkbox-label">
          <input type="checkbox" id="telemetry-toggle" ${optedIn ? "checked" : ""}>
          <strong>Share anonymous usage data</strong> — help improve Atested by sharing aggregated decision counts
        </label>
        <button id="telemetry-send-now" class="btn btn-secondary" style="margin-left:12px;">Send telemetry now</button>
        <div id="telemetry-result" class="feedback-result"></div>
      </div>
    </section>

    <section class="page-section">
      <h2>Feedback History</h2>
      <p class="section-note">Every feedback artifact generated by this installation — whether sent or not.</p>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Timestamp</th><th>Message</th><th>Experience note</th><th>Signed</th><th>Hash</th></tr></thead>
          <tbody>${feedbackRows}</tbody>
        </table>
      </div>
    </section>

    <section class="page-section">
      <h2>Telemetry History</h2>
      <p class="section-note">Every telemetry artifact generated — the full content of what was (or would be) sent.</p>
      <div class="table-scroll">
        <table>
          <thead><tr><th>Timestamp</th><th>ALLOW</th><th>DENY</th><th>Deterministic</th><th>Judgment</th><th>Signed</th><th>Hash</th></tr></thead>
          <tbody>${telemetryRows}</tbody>
        </table>
      </div>
    </section>
  `;
}

function _attachFeedbackListeners() {
  const form = document.getElementById("feedback-form");
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const resultDiv = document.getElementById("feedback-result");
      resultDiv.textContent = "Submitting...";
      resultDiv.className = "feedback-result";

      const message = document.getElementById("fb-message").value;
      const experience_note = document.getElementById("fb-experience").value;
      const permission_to_use = document.getElementById("fb-permission").checked;
      const send_to_remote = document.getElementById("fb-send-remote").checked;

      try {
        const resp = await apiFetch("/api/feedback/submit", {
          method: "POST",
          body: JSON.stringify({ message, experience_note, permission_to_use, send_to_remote }),
        });
        if (resp.error) {
          resultDiv.textContent = "Error: " + resp.error;
          resultDiv.className = "feedback-result feedback-error";
        } else {
          resultDiv.textContent = "Feedback submitted" + (resp.remote?.sent ? " and sent to Atested team." : " (stored locally).");
          resultDiv.className = "feedback-result feedback-success";
          form.reset();
        }
      } catch (err) {
        resultDiv.textContent = "Error: " + err.message;
        resultDiv.className = "feedback-result feedback-error";
      }
    });
  }

  const toggle = document.getElementById("telemetry-toggle");
  if (toggle) {
    toggle.addEventListener("change", async () => {
      try {
        await apiFetch("/api/telemetry/opt-in", {
          method: "POST",
          body: JSON.stringify({ opted_in: toggle.checked }),
        });
      } catch (err) {
        console.error("Failed to update telemetry opt-in:", err);
      }
    });
  }

  const sendNow = document.getElementById("telemetry-send-now");
  if (sendNow) {
    sendNow.addEventListener("click", async () => {
      const resultDiv = document.getElementById("telemetry-result");
      resultDiv.textContent = "Generating telemetry artifact...";
      resultDiv.className = "feedback-result";
      try {
        const resp = await apiFetch("/api/telemetry/submit", {
          method: "POST",
          body: JSON.stringify({ send_to_remote: true }),
        });
        if (resp.error) {
          resultDiv.textContent = "Error: " + resp.error;
          resultDiv.className = "feedback-result feedback-error";
        } else {
          resultDiv.textContent = `Telemetry sent. ALLOW: ${resp.total_allow}, DENY: ${resp.total_deny}, Deterministic: ${resp.total_deterministic}, Judgment: ${resp.total_judgment}`;
          resultDiv.className = "feedback-result feedback-success";
        }
      } catch (err) {
        resultDiv.textContent = "Error: " + err.message;
        resultDiv.className = "feedback-result feedback-error";
      }
    });
  }
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
  "/configuration": renderConfiguration,
  "/feedback": renderFeedback,
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
          <h1 title="Activating this UI is as simple as asking any AI connected to Atested to display it.">Atested Dashboard</h1>
        </div>
        ${globalNav(context.path)}
      </header>
      ${content}
    </div>
  `;

  // Attach event listeners for elements that replaced inline onclick attributes
  _attachOverviewActivityListeners();
  _attachActivityListeners();
  _attachAuditListeners();
  _attachHealthListeners();
  _attachConfigListeners();
  _attachFeedbackListeners();
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
      headers: { "Content-Type": "application/json", ..._authHeaders() },
      body: JSON.stringify({ source, message }),
    });
    clearCache();
    render();
  } catch (err) {
    console.error("Failed to acknowledge alert:", err);
  }
};

window.unlockConfigEditing = async function() {
  const input = document.getElementById("config-license-key-input");
  const errorEl = document.getElementById("config-unlock-error");
  if (!input) return;
  const key = input.value.trim();
  if (!key) {
    if (errorEl) { errorEl.textContent = "Please enter a license key."; errorEl.style.display = ""; }
    return;
  }
  try {
    const resp = await fetch(`${API}/api/config/verify-license`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ..._authHeaders() },
      body: JSON.stringify({ license_key: key }),
    });
    const result = await resp.json();
    if (result.valid) {
      _configLicenseKey = key;
      _configEditMode = true;
      if (errorEl) errorEl.style.display = "none";
      clearCache();
      render();
    } else {
      _configEditMode = false;
      if (errorEl) {
        errorEl.textContent = result.message || "License key is not valid. Editing is restricted to paid tiers.";
        errorEl.style.display = "";
      }
    }
  } catch (err) {
    _configEditMode = false;
    if (errorEl) {
      errorEl.textContent = "License verification failed: " + err.message;
      errorEl.style.display = "";
    }
  }
};

window.saveConfiguration = async function() {
  const statusEl = document.getElementById("config-save-status");
  const tools = _configData ? (_configData.registry?.tools || _configData.tools || []) : [];

  const updates = tools.map((t, idx) => {
    const name = t.name || t.tool_name || t.id || "";
    // Collect directory inputs
    const dirContainer = document.getElementById(`config-dirs-${idx}`);
    const dirs = dirContainer
      ? Array.from(dirContainer.querySelectorAll(".config-dir-input"))
          .map(inp => inp.value.trim())
          .filter(Boolean)
      : (t.allow_base_dirs || t.allowed_dirs || []);

    const denyHiddenEl = document.querySelector(`[name="deny_hidden_${idx}"]`);
    const denyOverwriteEl = document.querySelector(`[name="deny_overwrite_${idx}"]`);
    const denyExecEl = document.querySelector(`[name="deny_exec_${idx}"]`);
    const maxBytesEl = document.querySelector(`[name="max_bytes_${idx}"]`);

    return {
      tool_name: name,
      allow_base_dirs: dirs,
      deny_hidden_paths: denyHiddenEl ? denyHiddenEl.checked : undefined,
      deny_overwrite_by_default: denyOverwriteEl ? denyOverwriteEl.checked : undefined,
      deny_executable_outputs: denyExecEl ? denyExecEl.checked : undefined,
      max_bytes_hard: maxBytesEl && maxBytesEl.value !== "" ? Number(maxBytesEl.value) : undefined,
    };
  });

  if (statusEl) { statusEl.textContent = "Saving\u2026"; statusEl.className = ""; statusEl.style.display = ""; }

  try {
    const resp = await fetch(`${API}/api/config/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ..._authHeaders() },
      body: JSON.stringify({ license_key: _configLicenseKey, tools: updates }),
    });
    const result = await resp.json();
    if (resp.ok && (result.success !== false)) {
      if (statusEl) { statusEl.textContent = "Configuration saved successfully."; statusEl.className = "status-ok"; }
      _configEditMode = false;
      clearCache();
      render();
    } else {
      if (statusEl) {
        statusEl.textContent = "Save failed: " + (result.message || result.error || "Unknown error.");
        statusEl.className = "status-warn";
      }
    }
  } catch (err) {
    if (statusEl) {
      statusEl.textContent = "Save failed: " + err.message;
      statusEl.className = "status-warn";
    }
  }
};

window.addDirectory = function(toolIdx) {
  const container = document.getElementById(`config-dirs-${toolIdx}`);
  if (!container) return;
  const newIdx = container.querySelectorAll(".config-dir-row").length;
  const row = document.createElement("div");
  row.className = "config-dir-row";
  row.setAttribute("data-tool-idx", toolIdx);
  row.setAttribute("data-dir-idx", newIdx);
  row.innerHTML = `
    <input type="text" class="config-dir-input" value=""
      data-tool-idx="${toolIdx}" data-dir-idx="${newIdx}"
      style="width:280px;font-size:0.82rem" placeholder="/path/to/directory">
    <button class="pill" onclick="window.removeDirectory(${toolIdx}, ${newIdx})" style="margin-left:4px">Remove</button>
  `;
  container.appendChild(row);
};

window.removeDirectory = function(toolIdx, dirIdx) {
  const container = document.getElementById(`config-dirs-${toolIdx}`);
  if (!container) return;
  const row = container.querySelector(`.config-dir-row[data-dir-idx="${dirIdx}"]`);
  if (row) row.remove();
  // Re-index remaining rows so removeDirectory callbacks stay consistent
  container.querySelectorAll(".config-dir-row").forEach((r, i) => {
    r.setAttribute("data-dir-idx", i);
    const inp = r.querySelector(".config-dir-input");
    if (inp) inp.setAttribute("data-dir-idx", i);
    const btn = r.querySelector("button");
    if (btn) btn.setAttribute("onclick", `window.removeDirectory(${toolIdx}, ${i})`);
  });
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
