import { actions, approvals } from "./fixtures.js";

const timeframes = ["All", "Today", "Week", "Month", "Year", "Custom"];
const pageSize = 3;
const deterministicCategories = [
  { key: "", label: "All categories" },
  { key: "completed", label: "Completed" },
  { key: "failed", label: "Failed" },
  { key: "multi-attempt", label: "Multi-attempt" }
];
const judgmentCategories = [
  { key: "", label: "All categories" },
  { key: "judgment:Escalation justified", label: "Escalation justified" },
  { key: "judgment:Bounded estimation", label: "Bounded estimation" },
  { key: "judgment:Random tiebreak", label: "Random tiebreak" },
  { key: "judgment:No admissible choice", label: "No admissible choice" }
];

function classifyAction(action) {
  const hasJudged = action.attempts.some((attempt) =>
    attempt.steps.some((step) => step.label === "Judged")
  );
  return hasJudged ? "Judgment" : "Deterministic";
}

function enrichAction(action) {
  const classification = classifyAction(action);
  const allSteps = action.attempts.flatMap((attempt) =>
    attempt.steps.map((step) => ({
      ...step,
      attemptId: attempt.id,
      attemptSummary: attempt.summary
    }))
  );
  return {
    ...action,
    classification,
    attemptCount: action.attempts.length,
    hasApproval: action.attempts.some((attempt) =>
      attempt.steps.some((step) => JSON.stringify(step.evidence || {}).includes("APR-"))
    ),
    hasRevocation: action.attempts.some((attempt) =>
      attempt.steps.some((step) => JSON.stringify(step.evidence || {}).toLowerCase().includes("revocation"))
    ),
    judgmentMethods: allSteps
      .filter((step) => step.label === "Judged")
      .map((step) => step.judgmentMethod),
    judgmentCauses: allSteps
      .filter((step) => step.label === "Judged")
      .map((step) => step.judgmentCause),
    judgedOutcomeSummary: allSteps
      .filter((step) => step.label === "Judged")
      .map((step) => step.result)
  };
}

const enrichedActions = actions.map(enrichAction);

function parseDate(value) {
  return new Date(value);
}

function timeframeStart(timeframe, now = new Date("2026-03-22T12:00:00Z")) {
  if (timeframe === "All") {
    return null;
  }
  const start = new Date(now);
  if (timeframe === "Today") {
    start.setUTCHours(0, 0, 0, 0);
    return start;
  }
  if (timeframe === "Week") {
    start.setUTCDate(start.getUTCDate() - 7);
    return start;
  }
  if (timeframe === "Month") {
    start.setUTCMonth(start.getUTCMonth() - 1);
    return start;
  }
  if (timeframe === "Year") {
    start.setUTCFullYear(start.getUTCFullYear() - 1);
    return start;
  }
  if (timeframe === "Custom") {
    return new Date("2026-03-01T00:00:00Z");
  }
  return null;
}

function filterByTimeframe(items, timeframe) {
  const start = timeframeStart(timeframe);
  if (!start) {
    return items;
  }
  return items.filter((item) => parseDate(item.timestamps.updatedAt) >= start);
}

function countBy(list, selector) {
  return list.reduce((acc, item) => {
    const key = selector(item) || "Unknown";
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

function asPercent(part, total) {
  if (!total) {
    return "0%";
  }
  return `${Math.round((part / total) * 100)}%`;
}

function formatTime(iso) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit"
  });
}

function routeFromHash() {
  const raw = window.location.hash.slice(1) || "/summary";
  const [pathPart, queryPart] = raw.split("?");
  const params = new URLSearchParams(queryPart || "");
  return {
    path: pathPart || "/summary",
    params
  };
}

function navHref(path, nextParams = {}) {
  const route = routeFromHash();
  const params = new URLSearchParams(route.params.toString());
  Object.entries(nextParams).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") {
      params.delete(key);
    } else {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return `#${path}${query ? `?${query}` : ""}`;
}

function globalNav(currentPath) {
  if (currentPath === "/summary") {
    return "";
  }
  return `
    <nav class="nav">
      <a class="${currentPath === "/summary" ? "active" : ""}" href="${navHref("/summary", {
        action: null,
        attempt: null,
        step: null
      })}">Summary</a>
    </nav>
  `;
}

