/**
 * Licensing window — child window (depth 1).
 * Licensing app spec v1 section 1.
 *
 * Phase 1: window shell, panel bar, internal navigation, overview panel.
 * Phase 2: questionnaire panel with 6-state machine, chain persistence,
 *          and resumability.
 * Phase 4: registration panel, trial completion handling, mode transitions.
 */

import * as api from '../api.js';
import * as licensingApi from '../licensing-api.js';
// refreshLicenseState is loaded lazily to break the circular import:
// app.js → main-page.js → licensing.js → app.js
async function _refreshLicenseState() {
  const { refreshLicenseState } = await import('../app.js');
  refreshLicenseState();
}
import { modalManager } from '../modal-manager.js';
import '../components/loading-indicator.js';
import {
  STATES,
  reconstructState,
  computeBaseTier,
  runClimbingProcedure,
  getNextPhaseTwoQuestion,
  countPhaseTwoAnswered,
  countPhaseTwoTotal,
  estimateClimbingTotal,
  isConsequentialChange,
  thresholdReasoning,
  TIER_LABELS,
  TIERS,
  CAPACITY_QUESTIONS,
} from '../questionnaire-engine.js';
import {
  CAPACITY_RANGES,
  COMMERCIAL_TERMS,
  TIER_CAPABILITIES,
  TRANSLATION_TEMPLATES,
  getTemplate,
  getGroupedCapabilities,
} from '../tier-definitions.js';

// ---------- Panel definitions ----------

/**
 * All panels the licensing app can display.
 * `availableIn` lists the licensing modes where the panel appears.
 * Spec v1 section 1.2.
 */
const PANELS = [
  { id: 'overview', label: 'Overview', availableIn: ['trial', 'personal', 'personal_registered', 'personal_plus', 'crew', 'team', 'institution', 'unlicensed', 'clock_anomaly'] },
  { id: 'tiers', label: 'Tiers', availableIn: ['trial', 'personal', 'personal_registered', 'personal_plus', 'crew', 'team', 'institution', 'unlicensed', 'clock_anomaly'] },
  { id: 'questionnaire', label: 'Questionnaire', availableIn: ['trial', 'personal', 'personal_registered', 'unlicensed'] },
  { id: 'case-document', label: 'Case Document', availableIn: ['trial', 'personal', 'personal_registered', 'personal_plus', 'crew', 'team', 'institution', 'unlicensed'] },
  { id: 'register', label: 'Register', availableIn: ['trial', 'personal', 'unlicensed'] },
  { id: 'purchase', label: 'Purchase', availableIn: ['trial', 'personal', 'personal_registered', 'personal_plus', 'crew', 'team', 'unlicensed'] },
  { id: 'management', label: 'License Management', availableIn: ['personal_plus', 'crew', 'team', 'institution'] },
];

// ---------- Public API ----------

/**
 * Open the Licensing window.
 * @param {HTMLElement|null} trigger - the element that triggered the open
 */
export function openLicensingWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Licensing', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    mode: null,       // licensing mode from server
    activePanel: null, // current panel id
    panelEls: {},     // cached panel content elements
    qState: null,     // questionnaire engine state (reconstructed)
  };

  _loadMode(state);
}

// ---------- Window chrome ----------

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) {
    return modalManager.replaceChild({ title, trigger, content });
  }
  return modalManager.open({ title, trigger, content });
}

// ---------- Content shell ----------

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'lic-content';
  el.innerHTML = `
    <nav class="lic-panel-bar" id="lic-panel-bar" role="tablist" aria-label="Licensing panels"></nav>
    <div class="lic-panel-area" id="lic-panel-area">
      <atd-loading-indicator label="Loading licensing state"></atd-loading-indicator>
    </div>
  `;
  return el;
}

// ---------- Mode detection and panel bar ----------

async function _loadMode(state) {
  const res = await api.getLicensingMode();
  if (!res.ok) {
    const area = state.el.querySelector('#lic-panel-area');
    area.innerHTML = `<div class="lic-error">${_esc(res.error)}</div>`;
    return;
  }

  // Store server response for trial extension message access
  state.modeData = res.data;

  // If trial threshold met and not extended, trigger immediate view reversion
  if (res.data.trial_complete && !res.data.trial_extended) {
    // Trial complete — views revert immediately to personal unlicensed
    state.mode = 'personal';
    // Propagate mode transition to chrome + main page
    _refreshLicenseState();
  } else {
    state.mode = _normalizeMode(res.data);
  }

  _renderPanelBar(state);
  _switchPanel(state, 'overview');
}

/**
 * Normalize the server response into a mode string that matches
 * PANELS[].availableIn values.
 */
function _normalizeMode(data) {
  const status = data.license_status || 'trial';
  const tier = data.license_tier || 'personal';

  if (status === 'clock_anomaly') return 'clock_anomaly';
  if (status === 'trial') {
    // Check for trial extension
    if (data.trial_extended) return 'trial';
    return 'trial';
  }
  if (status === 'licensed') return tier; // 'personal_plus', 'crew', 'team', 'institution'
  if (status === 'personal') {
    // Post-trial personal: check if registered
    if (data.registered) return 'personal_registered';
    return 'personal';
  }
  if (status === 'unlicensed') return 'unlicensed';
  return 'trial'; // fallback
}

function _renderPanelBar(state) {
  const bar = state.el.querySelector('#lic-panel-bar');
  bar.innerHTML = '';

  const available = PANELS.filter(p => p.availableIn.includes(state.mode));
  for (const panel of available) {
    const tab = document.createElement('button');
    tab.className = 'lic-tab';
    tab.textContent = panel.label;
    tab.dataset.panelId = panel.id;
    tab.setAttribute('role', 'tab');
    tab.setAttribute('aria-selected', 'false');
    tab.addEventListener('click', () => _switchPanel(state, panel.id));
    bar.appendChild(tab);
  }
}

// ---------- Panel switching ----------

function _switchPanel(state, panelId) {
  // Update tab selection
  const tabs = state.el.querySelectorAll('.lic-tab');
  for (const tab of tabs) {
    const selected = tab.dataset.panelId === panelId;
    tab.classList.toggle('lic-tab-active', selected);
    tab.setAttribute('aria-selected', String(selected));
  }

  // Render or restore panel content
  const area = state.el.querySelector('#lic-panel-area');
  area.innerHTML = '';

  // Panels that read chain data always re-render to pick up fresh state
  if (panelId === 'questionnaire' || panelId === 'case-document' || panelId === 'tiers' || panelId === 'register' || panelId === 'purchase' || panelId === 'management') {
    delete state.panelEls[panelId];
  }

  if (!state.panelEls[panelId]) {
    state.panelEls[panelId] = _buildPanel(panelId, state);
  }
  area.appendChild(state.panelEls[panelId]);
  state.activePanel = panelId;
}

// ---------- Panel content ----------

function _buildPanel(panelId, state) {
  const el = document.createElement('div');
  el.className = 'lic-panel';
  el.dataset.panelId = panelId;

  if (panelId === 'overview') {
    el.appendChild(_buildOverviewPanel(state));
  } else if (panelId === 'questionnaire') {
    el.appendChild(_buildQuestionnairePanel(state));
  } else if (panelId === 'case-document') {
    el.appendChild(_buildCaseDocumentPanel(state));
  } else if (panelId === 'tiers') {
    el.appendChild(_buildTierDisplayPanel(state));
  } else if (panelId === 'register') {
    el.appendChild(_buildRegisterPanel(state));
  } else if (panelId === 'purchase') {
    el.appendChild(_buildPurchasePanel(state));
  } else if (panelId === 'management') {
    el.appendChild(_buildManagementPanel(state));
  } else {
    el.innerHTML = `
      <div class="lic-placeholder">
        <span class="lic-placeholder-label">${_esc(PANELS.find(p => p.id === panelId)?.label || panelId)}</span>
        <span class="lic-placeholder-note">Panel content coming in a future phase.</span>
      </div>
    `;
  }

  return el;
}

function _buildOverviewPanel(state) {
  const el = document.createElement('div');
  el.className = 'lic-overview';

  const mode = state.mode;
  const modeData = state.modeData || {};

  if (mode === 'trial') {
    const extensionMsg = modeData.trial_extended
      ? `<div class="lic-extension-banner">
           Atested has extended your trial to give you more time to evaluate.
         </div>`
      : '';

    el.innerHTML = `
      <div class="lic-state-card">
        <span class="lic-state-dot" style="background: var(--ok, #22c55e)"></span>
        <span class="lic-state-label">Trial</span>
      </div>
      ${extensionMsg}
      <p class="lic-overview-text">
        Trial in progress. Governance decisions are being recorded.
        Complete the questionnaire to receive a tier recommendation.
      </p>
      <div class="lic-overview-actions">
        <button class="lic-action-btn lic-action-primary" data-nav="questionnaire">Start Questionnaire</button>
        <button class="lic-action-btn" data-nav="tiers">View Tier Options</button>
      </div>
    `;
  } else if (mode === 'personal' || mode === 'unlicensed') {
    el.innerHTML = `
      <div class="lic-state-card lic-state-amber">
        <span class="lic-state-dot" style="background: var(--warning, #f59e42)"></span>
        <span class="lic-state-label">Personal (unlicensed)</span>
      </div>
      <p class="lic-overview-text">
        Governance is active and the chain is recording. Views and features
        beyond Personal are inactive until licensing.
      </p>
      <div class="lic-overview-actions">
        <button class="lic-action-btn lic-action-primary" data-nav="register">Register for Personal (free)</button>
        <button class="lic-action-btn" data-nav="tiers">View Tier Options</button>
      </div>
    `;
  } else if (mode === 'personal_registered') {
    el.innerHTML = `
      <div class="lic-state-card">
        <span class="lic-state-dot" style="background: var(--ok, #22c55e)"></span>
        <span class="lic-state-label">Personal</span>
      </div>
      <p class="lic-overview-text">
        Personal license active. Single operator, full governance.
      </p>
      <div class="lic-overview-actions">
        <button class="lic-action-btn" data-nav="tiers">View Tier Options</button>
      </div>
    `;
  } else if (mode === 'personal_plus' || mode === 'crew' || mode === 'team' || mode === 'institution') {
    const label = { personal_plus: 'Personal Plus', crew: 'Crew', team: 'Team', institution: 'Institution' }[mode] || mode;
    el.innerHTML = `
      <div class="lic-state-card">
        <span class="lic-state-dot" style="background: var(--ok, #22c55e)"></span>
        <span class="lic-state-label">${_esc(label)}</span>
      </div>
      <p class="lic-overview-text">
        Licensed. Governance is active.
      </p>
      <div class="lic-overview-actions">
        <button class="lic-action-btn" data-nav="management">Manage License</button>
        <button class="lic-action-btn" data-nav="tiers">View Tier Options</button>
      </div>
    `;
  } else if (mode === 'clock_anomaly') {
    el.innerHTML = `
      <div class="lic-state-card lic-state-amber">
        <span class="lic-state-dot" style="background: var(--danger, #ef4444)"></span>
        <span class="lic-state-label">Clock Anomaly</span>
      </div>
      <p class="lic-overview-text">
        A system clock anomaly was detected. License status is unavailable
        until the clock is corrected. Governance continues in fail-closed mode.
      </p>
    `;
  } else {
    el.innerHTML = `
      <div class="lic-state-card">
        <span class="lic-state-dot" style="background: var(--muted, #8b919a)"></span>
        <span class="lic-state-label">Unknown</span>
      </div>
      <p class="lic-overview-text">Unable to determine licensing state.</p>
    `;
  }

  // Wire nav buttons
  el.querySelectorAll('[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.nav;
      // Only navigate if the panel is available
      const tab = state.el.querySelector(`.lic-tab[data-panel-id="${target}"]`);
      if (tab) _switchPanel(state, target);
    });
  });

  return el;
}

// ==========================================================================
// Questionnaire panel (Phase 2)
// ==========================================================================

function _buildQuestionnairePanel(state) {
  const el = document.createElement('div');
  el.className = 'lic-questionnaire';
  el.innerHTML = `<atd-loading-indicator label="Loading questionnaire"></atd-loading-indicator>`;

  // Load chain state and render
  _loadQuestionnaireState(el, state);
  return el;
}

