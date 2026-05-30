import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { createDiscoveryItem, listDiscoveryItems } from "../repositories/discoveryItems.ts";
import { updateProjectScopedRecord } from "../repositories/projectScopedCrud.ts";
import { createPurposeItem, listPurposeItems } from "../repositories/purposeItems.ts";
import { nowIso } from "../repositories/base.ts";
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
  const table = kind === "purpose" ? "purpose_items" : "discovery_items";

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

  if (request.method === "PATCH") {
    const id = url.searchParams.get("id");
    if (!id) {
      sendJson(response, 400, { error: "id_required" });
      return;
    }
    const body = await readJsonBody<{ title?: string; body?: string; discoveryType?: string; purposeType?: string }>(
      request
    );
    const patch: Record<string, string> = { updatedAt: nowIso() };
    if (body.title !== undefined) patch.title = body.title;
    if (body.body !== undefined) patch.body = body.body;
    if (body.discoveryType !== undefined && kind !== "purpose") patch.discoveryType = body.discoveryType;
    if (body.purposeType !== undefined && kind === "purpose") patch.purposeType = body.purposeType;
    const item = updateProjectScopedRecord(db, table, projectId, id, patch);
    if (!item) {
      sendJson(response, 404, { error: "item_not_found" });
      return;
    }
    sendJson(response, 200, item);
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
