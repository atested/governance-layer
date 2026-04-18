/**
 * Licensing window — child window (depth 1).
 * Licensing app spec v1 section 1.
 *
 * Four-box launcher model: Tiers, Survey, Case, Purchase.
 * Each box opens a grandchild (depth 2) window.
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

// ---------- Public API ----------

/**
 * Open the Licensing window.
 * @param {HTMLElement|null} trigger - the element that triggered the open
 */
export function openLicensingWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('', trigger, content);
  if (!result) return;

  const state = {
    el: content,
    mode: null,       // licensing mode from server
    activePanel: null, // current panel id (kept for grandchild compat)
    panelEls: {},     // cached panel content elements
    qState: null,     // questionnaire engine state (reconstructed)
    modeData: null,
    caseData: null,
  };

  _loadLauncherData(state);
}

// ---------- Window chrome ----------

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) {
    return modalManager.replaceChild({ title, trigger, content });
  }
  return modalManager.open({ title, trigger, content });
}

// ---------- Content shell (launcher grid) ----------

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'lic-content';
  el.innerHTML = `
    <div class="ll-status-pane">
      <div class="ll-sp-header">
        <span class="ll-sp-dot"></span>
        <span class="ll-sp-title">License status: <span class="ll-sp-tier">Loading\u2026</span></span>
      </div>
      <div class="ll-sp-intro">Your current license status:</div>
      <div class="ll-sp-grid">
        <div class="ll-sp-row" data-pane="tiers">
          <span class="ll-sp-name">Tiers</span>
          <span class="ll-sp-desc">Loading\u2026</span>
          <span class="ll-sp-state"></span>
        </div>
        <div class="ll-sp-row" data-pane="survey">
          <span class="ll-sp-name">Survey</span>
          <span class="ll-sp-desc">Loading\u2026</span>
          <span class="ll-sp-state"></span>
        </div>
        <div class="ll-sp-row" data-pane="case">
          <span class="ll-sp-name">Case document</span>
          <span class="ll-sp-desc">Loading\u2026</span>
          <span class="ll-sp-state"></span>
        </div>
        <div class="ll-sp-row" data-pane="license">
          <span class="ll-sp-name">License</span>
          <span class="ll-sp-desc">Loading\u2026</span>
          <span class="ll-sp-state"></span>
        </div>
        <div class="ll-sp-row" data-pane="terms">
          <span class="ll-sp-name">Terms</span>
          <span class="ll-sp-desc">Loading\u2026</span>
          <span class="ll-sp-state"></span>
        </div>
      </div>
      <div class="ll-sp-closing">Review the panes below for your next step.</div>
    </div>

    <button class="ll-terms-sliver" data-box="terms">
      <span class="ll-ts-accent"></span>
      <span class="ll-ts-left"><strong>Terms</strong> <span class="ll-ts-desc">Understand the Atested licensing lifecycle</span></span>
      <span class="ll-ts-action">Click to review</span>
    </button>

    <div class="ll-grid">
      <button class="ll-box" data-box="tiers">
        <span class="ll-accent-bar"></span>
        <span class="ll-title">Tiers</span>
        <span class="ll-subtitle">Available plans</span>
        <p class="ll-desc">See what each plan includes and how they compare. Five levels from a solo user to thousands at the largest institutions, with capabilities that scale to your needs.</p>
        <span class="ll-status-line ll-s1"></span>
        <span class="ll-status-line ll-s2"></span>
        <span class="ll-status-line ll-s3"></span>
        <span class="ll-click">Click to compare plans and features</span>
      </button>
      <button class="ll-box" data-box="survey">
        <span class="ll-accent-bar"></span>
        <span class="ll-title">Survey</span>
        <span class="ll-subtitle">Your intended installation</span>
        <p class="ll-desc">Tell us about your planned deployment. We use your responses to help you decide the right plan and to create your case document. The more responses you provide the more accurate our assessment will be.</p>
        <span class="ll-status-line ll-s1"></span>
        <span class="ll-status-line ll-s2"></span>
        <span class="ll-click">Click to find your plan</span>
      </button>
      <button class="ll-box" data-box="case">
        <span class="ll-accent-bar"></span>
        <span class="ll-title">Case document</span>
        <span class="ll-subtitle">Your purchase argument</span>
        <p class="ll-desc">We take your responses to the survey and combine them with the evidence you have generated during your trial to create a document you can use internally to move forward with the project if you choose.</p>
        <span class="ll-status-line ll-s1"></span>
        <span class="ll-status-line ll-s2"></span>
        <span class="ll-click">Click to review and share your case</span>
      </button>
      <button class="ll-box" data-box="purchase">
        <span class="ll-accent-bar"></span>
        <span class="ll-title">License</span>
        <span class="ll-subtitle">Your Atested license</span>
        <p class="ll-desc">Select and purchase your plan. View your current license status, manage renewals, or change your plan as your needs evolve.</p>
        <span class="ll-status-line ll-s1"></span>
        <span class="ll-status-line ll-s2"></span>
        <span class="ll-click">Click to purchase your plan</span>
      </button>
    </div>
  `;
  return el;
}

// ---------- Launcher data loading ----------

async function _loadLauncherData(state) {
  const [modeRes, qRes, caseRes] = await Promise.all([
    api.getLicensingMode(),
    api.getQuestionnaireState(),
    api.getCaseDocument(),
  ]);

  if (!modeRes.ok) {
    state.el.innerHTML = `<div class="lic-error">${_esc(modeRes.error)}</div>`;
    return;
  }

  state.modeData = modeRes.data;
  if (modeRes.data.trial_complete && !modeRes.data.trial_extended) {
    state.mode = 'personal';
    _refreshLicenseState();
  } else {
    state.mode = _normalizeMode(modeRes.data);
  }
  if (qRes.ok) state.qState = reconstructState(qRes.data);
  if (caseRes.ok) state.caseData = caseRes.data;

  _renderLauncher(state);
}

function _normalizeMode(data) {
  const status = data.license_status || 'trial';
  const tier = data.license_tier || 'personal';
  if (status === 'clock_anomaly') return 'clock_anomaly';
  if (status === 'trial') return 'trial';
  if (status === 'licensed') return tier;
  if (status === 'personal') return data.registered ? 'personal_registered' : 'personal';
  if (status === 'unlicensed') return 'unlicensed';
  return 'trial';
}

// ---------- Dynamic action-state color engine ----------

// 'green' = complete/no action. 'amber' = action available or needed.
function _computePaneStates(state) {
  const md = state.modeData || {};
  const q = state.qState;
  const c = state.caseData;
  const isLicensed = md.license_status === 'licensed';
  const hasRec = q && q.recommendation;
  const doc = c?.document;
  const decisions = doc?.governance_evidence?.total_decisions || 0;
  const termsAck = md.terms_acknowledged || false;

  // --- Tiers ---
  const tiersState = hasRec || isLicensed ? 'green' : 'amber';

  // --- Survey ---
  let surveyState = 'amber';
  if (isLicensed) {
    surveyState = 'green';
  } else if (q) {
    if (q.state === STATES.COMPLETE) surveyState = 'green';
    else if (q.state === STATES.THRESHOLD || q.state === STATES.PHASE_TWO) surveyState = 'amber'; // optional refinement
  }

  // --- Case document --- (depends on survey)
  let caseState = 'amber';
  if (isLicensed && doc?.generated_at) {
    caseState = surveyState === 'amber' ? 'amber' : 'green'; // cascading dependency
  } else if (doc?.generated_at && hasRec) {
    caseState = surveyState === 'amber' ? 'amber' : 'green';
    // If survey is amber, case cascades to amber
    if (surveyState === 'green') caseState = 'green';
  }

  // --- License ---
  let licenseState = isLicensed ? 'green' : 'amber';

  // --- Terms ---
  let termsState = termsAck ? 'green' : 'amber';

  return { tiers: tiersState, survey: surveyState, case: caseState, license: licenseState, terms: termsState };
}

function _aggregateState(paneStates) {
  return Object.values(paneStates).every(s => s === 'green') ? 'green' : 'amber';
}

// ---------- Status pane grid content ----------

