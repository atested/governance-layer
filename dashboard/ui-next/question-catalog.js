/**
 * Question catalog — placeholder questions for the licensing questionnaire.
 *
 * This module is a pure data module. The questionnaire engine imports the
 * catalog and selects questions based on the current state machine state.
 * Real questions replace these placeholders without changing the engine.
 *
 * Spec v1 section 3.  Dispatch 026-D-2026-0417 Phase 2.
 */

// ---------- Capacity questions ----------

/**
 * Capacity gate inputs.  These are not questionnaire_response events —
 * they persist as capacity_inputs events.  The catalog defines the labels
 * and validation so the engine stays content-agnostic.
 */
export const CAPACITY_QUESTIONS = [
  {
    id: 'cap_user_count',
    label: 'How many people will use Atested at your organization?',
    inputType: 'number',
    min: 1,
    placeholder: '1',
  },
  {
    id: 'cap_machine_count',
    label: 'How many machines will run Atested?',
    inputType: 'number',
    min: 1,
    placeholder: '1',
    /** Only shown when user count is 1 (spec §3.2). */
    showWhen: (answers) => answers.cap_user_count === 1,
  },
];

// ---------- Tier definitions for the procedure ----------

export const TIERS = ['personal', 'personal_plus', 'crew', 'team', 'institution'];

export const TIER_LABELS = {
  personal: 'Personal',
  personal_plus: 'Personal Plus',
  crew: 'Crew',
  team: 'Team',
  institution: 'Institution',
};

// ---------- Climbing questions (per boundary) ----------

/**
 * Each boundary has an array of diagnostic questions.  The climbing
 * procedure picks the first unanswered question per boundary.
 *
 * answer_key values:
 *   'yes' — indicates the operator needs the next-tier feature (climb)
 *   'no'  — indicates no need (stop, recommend current tier)
 *   'skip' — treated as 'no' for boundary evaluation
 */