async function _loadQuestionnaireState(el, appState) {
  const res = await api.getQuestionnaireState();
  if (!res.ok) {
    el.innerHTML = `<div class="lic-error">${_esc(res.error)}</div>`;
    return;
  }

  const qState = reconstructState(res.data);
  appState.qState = qState;
  _renderQuestionnaireState(el, qState, appState);
}

function _renderQuestionnaireState(el, qState, appState) {
  el.innerHTML = '';

  switch (qState.state) {
    case STATES.EMPTY:
      _renderEmpty(el, qState, appState);
      break;
    case STATES.CAPACITY:
      _renderCapacity(el, qState, appState);
      break;
    case STATES.CLIMBING:
      _renderClimbing(el, qState, appState);
      break;
    case STATES.THRESHOLD:
      _renderThreshold(el, qState, appState);
      break;
    case STATES.PHASE_TWO:
      _renderPhaseTwo(el, qState, appState);
      break;
    case STATES.COMPLETE:
      _renderComplete(el, qState, appState);
      break;
  }
}

// ---------- EMPTY state ----------

function _renderEmpty(el, qState, appState) {
  el.innerHTML = `
    <div class="lq-intro">
      <h3 class="lq-heading">Licensing Questionnaire</h3>
      <p class="lq-text">
        This questionnaire determines which Atested tier fits your organization.
        It takes a few minutes and is fully resumable — your answers are saved to
        the governance chain, so you can close the window and return anytime.
      </p>
      <p class="lq-text lq-text-muted">
        You'll start with two quick capacity questions, then we'll test whether
        higher-tier features are relevant to your situation.
      </p>
      <div class="lq-actions">
        <button class="lic-action-btn lic-action-primary lq-start-btn">Begin</button>
      </div>
    </div>
  `;

  el.querySelector('.lq-start-btn').addEventListener('click', () => {
    // Transition to CAPACITY — just re-render with capacity state
    const capacityState = { ...qState, state: STATES.CAPACITY };
    _renderQuestionnaireState(el, capacityState, appState);
  });
}

// ---------- CAPACITY state ----------

function _renderCapacity(el, qState, appState) {
  const userQ = CAPACITY_QUESTIONS[0];
  const machineQ = CAPACITY_QUESTIONS[1];

  // Pre-fill from existing capacity data
  const existingUser = qState.capacity?.user_count || '';
  const existingMachine = qState.capacity?.machine_count || '';

  el.innerHTML = `
    <div class="lq-capacity">
      <h3 class="lq-heading">Organization Size</h3>
      <p class="lq-text lq-text-muted">
        These inputs determine your starting tier based on your organization's scale.
      </p>

      <div class="lq-field">
        <label class="lq-label" for="lq-user-count">${_esc(userQ.label)}</label>
        <input class="lq-input" type="number" id="lq-user-count"
               min="${userQ.min}" placeholder="${_esc(userQ.placeholder)}"
               value="${_esc(String(existingUser))}">
      </div>

      <div class="lq-field lq-machine-field" style="display: none;">
        <label class="lq-label" for="lq-machine-count">${_esc(machineQ.label)}</label>
        <input class="lq-input" type="number" id="lq-machine-count"
               min="${machineQ.min}" placeholder="${_esc(machineQ.placeholder)}"
               value="${_esc(String(existingMachine))}">
      </div>

      <div class="lq-base-tier-result" style="display: none;"></div>

      <div class="lq-actions">
        <button class="lic-action-btn lic-action-primary lq-capacity-next" disabled>Next</button>
      </div>

      <div class="lq-error" style="display: none;"></div>
    </div>
  `;

  const userInput = el.querySelector('#lq-user-count');
  const machineField = el.querySelector('.lq-machine-field');
  const machineInput = el.querySelector('#lq-machine-count');
  const baseTierResult = el.querySelector('.lq-base-tier-result');
  const nextBtn = el.querySelector('.lq-capacity-next');
  const errorEl = el.querySelector('.lq-error');

  function updateVisibility() {
    const userCount = parseInt(userInput.value, 10);
    const showMachine = userCount === 1;
    machineField.style.display = showMachine ? '' : 'none';

    if (!isNaN(userCount) && userCount >= 1) {
      const machineCount = showMachine ? Math.max(1, parseInt(machineInput.value, 10) || 1) : 1;
      if (!showMachine || (!isNaN(machineCount) && machineCount >= 1)) {
        const baseTier = computeBaseTier(userCount, machineCount);
        baseTierResult.style.display = '';
        baseTierResult.innerHTML = `
          <div class="lq-base-tier-card">
            <span class="lq-base-tier-dot"></span>
            Starting point: <strong>${_esc(TIER_LABELS[baseTier])}</strong>
          </div>
        `;
        nextBtn.disabled = false;
      } else {
        baseTierResult.style.display = 'none';
        nextBtn.disabled = true;
      }
    } else {
      baseTierResult.style.display = 'none';
      nextBtn.disabled = true;
    }
  }

  userInput.addEventListener('input', updateVisibility);
  machineInput.addEventListener('input', updateVisibility);

  // Initialize visibility
  updateVisibility();

  nextBtn.addEventListener('click', async () => {
    const userCount = parseInt(userInput.value, 10);
    const machineCount = userCount === 1 ? Math.max(1, parseInt(machineInput.value, 10) || 1) : 1;
    const baseTier = computeBaseTier(userCount, machineCount);

    nextBtn.disabled = true;
    nextBtn.textContent = 'Saving...';
    errorEl.style.display = 'none';

    const res = await api.postCapacityInputs({
      user_count: userCount,
      machine_count: machineCount,
      base_tier: baseTier,
    });

    if (!res.ok) {
      errorEl.textContent = res.error;
      errorEl.style.display = '';
      nextBtn.disabled = false;
      nextBtn.textContent = 'Next';
      return;
    }

    // Reload state from chain and re-render
    await _loadQuestionnaireState(el, appState);
  });
}

// ---------- CLIMBING state ----------

function _renderClimbing(el, qState, appState) {
  const q = qState.nextQuestion;
  if (!q) {
    // No next question — shouldn't happen, but handle gracefully
    el.innerHTML = `<div class="lic-error">No climbing question available.</div>`;
    return;
  }

  const progress = estimateClimbingTotal(qState.baseTier, qState.answers);
  const boundary = qState.currentBoundary;
  const boundaryParts = boundary ? boundary.split('_to_') : [];
  const fromTier = boundaryParts.length === 2 ? boundaryParts[0] : '';
  const toTier = boundaryParts.length === 2 ? boundaryParts[1] : '';

  el.innerHTML = `
    <div class="lq-climbing">
      <div class="lq-progress">
        <span class="lq-progress-text">
          Question ${progress.answered + 1} of approximately ${progress.total + 2}
        </span>
        <span class="lq-progress-boundary">
          Testing ${_esc(TIER_LABELS[fromTier] || fromTier)} → ${_esc(TIER_LABELS[toTier] || toTier)} boundary
        </span>
      </div>

      <div class="lq-question-card">
        <p class="lq-question-text">${_esc(q.text)}</p>
        <p class="lq-question-context">${_esc(q.context)}</p>

        <div class="lq-options">
          ${(q.options || []).map(opt => `
            <button class="lq-option-btn" data-value="${_esc(opt.value)}">${_esc(opt.label)}</button>
          `).join('')}
          <button class="lq-option-btn lq-option-skip" data-value="skip">Skip for now</button>
        </div>
      </div>

      <div class="lq-error" style="display: none;"></div>

      ${_renderPreviousAnswers(qState)}
    </div>
  `;

  // Wire option buttons
  el.querySelectorAll('.lq-option-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const value = btn.dataset.value;
      await _submitClimbingAnswer(el, q, value, qState, appState);
    });
  });
}

async function _submitClimbingAnswer(el, question, value, qState, appState) {
  // Check for consequential change
  if (isConsequentialChange(question.id, value, qState)) {
    const unlocked = await _checkIdentityUnlock(el);
    if (!unlocked) return;
  }

  // Disable all buttons
  el.querySelectorAll('.lq-option-btn').forEach(b => { b.disabled = true; });
  const errorEl = el.querySelector('.lq-error');
  errorEl.style.display = 'none';

  const res = await api.postQuestionnaireAnswer({
    question_id: question.id,
    answer_value: value,
    phase: 1,
    tier_boundary: question.boundary || null,
  });

  if (!res.ok) {
    errorEl.textContent = res.error;
    errorEl.style.display = '';
    el.querySelectorAll('.lq-option-btn').forEach(b => { b.disabled = false; });
    return;
  }

  // Reload from chain and re-render
  await _loadQuestionnaireState(el, appState);
}

// ---------- THRESHOLD state ----------

function _renderThreshold(el, qState, appState) {
  const reasoning = thresholdReasoning(qState);
  const tierLabel = TIER_LABELS[qState.recommendation] || qState.recommendation;

  el.innerHTML = `
    <div class="lq-threshold">
      <div class="lq-recommendation-card">
        <div class="lq-recommendation-badge">Verified Recommendation</div>
        <h3 class="lq-recommendation-tier">${_esc(tierLabel)}</h3>
        <p class="lq-recommendation-summary">
          Based on your answers, <strong>${_esc(tierLabel)}</strong> is the right tier
          for your organization.
        </p>
      </div>

      ${reasoning.whyNotLower ? `
        <div class="lq-reasoning-card">
          <h4 class="lq-reasoning-heading">Why not a lower tier?</h4>
          <p class="lq-reasoning-text">${_esc(reasoning.whyNotLower)}</p>
        </div>
      ` : ''}

      ${reasoning.whyNotHigher ? `
        <div class="lq-reasoning-card">
          <h4 class="lq-reasoning-heading">Why not a higher tier?</h4>
          <p class="lq-reasoning-text">${_esc(reasoning.whyNotHigher)}</p>
        </div>
      ` : ''}

      <div class="lq-threshold-actions">
        <button class="lic-action-btn lic-action-primary lq-see-case">
          See your case document
        </button>
        <button class="lic-action-btn lq-continue-refining">
          Answer more questions to strengthen your case
        </button>
      </div>

      <p class="lq-text lq-text-muted lq-threshold-note">
        Continuing adds detail to your case document but won't change
        this recommendation. You can stop at any time.
      </p>

      <div class="lq-restart-section">
        <button class="lic-action-btn lq-restart-btn">Restart Questionnaire</button>
        <span class="lq-restart-hint">Clears all answers and starts from the beginning.</span>
      </div>
    </div>
  `;

  el.querySelector('.lq-see-case').addEventListener('click', () => {
    _switchPanel(appState, 'case-document');
  });

  el.querySelector('.lq-continue-refining').addEventListener('click', () => {
    // Transition to PHASE_TWO
    const p2State = { ...qState, state: STATES.PHASE_TWO };
    p2State.nextQuestion = getNextPhaseTwoQuestion(qState.recommendation, qState.answers);
    _renderQuestionnaireState(el, p2State, appState);
  });

  el.querySelector('.lq-restart-btn').addEventListener('click', () => {
    _restartQuestionnaire(appState);
  });
}

// ---------- PHASE_TWO state ----------

