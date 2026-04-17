/**
 * Tier definitions and translation templates — static data module.
 *
 * This module defines:
 * - Tier capability sets (features per tier, grouped by category)
 * - Commercial terms (pricing, billing, support, dating)
 * - Translation templates (feature ID → buyer-facing text)
 * - Capacity ranges per tier
 *
 * Content is placeholder.  Real content replaces this module without
 * changing the case document assembly or tier display code.
 *
 * Spec v1 sections 2, 4.3.  Dispatch 027-D-2026-0417 Phase 3.
 */

// ---------- Capacity ranges ----------

export const CAPACITY_RANGES = {
  personal:      '1 user, 1 machine',
  personal_plus: '1 user, up to 3 machines',
  crew:          '2\u201312 users',
  team:          '13\u201350 users',
  institution:   '51+ users (negotiated)',
};

// ---------- Commercial terms ----------

export const COMMERCIAL_TERMS = {
  personal: {
    price: 'Free',
    billing: 'N/A',
    support: 'Community',
    dating: 'From registration',
    summary: 'Single operator, full governance chain, community support.',
  },
  personal_plus: {
    price: '$99/yr',
    billing: 'Annual',
    support: 'Email',
    dating: 'From purchase',
    summary: 'Single operator, multi-machine, priority email support.',
  },
  crew: {
    price: '$299/yr',
    billing: 'Annual',
    support: 'Email',
    dating: 'From trial completion',
    summary: '2\u201312 operators, shared governance chain, team visibility.',
  },
  team: {
    price: '$799/yr',
    billing: 'Annual',
    support: 'Priority',
    dating: 'From trial completion',
    summary: '13\u201350 operators, role-based governance, priority support.',
  },
  institution: {
    price: 'Negotiated',
    billing: 'Annual',
    support: 'Dedicated',
    dating: 'From trial completion',
    summary: '51+ operators, enterprise governance, dedicated support.',
  },
};

// ---------- Capability categories ----------

export const CATEGORIES = [
  'Governance',
  'Visibility',
  'Operations',
  'Support',
];

// ---------- Capabilities per tier ----------

/**
 * Each capability has:
 *   id       — stable identifier (matches translation template keys)
 *   name     — human-readable short name
 *   category — one of CATEGORIES
 *   isNew    — true if this capability is new at this tier (not in the tier below)
 *
 * Capabilities accumulate: higher tiers include all lower-tier capabilities
 * plus their own new ones.
 */
