/**
 * Licensing window — child window (depth 1).
 * Licensing app spec v1 section 1.
 *
 * Phase 1: window shell, panel bar, internal navigation, overview panel.
 * Phase 2: questionnaire panel with 6-state machine, chain persistence,
 *          and resumability.
 */

import * as api from '../api.js';
import * as licensingApi from '../licensing-api.js';
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
  { id: 'purchase', label: 'Purchase', availableIn: ['personal_registered', 'personal_plus'] },
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

  state.mode = _normalizeMode(res.data);
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
  if (status === 'trial') return 'trial';
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

  // Questionnaire panel always re-renders to pick up fresh chain state
  if (panelId === 'questionnaire') {
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
  } else {
    const phaseMap = {
      'tiers': 3,
      'case-document': 3,
      'register': 4,
      'purchase': 5,
      'management': 5,
    };
    const phase = phaseMap[panelId] || '?';
    el.innerHTML = `
      <div class="lic-placeholder">
        <span class="lic-placeholder-label">${_esc(PANELS.find(p => p.id === panelId)?.label || panelId)}</span>
        <span class="lic-placeholder-note">Panel content coming in Phase ${phase}.</span>
      </div>
    `;
  }

  return el;
}

function _buildOverviewPanel(state) {
  const el = document.createElement('div');
  el.className = 'lic-overview';

  const mode = state.mode;
  if (mode === 'trial') {
    el.innerHTML = `
      <div class="lic-state-card">
        <span class="lic-state-dot" style="background: var(--ok, #22c55e)"></span>
        <span class="lic-state-label">Trial</span>
      </div>
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
    </div>
  `;

  el.querySelector('.lq-view-case').addEventListener('click', () => {
    _switchPanel(appState, 'case-document');
  });

  el.querySelector('.lq-view-tiers').addEventListener('click', () => {
    _switchPanel(appState, 'tiers');
  });
}

// ---------- Previous answers (collapsible) ----------

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
  }
`;
document.head.appendChild(licStyles);