function _renderPhaseTwo(el, qState, appState) {
  const q = qState.nextQuestion;
  if (!q) {
    // All phase-two questions answered — transition to COMPLETE
    const completeState = { ...qState, state: STATES.COMPLETE };
    _renderQuestionnaireState(el, completeState, appState);
    return;
  }

  const tierLabel = TIER_LABELS[qState.recommendation] || qState.recommendation;

  el.innerHTML = `
    <div class="lq-phase-two">
      <div class="lq-phase-two-header">
        <span class="lq-recommendation-badge lq-recommendation-badge-small">
          Recommendation verified: ${_esc(tierLabel)}
        </span>
        <span class="lq-phase-two-count">
          ${qState.phaseTwoAnswered} of ${qState.phaseTwoTotal} refinement questions answered
        </span>
      </div>

      <div class="lq-question-card">
        <p class="lq-question-text">${_esc(q.text)}</p>
        <p class="lq-question-context">${_esc(q.context)}</p>

        <div class="lq-options">
          ${(q.options || []).map(opt => `
            <button class="lq-option-btn" data-value="${_esc(opt.value)}">${_esc(opt.label)}</button>
          `).join('')}
        </div>
      </div>

      <div class="lq-actions">
        <button class="lic-action-btn lq-stop-refining">Stop Refining</button>
      </div>

      <div class="lq-error" style="display: none;"></div>
    </div>
  `;

  // Wire option buttons
  el.querySelectorAll('.lq-option-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const value = btn.dataset.value;
      el.querySelectorAll('.lq-option-btn').forEach(b => { b.disabled = true; });
      const errorEl = el.querySelector('.lq-error');
      errorEl.style.display = 'none';

      const res = await api.postQuestionnaireAnswer({
        question_id: q.id,
        answer_value: value,
        phase: 2,
        tier_boundary: null,
      });

      if (!res.ok) {
        errorEl.textContent = res.error;
        errorEl.style.display = '';
        el.querySelectorAll('.lq-option-btn').forEach(b => { b.disabled = false; });
        return;
      }

      await _loadQuestionnaireState(el, appState);
    });
  });

  el.querySelector('.lq-stop-refining').addEventListener('click', () => {
    // Return to THRESHOLD view
    const thresholdState = { ...qState, state: STATES.THRESHOLD };
    _renderQuestionnaireState(el, thresholdState, appState);
  });
}

// ---------- COMPLETE state ----------

function _renderComplete(el, qState, appState) {
  const tierLabel = TIER_LABELS[qState.recommendation] || qState.recommendation;

  el.innerHTML = `
    <div class="lq-complete">
      <div class="lq-recommendation-card">
        <div class="lq-recommendation-badge">Verified Recommendation</div>
        <h3 class="lq-recommendation-tier">${_esc(tierLabel)}</h3>
        <p class="lq-recommendation-summary">
          All available questions have been answered. Your recommendation is
          <strong>${_esc(tierLabel)}</strong>.
        </p>
      </div>

      <div class="lq-actions">
        <button class="lic-action-btn lic-action-primary lq-view-case">
          View Case Document
        </button>
        <button class="lic-action-btn lq-view-tiers">
          View Tier Details
        </button>
      </div>

      <div class="lq-restart-section">
        <button class="lic-action-btn lq-restart-btn">
          Restart Questionnaire
        </button>
        <span class="lq-restart-hint">Clears all answers and starts from the beginning.</span>
      </div>
    </div>
  `;

  el.querySelector('.lq-view-case').addEventListener('click', () => {
    _switchPanel(appState, 'case-document');
  });

  el.querySelector('.lq-view-tiers').addEventListener('click', () => {
    _switchPanel(appState, 'tiers');
  });

  el.querySelector('.lq-restart-btn').addEventListener('click', () => {
    _restartQuestionnaire(appState);
  });
}

// ---------- Previous answers (collapsible) ----------

async function _restartQuestionnaire(appState) {
  const res = await api.postQuestionnaireReset();
  if (res.ok) {
    _switchPanel(appState, 'questionnaire');
  } else {
    console.error('Questionnaire reset failed:', res.error);
    // Show error inline — find nearest error element or alert
    const area = appState.el.querySelector('#lic-panel-area');
    if (area) {
      const err = document.createElement('div');
      err.className = 'lic-error';
      err.textContent = `Reset failed: ${res.error || 'Unknown error'}`;
      area.prepend(err);
    }
  }
}

function _renderPreviousAnswers(qState) {
  const entries = Object.entries(qState.answers);
  if (entries.length === 0) return '';

  const rows = entries.map(([qid, val]) =>
    `<div class="lq-prev-row"><span class="lq-prev-qid">${_esc(qid)}</span> <span class="lq-prev-val">${_esc(val)}</span></div>`
  ).join('');

  return `
    <details class="lq-previous">
      <summary class="lq-previous-toggle">Previous answers (${entries.length})</summary>
      <div class="lq-previous-list">${rows}</div>
    </details>
  `;
}

// ==========================================================================
// Registration panel (Phase 4)
// ==========================================================================

function _buildRegisterPanel(state) {
  const el = document.createElement('div');
  el.className = 'lr-panel';

  // 3-step state: 'info' → 'telemetry' → 'confirm'
  let step = 'info';
  const regData = {
    operator_name: '',
    context_note: '',
    telemetry_opted_in: true,
  };

  _renderRegisterStep(el, step, regData, state);
  return el;
}

function _renderRegisterStep(el, step, regData, state) {
  el.innerHTML = '';

  if (step === 'info') {
    el.innerHTML = `
      <div class="lr-step">
        <div class="lr-step-indicator">
          <span class="lr-step-dot lr-step-active"></span>
          <span class="lr-step-dot"></span>
          <span class="lr-step-dot"></span>
        </div>
        <h3 class="lr-heading">Register for Personal</h3>
        <p class="lr-text lr-text-muted">
          Personal licensing is free. Registration creates a license file
          locally and records the event in your governance chain.
        </p>
        <div class="lr-field">
          <label class="lr-label" for="lr-name">Your name or identifier</label>
          <input class="lr-input" id="lr-name" type="text" placeholder="e.g. your name or handle"
                 value="${_esc(regData.operator_name)}" autocomplete="off" />
        </div>
        <div class="lr-field">
          <label class="lr-label" for="lr-context">What are you using Atested for? (optional)</label>
          <input class="lr-input lr-input-wide" id="lr-context" type="text"
                 placeholder="e.g. personal development, side project governance"
                 value="${_esc(regData.context_note)}" autocomplete="off" />
        </div>
        <div class="lr-actions">
          <button class="lic-action-btn lic-action-primary lr-next-btn">Continue</button>
        </div>
        <div class="lr-error" style="display:none"></div>
      </div>
    `;

    const nameInput = el.querySelector('#lr-name');
    const contextInput = el.querySelector('#lr-context');
    const nextBtn = el.querySelector('.lr-next-btn');
    const errorEl = el.querySelector('.lr-error');

    nextBtn.addEventListener('click', () => {
      const name = nameInput.value.trim();
      if (!name) {
        errorEl.textContent = 'Please enter a name or identifier.';
        errorEl.style.display = '';
        nameInput.focus();
        return;
      }
      regData.operator_name = name;
      regData.context_note = contextInput.value.trim();
      _renderRegisterStep(el, 'telemetry', regData, state);
    });

  } else if (step === 'telemetry') {
    const optedClass = regData.telemetry_opted_in ? 'lr-tele-selected' : '';
    const outClass = !regData.telemetry_opted_in ? 'lr-tele-selected' : '';

    el.innerHTML = `
      <div class="lr-step">
        <div class="lr-step-indicator">
          <span class="lr-step-dot lr-step-done"></span>
          <span class="lr-step-dot lr-step-active"></span>
          <span class="lr-step-dot"></span>
        </div>
        <h3 class="lr-heading">Telemetry Exchange</h3>
        <p class="lr-text lr-text-muted">
          Atested offers a reciprocal data exchange. Participating operators
          share anonymous, aggregated usage data and receive shared insights
          and routine notifications in return.
        </p>
        <div class="lr-tele-options">
          <button class="lr-tele-option ${optedClass}" data-choice="in">
            <span class="lr-tele-title">Participate</span>
            <span class="lr-tele-desc">Share anonymous usage data. Receive shared insights, routine notifications, and community data.</span>
          </button>
          <button class="lr-tele-option ${outClass}" data-choice="out">
            <span class="lr-tele-title">Decline</span>
            <span class="lr-tele-desc">No data shared. Security and critical notifications continue regardless. No access to shared community data.</span>
          </button>
        </div>
        <div class="lr-actions">
          <button class="lic-action-btn lr-back-btn">Back</button>
          <button class="lic-action-btn lic-action-primary lr-next-btn">Continue</button>
        </div>
      </div>
    `;

    const options = el.querySelectorAll('.lr-tele-option');
    options.forEach(opt => {
      opt.addEventListener('click', () => {
        regData.telemetry_opted_in = opt.dataset.choice === 'in';
        options.forEach(o => o.classList.toggle('lr-tele-selected', o === opt));
      });
    });

    el.querySelector('.lr-back-btn').addEventListener('click', () => {
      _renderRegisterStep(el, 'info', regData, state);
    });
    el.querySelector('.lr-next-btn').addEventListener('click', () => {
      _renderRegisterStep(el, 'confirm', regData, state);
    });

  } else if (step === 'confirm') {
    const teleLabel = regData.telemetry_opted_in ? 'Participating' : 'Declined';

    el.innerHTML = `
      <div class="lr-step">
        <div class="lr-step-indicator">
          <span class="lr-step-dot lr-step-done"></span>
          <span class="lr-step-dot lr-step-done"></span>
          <span class="lr-step-dot lr-step-active"></span>
        </div>
        <h3 class="lr-heading">Confirm Registration</h3>
        <div class="lr-confirm-card">
          <div class="lr-confirm-row">
            <span class="lr-confirm-label">Tier</span>
            <span class="lr-confirm-value">Personal (free)</span>
          </div>
          <div class="lr-confirm-row">
            <span class="lr-confirm-label">Operator</span>
            <span class="lr-confirm-value">${_esc(regData.operator_name)}</span>
          </div>
          <div class="lr-confirm-row">
            <span class="lr-confirm-label">Telemetry</span>
            <span class="lr-confirm-value">${_esc(teleLabel)}</span>
          </div>
          <div class="lr-confirm-row">
            <span class="lr-confirm-label">Renewal</span>
            <span class="lr-confirm-value">Annual from registration date</span>
          </div>
        </div>
        <p class="lr-text lr-text-muted">
          Governance continues uninterrupted. A license file will be created
          locally and the registration will be recorded in the governance chain.
          Personal tier features remain active.
        </p>
        <div class="lr-actions">
          <button class="lic-action-btn lr-back-btn">Back</button>
          <button class="lic-action-btn lic-action-primary lr-confirm-btn">Register</button>
        </div>
        <div class="lr-error" style="display:none"></div>
      </div>
    `;

    el.querySelector('.lr-back-btn').addEventListener('click', () => {
      _renderRegisterStep(el, 'telemetry', regData, state);
    });

    const confirmBtn = el.querySelector('.lr-confirm-btn');
    const errorEl = el.querySelector('.lr-error');

    confirmBtn.addEventListener('click', async () => {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Registering...';
      errorEl.style.display = 'none';

      const res = await api.postRegister({
        operator_name: regData.operator_name,
        context_note: regData.context_note,
        telemetry_opted_in: regData.telemetry_opted_in,
      });

      if (!res.ok) {
        confirmBtn.disabled = false;
        confirmBtn.textContent = 'Register';
        errorEl.textContent = res.error || 'Registration failed.';
        errorEl.style.display = '';
        return;
      }

      // Registration succeeded — show success and propagate mode change
      _renderRegisterSuccess(el, res.data, state);

      // Propagate mode transitions to chrome + main page
      _refreshLicenseState();
    });
  }
}

function _renderRegisterSuccess(el, data, state) {
  el.innerHTML = `
    <div class="lr-step lr-success">
      <div class="lr-success-badge">Registered</div>
      <h3 class="lr-heading">Personal License Active</h3>
      <p class="lr-text lr-text-muted">
        Registration complete. Your Personal license is active and governance
        continues uninterrupted.
      </p>
      <div class="lr-confirm-card">
        <div class="lr-confirm-row">
          <span class="lr-confirm-label">Status</span>
          <span class="lr-confirm-value" style="color: #22c55e">Personal (registered)</span>
        </div>
        <div class="lr-confirm-row">
          <span class="lr-confirm-label">Expires</span>
          <span class="lr-confirm-value">${_esc((data.license_expiry || '').slice(0, 10))}</span>
        </div>
      </div>
      <div class="lr-actions" style="justify-content: center">
        <button class="lic-action-btn" data-nav="overview">Back to Overview</button>
        <button class="lic-action-btn" data-nav="tiers">View Tier Options</button>
      </div>
    </div>
  `;

  // Update state mode immediately
  state.mode = 'personal_registered';
  state.modeData = { ...state.modeData, registered: true };
  delete state.panelEls['overview'];
  _renderPanelBar(state);

  el.querySelectorAll('[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.nav;
      _switchPanel(state, target);
    });
  });
}

