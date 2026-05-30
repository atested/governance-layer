import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { createProject, listProjects } from "../repositories/projects.ts";
import { readJsonBody } from "./request.ts";
import { sendJson } from "./health.ts";

export async function handleProjects(
  request: IncomingMessage,
  response: ServerResponse,
  db: DesignDatabase
) {
  if (request.method === "POST") {
    const body = await readJsonBody<{ title?: string }>(request);
    const project = createProject(db, { title: body.title ?? "Untitled Design Project" });
    sendJson(response, 201, project);
    return;
  }

  if (request.method === "GET") {
    sendJson(response, 200, listProjects(db));
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