function timeframeControls(selected, path = routeFromHash().path) {
  return `
    <div class="timeframes">
      ${timeframes
        .map(
          (value) => `
            <a class="pill ${selected === value ? "active" : ""}" href="${navHref(path, {
              timeframe: value,
              page: 1
            })}">${value}</a>
          `
        )
        .join("")}
    </div>
  `;
}

function summaryCategorySelect(selectedScope) {
  const scopes = ["All", ...new Set(enrichedActions.map((action) => action.family))];
  return `
    <label class="selector">
      <span>Category</span>
      <select data-nav-key="scope" data-nav-path="/summary">
        ${scopes
          .map((value) => {
            const optionValue = value === "All" ? "" : value;
            const activeValue = selectedScope || "";
            return `<option value="${optionValue}" ${activeValue === optionValue ? "selected" : ""}>${value === "All" ? "All categories" : value}</option>`;
          })
          .join("")}
      </select>
    </label>
  `;
}

function pageCategorySelect(pageType, selectedCategory) {
  const options = pageType === "Judgment" ? judgmentCategories : deterministicCategories;
  return `
    <label class="selector">
      <span>Category</span>
      <select data-nav-key="category" data-nav-path="${pageType === "Judgment" ? "/judgment" : "/deterministic"}">
        ${options
          .map(
            (option) => `
              <option value="${option.key}" ${selectedCategory === option.key ? "selected" : ""}>${option.label}</option>
            `
          )
          .join("")}
      </select>
    </label>
  `;
}

function emptyState(title, body) {
  return `<div class="empty"><h3>${title}</h3><p class="muted">${body}</p></div>`;
}

function getContext() {
  const { path, params } = routeFromHash();
  return {
    path,
    params,
    timeframe: params.get("timeframe") || "All",
    parent: params.get("parent") || "",
    category: params.get("category") || "",
    scope: params.get("scope") || "",
    sort: params.get("sort") || "newest",
    page: Number(params.get("page") || "1"),
    actionId: params.get("action") || "",
    attemptId: params.get("attempt") || "",
    stepId: params.get("step") || ""
  };
}

function getActionsForCurrentScope() {
  const context = getContext();
  let filtered = filterByTimeframe(enrichedActions, context.timeframe);
  if (context.scope) {
    filtered = filtered.filter((action) => action.family === context.scope);
  }
  return filtered;
}

function renderSummary() {
  const context = getContext();
  const actionsForView = getActionsForCurrentScope();
  const deterministic = actionsForView.filter((action) => action.classification === "Deterministic");
  const judgment = actionsForView.filter((action) => action.classification === "Judgment");

  return `
    <section class="page">
      ${
        actionsForView.length
          ? `
            <div class="summary-band summary-band--simple">
              <a class="summary-link deterministic-block" href="${navHref("/deterministic", {
                timeframe: context.timeframe,
                parent: "summary",
                category: null,
                action: null,
                attempt: null,
                step: null
              })}">
                <span class="eyebrow">Deterministic</span>
                <small>No Judgment</small>
                <strong>${deterministic.length}</strong>
                <span>${asPercent(deterministic.length, actionsForView.length)} of governed actions</span>
              </a>
              <a class="summary-link judgment-block" href="${navHref("/judgment", {
                timeframe: context.timeframe,
                parent: "summary",
                category: null,
                action: null,
                attempt: null,
                step: null
              })}">
                <span class="eyebrow">Judgment</span>
                <small>Required</small>
                <strong>${judgment.length}</strong>
                <span>${asPercent(judgment.length, actionsForView.length)} of governed actions</span>
              </a>
            </div>
            <div class="card selector-row summary-selector-row">
              <div class="selector-row__group">
                ${timeframeControls(context.timeframe, "/summary")}
              </div>
              <div class="selector-row__group">
                ${summaryCategorySelect(context.scope)}
                <a class="button audit-button" href="${navHref("/audit", {
                  timeframe: context.timeframe,
                  scope: context.scope || null
                })}">Audit</a>
              </div>
            </div>
          `
          : emptyState(
              "No governed actions in this slice",
              "The selected timeframe and category currently return no actions."
            )
      }
    </section>
  `;
}

