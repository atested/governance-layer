/**
 * Questionnaire engine — 6-state machine, capacity gate, climbing procedure,
 * and state reconstruction from chain events.
 *
 * The engine is a pure-logic module.  It takes answers and produces:
 * - Current state machine state
 * - Current tier recommendation (if any)
 * - The next question to display
 * - Whether the recommendation is verified
 *
 * The engine does not touch the DOM or the network.  The UI panel calls
 * the engine and renders the results.
 *
 * Spec v1 section 3.  Dispatch 026-D-2026-0417 Phase 2.
 */

import {
  CAPACITY_QUESTIONS,
  CLIMBING_QUESTIONS,
  PHASE_TWO_QUESTIONS,
  TIERS,
  TIER_LABELS,
  BOUNDARIES,
  boundaryFrom,
} from './question-catalog.js';

// ---------- States ----------

export const STATES = {
  EMPTY: 'EMPTY',
  CAPACITY: 'CAPACITY',
  CLIMBING: 'CLIMBING',
  THRESHOLD: 'THRESHOLD',
  PHASE_TWO: 'PHASE_TWO',
  COMPLETE: 'COMPLETE',
};

// ---------- Capacity gate ----------

/**
 * Determine the base tier from capacity inputs.
 * Spec v1 section 3.2.
 *
 * @param {number} userCount
 * @param {number} machineCount
 * @returns {string} tier id
 */
export function computeBaseTier(userCount, machineCount) {
  if (userCount >= 51) return 'institution';
  if (userCount >= 13) return 'team';
  if (userCount >= 2) return 'crew';
  // Single user — check machine count
  if (machineCount >= 2) return 'personal_plus';
  return 'personal';
}

// ---------- Climbing procedure ----------

/**
 * Run the deterministic climbing procedure from a base tier using the
 * current set of climbing answers.
 *
 * Returns:
 *   {
 *     recommendedTier: string,
 *     verified: boolean,          // true if a boundary test failed (recommendation confirmed)
 *     currentBoundary: string|null, // boundary key being tested (null if done)
 *     nextQuestion: object|null,  // next climbing question to ask
 *     climbPath: string[],        // tiers climbed through
 *     failedBoundary: string|null, // the boundary where climbing stopped
 *   }
 *
 * @param {string} baseTier - tier from capacity gate
 * @param {Object} answers - map of question_id → answer_value
 */
export function runClimbingProcedure(baseTier, answers) {
  const baseTierIndex = TIERS.indexOf(baseTier);
  let currentTier = baseTier;
  const climbPath = [baseTier];
  let failedBoundary = null;

  // Walk boundaries from baseTier upward
  for (let i = baseTierIndex; i < TIERS.length - 1; i++) {
    const boundary = BOUNDARIES[i];
    if (!boundary || boundary.from !== TIERS[i]) continue;

    const questions = CLIMBING_QUESTIONS[boundary.key] || [];
    const diagnosticQ = _pickDiagnosticQuestion(questions, answers);

    if (!diagnosticQ) {
      // All questions for this boundary answered — evaluate
      const climbs = _evaluateBoundary(questions, answers);
      if (climbs) {
        currentTier = boundary.to;
        climbPath.push(boundary.to);
        continue;
      } else {
        failedBoundary = boundary.key;
        break;
      }
    }

    // There's an unanswered diagnostic question — need more input
    return {
      recommendedTier: currentTier,
      verified: false,
      currentBoundary: boundary.key,
      nextQuestion: diagnosticQ,
      climbPath,
      failedBoundary: null,
    };
  }

  // If we reached Institution without failing, recommendation is Institution (verified by ceiling)
  const verified = currentTier === 'institution' || failedBoundary !== null;

  return {
    recommendedTier: currentTier,
    verified,
    currentBoundary: null,
    nextQuestion: null,
    climbPath,
    failedBoundary,
  };
}

/**
 * Pick the first unanswered question from a boundary's question set.
 */
function _pickDiagnosticQuestion(questions, answers) {
  for (const q of questions) {
    if (!(q.id in answers)) return q;
  }
  return null;
}

