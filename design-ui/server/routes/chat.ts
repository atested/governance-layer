import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { createChatMessage, listChatMessages } from "../repositories/chatMessages.ts";
import { sendJson } from "./health.ts";
import { readJsonBody, requireProjectId } from "./request.ts";

export async function handleChat(
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

  if (request.method === "POST") {
    const body = await readJsonBody<{ role?: "operator" | "assistant" | "system"; content?: string }>(request);
    const message = createChatMessage(db, {
      projectId,
      role: body.role ?? "operator",
      content: body.content ?? ""
    });
    sendJson(response, 201, message);
    return;
  }

  if (request.method === "GET") {
    sendJson(response, 200, listChatMessages(db, projectId));
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
