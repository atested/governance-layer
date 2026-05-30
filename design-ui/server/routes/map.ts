import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { listActiveContexts } from "../repositories/activeContexts.ts";
import { listConcepts } from "../repositories/concepts.ts";
import { listRelationships } from "../repositories/relationships.ts";
import { sendJson } from "./health.ts";
import { requireProjectId } from "./request.ts";

export function handleMap(
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

  if (request.method === "GET") {
    sendJson(response, 200, {
      concepts: listConcepts(db, projectId),
      relationships: listRelationships(db, projectId),
      activeContexts: listActiveContexts(db, projectId)
    });
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
