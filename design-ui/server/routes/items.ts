import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { createDiscoveryItem, listDiscoveryItems } from "../repositories/discoveryItems.ts";
import { createPurposeItem, listPurposeItems } from "../repositories/purposeItems.ts";
import { sendJson } from "./health.ts";
import { readJsonBody, requireProjectId } from "./request.ts";

export async function handleItems(
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

  const kind = url.searchParams.get("kind") ?? "discovery";

  if (request.method === "POST") {
    const body = await readJsonBody<{
      title?: string;
      body?: string;
      discoveryType?: string;
      purposeType?: string;
    }>(request);
    const item =
      kind === "purpose"
        ? createPurposeItem(db, {
            projectId,
            title: body.title ?? "Untitled purpose item",
            body: body.body,
            purposeType: body.purposeType ?? "purpose_candidate"
          })
        : createDiscoveryItem(db, {
            projectId,
            title: body.title ?? "Untitled discovery item",
            body: body.body,
            discoveryType: body.discoveryType ?? "observation"
          });
    sendJson(response, 201, item);
    return;
  }

  if (request.method === "GET") {
    sendJson(
      response,
      200,
      kind === "purpose" ? listPurposeItems(db, projectId) : listDiscoveryItems(db, projectId)
    );
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