export const TIER_CAPABILITIES = {
  personal: [
    { id: 'gov_chain',       name: 'Governance Chain',         category: 'Governance', isNew: true },
    { id: 'gov_policy',      name: 'Policy Evaluation',        category: 'Governance', isNew: true },
    { id: 'vis_dashboard',   name: 'Dashboard',                category: 'Visibility', isNew: true },
    { id: 'vis_audit',       name: 'Audit Trail',              category: 'Visibility', isNew: true },
    { id: 'ops_single',      name: 'Single-Operator Mode',     category: 'Operations', isNew: true },
    { id: 'sup_community',   name: 'Community Support',        category: 'Support',    isNew: true },
  ],

  personal_plus: [
    { id: 'gov_chain',       name: 'Governance Chain',         category: 'Governance', isNew: false },
    { id: 'gov_policy',      name: 'Policy Evaluation',        category: 'Governance', isNew: false },
    { id: 'vis_dashboard',   name: 'Dashboard',                category: 'Visibility', isNew: false },
    { id: 'vis_audit',       name: 'Audit Trail',              category: 'Visibility', isNew: false },
    { id: 'ops_multi_machine', name: 'Multi-Machine Support',  category: 'Operations', isNew: true },
    { id: 'ops_single',      name: 'Single-Operator Mode',     category: 'Operations', isNew: false },
    { id: 'sup_email',       name: 'Email Support',            category: 'Support',    isNew: true },
  ],

  crew: [
    { id: 'gov_chain',       name: 'Governance Chain',         category: 'Governance', isNew: false },
    { id: 'gov_policy',      name: 'Policy Evaluation',        category: 'Governance', isNew: false },
    { id: 'gov_shared',      name: 'Shared Governance Chain',  category: 'Governance', isNew: true },
    { id: 'vis_dashboard',   name: 'Dashboard',                category: 'Visibility', isNew: false },
    { id: 'vis_audit',       name: 'Audit Trail',              category: 'Visibility', isNew: false },
    { id: 'vis_team',        name: 'Team Activity View',       category: 'Visibility', isNew: true },
    { id: 'ops_multi_machine', name: 'Multi-Machine Support',  category: 'Operations', isNew: false },
    { id: 'ops_multi_user',  name: 'Multi-User Governance',    category: 'Operations', isNew: true },
    { id: 'sup_email',       name: 'Email Support',            category: 'Support',    isNew: false },
  ],

  team: [
    { id: 'gov_chain',       name: 'Governance Chain',         category: 'Governance', isNew: false },
    { id: 'gov_policy',      name: 'Policy Evaluation',        category: 'Governance', isNew: false },
    { id: 'gov_shared',      name: 'Shared Governance Chain',  category: 'Governance', isNew: false },
    { id: 'gov_roles',       name: 'Role-Based Governance',    category: 'Governance', isNew: true },
    { id: 'vis_dashboard',   name: 'Dashboard',                category: 'Visibility', isNew: false },
    { id: 'vis_audit',       name: 'Audit Trail',              category: 'Visibility', isNew: false },
    { id: 'vis_team',        name: 'Team Activity View',       category: 'Visibility', isNew: false },
    { id: 'vis_reports',     name: 'Advanced Reporting',        category: 'Visibility', isNew: true },
    { id: 'ops_multi_machine', name: 'Multi-Machine Support',  category: 'Operations', isNew: false },
    { id: 'ops_multi_user',  name: 'Multi-User Governance',    category: 'Operations', isNew: false },
    { id: 'ops_rbac',        name: 'Access Control',           category: 'Operations', isNew: true },
    { id: 'sup_priority',    name: 'Priority Support',         category: 'Support',    isNew: true },
  ],

  institution: [
    { id: 'gov_chain',       name: 'Governance Chain',         category: 'Governance', isNew: false },
    { id: 'gov_policy',      name: 'Policy Evaluation',        category: 'Governance', isNew: false },
    { id: 'gov_shared',      name: 'Shared Governance Chain',  category: 'Governance', isNew: false },
    { id: 'gov_roles',       name: 'Role-Based Governance',    category: 'Governance', isNew: false },
    { id: 'gov_compliance',  name: 'Compliance Reporting',     category: 'Governance', isNew: true },
    { id: 'vis_dashboard',   name: 'Dashboard',                category: 'Visibility', isNew: false },
    { id: 'vis_audit',       name: 'Audit Trail',              category: 'Visibility', isNew: false },
    { id: 'vis_team',        name: 'Team Activity View',       category: 'Visibility', isNew: false },
    { id: 'vis_reports',     name: 'Advanced Reporting',        category: 'Visibility', isNew: false },
    { id: 'vis_enterprise',  name: 'Enterprise Analytics',     category: 'Visibility', isNew: true },
    { id: 'ops_multi_machine', name: 'Multi-Machine Support',  category: 'Operations', isNew: false },
    { id: 'ops_multi_user',  name: 'Multi-User Governance',    category: 'Operations', isNew: false },
    { id: 'ops_rbac',        name: 'Access Control',           category: 'Operations', isNew: false },
    { id: 'ops_custom_int',  name: 'Custom Integrations',      category: 'Operations', isNew: true },
    { id: 'sup_dedicated',   name: 'Dedicated Support',        category: 'Support',    isNew: true },
  ],
};

// ---------- Translation templates ----------

/**
 * Translation templates convert feature IDs into buyer-facing descriptions.
 * Each template has:
 *   name            — human-readable feature name
 *   description     — generic description (independent of operator context)
 *   justification   — buyer-facing value justification
 *
 * Placeholder content.  Real templates are downstream product work and
 * replace this object without changing the assembly or rendering code.
 */