// ==========================================================================
// Purchase panel (Phase 5)
// ==========================================================================

function _buildPurchasePanel(state) {
  const el = document.createElement('div');
  el.className = 'lp-panel';

  const modeData = state.modeData || {};
  const operatorName = modeData.operator_name || '';
  const currentTier = modeData.license_tier || '';
  const currentStatus = modeData.license_status || '';
  const isLicensed = currentStatus === 'licensed';

  // Tier options — all enabled except Institution (contact handoff)
  // Prices and dating come from COMMERCIAL_TERMS (tier-definitions.js) — single source of truth.
  const TIERS_FOR_PURCHASE = ['personal_plus', 'crew', 'team', 'institution'].map(id => ({
    id,
    label: TIER_LABELS[id] || id,
    price: COMMERCIAL_TERMS[id]?.price || '',
    dating: COMMERCIAL_TERMS[id]?.dating || '',
    selfServe: id !== 'institution',
  }));

  // Filter out tiers at or below current if upgrading
  const TIER_ORDER = ['personal', 'personal_plus', 'crew', 'team', 'institution'];
  const currentIdx = TIER_ORDER.indexOf(currentTier);

  let selectedTier = isLicensed
    ? (TIERS_FOR_PURCHASE.find(t => TIER_ORDER.indexOf(t.id) > currentIdx) || TIERS_FOR_PURCHASE[0]).id
    : 'personal_plus';

  const heading = isLicensed ? 'Upgrade License' : 'Purchase a License';
  const subtext = isLicensed
    ? `You are currently on ${_tierLabel(currentTier)}. Select a higher tier to upgrade.`
    : 'Select a tier for additional features and support.';

  let tiersHtml = '';
  for (const t of TIERS_FOR_PURCHASE) {
    const tierIdx = TIER_ORDER.indexOf(t.id);
    const belowCurrent = isLicensed && tierIdx <= currentIdx;
    const selected = t.id === selectedTier ? 'lp-tier-selected' : '';
    const disabled = belowCurrent ? 'lp-tier-disabled' : '';
    const tag = belowCurrent ? '<span class="lp-future-tag">Current or lower</span>'
      : !t.selfServe ? '<span class="lp-future-tag">Contact us</span>' : '';
    tiersHtml += `
      <button class="lp-tier-option ${selected} ${disabled}" data-tier="${t.id}" ${belowCurrent ? 'disabled' : ''}>
        <span class="lp-tier-label">${_esc(t.label)}</span>
        <span class="lp-tier-price">${_esc(t.price)}</span>
        ${tag}
      </button>
    `;
  }

  const selTierDef = TIERS_FOR_PURCHASE.find(t => t.id === selectedTier) || TIERS_FOR_PURCHASE[0];

  el.innerHTML = `
    <h3 class="lp-heading">${_esc(heading)}</h3>
    <p class="lp-text lp-text-muted">${subtext}</p>

    <div class="lp-section">
      <div class="lp-section-label">Select Tier</div>
      <div class="lp-tier-grid">${tiersHtml}</div>
    </div>

    <div class="lp-detail-area">
      <div class="lp-detail-card">
        <div class="lp-detail-row">
          <span class="lp-detail-label">Price</span>
          <span class="lp-detail-value lp-detail-price">${_esc(selTierDef.price)}</span>
        </div>
        <div class="lp-detail-row">
          <span class="lp-detail-label">Billing</span>
          <span class="lp-detail-value">${selTierDef.selfServe ? 'Annual' : 'Negotiated'}</span>
        </div>
        <div class="lp-detail-row">
          <span class="lp-detail-label">License dating</span>
          <span class="lp-detail-value lp-detail-dating">${_esc(selTierDef.dating)}</span>
        </div>
        <div class="lp-detail-row">
          <span class="lp-detail-label">Auto-renewal</span>
          <span class="lp-detail-value">Enabled by default</span>
        </div>
      </div>
      <p class="lp-dating-note lp-dating-note-text"></p>
    </div>

    <div class="lp-institution-contact" style="display:none">
      <div class="lp-institution-card">
        <h4 class="lp-inst-heading">Institution Tier</h4>
        <p class="lp-text lp-text-muted" style="margin:0 0 12px 0">
          Institution licenses are tailored to your organization. Download
          your case document to share with your team, then contact us to
          discuss your needs and receive a custom quote.
        </p>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="lic-action-btn lp-inst-case-btn" data-nav="case-document">View Case Document</button>
          <a href="mailto:hello@atested.com" class="lic-action-btn lic-action-primary" style="text-decoration:none;text-align:center">
            Contact hello@atested.com
          </a>
        </div>
      </div>
    </div>

    <div class="lp-actions lp-purchase-actions">
      <button class="lic-action-btn lic-action-primary lp-purchase-btn">${_purchaseBtnLabel(selectedTier, isLicensed)}</button>
    </div>
    <div class="lp-error" style="display:none"></div>
  `;

  _updateDatingNote(el, selectedTier);

  // Wire institution case doc button
  const instCaseBtn = el.querySelector('.lp-inst-case-btn');
  if (instCaseBtn) {
    instCaseBtn.addEventListener('click', () => _switchPanel(state, 'case-document'));
  }

  // Tier selection interaction
  el.querySelectorAll('.lp-tier-option:not([disabled])').forEach(btn => {
    btn.addEventListener('click', () => {
      el.querySelectorAll('.lp-tier-option').forEach(b => b.classList.remove('lp-tier-selected'));
      btn.classList.add('lp-tier-selected');
      selectedTier = btn.dataset.tier;
      const def = TIERS_FOR_PURCHASE.find(t => t.id === selectedTier) || TIERS_FOR_PURCHASE[0];
      el.querySelector('.lp-detail-price').textContent = def.price;
      el.querySelector('.lp-detail-dating').textContent = def.dating;
      el.querySelector('.lp-purchase-btn').textContent = _purchaseBtnLabel(selectedTier, isLicensed);
      _updateDatingNote(el, selectedTier);

      // Show/hide institution contact vs purchase button
      const isInst = selectedTier === 'institution';
      el.querySelector('.lp-institution-contact').style.display = isInst ? '' : 'none';
      el.querySelector('.lp-purchase-actions').style.display = isInst ? 'none' : '';
    });
  });

  // Purchase button
  const purchaseBtn = el.querySelector('.lp-purchase-btn');
  const errorEl = el.querySelector('.lp-error');

  purchaseBtn.addEventListener('click', async () => {
    if (selectedTier === 'institution') return; // Should not happen

    purchaseBtn.disabled = true;
    purchaseBtn.textContent = 'Processing...';
    errorEl.style.display = 'none';

    // Mock payment via licensing-api
    const payRes = await licensingApi.initiatePurchase({ tier: selectedTier });
    if (!payRes.ok) {
      purchaseBtn.disabled = false;
      purchaseBtn.textContent = _purchaseBtnLabel(selectedTier, isLicensed);
      errorEl.textContent = payRes.error || 'Payment failed.';
      errorEl.style.display = '';
      return;
    }

    // Submit to dashboard server
    const res = await api.postPurchase({
      tier: selectedTier,
      payment_ref: payRes.data.payment_ref,
      operator_name: operatorName,
    });

    if (!res.ok) {
      purchaseBtn.disabled = false;
      purchaseBtn.textContent = _purchaseBtnLabel(selectedTier, isLicensed);
      errorEl.textContent = res.error || 'Purchase failed.';
      errorEl.style.display = '';
      return;
    }

    // Success — show confirmation and propagate mode change
    _renderPurchaseSuccess(el, res.data, state);
    _refreshLicenseState();
  });

  return el;
}

function _purchaseBtnLabel(tier, isUpgrade) {
  const label = _tierLabel(tier);
  const price = COMMERCIAL_TERMS[tier]?.price || '';
  const verb = isUpgrade ? 'Upgrade to' : 'Purchase';
  const showPrice = price && price !== 'Free' && price !== 'Negotiated';
  return showPrice ? `${verb} ${label} — ${price}` : `${verb} ${label}`;
}

function _updateDatingNote(el, tier) {
  const noteEl = el.querySelector('.lp-dating-note-text');
  if (!noteEl) return;
  if (tier === 'personal_plus') {
    noteEl.textContent = 'Personal Plus dates from purchase. Crew and higher tiers date from trial completion.';
  } else if (tier === 'institution') {
    noteEl.textContent = 'Institution licenses have custom terms negotiated with Atested.';
  } else {
    noteEl.textContent = `${_tierLabel(tier)} dates from trial completion — your 1-year term begins when the trial threshold was met, not when you purchase.`;
  }
}

function _tierLabel(tier) {
  const LABELS = { personal: 'Personal', personal_plus: 'Personal Plus', crew: 'Crew', team: 'Team', institution: 'Institution' };
  return LABELS[tier] || tier;
}

function _renderPurchaseSuccess(el, data, state) {
  const tier = data.tier || 'personal_plus';
  const label = _tierLabel(tier);
  const upgraded = data.upgraded || false;
  const badge = upgraded ? 'Upgraded' : 'Purchased';
  const headline = upgraded
    ? `Upgraded to ${label}`
    : `${label} License Active`;
  const desc = upgraded
    ? `Your license has been upgraded from ${_tierLabel(data.from_tier)} to ${label}.`
    : `Your ${label} license has been activated.`;

  el.innerHTML = `
    <div class="lp-success">
      <div class="lp-success-badge">${_esc(badge)}</div>
      <h3 class="lp-heading">${_esc(headline)}</h3>
      <p class="lp-text lp-text-muted">${_esc(desc)}</p>
      <div class="lp-detail-card">
        <div class="lp-detail-row">
          <span class="lp-detail-label">Tier</span>
          <span class="lp-detail-value" style="color:#22c55e">${_esc(label)}</span>
        </div>
        <div class="lp-detail-row">
          <span class="lp-detail-label">Term Start</span>
          <span class="lp-detail-value">${_esc((data.license_start || '').slice(0, 10))}</span>
        </div>
        <div class="lp-detail-row">
          <span class="lp-detail-label">Term End</span>
          <span class="lp-detail-value">${_esc((data.license_expiry || '').slice(0, 10))}</span>
        </div>
        <div class="lp-detail-row">
          <span class="lp-detail-label">Auto-renewal</span>
          <span class="lp-detail-value">Enabled</span>
        </div>
      </div>
      <div class="lp-actions" style="justify-content:center">
        <button class="lic-action-btn" data-nav="overview">Back to Overview</button>
        <button class="lic-action-btn" data-nav="management">Manage License</button>
      </div>
    </div>
  `;

  // Update state to the purchased tier mode
  state.mode = tier;
  state.modeData = { ...state.modeData, license_status: 'licensed', license_tier: tier };
  delete state.panelEls['overview'];
  _renderPanelBar(state);

  el.querySelectorAll('[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => _switchPanel(state, btn.dataset.nav));
  });
}

// ==========================================================================
// License Management panel (Phase 5)
// ==========================================================================

function _buildManagementPanel(state) {
  const el = document.createElement('div');
  el.className = 'lm-panel';
  el.innerHTML = '<atd-loading-indicator label="Loading license details"></atd-loading-indicator>';
  _loadManagementData(el, state);
  return el;
}

