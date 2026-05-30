import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { createProposal, listProposals } from "../repositories/proposals.ts";
import { acceptProposal, rejectProposal } from "../services/proposalCommitter.ts";
import { withProposalPreview } from "../services/proposalPreview.ts";
import { sendJson } from "./health.ts";
import { readJsonBody, requireProjectId } from "./request.ts";

export async function handleProposals(
  request: IncomingMessage,
  response: ServerResponse,
  db: DesignDatabase,
  url: URL
) {
  const projectId = requireProjectId(url);
  if (!projectId) {
    sendJson(response, 400, { error: "projectId_required" });
    return;
  }

  const actionMatch = url.pathname.match(/^\/api\/proposals\/([^/]+)\/(accept|reject)$/);
  if (request.method === "POST" && actionMatch) {
    const [, proposalId, action] = actionMatch;
    const result =
      action === "accept"
        ? acceptProposal(db, projectId, proposalId)
        : { proposal: rejectProposal(db, projectId, proposalId) };
    sendJson(response, 200, result);
    return;
  }

  if (request.method === "POST") {
    const body = await readJsonBody<{
      proposalType?: string;
      proposedChanges?: unknown;
      rationale?: string;
      sourceMessageIds?: string[];
    }>(request);
    const proposal = createProposal(db, {
      projectId,
      proposalType: body.proposalType ?? "create_discovery",
      proposedChanges: body.proposedChanges ?? {},
      rationale: body.rationale,
      sourceMessageIds: body.sourceMessageIds
    });
    sendJson(response, 201, withProposalPreview(proposal));
    return;
  }

  if (request.method === "GET") {
    sendJson(response, 200, listProposals(db, projectId).map((proposal) => withProposalPreview(proposal)));
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