/**
 * Evaluate whether a boundary was climbed based on answers.
 * Any 'yes' answer at a boundary means the operator needs the higher tier.
 * 'no' and 'skip' both mean no need.
 */
function _evaluateBoundary(questions, answers) {
  for (const q of questions) {
    const val = answers[q.id];
    if (val === 'yes') return true;
  }
  return false;
}

// ---------- Phase-two question selection ----------

/**
 * Get the next unanswered phase-two question for the recommended tier.
 * Returns null if all phase-two questions for the tier are answered.
 */
export function getNextPhaseTwoQuestion(recommendedTier, answers) {
  const questions = PHASE_TWO_QUESTIONS[recommendedTier] || [];
  for (const q of questions) {
    if (!(q.id in answers)) return q;
  }
  return null;
}

/**
 * Count answered phase-two questions for a tier.
 */
export function countPhaseTwoAnswered(recommendedTier, answers) {
  const questions = PHASE_TWO_QUESTIONS[recommendedTier] || [];
  return questions.filter(q => q.id in answers).length;
}

/**
 * Total phase-two questions for a tier.
 */
export function countPhaseTwoTotal(recommendedTier) {
  return (PHASE_TWO_QUESTIONS[recommendedTier] || []).length;
}

// ---------- State reconstruction from chain events ----------

/**
 * Reconstruct the full questionnaire state from chain event data.
 * This is the resumability core — the chain is the source of truth.
 *
 * @param {Object} chainData - { answers: [{question_id, answer_value, ...}], capacity: {user_count, machine_count, base_tier} | null }
 * @returns {QuestionnaireState}
 */
export function reconstructState(chainData) {
  const { answers: rawAnswers, capacity } = chainData;

  // Build latest-answer map (last answer per question_id wins)
  const answers = {};
  if (rawAnswers && rawAnswers.length > 0) {
    for (const a of rawAnswers) {
      answers[a.question_id] = a.answer_value;
    }
  }

  // No capacity inputs yet — check if we're EMPTY or CAPACITY
  if (!capacity) {
    const hasAnyAnswers = Object.keys(answers).length > 0;
    return {
      state: hasAnyAnswers ? STATES.CAPACITY : STATES.EMPTY,
      answers,
      capacity: null,
      baseTier: null,
      recommendation: null,
      verified: false,
      nextQuestion: null,
      currentBoundary: null,
      climbPath: [],
      failedBoundary: null,
      phaseTwoAnswered: 0,
      phaseTwoTotal: 0,
    };
  }

  const baseTier = capacity.base_tier || computeBaseTier(capacity.user_count, capacity.machine_count);

  // Run the climbing procedure with current answers
  const climb = runClimbingProcedure(baseTier, answers);

  if (!climb.verified) {
    // Still climbing — need more boundary answers
    return {
      state: STATES.CLIMBING,
      answers,
      capacity,
      baseTier,
      recommendation: climb.recommendedTier,
      verified: false,
      nextQuestion: climb.nextQuestion,
      currentBoundary: climb.currentBoundary,
      climbPath: climb.climbPath,
      failedBoundary: null,
      phaseTwoAnswered: 0,
      phaseTwoTotal: countPhaseTwoTotal(climb.recommendedTier),
    };
  }

  // Recommendation is verified — determine if we're THRESHOLD, PHASE_TWO, or COMPLETE
  const p2Answered = countPhaseTwoAnswered(climb.recommendedTier, answers);
  const p2Total = countPhaseTwoTotal(climb.recommendedTier);
  const nextP2 = getNextPhaseTwoQuestion(climb.recommendedTier, answers);

  let state;
  if (p2Answered === 0) {
    state = STATES.THRESHOLD;
  } else if (p2Answered < p2Total) {
    state = STATES.PHASE_TWO;
  } else {
    state = STATES.COMPLETE;
  }

  return {
    state,
    answers,
    capacity,
    baseTier,
    recommendation: climb.recommendedTier,
    verified: true,
    nextQuestion: nextP2,
    currentBoundary: null,
    climbPath: climb.climbPath,
    failedBoundary: climb.failedBoundary,
    phaseTwoAnswered: p2Answered,
    phaseTwoTotal: p2Total,
  };
}