function _computeGridRows(state, paneStates) {
  const md = state.modeData || {};
  const q = state.qState;
  const c = state.caseData;
  const isLicensed = md.license_status === 'licensed';
  const rec = q?.recommendation ? (TIER_LABELS[q.recommendation] || q.recommendation) : null;
  const price = q?.recommendation ? (COMMERCIAL_TERMS[q.recommendation]?.price || '') : '';
  const doc = c?.document;
  const decisions = doc?.governance_evidence?.total_decisions || 0;
  const licensedTier = md.license_tier || '';
  const termsAck = md.terms_acknowledged || false;
  const p2Extra = q ? (q.phaseTwoTotal - q.phaseTwoAnswered) : 0;

  const rows = {};

  // Tiers
  if (isLicensed) {
    rows.tiers = { desc: `Licensed at ${_tierLabel(licensedTier)}`, label: 'Current' };
  } else if (rec) {
    const cap = q.capacity ? `${q.capacity.user_count} user${q.capacity.user_count !== 1 ? 's' : ''}, ${q.capacity.machine_count || 1} machine${(q.capacity.machine_count || 1) !== 1 ? 's' : ''}` : '';
    rows.tiers = { desc: `${rec} recommended at ${price}${cap ? ' \u2014 ' + cap : ''}`, label: 'Recommended' };
  } else {
    rows.tiers = { desc: 'Five plans from Personal to Institution', label: 'Available' };
  }

  // Survey
  if (isLicensed) {
    rows.survey = { desc: `Complete \u2014 ${rec || _tierLabel(licensedTier)}`, label: 'Complete' };
  } else if (!q || q.state === STATES.EMPTY) {
    rows.survey = { desc: 'Not started', label: 'Pending' };
  } else if (q.state === STATES.CAPACITY || q.state === STATES.CLIMBING) {
    rows.survey = { desc: 'In progress', label: 'Pending' };
  } else if (q.state === STATES.COMPLETE) {
    rows.survey = { desc: `${rec} recommended. All questions answered.`, label: 'Complete' };
  } else if (rec) {
    rows.survey = { desc: `${rec} recommended.${p2Extra > 0 ? ' There is more you can add.' : ''}`, label: p2Extra > 0 ? 'Optional' : 'Complete' };
  } else {
    rows.survey = { desc: 'Not started', label: 'Pending' };
  }

  // Case document
  if (doc?.generated_at) {
    const decStr = decisions > 0 ? `${decisions.toLocaleString()} Atested decisions as evidence` : 'Evidence available';
    rows.case = { desc: `Ready with ${decStr}`, label: 'Ready' };
  } else if (rec) {
    rows.case = { desc: 'Ready to generate', label: 'Available' };
  } else {
    rows.case = { desc: 'Complete the survey first', label: 'Pending' };
  }

  // License
  if (isLicensed) {
    rows.license = { desc: `Licensed at ${_tierLabel(licensedTier)}`, label: 'Active' };
  } else if (md.registered) {
    rows.license = { desc: 'Registered \u2014 Personal (free)', label: 'Registered' };
  } else if (rec) {
    rows.license = { desc: `Not yet licensed. Recommended: ${rec} at ${price}`, label: 'Pending' };
  } else {
    rows.license = { desc: 'Not yet licensed', label: 'Pending' };
  }

  // Terms
  if (termsAck) {
    rows.terms = { desc: 'Reviewed', label: 'Reviewed' };
  } else {
    rows.terms = { desc: 'Not reviewed', label: 'Pending' };
  }

  return rows;
}

function _computeStatusTitle(state) {
  const md = state.modeData || {};
  const isLicensed = md.license_status === 'licensed';
  if (isLicensed) return _tierLabel(md.license_tier || '');
  return 'Trial';
}

// ---------- Box content computation ----------

function _computeBoxContent(state, paneStates) {
  const md = state.modeData || {};
  const q = state.qState;
  const c = state.caseData;
  const isLicensed = md.license_status === 'licensed';
  const rec = q?.recommendation ? (TIER_LABELS[q.recommendation] || q.recommendation) : null;
  const price = q?.recommendation ? (COMMERCIAL_TERMS[q.recommendation]?.price || '') : '';
  const doc = c?.document;
  const decisions = doc?.governance_evidence?.total_decisions || 0;
  const licensedTier = md.license_tier || '';
  const p2Extra = q ? (q.phaseTwoTotal - q.phaseTwoAnswered) : 0;

  const boxes = {};

  // Tiers
  if (isLicensed) {
    const lp = COMMERCIAL_TERMS[licensedTier]?.price || '';
    boxes.tiers = { s1: `Current: ${_tierLabel(licensedTier)}`, s2: lp ? `Price: ${lp}` : '', s3: '', click: 'Click to see what other plans offer' };
  } else if (rec) {
    const cap = q.capacity ? `${q.capacity.user_count} user${q.capacity.user_count !== 1 ? 's' : ''}, ${q.capacity.machine_count || 1} machine${(q.capacity.machine_count || 1) !== 1 ? 's' : ''}` : '';
    boxes.tiers = { s1: `Recommended: ${rec}`, s2: price ? `Price: ${price}` : '', s3: cap, click: 'Click to compare plans and features' };
  } else {
    boxes.tiers = { s1: '', s2: '', s3: '', click: 'Click to compare plans and features' };
  }

  // Survey
  if (isLicensed) {
    boxes.survey = { s1: `Complete \u2014 ${rec || _tierLabel(licensedTier)}`, s2: '', click: 'Click to retake if your situation has changed' };
  } else if (!q || q.state === STATES.EMPTY) {
    boxes.survey = { s1: 'Not started', s2: '', click: 'Click to find your plan' };
  } else if (q.state === STATES.CAPACITY || q.state === STATES.CLIMBING) {
    boxes.survey = { s1: 'In progress', s2: '', click: 'Click to continue your survey' };
  } else if (q.state === STATES.COMPLETE) {
    boxes.survey = { s1: `Complete: ${rec} recommended`, s2: 'All questions answered', click: 'Click to review your answers' };
  } else if (rec) {
    boxes.survey = { s1: `Complete: ${rec} recommended`, s2: p2Extra > 0 ? 'There is more you can add' : '', click: p2Extra > 0 ? 'Click to strengthen your case' : 'Click to review your answers' };
  } else {
    boxes.survey = { s1: 'Not started', s2: '', click: 'Click to find your plan' };
  }

  // Case document
  if (isLicensed && doc?.generated_at) {
    boxes.case = { s1: `${_tierLabel(licensedTier)} \u2014 ${doc.generated_at.slice(0, 10)}`, s2: decisions > 0 ? `${decisions.toLocaleString()} Atested decisions as evidence` : '', click: 'Click to view your current case with live evidence' };
  } else if (doc?.generated_at) {
    boxes.case = { s1: `Generated for ${rec} on ${doc.generated_at.slice(0, 10)}`, s2: decisions > 0 ? `${decisions.toLocaleString()} Atested decisions as evidence` : '', click: 'Click to review and share your case' };
  } else if (rec) {
    boxes.case = { s1: 'Ready to generate', s2: '', click: 'Click to review and share your case' };
  } else {
    boxes.case = { s1: 'Complete the survey first', s2: '', click: 'Click to review and share your case' };
  }

  // License
  if (isLicensed) {
    const lp = COMMERCIAL_TERMS[licensedTier]?.price || '';
    const pd = md.purchase_date ? md.purchase_date.slice(0, 10) : '';
    boxes.purchase = { s1: `Licensed: ${_tierLabel(licensedTier)}${lp ? ' at ' + lp : ''}`, s2: pd ? `Purchased ${pd}` : '', click: 'Click to view license details and renewal' };
  } else if (rec) {
    boxes.purchase = { s1: 'Not yet licensed', s2: `Recommended: ${rec} at ${price}`, click: q.recommendation === 'personal' ? 'Click to register \u2014 free' : `Click to purchase your plan` };
  } else {
    boxes.purchase = { s1: 'Not yet licensed', s2: '', click: 'Click to purchase your plan' };
  }

  return boxes;
}

// ---------- Render launcher surface ----------

function _renderLauncher(state) {
  const paneStates = _computePaneStates(state);
  const agg = _aggregateState(paneStates);
  const gridRows = _computeGridRows(state, paneStates);
  const boxContent = _computeBoxContent(state, paneStates);
  const statusTitle = _computeStatusTitle(state);

  // Status pane
  const pane = state.el.querySelector('.ll-status-pane');
  if (pane) {
    pane.classList.toggle('ll-sp-green', agg === 'green');
    pane.classList.toggle('ll-sp-amber', agg === 'amber');
    const dot = pane.querySelector('.ll-sp-dot');
    if (dot) { dot.className = 'll-sp-dot'; dot.classList.add(agg === 'green' ? 'll-dot-green' : 'll-dot-amber'); }
    const titleEl = pane.querySelector('.ll-sp-tier');
    if (titleEl) titleEl.textContent = statusTitle;
    const closingEl = pane.querySelector('.ll-sp-closing');
    if (closingEl) closingEl.textContent = agg === 'green' ? 'All panes current.' : 'Review the panes below for your next step.';

    // Grid rows
    const paneKeys = ['tiers', 'survey', 'case', 'license', 'terms'];
    paneKeys.forEach(key => {
      const row = pane.querySelector(`[data-pane="${key}"]`);
      if (!row) return;
      const ps = paneStates[key] || 'amber';
      row.classList.toggle('ll-sp-row-green', ps === 'green');
      row.classList.toggle('ll-sp-row-amber', ps === 'amber');
      const nameEl = row.querySelector('.ll-sp-name');
      const descEl = row.querySelector('.ll-sp-desc');
      const stateEl = row.querySelector('.ll-sp-state');
      if (nameEl) nameEl.textContent = { tiers: 'Tiers', survey: 'Survey', case: 'Case document', license: 'License', terms: 'Terms' }[key];
      const r = gridRows[key] || {};
      if (descEl) descEl.textContent = r.desc || '';
      if (stateEl) stateEl.textContent = r.label || '';
    });
  }

  // Terms sliver
  const sliver = state.el.querySelector('.ll-terms-sliver');
  if (sliver) {
    const ts = paneStates.terms;
    sliver.classList.toggle('ll-ts-green', ts === 'green');
    sliver.classList.toggle('ll-ts-amber', ts === 'amber');
    const actionEl = sliver.querySelector('.ll-ts-action');
    if (actionEl) actionEl.textContent = ts === 'green' ? 'Reviewed' : 'Click to review';
  }

  // Boxes
  const boxKeys = ['tiers', 'survey', 'case', 'purchase'];
  const boxPaneMap = { tiers: 'tiers', survey: 'survey', case: 'case', purchase: 'license' };
  boxKeys.forEach(key => {
    const box = state.el.querySelector(`.ll-box[data-box="${key}"]`);
    if (!box) return;
    const ps = paneStates[boxPaneMap[key]] || 'amber';
    box.classList.toggle('ll-box-green', ps === 'green');
    box.classList.toggle('ll-box-amber', ps === 'amber');
    const bc = boxContent[key] || {};
    const s1 = box.querySelector('.ll-s1');
    const s2 = box.querySelector('.ll-s2');
    const s3 = box.querySelector('.ll-s3');
    const click = box.querySelector('.ll-click');
    if (s1) s1.textContent = bc.s1 || '';
    if (s2) s2.textContent = bc.s2 || '';
    if (s3) s3.textContent = bc.s3 || '';
    if (click) click.textContent = bc.click || '';
  });

  // Wire click handlers
  state.el.querySelectorAll('.ll-box').forEach(btn => {
    btn.addEventListener('click', () => _openBoxGrandchild(btn.dataset.box, btn, state));
  });
  if (sliver) {
    sliver.addEventListener('click', () => _openBoxGrandchild('terms', sliver, state));
  }
}

