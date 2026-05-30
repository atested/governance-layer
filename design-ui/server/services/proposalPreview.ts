import type { Proposal } from "../repositories/proposals.ts";

export type ProposalPreview = {
  proposalId: string;
  proposalType: string;
  creates: Array<{ table: string; title: string }>;
  changes: Array<{ table: string; id: string; fields: string[] }>;
  connections: Array<{ fromId: string; toId: string; type: string }>;
  lineageEvents: Array<{ eventType: string; subjectId: string }>;
};

type ProposedChanges = Record<string, unknown>;

function changes(proposal: Proposal): ProposedChanges {
  return proposal.proposedChanges && typeof proposal.proposedChanges === "object"
    ? (proposal.proposedChanges as ProposedChanges)
    : {};
}

function text(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

export function buildProposalPreview(proposal: Proposal): ProposalPreview {
  const proposed = changes(proposal);
  const preview: ProposalPreview = {
    proposalId: proposal.id,
    proposalType: proposal.proposalType,
    creates: [],
    changes: [],
    connections: [],
    lineageEvents: []
  };

  if (proposal.proposalType === "create_discovery") {
    preview.creates.push({
      table: "discovery_items",
      title: text(proposed.title, "Untitled discovery item")
    });
    preview.lineageEvents.push({ eventType: "created", subjectId: "new_discovery_item" });
  } else if (proposal.proposalType === "create_purpose") {
    preview.creates.push({
      table: "purpose_items",
      title: text(proposed.title, "Untitled purpose item")
    });
    preview.lineageEvents.push({ eventType: "created", subjectId: "new_purpose_item" });
  } else if (proposal.proposalType === "promote_to_purpose") {
    preview.creates.push({
      table: "purpose_items",
      title: text(proposed.title, "Promoted purpose item")
    });
    preview.changes.push({
      table: "discovery_items",
      id: text(proposed.sourceId, "source_discovery_item"),
      fields: ["state", "updatedAt"]
    });
    preview.lineageEvents.push({
      eventType: "promoted",
      subjectId: text(proposed.sourceId, "source_discovery_item")
    });
  } else if (proposal.proposalType === "demote_to_discovery") {
    preview.creates.push({
      table: "discovery_items",
      title: text(proposed.title, "Demoted discovery item")
    });
    preview.changes.push({
      table: "purpose_items",
      id: text(proposed.sourceId, "source_purpose_item"),
      fields: ["state", "updatedAt"]
    });
    preview.lineageEvents.push({
      eventType: "demoted",
      subjectId: text(proposed.sourceId, "source_purpose_item")
    });
  } else if (proposal.proposalType === "connect_items") {
    preview.creates.push({
      table: "relationships",
      title: text(proposed.description, "Relationship")
    });
    preview.connections.push({
      fromId: text(proposed.fromId, "from_item"),
      toId: text(proposed.toId, "to_item"),
      type: text(proposed.type, "related_to")
    });
    preview.lineageEvents.push({
      eventType: "connected",
      subjectId: text(proposed.fromId, "from_item")
    });
  } else if (proposal.proposalType === "update_item") {
    const patch = proposed.patch && typeof proposed.patch === "object" ? proposed.patch : {};
    preview.changes.push({
      table: text(proposed.table, "design_object"),
      id: text(proposed.id, "item"),
      fields: Object.keys(patch)
    });
    preview.lineageEvents.push({ eventType: "edited", subjectId: text(proposed.id, "item") });
  }

  return preview;
}

export function withProposalPreview(proposal: Proposal) {
  return {
    ...proposal,
    preview: buildProposalPreview(proposal)
  };
}