async function _loadManagementData(el, state) {
  const res = await api.getLicensingMode();
  if (!res.ok) {
    el.innerHTML = `<div class="lic-error">${_esc(res.error)}</div>`;
    return;
  }

  const data = res.data;
  const tier = data.license_tier || '';
  const tierLabel = _tierLabel(tier);
  const purchaseDate = (data.purchase_date || '').slice(0, 10) || 'N/A';
  const expiryDate = (data.license_expiry || '').slice(0, 10) || 'N/A';
  const autoRenewal = data.auto_renewal !== false;
  const pendingDowngrade = data.pending_downgrade || null;

  // Tiers the user can downgrade to
  const TIER_ORDER = ['personal', 'personal_plus', 'crew', 'team', 'institution'];
  const currentIdx = TIER_ORDER.indexOf(tier);
  const downgradeTiers = TIER_ORDER.slice(0, Math.max(0, currentIdx)).filter(t => t !== 'personal');

  let pendingHtml = '';
  if (pendingDowngrade) {
    pendingHtml = `
      <div class="lm-section">
        <div class="lm-section-label">Pending Downgrade</div>
        <div class="lm-pending-card">
          <div class="lm-pending-text">
            Downgrade to <strong>${_esc(_tierLabel(pendingDowngrade.to_tier))}</strong>
            scheduled for <strong>${_esc((pendingDowngrade.effective_date || '').slice(0, 10))}</strong>
            (next renewal).
          </div>
          <button class="lic-action-btn lm-cancel-downgrade">Cancel Downgrade</button>
        </div>
      </div>
    `;
  }

  let downgradeHtml = '';
  if (downgradeTiers.length > 0 && !pendingDowngrade) {
    let downgradeOptions = '';
    for (const dt of downgradeTiers) {
      downgradeOptions += `<option value="${dt}">${_tierLabel(dt)}</option>`;
    }
    downgradeHtml = `
      <div class="lm-section">
        <div class="lm-section-label">Downgrade</div>
        <div class="lm-downgrade-card">
          <p class="lm-downgrade-text">
            Schedule a downgrade for your next renewal. You keep your current tier until then.
          </p>
          <div class="lm-downgrade-row">
            <select class="lm-downgrade-select">${downgradeOptions}</select>
            <button class="lic-action-btn lm-downgrade-btn">Schedule Downgrade</button>
          </div>
        </div>
      </div>
    `;
  }

  el.innerHTML = `
    <h3 class="lm-heading">License Management</h3>
    <div class="lm-status-card">
      <div class="lm-status-row">
        <span class="lm-status-label">Current Tier</span>
        <span class="lm-status-value">${_esc(tierLabel)}</span>
      </div>
      <div class="lm-status-row">
        <span class="lm-status-label">Purchase Date</span>
        <span class="lm-status-value">${_esc(purchaseDate)}</span>
      </div>
      <div class="lm-status-row">
        <span class="lm-status-label">Renewal Date</span>
        <span class="lm-status-value">${_esc(expiryDate)}</span>
      </div>
      <div class="lm-status-row">
        <span class="lm-status-label">License Dating</span>
        <span class="lm-status-value">${tier === 'personal_plus' ? 'From purchase date' : 'From trial completion'}</span>
      </div>
    </div>

    ${pendingHtml}

    <div class="lm-section">
      <div class="lm-section-label">Auto-Renewal</div>
      <div class="lm-renewal-card">
        <div class="lm-renewal-status">
          <span class="lm-renewal-dot" style="background: ${autoRenewal ? '#22c55e' : '#f59e42'}"></span>
          <span class="lm-renewal-text">${autoRenewal ? 'Enabled — your license will renew automatically on ' + _esc(expiryDate) : 'Disabled — your license will expire on ' + _esc(expiryDate) + ' and revert to Personal'}</span>
        </div>
        <button class="lic-action-btn lm-renewal-toggle">${autoRenewal ? 'Turn Off Auto-Renewal' : 'Turn On Auto-Renewal'}</button>
      </div>
    </div>

    <div class="lm-section">
      <div class="lm-section-label">Upgrade</div>
      <div class="lm-upgrade-card">
        <button class="lic-action-btn lic-action-primary lm-upgrade-btn" data-nav="purchase">Upgrade to a Higher Tier</button>
      </div>
    </div>

    ${downgradeHtml}

    <div class="lm-confirm-dialog" style="display:none"></div>
    <div class="lm-error" style="display:none"></div>
  `;

  const confirmArea = el.querySelector('.lm-confirm-dialog');
  const errorEl = el.querySelector('.lm-error');

  // Auto-renewal toggle
  const toggleBtn = el.querySelector('.lm-renewal-toggle');
  toggleBtn.addEventListener('click', () => {
    _showConfirmDialog(confirmArea, errorEl, state, {
      message: autoRenewal
        ? `Auto-renewal will be disabled. Your license will expire on ${expiryDate} and revert to Personal.`
        : `Auto-renewal will be enabled. Your license will renew automatically on ${expiryDate}.`,
      action: () => api.postAutoRenewal({ auto_renewal: !autoRenewal }),
      panel: 'management',
    });
  });

  // Upgrade button
  el.querySelector('.lm-upgrade-btn').addEventListener('click', () => {
    _switchPanel(state, 'purchase');
  });

  // Cancel pending downgrade
  const cancelBtn = el.querySelector('.lm-cancel-downgrade');
  if (cancelBtn) {
    cancelBtn.addEventListener('click', () => {
      _showConfirmDialog(confirmArea, errorEl, state, {
        message: `Cancel the pending downgrade to ${_tierLabel(pendingDowngrade.to_tier)}? You will remain on ${tierLabel}.`,
        action: () => api.postPurchase({ tier, payment_ref: 'cancel_downgrade', operator_name: data.operator_name || '' }),
        panel: 'management',
      });
    });
  }

  // Downgrade button
  const downgradeBtn = el.querySelector('.lm-downgrade-btn');
  if (downgradeBtn) {
    downgradeBtn.addEventListener('click', () => {
      const selectEl = el.querySelector('.lm-downgrade-select');
      const toTier = selectEl.value;
      _showConfirmDialog(confirmArea, errorEl, state, {
        message: `Schedule downgrade from ${tierLabel} to ${_tierLabel(toTier)}? ` +
          `You keep ${tierLabel} until your renewal date (${expiryDate}), then switch to ${_tierLabel(toTier)}.`,
        action: () => api.postDowngrade({ to_tier: toTier }),
        panel: 'management',
      });
    });
  }
}

function _showConfirmDialog(confirmArea, errorEl, state, { message, action, panel }) {
  confirmArea.style.display = '';
  confirmArea.innerHTML = `
    <div class="lm-confirm-card">
      <p class="lm-confirm-text">${_esc(message)}</p>
      <div class="lm-confirm-actions">
        <button class="lic-action-btn lm-confirm-cancel">Cancel</button>
        <button class="lic-action-btn lic-action-primary lm-confirm-ok">Confirm</button>
      </div>
    </div>
  `;

  // Focus the cancel button so keyboard users land in the dialog
  const cancelBtn = confirmArea.querySelector('.lm-confirm-cancel');
  cancelBtn.focus();

  cancelBtn.addEventListener('click', () => {
    confirmArea.style.display = 'none';
  });

  confirmArea.querySelector('.lm-confirm-ok').addEventListener('click', async () => {
    const okBtn = confirmArea.querySelector('.lm-confirm-ok');
    okBtn.disabled = true;
    okBtn.textContent = 'Saving...';
    errorEl.style.display = 'none';

    const res = await action();
    if (!res.ok) {
      okBtn.disabled = false;
      okBtn.textContent = 'Confirm';
      errorEl.textContent = res.error || 'Operation failed.';
      errorEl.style.display = '';
      return;
    }

    delete state.panelEls[panel];
    _switchPanel(state, panel);
  });
}

// ==========================================================================
// Case document panel (Phase 3)
// ==========================================================================

function _buildCaseDocumentPanel(state) {
  const el = document.createElement('div');
  el.className = 'lcd-panel';
  el.innerHTML = `<atd-loading-indicator label="Assembling case document"></atd-loading-indicator>`;
  _loadCaseDocument(el, state);
  return el;
}

async function _loadCaseDocument(el, appState) {
  const res = await api.getCaseDocument();
  if (!res.ok) {
    el.innerHTML = `<div class="lic-error">${_esc(res.error)}</div>`;
    return;
  }

  const doc = res.data.document;
  if (!doc) {
    el.innerHTML = `<div class="lic-error">No case document data available.</div>`;
    return;
  }

  // Commercial terms come from the client-side single source of truth,
  // not from the server response. This ensures price changes propagate
  // from tier-definitions.js without needing server updates.
  if (doc.recommendation && COMMERCIAL_TERMS[doc.recommendation]) {
    doc.commercial_terms = COMMERCIAL_TERMS[doc.recommendation];
  }

  _renderCaseDocument(el, doc, appState);
}

function _renderCaseDocument(el, doc, appState) {
  const isTentative = doc.recommendation_status === 'tentative';
  const hasRecommendation = !!doc.recommendation;
  const tierLabel = doc.recommendation_label || doc.recommendation || 'None';
  const ev = doc.governance_evidence || {};

  el.innerHTML = `
    <div class="lcd-document">
      <!-- Header -->
      <div class="lcd-header">
        <h3 class="lcd-title">Case Document</h3>
        <span class="lcd-timestamp">Generated ${_esc(doc.generated_at || '')}</span>
      </div>

      ${isTentative && hasRecommendation ? `
        <div class="lcd-tentative-banner">
          This recommendation is tentative. Additional questionnaire questions would verify it.
        </div>
      ` : ''}

      ${!hasRecommendation ? `
        <div class="lcd-no-rec">
          <p class="lq-text">No recommendation yet. Complete the questionnaire to receive a tier recommendation.</p>
          <div class="lq-actions">
            <button class="lic-action-btn lic-action-primary" data-nav="questionnaire">Start Questionnaire</button>
          </div>
        </div>
      ` : `
        <!-- Section 1: Recommendation -->
        <div class="lcd-recommendation">
          <div class="lcd-rec-badge">${isTentative ? 'Tentative' : 'Verified'} Recommendation</div>
          <h2 class="lcd-rec-tier">${_esc(tierLabel)}</h2>
          <p class="lcd-rec-summary">${_esc(doc.recommendation_section?.summary || '')}</p>
        </div>

        <!-- Section 2: Governance evidence (live installation data) -->
        <div class="lcd-section lcd-evidence-section">
          <h4 class="lcd-section-heading">Evidence from Your Installation</h4>
          ${ev.as_of ? `<p class="lcd-evidence-as-of">As of ${_esc(ev.as_of.replace('T', ' ').replace('Z', ' UTC'))}</p>` : ''}
          <div class="lcd-evidence-grid">
            <div class="lcd-evidence-stat">
              <span class="lcd-ev-number">${ev.total_decisions || 0}</span>
              <span class="lcd-ev-label">Total Decisions</span>
            </div>
            <div class="lcd-evidence-stat">
              <span class="lcd-ev-number lcd-ev-allow">${ev.allow_count || 0}</span>
              <span class="lcd-ev-label">ALLOW</span>
            </div>
            <div class="lcd-evidence-stat">
              <span class="lcd-ev-number lcd-ev-deny">${ev.deny_count || 0}</span>
              <span class="lcd-ev-label">DENY</span>
            </div>
            <div class="lcd-evidence-stat">
              <span class="lcd-ev-number">${(ev.tool_categories || []).length}</span>
              <span class="lcd-ev-label">Tool Categories</span>
            </div>
          </div>
          ${ev.first_decision && ev.last_decision ? `
            <p class="lcd-evidence-timeline">Activity: ${_esc(ev.first_decision.slice(0, 10))} to ${_esc(ev.last_decision.slice(0, 10))}</p>
          ` : ''}
        </div>

        <!-- Section 3: Why not lower -->
        ${doc.why_not_lower ? `
          <div class="lcd-section">
            <h4 class="lcd-section-heading">Why not a lower tier?</h4>
            <p class="lcd-section-text">${_esc(doc.why_not_lower)}</p>
          </div>
        ` : ''}

        <!-- Section 4: Why not higher -->
        ${doc.why_not_higher ? `
          <div class="lcd-section">
            <h4 class="lcd-section-heading">Why not a higher tier?</h4>
            <p class="lcd-section-text">${_esc(doc.why_not_higher)}</p>
          </div>
        ` : ''}

        <!-- Section 5: Features -->
        <div class="lcd-section">
          <h4 class="lcd-section-heading">Features at ${_esc(tierLabel)}</h4>
          <div class="lcd-features">
            ${(doc.feature_ids || []).map(fid => {
              const t = getTemplate(fid);
              return `
                <div class="lcd-feature">
                  <span class="lcd-feature-name">${_esc(t.name)}</span>
                  <span class="lcd-feature-desc">${_esc(t.description)}</span>
                </div>
              `;
            }).join('')}
          </div>
        </div>

        <!-- Section 6: Commercial terms -->
        ${doc.commercial_terms ? `
          <div class="lcd-section">
            <h4 class="lcd-section-heading">Commercial Terms</h4>
            <div class="lcd-terms-grid">
              <div class="lcd-term"><span class="lcd-term-label">Price</span><span class="lcd-term-value">${_esc(doc.commercial_terms.price || '')}</span></div>
              <div class="lcd-term"><span class="lcd-term-label">Billing</span><span class="lcd-term-value">${_esc(doc.commercial_terms.billing || '')}</span></div>
              <div class="lcd-term"><span class="lcd-term-label">Support</span><span class="lcd-term-value">${_esc(doc.commercial_terms.support || '')}</span></div>
              <div class="lcd-term"><span class="lcd-term-label">License Dating</span><span class="lcd-term-value">${_esc(doc.commercial_terms.dating || '')}</span></div>
            </div>
            <p class="lcd-terms-summary">${_esc(doc.commercial_terms.summary || '')}</p>
          </div>
        ` : ''}

        <!-- Section 7: Actions -->
        <div class="lcd-actions">
          <button class="lic-action-btn lic-action-primary lcd-download-btn">Download Case Document</button>
          <button class="lic-action-btn" data-nav="tiers">View Tier Details</button>
          <button class="lic-action-btn lq-restart-btn lcd-restart-btn">Restart Questionnaire</button>
        </div>
      `}
    </div>
  `;

  // Wire nav buttons
  el.querySelectorAll('[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.nav;
      const tab = appState.el.querySelector(`.lic-tab[data-panel-id="${target}"]`);
      if (tab) _switchPanel(appState, target);
    });
  });

  // Wire download button
  const dlBtn = el.querySelector('.lcd-download-btn');
  if (dlBtn) {
    dlBtn.addEventListener('click', () => _downloadCaseDocument(doc));
  }

  // Wire restart questionnaire button
  const rstBtn = el.querySelector('.lcd-restart-btn');
  if (rstBtn) {
    rstBtn.addEventListener('click', () => _restartQuestionnaire(appState));
  }
}

