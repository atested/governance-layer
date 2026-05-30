export type DesignItemState =
  | "raw"
  | "noticed"
  | "clustered"
  | "purpose_candidate"
  | "stabilized"
  | "spec_ready"
  | "deferred"
  | "superseded";

export type ProposalStatus = "pending" | "accepted" | "rejected" | "modified";

export type DesignProject = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  activeContextId?: string | null;
};

export type DiscoveryItem = {
  id: string;
  projectId: string;
  title: string;
  body: string;
  discoveryType: string;
  state: DesignItemState;
  createdAt: string;
  updatedAt: string;
};

export type PurposeItem = {
  id: string;
  projectId: string;
  title: string;
  body: string;
  purposeType: string;
  state: DesignItemState;
  createdAt: string;
  updatedAt: string;
};

export type Relationship = {
  id: string;
  projectId: string;
  fromId: string;
  toId: string;
  type: string;
  description: string;
  createdAt: string;
};

export type ActiveContext = {
  id: string;
  projectId: string;
  label: string;
  discoveryItemIds: string[];
  purposeItemIds: string[];
  conceptIds: string[];
  relationshipIds: string[];
  createdAt: string;
  updatedAt: string;
};

export type LineageEvent = {
  id: string;
  projectId: string;
  subjectId: string;
  eventType:
    | "created"
    | "edited"
    | "promoted"
    | "demoted"
    | "merged"
    | "split"
    | "connected"
    | "challenged"
    | "superseded"
    | "exported";
  beforeValue: unknown;
  afterValue: unknown;
  messageIds: string[];
  proposalId: string | null;
  createdAt: string;
};

export type MapNodeType =
  | "concept"
  | "discovery_cluster"
  | "purpose_region"
  | "tension"
  | "open_area"
  | "disconnected_idea";

export type MapNode = {
  id: string;
  label: string;
  nodeType: MapNodeType;
  maturity: DesignItemState | string;
  connected: boolean;
  sourceKind: "concept" | "discovery" | "purpose";
  sourceId: string;
};

export type MapEdge = {
  id: string;
  fromId: string;
  toId: string;
  type: string;
  description: string;
};

export type DesignMap = {
  nodes: MapNode[];
  edges: MapEdge[];
  activeContexts: ActiveContext[];
  activeContext: ActiveContext | null;
};

export type SpecSectionTitle =
  | "Purpose"
  | "Core concept summary"
  | "Relevant discovered structure"
  | "Principles"
  | "Operational intent"
  | "Expectations"
  | "Boundaries"
  | "Constraints"
  | "Key relationships"
  | "Tensions"
  | "Residual judgments"
  | "Positive exemplars"
  | "Negative exemplars"
  | "Distinguishing properties"
  | "Supporting lineage references"
  | "Notes for Specification";

export type DesignSpecification = {
  projectId: string;
  title: string;
  sections: Record<SpecSectionTitle, string[]>;
  sourcePurposeItemIds: string[];
  sourceLineageEventIds: string[];
  relationshipReferences: Array<{ id: string; fromId: string; toId: string; type: string; description: string }>;
  discoveryReferences: Array<{ id: string; title: string; discoveryType: string; state: string }>;
};

export type ValidationCheck = {
  status: "pass" | "warning" | "fail";
  message: string;
  relatedItemIds: string[];
};

export type SpecValidationResult = {
  passed: boolean;
  checks: {
    purposeClarity: ValidationCheck;
    expectationClarity: ValidationCheck;
    operationalIntentPreserved: ValidationCheck;
    confusionRiskAddressed: ValidationCheck;
    examplesAdequate: ValidationCheck;
    boundariesPresent: ValidationCheck;
    residualJudgmentsPresent: ValidationCheck;
    downstreamRediscoveryRisk: ValidationCheck;
  };
};

export type SpecExport = {
  id: string;
  projectId: string;
  format: "markdown" | "json";
  content: string;
  sourcePurposeItemIds: string[];
  sourceLineageEventIds: string[];
  createdAt: string;
};

export type SpecBuilderResponse = {
  spec: DesignSpecification;
  markdown: string;
  json: string;
  validation: SpecValidationResult;
  exports: SpecExport[];
};

export type ChatMessage = {
  id: string;
  projectId: string;
  role: "operator" | "assistant" | "system";
  content: string;
  createdAt: string;
  sourceRefs: string[];
};

export type ProposalPreview = {
  proposalId: string;
  proposalType: string;
  creates: Array<{ table: string; title: string }>;
  changes: Array<{ table: string; id: string; fields: string[] }>;
  connections: Array<{ fromId: string; toId: string; type: string }>;
  lineageEvents: Array<{ eventType: string; subjectId: string }>;
};

export type DesignProposal = {
  id: string;
  projectId: string;
  proposalType:
    | "create_discovery"
    | "create_purpose"
    | "promote_to_purpose"
    | "demote_to_discovery"
    | "merge_items"
    | "split_item"
    | "connect_items"
    | "update_item"
    | "mark_spec_ready";
  rationale: string;
  proposedChanges: unknown;
  sourceMessageIds: string[];
  status: ProposalStatus;
  createdAt: string;
  resolvedAt?: string | null;
  preview?: ProposalPreview;
};
