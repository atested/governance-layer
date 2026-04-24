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
  const result = _openAsChild('Licensing', 'Plans, pricing, and license management', trigger, content);
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

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) {
    return modalManager.replaceChild({ title, subtitle, trigger, content });
  }
  return modalManager.open({ title, subtitle, trigger, content });
}

// ---------- Content shell (launcher grid) ----------

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'lic-content';
  el.innerHTML = `
    <div class="ll-status-pane">
      <div class="ll-sp-header">
        <span class="ll-sp-dot"></span>
        <span class="ll-sp-title">Atested License Status: <span class="ll-sp-tier">Loading\u2026</span></span>
      </div>
      <div class="ll-sp-intro">Your current license status:</div>
      <div class="ll-sp-grid">
        <div class="ll-sp-row" data-pane="tiers">
          <span class="ll-sp-name">Pricing</span>
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
      <div class="ll-sp-closing">Yellow below indicates action needed</div>
    </div>

    <button class="ll-terms-sliver" data-box="terms">
      <span class="ll-ts-accent"></span>
      <span class="ll-ts-left"><strong>Terms</strong> <span class="ll-ts-desc">Understand the Atested licensing lifecycle</span></span>
      <span class="ll-ts-action">Click to review</span>
    </button>

    <div class="ll-grid">
      <button class="ll-box" data-box="tiers">
        <span class="ll-accent-bar"></span>
        <span class="ll-title">Atested Pricing</span>
        <span class="ll-subtitle">Available plans</span>
        <p class="ll-desc">See what each plan includes and how they compare. Five levels from a solo user to thousands at the largest institutions, with capabilities that scale to your needs.</p>
        <span class="ll-status-line ll-s1"></span>
        <span class="ll-status-line ll-s2"></span>
        <span class="ll-status-line ll-s3"></span>
        <span class="ll-click">Click to compare plans and features</span>
      </button>
      <button class="ll-box" data-box="survey">
        <span class="ll-accent-bar"></span>
        <span class="ll-title">Atested Survey</span>
        <span class="ll-subtitle">Your intended installation</span>
        <p class="ll-desc">Tell us about your planned deployment. We use your responses to help you decide the right plan and to create your case document. The more responses you provide the more accurate our assessment will be.</p>
        <span class="ll-status-line ll-s1"></span>
        <span class="ll-status-line ll-s2"></span>
        <span class="ll-click">Click to find your plan</span>
      </button>
      <button class="ll-box" data-box="case">
        <span class="ll-accent-bar"></span>
        <span class="ll-title">Atested Case Document</span>
        <span class="ll-subtitle">Your purchase argument</span>
        <p class="ll-desc">Combining your responses with the evidence you generated in the trial, Atested creates a document you can use to communicate internally to formally move Atested into production in your environment. This is intended to make this part of your job easier.</p>
        <span class="ll-status-line ll-s1"></span>
        <span class="ll-status-line ll-s2"></span>
        <span class="ll-click">Click to review and share your case</span>
      </button>
      <button class="ll-box" data-box="purchase">
        <span class="ll-accent-bar"></span>
        <span class="ll-title">Atested License</span>
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
  const capStr = q?.capacity ? `${q.capacity.user_count} user${q.capacity.user_count !== 1 ? 's' : ''}, ${q.capacity.machine_count || 1} machine${(q.capacity.machine_count || 1) !== 1 ? 's' : ''}` : '';
  const decStr = decisions > 0 ? `${decisions.toLocaleString()} Atested decisions as evidence` : '';
  const renewalDate = md.license_expiry || '';

  const rows = {};

  // Tiers — line 1: state, line 2: capacity detail
  if (isLicensed) {
    rows.tiers = { desc: `Licensed at ${_tierLabel(licensedTier)}`, detail: '5 plans available', label: '[Current]' };
  } else if (rec) {
    rows.tiers = { desc: `${rec} recommended at ${price}`, detail: capStr || '', label: '[Recommended]' };
  } else {
    rows.tiers = { desc: 'Five plans from Personal to Institution', detail: '', label: '[Available]' };
  }

  // Survey — line 1: state, line 2: next action
  if (isLicensed) {
    rows.survey = { desc: 'Complete', detail: 'Retake if your situation changes', label: '[Complete]' };
  } else if (!q || q.state === STATES.EMPTY) {
    rows.survey = { desc: 'Not started', detail: '', label: '[Pending]' };
  } else if (q.state === STATES.CAPACITY || q.state === STATES.CLIMBING) {
    rows.survey = { desc: 'In progress', detail: '', label: '[Pending]' };
  } else if (q.state === STATES.COMPLETE) {
    rows.survey = { desc: `${rec} recommended`, detail: 'All questions answered', label: '[Complete]' };
  } else if (rec) {
    rows.survey = { desc: `${rec} recommended`, detail: p2Extra > 0 ? 'There is more you can add' : '', label: p2Extra > 0 ? '[Optional]' : '[Complete]' };
  } else {
    rows.survey = { desc: 'Not started', detail: '', label: '[Pending]' };
  }

  // Case document — line 1: state, line 2: evidence count
  if (doc?.generated_at) {
    rows.case = { desc: 'Ready', detail: decStr || 'Evidence available', label: '[Ready]' };
  } else if (rec) {
    rows.case = { desc: 'Ready to generate', detail: decStr || '', label: '[Available]' };
  } else {
    rows.case = { desc: 'Complete the survey first', detail: '', label: '[Pending]' };
  }

  // License — line 1: state, line 2: recommendation or renewal
  if (isLicensed) {
    rows.license = { desc: `Licensed: ${_tierLabel(licensedTier)}`, detail: renewalDate ? `Renewal: ${renewalDate}` : '', label: '[Active]' };
  } else if (md.registered) {
    rows.license = { desc: 'Registered \u2014 Personal (free)', detail: '', label: '[Registered]' };
  } else if (rec) {
    rows.license = { desc: 'Not yet licensed', detail: `${rec} at ${price}`, label: '[Pending]' };
  } else {
    rows.license = { desc: 'Not yet licensed', detail: '', label: '[Pending]' };
  }

  // Terms — line 1: state, no blue line
  if (termsAck) {
    rows.terms = { desc: 'Reviewed', detail: '', label: '[Reviewed]' };
  } else {
    rows.terms = { desc: 'Not reviewed', detail: '', label: '[Pending]' };
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
    if (closingEl) closingEl.textContent = agg === 'green' ? 'All panes current.' : 'Yellow below indicates action needed';

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
      if (nameEl) nameEl.textContent = { tiers: 'Pricing', survey: 'Survey', case: 'Case document', license: 'License', terms: 'Terms' }[key];
      const r = gridRows[key] || {};
      if (descEl) {
        descEl.textContent = r.desc || '';
        // Add blue detail line if present
        const existingDetail = descEl.querySelector('.ll-sp-detail');
        if (existingDetail) existingDetail.remove();
        if (r.detail) {
          const detailSpan = document.createElement('span');
          detailSpan.className = 'll-sp-detail';
          detailSpan.textContent = r.detail;
          descEl.appendChild(detailSpan);
        }
      }
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
    if (s1) { s1.textContent = bc.s1 || ''; s1.classList.remove('ll-data'); }
    if (s2) { s2.textContent = bc.s2 || ''; s2.classList.remove('ll-data'); }
    if (s3) { s3.textContent = bc.s3 || ''; s3.classList.remove('ll-data'); }
    // Mark last non-empty status line blue
    const lastData = (bc.s3 ? s3 : bc.s2 ? s2 : null);
    if (lastData) lastData.classList.add('ll-data');
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
    if (closingEl) closingEl.textContent = agg === 'green' ? 'All panes current.' : 'Yellow below indicates action needed';
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
      if (descEl) {
        descEl.textContent = r.desc || '';
        const existingDetail = descEl.querySelector('.ll-sp-detail');
        if (existingDetail) existingDetail.remove();
        if (r.detail) {
          const detailSpan = document.createElement('span');
          detailSpan.className = 'll-sp-detail';
          detailSpan.textContent = r.detail;
          descEl.appendChild(detailSpan);
        }
      }
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
    if (s1) { s1.textContent = bc.s1 || ''; s1.classList.remove('ll-data'); }
    if (s2) { s2.textContent = bc.s2 || ''; s2.classList.remove('ll-data'); }
    if (s3) { s3.textContent = bc.s3 || ''; s3.classList.remove('ll-data'); }
    const lastData = (bc.s3 ? s3 : bc.s2 ? s2 : null);
    if (lastData) lastData.classList.add('ll-data');
    if (click) click.textContent = bc.click || '';
  });

  _refreshLicenseState();
}

// ---------- Grandchild navigation ----------

function _openBoxGrandchild(boxId, trigger, state) {
  if (modalManager.depth >= 2) return;
  const titles = { tiers: 'Pricing', survey: 'Survey', case: 'Case Document', purchase: 'License', terms: 'Terms' };
  const subtitles = { tiers: 'Compare what each plan includes', survey: 'Questionnaire for plan recommendation', case: 'Your recommendation with evidence', purchase: 'Purchase and manage your license', terms: 'Atested licensing terms' };
  const content = _buildGrandchildContent(boxId, state);
  const result = modalManager.open({ title: titles[boxId] || boxId, subtitle: subtitles[boxId] || '', trigger, content });
  if (!result) return;

  // Accent color: use action-state color, not fixed pane color
  const paneStates = _computePaneStates(state);
  const paneMap = { tiers: 'tiers', survey: 'survey', case: 'case', purchase: 'license', terms: 'terms' };
  const ps = paneStates[paneMap[boxId]] || 'amber';
  const accent = ps === 'green' ? '#22c55e' : '#f5a623';
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
  const price = COMMERCIAL_TERMS[qState.recommendation]?.price || '';
  const hasLower = !!reasoning.whyNotLower;
  const hasHigher = !!reasoning.whyNotHigher;

  el.innerHTML = `
    <div class="lq-threshold">
      <div class="lqc-rec-pane">
        <div class="lqc-accent lqc-accent-green"></div>
        <div class="lqc-rec-badge">[Verified Recommendation]</div>
        <h3 class="lqc-rec-tier">${_esc(tierLabel)}</h3>
        <div class="lqc-rec-price">${_esc(price)}</div>
        <p class="lqc-rec-summary">Based on your answers, ${_esc(tierLabel)} is the right plan for your organization.</p>
      </div>

      ${(hasLower || hasHigher) ? `
        <div class="lqc-why-row">
          ${hasLower ? `
            <div class="lqc-why-pane">
              <div class="lqc-accent lqc-accent-amber"></div>
              <h4 class="lqc-why-heading">Why not a lower plan?</h4>
              <p class="lqc-why-text">${_esc(reasoning.whyNotLower)}</p>
            </div>
          ` : ''}
          ${hasHigher ? `
            <div class="lqc-why-pane">
              <div class="lqc-accent lqc-accent-green"></div>
              <h4 class="lqc-why-heading">Why not a higher plan?</h4>
              <p class="lqc-why-text">${_esc(reasoning.whyNotHigher)}</p>
            </div>
          ` : ''}
        </div>
      ` : ''}

      <div class="lqc-workflow-pane">
        <div class="lqc-accent lqc-accent-amber"></div>
        <h4 class="lqc-workflow-heading">What to do next</h4>
        <div class="lqc-action-row">
          <div class="lqc-action-card lqc-action-review">
            <div class="lqc-card-accent lqc-card-accent-green"></div>
            <h5 class="lqc-card-title">Review your case</h5>
            <p class="lqc-card-desc">Your trial generated data that shows Atested does what it says it does.</p>
            <span class="lqc-card-click lqc-nav-case">Click to review</span>
          </div>
          <div class="lqc-action-card lqc-action-strengthen">
            <div class="lqc-card-accent lqc-card-accent-amber"></div>
            <h5 class="lqc-card-title">Strengthen your case</h5>
            <p class="lqc-card-desc">Tell us more and maybe it will help make a better case, but it can\u2019t change the recommendation.</p>
            <span class="lqc-card-click lqc-nav-strengthen">Click to continue</span>
          </div>
          <div class="lqc-action-card lqc-action-restart">
            <div class="lqc-card-accent lqc-card-accent-gray"></div>
            <h5 class="lqc-card-title">Restart survey</h5>
            <p class="lqc-card-desc">If you want to start over, click here. You can do this again if you want to.</p>
            <span class="lqc-card-click lqc-nav-restart">Click to restart</span>
          </div>
        </div>
      </div>
    </div>
  `;

  el.querySelector('.lqc-nav-case').addEventListener('click', () => {
    _switchPanel(appState, 'case-document');
  });

  el.querySelector('.lqc-nav-strengthen').addEventListener('click', () => {
    const p2State = { ...qState, state: STATES.PHASE_TWO };
    p2State.nextQuestion = getNextPhaseTwoQuestion(qState.recommendation, qState.answers);
    _renderQuestionnaireState(el, p2State, appState);
  });

  el.querySelector('.lqc-nav-restart').addEventListener('click', () => {
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
        <span class="lqc-rec-badge" style="font-size:0.82rem;padding:3px 10px;">
          [Recommendation verified: ${_esc(tierLabel)}]
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
  const price = COMMERCIAL_TERMS[qState.recommendation]?.price || '';
  const reasoning = thresholdReasoning(qState);
  const hasLower = !!reasoning.whyNotLower;
  const hasHigher = !!reasoning.whyNotHigher;

  el.innerHTML = `
    <div class="lq-threshold">
      <div class="lqc-rec-pane">
        <div class="lqc-accent lqc-accent-green"></div>
        <div class="lqc-rec-badge">[Verified Recommendation]</div>
        <h3 class="lqc-rec-tier">${_esc(tierLabel)}</h3>
        <div class="lqc-rec-price">${_esc(price)}</div>
        <p class="lqc-rec-summary">Based on your answers, ${_esc(tierLabel)} is the right plan for your organization.</p>
      </div>

      ${(hasLower || hasHigher) ? `
        <div class="lqc-why-row">
          ${hasLower ? `
            <div class="lqc-why-pane">
              <div class="lqc-accent lqc-accent-amber"></div>
              <h4 class="lqc-why-heading">Why not a lower plan?</h4>
              <p class="lqc-why-text">${_esc(reasoning.whyNotLower)}</p>
            </div>
          ` : ''}
          ${hasHigher ? `
            <div class="lqc-why-pane">
              <div class="lqc-accent lqc-accent-green"></div>
              <h4 class="lqc-why-heading">Why not a higher plan?</h4>
              <p class="lqc-why-text">${_esc(reasoning.whyNotHigher)}</p>
            </div>
          ` : ''}
        </div>
      ` : ''}

      <div class="lqc-workflow-pane">
        <div class="lqc-accent lqc-accent-amber"></div>
        <h4 class="lqc-workflow-heading">What to do next</h4>
        <div class="lqc-action-row">
          <div class="lqc-action-card lqc-action-review">
            <div class="lqc-card-accent lqc-card-accent-green"></div>
            <h5 class="lqc-card-title">Review your case</h5>
            <p class="lqc-card-desc">Your trial generated data that shows Atested does what it says it does.</p>
            <span class="lqc-card-click lqc-nav-case">Click to review</span>
          </div>
          <div class="lqc-action-card lqc-action-strengthen">
            <div class="lqc-card-accent lqc-card-accent-amber"></div>
            <h5 class="lqc-card-title">Strengthen your case</h5>
            <p class="lqc-card-desc">Tell us more and maybe it will help make a better case, but it can\u2019t change the recommendation.</p>
            <span class="lqc-card-click lqc-nav-strengthen">Click to continue</span>
          </div>
          <div class="lqc-action-card lqc-action-restart">
            <div class="lqc-card-accent lqc-card-accent-gray"></div>
            <h5 class="lqc-card-title">Restart survey</h5>
            <p class="lqc-card-desc">If you want to start over, click here. You can do this again if you want to.</p>
            <span class="lqc-card-click lqc-nav-restart">Click to restart</span>
          </div>
        </div>
      </div>
    </div>
  `;

  el.querySelector('.lqc-nav-case').addEventListener('click', () => {
    _switchPanel(appState, 'case-document');
  });

  el.querySelector('.lqc-nav-strengthen').addEventListener('click', () => {
    _switchPanel(appState, 'questionnaire');
  });

  el.querySelector('.lqc-nav-restart').addEventListener('click', () => {
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

// Compute license period dates for a tier
function _computeLicenseDates(tier, state) {
  const now = new Date();
  const fmt = d => d.toISOString().slice(0, 10);
  const addYear = d => { const r = new Date(d); r.setFullYear(r.getFullYear() + 1); return r; };

  if (tier === 'personal' || tier === 'personal_plus') {
    return { start: fmt(now), end: fmt(addYear(now)) };
  }
  // Crew, Team: date from trial completion if available
  const tc = state.modeData?.trial_completion_date;
  if (tc) {
    const tcDate = new Date(tc);
    return { start: fmt(tcDate), end: fmt(addYear(tcDate)) };
  }
  return { start: fmt(now), end: fmt(addYear(now)) };
}

function _renderUnifiedPurchase(el, state) {
  const modeData = state.modeData || {};
  const currentTier = modeData.license_tier || '';
  const currentStatus = modeData.license_status || '';
  const isLicensed = currentStatus === 'licensed';
  const isRegistered = modeData.registered === true;
  const operatorName = modeData.operator_name || '';

  const TIER_ORDER = ['personal', 'personal_plus', 'crew', 'team', 'institution'];
  const currentIdx = TIER_ORDER.indexOf(currentTier);

  // Determine recommended tier from survey
  const recTier = state.qState?.recommendation || null;

  // Initial selection: recommended > next above current > personal
  let selectedTier = recTier || 'personal';
  if (isLicensed) {
    selectedTier = (TIER_ORDER.find(t => TIER_ORDER.indexOf(t) > currentIdx)) || 'institution';
  }

  // Form data object — persists across tier switches
  const formData = {
    operator_name: operatorName,
    operator_role: modeData.operator_role || '',
    how_found: modeData.how_found || '',
    deciding_factor: modeData.deciding_factor || '',
    biggest_insight: modeData.biggest_insight || '',
    organization_name: modeData.organization_name || '',
    industry_sector: modeData.industry_sector || '',
    billing_contact: modeData.billing_contact || '',
    primary_operator: modeData.primary_operator || '',
    telemetry_opted_in: modeData.telemetry_opted_in !== false,
    research_opted_in: modeData.research_opted_in !== false,
    // Institution questions
    simultaneous_policies: '',
    cross_jurisdiction: '',
    certification_value: '',
    data_residency: '',
  };

  el.innerHTML = '';

  // If post-purchase/registered, render management view
  if (isLicensed || isRegistered) {
    _renderManagementView(el, state, formData, selectedTier);
    return;
  }

  // --- Pre-purchase flow ---

  // 3A. Context pane
  const recLabel = recTier ? (TIER_LABELS[recTier] || _tierLabel(recTier)) : null;
  const recPrice = recTier ? (COMMERCIAL_TERMS[recTier]?.price || '') : '';
  const contextText = recLabel
    ? `Your survey recommends <strong>${_esc(recLabel)}</strong>${recPrice ? ` at <strong>${_esc(recPrice)}</strong>/yr` : ''}. Select any plan below.`
    : 'Select a plan below.';

  // 3B. Plan selector — five full-width panes
  let selectorHtml = '';
  for (const t of _TIER_SELECTOR) {
    const isCurrent = isLicensed && t.id === currentTier;
    const isRec = t.id === recTier;
    const isSelected = t.id === selectedTier;
    const belowCurrent = isLicensed && TIER_ORDER.indexOf(t.id) <= currentIdx;
    let badgeHtml = '';
    if (isCurrent) badgeHtml = '<span class="lup-sel-badge lup-sel-badge-current">[CURRENT]</span>';
    else if (isRec) badgeHtml = '<span class="lup-sel-badge lup-sel-badge-rec">[RECOMMENDED]</span>';

    selectorHtml += `<button class="lup-sel-row${isSelected ? ' lup-sel-active' : ''}${isRec && !isCurrent ? ' lup-sel-recommended' : ''}${belowCurrent ? ' lup-sel-disabled' : ''}" data-tier="${t.id}" ${belowCurrent ? 'disabled' : ''}>
      <span class="lup-sel-name">${_esc(t.name)}</span>
      <span class="lup-sel-spec">${_esc(t.spec)}</span>
      <span class="lup-sel-price">${_esc(t.price)}</span>
      ${badgeHtml}
    </button>`;
  }

  el.innerHTML = `
    <div class="lup-context"><div class="lup-context-bar"></div><p class="lup-context-text">${contextText}</p></div>
    <div class="lup-selector">${selectorHtml}</div>
    <div class="lup-body-area"></div>
    <div class="lup-confirm-dialog" style="display:none"></div>
    <div class="lup-error" style="display:none"></div>
  `;

  // Render body for initial selection
  _renderPurchaseBody(el, selectedTier, formData, state);

  // Wire selector clicks
  el.querySelectorAll('.lup-sel-row:not([disabled])').forEach(btn => {
    btn.addEventListener('click', () => {
      el.querySelectorAll('.lup-sel-row').forEach(b => b.classList.remove('lup-sel-active'));
      btn.classList.add('lup-sel-active');
      selectedTier = btn.dataset.tier;
      _renderPurchaseBody(el, selectedTier, formData, state);
    });
  });
}

// ---------- Purchase body: About You + Communication/Research + Purchase pane ----------

function _renderPurchaseBody(el, tier, formData, state) {
  const bodyArea = el.querySelector('.lup-body-area');
  if (!bodyArea) return;

  const isInstitution = tier === 'institution';
  const isPersonal = tier === 'personal';
  const isCrew = tier === 'crew' || tier === 'team' || tier === 'institution';
  const isTeam = tier === 'team' || tier === 'institution';
  const terms = COMMERCIAL_TERMS[tier] || {};
  const price = terms.price || (isPersonal ? 'Free' : '');
  const isLicensed = (state.modeData?.license_status === 'licensed');
  const dates = _computeLicenseDates(tier, state);

  // --- Left column: About You ---
  let aboutFields = `
    <div class="lup-field">
      <label class="lup-label">Your name</label>
      <input class="lup-input lup-input-wide" data-field="operator_name" type="text" placeholder="e.g. your name or handle" value="${_esc(formData.operator_name)}" autocomplete="off" />
    </div>
    <div class="lup-field">
      <label class="lup-label">Your role</label>
      <input class="lup-input lup-input-wide" data-field="operator_role" type="text" placeholder="e.g. developer, security engineer, CTO" value="${_esc(formData.operator_role)}" autocomplete="off" />
    </div>
    <div class="lup-field">
      <label class="lup-label">How did you find Atested?</label>
      <input class="lup-input lup-input-wide" data-field="how_found" type="text" placeholder="e.g. colleague, search, conference" value="${_esc(formData.how_found)}" autocomplete="off" />
    </div>
    <div class="lup-field">
      <label class="lup-label">What was the deciding factor?</label>
      <input class="lup-input lup-input-wide" data-field="deciding_factor" type="text" placeholder="e.g. governance chain, auditability" value="${_esc(formData.deciding_factor)}" autocomplete="off" />
    </div>
    <div class="lup-field">
      <label class="lup-label">For you, what is the single biggest insight you have had about AI tech?</label>
      <textarea class="lup-textarea" data-field="biggest_insight" rows="3" placeholder="Share your perspective">${_esc(formData.biggest_insight)}</textarea>
    </div>
  `;

  if (isCrew) {
    aboutFields += `
      <div class="lup-field">
        <label class="lup-label">Organization name</label>
        <input class="lup-input lup-input-wide" data-field="organization_name" type="text" placeholder="Your organization" value="${_esc(formData.organization_name)}" autocomplete="off" />
      </div>
      <div class="lup-field">
        <label class="lup-label">Industry or sector</label>
        <input class="lup-input lup-input-wide" data-field="industry_sector" type="text" placeholder="e.g. fintech, healthcare, government" value="${_esc(formData.industry_sector)}" autocomplete="off" />
      </div>
      <div class="lup-field">
        <label class="lup-label">Billing contact if different from you</label>
        <input class="lup-input lup-input-wide" data-field="billing_contact" type="text" placeholder="Name or email" value="${_esc(formData.billing_contact)}" autocomplete="off" />
      </div>
    `;
  }

  if (isTeam) {
    aboutFields += `
      <div class="lup-field">
        <label class="lup-label">Primary operator's name</label>
        <input class="lup-input lup-input-wide" data-field="primary_operator" type="text" placeholder="The person who will manage the license" value="${_esc(formData.primary_operator)}" autocomplete="off" />
      </div>
    `;
  }

  // --- Right column: Communication + Research ---
  const commHtml = `
    <div class="lup-pane">
      <div class="lup-pane-bar lup-pane-bar-amber"></div>
      <h4 class="lup-pane-heading">Communication</h4>
      <p class="lup-pane-desc">Atested maintains a bidirectional telemetry channel. Participating operators share anonymous, aggregated usage data and receive shared insights and routine notifications in return.</p>
      <div class="lup-card-options">
        <button class="lup-card-option${formData.telemetry_opted_in ? ' lup-card-selected' : ''}" data-comm="in">
          <span class="lup-card-title">Participate</span>
          <span class="lup-card-hint">Share anonymous data. Receive community insights.</span>
        </button>
        <button class="lup-card-option${!formData.telemetry_opted_in ? ' lup-card-selected' : ''}" data-comm="out">
          <span class="lup-card-title">Decline</span>
          <span class="lup-card-hint">No data shared. Critical notifications continue.</span>
        </button>
      </div>
      <p class="lup-pane-note">You can change this choice at any time.</p>
    </div>
  `;

  const researchHtml = `
    <div class="lup-pane">
      <div class="lup-pane-bar lup-pane-bar-blue"></div>
      <h4 class="lup-pane-heading">Research program</h4>
      <p class="lup-pane-desc">Often we invite clients to help us evaluate a new AI application we are developing. These are in-house developed applications that are often high-concept prototypes. Not everyone will want to play, so if it is not right for you, no worries.</p>
      <div class="lup-card-options">
        <button class="lup-card-option${formData.research_opted_in ? ' lup-card-selected' : ''}" data-research="in">
          <span class="lup-card-title">I am open to this</span>
          <span class="lup-card-hint">You may be contacted about research participation.</span>
        </button>
        <button class="lup-card-option${!formData.research_opted_in ? ' lup-card-selected' : ''}" data-research="out">
          <span class="lup-card-title">Not right now</span>
          <span class="lup-card-hint">No research contact. You can opt in later.</span>
        </button>
      </div>
    </div>
  `;

  // --- Purchase pane ---
  let purchaseHtml = '';
  if (isInstitution) {
    purchaseHtml = _buildInstitutionQuestions(formData);
  } else {
    const actionLabel = isPersonal
      ? 'Register \u2014 Free'
      : `${isLicensed ? 'Upgrade to' : 'Purchase'} ${_tierLabel(tier)} \u2014 ${price}`;

    purchaseHtml = `
      <div class="lup-purchase-pane">
        <div class="lup-pane-bar lup-pane-bar-green"></div>
        <div class="lup-purchase-header">
          <span class="lup-purchase-plan">${_esc(_tierLabel(tier))}</span>
          <span class="lup-purchase-price">${_esc(price)}</span>
          <span class="lup-purchase-billing">${isPersonal ? 'Free forever' : (terms.billing || 'Annual billing')}</span>
        </div>
        <div class="lup-purchase-dates">License period: <span class="lup-date-blue">${_esc(dates.start)}</span> to <span class="lup-date-blue">${_esc(dates.end)}</span></div>
        <button class="lic-action-btn lic-action-primary lup-action-btn">${_esc(actionLabel)}</button>
        <div class="lup-purchase-divider"></div>
        <button class="lup-invoice-btn lup-invoice-disabled" disabled>Invoice available after purchase</button>
        <div class="lup-action-error" style="display:none"></div>
      </div>
    `;
  }

  bodyArea.innerHTML = `
    <div class="lup-columns">
      <div class="lup-col-left">
        <div class="lup-pane">
          <div class="lup-pane-bar lup-pane-bar-amber"></div>
          <h4 class="lup-pane-heading">About you</h4>
          <div class="lup-about-fields">${aboutFields}</div>
        </div>
      </div>
      <div class="lup-col-right">
        ${commHtml}
        ${researchHtml}
      </div>
    </div>
    ${purchaseHtml}
    <details class="lup-activate-collapsible">
      <summary class="lup-activate-summary">Already have a license key?</summary>
      <div class="lup-activate-section lup-activate-inline">
        <p class="lup-section-desc">Paste a license key or upload a <code>.key</code> file to activate.</p>
        <textarea class="lup-activate-textarea lup-activate-prepurchase" rows="3" placeholder="Paste license key here\u2026"></textarea>
        <input type="file" class="lup-activate-file lup-activate-prepurchase-file" accept=".key,.txt" style="margin-top:8px;font-size:0.82rem;color:#8b919a;">
        <div class="lup-activate-preview lup-activate-prepurchase-preview" style="display:none"></div>
        <div class="lup-activate-error lup-activate-prepurchase-error" style="display:none"></div>
        <button class="lic-action-btn lic-action-primary lup-activate-prepurchase-btn" disabled style="margin-top:10px">Activate</button>
      </div>
    </details>
    <details class="lup-activate-collapsible">
      <summary class="lup-activate-summary">Join a license on this network</summary>
      <div class="lup-join-section">
        <p class="lup-section-desc">Enter the address shown on the sharing machine's dashboard.</p>
        <div class="lup-join-row">
          <input class="lup-input lup-join-input" type="text" placeholder="192.168.1.5:54321">
          <button class="lic-action-btn lic-action-primary lup-join-btn">Join</button>
        </div>
        <button class="lic-action-btn lup-discover-btn">Scan network</button>
        <div class="lup-join-peers" style="display:none"></div>
        <div class="lup-join-status" style="display:none"></div>
        <div class="lup-join-error" style="display:none"></div>
      </div>
    </details>
  `;

  // Wire pre-purchase activate-with-key
  {
    const ppTextarea = bodyArea.querySelector('.lup-activate-prepurchase');
    const ppPreview = bodyArea.querySelector('.lup-activate-prepurchase-preview');
    const ppError = bodyArea.querySelector('.lup-activate-prepurchase-error');
    const ppBtn = bodyArea.querySelector('.lup-activate-prepurchase-btn');
    const ppFile = bodyArea.querySelector('.lup-activate-prepurchase-file');
    let ppTimer = null;

    if (ppTextarea) {
      ppTextarea.addEventListener('input', () => {
        clearTimeout(ppTimer);
        ppTimer = setTimeout(async () => {
          const key = ppTextarea.value.trim();
          ppPreview.style.display = 'none';
          ppError.style.display = 'none';
          ppBtn.disabled = true;
          if (!key) return;
          try {
            const res = await api.postVerifyLicense({ license_key: key });
            if (res.ok && res.data && !res.data.error) {
              if (res.data.expired) {
                ppError.textContent = 'This token has expired.';
                ppError.style.display = '';
              } else {
                ppPreview.textContent = `Tier: ${res.data.tier || 'N/A'} \u2022 Expires: ${(res.data.expiry_iso || res.data.expiry || '').slice(0, 10) || 'N/A'}`;
                ppPreview.style.display = '';
                ppBtn.disabled = false;
              }
            } else {
              ppError.textContent = 'Invalid token.';
              ppError.style.display = '';
            }
          } catch {
            ppError.textContent = 'Validation failed.';
            ppError.style.display = '';
          }
        }, 300);
      });
    }

    if (ppFile) {
      ppFile.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = () => {
          if (ppTextarea) {
            ppTextarea.value = reader.result;
            ppTextarea.dispatchEvent(new Event('input'));
          }
        };
        reader.readAsText(file);
      });
    }

    if (ppBtn) {
      ppBtn.addEventListener('click', async () => {
        const key = ppTextarea ? ppTextarea.value.trim() : '';
        if (!key) return;
        ppBtn.disabled = true;
        ppError.style.display = 'none';
        try {
          const res = await api.postActivateWithKey({ license_key: key });
          if (res.ok && res.data && res.data.ok) {
            await _refreshLicenseState();
            _loadUnifiedPurchase(el, state);
          } else {
            ppError.textContent = (res.data && res.data.error) || 'Activation failed.';
            ppError.style.display = '';
            ppBtn.disabled = false;
          }
        } catch {
          ppError.textContent = 'Activation request failed.';
          ppError.style.display = '';
          ppBtn.disabled = false;
        }
      });
    }
  }

  // Wire form field syncing
  bodyArea.querySelectorAll('[data-field]').forEach(input => {
    const field = input.dataset.field;
    input.addEventListener('input', () => { formData[field] = input.value.trim(); });
  });

  // Wire communication cards
  bodyArea.querySelectorAll('[data-comm]').forEach(btn => {
    btn.addEventListener('click', () => {
      formData.telemetry_opted_in = btn.dataset.comm === 'in';
      bodyArea.querySelectorAll('[data-comm]').forEach(b =>
        b.classList.toggle('lup-card-selected', b === btn)
      );
    });
  });

  // Wire research cards
  bodyArea.querySelectorAll('[data-research]').forEach(btn => {
    btn.addEventListener('click', () => {
      formData.research_opted_in = btn.dataset.research === 'in';
      bodyArea.querySelectorAll('[data-research]').forEach(b =>
        b.classList.toggle('lup-card-selected', b === btn)
      );
    });
  });

  // Wire purchase/register action (non-institution)
  if (!isInstitution) {
    _wirePurchaseAction(bodyArea, el, tier, formData, state);
  } else {
    _wireInstitutionSubmit(bodyArea, el, formData, state);
  }

  // Wire join-a-license flow
  const joinBtn = bodyArea.querySelector('.lup-join-btn');
  const joinInput = bodyArea.querySelector('.lup-join-input');
  const joinStatus = bodyArea.querySelector('.lup-join-status');
  const joinError = bodyArea.querySelector('.lup-join-error');
  const joinPeers = bodyArea.querySelector('.lup-join-peers');
  const discoverBtn = bodyArea.querySelector('.lup-discover-btn');

  if (joinBtn && joinInput) {
    joinBtn.addEventListener('click', async () => {
      const address = joinInput.value.trim();
      if (!address) return;
      joinError.style.display = 'none';
      joinStatus.style.display = '';
      joinStatus.textContent = 'Connecting\u2026';
      joinBtn.disabled = true;

      const res = await api.postJoinLicense({ address });
      if (!res.ok || res.data?.error) {
        joinError.textContent = res.data?.error || res.error || 'Connection failed';
        joinError.style.display = '';
        joinStatus.style.display = 'none';
        joinBtn.disabled = false;
        return;
      }

      joinStatus.textContent = 'Waiting for approval\u2026';
      // Operator-initiated bounded poll: auto-terminates on approved/denied/timeout.
      // Acceptable per v4 §8 — operator explicitly triggered this flow.
      const pollId = setInterval(async () => {
        const sr = await api.getJoinStatus();
        if (!sr.ok) return;
        const st = sr.data.status;
        if (st === 'approved') {
          clearInterval(pollId);
          joinStatus.textContent = 'Approved! License activated.';
          joinStatus.style.color = '#4ade80';
          await _refreshLicenseState();
          setTimeout(() => _loadUnifiedPurchase(el, state), 1500);
        } else if (st === 'denied') {
          clearInterval(pollId);
          joinError.textContent = 'Request was denied by the sharing machine.';
          joinError.style.display = '';
          joinStatus.style.display = 'none';
          joinBtn.disabled = false;
        } else if (st === 'timeout') {
          clearInterval(pollId);
          joinError.textContent = 'Sharing server timed out.';
          joinError.style.display = '';
          joinStatus.style.display = 'none';
          joinBtn.disabled = false;
        }
      }, 2000);
    });
  }

  if (discoverBtn) {
    discoverBtn.addEventListener('click', async () => {
      discoverBtn.disabled = true;
      discoverBtn.textContent = 'Scanning\u2026';
      await api.postStartDiscovery();
      // Poll for discovered peers for 8 seconds
      let checks = 0;
      const discPoll = setInterval(async () => {
        checks++;
        const sr = await api.getJoinStatus();
        if (sr.ok && sr.data) {
          const mgr = sr.data;
          // Check discovered_peers via machines endpoint or through join-status
          // The peers come from the manager state returned in join-status when discovering
        }
        if (checks >= 4) {
          clearInterval(discPoll);
          // Fetch final discovered peers via sharing status
          const sr2 = await api.getSharingStatus();
          discoverBtn.disabled = false;
          discoverBtn.textContent = 'Scan network';
          // Show peers from join-status discovered_peers
          // For now, the discover results flow through the manager
        }
      }, 2000);
    });
  }
}

function _buildInstitutionQuestions(formData) {
  return `
    <div class="lup-purchase-pane lup-inst-questions">
      <div class="lup-pane-bar lup-pane-bar-green"></div>
      <h4 class="lup-pane-heading">Institution \u2014 Let's start a conversation</h4>
      <div class="lup-field">
        <label class="lup-label">How many distinct governance policies does your organization need to maintain simultaneously?</label>
        <input class="lup-input lup-input-wide" data-inst="simultaneous_policies" type="text" placeholder="e.g. 3, 10+" value="${_esc(formData.simultaneous_policies)}" autocomplete="off" />
      </div>
      <div class="lup-field">
        <label class="lup-label">Do your AI application operations cross regulatory jurisdictions?</label>
        <div class="lup-yn-row">
          <button class="lup-yn-btn${formData.cross_jurisdiction === 'yes' ? ' lup-yn-active' : ''}" data-inst-yn="cross_jurisdiction" data-val="yes">Yes</button>
          <button class="lup-yn-btn${formData.cross_jurisdiction === 'no' ? ' lup-yn-active' : ''}" data-inst-yn="cross_jurisdiction" data-val="no">No</button>
        </div>
      </div>
      <div class="lup-field">
        <label class="lup-label">Would independent certification of your governance chain data be valuable for your legal or compliance requirements?</label>
        <div class="lup-yn-row">
          <button class="lup-yn-btn${formData.certification_value === 'yes' ? ' lup-yn-active' : ''}" data-inst-yn="certification_value" data-val="yes">Yes</button>
          <button class="lup-yn-btn${formData.certification_value === 'no' ? ' lup-yn-active' : ''}" data-inst-yn="certification_value" data-val="no">No</button>
        </div>
      </div>
      <div class="lup-field">
        <label class="lup-label">Does your organization require on-premises deployment or do you have flexibility on data residency?</label>
        <input class="lup-input lup-input-wide" data-inst="data_residency" type="text" placeholder="e.g. on-premises required, cloud OK, hybrid" value="${_esc(formData.data_residency)}" autocomplete="off" />
      </div>
      <p class="lup-pane-desc">We'll use your answers and About You information to prepare a tailored proposal.</p>
      <button class="lic-action-btn lic-action-primary lup-inst-submit-btn">Submit for proposal</button>
      <div class="lup-action-error" style="display:none"></div>
    </div>
  `;
}

function _wireInstitutionSubmit(bodyArea, el, formData, state) {
  // Wire institution text inputs
  bodyArea.querySelectorAll('[data-inst]').forEach(input => {
    const field = input.dataset.inst;
    input.addEventListener('input', () => { formData[field] = input.value.trim(); });
  });

  // Wire yes/no buttons
  bodyArea.querySelectorAll('[data-inst-yn]').forEach(btn => {
    btn.addEventListener('click', () => {
      const field = btn.dataset.instYn;
      formData[field] = btn.dataset.val;
      bodyArea.querySelectorAll(`[data-inst-yn="${field}"]`).forEach(b =>
        b.classList.toggle('lup-yn-active', b === btn)
      );
    });
  });

  const submitBtn = bodyArea.querySelector('.lup-inst-submit-btn');
  const errorEl = bodyArea.querySelector('.lup-action-error');

  submitBtn?.addEventListener('click', async () => {
    if (!formData.operator_name) {
      errorEl.textContent = 'Please enter your name in the About You section.';
      errorEl.style.display = '';
      return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting\u2026';
    errorEl.style.display = 'none';

    const res = await api.postInstitutionInquiry({
      operator_name: formData.operator_name,
      operator_role: formData.operator_role,
      how_found: formData.how_found,
      deciding_factor: formData.deciding_factor,
      biggest_insight: formData.biggest_insight,
      organization_name: formData.organization_name,
      industry_sector: formData.industry_sector,
      billing_contact: formData.billing_contact,
      primary_operator: formData.primary_operator,
      research_opted_in: formData.research_opted_in,
      simultaneous_policies: formData.simultaneous_policies,
      cross_jurisdiction: formData.cross_jurisdiction,
      certification_value: formData.certification_value,
      data_residency: formData.data_residency,
    });

    if (!res.ok) {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit for proposal';
      errorEl.textContent = res.error || 'Submission failed.';
      errorEl.style.display = '';
      return;
    }

    submitBtn.textContent = 'Submitted';
    submitBtn.style.background = 'rgba(34, 197, 94, 0.15)';
    submitBtn.style.color = '#22c55e';
    submitBtn.style.borderColor = 'rgba(34, 197, 94, 0.3)';
  });
}

function _wirePurchaseAction(bodyArea, el, tier, formData, state) {
  const actionBtn = bodyArea.querySelector('.lup-action-btn');
  const errorEl = bodyArea.querySelector('.lup-action-error');
  if (!actionBtn) return;

  const isPersonal = tier === 'personal';
  const isLicensed = (state.modeData?.license_status === 'licensed');
  const terms = COMMERCIAL_TERMS[tier] || {};
  const price = terms.price || 'Free';
  const actionLabel = isPersonal
    ? 'Register \u2014 Free'
    : `${isLicensed ? 'Upgrade to' : 'Purchase'} ${_tierLabel(tier)} \u2014 ${price}`;

  actionBtn.addEventListener('click', async () => {
    if (!formData.operator_name) {
      errorEl.textContent = 'Please enter your name in the About You section.';
      errorEl.style.display = '';
      return;
    }
    if (!state.modeData?.terms_acknowledged) {
      errorEl.textContent = 'Review the licensing terms first. Close this window and click the Terms pane.';
      errorEl.style.display = '';
      return;
    }

    actionBtn.disabled = true;
    actionBtn.textContent = 'Processing\u2026';
    errorEl.style.display = 'none';

    const ciFields = {
      operator_role: formData.operator_role,
      how_found: formData.how_found,
      deciding_factor: formData.deciding_factor,
      biggest_insight: formData.biggest_insight,
      research_opted_in: formData.research_opted_in,
    };
    if (formData.organization_name) ciFields.organization_name = formData.organization_name;
    if (formData.industry_sector) ciFields.industry_sector = formData.industry_sector;
    if (formData.billing_contact) ciFields.billing_contact = formData.billing_contact;
    if (formData.primary_operator) ciFields.primary_operator = formData.primary_operator;

    if (isPersonal) {
      const res = await api.postRegister({
        operator_name: formData.operator_name,
        context_note: '',
        telemetry_opted_in: formData.telemetry_opted_in,
        ...ciFields,
      });

      if (!res.ok) {
        actionBtn.disabled = false;
        actionBtn.textContent = actionLabel;
        errorEl.textContent = res.error || 'Registration failed.';
        errorEl.style.display = '';
        return;
      }

      _refreshLicenseState();
      _loadUnifiedPurchase(el, state);
    } else {
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
        operator_name: formData.operator_name,
        ...ciFields,
      });

      if (!res.ok) {
        actionBtn.disabled = false;
        actionBtn.textContent = actionLabel;
        errorEl.textContent = res.error || 'Purchase failed.';
        errorEl.style.display = '';
        return;
      }

      _refreshLicenseState();
      _loadUnifiedPurchase(el, state);
    }
  });
}

// ---------- Post-purchase management view ----------

function _renderManagementView(el, state, formData, upgradeTarget) {
  const modeData = state.modeData || {};
  const currentTier = modeData.license_tier || 'personal';
  const isLicensed = modeData.license_status === 'licensed';
  const TIER_ORDER = ['personal', 'personal_plus', 'crew', 'team', 'institution'];
  const currentIdx = TIER_ORDER.indexOf(currentTier);
  const purchaseDate = (modeData.purchase_date || modeData.registration_date || '').slice(0, 10) || 'N/A';
  const expiryDate = (modeData.license_expiry || '').slice(0, 10) || 'N/A';
  const autoRenewal = modeData.auto_renewal !== false;
  const operatorName = modeData.operator_name || '';

  // Plan selector — informational
  let selectorHtml = '';
  for (const t of _TIER_SELECTOR) {
    const isCurrent = t.id === currentTier;
    const isAbove = TIER_ORDER.indexOf(t.id) > currentIdx;
    let badgeHtml = '';
    if (isCurrent) badgeHtml = '<span class="lup-sel-badge lup-sel-badge-current">[CURRENT]</span>';

    selectorHtml += `<button class="lup-sel-row${isCurrent ? ' lup-sel-active' : ''}${!isAbove && !isCurrent ? ' lup-sel-disabled' : ''}" data-tier="${t.id}" ${!isAbove && !isCurrent ? 'disabled' : ''}>
      <span class="lup-sel-name">${_esc(t.name)}</span>
      <span class="lup-sel-spec">${_esc(t.spec)}</span>
      <span class="lup-sel-price">${_esc(t.price)}</span>
      ${badgeHtml}
    </button>`;
  }

  // About You — readonly with edit toggle
  const readonlyFields = [
    { label: 'Name', value: operatorName },
    { label: 'Role', value: modeData.operator_role || '' },
    { label: 'How found', value: modeData.how_found || '' },
    { label: 'Deciding factor', value: modeData.deciding_factor || '' },
    { label: 'Biggest insight', value: modeData.biggest_insight || '' },
  ];
  if (modeData.organization_name) readonlyFields.push({ label: 'Organization', value: modeData.organization_name });
  if (modeData.industry_sector) readonlyFields.push({ label: 'Industry', value: modeData.industry_sector });
  if (modeData.billing_contact) readonlyFields.push({ label: 'Billing contact', value: modeData.billing_contact });
  if (modeData.primary_operator) readonlyFields.push({ label: 'Primary operator', value: modeData.primary_operator });

  let aboutHtml = readonlyFields
    .filter(f => f.value)
    .map(f => `<div class="lup-mgmt-row"><span class="lup-mgmt-label">${_esc(f.label)}</span><span class="lup-mgmt-value">${_esc(f.value)}</span></div>`)
    .join('');

  // Renewal section varies by tier
  const showAutoRenewal = currentTier === 'personal_plus';
  const showRenewalGuidance = ['crew', 'team', 'institution'].includes(currentTier);

  el.innerHTML = `
    <div class="lup-context"><div class="lup-context-bar lup-context-bar-green"></div><p class="lup-context-text">Your <strong>${_esc(_tierLabel(currentTier))}</strong> license is active.</p></div>
    <div class="lup-selector">${selectorHtml}</div>
    <div class="lup-columns">
      <div class="lup-col-left">
        <div class="lup-pane">
          <div class="lup-pane-bar lup-pane-bar-amber"></div>
          <h4 class="lup-pane-heading">Customer record</h4>
          <div class="lup-mgmt-card">${aboutHtml || '<span class="lup-pane-desc">No customer information on file.</span>'}</div>
        </div>
      </div>
      <div class="lup-col-right">
        <div class="lup-pane">
          <div class="lup-pane-bar lup-pane-bar-amber"></div>
          <h4 class="lup-pane-heading">Communication</h4>
          <div class="lup-card-options">
            <button class="lup-card-option${formData.telemetry_opted_in ? ' lup-card-selected' : ''}" data-comm="in">
              <span class="lup-card-title">Participating</span>
            </button>
            <button class="lup-card-option${!formData.telemetry_opted_in ? ' lup-card-selected' : ''}" data-comm="out">
              <span class="lup-card-title">Declined</span>
            </button>
          </div>
        </div>
        <div class="lup-pane">
          <div class="lup-pane-bar lup-pane-bar-blue"></div>
          <h4 class="lup-pane-heading">Research program</h4>
          <div class="lup-card-options">
            <button class="lup-card-option${formData.research_opted_in ? ' lup-card-selected' : ''}" data-research="in">
              <span class="lup-card-title">Opted in</span>
            </button>
            <button class="lup-card-option${!formData.research_opted_in ? ' lup-card-selected' : ''}" data-research="out">
              <span class="lup-card-title">Not participating</span>
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="lup-purchase-pane">
      <div class="lup-pane-bar lup-pane-bar-green"></div>
      <div class="lup-purchase-header">
        <span class="lup-purchase-plan">${_esc(_tierLabel(currentTier))}</span>
        <span class="lup-purchase-billing">Renewal: ${_esc(expiryDate)}</span>
      </div>
      ${showAutoRenewal ? `
      <div class="lup-renewal-section">
        <div class="lup-renewal-status">
          <span class="lup-renewal-dot" style="background: ${autoRenewal ? '#22c55e' : '#f5a623'}"></span>
          <span>Auto-renewal ${autoRenewal ? 'enabled' : 'disabled'}</span>
        </div>
        <button class="lic-action-btn lup-renewal-toggle">${autoRenewal ? 'Turn Off' : 'Turn On'}</button>
      </div>
      ` : ''}
      ${showRenewalGuidance ? `
      <div class="lup-renewal-guidance">
        <p class="lup-renewal-guidance-text">Review your case document before renewal to confirm your plan is still the right fit.</p>
      </div>
      ` : ''}
      <div class="lup-purchase-divider"></div>
      <button class="lup-invoice-btn" data-tier="${currentTier}" data-start="${purchaseDate}" data-end="${expiryDate}" data-name="${_esc(operatorName)}">Download invoice</button>
      <div class="lup-token-section">
        <h4 class="lup-section-heading">License files</h4>
        <p class="lup-section-desc">Download your license certificate or token file for safekeeping. You'll need the token if you reinstall Atested on a new machine.</p>
        <div class="lup-token-actions">
          <button class="lup-invoice-btn lup-download-cert-btn">Download certificate</button>
          <button class="lup-invoice-btn lup-download-token-btn${modeData.license_key ? '' : ' lup-invoice-disabled'}">Download token</button>
        </div>
      </div>
    </div>
    <div class="lup-activate-section">
      <div class="lup-pane-bar lup-pane-bar-blue"></div>
      <h4 class="lup-pane-heading">Activate with license key</h4>
      <p class="lup-section-desc">Paste a license key or upload a <code>.key</code> file to activate.</p>
      <textarea class="lup-activate-textarea" rows="3" placeholder="Paste license key here\u2026"></textarea>
      <input type="file" class="lup-activate-file" accept=".key,.txt" style="margin-top:8px;font-size:0.82rem;color:#8b919a;">
      <div class="lup-activate-preview" style="display:none"></div>
      <div class="lup-activate-error" style="display:none"></div>
      <button class="lic-action-btn lic-action-primary lup-activate-btn" disabled style="margin-top:10px">Activate</button>
    </div>
    ${currentTier !== 'personal' ? `
    <div class="lup-pane lup-machines-section">
      <div class="lup-pane-bar lup-pane-bar-green"></div>
      <h4 class="lup-pane-heading">Authorized machines</h4>
      <p class="lup-section-desc">Machines authorized to use this license.${currentTier === 'personal_plus' ? ' Personal Plus supports up to 3 machines.' : ''}</p>
      <div class="lup-machines-list">Loading\u2026</div>
      <div class="lup-machines-actions">
        <button class="lic-action-btn lic-action-primary lup-share-btn">Share license</button>
      </div>
    </div>` : ''}
    <div class="lup-save-prompt" style="display:none"></div>
    <div class="lup-confirm-dialog" style="display:none"></div>
    <div class="lup-error" style="display:none"></div>
  `;

  // Wire communication toggle
  el.querySelectorAll('[data-comm]').forEach(btn => {
    btn.addEventListener('click', async () => {
      formData.telemetry_opted_in = btn.dataset.comm === 'in';
      el.querySelectorAll('[data-comm]').forEach(b =>
        b.classList.toggle('lup-card-selected', b === btn)
      );
      await api.postTelemetryOptIn({ opted_in: formData.telemetry_opted_in });
    });
  });

  // Wire research toggle
  el.querySelectorAll('[data-research]').forEach(btn => {
    btn.addEventListener('click', async () => {
      formData.research_opted_in = btn.dataset.research === 'in';
      el.querySelectorAll('[data-research]').forEach(b =>
        b.classList.toggle('lup-card-selected', b === btn)
      );
      await api.postResearchOptIn({ opted_in: formData.research_opted_in });
    });
  });

  // Wire invoice download
  const invoiceBtn = el.querySelector('.lup-invoice-btn');
  if (invoiceBtn) {
    invoiceBtn.addEventListener('click', () => {
      _downloadInvoice({
        tier: invoiceBtn.dataset.tier,
        start: invoiceBtn.dataset.start,
        end: invoiceBtn.dataset.end,
        name: invoiceBtn.dataset.name,
        price: COMMERCIAL_TERMS[invoiceBtn.dataset.tier]?.price || 'Free',
      });
    });
  }

  // Wire certificate download
  const certBtn = el.querySelector('.lup-download-cert-btn');
  if (certBtn) {
    certBtn.addEventListener('click', () => _downloadCertificate(modeData));
  }

  // Wire token download
  const tokenBtn = el.querySelector('.lup-download-token-btn');
  if (tokenBtn && modeData.license_key) {
    tokenBtn.addEventListener('click', () => _downloadTokenFile(modeData));
  }

  // Wire activate-with-key
  const activateTextarea = el.querySelector('.lup-activate-textarea');
  const activateFile = el.querySelector('.lup-activate-file');
  const activatePreview = el.querySelector('.lup-activate-preview');
  const activateError = el.querySelector('.lup-activate-error');
  const activateBtn = el.querySelector('.lup-activate-btn');

  let _validateTimer = null;
  if (activateTextarea) {
    activateTextarea.addEventListener('input', () => {
      clearTimeout(_validateTimer);
      _validateTimer = setTimeout(async () => {
        const key = activateTextarea.value.trim();
        activatePreview.style.display = 'none';
        activateError.style.display = 'none';
        activateBtn.disabled = true;
        if (!key) return;
        try {
          const res = await api.postVerifyLicense({ license_key: key });
          if (res.ok && res.data && !res.data.error) {
            const d = res.data;
            if (d.expired) {
              activateError.textContent = 'This token has expired.';
              activateError.style.display = '';
            } else {
              activatePreview.textContent = `Tier: ${d.tier || 'N/A'} \u2022 Expires: ${(d.expiry_iso || d.expiry || '').slice(0, 10) || 'N/A'}`;
              activatePreview.style.display = '';
              activateBtn.disabled = false;
            }
          } else {
            activateError.textContent = 'Invalid token.';
            activateError.style.display = '';
          }
        } catch {
          activateError.textContent = 'Validation failed.';
          activateError.style.display = '';
        }
      }, 300);
    });
  }

  if (activateFile) {
    activateFile.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        if (activateTextarea) {
          activateTextarea.value = reader.result;
          activateTextarea.dispatchEvent(new Event('input'));
        }
      };
      reader.readAsText(file);
    });
  }

  if (activateBtn) {
    activateBtn.addEventListener('click', async () => {
      const key = activateTextarea ? activateTextarea.value.trim() : '';
      if (!key) return;
      activateBtn.disabled = true;
      activateError.style.display = 'none';
      try {
        const res = await api.postActivateWithKey({ license_key: key });
        if (res.ok && res.data && res.data.ok) {
          await _refreshLicenseState();
          _loadUnifiedPurchase(el, state);
        } else {
          activateError.textContent = (res.data && res.data.error) || 'Activation failed.';
          activateError.style.display = '';
          activateBtn.disabled = false;
        }
      } catch {
        activateError.textContent = 'Activation request failed.';
        activateError.style.display = '';
        activateBtn.disabled = false;
      }
    });
  }

  // Save prompt — show once per license
  _showTokenSavePrompt(el, modeData);

  // Wire management actions
  const confirmArea = el.querySelector('.lup-confirm-dialog');
  const errorEl = el.querySelector('.lup-error');

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

  // Wire plan selector for upgrades
  el.querySelectorAll('.lup-sel-row:not([disabled])').forEach(btn => {
    if (btn.dataset.tier === currentTier) return;
    btn.addEventListener('click', () => {
      // Switch to purchase flow for upgrade
      state.modeData = { ...state.modeData, license_status: 'licensed' };
      el.querySelectorAll('.lup-sel-row').forEach(b => b.classList.remove('lup-sel-active'));
      btn.classList.add('lup-sel-active');
      // Re-render as purchase body for the upgrade tier
      const bodyArea = el.querySelector('.lup-columns')?.parentElement;
      if (bodyArea) {
        // Rebuild: remove columns + purchase pane, add body area
        const oldCols = el.querySelector('.lup-columns');
        const oldPurch = el.querySelector('.lup-purchase-pane');
        if (oldCols) oldCols.remove();
        if (oldPurch) oldPurch.remove();
        const newBody = document.createElement('div');
        newBody.className = 'lup-body-area';
        el.querySelector('.lup-selector').after(newBody);
        _renderPurchaseBody(el, btn.dataset.tier, formData, state);
      }
    });
  });

  // Wire machine list + sharing
  if (currentTier !== 'personal') {
    _loadMachineList(el, modeData);
    const shareBtn = el.querySelector('.lup-share-btn');
    if (shareBtn) {
      shareBtn.addEventListener('click', () => _startSharingFlow(el, modeData, state));
    }
  }
}

// ---------- Machine management ----------

async function _loadMachineList(el, modeData) {
  const listEl = el.querySelector('.lup-machines-list');
  if (!listEl) return;

  const res = await api.getMachines();
  if (!res.ok) {
    listEl.innerHTML = `<div style="color:#f5a623;font-size:0.82rem;">${_esc(res.error)}</div>`;
    return;
  }
  const { machines, count, cap, tier } = res.data;
  const myFp = modeData.install_fingerprint || '';
  const capText = cap != null ? `${count} of ${cap} machines` : `${count} machine${count !== 1 ? 's' : ''}`;

  let html = '';
  if (machines.length === 0) {
    html = '<div style="font-size:0.82rem;color:#8b919a;">No machines authorized yet.</div>';
  } else {
    for (const m of machines) {
      const isMe = m.fingerprint === myFp;
      html += `<div class="lup-machine-row">
        <div class="lup-machine-info">
          <span class="lup-machine-hostname">${_esc(m.hostname || 'Unknown')}${isMe ? ' (this machine)' : ''}</span>
          <span class="lup-machine-meta">${_esc((m.fingerprint || '').slice(0, 8))} &middot; ${_esc((m.added_at || '').slice(0, 10))}</span>
        </div>
        ${!isMe ? `<button class="lic-action-btn lup-revoke-btn" data-fp="${_esc(m.fingerprint)}">Revoke</button>` : ''}
      </div>`;
    }
  }
  html += `<div class="lup-machine-count">${capText}</div>`;
  listEl.innerHTML = html;

  // Wire revoke buttons
  listEl.querySelectorAll('.lup-revoke-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm(`Revoke access for this machine? It will no longer be able to use this license.`)) return;
      btn.disabled = true;
      btn.textContent = 'Revoking\u2026';
      const res2 = await api.postRevokeMachine({ fingerprint: btn.dataset.fp });
      if (res2.ok) {
        _loadMachineList(el, modeData);
      } else {
        btn.disabled = false;
        btn.textContent = 'Revoke';
        alert(res2.error || 'Failed to revoke');
      }
    });
  });
}

async function _startSharingFlow(el, modeData, state) {
  const actionsEl = el.querySelector('.lup-machines-actions');
  if (!actionsEl) return;

  actionsEl.innerHTML = '<div style="font-size:0.82rem;color:#8b919a;">Starting sharing server\u2026</div>';

  const res = await api.postStartSharing();
  if (!res.ok) {
    actionsEl.innerHTML = `<div class="lup-join-error">${_esc(res.data?.error || res.error)}</div>
      <button class="lic-action-btn lic-action-primary lup-share-btn" style="margin-top:8px">Try again</button>`;
    el.querySelector('.lup-share-btn')?.addEventListener('click', () => _startSharingFlow(el, modeData, state));
    return;
  }

  const address = res.data.address || '';
  actionsEl.innerHTML = `
    <div class="lup-sharing-address">${_esc(address)}</div>
    <p style="font-size:0.82rem;color:#8b919a;margin:4px 0 12px;">Tell the other machine to enter this address in their dashboard.</p>
    <div class="lup-sharing-waiting">Waiting for requests\u2026</div>
    <div class="lup-sharing-requests"></div>
    <button class="lic-action-btn lup-stop-sharing-btn" style="margin-top:10px">Stop sharing</button>
  `;

  // Operator-initiated bounded poll: auto-terminates when sharing stops.
  // Acceptable per v4 §8 — operator explicitly triggered this flow.
  let pollId = setInterval(async () => {
    const sr = await api.getSharingStatus();
    if (!sr.ok || sr.data.state !== 'listening') {
      clearInterval(pollId);
      actionsEl.innerHTML = '<button class="lic-action-btn lic-action-primary lup-share-btn">Share license</button>';
      el.querySelector('.lup-share-btn')?.addEventListener('click', () => _startSharingFlow(el, modeData, state));
      return;
    }
    const reqs = sr.data.pending_requests || {};
    const reqsEl = actionsEl.querySelector('.lup-sharing-requests');
    const waitEl = actionsEl.querySelector('.lup-sharing-waiting');
    const pending = Object.entries(reqs).filter(([, r]) => r.status === 'pending');
    if (pending.length > 0 && waitEl) waitEl.style.display = 'none';

    for (const [rid, r] of pending) {
      if (reqsEl.querySelector(`[data-rid="${rid}"]`)) continue;
      const reqDiv = document.createElement('div');
      reqDiv.className = 'lup-sharing-request';
      reqDiv.dataset.rid = rid;
      reqDiv.innerHTML = `
        <p class="lup-sharing-request-text"><strong>${_esc(r.hostname)}</strong> (${_esc((r.fingerprint || '').slice(0, 8))}) is requesting access. All governance activity on this machine will be visible in your chain.</p>
        <div class="lup-sharing-request-actions">
          <button class="lic-action-btn lic-action-primary lup-approve-btn">Approve</button>
          <button class="lic-action-btn lup-deny-btn-inner">Deny</button>
        </div>
      `;
      reqsEl.appendChild(reqDiv);

      reqDiv.querySelector('.lup-approve-btn').addEventListener('click', async () => {
        reqDiv.querySelector('.lup-sharing-request-actions').innerHTML = '<span style="color:#8b919a;font-size:0.82rem;">Approving\u2026</span>';
        const ar = await api.postApproveShare({ request_id: rid });
        if (ar.ok) {
          reqDiv.innerHTML = '<p class="lup-sharing-request-text" style="color:#4ade80;">Approved! Machine has been authorized.</p>';
          _loadMachineList(el, modeData);
        } else {
          reqDiv.querySelector('.lup-sharing-request-actions').innerHTML = `<span style="color:#f5a623;font-size:0.82rem;">${_esc(ar.data?.error || ar.error)}</span>`;
        }
      });
      reqDiv.querySelector('.lup-deny-btn-inner').addEventListener('click', async () => {
        await api.postDenyShare({ request_id: rid });
        reqDiv.remove();
      });
    }
  }, 2000);

  // Stop sharing button
  actionsEl.querySelector('.lup-stop-sharing-btn')?.addEventListener('click', async () => {
    clearInterval(pollId);
    await api.postStopSharing();
    actionsEl.innerHTML = '<button class="lic-action-btn lic-action-primary lup-share-btn">Share license</button>';
    el.querySelector('.lup-share-btn')?.addEventListener('click', () => _startSharingFlow(el, modeData, state));
  });
}

// ---------- Invoice download ----------

function _downloadInvoice({ tier, start, end, name, price }) {
  const today = new Date().toISOString().slice(0, 10);
  let md = `# Atested License Invoice\n\n`;
  md += `Plan: ${_tierLabel(tier)}\n`;
  md += `License period: ${start} to ${end}\n`;
  md += `Price: ${price}\n`;
  md += `Operator: ${name}\n`;
  md += `Date: ${today}\n`;

  const blob = new Blob([md], { type: 'text/markdown' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `atested-invoice-${today}.md`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function _downloadCertificate(modeData) {
  const today = new Date().toISOString().slice(0, 10);
  const tier = modeData.license_tier || 'personal';
  const org = modeData.organization_name || modeData.operator_name || '';
  const licenseId = modeData.license_id || '';
  const issued = (modeData.purchase_date || modeData.registration_date || '').slice(0, 10) || 'N/A';
  const expires = (modeData.license_expiry || '').slice(0, 10) || 'N/A';

  const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Atested License Certificate</title>
<style>
  body { font-family: "Inter", system-ui, sans-serif; max-width: 600px; margin: 40px auto; color: #1a1a2e; }
  h1 { color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; }
  table { border-collapse: collapse; width: 100%; margin: 24px 0; }
  td { padding: 10px 14px; border: 1px solid #e2e8f0; }
  td:first-child { font-weight: 600; background: #f7fafc; width: 140px; }
  .footer { margin-top: 40px; font-size: 0.85rem; color: #718096; }
</style></head><body>
<h1>Atested License Certificate</h1>
<table>
  <tr><td>Tier</td><td>${_esc(tier)}</td></tr>
  ${org ? `<tr><td>Organization</td><td>${_esc(org)}</td></tr>` : ''}
  ${licenseId ? `<tr><td>License ID</td><td>${_esc(licenseId)}</td></tr>` : ''}
  <tr><td>Issued</td><td>${_esc(issued)}</td></tr>
  <tr><td>Expires</td><td>${_esc(expires)}</td></tr>
</table>
<p class="footer">Generated ${today} by Atested Governance Platform</p>
</body></html>`;

  const blob = new Blob([html], { type: 'text/html' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `atested-license-certificate-${today}.html`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function _downloadTokenFile(modeData) {
  const key = modeData.license_key || '';
  if (!key) return;
  const blob = new Blob([key], { type: 'application/octet-stream' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'atested-license.key';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function _showTokenSavePrompt(el, modeData) {
  if (modeData.license_status !== 'licensed') return;
  const key = modeData.license_key || '';
  if (!key) return;
  const storageKey = 'atd_token_prompted_' + key.slice(0, 16);
  if (localStorage.getItem(storageKey)) return;

  const promptEl = el.querySelector('.lup-save-prompt');
  if (!promptEl) return;

  promptEl.style.display = '';
  promptEl.innerHTML = `
    <div class="lup-save-prompt-card">
      <p class="lup-save-prompt-text">Save your license file somewhere safe. You'll need it if you ever reinstall Atested on a new machine.</p>
      <div class="lup-token-actions">
        <button class="lup-invoice-btn lup-save-cert">Download certificate</button>
        <button class="lup-invoice-btn lup-save-token">Download token</button>
        <button class="lup-invoice-btn lup-save-dismiss">Got it</button>
      </div>
    </div>
  `;

  promptEl.querySelector('.lup-save-cert')?.addEventListener('click', () => _downloadCertificate(modeData));
  promptEl.querySelector('.lup-save-token')?.addEventListener('click', () => _downloadTokenFile(modeData));
  promptEl.querySelector('.lup-save-dismiss')?.addEventListener('click', () => {
    localStorage.setItem(storageKey, '1');
    promptEl.style.display = 'none';
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
  const hasRecommendation = !!doc.recommendation;

  if (!hasRecommendation) {
    el.innerHTML = `
      <div class="lcd-document">
        <div class="lcd-no-rec">
          <p class="lq-text">No recommendation yet. Complete the survey to receive a plan recommendation.</p>
          <div class="lq-actions">
            <button class="lic-action-btn lic-action-primary" data-nav="questionnaire">Start Survey</button>
          </div>
        </div>
      </div>
    `;
    el.querySelectorAll('[data-nav]').forEach(btn => {
      btn.addEventListener('click', () => _switchPanel(appState, btn.dataset.nav));
    });
    return;
  }

  // Commercial terms from client-side single source
  if (doc.recommendation && COMMERCIAL_TERMS[doc.recommendation]) {
    doc.commercial_terms = COMMERCIAL_TERMS[doc.recommendation];
  }

  _renderCaseForTier(el, doc, doc.recommendation, false, appState);
}

function _renderCaseForTier(el, doc, tierId, isExploring, appState) {
  const isTentative = doc.recommendation_status === 'tentative' && !isExploring;
  const tierLabel = TIER_LABELS[tierId] || tierId;
  const ev = doc.governance_evidence || {};
  const terms = COMMERCIAL_TERMS[tierId] || {};
  const price = terms.price || '';

  // Build plan selector for "explore other plans"
  const recTierId = doc.recommendation;
  const recIdx = TIERS.indexOf(recTierId);
  let selectorHtml = '';
  if (isExploring) {
    const explorableTiers = TIERS.filter((t, i) => i >= recIdx);
    selectorHtml = `<div class="lcd-plan-selector">
      ${explorableTiers.map(t => `<button class="lcd-plan-btn${t === tierId ? ' lcd-plan-active' : ''}" data-explore="${t}">${_esc(TIER_LABELS[t])}</button>`).join('')}
    </div>`;
  }

  // Recommendation pane
  const badgeText = isExploring ? `[Exploring: ${tierLabel}]` : (isTentative ? '[Tentative recommendation]' : '[Verified recommendation]');
  const badgeClass = isExploring ? 'lcd-rec-badge lcd-rec-exploring' : 'lcd-rec-badge';
  const descText = 'Your responses and trial data combined into one document. Use it to make the case internally for moving Atested into production.';

  // Why panes — use threshold reasoning from questionnaire engine
  const qState = appState.qState;
  let whyLowerHtml = '';
  let whyHigherHtml = '';
  if (qState && qState.verified && qState.recommendation) {
    const reasoning = thresholdReasoning(qState);
    if (doc.why_not_lower || reasoning.whyNotLower) {
      whyLowerHtml = `<div class="lcd-why-pane lcd-why-lower">
        <div class="lcd-why-accent lcd-why-accent-amber"></div>
        <h4 class="lcd-why-heading">Why not a lower plan?</h4>
        <p class="lcd-why-text">${_esc(doc.why_not_lower || reasoning.whyNotLower)}</p>
      </div>`;
    }
    if (doc.why_not_higher || reasoning.whyNotHigher) {
      whyHigherHtml = `<div class="lcd-why-pane lcd-why-higher">
        <div class="lcd-why-accent lcd-why-accent-green"></div>
        <h4 class="lcd-why-heading">Why not a higher plan?</h4>
        <p class="lcd-why-text">${_esc(doc.why_not_higher || reasoning.whyNotHigher)}</p>
      </div>`;
    }
  }

  el.innerHTML = `
    <div class="lcd-document">
      ${selectorHtml}

      ${isTentative ? `<div class="lcd-tentative-banner">This recommendation is tentative. Additional survey questions would verify it.</div>` : ''}

      <div class="lcd-recommendation">
        <div class="lcd-rec-accent"></div>
        <div class="${badgeClass}">${_esc(badgeText)}</div>
        <h2 class="lcd-rec-tier">${_esc(tierLabel)}</h2>
        <div class="lcd-rec-price">${_esc(price)}</div>
        <p class="lcd-rec-summary">${_esc(descText)}</p>
      </div>

      <div class="lcd-evidence-pane">
        <div class="lcd-evidence-accent"></div>
        <h4 class="lcd-evidence-heading">Evidence from your installation</h4>
        ${ev.as_of ? `<p class="lcd-evidence-as-of">As of ${_esc(ev.as_of.replace('T', ' ').replace('Z', ' UTC'))}</p>` : ''}
        <div class="lcd-evidence-grid">
          <div class="lcd-evidence-stat">
            <span class="lcd-ev-number">${(ev.total_decisions || 0).toLocaleString()}</span>
            <span class="lcd-ev-label">Total Decisions</span>
          </div>
          <div class="lcd-evidence-stat">
            <span class="lcd-ev-number lcd-ev-allow">${(ev.allow_count || 0).toLocaleString()}</span>
            <span class="lcd-ev-label">Allow</span>
          </div>
          <div class="lcd-evidence-stat">
            <span class="lcd-ev-number lcd-ev-deny">${(ev.deny_count || 0).toLocaleString()}</span>
            <span class="lcd-ev-label">Deny</span>
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

      ${(whyLowerHtml || whyHigherHtml) ? `<div class="lcd-why-row">${whyLowerHtml}${whyHigherHtml}</div>` : ''}

      <div class="lcd-action-row">
        <div class="lcd-action-pane lcd-action-share">
          <div class="lcd-action-accent lcd-action-accent-green"></div>
          <h4 class="lcd-action-title">Sharing</h4>
          <p class="lcd-action-desc">Download a formatted document to use as your input in the purchasing process.</p>
          <span class="lcd-action-click lcd-download-btn">Click to download</span>
        </div>
        <div class="lcd-action-pane lcd-action-strengthen">
          <div class="lcd-action-accent lcd-action-accent-amber"></div>
          <h4 class="lcd-action-title">Strengthen your case</h4>
          <p class="lcd-action-desc">The more you share about your installation the more precise and stronger your case document. This does not change your recommendation.</p>
          <span class="lcd-action-click" data-nav="questionnaire">Click to continue the survey</span>
        </div>
        <div class="lcd-action-pane lcd-action-explore">
          <div class="lcd-action-accent lcd-action-accent-blue"></div>
          <h4 class="lcd-action-title">See a different plan</h4>
          <p class="lcd-action-desc">Explore the argument for a different plan without changing your recommendation.</p>
          <span class="lcd-action-click lcd-explore-btn">Click to explore other plans</span>
        </div>
      </div>
    </div>
  `;

  // Wire nav buttons
  el.querySelectorAll('[data-nav]').forEach(btn => {
    btn.addEventListener('click', () => _switchPanel(appState, btn.dataset.nav));
  });

  // Wire download
  const dlBtn = el.querySelector('.lcd-download-btn');
  if (dlBtn) {
    dlBtn.addEventListener('click', () => _downloadCaseDocument(doc));
  }

  // Wire explore
  const expBtn = el.querySelector('.lcd-explore-btn');
  if (expBtn) {
    expBtn.addEventListener('click', () => {
      _renderCaseForTier(el, doc, doc.recommendation, true, appState);
    });
  }

  // Wire plan selector buttons (when exploring)
  el.querySelectorAll('[data-explore]').forEach(btn => {
    btn.addEventListener('click', () => {
      _renderCaseForTier(el, doc, btn.dataset.explore, true, appState);
    });
  });
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
// Pricing grandchild — tier selector + incremental feature detail
// ==========================================================================

// ---------- Pricing feature content (incremental per plan) ----------

const _TELEMETRY_INTRO = 'Atested maintains a bidirectional channel between your installation and Atested. This channel carries data in both directions and is the transport layer we both use to communicate. Uses include escalation requests from you, security notifications, new version notifications, and operational intelligence. All traffic on this channel is recorded in your governance chain, so you can independently verify what was sent and received. The transport layer itself is encrypted end to end.';

const _TELEMETRY_OUTBOUND = 'Your installation sends anonymized, summarized operational data to Atested. Aggregate decision counts, classifier confidence distributions, and policy rule hit patterns. No tool names, file paths, commands, or content is transmitted or ever retained in any way. This data helps Atested improve classification accuracy and prioritize development.';

const _TELEMETRY_OPT_OUT = 'You can opt out of telemetry during licensing. Opting out is supported but reduces our ability to deliver version updates and operational intelligence to your installation. Emergency communications are never affected by telemetry status or plan level. Atested will always act to protect every installation regardless.';

const _PRIORITY_INTRO = [
  'Priority requests use the telemetry channel to connect you directly with Atested. You decide when to use a slot and what priority it warrants. We do not require you to exhaust documentation or verify your issue before reaching out. Your judgment is enough.',
  'When you submit a priority request, one of your slots is immediately occupied with your submission. A companion pane comes alive with a receipt of delivery, your position in the queue, and an expected investigation start time. As we work on your request, our response is reported in real time alongside your original submission. This is not a ticket number you check periodically. It is a live view of the exchange between you and Atested.',
  'Slots remain occupied until the request is resolved. You choose which issues warrant a slot, knowing the count is limited.',
];

const PRICING_FEATURES = {
  personal: {
    title: 'All Atested plans include the following',
    categories: [
      { name: 'Governance', features: [
        { name: 'The Chain', desc: 'Cryptographically signed, hash-chained, immutable record of every AI application action. Every decision is recorded with Ed25519 signatures and can be independently verified by anyone with the public key.' },
        { name: 'Policy Evaluation', desc: 'Declarative rules evaluated against every tool call before execution. ALLOW or DENY, decided and recorded before the action can happen.' },
      ]},
      { name: 'Oversight', features: [
        { name: 'Dashboard', desc: 'Real-time operational view of what your AI applications are doing. Decisions, activity, health, and configuration in one surface.' },
        { name: 'Audit', desc: 'Searchable, filterable record of every governed operation. Query by time, user, tool, decision type, or event category. Independently verifiable against the chain.' },
      ]},
      { name: 'Operations', features: [
        { name: 'Single Operator', desc: 'Full Atested capabilities for one person. Your chain, your machine. Everything you need to trust your AI applications.' },
      ]},
      { name: 'Communication', features: [
        { name: 'Telemetry Communication', telemetry: true, inbound: 'Atested sends security notifications, version updates, and operational intelligence back through the same channel. Critical security alerts reach your installation as they are identified. New version availability is communicated with release details so you can evaluate before updating.' },
        { name: 'Priority Requests', priority: true, detail: 'All requests are accepted at standard priority. Standard requests are not tracked individually.' },
        { name: 'Safety Alerts', monitoring: true, desc: 'Atested monitors for security vulnerabilities that affect your version. If we detect one, we notify you through the telemetry channel. At Personal, we watch for safety. We only reach out when your installation\u2019s security is at risk.' },
      ]},
    ],
  },
  personal_plus: {
    title: 'In addition to everything included with Personal, Personal Plus adds the following.',
    categories: [
      { name: 'Operations', features: [
        { name: 'Multi-Machine', desc: 'Run Atested on up to 3 machines under a single license. All machines share one chain and one policy configuration. Your governance picture is complete regardless of which machine you work from.' },
      ]},
      { name: 'Communication', features: [
        { name: 'Telemetry Communication', telemetry: true, inbound: 'Cross-machine pattern detection. Atested can identify inconsistencies between your machines and surface operational insights specific to your multi-machine setup.' },
        { name: 'Priority Requests', priority: true, detail: '2 Medium priority slots. Medium requests move ahead of standard requests in the queue.' },
        { name: 'Operational Monitoring', monitoring: true, desc: 'Atested monitors your installation\u2019s operational health in addition to safety. If your DENY rate spikes abnormally or your chain integrity degrades, we send a notice describing what we observed and what it may indicate. We are watching for operational health, not just safety.' },
      ]},
    ],
  },
  crew: {
    title: 'In addition to everything included with Personal Plus, the Crew plan adds the following.',
    categories: [
      { name: 'Operations', features: [
        { name: 'Unlimited Machines', desc: 'No machine limit. Run Atested across your entire infrastructure under one license.' },
        { name: 'Multi-User Governance', desc: 'When multiple people use Atested under one license, their activity is governed together. Shared policies, combined views, and organizational-level reporting. One set of rules, one complete picture of what is happening. Everyone on the license shares governance, giving you complete organizational visibility across all users.' },
      ]},
      { name: 'Communication', features: [
        { name: 'Telemetry Communication', telemetry: true, inbound: 'Aggregate patterns across your users visible in your dashboard. Cross-install intelligence feeds back into your operational views. You see how your deployment compares to similar installations.' },
        { name: 'Priority Requests', priority: true, detail: '4 Medium priority slots and 2 High priority slots. Elevated requests receive priority handling with faster response times.' },
        { name: 'Usage Pattern Detection', monitoring: true, desc: 'Atested monitors cross-user patterns within your license. If one user generates significantly more DENYs than others, or if classifier confidence trends toward opaque operations, we flag it with specifics. We are watching user dynamics, not just the installation.' },
      ]},
    ],
  },
  team: {
    title: 'In addition to everything included with Crew, the Team plan adds the following.',
    categories: [
      { name: 'Operations', features: [
        { name: 'Role-Based Governance', desc: 'Configurable roles with different permission levels for operators, reviewers, and administrators. Control who can approve, who can configure, and who can view.' },
        { name: 'Organizational Structure', desc: '13\u201350 users with delegated administration. Manage your governance organization, not just individual operators.' },
      ]},
      { name: 'Oversight', features: [
        { name: 'Team Activity View', desc: 'Aggregated activity across all team members with per-user breakdown. See who is doing what and how governance decisions distribute across the organization.' },
        { name: 'Advanced Reporting', desc: 'Scheduled and ad-hoc reports covering metrics, trends, and compliance status over configurable time periods.' },
      ]},
      { name: 'Communication', features: [
        { name: 'Telemetry Communication', telemetry: true, inbound: 'Organizational telemetry with role-level breakdowns. Compliance-relevant aggregate metrics derived from your telemetry data and surfaced in your reporting. Industry-level benchmarking at this scale.' },
        { name: 'Priority Requests', priority: true, detail: '8 Medium priority slots with 3-business-day response and 4 High priority slots with 2-business-day response. Your team can see all open requests, who submitted them, and their current status. 3-business-day response commitment for Medium. 2-business-day response commitment for High.' },
        { name: 'Governance Health Monitoring', monitoring: true, desc: 'Atested monitors your governance posture for compliance-relevant drift. Policy rules that never fire, rules that fire constantly, approval backlogs building. We surface these before they become audit findings. If we send an alert and it is not acknowledged within a reasonable window, we follow up. We are actively managing your governance health, not just monitoring it.' },
      ]},
    ],
  },
  institution: {
    title: 'In addition to everything included with Team, the Institution plan adds the following.',
    categories: [
      { name: 'Operations', features: [
        { name: 'Custom Deployment', desc: 'On-premises or hybrid deployment configured to your infrastructure requirements. Your data stays where you need it.' },
        { name: 'Unlimited Scale', desc: '51+ users with enterprise-scale administration and policy management. No user ceiling.' },
      ]},
      { name: 'Compliance', features: [
        { name: 'Third-Party Attestation', desc: 'Independent verification of your governance chain by authorized auditors. Proof that your AI governance is what you say it is.' },
        { name: 'Compliance Reporting', desc: 'Regulatory-aligned reporting for healthcare, finance, legal, and defense requirements. Built from your chain data, not from surveys or self-assessments.' },
      ]},
      { name: 'Communication', features: [
        { name: 'Telemetry Communication', telemetry: true, inbound: 'Custom telemetry configuration. You control what is shared, what is retained, and what is reported. Telemetry terms are part of your negotiated agreement.' },
        { name: 'Priority Requests', priority: true, detail: 'Custom priority slot allocation and SLA negotiated for your organization. Named contact with direct access to the people who build and maintain Atested.' },
        { name: 'Continuous Oversight', monitoring: true, desc: 'Custom alert thresholds configured for your environment. Your named contact proactively reaches out on a scheduled cadence, not only when something triggers. The relationship is continuous, not reactive.' },
      ]},
    ],
  },
};

const _TIER_SELECTOR = [
  { id: 'personal',      name: 'Personal',      spec: '1 user, 1 machine',                       price: 'Free' },
  { id: 'personal_plus', name: 'Personal Plus',  spec: '1 user, up to 3 machines',                price: '$99/yr' },
  { id: 'crew',          name: 'Crew',           spec: '2\u201312 users, unlimited machines',      price: '$2,995/yr' },
  { id: 'team',          name: 'Team',           spec: '13\u201350 users, organizational governance', price: '$19,995/yr' },
  { id: 'institution',   name: 'Institution',    spec: '51+ users, custom deployment',             price: 'Negotiated' },
];

// ---------- Pricing grandchild builder ----------

function _buildTierDisplayPanel(state) {
  const el = document.createElement('div');
  el.className = 'lp-panel';

  // Tier selector panes
  let selectorHtml = '';
  for (const t of _TIER_SELECTOR) {
    selectorHtml += `<button class="lp-tier-row" data-tier="${t.id}">
      <span class="lp-tier-name">${_esc(t.name)}</span>
      <span class="lp-tier-spec">${_esc(t.spec)}</span>
      <span class="lp-tier-price">${_esc(t.price)}</span>
    </button>`;
  }

  el.innerHTML = `
    <div class="lp-selector">${selectorHtml}</div>
    <div class="lp-detail"></div>
  `;

  // Select first tier (or recommended/licensed)
  const rec = state.qState?.recommendation;
  const licensed = _getLicensedTier(state.mode);
  const initial = licensed || rec || 'personal';

  // Wire selector clicks
  el.querySelectorAll('.lp-tier-row').forEach(btn => {
    btn.addEventListener('click', () => {
      el.querySelectorAll('.lp-tier-row').forEach(b => b.classList.remove('lp-tier-active'));
      btn.classList.add('lp-tier-active');
      _renderPricingDetail(el.querySelector('.lp-detail'), btn.dataset.tier, state);
    });
  });

  // Activate initial tier
  const initialBtn = el.querySelector(`[data-tier="${initial}"]`);
  if (initialBtn) {
    initialBtn.classList.add('lp-tier-active');
    _renderPricingDetail(el.querySelector('.lp-detail'), initial, state);
  }

  return el;
}

function _renderPricingDetail(container, tierId, state) {
  const plan = PRICING_FEATURES[tierId];
  if (!plan) { container.innerHTML = ''; return; }

  const paneStates = _computePaneStates(state);
  const accentColor = (paneStates.tiers === 'green') ? '#22c55e' : '#f5a623';

  let html = `<div class="lp-accent-bar" style="background:${accentColor}"></div>`;
  html += `<h3 class="lp-detail-title">${_esc(plan.title)}</h3>`;

  for (const cat of plan.categories) {
    html += `<div class="lp-category-header">${_esc(cat.name)}</div>`;
    for (const feat of cat.features) {
      if (feat.telemetry) {
        html += _renderTelemetryItem(feat, tierId);
      } else if (feat.priority) {
        html += _renderPriorityItem(feat, tierId === 'personal');
      } else if (feat.monitoring) {
        html += `<div class="lp-feature">
          <div class="lp-feature-name">${_esc(feat.name)}</div>
          <div class="lp-feature-desc">${_esc(feat.desc)}</div>
        </div>`;
      } else {
        html += `<div class="lp-feature">
          <div class="lp-feature-name">${_esc(feat.name)}</div>
          <div class="lp-feature-desc">${_esc(feat.desc)}</div>
        </div>`;
      }
    }
  }

  container.innerHTML = html;
}

function _renderTelemetryItem(feat, tierId) {
  const isPersonal = (tierId === 'personal');
  let html = `<div class="lp-feature lp-feature-telemetry">
    <div class="lp-feature-name">${_esc(feat.name)}</div>`;

  if (isPersonal) {
    html += `<div class="lp-feature-desc">${_esc(_TELEMETRY_INTRO)}</div>`;
  }

  html += `<div class="lp-telem-sections">`;
  if (isPersonal) {
    html += `<div class="lp-telem-sub"><span class="lp-telem-label">Outbound</span><div class="lp-telem-text">${_esc(_TELEMETRY_OUTBOUND)}</div></div>`;
  }
  html += `<div class="lp-telem-sub"><span class="lp-telem-label">Inbound</span><div class="lp-telem-text">${_esc(feat.inbound)}</div></div>`;
  if (isPersonal) {
    html += `<div class="lp-telem-sub"><span class="lp-telem-label">Opting Out</span><div class="lp-telem-text">${_esc(_TELEMETRY_OPT_OUT)}</div></div>`;
  }
  html += `</div></div>`;
  return html;
}

function _renderPriorityItem(feat, isBase) {
  let html = `<div class="lp-feature lp-feature-priority">
    <div class="lp-feature-name">${_esc(feat.name)}</div>`;

  // Shared intro only at Personal (full base set)
  if (isBase) {
    html += _PRIORITY_INTRO.map(p => `<div class="lp-feature-desc">${_esc(p)}</div>`).join('');
  }

  html += `<div class="lp-feature-desc">${_esc(feat.detail)}</div>`;
  html += `</div>`;
  return html;
}

function _getLicensedTier(mode) {
  if (mode === 'personal_registered') return 'personal';
  if (['personal_plus', 'crew', 'team', 'institution'].includes(mode)) return mode;
  return null;
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
    padding: 12px 16px 10px;
  }
  .lic-error {
    color: #f5a623;
    background: rgba(245, 166, 35, 0.10);
    font-size: 0.82rem;
    padding: 12px 16px;
    border-radius: 2px;
  }
  .lic-action-btn {
    background: none;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    color: #60a5fa;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 500;
    padding: 8px 16px;
    transition: background 0.15s, border-color 0.15s;
  }
  .lic-action-btn:hover {
    background: rgba(96, 165, 250, 0.12);
    border-color: #60a5fa;
  }
  .lic-action-btn:focus-visible {
    outline: 2px solid #60a5fa;
    outline-offset: 2px;
  }
  .lic-action-btn.lic-action-primary {
    background: #60a5fa;
    color: #fff;
    border-color: #60a5fa;
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
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 2px;
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
    background: #22c55e;
  }
  .ll-dot-amber {
    background: #f5a623;
  }
  .ll-sp-title {
    font-size: 1rem;
    font-weight: 600;
    color: #e4e6eb;
  }
  .ll-sp-tier {
    font-weight: 600;
    color: #60a5fa;
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
    color: #e4e6eb;
    padding: 3px 0;
    line-height: 1.35;
  }
  .ll-sp-detail {
    display: block;
    font-size: 13px;
    color: #60a5fa;
    line-height: 1.35;
    margin-top: 1px;
  }
  .ll-sp-state {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 3px 10px;
    white-space: nowrap;
  }
  .ll-sp-closing {
    font-size: 0.82rem;
    color: #60a5fa;
    font-weight: 500;
    text-align: center;
    margin-top: 10px;
    padding-left: 0;
  }
  /* Dynamic row colors */
  .ll-sp-row-green .ll-sp-name { color: #22c55e; }
  .ll-sp-row-green .ll-sp-state {
    color: #22c55e;
  }
  .ll-sp-row-amber .ll-sp-name { color: #f5a623; }
  .ll-sp-row-amber .ll-sp-state {
    color: #f5a623;
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
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 2px;
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
    outline: 2px solid #60a5fa;
    outline-offset: 2px;
  }
  .ll-ts-accent {
    width: 6px;
    align-self: stretch;
    flex-shrink: 0;
    background: #8b919a;
    transition: background 0.2s;
  }
  .ll-ts-green .ll-ts-accent { background: #22c55e; }
  .ll-ts-amber .ll-ts-accent { background: #f5a623; }
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
  .ll-ts-green .ll-ts-action { color: #22c55e; }
  .ll-ts-amber .ll-ts-action { color: #f5a623; }

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
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    transition: background 0.15s, border-color 0.15s, transform 0.1s;
    text-align: left;
    overflow: hidden;
    min-height: 200px;
  }
  .ll-accent-bar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    border-radius: 2px 2px 0 0;
    background: rgba(255, 255, 255, 0.1);
    transition: background 0.2s;
  }
  /* Dynamic box accent colors */
  .ll-box-green .ll-accent-bar { background: #22c55e; }
  .ll-box-amber .ll-accent-bar { background: #f5a623; }
  .ll-box:hover {
    background: rgba(255, 255, 255, 0.06);
    border-color: rgba(255, 255, 255, 0.14);
    transform: translateY(-1px);
  }
  .ll-box-green:hover { border-color: rgba(34, 197, 94, 0.3); }
  .ll-box-amber:hover { border-color: rgba(245, 166, 35, 0.3); }
  .ll-box:focus-visible {
    outline: 2px solid #60a5fa;
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
    color: #e4e6eb;
    line-height: 1.4;
  }
  .ll-status-line.ll-data {
    color: #60a5fa;
  }
  .ll-click {
    font-size: 0.82rem;
    font-weight: 500;
    margin-top: auto;
    padding-top: 4px;
    color: #fbbf24;
    text-align: center;
    width: 100%;
    transition: color 0.15s;
  }

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
    color: #22c55e;
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
    accent-color: #60a5fa;
    width: 16px;
    height: 16px;
  }
  .lt-ack-btn {
    display: inline-block;
    padding: 10px 32px;
    font-size: 0.9rem;
    font-weight: 500;
    color: #fff;
    background: #60a5fa;
    border: none;
    border-radius: 2px;
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
    color: #f5a623;
    background: rgba(245, 166, 35, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 2px;
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
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 1rem;
    padding: 8px 12px;
    width: 160px;
    outline: none;
    transition: border-color 0.15s;
  }
  .lq-input:focus {
    border-color: #60a5fa;
  }
  .lq-input::placeholder {
    color: #6b7280;
  }
  .lq-base-tier-card {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    background: rgba(96, 165, 250, 0.08);
    border: 1px dashed rgba(96, 165, 250, 0.2);
    border-radius: 2px;
    font-size: 0.9rem;
    color: #e4e6eb;
    margin-top: 8px;
  }
  .lq-base-tier-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #60a5fa;
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
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 2px;
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
    border-radius: 2px;
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
    background: rgba(96, 165, 250, 0.10);
    border-color: #60a5fa;
  }
  .lq-option-btn:focus-visible {
    outline: 2px solid #60a5fa;
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

  /* ---- Survey completion panes ---- */
  .lqc-rec-pane {
    position: relative;
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 24px 20px 20px;
    margin-bottom: 16px;
    text-align: center;
    overflow: hidden;
  }
  .lqc-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    border-radius: 2px 2px 0 0;
  }
  .lqc-accent-green { background: #22c55e; }
  .lqc-accent-amber { background: #f5a623; }
  .lqc-rec-badge {
    display: inline-block;
    color: #22c55e;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 3px 12px;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lqc-rec-tier {
    font-size: 1.75rem;
    font-weight: 700;
    margin: 0 0 4px 0;
    color: #e4e6eb;
  }
  .lqc-rec-price {
    font-size: 1rem;
    font-weight: 500;
    color: #60a5fa;
    margin: 0 0 10px 0;
  }
  .lqc-rec-summary {
    font-size: 0.9rem;
    color: #8b919a;
    margin: 0;
    line-height: 1.6;
    max-width: 500px;
    margin-left: auto;
    margin-right: auto;
  }

  /* Why panes — side by side */
  .lqc-why-row {
    display: flex;
    gap: 16px;
    margin-bottom: 16px;
  }
  .lqc-why-pane {
    flex: 1;
    min-width: 0;
    position: relative;
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 16px 16px 14px;
    overflow: hidden;
  }
  .lqc-why-heading {
    font-size: 0.82rem;
    font-weight: 600;
    color: #60a5fa;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 4px 0 8px 0;
  }
  .lqc-why-text {
    font-size: 0.82rem;
    color: #b0b6c0;
    line-height: 1.6;
    margin: 0;
  }

  /* Workflow pane with nested action cards */
  .lqc-workflow-pane {
    position: relative;
    background: #22262e;
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 20px 20px 16px;
    overflow: hidden;
  }
  .lqc-workflow-heading {
    font-size: 0.82rem;
    font-weight: 600;
    color: #60a5fa;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin: 4px 0 16px 0;
  }
  .lqc-action-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
  }
  .lqc-action-card {
    position: relative;
    background: #1a1d23;
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 14px 14px 12px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  .lqc-card-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 4px;
    border-radius: 2px 2px 0 0;
  }
  .lqc-card-accent-green { background: #22c55e; }
  .lqc-card-accent-amber { background: #f5a623; }
  .lqc-card-accent-gray { background: #6b7280; }
  .lqc-card-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 4px 0 8px 0;
  }
  .lqc-card-desc {
    font-size: 0.82rem;
    color: #b0b6c0;
    line-height: 1.5;
    margin: 0 0 12px 0;
    flex: 1;
  }
  .lqc-card-click {
    font-size: 0.82rem;
    font-weight: 600;
    color: #fbbf24;
    cursor: pointer;
    user-select: none;
    transition: opacity 0.15s;
  }
  .lqc-card-click:hover {
    opacity: 0.8;
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

  /* ---- Case Document panel ---- */
  .lcd-document {
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 900px;
  }
  .lcd-tentative-banner {
    background: rgba(245, 166, 35, 0.10);
    border: 1px dashed rgba(245, 166, 35, 0.3);
    border-radius: 2px;
    padding: 10px 14px;
    font-size: 0.82rem;
    color: #f5a623;
  }
  .lcd-no-rec {
    font-size: 1rem;
    color: #8b919a;
    padding: 20px 0;
    text-align: center;
  }

  /* Plan selector (explore mode) */
  .lcd-plan-selector {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    margin-bottom: 4px;
  }
  .lcd-plan-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 2px;
    padding: 6px 14px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 500;
    color: #8b919a;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
  }
  .lcd-plan-btn:hover {
    background: rgba(255, 255, 255, 0.07);
    color: #e4e6eb;
  }
  .lcd-plan-btn:focus-visible {
    outline: 2px solid #60a5fa;
    outline-offset: 2px;
  }
  .lcd-plan-active {
    background: rgba(96, 165, 250, 0.12);
    border-color: rgba(96, 165, 250, 0.3);
    color: #60a5fa;
    font-weight: 600;
  }

  /* Recommendation pane */
  .lcd-recommendation {
    position: relative;
    text-align: center;
    padding: 24px 20px 20px;
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    overflow: hidden;
  }
  .lcd-rec-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: #22c55e;
    border-radius: 2px 2px 0 0;
  }
  .lcd-rec-badge {
    display: inline-block;
    color: #22c55e;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 3px 12px;
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lcd-rec-exploring {
    color: #60a5fa;
  }
  .lcd-rec-tier {
    font-size: 1.7rem;
    font-weight: 700;
    margin: 0 0 4px 0;
    color: #e4e6eb;
  }
  .lcd-rec-price {
    font-size: 1rem;
    font-weight: 500;
    color: #60a5fa;
    margin: 0 0 10px 0;
  }
  .lcd-rec-summary {
    font-size: 0.9rem;
    color: #8b919a;
    margin: 0;
    line-height: 1.6;
    max-width: 600px;
    margin-left: auto;
    margin-right: auto;
  }

  /* Evidence pane */
  .lcd-evidence-pane {
    position: relative;
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 20px 20px 16px;
    overflow: hidden;
  }
  .lcd-evidence-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    background: #22c55e;
    border-radius: 2px 2px 0 0;
  }
  .lcd-evidence-heading {
    font-size: 0.9rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 4px 0 8px 0;
  }
  .lcd-evidence-as-of {
    font-size: 0.82rem;
    color: #6b7280;
    margin: 0 0 10px 0;
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
    color: #f5a623;
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

  /* Why panes — side by side */
  .lcd-why-row {
    display: flex;
    gap: 16px;
  }
  .lcd-why-pane {
    flex: 1;
    min-width: 0;
    position: relative;
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 16px 16px 14px;
    overflow: hidden;
  }
  .lcd-why-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    border-radius: 2px 2px 0 0;
  }
  .lcd-why-accent-amber {
    background: #f5a623;
  }
  .lcd-why-accent-green {
    background: #22c55e;
  }
  .lcd-why-heading {
    font-size: 0.9rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 4px 0 8px 0;
  }
  .lcd-why-text {
    font-size: 0.82rem;
    color: #b0b6c0;
    line-height: 1.6;
    margin: 0;
  }

  /* Action panes — 3 column row */
  .lcd-action-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
  }
  .lcd-action-pane {
    position: relative;
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 16px 16px 14px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }
  .lcd-action-accent {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    border-radius: 2px 2px 0 0;
  }
  .lcd-action-accent-green {
    background: #22c55e;
  }
  .lcd-action-accent-amber {
    background: #f5a623;
  }
  .lcd-action-accent-blue {
    background: #60a5fa;
  }
  .lcd-action-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 4px 0 8px 0;
  }
  .lcd-action-desc {
    font-size: 0.82rem;
    color: #b0b6c0;
    line-height: 1.5;
    margin: 0 0 12px 0;
    flex: 1;
  }
  .lcd-action-click {
    font-size: 0.82rem;
    font-weight: 600;
    color: #fbbf24;
    cursor: pointer;
    user-select: none;
    transition: opacity 0.15s;
  }
  .lcd-action-click:hover {
    opacity: 0.8;
  }

  /* ---- Pricing grandchild ---- */
  .lp-panel {
    max-width: 900px;
  }
  .lp-selector {
    display: flex;
    flex-direction: column;
    gap: 2px;
    margin-bottom: 20px;
  }
  .lp-tier-row {
    display: grid;
    grid-template-columns: 180px 1fr auto;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    background: rgba(255, 255, 255, 0.03);
    border: none;
    border-left: 4px solid transparent;
    border-radius: 2px;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
    text-align: left;
    transition: background 0.15s, border-color 0.15s;
  }
  .lp-tier-row:hover {
    background: rgba(255, 255, 255, 0.05);
  }
  .lp-tier-row:focus-visible {
    outline: 2px solid #60a5fa;
    outline-offset: -2px;
  }
  .lp-tier-active {
    border-left-color: #22c55e;
    background: rgba(255, 255, 255, 0.06);
  }
  .lp-tier-name {
    font-size: 0.9rem;
    font-weight: 600;
  }
  .lp-tier-spec {
    font-size: 0.82rem;
    color: #60a5fa;
  }
  .lp-tier-price {
    font-size: 0.9rem;
    font-weight: 500;
    color: #b0b6c0;
    text-align: right;
  }

  /* Detail pane */
  .lp-detail {
    position: relative;
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 24px 28px;
    overflow: hidden;
  }
  .lp-accent-bar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 6px;
    border-radius: 2px 2px 0 0;
  }
  .lp-detail-title {
    font-size: 1.05rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 6px 0 18px 0;
  }
  .lp-category-header {
    font-size: 0.82rem;
    font-weight: 600;
    color: #60a5fa;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin: 20px 0 10px 0;
  }
  .lp-category-header:first-of-type {
    margin-top: 0;
  }
  .lp-feature {
    margin-bottom: 16px;
  }
  .lp-feature-name {
    font-size: 0.9rem;
    font-weight: 600;
    color: #e4e6eb;
    margin-bottom: 4px;
  }
  .lp-feature-desc {
    font-size: 0.82rem;
    color: #b0b6c0;
    line-height: 1.6;
    margin-bottom: 6px;
  }

  /* Telemetry subsections */
  .lp-telem-sections {
    margin-top: 8px;
    padding-left: 12px;
    border-left: 2px solid rgba(255, 255, 255, 0.06);
  }
  .lp-telem-sub {
    margin-bottom: 10px;
  }
  .lp-telem-label {
    font-size: 0.82rem;
    font-weight: 600;
    color: #e4e6eb;
    display: block;
    margin-bottom: 3px;
  }
  .lp-telem-text {
    font-size: 0.82rem;
    color: #b0b6c0;
    line-height: 1.6;
  }

  /* ---- Unified Purchase panel ---- */
  .lup-panel {
    max-width: 900px;
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }

  /* Context pane */
  .lup-context {
    margin-bottom: 20px;
    position: relative;
    padding-left: 16px;
  }
  .lup-context-bar {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: #60a5fa;
    border-radius: 2px;
  }
  .lup-context-bar-green { background: #22c55e; }
  .lup-context-text {
    font-size: 0.95rem;
    color: #e4e6eb;
    margin: 0;
    line-height: 1.6;
  }

  /* Plan selector — full-width panes (reuses lp-tier-row pattern) */
  .lup-selector {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 20px;
  }
  .lup-sel-row {
    display: grid;
    grid-template-columns: 140px 1fr auto auto;
    align-items: center;
    gap: 12px;
    background: rgba(255, 255, 255, 0.04);
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-left: 3px solid transparent;
    border-radius: 2px;
    color: #e4e6eb;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    padding: 10px 16px;
    text-align: left;
    transition: background 0.15s, border-color 0.15s;
  }
  .lup-sel-row:hover:not([disabled]) {
    background: rgba(96, 165, 250, 0.06);
  }
  .lup-sel-row:focus-visible {
    outline: 2px solid #60a5fa;
    outline-offset: 2px;
  }
  .lup-sel-active {
    background: rgba(96, 165, 250, 0.08);
    border-color: rgba(96, 165, 250, 0.3);
    border-left-color: #60a5fa;
  }
  .lup-sel-recommended {
    border-left-color: #22c55e;
    background: rgba(34, 197, 94, 0.04);
  }
  .lup-sel-recommended.lup-sel-active {
    background: rgba(34, 197, 94, 0.08);
    border-color: rgba(34, 197, 94, 0.3);
    border-left-color: #22c55e;
  }
  .lup-sel-disabled {
    opacity: 0.4;
    cursor: default;
  }
  .lup-sel-name {
    font-size: 0.95rem;
    font-weight: 600;
  }
  .lup-sel-spec {
    font-size: 0.82rem;
    color: #60a5fa;
  }
  .lup-sel-price {
    font-size: 0.82rem;
    color: #8b919a;
    text-align: right;
  }
  .lup-sel-badge {
    font-size: 0.65rem;
    font-weight: 600;
    padding: 2px 8px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .lup-sel-badge-rec {
    color: #22c55e;
  }
  .lup-sel-badge-current {
    color: #60a5fa;
  }

  /* Two-column layout */
  .lup-columns {
    display: flex;
    gap: 20px;
    margin-bottom: 20px;
  }
  .lup-col-left {
    flex: 1;
    min-width: 0;
  }
  .lup-col-right {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  /* Pane containers */
  .lup-pane {
    background: rgba(255, 255, 255, 0.02);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 16px 20px;
    position: relative;
  }
  .lup-pane-bar {
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    border-radius: 2px 0 0 2px;
  }
  .lup-pane-bar-amber { background: #f5a623; }
  .lup-pane-bar-blue { background: #60a5fa; }
  .lup-pane-bar-green { background: #22c55e; }
  .lup-pane-heading {
    font-size: 1rem;
    font-weight: 600;
    color: #60a5fa;
    margin: 0 0 12px 0;
  }
  .lup-pane-desc {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.5;
    margin: 0 0 12px 0;
  }
  .lup-pane-note {
    font-size: 0.75rem;
    color: #6b7280;
    margin: 8px 0 0 0;
  }

  /* Form fields */
  .lup-section-label {
    font-size: 0.82rem;
    font-weight: 600;
    color: #6b7280;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 8px;
  }
  .lup-field {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-bottom: 12px;
  }
  .lup-label {
    font-size: 0.82rem;
    font-weight: 500;
    color: #e4e6eb;
    line-height: 1.4;
  }
  .lup-input {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.9rem;
    padding: 8px 12px;
    outline: none;
    transition: border-color 0.15s;
  }
  .lup-input:focus { border-color: #60a5fa; }
  .lup-input::placeholder { color: #6b7280; }
  .lup-input-wide { width: 100%; box-sizing: border-box; }
  .lup-textarea {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.9rem;
    padding: 8px 12px;
    width: 100%;
    box-sizing: border-box;
    outline: none;
    resize: vertical;
    transition: border-color 0.15s;
  }
  .lup-textarea:focus { border-color: #60a5fa; }
  .lup-textarea::placeholder { color: #6b7280; }

  /* Selectable card options */
  .lup-card-options {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .lup-card-option {
    background: rgba(255, 255, 255, 0.04);
    border: 1px dashed rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    color: #e4e6eb;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    padding: 10px 14px;
    text-align: left;
    transition: background 0.15s, border-color 0.15s;
    display: flex;
    flex-direction: column;
    gap: 3px;
  }
  .lup-card-option:hover {
    background: rgba(96, 165, 250, 0.06);
  }
  .lup-card-option:focus-visible {
    outline: 2px solid #60a5fa;
    outline-offset: 2px;
  }
  .lup-card-selected {
    background: rgba(34, 197, 94, 0.06);
    border-color: rgba(34, 197, 94, 0.4);
  }
  .lup-card-title {
    font-size: 0.9rem;
    font-weight: 600;
  }
  .lup-card-hint {
    font-size: 0.75rem;
    color: #8b919a;
  }

  /* Institution yes/no buttons */
  .lup-yn-row {
    display: flex;
    gap: 8px;
  }
  .lup-yn-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    color: #e4e6eb;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.9rem;
    padding: 6px 20px;
    transition: background 0.15s, border-color 0.15s;
  }
  .lup-yn-btn:hover {
    background: rgba(96, 165, 250, 0.06);
  }
  .lup-yn-active {
    background: rgba(34, 197, 94, 0.06);
    border-color: rgba(34, 197, 94, 0.4);
    color: #22c55e;
  }

  /* Purchase pane */
  .lup-purchase-pane {
    background: rgba(255, 255, 255, 0.02);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 16px 20px;
    position: relative;
    margin-bottom: 16px;
  }
  .lup-purchase-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 8px;
    flex-wrap: wrap;
  }
  .lup-purchase-plan {
    font-size: 1rem;
    font-weight: 700;
    color: #e4e6eb;
  }
  .lup-purchase-price {
    font-size: 1rem;
    font-weight: 600;
    color: #60a5fa;
  }
  .lup-purchase-billing {
    font-size: 0.82rem;
    color: #8b919a;
  }
  .lup-purchase-dates {
    font-size: 0.82rem;
    color: #8b919a;
    margin-bottom: 14px;
  }
  .lup-date-blue {
    color: #60a5fa;
    font-weight: 500;
  }
  .lup-purchase-divider {
    height: 1px;
    background: rgba(255, 255, 255, 0.06);
    margin: 14px 0;
  }
  .lup-invoice-btn {
    background: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    color: #e4e6eb;
    cursor: pointer;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 8px 14px;
    transition: background 0.15s;
  }
  .lup-invoice-btn:hover { background: rgba(96, 165, 250, 0.08); }
  .lup-invoice-disabled {
    opacity: 0.4;
    cursor: default;
  }
  .lup-invoice-disabled:hover { background: rgba(255, 255, 255, 0.04); }

  /* Action error */
  .lup-action-error {
    color: #f5a623;
    background: rgba(245, 166, 35, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 2px;
    margin-top: 12px;
  }

  /* Management card */
  .lup-mgmt-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
  }
  .lup-mgmt-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 0.82rem;
  }
  .lup-mgmt-label {
    color: #6b7280;
    font-weight: 500;
  }
  .lup-mgmt-value {
    color: #e4e6eb;
    font-weight: 600;
  }

  /* Renewal */
  .lup-renewal-section {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 14px;
  }
  .lup-renewal-status {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.82rem;
    color: #e4e6eb;
  }
  .lup-renewal-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .lup-renewal-guidance {
    margin-bottom: 14px;
  }
  .lup-renewal-guidance-text {
    font-size: 0.85rem;
    color: var(--muted, #8b919a);
    margin: 0;
    line-height: 1.5;
  }

  /* Confirm dialog */
  .lup-confirm-card {
    background: rgba(245, 166, 35, 0.06);
    border: 1px dashed rgba(245, 166, 35, 0.2);
    border-radius: 2px;
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
    color: #f5a623;
    background: rgba(245, 166, 35, 0.10);
    font-size: 0.82rem;
    padding: 10px 14px;
    border-radius: 2px;
  }


  /* Token & activate sections */
  .lup-token-section {
    margin-top: 14px;
    padding-top: 14px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
  }
  .lup-token-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 8px;
  }
  .lup-section-heading {
    font-size: 0.88rem;
    font-weight: 600;
    color: #e4e6eb;
    margin: 0 0 4px 0;
  }
  .lup-section-desc {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.5;
    margin: 0 0 8px 0;
  }
  .lup-activate-section {
    background: rgba(255, 255, 255, 0.02);
    border: 1px dashed rgba(255, 255, 255, 0.06);
    border-radius: 2px;
    padding: 16px 20px;
    position: relative;
    margin-bottom: 16px;
  }
  .lup-activate-textarea {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Menlo", "Consolas", monospace;
    font-size: 0.82rem;
    padding: 8px 12px;
    width: 100%;
    box-sizing: border-box;
    outline: none;
    resize: vertical;
    transition: border-color 0.15s;
  }
  .lup-activate-textarea:focus { border-color: #60a5fa; }
  .lup-activate-textarea::placeholder { color: #6b7280; }
  .lup-activate-preview {
    font-size: 0.82rem;
    color: #22c55e;
    background: rgba(34, 197, 94, 0.06);
    padding: 8px 12px;
    border-radius: 2px;
    margin-top: 8px;
  }
  .lup-activate-error {
    font-size: 0.82rem;
    color: #f5a623;
    background: rgba(245, 166, 35, 0.10);
    padding: 8px 12px;
    border-radius: 2px;
    margin-top: 8px;
  }
  .lup-save-prompt-card {
    background: rgba(96, 165, 250, 0.06);
    border: 1px dashed rgba(96, 165, 250, 0.2);
    border-radius: 2px;
    padding: 14px 18px;
    margin-bottom: 16px;
  }
  .lup-save-prompt-text {
    font-size: 0.88rem;
    color: #e4e6eb;
    margin: 0 0 10px 0;
    line-height: 1.5;
  }
  .lup-activate-collapsible {
    margin-bottom: 16px;
  }
  .lup-activate-summary {
    font-size: 0.88rem;
    font-weight: 500;
    color: #60a5fa;
    cursor: pointer;
    padding: 8px 0;
  }
  .lup-activate-summary:hover { text-decoration: underline; }
  .lup-activate-inline {
    margin-top: 10px;
    border: none;
    padding: 0;
    background: none;
  }

  .lup-machines-section { margin-bottom: 16px; }
  .lup-machines-list { margin-bottom: 12px; }
  .lup-machine-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.06); }
  .lup-machine-info { display: flex; flex-direction: column; gap: 2px; }
  .lup-machine-hostname { font-weight: 500; font-size: 0.88rem; color: #e4e6eb; }
  .lup-machine-meta { font-size: 0.75rem; color: #8b919a; font-family: "Menlo", monospace; }
  .lup-machine-count { font-size: 0.82rem; color: #8b919a; margin-top: 8px; }
  .lup-machines-actions { margin-top: 10px; }
  .lup-sharing-address { font-family: "Menlo", monospace; font-size: 1.1rem; color: #60a5fa; background: rgba(96,165,250,0.08); padding: 10px 14px; border-radius: 2px; margin: 8px 0; text-align: center; user-select: all; }
  .lup-sharing-waiting { font-size: 0.85rem; color: #8b919a; font-style: italic; margin: 8px 0; }
  .lup-sharing-request { background: rgba(245,166,35,0.06); border: 1px dashed rgba(245,166,35,0.2); border-radius: 2px; padding: 14px 18px; margin: 10px 0; }
  .lup-sharing-request-text { font-size: 0.88rem; color: #e4e6eb; margin: 0 0 10px 0; line-height: 1.5; }
  .lup-sharing-request-actions { display: flex; gap: 8px; }
  .lup-join-section { margin-top: 10px; }
  .lup-join-row { display: flex; gap: 8px; margin-bottom: 8px; }
  .lup-join-input { flex: 1; }
  .lup-join-status { font-size: 0.85rem; color: #8b919a; font-style: italic; margin: 8px 0; }
  .lup-join-error { font-size: 0.82rem; color: #f5a623; background: rgba(245,166,35,0.10); padding: 8px 12px; border-radius: 2px; margin: 8px 0; }
  .lup-join-peers { margin: 8px 0; }
  .lup-join-peer { cursor: pointer; padding: 8px 12px; border-radius: 2px; background: rgba(255,255,255,0.03); margin-bottom: 4px; font-size: 0.85rem; color: #e4e6eb; }
  .lup-join-peer:hover { background: rgba(96,165,250,0.08); }

  @media (max-width: 600px) {
    .ll-status-pane {
      padding: 14px 16px;
    }
    .ll-sp-grid {
      grid-template-columns: 70px 1fr auto;
      gap: 3px 8px;
      padding-left: 12px;
    }
    .ll-sp-intro {
      padding-left: 12px;
    }
    .ll-terms-sliver {
      border-radius: 2px;
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
    .lcd-why-row {
      flex-direction: column;
    }
    .lcd-action-row {
      grid-template-columns: 1fr;
    }
    .lp-tier-row {
      grid-template-columns: 120px 1fr auto;
      padding: 10px 12px;
      gap: 8px;
    }
    .lp-detail {
      padding: 18px 16px;
    }
    .lup-columns {
      flex-direction: column;
    }
    .lup-sel-row {
      grid-template-columns: 100px 1fr auto;
    }
    .lup-input {
      width: 100%;
    }
    .lqc-why-row {
      flex-direction: column;
    }
    .lqc-action-row {
      grid-template-columns: 1fr;
    }
  }
`;
document.head.appendChild(licStyles);
