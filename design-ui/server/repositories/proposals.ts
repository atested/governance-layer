import type { DesignDatabase } from "../db.ts";
import { encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createProposal(
  db: DesignDatabase,
  input: {
    projectId: string;
    proposalType: string;
    proposedChanges: unknown;
    rationale?: string;
    sourceMessageIds?: string[];
    status?: "pending" | "accepted" | "rejected" | "modified";
    id?: string;
  }
) {
  return insertRecord(db, "proposals", {
    id: input.id ?? newId("proposal"),
    projectId: input.projectId,
    proposalType: input.proposalType,
    rationale: input.rationale ?? "",
    proposedChanges: JSON.stringify(input.proposedChanges ?? {}),
    sourceMessageIds: encodeJson(input.sourceMessageIds ?? []),
    status: input.status ?? "pending",
    createdAt: nowIso(),
    resolvedAt: null
  });
}

export function listProposals(db: DesignDatabase, projectId: string) {
  return listByProject(db, "proposals", projectId);
}