function filterByCategory(actionsForView, category) {
  if (!category) {
    return actionsForView;
  }
  const [kind, value] = category.includes(":") ? category.split(":") : [category, ""];
  if (kind === "completed") {
    return actionsForView.filter((action) => action.disposition === "completed");
  }
  if (kind === "failed") {
    return actionsForView.filter((action) => action.disposition === "failed" || action.disposition === "denied");
  }
  if (kind === "multi-attempt") {
    return actionsForView.filter((action) => action.attemptCount > 1);
  }
  if (kind === "judgment") {
    return actionsForView.filter((action) => action.judgmentCategory === value);
  }
  if (kind === "family") {
    return actionsForView.filter((action) => action.family === value);
  }
  return actionsForView;
}

function sortActions(actionsForView, sort) {
  const copy = [...actionsForView];
  if (sort === "oldest") {
    copy.sort((a, b) => parseDate(a.timestamps.updatedAt) - parseDate(b.timestamps.updatedAt));
  } else {
    copy.sort((a, b) => parseDate(b.timestamps.updatedAt) - parseDate(a.timestamps.updatedAt));
  }
  return copy;
}

function summaryItems(pageType, actionsForView) {
  if (pageType === "Deterministic") {
    return [
      { label: "Total deterministic actions", value: actionsForView.length },
      { label: "Completed", value: actionsForView.filter((action) => action.disposition === "completed").length },
      { label: "Failed", value: actionsForView.filter((action) => action.disposition === "failed").length },
      { label: "Multi-attempt", value: actionsForView.filter((action) => action.attemptCount > 1).length }
    ];
  }
  const counts = countBy(actionsForView, (action) => action.judgmentCategory || "Uncategorized");
  return [
    { label: "Total judgment actions", value: actionsForView.length },
    { label: "Escalation justified", value: counts["Escalation justified"] || 0 },
    { label: "Bounded estimation", value: counts["Bounded estimation"] || 0 },
    { label: "Random tiebreak", value: counts["Random tiebreak"] || 0 },
    { label: "No admissible choice", value: counts["No admissible choice"] || 0 }
  ];
}

function renderActionRows(actionsForView, pageType) {
  return actionsForView.length
    ? `
      <div class="list-shell">
        ${actionsForView
          .map(
            (action) => `
              <a class="list-row" href="${navHref("/action", {
                parent: pageType.toLowerCase(),
                action: action.id,
                attempt: null,
                step: null
              })}">
                <div>
                  <div class="title">${action.id} · ${action.title}</div>
                  <div class="meta">${action.family} / ${action.type}</div>
                </div>
                <div>
                  <div class="${action.classification === "Judgment" ? "judgment-tag" : "det-tag"}">${action.classification}</div>
                </div>
                <div>
                  <div>${action.disposition}</div>
                  <div class="meta">${action.governanceResponseSummary}</div>
                </div>
                <div>
                  <div>${action.attemptCount} attempt${action.attemptCount === 1 ? "" : "s"}</div>
                  <div class="meta">${formatTime(action.timestamps.updatedAt)}</div>
                </div>
                <div class="meta">
                  ${action.hasApproval ? "Approval-linked" : "No approval"}
                  <br>
                  ${action.hasRevocation ? "Revocation context" : "No revocation"}
                </div>
              </a>
            `
          )
          .join("")}
      </div>
    `
    : emptyState(
        `No ${pageType.toLowerCase()} actions in this slice`,
        "The selected timeframe/category combination returned no matching actions."
      );
}

