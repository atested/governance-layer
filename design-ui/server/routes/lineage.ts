import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { listLineagePlayback } from "../repositories/lineageEvents.ts";
import { sendJson } from "./health.ts";
import { requireProjectId } from "./request.ts";

export function handleLineage(
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
      events: listLineagePlayback(db, projectId, url.searchParams.get("subjectId") ?? undefined)
    });
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