// ---------- Refresh (after grandchild close) ----------

async function _refreshLauncher(state) {
  const [modeRes, qRes, caseRes] = await Promise.all([
    api.getLicensingMode(),
    api.getQuestionnaireState(),
    api.getCaseDocument(),
  ]);

  if (modeRes.ok) {
    state.modeData = modeRes.data;
    if (modeRes.data.trial_complete && !modeRes.data.trial_extended) {
      state.mode = 'personal';
      _refreshLicenseState();
    } else {
      state.mode = _normalizeMode(modeRes.data);
    }
  }
  if (qRes.ok) state.qState = reconstructState(qRes.data);
  if (caseRes.ok) state.caseData = caseRes.data;

  // Re-render all dynamic content
  const paneStates = _computePaneStates(state);
  const agg = _aggregateState(paneStates);
  const gridRows = _computeGridRows(state, paneStates);
  const boxContent = _computeBoxContent(state, paneStates);
  const statusTitle = _computeStatusTitle(state);

  // Status pane
  const pane = state.el.querySelector('.ll-status-pane');
  if (pane) {
    pane.classList.toggle('ll-sp-green', agg === 'green');
    pane.classList.toggle('ll-sp-amber', agg === 'amber');
    const dot = pane.querySelector('.ll-sp-dot');
    if (dot) { dot.className = 'll-sp-dot'; dot.classList.add(agg === 'green' ? 'll-dot-green' : 'll-dot-amber'); }
    const titleEl = pane.querySelector('.ll-sp-tier');
    if (titleEl) titleEl.textContent = statusTitle;
    const closingEl = pane.querySelector('.ll-sp-closing');
    if (closingEl) closingEl.textContent = agg === 'green' ? 'All panes current.' : 'Review the panes below for your next step.';
    const paneKeys = ['tiers', 'survey', 'case', 'license', 'terms'];
    paneKeys.forEach(key => {
      const row = pane.querySelector(`[data-pane="${key}"]`);
      if (!row) return;
      const ps = paneStates[key] || 'amber';
      row.classList.toggle('ll-sp-row-green', ps === 'green');
      row.classList.toggle('ll-sp-row-amber', ps === 'amber');
      const r = gridRows[key] || {};
      const descEl = row.querySelector('.ll-sp-desc');
      const stateEl = row.querySelector('.ll-sp-state');
      if (descEl) descEl.textContent = r.desc || '';
      if (stateEl) stateEl.textContent = r.label || '';
    });
  }

  // Terms sliver
  const sliver = state.el.querySelector('.ll-terms-sliver');
  if (sliver) {
    const ts = paneStates.terms;
    sliver.classList.toggle('ll-ts-green', ts === 'green');
    sliver.classList.toggle('ll-ts-amber', ts === 'amber');
    const actionEl = sliver.querySelector('.ll-ts-action');
    if (actionEl) actionEl.textContent = ts === 'green' ? 'Reviewed' : 'Click to review';
  }

  // Boxes
  const boxKeys = ['tiers', 'survey', 'case', 'purchase'];
  const boxPaneMap = { tiers: 'tiers', survey: 'survey', case: 'case', purchase: 'license' };
  boxKeys.forEach(key => {
    const box = state.el.querySelector(`.ll-box[data-box="${key}"]`);
    if (!box) return;
    const ps = paneStates[boxPaneMap[key]] || 'amber';
    box.classList.toggle('ll-box-green', ps === 'green');
    box.classList.toggle('ll-box-amber', ps === 'amber');
    const bc = boxContent[key] || {};
    const s1 = box.querySelector('.ll-s1');
    const s2 = box.querySelector('.ll-s2');
    const s3 = box.querySelector('.ll-s3');
    const click = box.querySelector('.ll-click');
    if (s1) s1.textContent = bc.s1 || '';
    if (s2) s2.textContent = bc.s2 || '';
    if (s3) s3.textContent = bc.s3 || '';
    if (click) click.textContent = bc.click || '';
  });

  _refreshLicenseState();
}

// ---------- Grandchild navigation ----------

function _openBoxGrandchild(boxId, trigger, state) {
  if (modalManager.depth >= 2) return;
  const titles = { tiers: 'Tiers', survey: 'Survey', case: 'Case Document', purchase: 'License', terms: 'Terms' };
  const content = _buildGrandchildContent(boxId, state);
  const result = modalManager.open({ title: titles[boxId] || boxId, trigger, content });
  if (!result) return;

  // Accent color: use action-state color, not fixed pane color
  const paneStates = _computePaneStates(state);
  const paneMap = { tiers: 'tiers', survey: 'survey', case: 'case', purchase: 'license', terms: 'terms' };
  const ps = paneStates[paneMap[boxId]] || 'amber';
  const accent = ps === 'green' ? '#4ade80' : '#f59e42';
  if (result.frame) result.frame.style.setProperty('--grandchild-accent', accent);

  modalManager.setOnClose(() => _refreshLauncher(state));
}

function _buildGrandchildContent(boxId, state) {
  switch (boxId) {
    case 'tiers': return _buildTierDisplayPanel(state);
    case 'survey': return _buildQuestionnairePanel(state);
    case 'case': return _buildCaseDocumentPanel(state);
    case 'purchase': return _buildUnifiedPurchasePanel(state);
    case 'terms': return _buildTermsPanel(state);
    default: {
      const el = document.createElement('div');
      el.className = 'lic-panel';
      el.textContent = 'Unknown panel.';
      return el;
    }
  }
}

// ---------- Terms grandchild ----------

function _buildTermsPanel(state) {
  const el = document.createElement('div');
  el.className = 'lic-terms-panel';
  const ack = state.modeData?.terms_acknowledged || false;

  el.innerHTML = `
    <div class="lt-section">
      <h3 class="lt-heading">How Atested licensing works</h3>
      <p class="lt-text">Atested demonstrates its capabilities on your real governance data during your trial. The trial is not time-limited \u2014 it ends when you have generated enough governance decisions to see the value. At that point you can license the tier that fits your organization, or continue on the free Personal tier.</p>
    </div>

    <div class="lt-section">
      <h3 class="lt-heading">The recommendation process</h3>
      <p class="lt-text">The survey asks about your deployment: how many users, how many machines, which governance capabilities you need. The climbing procedure tests each tier boundary until it finds the one that fits. The result is a verified recommendation \u2014 the lowest tier that covers everything you need.</p>
    </div>

    <div class="lt-section">
      <h3 class="lt-heading">Purchasing and license dating</h3>
      <p class="lt-text">Crew and higher are annual licenses dated from trial completion. Personal Plus is dated from purchase. Personal is free and does not require purchase. All paid licenses renew annually. If you choose not to renew, your views revert to Personal capabilities. Governance continues uninterrupted \u2014 chain records are marked as unlicensed but never lost.</p>
    </div>

    <div class="lt-section">
      <h3 class="lt-heading">Telemetry reciprocity</h3>
      <p class="lt-text">If you opt into telemetry, Atested receives anonymous aggregated usage counts: total decisions, deterministic vs judgment split, tool categories. No file paths, no user identities, no organization names. In return, Atested shares back anonymized benchmarks so you can compare your governance posture to similar deployments. Opting out is always available \u2014 you lose the benchmark comparison but nothing else changes.</p>
    </div>

    <div class="lt-section">
      <h3 class="lt-heading">What the trial means</h3>
      <p class="lt-text">During trial, all tier capabilities are available. This lets you evaluate the full product before deciding. The trial threshold is based on governance activity, not time. Once you reach it, Atested prompts you to license or register for Personal. There is no lockout \u2014 governance continues regardless of licensing status.</p>
    </div>

    <div class="lt-ack-area">
      ${ack
        ? `<div class="lt-ack-done"><span class="lt-ack-check">\u2713</span> Terms reviewed${state.modeData?.terms_acknowledged_at ? ' on ' + state.modeData.terms_acknowledged_at.slice(0, 10) : ''}</div>`
        : `<button class="lic-action-btn lic-action-primary lt-ack-btn">I have reviewed these terms</button>`
      }
    </div>
  `;

  if (!ack) {
    const btn = el.querySelector('.lt-ack-btn');
    if (btn) {
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        btn.textContent = 'Recording\u2026';
        const res = await api.postTermsAcknowledge();
        if (res.ok) {
          state.modeData.terms_acknowledged = true;
          state.modeData.terms_acknowledged_at = res.data.acknowledged_at || '';
          const area = el.querySelector('.lt-ack-area');
          if (area) {
            area.innerHTML = `<div class="lt-ack-done"><span class="lt-ack-check">\u2713</span> Terms reviewed${res.data.acknowledged_at ? ' on ' + res.data.acknowledged_at.slice(0, 10) : ''}</div>`;
          }
        } else {
          btn.disabled = false;
          btn.textContent = 'I have reviewed these terms';
        }
      });
    }
  }

  return el;
}

