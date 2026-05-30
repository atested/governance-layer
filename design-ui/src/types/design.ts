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