function renderClassificationPage(pageType) {
  const context = getContext();
  const pageBase = getActionsForCurrentScope().filter((action) => action.classification === pageType);
  const actionsForView = sortActions(filterByCategory(pageBase, context.category), context.sort);
  const bodyClass = pageType === "Deterministic" ? "det-tag" : "judgment-tag";
  const pageSummary = summaryItems(pageType, pageBase);
  const pageLabel = pageType === "Deterministic" ? "No judgment steps recorded" : "Judgment required in at least one step";

  return `
    <section class="page">
      <div class="card">
        <div class="toolbar">
          <div>
            <span class="eyebrow">${pageType} path</span>
            <h2>${pageType} Actions</h2>
            <p class="muted">${pageLabel}</p>
          </div>
          <div class="control-row">
            <span class="${bodyClass}">${pageType}</span>
            ${
              pageType === "Judgment"
                ? `<a class="button primary" href="${navHref("/approvals", { timeframe: context.timeframe, parent: "judgment" })}">Open Approval List</a>`
                : ""
            }
          </div>
        </div>
      </div>
      ${
        pageBase.length
          ? `
            <div class="stats-grid">
              ${pageSummary
                .map(
                  (item) => `
                    <div class="stat-card">
                      <span class="eyebrow">${item.label}</span>
                      <span class="stat-number">${item.value}</span>
                    </div>
                  `
                )
                .join("")}
            </div>
            <div class="card selector-row">
              <div class="selector-row__group">
                ${timeframeControls(context.timeframe, pageType === "Judgment" ? "/judgment" : "/deterministic")}
              </div>
              <div class="selector-row__group">
                ${pageCategorySelect(pageType, context.category)}
              </div>
            </div>
            <div class="card">
              <h3>${pageType} actions in this slice</h3>
              ${renderActionRows(actionsForView, pageType)}
            </div>
          `
          : emptyState(
              `No ${pageType.toLowerCase()} actions in this timeframe`,
              "The classification page stays explicit when a timeframe yields no matching actions."
            )
      }
    </section>
  `;
}

function renderActionList() {
  const context = getContext();
  const pageType = context.parent === "judgment" ? "Judgment" : "Deterministic";
  return renderClassificationPage(pageType);
}

function flattenSteps(action) {
  return action.attempts.flatMap((attempt) =>
    attempt.steps.map((step) => ({
      ...step,
      attemptId: attempt.id,
      attemptSummary: attempt.summary,
      actionId: action.id
    }))
  );
}

function describeEvidenceMeaning(step, action) {
  const classificationClause =
    action.classification === "Judgment"
      ? "This action is on the Judgment path because at least one step in its lifecycle is Judged."
      : "This action remains on the Deterministic path because every recorded step is Determined.";
  const stepClause =
    step.label === "Judged"
      ? `This evidence block explains why ${step.judgmentMethod || "the judgment method"} produced the current governance response.`
      : "This evidence block shows the deterministic check or execution evidence tied to the current governance response.";
  return `${stepClause} ${classificationClause}`;
}

