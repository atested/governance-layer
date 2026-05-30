import type { SQLInputValue } from "node:sqlite";
import type { DesignDatabase } from "../db.ts";
import { createDiscoveryItem } from "../repositories/discoveryItems.ts";
import { createLineageEvent } from "../repositories/lineageEvents.ts";
import { getProjectScopedRecord, updateProjectScopedRecord } from "../repositories/projectScopedCrud.ts";
import { getProposal, updateProposalStatus } from "../repositories/proposals.ts";
import { createPurposeItem } from "../repositories/purposeItems.ts";
import { createRelationship } from "../repositories/relationships.ts";
import { nowIso } from "../repositories/base.ts";

type ProposedChanges = Record<string, unknown>;

function asObject(value: unknown): ProposedChanges {
  return value && typeof value === "object" ? (value as ProposedChanges) : {};
}

function stringValue(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function assertPending(status: string) {
  if (status !== "pending") {
    throw new Error(`Only pending proposals can be resolved; current status is ${status}`);
  }
}

export function rejectProposal(db: DesignDatabase, projectId: string, proposalId: string) {
  const proposal = getProposal(db, projectId, proposalId);
  if (!proposal) throw new Error("Proposal not found");
  assertPending(proposal.status);
  return updateProposalStatus(db, { projectId, id: proposalId, status: "rejected" });
}

export function acceptProposal(db: DesignDatabase, projectId: string, proposalId: string) {
  const proposal = getProposal(db, projectId, proposalId);
  if (!proposal) throw new Error("Proposal not found");
  assertPending(proposal.status);

  const acceptedAt = nowIso();
  const proposed = asObject(proposal.proposedChanges);
  const createdObjects: unknown[] = [];
  const lineageEvents: unknown[] = [];

  db.exec("BEGIN;");
  try {
    if (proposal.proposalType === "create_discovery") {
      const item = createDiscoveryItem(db, {
        projectId,
        title: stringValue(proposed.title, "Untitled discovery item"),
        body: stringValue(proposed.body),
        discoveryType: stringValue(proposed.discoveryType, "observation"),
        state: stringValue(proposed.state, "noticed"),
        createdFromMessageIds: stringArray(proposed.createdFromMessageIds),
        tags: stringArray(proposed.tags)
      });
      createdObjects.push(item);
      lineageEvents.push(
        createLineageEvent(db, {
          projectId,
          subjectId: String(item.id),
          eventType: "created",
          afterValue: item,
          messageIds: proposal.sourceMessageIds,
          proposalId
        })
      );
    } else if (proposal.proposalType === "create_purpose") {
      const item = createPurposeItem(db, {
        projectId,
        title: stringValue(proposed.title, "Untitled purpose item"),
        body: stringValue(proposed.body),
        purposeType: stringValue(proposed.purposeType, "purpose_candidate"),
        state: stringValue(proposed.state, "purpose_candidate"),
        createdFromMessageIds: stringArray(proposed.createdFromMessageIds),
        tags: stringArray(proposed.tags)
      });
      createdObjects.push(item);
      lineageEvents.push(
        createLineageEvent(db, {
          projectId,
          subjectId: String(item.id),
          eventType: "created",
          afterValue: item,
          messageIds: proposal.sourceMessageIds,
          proposalId
        })
      );
    } else if (proposal.proposalType === "promote_to_purpose") {
      const sourceId = stringValue(proposed.sourceId);
      const source = getProjectScopedRecord(db, "discovery_items", projectId, sourceId);
      if (!source) throw new Error("Source discovery item not found");
      const item = createPurposeItem(db, {
        projectId,
        title: stringValue(proposed.title, String(source.title ?? "Promoted purpose item")),
        body: stringValue(proposed.body, String(source.body ?? "")),
        purposeType: stringValue(proposed.purposeType, "purpose_candidate"),
        state: stringValue(proposed.state, "purpose_candidate"),
        createdFromMessageIds: stringArray(proposed.createdFromMessageIds)
      });
      const updatedSource = updateProjectScopedRecord(db, "discovery_items", projectId, sourceId, {
        state: "superseded",
        updatedAt: acceptedAt
      });
      createdObjects.push(item, updatedSource);
      lineageEvents.push(
        createLineageEvent(db, {
          projectId,
          subjectId: sourceId,
          eventType: "promoted",
          beforeValue: source,
          afterValue: { source: updatedSource, createdPurposeItem: item },
          messageIds: proposal.sourceMessageIds,
          proposalId
        })
      );
    } else if (proposal.proposalType === "demote_to_discovery") {
      const sourceId = stringValue(proposed.sourceId);
      const source = getProjectScopedRecord(db, "purpose_items", projectId, sourceId);
      if (!source) throw new Error("Source purpose item not found");
      const item = createDiscoveryItem(db, {
        projectId,
        title: stringValue(proposed.title, String(source.title ?? "Demoted discovery item")),
        body: stringValue(proposed.body, String(source.body ?? "")),
        discoveryType: stringValue(proposed.discoveryType, "observation"),
        state: stringValue(proposed.state, "noticed"),
        createdFromMessageIds: stringArray(proposed.createdFromMessageIds)
      });
      const updatedSource = updateProjectScopedRecord(db, "purpose_items", projectId, sourceId, {
        state: "superseded",
        updatedAt: acceptedAt
      });
      createdObjects.push(item, updatedSource);
      lineageEvents.push(
        createLineageEvent(db, {
          projectId,
          subjectId: sourceId,
          eventType: "demoted",
          beforeValue: source,
          afterValue: { source: updatedSource, createdDiscoveryItem: item },
          messageIds: proposal.sourceMessageIds,
          proposalId
        })
      );
    } else if (proposal.proposalType === "connect_items") {
      const relationship = createRelationship(db, {
        projectId,
        fromId: stringValue(proposed.fromId),
        toId: stringValue(proposed.toId),
        type: stringValue(proposed.type, "related_to"),
        description: stringValue(proposed.description)
      });
      createdObjects.push(relationship);
      lineageEvents.push(
        createLineageEvent(db, {
          projectId,
          subjectId: stringValue(proposed.fromId, String(relationship.id)),
          eventType: "connected",
          afterValue: relationship,
          messageIds: proposal.sourceMessageIds,
          proposalId
        })
      );
    } else if (proposal.proposalType === "update_item") {
      const table = stringValue(proposed.table);
      const id = stringValue(proposed.id);
      const patch = asObject(proposed.patch);
      const before = getProjectScopedRecord(db, table, projectId, id);
      if (!before) throw new Error("Item to update not found");
      const after = updateProjectScopedRecord(db, table, projectId, id, {
        ...Object.fromEntries(Object.entries(patch).map(([key, value]) => [key, value as SQLInputValue])),
        updatedAt: acceptedAt
      });
      createdObjects.push(after);
      lineageEvents.push(
        createLineageEvent(db, {
          projectId,
          subjectId: id,
          eventType: "edited",
          beforeValue: before,
          afterValue: after,
          messageIds: proposal.sourceMessageIds,
          proposalId
        })
      );
    } else {
      throw new Error(`Unsupported proposal type: ${proposal.proposalType}`);
    }

    const resolvedProposal = updateProposalStatus(db, {
      projectId,
      id: proposalId,
      status: "accepted",
      resolvedAt: acceptedAt
    });
    db.exec("COMMIT;");
    return { proposal: resolvedProposal, createdObjects, lineageEvents };
  } catch (error) {
    db.exec("ROLLBACK;");
    throw error;
  }
}
