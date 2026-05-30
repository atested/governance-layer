import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { replaceActiveContext } from "../repositories/activeContexts.ts";
import { buildDesignMap, contextForNode } from "../services/mapBuilder.ts";
import { sendJson } from "./health.ts";
import { readJsonBody, requireProjectId } from "./request.ts";

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
    sendJson(response, 200, buildDesignMap(db, projectId));
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/map/context") {
    readJsonBody<{ nodeId?: string }>(request)
      .then((body) => {
        if (!body.nodeId) {
          sendJson(response, 400, { error: "nodeId_required" });
          return;
        }
        const context = replaceActiveContext(db, {
          projectId,
          ...contextForNode(db, projectId, body.nodeId)
        });
        sendJson(response, 201, { activeContext: context, map: buildDesignMap(db, projectId) });
      })
      .catch((error) => {
        sendJson(response, 500, {
          error: "map_context_failed",
          message: error instanceof Error ? error.message : String(error)
        });
      });
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
