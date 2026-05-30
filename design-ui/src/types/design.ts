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

export type ChatMessage = {
  id: string;
  projectId: string;
  role: "operator" | "assistant" | "system";
  content: string;
  createdAt: string;
  sourceRefs: string[];
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
};
