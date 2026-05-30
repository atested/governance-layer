import type { IncomingMessage, ServerResponse } from "node:http";
import type { DesignDatabase } from "../db.ts";
import { listSpecExports } from "../repositories/specExports.ts";
import {
  buildDesignSpecification,
  persistSpecExport,
  renderJsonSpec,
  renderMarkdownSpec
} from "../services/specBuilder.ts";
import { validateDesignSpecification } from "../services/specValidator.ts";
import { sendJson } from "./health.ts";
import { readJsonBody, requireProjectId } from "./request.ts";

export function handleSpec(
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
    const spec = buildDesignSpecification(db, projectId);
    sendJson(response, 200, {
      spec,
      markdown: renderMarkdownSpec(spec),
      json: renderJsonSpec(spec),
      validation: validateDesignSpecification(db, projectId),
      exports: listSpecExports(db, projectId)
    });
    return;
  }

  if (request.method === "POST" && url.pathname === "/api/spec/export") {
    readJsonBody<{ format?: "markdown" | "json" }>(request)
      .then((body) => {
        const format = body.format === "json" ? "json" : "markdown";
        sendJson(response, 201, { export: persistSpecExport(db, projectId, format) });
      })
      .catch((error) => {
        sendJson(response, 500, {
          error: "spec_export_failed",
          message: error instanceof Error ? error.message : String(error)
        });
      });
    return;
  }

  sendJson(response, 405, { error: "method_not_allowed" });
}