function _downloadCaseDocument(doc) {
  const tierLabel = doc.recommendation_label || doc.recommendation || 'Unknown';
  const isTentative = doc.recommendation_status === 'tentative';
  const ev = doc.governance_evidence || {};
  const terms = (doc.recommendation && COMMERCIAL_TERMS[doc.recommendation]) || doc.commercial_terms || {};

  let md = `# Atested Case Document\n\n`;
  md += `Generated: ${doc.generated_at || 'N/A'}\n\n`;

  if (isTentative) {
    md += `> **Note:** This recommendation is tentative. Additional questionnaire questions would verify it.\n\n`;
  }

  md += `## Recommendation: ${tierLabel}\n\n`;
  md += `Status: ${isTentative ? 'Tentative' : 'Verified'}\n\n`;
  md += `${doc.recommendation_section?.summary || ''}\n\n`;

  md += `### Evidence from Your Installation\n\n`;
  if (ev.as_of) md += `As of ${ev.as_of.replace('T', ' ').replace('Z', ' UTC')}\n\n`;
  md += `- Total decisions: ${ev.total_decisions || 0}\n`;
  md += `- ALLOW: ${ev.allow_count || 0}\n`;
  md += `- DENY: ${ev.deny_count || 0}\n`;
  md += `- Tool categories: ${(ev.tool_categories || []).join(', ') || 'None'}\n`;
  if (ev.first_decision && ev.last_decision) {
    md += `- Activity period: ${ev.first_decision.slice(0, 10)} to ${ev.last_decision.slice(0, 10)}\n`;
  }
  md += `\n`;

  if (doc.why_not_lower) {
    md += `### Why not a lower tier?\n\n${doc.why_not_lower}\n\n`;
  }
  if (doc.why_not_higher) {
    md += `### Why not a higher tier?\n\n${doc.why_not_higher}\n\n`;
  }

  md += `### Features at ${tierLabel}\n\n`;
  for (const fid of (doc.feature_ids || [])) {
    const t = getTemplate(fid);
    md += `- **${t.name}**: ${t.description}\n`;
  }
  md += `\n`;

  md += `### Commercial Terms\n\n`;
  md += `| Term | Value |\n|---|---|\n`;
  md += `| Price | ${terms.price || 'N/A'} |\n`;
  md += `| Billing | ${terms.billing || 'N/A'} |\n`;
  md += `| Support | ${terms.support || 'N/A'} |\n`;
  md += `| License Dating | ${terms.dating || 'N/A'} |\n\n`;
  if (terms.summary) md += `${terms.summary}\n\n`;
  md += `\n---\n\n*Generated by Atested. This document contains rendered text only — no raw chain data.*\n`;

  // Trigger download
  const blob = new Blob([md], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `atested-case-document-${(doc.generated_at || '').slice(0, 10) || 'draft'}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// ==========================================================================
// Tier display panel (Phase 3)
// ==========================================================================

function _buildTierDisplayPanel(state) {
  const el = document.createElement('div');
  el.className = 'ltd-panel';
  el.innerHTML = `<atd-loading-indicator label="Loading tier information"></atd-loading-indicator>`;
  _loadTierDisplay(el, state);
  return el;
}

async function _loadTierDisplay(el, appState) {
  // Fetch questionnaire state for recommendation highlight + fit reasoning
  const qRes = await api.getQuestionnaireState();
  let qState = null;
  if (qRes.ok) {
    qState = reconstructState(qRes.data);
  }

  _renderTierDisplay(el, qState, appState);
}

function _renderTierDisplay(el, qState, appState) {
  const recommendation = qState?.verified ? qState.recommendation : null;
  const tentativeRec = !qState?.verified ? qState?.recommendation : null;
  const licensedTier = _getLicensedTier(appState.mode);

  // Build tier index + sections
  let indexHtml = '';
  let sectionsHtml = '';

  for (const tierId of TIERS) {
    const label = TIER_LABELS[tierId];
    const isLicensed = licensedTier === tierId;
    const isRecommended = recommendation === tierId;
    const isTentative = tentativeRec === tierId;
    const range = CAPACITY_RANGES[tierId];
    const terms = COMMERCIAL_TERMS[tierId];
    const groups = getGroupedCapabilities(tierId);

    // Index entry
    indexHtml += `<button class="ltd-index-item" data-tier="${tierId}">${_esc(label)}</button>`;

    // Badges
    let badges = '';
    if (isLicensed) badges += `<span class="ltd-badge ltd-badge-licensed">Licensed</span>`;
    if (isRecommended) badges += `<span class="ltd-badge ltd-badge-recommended">Recommended</span>`;
    if (isTentative) badges += `<span class="ltd-badge ltd-badge-tentative">Tentative</span>`;

    // Capabilities grouped by category
    let capsHtml = '';
    for (const group of groups) {
      capsHtml += `<div class="ltd-cap-group">`;
      capsHtml += `<div class="ltd-cap-category">${_esc(group.category)}</div>`;
      for (const cap of group.capabilities) {
        capsHtml += `
          <div class="ltd-cap-row">
            <span class="ltd-cap-name">${_esc(cap.name)}</span>
            ${cap.isNew ? `<span class="ltd-cap-new">New at ${_esc(label)}</span>` : ''}
            <span class="ltd-cap-desc">${_esc(cap.description)}</span>
          </div>
        `;
      }
      capsHtml += `</div>`;
    }

    // Fit reasoning (conditional)
    let fitHtml = '';
    if (qState && qState.verified && qState.recommendation) {
      const reasoning = thresholdReasoning(qState);
      if (tierId === qState.recommendation) {
        fitHtml = `<div class="ltd-fit"><div class="ltd-fit-eyebrow">Fit Assessment</div><p class="ltd-fit-text">This tier is the verified recommendation for your organization.</p></div>`;
      } else {
        const recIdx = TIERS.indexOf(qState.recommendation);
        const tierIdx = TIERS.indexOf(tierId);
        if (tierIdx < recIdx && reasoning.whyNotLower) {
          fitHtml = `<div class="ltd-fit"><div class="ltd-fit-eyebrow">Fit Assessment</div><p class="ltd-fit-text">${_esc(reasoning.whyNotLower)}</p></div>`;
        } else if (tierIdx > recIdx && reasoning.whyNotHigher) {
          fitHtml = `<div class="ltd-fit"><div class="ltd-fit-eyebrow">Fit Assessment</div><p class="ltd-fit-text">${_esc(reasoning.whyNotHigher)}</p></div>`;
        }
      }
    }

    // Action button
    let actionHtml = _tierActionButton(tierId, appState.mode, isLicensed, isRecommended);

    sectionsHtml += `
      <div class="ltd-tier-section" id="ltd-tier-${tierId}">
        <div class="ltd-tier-header">
          <h3 class="ltd-tier-name">${_esc(label)}</h3>
          ${badges}
        </div>
        <div class="ltd-tier-range">${_esc(range)}</div>
        <div class="ltd-tier-caps">${capsHtml}</div>
        <div class="ltd-tier-terms">
          <div class="ltd-term-row"><span class="ltd-term-label">Price</span><span class="ltd-term-value">${_esc(terms.price)}</span></div>
          <div class="ltd-term-row"><span class="ltd-term-label">Billing</span><span class="ltd-term-value">${_esc(terms.billing)}</span></div>
          <div class="ltd-term-row"><span class="ltd-term-label">Support</span><span class="ltd-term-value">${_esc(terms.support)}</span></div>
          <div class="ltd-term-row"><span class="ltd-term-label">License Dating</span><span class="ltd-term-value">${_esc(terms.dating)}</span></div>
        </div>
        ${fitHtml}
        ${actionHtml}
      </div>
    `;
  }

  el.innerHTML = `
    <div class="ltd-layout">
      <nav class="ltd-index">${indexHtml}</nav>
      <div class="ltd-sections">${sectionsHtml}</div>
    </div>
  `;

  // Wire index buttons
  el.querySelectorAll('.ltd-index-item').forEach(btn => {
    btn.addEventListener('click', () => {
      const tierId = btn.dataset.tier;
      const section = el.querySelector(`#ltd-tier-${tierId}`);
      if (section) section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  // Highlight active tier on scroll
  const sections = el.querySelector('.ltd-sections');
  if (sections) {
    sections.addEventListener('scroll', () => {
      const tierSections = el.querySelectorAll('.ltd-tier-section');
      let activeId = '';
      for (const sec of tierSections) {
        const rect = sec.getBoundingClientRect();
        const parentRect = sections.getBoundingClientRect();
        if (rect.top <= parentRect.top + 60) activeId = sec.id.replace('ltd-tier-', '');
      }
      el.querySelectorAll('.ltd-index-item').forEach(btn => {
        btn.classList.toggle('ltd-index-active', btn.dataset.tier === activeId);
      });
    });
  }

  // Wire action buttons
  el.querySelectorAll('[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => {
      const target = btn.dataset.nav;
      const tab = appState.el.querySelector(`.lic-tab[data-panel-id="${target}"]`);
      if (tab) _switchPanel(appState, target);
    });
  });
}

function _getLicensedTier(mode) {
  if (mode === 'personal_registered') return 'personal';
  if (['personal_plus', 'crew', 'team', 'institution'].includes(mode)) return mode;
  return null;
}

