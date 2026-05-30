import type { DesignDatabase } from "../db.ts";
import { decodeJson, encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export type ProposalStatus = "pending" | "accepted" | "rejected" | "modified";

export type ProposalRow = {
  id: string;
  projectId: string;
  proposalType: string;
  rationale: string;
  proposedChanges: string;
  sourceMessageIds: string;
  status: ProposalStatus;
  createdAt: string;
  resolvedAt: string | null;
};

export type Proposal = Omit<ProposalRow, "proposedChanges" | "sourceMessageIds"> & {
  proposedChanges: unknown;
  sourceMessageIds: string[];
};

export function normalizeProposal(row: unknown): Proposal | undefined {
  if (!row || typeof row !== "object") return undefined;
  const proposal = row as ProposalRow;
  return {
    ...proposal,
    proposedChanges: decodeJson(proposal.proposedChanges, {}),
    sourceMessageIds: decodeJson(proposal.sourceMessageIds, [])
  };
}

export function createProposal(
  db: DesignDatabase,
  input: {
    projectId: string;
    proposalType: string;
    proposedChanges: unknown;
    rationale?: string;
    sourceMessageIds?: string[];
    status?: ProposalStatus;
    id?: string;
  }
) {
  const row = insertRecord(db, "proposals", {
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
  const proposal = normalizeProposal(row);
  if (!proposal) throw new Error("Failed to normalize created proposal");
  return proposal;
}

export function listProposals(db: DesignDatabase, projectId: string) {
  return listByProject(db, "proposals", projectId)
    .map(normalizeProposal)
    .filter((proposal): proposal is Proposal => Boolean(proposal));
}

export function getProposal(db: DesignDatabase, projectId: string, id: string) {
  return normalizeProposal(
    db.prepare("SELECT * FROM proposals WHERE projectId = ? AND id = ?").get(projectId, id)
  );
}

export function updateProposalStatus(
  db: DesignDatabase,
  input: {
    projectId: string;
    id: string;
    status: ProposalStatus;
    resolvedAt?: string;
  }
) {
  db.prepare(
    "UPDATE proposals SET status = ?, resolvedAt = ? WHERE projectId = ? AND id = ?"
  ).run(input.status, input.resolvedAt ?? nowIso(), input.projectId, input.id);
  const proposal = getProposal(db, input.projectId, input.id);
  if (!proposal) throw new Error("Proposal not found after status update");
  return proposal;
}