// ---------- Climbing progress estimation ----------

/**
 * Estimate total climbing questions remaining from the current position.
 * Used for the progress display: "Question N of approximately M."
 */
export function estimateClimbingTotal(baseTier, answers) {
  const baseTierIndex = TIERS.indexOf(baseTier);
  let total = 0;
  let answered = 0;

  for (let i = baseTierIndex; i < TIERS.length - 1; i++) {
    const boundary = BOUNDARIES[i];
    if (!boundary) continue;
    // Each boundary contributes 1 diagnostic question
    total += 1;
    const questions = CLIMBING_QUESTIONS[boundary.key] || [];
    const allAnswered = questions.every(q => q.id in answers);
    if (allAnswered) answered += 1;
  }

  return { total, answered };
}

// ---------- Answer change detection ----------

/**
 * Check if changing a question's answer would affect the recommendation.
 * Used to determine whether operator identity unlock is required.
 *
 * @param {string} questionId - the question being re-answered
 * @param {string} newValue - the new answer value
 * @param {Object} currentState - current QuestionnaireState from reconstructState()
 * @returns {boolean} true if the change is consequential (affects recommendation)
 */
export function isConsequentialChange(questionId, newValue, currentState) {
  if (!currentState.verified) return false; // No recommendation to affect
  if (!(questionId in currentState.answers)) return false; // First-time answer
  if (currentState.answers[questionId] === newValue) return false; // Same answer

  // Check if it's a climbing question (boundary question)
  for (const boundary of BOUNDARIES) {
    const questions = CLIMBING_QUESTIONS[boundary.key] || [];
    if (questions.some(q => q.id === questionId)) {
      return true; // Boundary questions always affect recommendation
    }
  }

  // Capacity input changes always affect recommendation
  if (questionId === 'cap_user_count' || questionId === 'cap_machine_count') {
    return true;
  }

  // Phase-two questions don't affect recommendation
  return false;
}

// ---------- Threshold messaging ----------

/**
 * Generate the "why not lower" and "why not higher" reasoning for the
 * threshold display.
 *
 * @param {Object} state - QuestionnaireState from reconstructState()
 * @returns {{ whyNotLower: string|null, whyNotHigher: string|null }}
 */
export function thresholdReasoning(state) {
  if (!state.verified || !state.recommendation) return { whyNotLower: null, whyNotHigher: null };

  const recIndex = TIERS.indexOf(state.recommendation);
  let whyNotLower = null;
  let whyNotHigher = null;

  // Why not lower: capacity or climbing from a lower tier passed
  if (recIndex > 0) {
    if (state.baseTier !== state.recommendation) {
      // Climbed above base tier
      const climbedBoundaries = state.climbPath.slice(1).map(tier => {
        const idx = TIERS.indexOf(tier);
        return TIER_LABELS[tier];
      });
      whyNotLower = `Your answers show a need for features in ${TIER_LABELS[state.recommendation]}. ` +
        `You climbed through ${climbedBoundaries.join(', ')} based on your feature needs.`;
    } else if (state.capacity) {
      // Base tier from capacity
      whyNotLower = `Your organization size (${state.capacity.user_count} user${state.capacity.user_count !== 1 ? 's' : ''}) ` +
        `places you at ${TIER_LABELS[state.recommendation]} as the minimum tier.`;
    }
  }

  // Why not higher: boundary test failed or at ceiling
  if (state.recommendation === 'institution') {
    whyNotHigher = 'Institution is the highest tier — it includes everything.';
  } else if (state.failedBoundary) {
    const boundary = BOUNDARIES.find(b => b.key === state.failedBoundary);
    if (boundary) {
      whyNotHigher = `Your answers indicate that ${TIER_LABELS[boundary.to]} features ` +
        `are not needed for your current situation.`;
    }
  }

  return { whyNotLower, whyNotHigher };
}

// Re-export for convenience
export { TIER_LABELS, TIERS, CAPACITY_QUESTIONS };