function _tierActionButton(tierId, mode, isLicensed, isRecommended) {
  if (isLicensed) {
    return `<div class="ltd-tier-action"><button class="lic-action-btn" data-nav="management">Manage License</button></div>`;
  }

  if (mode === 'trial') {
    if (isRecommended) {
      return `<div class="ltd-tier-action"><button class="lic-action-btn lic-action-primary" data-nav="questionnaire">Continue Questionnaire</button></div>`;
    }
    return '';
  }

  if (mode === 'personal' || mode === 'unlicensed') {
    return `<div class="ltd-tier-action"><button class="lic-action-btn" data-nav="register">Register First</button></div>`;
  }

  if (mode === 'personal_registered' && tierId !== 'personal') {
    if (tierId === 'institution') {
      return `<div class="ltd-tier-action"><button class="lic-action-btn" data-nav="purchase">Get Institution Pricing</button></div>`;
    }
    return `<div class="ltd-tier-action"><button class="lic-action-btn lic-action-primary" data-nav="purchase">Purchase ${_esc(TIER_LABELS[tierId])}</button></div>`;
  }

  // Licensed users can upgrade from tier display
  if (['personal_plus', 'crew', 'team'].includes(mode) && tierId !== 'personal') {
    const TIER_ORDER = ['personal', 'personal_plus', 'crew', 'team', 'institution'];
    const modeIdx = TIER_ORDER.indexOf(mode);
    const tierIdx = TIER_ORDER.indexOf(tierId);
    if (tierIdx > modeIdx) {
      if (tierId === 'institution') {
        return `<div class="ltd-tier-action"><button class="lic-action-btn" data-nav="purchase">Get Institution Pricing</button></div>`;
      }
      return `<div class="ltd-tier-action"><button class="lic-action-btn lic-action-primary" data-nav="purchase">Upgrade to ${_esc(TIER_LABELS[tierId])}</button></div>`;
    }
  }

  return '';
}

// ---------- Identity unlock check ----------

/**
 * Check whether the operator identity is configured and unlocked.
 * If configured and locked, prompt for unlock.
 * If not configured, return true (no-op per spec).
 */
async function _checkIdentityUnlock(el) {
  try {
    const res = await api.getIdentitySession();
    if (!res.ok) return true; // Can't check — graceful degradation
    const session = res.data;
    if (!session.configured) return true; // Not configured — no-op
    if (!session.locked) return true; // Already unlocked

    // Show inline unlock message
    const errorEl = el.querySelector('.lq-error');
    if (errorEl) {
      errorEl.textContent = 'This change affects your recommendation. Please unlock your identity to continue.';
      errorEl.style.display = '';
    }
    return false;
  } catch {
    return true; // Network error — graceful degradation
  }
}

// ---------- Helpers ----------

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// ---------- Styles ----------