// ---------- Panel switching (repurposed for grandchild model) ----------

/**
 * _switchPanel is called from within panel builders (e.g. "View Tier Details",
 * "See your case document"). In the grandchild model, it closes the current
 * grandchild and opens the target box's grandchild.
 */
function _switchPanel(state, panelId) {
  const boxMap = {
    tiers: 'tiers',
    questionnaire: 'survey',
    'case-document': 'case',
    register: 'purchase',
    purchase: 'purchase',
    management: 'purchase',
    overview: null,
  };
  const targetBox = boxMap[panelId];
  if (!targetBox) return;

  // Close the current grandchild
  if (modalManager.depth >= 2) {
    modalManager.closeTopmost();
  }

  // Open the target grandchild after a frame so DOM settles
  requestAnimationFrame(() => {
    const trigger = state.el.querySelector(`[data-box="${targetBox}"]`);
    _openBoxGrandchild(targetBox, trigger, state);
  });
}

// ==========================================================================
// Questionnaire panel (Survey)
// ==========================================================================

function _buildQuestionnairePanel(state) {
  const el = document.createElement('div');
  el.className = 'lic-questionnaire';
  el.innerHTML = `<atd-loading-indicator label="Loading survey"></atd-loading-indicator>`;

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
      <h3 class="lq-heading">Licensing Survey</h3>
      <p class="lq-text">
        This survey determines which Atested tier fits your organization.
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
          Testing ${_esc(TIER_LABELS[fromTier] || fromTier)} \u2192 ${_esc(TIER_LABELS[toTier] || toTier)} boundary
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

  // Build side-by-side reasoning cards
  const hasLower = !!reasoning.whyNotLower;
  const hasHigher = !!reasoning.whyNotHigher;
  const hasBoth = hasLower && hasHigher;

  el.innerHTML = `
    <div class="lq-threshold">
      <!-- Row 1: Recommendation (full width) -->
      <div class="lq-recommendation-card">
        <div class="lq-recommendation-badge">Verified Recommendation</div>
        <h3 class="lq-recommendation-tier">${_esc(tierLabel)}</h3>
        <p class="lq-recommendation-summary">
          Based on your answers, <strong>${_esc(tierLabel)}</strong> is the right tier
          for your organization.
        </p>
      </div>

      <!-- Row 2: Why panes side by side -->
      ${(hasLower || hasHigher) ? `
        <div class="lq-why-row ${hasBoth ? 'lq-why-row-pair' : ''}">
          ${hasLower ? `
            <div class="lq-reasoning-card">
              <h4 class="lq-reasoning-heading">Why not a lower tier?</h4>
              <p class="lq-reasoning-text">${_esc(reasoning.whyNotLower)}</p>
            </div>
          ` : ''}
          ${hasHigher ? `
            <div class="lq-reasoning-card">
              <h4 class="lq-reasoning-heading">Why not a higher tier?</h4>
              <p class="lq-reasoning-text">${_esc(reasoning.whyNotHigher)}</p>
            </div>
          ` : ''}
        </div>
      ` : ''}

      <!-- Row 3: Workflow pane -->
      <div class="lq-workflow-pane">
        <div class="lq-workflow-primary">
          <button class="lic-action-btn lic-action-primary lq-see-case">Review your case document</button>
          <span class="lq-workflow-hint">See the full recommendation with evidence before sharing or purchasing.</span>
        </div>

        <div class="lq-workflow-secondary">
          <button class="lic-action-btn lq-continue-refining">Answer more questions to strengthen your case</button>
          <span class="lq-workflow-hint">Adds detail useful for justifying the purchase to your organization.</span>
        </div>

        <div class="lq-workflow-tertiary">
          <button class="lic-action-btn lq-restart-btn">Restart Survey</button>
          <span class="lq-restart-hint">Restart if your situation has changed \u2014 different team size, different machine count, or different priorities than when you first answered. Your previous answers are cleared and the survey begins fresh.</span>
        </div>
      </div>
    </div>
  `;

  el.querySelector('.lq-see-case').addEventListener('click', () => {
    _switchPanel(appState, 'case-document');
  });

  el.querySelector('.lq-continue-refining').addEventListener('click', () => {
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
  const reasoning = thresholdReasoning(qState);
  const hasLower = !!reasoning.whyNotLower;
  const hasHigher = !!reasoning.whyNotHigher;
  const hasBoth = hasLower && hasHigher;

  el.innerHTML = `
    <div class="lq-threshold">
      <!-- Row 1: Recommendation (full width) -->
      <div class="lq-recommendation-card">
        <div class="lq-recommendation-badge">Verified Recommendation</div>
        <h3 class="lq-recommendation-tier">${_esc(tierLabel)}</h3>
        <p class="lq-recommendation-summary">
          All available questions have been answered. Your recommendation is
          <strong>${_esc(tierLabel)}</strong>.
        </p>
      </div>

      <!-- Row 2: Why panes side by side -->
      ${(hasLower || hasHigher) ? `
        <div class="lq-why-row ${hasBoth ? 'lq-why-row-pair' : ''}">
          ${hasLower ? `
            <div class="lq-reasoning-card">
              <h4 class="lq-reasoning-heading">Why not a lower tier?</h4>
              <p class="lq-reasoning-text">${_esc(reasoning.whyNotLower)}</p>
            </div>
          ` : ''}
          ${hasHigher ? `
            <div class="lq-reasoning-card">
              <h4 class="lq-reasoning-heading">Why not a higher tier?</h4>
              <p class="lq-reasoning-text">${_esc(reasoning.whyNotHigher)}</p>
            </div>
          ` : ''}
        </div>
      ` : ''}

      <!-- Row 3: Workflow pane -->
      <div class="lq-workflow-pane">
        <div class="lq-workflow-primary">
          <button class="lic-action-btn lic-action-primary lq-view-case">Review your case document</button>
          <span class="lq-workflow-hint">See the full recommendation with evidence before sharing or purchasing.</span>
        </div>

        <div class="lq-workflow-secondary">
          <button class="lic-action-btn lq-view-tiers">View Tier Details</button>
          <span class="lq-workflow-hint">Compare all tiers side by side with fit assessments.</span>
        </div>

        <div class="lq-workflow-tertiary">
          <button class="lic-action-btn lq-restart-btn">Restart Survey</button>
          <span class="lq-restart-hint">Restart if your situation has changed \u2014 different team size, different machine count, or different priorities than when you first answered. Your previous answers are cleared and the survey begins fresh.</span>
        </div>
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
    // Close current grandchild and reopen survey
    _switchPanel(appState, 'questionnaire');
  } else {
    console.error('Survey reset failed:', res.error);
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
// Unified Purchase panel (merges Register + Purchase + Management)
// ==========================================================================

function _buildUnifiedPurchasePanel(state) {
  const el = document.createElement('div');
  el.className = 'lup-panel';
  el.innerHTML = '<atd-loading-indicator label="Loading license details"></atd-loading-indicator>';
  _loadUnifiedPurchase(el, state);
  return el;
}

async function _loadUnifiedPurchase(el, state) {
  // Refresh mode data to get latest license status
  const res = await api.getLicensingMode();
  if (!res.ok) {
    el.innerHTML = `<div class="lic-error">${_esc(res.error)}</div>`;
    return;
  }

  state.modeData = res.data;
  if (res.data.trial_complete && !res.data.trial_extended) {
    state.mode = 'personal';
  } else {
    state.mode = _normalizeMode(res.data);
  }

  _renderUnifiedPurchase(el, state);
}

function _renderUnifiedPurchase(el, state) {
  const modeData = state.modeData || {};
  const currentTier = modeData.license_tier || '';
  const currentStatus = modeData.license_status || '';
  const isLicensed = currentStatus === 'licensed';
  const operatorName = modeData.operator_name || '';

  const TIER_ORDER = ['personal', 'personal_plus', 'crew', 'team', 'institution'];
  const currentIdx = TIER_ORDER.indexOf(currentTier);

  // All 5 tiers including Personal
  const ALL_TIERS = TIER_ORDER.map(id => ({
    id,
    label: TIER_LABELS[id] || _tierLabel(id),
    price: COMMERCIAL_TERMS[id]?.price || 'Free',
    dating: COMMERCIAL_TERMS[id]?.dating || '',
    selfServe: id !== 'institution',
    isPersonal: id === 'personal',
  }));

  let selectedTier = isLicensed
    ? (ALL_TIERS.find(t => TIER_ORDER.indexOf(t.id) > currentIdx) || ALL_TIERS[1]).id
    : 'personal';

  // Registration data
  const regData = {
    operator_name: operatorName,
    context_note: '',
    telemetry_opted_in: true,
  };

  el.innerHTML = '';

  // A. Management section (if licensed)
  let managementHtml = '';
  if (isLicensed) {
    const purchaseDate = (modeData.purchase_date || '').slice(0, 10) || 'N/A';
    const expiryDate = (modeData.license_expiry || '').slice(0, 10) || 'N/A';
    const autoRenewal = modeData.auto_renewal !== false;
    const pendingDowngrade = modeData.pending_downgrade || null;

    const downgradeTiers = TIER_ORDER.slice(0, Math.max(0, currentIdx)).filter(t => t !== 'personal');
    let downgradeOptions = downgradeTiers.map(dt =>
      `<option value="${dt}">${_tierLabel(dt)}</option>`
    ).join('');

    managementHtml = `
      <div class="lup-management">
        <h3 class="lup-heading">License Management</h3>
        <div class="lup-mgmt-card">
          <div class="lup-mgmt-row"><span class="lup-mgmt-label">Current Tier</span><span class="lup-mgmt-value">${_esc(_tierLabel(currentTier))}</span></div>
          <div class="lup-mgmt-row"><span class="lup-mgmt-label">Purchase Date</span><span class="lup-mgmt-value">${_esc(purchaseDate)}</span></div>
          <div class="lup-mgmt-row"><span class="lup-mgmt-label">Renewal Date</span><span class="lup-mgmt-value">${_esc(expiryDate)}</span></div>
        </div>

        <div class="lup-renewal-section">
          <div class="lup-renewal-status">
            <span class="lup-renewal-dot" style="background: ${autoRenewal ? '#22c55e' : '#f59e42'}"></span>
            <span>Auto-renewal ${autoRenewal ? 'enabled' : 'disabled'}</span>
          </div>
          <button class="lic-action-btn lup-renewal-toggle">${autoRenewal ? 'Turn Off' : 'Turn On'}</button>
        </div>

        ${pendingDowngrade ? `
          <div class="lup-pending-downgrade">
            Downgrade to <strong>${_esc(_tierLabel(pendingDowngrade.to_tier))}</strong>
            scheduled for <strong>${_esc((pendingDowngrade.effective_date || '').slice(0, 10))}</strong>
            <button class="lic-action-btn lup-cancel-downgrade">Cancel</button>
          </div>
        ` : (downgradeTiers.length > 0 ? `
          <div class="lup-downgrade-section">
            <span class="lup-section-label">Downgrade at renewal</span>
            <div class="lup-downgrade-row">
              <select class="lup-downgrade-select">${downgradeOptions}</select>
              <button class="lic-action-btn lup-downgrade-btn">Schedule</button>
            </div>
          </div>
        ` : '')}

        <div class="lup-divider"></div>
        <p class="lup-upgrade-prompt">Upgrade to a higher tier</p>
      </div>
    `;
  }

  // B. Tier selector grid
  let tiersHtml = '';
  for (const t of ALL_TIERS) {
    const tierIdx = TIER_ORDER.indexOf(t.id);
    const belowCurrent = isLicensed && tierIdx <= currentIdx;
    const selected = t.id === selectedTier ? 'lup-tier-selected' : '';
    const disabled = belowCurrent ? 'lup-tier-disabled' : '';
    const tag = belowCurrent ? '<span class="lup-tier-tag">Current or lower</span>'
      : t.id === 'institution' ? '<span class="lup-tier-tag">Contact us</span>' : '';
    tiersHtml += `
      <button class="lup-tier-btn ${selected} ${disabled}" data-tier="${t.id}" ${belowCurrent ? 'disabled' : ''}>
        <span class="lup-tier-label">${_esc(t.label)}</span>
        <span class="lup-tier-price">${_esc(t.price)}</span>
        ${tag}
      </button>
    `;
  }

  // C. Detail + action area placeholder
  el.innerHTML = `
    ${managementHtml}
    <div class="lup-section">
      <div class="lup-section-label">Select Tier</div>
      <div class="lup-tier-grid">${tiersHtml}</div>
    </div>
    <div class="lup-detail-area"></div>
    <div class="lup-confirm-dialog" style="display:none"></div>
    <div class="lup-error" style="display:none"></div>
  `;

  // Render detail for initial selection
  _renderPurchaseDetail(el, selectedTier, regData, state, isLicensed);

  // Wire tier selection
  el.querySelectorAll('.lup-tier-btn:not([disabled])').forEach(btn => {
    btn.addEventListener('click', () => {
      el.querySelectorAll('.lup-tier-btn').forEach(b => b.classList.remove('lup-tier-selected'));
      btn.classList.add('lup-tier-selected');
      selectedTier = btn.dataset.tier;
      _renderPurchaseDetail(el, selectedTier, regData, state, isLicensed);
    });
  });

  // Wire management actions (if licensed)
  if (isLicensed) {
    const confirmArea = el.querySelector('.lup-confirm-dialog');
    const errorEl = el.querySelector('.lup-error');
    const expiryDate = (modeData.license_expiry || '').slice(0, 10) || 'N/A';
    const autoRenewal = modeData.auto_renewal !== false;

    const renewalToggle = el.querySelector('.lup-renewal-toggle');
    if (renewalToggle) {
      renewalToggle.addEventListener('click', () => {
        _showConfirmDialog(confirmArea, errorEl, state, {
          message: autoRenewal
            ? `Auto-renewal will be disabled. Your license will expire on ${expiryDate} and revert to Personal.`
            : `Auto-renewal will be enabled. Your license will renew automatically on ${expiryDate}.`,
          action: () => api.postAutoRenewal({ auto_renewal: !autoRenewal }),
          onSuccess: () => _loadUnifiedPurchase(el, state),
        });
      });
    }

    const cancelDowngrade = el.querySelector('.lup-cancel-downgrade');
    if (cancelDowngrade) {
      const pendingDowngrade = modeData.pending_downgrade;
      cancelDowngrade.addEventListener('click', () => {
        _showConfirmDialog(confirmArea, errorEl, state, {
          message: `Cancel the pending downgrade to ${_tierLabel(pendingDowngrade.to_tier)}?`,
          action: () => api.postPurchase({ tier: currentTier, payment_ref: 'cancel_downgrade', operator_name: operatorName }),
          onSuccess: () => _loadUnifiedPurchase(el, state),
        });
      });
    }

    const downgradeBtn = el.querySelector('.lup-downgrade-btn');
    if (downgradeBtn) {
      downgradeBtn.addEventListener('click', () => {
        const selectEl = el.querySelector('.lup-downgrade-select');
        const toTier = selectEl.value;
        const expiryDate = (modeData.license_expiry || '').slice(0, 10) || 'N/A';
        _showConfirmDialog(confirmArea, errorEl, state, {
          message: `Schedule downgrade from ${_tierLabel(currentTier)} to ${_tierLabel(toTier)}? You keep ${_tierLabel(currentTier)} until ${expiryDate}.`,
          action: () => api.postDowngrade({ to_tier: toTier }),
          onSuccess: () => _loadUnifiedPurchase(el, state),
        });
      });
    }
  }
}

function _renderPurchaseDetail(el, tier, regData, state, isLicensed) {
  const detailArea = el.querySelector('.lup-detail-area');
  if (!detailArea) return;

  const terms = COMMERCIAL_TERMS[tier] || {};
  const isPersonal = tier === 'personal';
  const isInstitution = tier === 'institution';
  const price = terms.price || (isPersonal ? 'Free' : '');

  // Institution: show contact card
  if (isInstitution) {
    detailArea.innerHTML = `
      <div class="lup-inst-card">
        <h4 class="lup-inst-heading">Institution Tier</h4>
        <p class="lup-inst-text">
          Institution licenses are tailored to your organization. Download
          your case document to share with your team, then contact us.
        </p>
        <div class="lup-inst-actions">
          <button class="lic-action-btn lup-inst-case-btn">View Case Document</button>
          <a href="mailto:hello@atested.com" class="lic-action-btn lic-action-primary" style="text-decoration:none;text-align:center">
            Contact hello@atested.com
          </a>
        </div>
      </div>
    `;
    detailArea.querySelector('.lup-inst-case-btn')?.addEventListener('click', () => {
      _switchPanel(state, 'case-document');
    });
    return;
  }

  // Registration fields + telemetry + action
  const actionLabel = isPersonal
    ? 'Register \u2014 Free'
    : `${isLicensed ? 'Upgrade to' : 'Purchase'} ${_tierLabel(tier)} \u2014 ${price}`;

  detailArea.innerHTML = `
    <div class="lup-detail-card">
      <div class="lup-detail-row"><span class="lup-detail-label">Price</span><span class="lup-detail-value lup-detail-price">${_esc(price)}</span></div>
      <div class="lup-detail-row"><span class="lup-detail-label">Billing</span><span class="lup-detail-value">${isPersonal ? 'Free' : (terms.billing || 'Annual')}</span></div>
      <div class="lup-detail-row"><span class="lup-detail-label">License Dating</span><span class="lup-detail-value">${_esc(terms.dating || 'From registration')}</span></div>
    </div>

    <div class="lup-reg-fields">
      <div class="lup-field">
        <label class="lup-label" for="lup-name">Your name or identifier</label>
        <input class="lup-input" id="lup-name" type="text" placeholder="e.g. your name or handle"
               value="${_esc(regData.operator_name)}" autocomplete="off" />
      </div>
      <div class="lup-field">
        <label class="lup-label" for="lup-context">What are you using Atested for? (optional)</label>
        <input class="lup-input lup-input-wide" id="lup-context" type="text"
               placeholder="e.g. personal development, team governance"
               value="${_esc(regData.context_note)}" autocomplete="off" />
      </div>
    </div>

    <div class="lup-tele-section">
      <div class="lup-section-label">Telemetry Exchange</div>
      <p class="lup-tele-desc">
        Participating operators share anonymous, aggregated usage data and receive
        shared insights and routine notifications in return.
      </p>
      <div class="lup-tele-options">
        <button class="lup-tele-btn ${regData.telemetry_opted_in ? 'lup-tele-selected' : ''}" data-choice="in">
          <span class="lup-tele-title">Participate</span>
          <span class="lup-tele-hint">Share anonymous data. Receive community insights.</span>
        </button>
        <button class="lup-tele-btn ${!regData.telemetry_opted_in ? 'lup-tele-selected' : ''}" data-choice="out">
          <span class="lup-tele-title">Decline</span>
          <span class="lup-tele-hint">No data shared. Critical notifications continue.</span>
        </button>
      </div>
    </div>

    <div class="lup-actions">
      <button class="lic-action-btn lic-action-primary lup-action-btn">${_esc(actionLabel)}</button>
    </div>
    <div class="lup-action-error" style="display:none"></div>
  `;

  // Wire telemetry selection
  detailArea.querySelectorAll('.lup-tele-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      regData.telemetry_opted_in = btn.dataset.choice === 'in';
      detailArea.querySelectorAll('.lup-tele-btn').forEach(b =>
        b.classList.toggle('lup-tele-selected', b === btn)
      );
    });
  });

  // Sync name/context inputs back to regData on change
  const nameInput = detailArea.querySelector('#lup-name');
  const contextInput = detailArea.querySelector('#lup-context');
  nameInput.addEventListener('input', () => { regData.operator_name = nameInput.value.trim(); });
  contextInput.addEventListener('input', () => { regData.context_note = contextInput.value.trim(); });

  // Wire action button
  const actionBtn = detailArea.querySelector('.lup-action-btn');
  const errorEl = detailArea.querySelector('.lup-action-error');

  actionBtn.addEventListener('click', async () => {
    // Validate name
    const name = nameInput.value.trim();
    if (!name) {
      errorEl.textContent = 'Please enter a name or identifier.';
      errorEl.style.display = '';
      nameInput.focus();
      return;
    }
    // Terms gate: require acknowledgment before purchase
    if (!state.modeData?.terms_acknowledged) {
      errorEl.textContent = 'Review the licensing terms first. Close this window and click the Terms pane.';
      errorEl.style.display = '';
      return;
    }

    regData.operator_name = name;
    regData.context_note = contextInput.value.trim();

    actionBtn.disabled = true;
    actionBtn.textContent = 'Processing\u2026';
    errorEl.style.display = 'none';

    if (isPersonal) {
      // Register for Personal (free)
      const res = await api.postRegister({
        operator_name: regData.operator_name,
        context_note: regData.context_note,
        telemetry_opted_in: regData.telemetry_opted_in,
      });

      if (!res.ok) {
        actionBtn.disabled = false;
        actionBtn.textContent = actionLabel;
        errorEl.textContent = res.error || 'Registration failed.';
        errorEl.style.display = '';
        return;
      }

      // Success
      _renderPurchaseSuccess(el, { ...res.data, tier: 'personal' }, state, 'Registered', 'Personal License Active');
      _refreshLicenseState();
    } else {
      // Paid tier purchase/upgrade
      const payRes = await licensingApi.initiatePurchase({ tier });
      if (!payRes.ok) {
        actionBtn.disabled = false;
        actionBtn.textContent = actionLabel;
        errorEl.textContent = payRes.error || 'Payment failed.';
        errorEl.style.display = '';
        return;
      }

      const res = await api.postPurchase({
        tier,
        payment_ref: payRes.data.payment_ref,
        operator_name: regData.operator_name,
      });

      if (!res.ok) {
        actionBtn.disabled = false;
        actionBtn.textContent = actionLabel;
        errorEl.textContent = res.error || 'Purchase failed.';
        errorEl.style.display = '';
        return;
      }

      const badge = isLicensed ? 'Upgraded' : 'Purchased';
      const headline = isLicensed ? `Upgraded to ${_tierLabel(tier)}` : `${_tierLabel(tier)} License Active`;
      _renderPurchaseSuccess(el, res.data, state, badge, headline);
      _refreshLicenseState();
    }
  });
}

function _renderPurchaseSuccess(el, data, state, badge, headline) {
  const tier = data.tier || 'personal';
  const label = _tierLabel(tier);

  el.innerHTML = `
    <div class="lup-success">
      <div class="lup-success-badge">${_esc(badge)}</div>
      <h3 class="lup-heading">${_esc(headline)}</h3>
      <p class="lup-text-muted">Your ${_esc(label)} license is now active.</p>
      <div class="lup-mgmt-card">
        <div class="lup-mgmt-row">
          <span class="lup-mgmt-label">Tier</span>
          <span class="lup-mgmt-value" style="color:#22c55e">${_esc(label)}</span>
        </div>
        ${data.license_expiry ? `
          <div class="lup-mgmt-row">
            <span class="lup-mgmt-label">Expires</span>
            <span class="lup-mgmt-value">${_esc((data.license_expiry || '').slice(0, 10))}</span>
          </div>
        ` : ''}
      </div>
      <div class="lup-actions" style="justify-content:center">
        <button class="lic-action-btn lup-view-tiers">View Tier Details</button>
      </div>
    </div>
  `;

  // Update state
  state.mode = tier === 'personal' ? 'personal_registered' : tier;
  state.modeData = { ...state.modeData, license_status: tier === 'personal' ? 'personal' : 'licensed', license_tier: tier, registered: true };

  el.querySelector('.lup-view-tiers')?.addEventListener('click', () => {
    _switchPanel(state, 'tiers');
  });
}

function _showConfirmDialog(confirmArea, errorEl, state, { message, action, onSuccess }) {
  confirmArea.style.display = '';
  confirmArea.innerHTML = `
    <div class="lup-confirm-card">
      <p class="lup-confirm-text">${_esc(message)}</p>
      <div class="lup-confirm-actions">
        <button class="lic-action-btn lup-confirm-cancel">Cancel</button>
        <button class="lic-action-btn lic-action-primary lup-confirm-ok">Confirm</button>
      </div>
    </div>
  `;

  const cancelBtn = confirmArea.querySelector('.lup-confirm-cancel');
  cancelBtn.focus();

  cancelBtn.addEventListener('click', () => {
    confirmArea.style.display = 'none';
  });

  confirmArea.querySelector('.lup-confirm-ok').addEventListener('click', async () => {
    const okBtn = confirmArea.querySelector('.lup-confirm-ok');
    okBtn.disabled = true;
    okBtn.textContent = 'Saving\u2026';
    errorEl.style.display = 'none';

    const res = await action();
    if (!res.ok) {
      okBtn.disabled = false;
      okBtn.textContent = 'Confirm';
      errorEl.textContent = res.error || 'Operation failed.';
      errorEl.style.display = '';
      return;
    }

    confirmArea.style.display = 'none';
    if (onSuccess) onSuccess();
  });
}

// ==========================================================================
// Case document panel
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

  // Commercial terms come from client-side single source of truth
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
          This recommendation is tentative. Additional survey questions would verify it.
        </div>
      ` : ''}

      ${!hasRecommendation ? `
        <div class="lcd-no-rec">
          <p class="lq-text">No recommendation yet. Complete the survey to receive a tier recommendation.</p>
          <div class="lq-actions">
            <button class="lic-action-btn lic-action-primary" data-nav="questionnaire">Start Survey</button>
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
          <button class="lic-action-btn lq-restart-btn lcd-restart-btn">Restart Survey</button>
        </div>
      `}
    </div>
  `;

  // Wire nav buttons
  el.querySelectorAll('[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => {
      _switchPanel(appState, btn.dataset.nav);
    });
  });

  // Wire download button
  const dlBtn = el.querySelector('.lcd-download-btn');
  if (dlBtn) {
    dlBtn.addEventListener('click', () => _downloadCaseDocument(doc));
  }

  // Wire restart button
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
    md += `> **Note:** This recommendation is tentative. Additional survey questions would verify it.\n\n`;
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
// Tier display panel
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
      _switchPanel(appState, btn.dataset.nav);
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
      return `<div class="ltd-tier-action"><button class="lic-action-btn lic-action-primary" data-nav="questionnaire">Continue Survey</button></div>`;
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

function _tierLabel(tier) {
  const LABELS = { personal: 'Personal', personal_plus: 'Personal Plus', crew: 'Crew', team: 'Team', institution: 'Institution' };
  return LABELS[tier] || tier;
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
    align-items: center;
    padding: 24px 24px 16px;
  }
  .lic-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 12px 16px;
    border-radius: 8px;
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

  /* ---- License status pane (five-row grid) ---- */
  .ll-status-pane {
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 20px 24px 16px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    margin-bottom: 12px;
    width: 100%;
    max-width: 780px;
  }
  .ll-sp-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
  }
  .ll-sp-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
    background: #8b919a;
    transition: background 0.2s, box-shadow 0.2s;
  }
  .ll-dot-green {
    background: #4ade80;
    box-shadow: 0 0 8px rgba(74, 222, 128, 0.4);
  }
  .ll-dot-amber {
    background: #f59e42;
    box-shadow: 0 0 8px rgba(245, 158, 66, 0.3);
  }
  .ll-sp-title {
    font-size: 1rem;
    font-weight: 600;
    color: #e4e6eb;
  }
  .ll-sp-tier {
    font-weight: 400;
    color: #b0b6c0;
  }
  .ll-sp-intro {
    font-size: 0.82rem;
    color: #8b919a;
    margin-bottom: 10px;
    padding-left: 20px;
  }
  .ll-sp-grid {
    display: grid;
    grid-template-columns: 90px 1fr auto;
    gap: 4px 12px;
    padding-left: 20px;
    align-items: baseline;
  }
  .ll-sp-row {
    display: contents;
  }
  .ll-sp-name {
    font-size: 0.82rem;
    font-weight: 500;
    color: #8b919a;
    padding: 3px 0;
  }
  .ll-sp-desc {
    font-size: 0.82rem;
    color: #b0b6c0;
    padding: 3px 0;
    line-height: 1.35;
  }
  .ll-sp-state {
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 2px 8px;
    border-radius: 4px;
    white-space: nowrap;
  }
  .ll-sp-closing {
    font-size: 0.82rem;
    color: #6b7280;
    margin-top: 10px;
    padding-left: 20px;
  }
  /* Dynamic row colors */
  .ll-sp-row-green .ll-sp-name { color: #4ade80; }
  .ll-sp-row-green .ll-sp-state {
    color: #166534;
    background: rgba(74, 222, 128, 0.15);
  }
  .ll-sp-row-amber .ll-sp-name { color: #f59e42; }
  .ll-sp-row-amber .ll-sp-state {
    color: #92400e;
    background: rgba(245, 158, 66, 0.15);
  }
  /* Aggregate header dot colors applied via .ll-dot-green / .ll-dot-amber */
  .ll-sp-green .ll-sp-title { color: #e4e6eb; }
  .ll-sp-amber .ll-sp-title { color: #e4e6eb; }

  /* ---- Terms sliver ---- */
  .ll-terms-sliver {
    display: flex;
    align-items: center;
    gap: 0;
    width: 100%;
    max-width: 780px;
    padding: 0;
    margin-bottom: 12px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    transition: background 0.15s, border-color 0.15s;
    overflow: hidden;
    text-align: left;
  }
  .ll-terms-sliver:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.14);
  }
  .ll-terms-sliver:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .ll-ts-accent {
    width: 4px;
    align-self: stretch;
    flex-shrink: 0;
    background: #8b919a;
    transition: background 0.2s;
  }
  .ll-ts-green .ll-ts-accent { background: #4ade80; }
  .ll-ts-amber .ll-ts-accent { background: #f59e42; }
  .ll-ts-left {
    flex: 1;
    padding: 10px 16px;
    font-size: 0.9rem;
    color: #e4e6eb;
    line-height: 1.4;
  }
  .ll-ts-desc {
    color: #8b919a;
    font-weight: 400;
    margin-left: 6px;
  }
  .ll-ts-action {
    padding: 10px 16px;
    font-size: 0.82rem;
    font-weight: 500;
    color: #8b919a;
    white-space: nowrap;
    transition: color 0.15s;
  }
  .ll-ts-green .ll-ts-action { color: #4ade80; }
  .ll-ts-amber .ll-ts-action { color: #f59e42; }

  /* ---- Launcher grid ---- */
  .ll-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    width: 100%;
    max-width: 780px;
    flex: 1;
    align-content: start;
  }
  .ll-box {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
    padding: 28px 24px 20px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    transition: background 0.15s, border-color 0.15s, transform 0.1s, box-shadow 0.15s;
    text-align: left;
    overflow: hidden;
    min-height: 200px;
  }
  .ll-accent-bar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    border-radius: 12px 12px 0 0;
    background: rgba(255, 255, 255, 0.1);
    transition: background 0.2s;
  }
  /* Dynamic box accent colors */
  .ll-box-green .ll-accent-bar { background: #4ade80; }
  .ll-box-amber .ll-accent-bar { background: #f59e42; }
  .ll-box:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.14);
    transform: translateY(-1px);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  }
  .ll-box-green:hover { border-color: rgba(74, 222, 128, 0.3); }
  .ll-box-amber:hover { border-color: rgba(245, 158, 66, 0.3); }
  .ll-box:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .ll-box:active {
    transform: translateY(0);
  }
  .ll-title {
    font-size: 1.25rem;
    font-weight: 600;
    color: #e4e6eb;
    margin-bottom: 0;
  }
  .ll-subtitle {
    font-size: 0.82rem;
    color: #8b919a;
    margin-bottom: 6px;
  }
  .ll-desc {
    font-size: 0.9rem;
    color: #b0b6c0;
    line-height: 1.5;
    margin-bottom: 8px;
  }
  .ll-status-line {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.4;
  }
  .ll-click {
    font-size: 0.82rem;
    font-weight: 500;
    margin-top: auto;
    padding-top: 4px;
    color: #8b919a;
    transition: color 0.15s;
  }
  .ll-box-green .ll-click { color: #4ade80; }
  .ll-box-amber .ll-click { color: #f59e42; }

  /* ---- Terms panel (grandchild) ---- */
  .lic-terms-panel {
    max-width: 680px;
    margin: 0 auto;
    padding: 8px 0;
  }
  .lt-section {
    margin-bottom: 28px;
  }
  .lt-heading {
    font-size: 1.05rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 0 0 10px 0;
  }
  .lt-text {
    font-size: 0.9rem;
    color: #b0b6c0;
    line-height: 1.6;
    margin: 0 0 8px 0;
  }
  .lt-ack-area {
    margin-top: 32px;
    padding-top: 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    text-align: center;
  }
  .lt-ack-done {
    font-size: 0.9rem;
    color: #4ade80;
    font-weight: 500;
  }
  .lt-ack-check {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    margin-bottom: 14px;
    font-size: 0.9rem;
    color: #b0b6c0;
    cursor: pointer;
  }
  .lt-ack-check input {
    accent-color: #5b8af5;
    width: 16px;
    height: 16px;
  }
  .lt-ack-btn {
    display: inline-block;
    padding: 10px 32px;
    font-size: 0.9rem;
    font-weight: 500;
    color: #fff;
    background: #5b8af5;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    transition: background 0.15s;
  }
  .lt-ack-btn:hover { background: #4a79e4; }
  .lt-ack-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  /* ---- Survey panel ---- */
  .lic-questionnaire {
    /* full-width layout — no max-width constraint */
  }
  .lq-heading {
    font-size: 1.2rem;
    font-weight: 600;
    margin: 0 0 12px 0;
    color: #e4e6eb;
  }
  .lq-text {
    font-size: 1rem;
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
    font-size: 0.9rem;
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
    font-size: 1rem;
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
    font-size: 0.9rem;
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
    font-size: 0.82rem;
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
    font-size: 1rem;
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
    font-size: 0.9rem;
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
    font-size: 0.82rem;
    font-weight: 600;
    padding: 4px 12px;
    border-radius: 12px;
    margin-bottom: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lq-recommendation-badge-small {
    font-size: 0.82rem;
    padding: 3px 10px;
    margin-bottom: 0;
  }
  .lq-recommendation-tier {
    font-size: 1.7rem;
    font-weight: 700;
    margin: 0 0 8px 0;
    color: #e4e6eb;
  }
  .lq-recommendation-summary {
    font-size: 1rem;
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
    font-size: 0.9rem;
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
    font-size: 0.82rem;
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
    font-size: 0.82rem;
    color: #6b7280;
  }

  /* Previous answers */
  .lq-previous {
    margin-top: 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    padding-top: 12px;
  }
  .lq-previous-toggle {
    font-size: 0.82rem;
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
    font-size: 0.82rem;
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
    font-size: 1.2rem;
    font-weight: 600;
    margin: 0;
    color: #e4e6eb;
  }
  .lcd-timestamp {
    font-size: 0.82rem;
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
    font-size: 1rem;
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
    font-size: 0.82rem;
    font-weight: 600;
    padding: 3px 12px;
    border-radius: 12px;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lcd-rec-tier {
    font-size: 1.7rem;
    font-weight: 700;
    margin: 0 0 6px 0;
    color: #e4e6eb;
  }
  .lcd-rec-summary {
    font-size: 1rem;
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
    font-size: 0.9rem;
    font-weight: 600;
    color: #8b919a;
    margin: 0 0 8px 0;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .lcd-section-text {
    font-size: 1rem;
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
    font-size: 0.9rem;
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
    font-size: 0.82rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lcd-term-value {
    font-size: 1rem;
    color: #e4e6eb;
  }
  .lcd-terms-summary {
    font-size: 0.9rem;
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
    font-size: 0.82rem;
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
    font-size: 0.82rem;
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

  /* ---- Restart section ---- */
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
    font-size: 0.82rem;
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
    font-size: 0.9rem;
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
    font-size: 0.82rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .ltd-term-value {
    font-size: 0.9rem;
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
    font-size: 0.82rem;
    font-weight: 600;
    color: #5b8af5;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
  }
  .ltd-fit-text {
    font-size: 0.9rem;
    color: #e4e6eb;
    margin: 0;
    line-height: 1.5;
  }
  .ltd-tier-action {
    margin-top: 8px;
  }

  /* ---- Unified Purchase panel ---- */
  .lup-panel {
    max-width: 600px;
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }
  .lup-heading {
    font-size: 1.2rem;
    font-weight: 600;
    margin: 0 0 12px 0;
    color: #e4e6eb;
  }
  .lup-text-muted {
    font-size: 1rem;
    color: #8b919a;
    margin: 0 0 16px 0;
    line-height: 1.6;
  }
  .lup-section {
    margin-bottom: 20px;
  }
  .lup-section-label {
    font-size: 0.82rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
  }
  .lup-tier-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .lup-tier-btn {
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
  }
  .lup-tier-btn:hover:not([disabled]) {
    background: rgba(91, 138, 245, 0.08);
    border-color: rgba(91, 138, 245, 0.3);
  }
  .lup-tier-btn:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .lup-tier-selected {
    background: rgba(91, 138, 245, 0.10);
    border-color: #5b8af5;
  }
  .lup-tier-disabled {
    opacity: 0.45;
    cursor: default;
  }
  .lup-tier-label {
    font-size: 1rem;
    font-weight: 600;
  }
  .lup-tier-price {
    font-size: 0.82rem;
    color: #8b919a;
  }
  .lup-tier-tag {
    font-size: 0.68rem;
    color: #6b7280;
    font-style: italic;
  }

  /* Detail card */
  .lup-detail-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }
  .lup-detail-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.9rem;
  }
  .lup-detail-label {
    color: #6b7280;
    font-weight: 500;
  }
  .lup-detail-value {
    color: #e4e6eb;
    font-weight: 600;
  }
  .lup-detail-price {
    font-size: 1.2rem;
    color: #5b8af5;
  }

  /* Registration fields */
  .lup-reg-fields {
    margin-bottom: 16px;
  }
  .lup-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }
  .lup-label {
    font-size: 0.9rem;
    font-weight: 500;
    color: #e4e6eb;
  }
  .lup-input {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 1rem;
    padding: 8px 12px;
    width: 260px;
    outline: none;
    transition: border-color 0.15s;
  }
  .lup-input:focus {
    border-color: #5b8af5;
  }
  .lup-input::placeholder {
    color: #6b7280;
  }
  .lup-input-wide {
    width: 100%;
  }

  /* Telemetry */
  .lup-tele-section {
    margin-bottom: 20px;
  }
  .lup-tele-desc {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.5;
    margin: 0 0 10px 0;
  }
  .lup-tele-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lup-tele-btn {
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
    gap: 3px;
  }
  .lup-tele-btn:hover {
    background: rgba(91, 138, 245, 0.08);
    border-color: rgba(91, 138, 245, 0.3);
  }
  .lup-tele-btn:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .lup-tele-selected {
    background: rgba(91, 138, 245, 0.10);
    border-color: #5b8af5;
  }
  .lup-tele-title {
    font-size: 1rem;
    font-weight: 600;
  }
  .lup-tele-hint {
    font-size: 0.82rem;
    color: #8b919a;
  }

  /* Actions */
  .lup-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  .lup-action-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 8px;
    margin-top: 12px;
  }

  /* Management section */
  .lup-management {
    margin-bottom: 24px;
  }
  .lup-mgmt-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 16px;
  }
  .lup-mgmt-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.9rem;
  }
  .lup-mgmt-label {
    color: #6b7280;
    font-weight: 500;
  }
  .lup-mgmt-value {
    color: #e4e6eb;
    font-weight: 600;
  }
  .lup-renewal-section {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
  }
  .lup-renewal-status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.9rem;
    color: #e4e6eb;
  }
  .lup-renewal-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .lup-pending-downgrade {
    background: rgba(245, 158, 66, 0.06);
    border: 1px solid rgba(245, 158, 66, 0.2);
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 0.9rem;
    color: #f59e42;
    line-height: 1.5;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }
  .lup-downgrade-section {
    margin-bottom: 16px;
  }
  .lup-downgrade-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }
  .lup-downgrade-select {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 6px;
    color: #e4e6eb;
    padding: 6px 10px;
    font-size: 0.9rem;
    font-family: "Inter", system-ui, sans-serif;
    min-width: 140px;
    outline: none;
    transition: border-color 0.15s;
  }
  .lup-downgrade-select:focus-visible {
    border-color: #5b8af5;
    outline: 2px solid #5b8af5;
    outline-offset: 1px;
  }
  .lup-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.06);
    margin: 4px 0 16px 0;
  }
  .lup-upgrade-prompt {
    font-size: 0.9rem;
    color: #8b919a;
    margin: 0;
  }

  /* Confirm dialog */
  .lup-confirm-card {
    background: rgba(245, 158, 66, 0.06);
    border: 1px solid rgba(245, 158, 66, 0.2);
    border-radius: 10px;
    padding: 16px 20px;
    margin-top: 12px;
  }
  .lup-confirm-text {
    font-size: 0.9rem;
    color: #e4e6eb;
    margin: 0 0 12px 0;
    line-height: 1.5;
  }
  .lup-confirm-actions {
    display: flex;
    gap: 8px;
  }
  .lup-error {
    color: #f59e42;
    background: rgba(245, 158, 66, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 8px;
  }

  /* Success */
  .lup-success {
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
  }
  .lup-success-badge {
    display: inline-block;
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 4px 14px;
    border-radius: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lup-success .lup-mgmt-card {
    width: 100%;
    max-width: 340px;
  }

  /* Institution contact */
  .lup-inst-card {
    background: rgba(139, 92, 246, 0.06);
    border: 1px solid rgba(139, 92, 246, 0.2);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 16px;
  }
  .lup-inst-heading {
    font-size: 1rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 0 0 8px 0;
  }
  .lup-inst-text {
    font-size: 0.9rem;
    color: #8b919a;
    line-height: 1.5;
    margin: 0 0 12px 0;
  }
  .lup-inst-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  /* ---- Survey completion: why-row + workflow pane ---- */
  .lq-why-row {
    display: flex;
    flex-direction: column;
    gap: 12px;
    margin-bottom: 20px;
  }
  .lq-why-row-pair {
    flex-direction: row;
    gap: 16px;
  }
  .lq-why-row-pair > .lq-reasoning-card {
    flex: 1;
    min-width: 0;
    margin-bottom: 0;
  }
  .lq-workflow-pane {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
    padding: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .lq-workflow-primary,
  .lq-workflow-secondary,
  .lq-workflow-tertiary {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .lq-workflow-primary {
    padding-bottom: 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }
  .lq-workflow-secondary {
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  }
  .lq-workflow-hint {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.4;
    padding-left: 2px;
  }
  .lq-restart-hint {
    font-size: 0.82rem;
    color: #6b7280;
    line-height: 1.4;
    padding-left: 2px;
  }

  @media (max-width: 600px) {
    .ll-status-pane {
      padding: 14px 16px;
    }
    .ll-sp-grid {
      grid-template-columns: 70px 1fr auto;
      gap: 3px 8px;
      padding-left: 12px;
    }
    .ll-sp-intro, .ll-sp-closing {
      padding-left: 12px;
    }
    .ll-terms-sliver {
      border-radius: 8px;
    }
    .ll-grid {
      grid-template-columns: 1fr;
    }
    .ll-box {
      min-height: 140px;
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
      font-size: 0.82rem;
    }
    .ltd-index-active {
      border-bottom-color: #5b8af5;
      border-left-color: transparent;
    }
    .ltd-tier-terms {
      grid-template-columns: 1fr;
    }
    .lup-input {
      width: 100%;
    }
    .lup-tier-grid {
      grid-template-columns: 1fr;
    }
    .lup-downgrade-row {
      flex-wrap: wrap;
    }
    .lup-downgrade-select {
      min-width: 120px;
      flex: 1;
    }
    .lq-why-row-pair {
      flex-direction: column;
    }
  }
`;
document.head.appendChild(licStyles);