export const CLIMBING_QUESTIONS = {
  personal_to_personal_plus: [
    {
      id: 'climb_pp_multi_machine',
      text: 'Do you run Atested on more than one machine (e.g. laptop and CI server)?',
      context: 'This helps determine whether Personal Plus multi-machine support is relevant.',
      boundary: 'personal_to_personal_plus',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
    {
      id: 'climb_pp_priority',
      text: 'Would dedicated support through the Atested feedback system be valuable to you?',
      context: 'Personal Plus includes support through the Atested feedback system.',
      boundary: 'personal_to_personal_plus',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
  ],

  personal_plus_to_crew: [
    {
      id: 'climb_crew_multi_user',
      text: 'Do multiple people at your organization need to use governed AI applications?',
      context: 'Crew supports 2-12 operators with shared governance.',
      boundary: 'personal_plus_to_crew',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
    {
      id: 'climb_crew_shared_chain',
      text: 'Do you need a shared governance chain across team members?',
      context: 'Crew provides a unified governance chain for team-level auditability.',
      boundary: 'personal_plus_to_crew',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
  ],

  crew_to_team: [
    {
      id: 'climb_team_scale',
      text: 'Does your team have more than 12 people using AI applications?',
      context: 'Team supports 13-50 operators with advanced governance.',
      boundary: 'crew_to_team',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
    {
      id: 'climb_team_roles',
      text: 'Do you need role-based access control for governance operations?',
      context: 'Team includes role-based governance with configurable permissions.',
      boundary: 'crew_to_team',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
  ],

  team_to_institution: [
    {
      id: 'climb_inst_scale',
      text: 'Does your organization have more than 50 people using AI applications?',
      context: 'Institution supports 51+ operators with enterprise governance.',
      boundary: 'team_to_institution',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
    {
      id: 'climb_inst_compliance',
      text: 'Do you need dedicated compliance reporting and audit export for AI governance?',
      context: 'Institution includes dedicated compliance support and custom audit integrations.',
      boundary: 'team_to_institution',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
    {
      id: 'climb_inst_dedicated',
      text: 'Would dedicated support with a named contact be valuable?',
      context: 'Institution includes dedicated support through the Atested feedback system with a named contact.',
      boundary: 'team_to_institution',
      options: [
        { value: 'yes', label: 'Yes' },
        { value: 'no', label: 'No' },
      ],
    },
  ],
};

// ---------- Phase-two refinement questions (per tier) ----------

/**
 * Phase-two questions refine the case document within the recommended tier.
 * They don't change the recommendation.  Each question enriches the case
 * document with detail about features the operator gets at their tier.
 */
export const PHASE_TWO_QUESTIONS = {
  personal: [
    {
      id: 'p2_personal_solo',
      text: 'Are you the only person making AI governance decisions at your organization?',
      context: 'This adds detail about your governance operating model to the case document.',
      options: [
        { value: 'yes', label: 'Yes, just me' },
        { value: 'no', label: 'Others are involved but only I use Atested' },
      ],
    },
    {
      id: 'p2_personal_chain_use',
      text: 'How do you primarily use the governance chain?',
      context: 'This helps describe your audit and compliance posture.',
      options: [
        { value: 'audit', label: 'For audit trail and compliance' },
        { value: 'visibility', label: 'For visibility into what agents do' },
        { value: 'both', label: 'Both equally' },
      ],
    },
  ],

  personal_plus: [
    {
      id: 'p2_pp_machines',
      text: 'How do you distribute Atested across your machines?',
      context: 'This documents your multi-machine governance setup.',
      options: [
        { value: 'dev_ci', label: 'Development machine + CI/CD' },
        { value: 'multi_dev', label: 'Multiple development machines' },
        { value: 'mixed', label: 'Mix of development, CI, and staging' },
      ],
    },
    {
      id: 'p2_pp_support',
      text: 'What governance topics would you most want support for?',
      context: 'This helps characterize the support value for the case document.',
      options: [
        { value: 'policy', label: 'Policy configuration' },
        { value: 'integration', label: 'Integration with existing tools' },
        { value: 'compliance', label: 'Compliance and audit questions' },
      ],
    },
  ],

  crew: [
    {
      id: 'p2_crew_structure',
      text: 'How is your team structured for AI application usage?',
      context: 'This documents your team governance model.',
      options: [
        { value: 'centralized', label: 'Centralized — one person manages governance' },
        { value: 'distributed', label: 'Distributed — each person manages their own' },
        { value: 'hybrid', label: 'Hybrid — shared chain with individual oversight' },
      ],
    },
    {
      id: 'p2_crew_agents',
      text: 'How many AI applications does your team typically run concurrently?',
      context: 'This adds scale context to the case document.',
      options: [
        { value: 'few', label: '1-5 applications' },
        { value: 'moderate', label: '6-20 applications' },
        { value: 'many', label: '20+ applications' },
      ],
    },
  ],

  team: [
    {
      id: 'p2_team_departments',
      text: 'Do multiple departments or teams use AI applications?',
      context: 'This documents cross-team governance needs.',
      options: [
        { value: 'single', label: 'Single team' },
        { value: 'few', label: '2-3 teams' },
        { value: 'many', label: '4+ teams or departments' },
      ],
    },
    {
      id: 'p2_team_compliance',
      text: 'What compliance frameworks apply to your AI application usage?',
      context: 'This adds compliance context to the case document.',
      options: [
        { value: 'internal', label: 'Internal policies only' },
        { value: 'regulatory', label: 'External regulatory requirements' },
        { value: 'both', label: 'Both internal and regulatory' },
        { value: 'none', label: 'None yet, exploring' },
      ],
    },
  ],

  institution: [
    {
      id: 'p2_inst_geography',
      text: 'Does your AI application deployment span multiple geographic regions?',
      context: 'This documents data residency and compliance needs.',
      options: [
        { value: 'single', label: 'Single region' },
        { value: 'multi', label: 'Multiple regions' },
        { value: 'global', label: 'Global deployment' },
      ],
    },
    {
      id: 'p2_inst_integration',
      text: 'What existing enterprise systems need to integrate with AI governance?',
      context: 'This documents integration requirements for the case document.',
      options: [
        { value: 'siem', label: 'SIEM / security tools' },
        { value: 'grc', label: 'GRC platforms' },
        { value: 'cicd', label: 'CI/CD and DevOps tooling' },
        { value: 'multiple', label: 'Multiple of the above' },
      ],
    },
    {
      id: 'p2_inst_timeline',
      text: 'What is your timeline for deploying governed AI applications at scale?',
      context: 'This adds deployment planning context.',
      options: [
        { value: 'now', label: 'Already deploying' },
        { value: 'quarter', label: 'This quarter' },
        { value: 'year', label: 'Within the year' },
        { value: 'exploring', label: 'Still exploring' },
      ],
    },
  ],
};

// ---------- Boundary ordering ----------

/**
 * Ordered list of tier boundaries for the climbing procedure.
 * Each entry maps a boundary key to the tier being tested and the
 * tier the operator would climb to.
 */
export const BOUNDARIES = [
  { key: 'personal_to_personal_plus', from: 'personal', to: 'personal_plus' },
  { key: 'personal_plus_to_crew', from: 'personal_plus', to: 'crew' },
  { key: 'crew_to_team', from: 'crew', to: 'team' },
  { key: 'team_to_institution', from: 'team', to: 'institution' },
];

/**
 * Look up the boundary key for climbing from `fromTier` to the next tier.
 * Returns null if fromTier is already the highest.
 */
export function boundaryFrom(fromTier) {
  return BOUNDARIES.find(b => b.from === fromTier) || null;
}