export const TRANSLATION_TEMPLATES = {
  gov_chain: {
    name: 'Governance Chain',
    description: 'Every AI agent action is recorded in a tamper-evident chain, creating a complete audit trail of all governed operations.',
    justification: 'Provides verifiable proof that AI agents operated within policy, essential for compliance and incident investigation.',
  },
  gov_policy: {
    name: 'Policy Evaluation',
    description: 'Declarative policy rules evaluated against every tool call before execution, with ALLOW/DENY decisions recorded.',
    justification: 'Ensures AI agents cannot exceed their authorized scope, reducing risk of unauthorized data access or destructive operations.',
  },
  gov_shared: {
    name: 'Shared Governance Chain',
    description: 'A unified governance chain across all team members, providing organization-wide visibility into AI agent operations.',
    justification: 'Gives managers and compliance officers a single view of all governed AI activity across the team.',
  },
  gov_roles: {
    name: 'Role-Based Governance',
    description: 'Configurable governance roles with different permission levels for operators, reviewers, and administrators.',
    justification: 'Allows organizations to delegate governance responsibilities while maintaining oversight and control.',
  },
  gov_compliance: {
    name: 'Compliance Reporting',
    description: 'Automated compliance report generation with export to standard formats for regulatory submissions.',
    justification: 'Reduces the burden of demonstrating AI governance compliance to regulators and auditors.',
  },
  vis_dashboard: {
    name: 'Dashboard',
    description: 'Real-time web dashboard showing governance status, activity feed, health metrics, and system configuration.',
    justification: 'Provides immediate visibility into AI governance posture without searching through logs or chain data.',
  },
  vis_audit: {
    name: 'Audit Trail',
    description: 'Searchable audit interface with filtering by time, user, tool, decision, and event category.',
    justification: 'Enables rapid investigation of specific governance events and supports internal audit requirements.',
  },
  vis_team: {
    name: 'Team Activity View',
    description: 'Aggregated activity view showing governance decisions across all team members with per-user breakdown.',
    justification: 'Helps team leads identify patterns, ensure consistent governance, and spot unusual agent behavior.',
  },
  vis_reports: {
    name: 'Advanced Reporting',
    description: 'Scheduled and ad-hoc reports covering governance metrics, trends, and compliance status over configurable time periods.',
    justification: 'Supports executive reporting on AI governance maturity and operational risk management.',
  },
  vis_enterprise: {
    name: 'Enterprise Analytics',
    description: 'Enterprise-grade analytics with custom dashboards, data export APIs, and integration with existing BI tools.',
    justification: 'Embeds AI governance data into existing enterprise analytics workflows for comprehensive oversight.',
  },
  ops_single: {
    name: 'Single-Operator Mode',
    description: 'Full governance capabilities for an individual operator, with local chain storage and personal policy configuration.',
    justification: 'Provides complete AI governance even for individual practitioners and small-scale deployments.',
  },
  ops_multi_machine: {
    name: 'Multi-Machine Support',
    description: 'Run governed AI agents on multiple machines under a single license, with chain data from all machines.',
    justification: 'Supports developers who work across multiple environments (laptop, CI server, staging) without separate licenses.',
  },
  ops_multi_user: {
    name: 'Multi-User Governance',
    description: 'Multiple operators governed under a single organizational license with shared policy configuration.',
    justification: 'Enables teams to adopt AI governance with consistent policies and centralized management.',
  },
  ops_rbac: {
    name: 'Access Control',
    description: 'Role-based access control for governance operations, allowing different team members to have different capabilities.',
    justification: 'Ensures appropriate separation of duties in AI governance, with reviewers and administrators having distinct permissions.',
  },
  ops_custom_int: {
    name: 'Custom Integrations',
    description: 'API access for integrating Atested governance data with existing enterprise systems (SIEM, GRC, CI/CD).',
    justification: 'Enables AI governance to be part of existing security and compliance workflows rather than a standalone tool.',
  },
  sup_community: {
    name: 'Community Support',
    description: 'Access to community forums, documentation, and knowledge base for governance questions and configuration help.',
    justification: 'Self-service support resources for operators comfortable with independent problem-solving.',
  },
  sup_email: {
    name: 'Email Support',
    description: 'Direct email support for governance questions, configuration assistance, and issue resolution.',
    justification: 'Human support for when documentation isn\'t enough, with responses within one business day.',
  },
  sup_priority: {
    name: 'Priority Support',
    description: 'Priority email support with faster response times and escalation paths for urgent governance issues.',
    justification: 'Ensures governance issues that affect team productivity are resolved quickly.',
  },
  sup_dedicated: {
    name: 'Dedicated Support',
    description: 'Dedicated account representative with proactive support, custom onboarding, and regular governance reviews.',
    justification: 'White-glove support for organizations where AI governance is mission-critical.',
  },
};

/**
 * Get the translated description for a capability.
 * Returns the template object or a fallback with the capability name.
 */
export function getTemplate(capabilityId) {
  return TRANSLATION_TEMPLATES[capabilityId] || {
    name: capabilityId,
    description: 'Feature description not yet available.',
    justification: '',
  };
}

/**
 * Get all capabilities for a tier, grouped by category.
 * Returns: [{ category: string, capabilities: [{id, name, description, justification, isNew}] }]
 */
export function getGroupedCapabilities(tierId) {
  const caps = TIER_CAPABILITIES[tierId] || [];
  const groups = {};

  for (const cap of caps) {
    if (!groups[cap.category]) {
      groups[cap.category] = [];
    }
    const template = getTemplate(cap.id);
    groups[cap.category].push({
      ...cap,
      description: template.description,
      justification: template.justification,
    });
  }

  return CATEGORIES
    .filter(cat => groups[cat])
    .map(cat => ({ category: cat, capabilities: groups[cat] }));
}
