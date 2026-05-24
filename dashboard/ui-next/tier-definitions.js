/**
 * Tier definitions and translation templates.
 *
 * Tier gates, pricing, capacity, communications slots, and alert activation
 * are sourced from tier-feature-registry.js. This module keeps the existing
 * exports used by questionnaire and licensing UI code, and owns only the
 * explanatory translation templates.
 */

import {
  PAYMENT_LINKS,
  CHARTER,
  CHARTER_ACTIVE,
  CAPACITY_RANGES,
  COMMERCIAL_TERMS,
  CATEGORIES,
  TIER_CAPABILITIES,
  FEATURE_FLAGS,
  MACHINE_CAPS,
  REPORT_RANGE_LIMITS,
  COMMUNICATIONS_SLOTS,
  ALERT_GROUPS,
  tierLabel,
  tierLevel,
} from './tier-feature-registry.js';

// tierLabel and tierLevel live in tier-feature-registry.js as the canonical
// source. They are re-exported here so existing importers (app.js,
// windows/activity.js, windows/alerts.js) continue to resolve without
// requiring a wider refactor. Removing either re-export breaks the module
// graph and renders the dashboard a blank page — see QS-025 report.
export {
  PAYMENT_LINKS,
  CHARTER,
  CHARTER_ACTIVE,
  CAPACITY_RANGES,
  COMMERCIAL_TERMS,
  CATEGORIES,
  TIER_CAPABILITIES,
  FEATURE_FLAGS,
  MACHINE_CAPS,
  REPORT_RANGE_LIMITS,
  COMMUNICATIONS_SLOTS,
  ALERT_GROUPS,
  tierLabel,
  tierLevel,
};

export const TRANSLATION_TEMPLATES = {
  gov_chain: {
    name: 'Governance Chain',
    description: 'Every AI application action is recorded in a tamper-evident chain, creating a complete audit trail of all governed operations.',
    justification: 'Provides verifiable proof that AI applications operated within policy, essential for compliance and incident investigation.',
  },
  gov_policy: {
    name: 'Policy Evaluation',
    description: 'Declarative policy rules evaluated against every governed action before execution, with ALLOW/DENY decisions recorded.',
    justification: 'Ensures AI applications cannot exceed their authorized scope, reducing risk of unauthorized data access or destructive operations.',
  },
  gov_shared: {
    name: 'Shared Governance Chain',
    description: 'A unified governance chain across all team members, providing organization-wide visibility into AI application operations.',
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
    description: 'Searchable audit interface with filtering by time, user, action, decision, and event category.',
    justification: 'Enables rapid investigation of specific governance events and supports internal audit requirements.',
  },
  vis_team: {
    name: 'Team Activity View',
    description: 'Aggregated activity view showing governance decisions across all team members with per-user breakdown.',
    justification: 'Helps team leads identify patterns, ensure consistent governance, and spot unusual AI application behavior.',
  },
  vis_reports: {
    name: 'Advanced Reporting',
    description: 'Scheduled and ad-hoc reports covering governance metrics, trends, and compliance status over configurable time periods.',
    justification: 'Supports executive reporting on AI governance maturity and operational risk management.',
  },
  vis_enterprise: {
    name: 'Institutional Analytics',
    description: 'Institution-scale analytics with custom dashboards, data export APIs, and integration with existing BI tools.',
    justification: 'Embeds AI governance data into existing institutional analytics workflows for comprehensive oversight.',
  },
  ops_single: {
    name: 'Single-Operator Mode',
    description: 'Full governance capabilities for an individual operator, with local chain storage and personal policy configuration.',
    justification: 'Provides complete AI governance even for individual practitioners and small-scale deployments.',
  },
  ops_multi_machine: {
    name: 'Multi-Machine Support',
    description: 'Run governed AI applications on multiple machines under a single license, with chain data from all machines.',
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
    description: 'API access for integrating Atested governance data with existing institutional systems (SIEM, GRC, CI/CD).',
    justification: 'Enables AI governance to be part of existing security and compliance workflows rather than a standalone console.',
  },
  sup_docs_feedback: {
    name: 'Documentation & Feedback Support',
    description: 'Support through documentation and the Atested feedback system for governance questions and configuration help.',
    justification: 'Self-service support through documentation plus the ability to submit feedback artifacts for assistance.',
  },
  sup_feedback: {
    name: 'Feedback System Support',
    description: 'Support through the Atested feedback system for governance questions, configuration assistance, and issue resolution.',
    justification: 'Direct support through the in-app feedback artifact system with responses tracked in the governance chain.',
  },
  sup_priority_feedback: {
    name: 'Priority Feedback Support',
    description: 'Priority support through the Atested feedback system with faster response times for urgent governance issues.',
    justification: 'Ensures governance issues that affect team productivity are resolved quickly through prioritized feedback handling.',
  },
  sup_dedicated_feedback: {
    name: 'Dedicated Feedback Support',
    description: 'Dedicated support through the Atested feedback system with a named contact, custom onboarding, and regular governance reviews.',
    justification: 'White-glove support for organizations where AI governance is mission-critical, with a named support contact.',
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