const licStyles = document.createElement('style');
licStyles.textContent = `
  .lic-content {
    display: flex;
    flex-direction: column;
    height: 100%;
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }
  .lic-panel-bar {
    display: flex;
    gap: 0;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    padding: 0 16px;
    flex-shrink: 0;
  }
  .lic-tab {
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: #8b919a;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 10px 16px;
    transition: color 0.15s, border-color 0.15s;
  }
  .lic-tab:hover {
    color: #e4e6eb;
  }
  .lic-tab:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: -2px;
  }
  .lic-tab-active {
    color: #5b8af5;
    border-bottom-color: #5b8af5;
  }
  .lic-panel-area {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
  }
  .lic-panel {
    min-height: 200px;
  }
  .lic-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    text-align: center;
    gap: 8px;
  }
  .lic-placeholder-label {
    font-size: 1rem;
    font-weight: 600;
    color: #8b919a;
  }
  .lic-placeholder-note {
    font-size: 0.82rem;
    color: #6b7280;
  }
  .lic-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 12px 16px;
    border-radius: 8px;
  }

  /* Overview panel */
  .lic-overview {
    max-width: 600px;
  }
  .lic-state-card {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px 20px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    margin-bottom: 16px;
  }
  .lic-state-card.lic-state-amber {
    border-color: rgba(245, 158, 66, 0.3);
    background: rgba(245, 158, 66, 0.06);
  }
  .lic-state-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .lic-state-label {
    font-size: 1rem;
    font-weight: 600;
  }
  .lic-overview-text {
    font-size: 0.88rem;
    color: #8b919a;
    line-height: 1.6;
    margin: 0 0 20px 0;
  }
  .lic-overview-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .lic-action-btn {
    background: none;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    color: #5b8af5;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 8px 16px;
    transition: background 0.15s, border-color 0.15s;
  }
  .lic-action-btn:hover {
    background: rgba(91, 138, 245, 0.12);
    border-color: #5b8af5;
  }
  .lic-action-btn:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .lic-action-btn.lic-action-primary {
    background: #5b8af5;
    color: #fff;
    border-color: #5b8af5;
  }
  .lic-action-btn.lic-action-primary:hover {
    background: #4a79e4;
  }
  .lic-action-btn:disabled {
    opacity: 0.5;
    cursor: default;
    pointer-events: none;
  }
  .lic-extension-banner {
    background: rgba(91, 138, 245, 0.10);
    border: 1px solid rgba(91, 138, 245, 0.25);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #5b8af5;
    margin-bottom: 8px;
  }

  /* Questionnaire panel */
  .lic-questionnaire {
    max-width: 640px;
  }

  .lq-heading {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0 0 12px 0;
    color: #e4e6eb;
  }
  .lq-text {
    font-size: 0.88rem;
    color: #e4e6eb;
    line-height: 1.6;
    margin: 0 0 12px 0;
  }
  .lq-text-muted {
    color: #8b919a;
  }
  .lq-actions {
    margin-top: 20px;
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .lq-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 8px;
    margin-top: 12px;
  }

  /* Capacity inputs */
  .lq-field {
    margin-bottom: 16px;
  }
  .lq-label {
    display: block;
    font-size: 0.85rem;
    font-weight: 500;
    margin-bottom: 6px;
    color: #e4e6eb;
  }
  .lq-input {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.88rem;
    padding: 8px 12px;
    width: 160px;
    outline: none;
    transition: border-color 0.15s;
  }
  .lq-input:focus {
    border-color: #5b8af5;
  }
  .lq-input::placeholder {
    color: #6b7280;
  }
  .lq-base-tier-card {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: rgba(91, 138, 245, 0.08);
    border: 1px solid rgba(91, 138, 245, 0.2);
    border-radius: 8px;
    font-size: 0.85rem;
    color: #e4e6eb;
    margin-top: 8px;
  }
  .lq-base-tier-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #5b8af5;
    flex-shrink: 0;
  }

  /* Climbing progress */
  .lq-progress {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 4px;
  }
  .lq-progress-text {
    font-size: 0.82rem;
    color: #8b919a;
  }
  .lq-progress-boundary {
    font-size: 0.78rem;
    color: #6b7280;
  }

  /* Question card */
  .lq-question-card {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 16px;
  }
  .lq-question-text {
    font-size: 0.95rem;
    font-weight: 500;
    margin: 0 0 8px 0;
    color: #e4e6eb;
    line-height: 1.5;
  }
  .lq-question-context {
    font-size: 0.82rem;
    color: #8b919a;
    margin: 0 0 16px 0;
    line-height: 1.5;
  }

  /* Answer options */
  .lq-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lq-option-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    color: #e4e6eb;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.85rem;
    font-weight: 500;
    padding: 10px 16px;
    text-align: left;
    transition: background 0.15s, border-color 0.15s;
  }
  .lq-option-btn:hover {
    background: rgba(91, 138, 245, 0.10);
    border-color: #5b8af5;
  }
  .lq-option-btn:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .lq-option-btn:disabled {
    opacity: 0.5;
    cursor: default;
    pointer-events: none;
  }
  .lq-option-skip {
    color: #8b919a;
    border-color: rgba(255, 255, 255, 0.06);
    background: transparent;
    font-weight: 400;
  }

  /* Recommendation card */
  .lq-recommendation-card {
    background: rgba(91, 138, 245, 0.06);
    border: 1px solid rgba(91, 138, 245, 0.2);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
    text-align: center;
  }
  .lq-recommendation-badge {
    display: inline-block;
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    font-size: 0.76rem;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 12px;
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lq-recommendation-badge-small {
    font-size: 0.72rem;
    padding: 3px 10px;
    margin-bottom: 0;
  }
  .lq-recommendation-tier {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: #e4e6eb;
  }
  .lq-recommendation-summary {
    font-size: 0.88rem;
    color: #8b919a;
    margin: 0;
    line-height: 1.6;
  }

  /* Reasoning cards */
  .lq-reasoning-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
  }
  .lq-reasoning-heading {
    font-size: 0.82rem;
    font-weight: 600;
    color: #8b919a;
    margin: 0 0 6px 0;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lq-reasoning-text {
    font-size: 0.85rem;
    color: #e4e6eb;
    margin: 0;
    line-height: 1.5;
  }

  /* Threshold actions */
  .lq-threshold-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 12px;
  }
  .lq-threshold-note {
    font-size: 0.78rem;
  }

  /* Phase two header */
  .lq-phase-two-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    flex-wrap: wrap;
    gap: 8px;
  }
  .lq-phase-two-count {
    font-size: 0.78rem;
    color: #6b7280;
  }

  /* Previous answers */
  .lq-previous {
    margin-top: 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 12px;
  }
  .lq-previous-toggle {
    font-size: 0.78rem;
    color: #6b7280;
    cursor: pointer;
    user-select: none;
  }
  .lq-previous-toggle:hover {
    color: #8b919a;
  }
  .lq-previous-list {
    margin-top: 8px;
  }
  .lq-prev-row {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 0.78rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  }
  .lq-prev-qid {
    color: #6b7280;
    font-family: monospace;
  }
  .lq-prev-val {
    color: #8b919a;
    font-weight: 500;
  }

  /* Complete state */
  .lq-complete {
    text-align: center;
    padding: 20px 0;
  }
  .lq-complete .lq-actions {
    justify-content: center;
  }

  /* ---- Case Document panel ---- */
  .lcd-panel {
    max-width: 720px;
  }
  .lcd-document {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }
  .lcd-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 8px;
  }
  .lcd-title {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0;
    color: #e4e6eb;
  }
  .lcd-timestamp {
    font-size: 0.78rem;
    color: #6b7280;
  }
  .lcd-tentative-banner {
    background: rgba(245, 158, 66, 0.10);
    border: 1px solid rgba(245, 158, 66, 0.3);
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.82rem;
    color: #f59e42;
  }
  .lcd-no-rec {
    font-size: 0.88rem;
    color: #8b919a;
    padding: 20px 0;
    text-align: center;
  }
  .lcd-recommendation {
    text-align: center;
    padding: 24px 20px;
    background: rgba(91, 138, 245, 0.06);
    border: 1px solid rgba(91, 138, 245, 0.2);
    border-radius: 12px;
  }
  .lcd-rec-badge {
    display: inline-block;
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 3px 12px;
    border-radius: 12px;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lcd-rec-tier {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0 0 6px 0;
    color: #e4e6eb;
  }
  .lcd-rec-summary {
    font-size: 0.88rem;
    color: #8b919a;
    margin: 0;
    line-height: 1.6;
  }
  .lcd-section {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
  }
  .lcd-section-heading {
    font-size: 0.85rem;
    font-weight: 600;
    color: #8b919a;
    margin: 0 0 8px 0;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .lcd-section-text {
    font-size: 0.88rem;
    color: #e4e6eb;
    margin: 0;
    line-height: 1.6;
  }
  .lcd-features {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lcd-feature {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .lcd-feature-name {
    font-size: 0.85rem;
    font-weight: 600;
    color: #e4e6eb;
  }
  .lcd-feature-desc {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.5;
  }
  .lcd-terms-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 10px;
  }
  .lcd-term {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .lcd-term-label {
    font-size: 0.76rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lcd-term-value {
    font-size: 0.88rem;
    color: #e4e6eb;
  }
  .lcd-terms-summary {
    font-size: 0.85rem;
    color: #8b919a;
    margin: 0;
    line-height: 1.5;
  }
  .lcd-evidence-section {
    background: rgba(34, 197, 94, 0.04);
    border: 1px solid rgba(34, 197, 94, 0.15);
    border-radius: 8px;
    padding: 14px 16px;
  }
  .lcd-evidence-as-of {
    font-size: 0.78rem;
    color: #6b7280;
    margin: 2px 0 10px 0;
  }
  .lcd-evidence-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin-bottom: 10px;
  }
  .lcd-evidence-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }
  .lcd-ev-number {
    font-size: 1.3rem;
    font-weight: 700;
    color: #e4e6eb;
  }
  .lcd-ev-allow {
    color: #22c55e;
  }
  .lcd-ev-deny {
    color: #f59e42;
  }
  .lcd-ev-label {
    font-size: 0.72rem;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .lcd-evidence-timeline {
    font-size: 0.82rem;
    color: #8b919a;
    margin: 4px 0 0 0;
  }
  .lcd-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  /* ---- Restart questionnaire ---- */
  .lq-restart-section {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
  }
  .lq-restart-hint {
    font-size: 0.82rem;
    color: #8b919a;
  }

  /* ---- Tier Display panel ---- */
  .ltd-panel {
    max-width: 900px;
  }
  .ltd-layout {
    display: flex;
    gap: 20px;
  }
  .ltd-index {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex-shrink: 0;
    width: 140px;
    position: sticky;
    top: 0;
    align-self: flex-start;
  }
  .ltd-index-item {
    background: none;
    border: none;
    border-left: 2px solid transparent;
    color: #8b919a;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 8px 12px;
    text-align: left;
    transition: color 0.15s, border-color 0.15s;
  }
  .ltd-index-item:hover {
    color: #e4e6eb;
  }
  .ltd-index-item:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: -2px;
  }
  .ltd-index-active {
    color: #5b8af5;
    border-left-color: #5b8af5;
  }
  .ltd-sections {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 24px;
    min-width: 0;
  }
  .ltd-tier-section {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 20px 24px;
  }
  .ltd-tier-header {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .ltd-tier-name {
    font-size: 1.05rem;
    font-weight: 600;
    margin: 0;
    color: #e4e6eb;
  }
  .ltd-badge {
    font-size: 0.68rem;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .ltd-badge-licensed {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }
  .ltd-badge-recommended {
    background: rgba(91, 138, 245, 0.15);
    color: #5b8af5;
  }
  .ltd-badge-tentative {
    background: rgba(245, 158, 66, 0.15);
    color: #f59e42;
  }
  .ltd-tier-range {
    font-size: 0.82rem;
    color: #6b7280;
    margin-bottom: 14px;
  }
  .ltd-tier-caps {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 14px;
  }
  .ltd-cap-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .ltd-cap-category {
    font-size: 0.76rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .ltd-cap-row {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 6px;
    padding: 2px 0;
  }
  .ltd-cap-name {
    font-size: 0.85rem;
    font-weight: 600;
    color: #e4e6eb;
  }
  .ltd-cap-new {
    font-size: 0.68rem;
    font-weight: 500;
    color: #5b8af5;
    background: rgba(91, 138, 245, 0.12);
    padding: 1px 6px;
    border-radius: 6px;
  }
  .ltd-cap-desc {
    font-size: 0.82rem;
    color: #8b919a;
    flex-basis: 100%;
    line-height: 1.5;
  }
  .ltd-tier-terms {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 12px;
    padding-top: 12px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
  .ltd-term-row {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }
  .ltd-term-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .ltd-term-value {
    font-size: 0.85rem;
    color: #e4e6eb;
  }
  .ltd-fit {
    background: rgba(91, 138, 245, 0.06);
    border: 1px solid rgba(91, 138, 245, 0.15);
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 12px;
  }
  .ltd-fit-eyebrow {
    font-size: 0.72rem;
    font-weight: 600;
    color: #5b8af5;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
  }
  .ltd-fit-text {
    font-size: 0.85rem;
    color: #e4e6eb;
    margin: 0;
    line-height: 1.5;
  }
  .ltd-tier-action {
    margin-top: 8px;
  }

  /* ---- Registration panel ---- */
  .lr-panel {
    max-width: 560px;
  }
  .lr-step {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .lr-step-indicator {
    display: flex;
    gap: 8px;
  }
  .lr-step-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.12);
  }
  .lr-step-active {
    background: #5b8af5;
  }
  .lr-step-done {
    background: #22c55e;
  }
  .lr-heading {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0;
    color: #e4e6eb;
  }
  .lr-text {
    font-size: 0.88rem;
    color: #e4e6eb;
    line-height: 1.6;
    margin: 0;
  }
  .lr-text-muted {
    color: #8b919a;
  }
  .lr-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .lr-label {
    font-size: 0.85rem;
    font-weight: 500;
    color: #e4e6eb;
  }
  .lr-input {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.88rem;
    padding: 8px 12px;
    width: 260px;
    outline: none;
    transition: border-color 0.15s;
  }
  .lr-input:focus {
    border-color: #5b8af5;
  }
  .lr-input::placeholder {
    color: #6b7280;
  }
  .lr-input-wide {
    width: 100%;
  }
  .lr-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 4px;
  }
  .lr-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 8px;
  }

  /* Telemetry choice */
  .lr-tele-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lr-tele-option {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    color: #e4e6eb;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    padding: 14px 18px;
    text-align: left;
    transition: background 0.15s, border-color 0.15s;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .lr-tele-option:hover {
    background: rgba(91, 138, 245, 0.08);
    border-color: rgba(91, 138, 245, 0.3);
  }
  .lr-tele-option:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .lr-tele-selected {
    background: rgba(91, 138, 245, 0.10);
    border-color: #5b8af5;
  }
  .lr-tele-title {
    font-size: 0.92rem;
    font-weight: 600;
  }
  .lr-tele-desc {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.5;
  }

  /* Confirm card */
  .lr-confirm-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lr-confirm-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.85rem;
  }
  .lr-confirm-label {
    color: #6b7280;
    font-weight: 500;
  }
  .lr-confirm-value {
    color: #e4e6eb;
    font-weight: 600;
  }

  /* Success */
  .lr-success {
    text-align: center;
    align-items: center;
  }
  .lr-success-badge {
    display: inline-block;
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    font-size: 0.76rem;
    font-weight: 600;
    padding: 4px 14px;
    border-radius: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lr-success .lr-confirm-card {
    width: 100%;
    max-width: 320px;
  }

  /* ---- Purchase panel ---- */
  .lp-panel {
    max-width: 600px;
  }
  .lp-heading {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0 0 8px 0;
    color: #e4e6eb;
  }
  .lp-text {
    font-size: 0.88rem;
    color: #e4e6eb;
    line-height: 1.6;
    margin: 0 0 16px 0;
  }
  .lp-text-muted {
    color: #8b919a;
  }
  .lp-section {
    margin-bottom: 20px;
  }
  .lp-section-label {
    font-size: 0.76rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
  }
  .lp-tier-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .lp-tier-option {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 10px;
    color: #e4e6eb;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    padding: 12px 16px;
    text-align: left;
    transition: background 0.15s, border-color 0.15s;
    display: flex;
    flex-direction: column;
    gap: 4px;
    position: relative;
  }
  .lp-tier-option:hover:not([disabled]) {
    background: rgba(91, 138, 245, 0.08);
    border-color: rgba(91, 138, 245, 0.3);
  }
  .lp-tier-option:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .lp-tier-selected {
    background: rgba(91, 138, 245, 0.10);
    border-color: #5b8af5;
  }
  .lp-tier-disabled {
    opacity: 0.45;
    cursor: default;
  }
  .lp-tier-label {
    font-size: 0.88rem;
    font-weight: 600;
  }
  .lp-tier-price {
    font-size: 0.82rem;
    color: #8b919a;
  }
  .lp-future-tag {
    font-size: 0.68rem;
    color: #6b7280;
    font-style: italic;
  }
  .lp-detail-area {
    margin-bottom: 20px;
  }
  .lp-detail-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 10px;
  }
  .lp-detail-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.85rem;
  }
  .lp-detail-label {
    color: #6b7280;
    font-weight: 500;
  }
  .lp-detail-value {
    color: #e4e6eb;
    font-weight: 600;
  }
  .lp-detail-price {
    font-size: 1.1rem;
    color: #5b8af5;
  }
  .lp-dating-note {
    font-size: 0.82rem;
    color: #8b919a;
    margin: 0;
    line-height: 1.5;
  }
  .lp-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .lp-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 8px;
    margin-top: 12px;
  }
  .lp-success {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
  .lp-success-badge {
    display: inline-block;
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    font-size: 0.76rem;
    font-weight: 600;
    padding: 4px 14px;
    border-radius: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lp-success .lp-detail-card {
    width: 100%;
    max-width: 340px;
  }

  /* ---- License Management panel ---- */
  .lm-panel {
    max-width: 600px;
  }
  .lm-heading {
    font-size: 1.1rem;
    font-weight: 600;
    margin: 0 0 16px 0;
    color: #e4e6eb;
  }
  .lm-status-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 24px;
  }
  .lm-status-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.85rem;
  }
  .lm-status-label {
    color: #6b7280;
    font-weight: 500;
  }
  .lm-status-value {
    color: #e4e6eb;
    font-weight: 600;
  }
  .lm-section {
    margin-bottom: 20px;
  }
  .lm-section-label {
    font-size: 0.76rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 10px;
  }
  .lm-renewal-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .lm-renewal-status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    color: #e4e6eb;
  }
  .lm-renewal-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .lm-renewal-text {
    line-height: 1.5;
  }
  .lm-renewal-toggle {
    align-self: flex-start;
  }
  .lm-confirm-card {
    background: rgba(245, 158, 66, 0.06);
    border: 1px solid rgba(245, 158, 66, 0.2);
    border-radius: 10px;
    padding: 16px 20px;
    margin-top: 12px;
  }
  .lm-confirm-text {
    font-size: 0.85rem;
    color: #e4e6eb;
    margin: 0 0 12px 0;
    line-height: 1.5;
  }
  .lm-confirm-actions {
    display: flex;
    gap: 8px;
  }
  .lm-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 8px;
  }
  .lm-upgrade-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
  }
  .lm-pending-card {
    background: rgba(245, 158, 66, 0.06);
    border: 1px solid rgba(245, 158, 66, 0.2);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .lm-pending-text {
    font-size: 0.85rem;
    color: #f59e42;
    line-height: 1.5;
  }
  .lm-downgrade-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
  }
  .lm-downgrade-text {
    font-size: 0.85rem;
    color: #9ca3af;
    margin: 0 0 12px 0;
    line-height: 1.5;
  }
  .lm-downgrade-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .lm-downgrade-select {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    color: #e4e6eb;
    padding: 6px 10px;
    font-size: 0.85rem;
    font-family: "Inter", system-ui, sans-serif;
    min-width: 140px;
    outline: none;
    transition: border-color 0.15s;
  }
  .lm-downgrade-select:focus-visible {
    border-color: #5b8af5;
    outline: 2px solid #5b8af5;
    outline-offset: 1px;
  }
  .lp-institution-card {
    background: rgba(139, 92, 246, 0.06);
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 16px;
  }
  .lp-inst-heading {
    font-size: 0.95rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 0 0 8px 0;
  }

  @media (max-width: 600px) {
    .lic-panel-bar {
      overflow-x: auto;
      padding: 0 8px;
    }
    .lic-tab {
      padding: 8px 10px;
      font-size: 0.76rem;
      white-space: nowrap;
    }
    .lic-panel-area {
      padding: 12px;
    }
    .lcd-evidence-grid {
      grid-template-columns: repeat(2, 1fr);
    }
    .lcd-terms-grid {
      grid-template-columns: 1fr;
    }
    .ltd-layout {
      flex-direction: column;
    }
    .ltd-index {
      flex-direction: row;
      width: auto;
      overflow-x: auto;
      position: static;
    }
    .ltd-index-item {
      border-left: none;
      border-bottom: 2px solid transparent;
      white-space: nowrap;
      padding: 6px 10px;
      font-size: 0.76rem;
    }
    .ltd-index-active {
      border-bottom-color: #5b8af5;
      border-left-color: transparent;
    }
    .ltd-tier-terms {
      grid-template-columns: 1fr;
    }
    .lr-input {
      width: 100%;
    }
    .lp-tier-grid {
      grid-template-columns: 1fr;
    }
    .lm-downgrade-row {
      flex-wrap: wrap;
    }
    .lm-downgrade-select {
      min-width: 120px;
      flex: 1;
    }
    .lm-status-row {
      flex-wrap: wrap;
      gap: 2px;
    }
  }
`;
document.head.appendChild(licStyles);