function renderActionDetail() {
  const context = getContext();
  const action = enrichedActions.find((item) => item.id === context.actionId);
  if (!action) {
    return emptyState("Action not found", "The selected action identifier does not exist in the prototype fixtures.");
  }

  const evidencePages = flattenSteps(action);
  const selectedIndex = evidencePages.findIndex((step) => step.id === context.stepId);
  const currentIndex = selectedIndex >= 0 ? selectedIndex : 0;
  const currentEvidence = evidencePages[currentIndex];
  const previousEvidence = evidencePages[currentIndex - 1];
  const nextEvidence = evidencePages[currentIndex + 1];
  const sourcePath = context.parent ? `/${context.parent}` : "/summary";
  const currentAttempt = action.attempts.find((attempt) => attempt.id === currentEvidence.attemptId);
  const evidenceMeaning = describeEvidenceMeaning(currentEvidence, action);

  return `
    <section class="page">
      <div class="card">
        <div class="detail-head">
          <div>
            <span class="eyebrow">Action Detail</span>
            <h2>${action.id} · ${action.title}</h2>
            <p class="muted">${action.family} / ${action.type}</p>
          </div>
          <div class="${action.classification === "Judgment" ? "judgment-tag" : "det-tag"}">${action.classification}</div>
        </div>
        <div class="detail-summary-grid">
          <div class="detail-summary-card">
            <span class="eyebrow">Current outcome</span>
            <strong>${action.disposition}</strong>
            <p class="muted">${action.governanceResponseSummary}</p>
          </div>
          <div class="detail-summary-card">
            <span class="eyebrow">Inspection slice</span>
            <strong>${sourcePath}</strong>
            <p class="muted">${context.timeframe} · ${context.category || "All categories"}</p>
          </div>
          <div class="detail-summary-card">
            <span class="eyebrow">Evidence position</span>
            <strong>${currentIndex + 1} of ${evidencePages.length}</strong>
            <p class="muted">${currentEvidence.attemptId} · ${currentEvidence.id}</p>
          </div>
          <div class="detail-summary-card">
            <span class="eyebrow">Action scope</span>
            <strong>${action.attemptCount} attempt${action.attemptCount === 1 ? "" : "s"}</strong>
            <p class="muted">Updated ${formatTime(action.timestamps.updatedAt)}</p>
          </div>
        </div>
        <div class="detail-grid detail-grid--context">
          <div class="detail-panel">
            <h4>Action orientation</h4>
            <ul class="kv">
              <li><span>Classification path</span><strong>${action.classification}</strong></li>
              <li><span>Source path</span><strong>${sourcePath}</strong></li>
              <li><span>Timeframe</span><strong>${context.timeframe}</strong></li>
              <li><span>Category</span><strong>${context.category || "All categories"}</strong></li>
            </ul>
          </div>
          <div class="detail-panel">
            <h4>Judgment and approval context</h4>
            <p class="muted">${action.hasApproval ? "Approval context is present in this action." : "No approval context tracked."}</p>
            <p class="muted">${action.judgmentMethods.length ? `Methods used: ${action.judgmentMethods.join(", ")}` : "No judged steps tracked."}</p>
            ${
              action.classification === "Judgment"
                ? `<a class="button" href="${navHref("/approvals", { parent: "action" })}">View Approval List</a>`
                : ""
            }
          </div>
        </div>
      </div>
      <div class="card">
        <div class="detail-head">
          <div>
            <span class="eyebrow">Inline evidence</span>
            <h3>${currentEvidence.id} · ${currentEvidence.attemptId}</h3>
            <p class="muted">Evidence page ${currentIndex + 1} of ${evidencePages.length} · ${formatTime(currentEvidence.timestamp)}</p>
          </div>
          <div class="step-tag ${currentEvidence.label === "Judged" ? "judged" : "determined"}">${currentEvidence.label}</div>
        </div>
        <div class="detail-grid detail-grid--evidence">
          <div class="detail-panel detail-panel--highlight">
            <h4>What this evidence block means</h4>
            <p>${evidenceMeaning}</p>
            <ul class="kv">
              <li><span>Current attempt</span><strong>${currentEvidence.attemptId}</strong></li>
              <li><span>Current step</span><strong>${currentEvidence.id}</strong></li>
              <li><span>Result</span><strong>${currentEvidence.result}</strong></li>
              <li><span>Governance response</span><strong>${currentEvidence.governanceResponse}</strong></li>
            </ul>
          </div>
          <div class="detail-panel">
            <h4>Current step context</h4>
            <p>${currentAttempt ? currentAttempt.summary : "Attempt summary unavailable."}</p>
            <p class="muted">Result: ${currentEvidence.result} · ${currentEvidence.keyChange}</p>
            ${
              currentEvidence.label === "Judged"
                ? `<p class="muted">Judgment method: ${currentEvidence.judgmentMethod} · Cause: ${currentEvidence.judgmentCause || "Not tracked"}</p>`
                : ""
            }
          </div>
          <div class="detail-panel">
            <h4>Evidence</h4>
            <ul class="evidence-list">
              ${Object.entries(currentEvidence.evidence || {})
                .map(([key, value]) => `<li><strong>${key}:</strong> ${Array.isArray(value) ? value.join(", ") : value}</li>`)
                .join("")}
            </ul>
          </div>
        </div>
        <div class="toolbar">
          ${
            previousEvidence
              ? `<a class="pill" href="${navHref("/action", {
                  action: action.id,
                  attempt: previousEvidence.attemptId,
                  step: previousEvidence.id
                })}">Previous Evidence</a>`
              : `<span class="pill">Previous Evidence</span>`
          }
          ${
            nextEvidence
              ? `<a class="pill" href="${navHref("/action", {
                  action: action.id,
                  attempt: nextEvidence.attemptId,
                  step: nextEvidence.id
                })}">Next Evidence</a>`
              : `<span class="pill">Next Evidence</span>`
          }
        </div>
      </div>
      <div class="card">
        <div class="detail-head">
          <div>
            <h3>Attempts and steps</h3>
            <p class="muted">Select any step to update the inline evidence panel without leaving Action Detail.</p>
          </div>
        </div>
        <div class="attempt-list">
          ${action.attempts
            .map(
              (attempt) => `
                <div class="attempt-card">
                  <div class="attempt-head">
                    <div>
                      <strong>${attempt.id}</strong>
                      <div class="muted">${attempt.summary}</div>
                    </div>
                    <div class="muted">${formatTime(attempt.startedAt)} → ${formatTime(attempt.finishedAt)}</div>
                  </div>
                  <div class="step-grid">
                    ${attempt.steps
                      .map(
                        (step) => `
                          <a class="step-card ${step.label === "Judged" ? "judged" : "determined"}" href="${navHref("/action", {
                            action: action.id,
                            parent: context.parent || "",
                            attempt: attempt.id,
                            step: step.id
                          })}">
                            <div class="step-head">
                              <strong>${step.id}</strong>
                              <span class="step-tag ${step.label === "Judged" ? "judged" : "determined"}">${step.label}</span>
                            </div>
                            <p>${step.governanceResponse}</p>
                            <p class="muted">Result: ${step.result} · Evidence present · ${step.keyChange}</p>
                            ${
                              step.label === "Judged"
                                ? `<p class="muted">Method: ${step.judgmentMethod} · Cause: ${step.judgmentCause || "Not tracked"}</p>`
                                : ""
                            }
                          </a>
                        `
                      )
                      .join("")}
                  </div>
                </div>
              `
            )
            .join("")}
        </div>
      </div>
    </section>
  `;
}

function renderStepDetail() {
  const context = getContext();
  const action = enrichedActions.find((item) => item.id === context.actionId);
  if (!action) {
    return emptyState("Action not found", "The selected action identifier does not exist in the prototype fixtures.");
  }
  const steps = flattenSteps(action);
  const index = steps.findIndex((step) => step.id === context.stepId);
  if (index === -1) {
    return emptyState("Step not found", "The selected step identifier does not exist in the prototype fixtures.");
  }
  const step = steps[index];
  const previous = steps[index - 1];
  const next = steps[index + 1];

  return `
    <section class="page">
      <div class="card">
        <div class="detail-head">
          <div>
            <span class="eyebrow">Step Detail</span>
            <h2>${step.id} within ${step.attemptId} / ${action.id}</h2>
            <p class="muted">${action.family} / ${action.type} · ${formatTime(step.timestamp)}</p>
          </div>
          <div class="step-tag ${step.label === "Judged" ? "judged" : "determined"}">${step.label}</div>
        </div>
        <div class="detail-grid">
          <div class="detail-panel">
            <h4>Governance response</h4>
            <ul class="kv">
              <li><span>Response</span><strong>${step.governanceResponse}</strong></li>
              <li><span>Result</span><strong>${step.result}</strong></li>
              <li><span>Key change</span><strong>${step.keyChange}</strong></li>
            </ul>
          </div>
          <div class="detail-panel">
            <h4>Structured evidence</h4>
            <ul class="evidence-list">
              ${Object.entries(step.evidence || {})
                .map(([key, value]) => `<li><strong>${key}:</strong> ${Array.isArray(value) ? value.join(", ") : value}</li>`)
                .join("")}
            </ul>
          </div>
          <div class="detail-panel">
            <h4>Judgment and approval context</h4>
            <p class="muted">${step.label === "Judged" ? `Method: ${step.judgmentMethod}` : "No judgment method for determined steps."}</p>
            <p class="muted">${step.label === "Judged" ? `Cause: ${step.judgmentCause || "Not tracked"}` : "No judgment cause for determined steps."}</p>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="toolbar">
          <a class="button" href="${navHref("/action", { action: action.id })}">Return to Action Detail</a>
          <a class="button" href="${navHref(context.parent === "judgment" ? "/judgment" : "/deterministic", {
            action: null,
            attempt: null,
            step: null
          })}">Return to ${context.parent || "parent"} page</a>
        </div>
        <div class="toolbar">
          ${
            previous
              ? `<a class="pill" href="${navHref("/step", { action: action.id, attempt: previous.attemptId, step: previous.id })}">Previous Step</a>`
              : `<span class="pill">Previous Step</span>`
          }
          ${
            next
              ? `<a class="pill" href="${navHref("/step", { action: action.id, attempt: next.attemptId, step: next.id })}">Next Step</a>`
              : `<span class="pill">Next Step</span>`
          }
        </div>
      </div>
    </section>
  `;
}

function renderApprovals() {
  const context = getContext();
  return `
    <section class="page">
      <div class="card">
        <div class="toolbar">
          <div>
            <span class="eyebrow">Approval List</span>
            <h2>Lightweight approval management surface</h2>
          </div>
          ${
            context.parent
              ? `<a class="button" href="${navHref(context.parent === "judgment" ? "/judgment" : "/summary", {})}">Return to ${context.parent}</a>`
              : ""
          }
        </div>
        <p class="muted">Current-state view only. No forensic approval analysis is introduced here.</p>
      </div>
      <div class="approval-grid">
        ${approvals
          .map((entry) => {
            const related = enrichedActions.find((action) => action.id === entry.originatingActionId);
            return `
              <div class="approval-card">
                <span class="eyebrow">${entry.status === "active" ? "Active approval" : "Revoked approval"}</span>
                <h3>${entry.artifactIdentity}</h3>
                <ul class="kv">
                  <li><span>Family</span><strong>${entry.family}</strong></li>
                  <li><span>Approved by</span><strong>${entry.approvedBy}</strong></li>
                  <li><span>Approved at</span><strong>${formatTime(entry.approvedAt)}</strong></li>
                  <li><span>Status</span><strong>${entry.status}</strong></li>
                </ul>
                <p class="muted">${entry.approvalBasis}</p>
                ${
                  related
                    ? `<p><a class="button" href="${navHref("/action", {
                        parent: "judgment",
                        action: related.id
                      })}">Open ${related.id}</a></p>`
                    : ""
                }
                ${
                  entry.revocationHistory.length
                    ? `
                      <h4>Revocation history</h4>
                      <ul class="history-list">
                        ${entry.revocationHistory
                          .map(
                            (item) => `
                              <li><strong>${formatTime(item.revokedAt)}</strong> · ${item.revokedBy} · ${item.reason}</li>
                            `
                          )
                          .join("")}
                      </ul>
                    `
                    : ""
                }
              </div>
            `;
          })
          .join("")}
      </div>
    </section>
  `;
}

function renderAuditStub() {
  return `
    <section class="page">
      <div class="card">
        <span class="eyebrow">Audit</span>
        <h2>Audit surface reserved</h2>
        <p class="muted">Out of scope for the current operator UI phase. Raw records, forensic inspection, provenance trace, and exports live here later.</p>
      </div>
    </section>
  `;
}

function render() {
  const context = getContext();
  const app = document.querySelector("#app");
  const contentMap = {
    "/summary": renderSummary,
    "/deterministic": () => renderClassificationPage("Deterministic"),
    "/judgment": () => renderClassificationPage("Judgment"),
    "/list": renderActionList,
    "/action": renderActionDetail,
    "/step": renderStepDetail,
    "/approvals": renderApprovals,
    "/audit": renderAuditStub
  };

  const content = (contentMap[context.path] || renderSummary)();
  app.innerHTML = `
    <div class="shell">
      <header class="topbar">
        <div class="brand">
          <h1>Governed Actions</h1>
          ${context.path === "/summary" ? "<p>Select a timeframe, then choose Deterministic or Judgment to review governed actions.</p>" : ""}
        </div>
        ${globalNav(context.path)}
      </header>
      ${content}
    </div>
  `;
}

document.addEventListener("change", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLSelectElement) || !target.dataset.navKey) {
    return;
  }
  const path = target.dataset.navPath || routeFromHash().path;
  window.location.hash = navHref(path, {
    [target.dataset.navKey]: target.value || null,
    page: 1,
    action: null,
    attempt: null,
    step: null
  });
});

window.addEventListener("hashchange", render);

if (!window.location.hash) {
  window.location.hash = "/summary?timeframe=All";
} else {
  render();
}
