import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { initializeDatabase } from "./db.ts";
import { handleChat } from "./routes/chat.ts";
import { handleHealth, sendJson } from "./routes/health.ts";
import { handleItems } from "./routes/items.ts";
import { handleLineage } from "./routes/lineage.ts";
import { handleMap } from "./routes/map.ts";
import { handleProjects } from "./routes/projects.ts";
import { handleProposals } from "./routes/proposals.ts";
import { handleSpec } from "./routes/spec.ts";

export function createApiServer(options: { dbPath?: string } = {}) {
  const db = initializeDatabase(options.dbPath);

  return createServer(async (request, response) => {
    const host = request.headers.host ?? "127.0.0.1";
    const url = new URL(request.url ?? "/", `http://${host}`);

    try {
      if (url.pathname === "/api/health") {
        handleHealth(request, response);
        return;
      }

      if (url.pathname === "/api/projects") {
        await handleProjects(request, response, db);
        return;
      }

      if (url.pathname === "/api/chat" || url.pathname === "/api/chat/send") {
        await handleChat(request, response, db, url);
        return;
      }

      if (url.pathname === "/api/proposals" || url.pathname.startsWith("/api/proposals/")) {
        await handleProposals(request, response, db, url);
        return;
      }

      if (url.pathname === "/api/items") {
        await handleItems(request, response, db, url);
        return;
      }

      if (url.pathname === "/api/lineage") {
        handleLineage(request, response, db, url);
        return;
      }

      if (url.pathname === "/api/map" || url.pathname === "/api/map/context") {
        handleMap(request, response, db, url);
        return;
      }

      if (url.pathname === "/api/spec") {
        handleSpec(request, response, db, url);
        return;
      }

      sendJson(response, 404, { error: "not_found" });
    } catch (error) {
      sendJson(response, 500, {
        error: "internal_server_error",
        message: error instanceof Error ? error.message : String(error)
      });
    }
  });
}

const isMain = process.argv[1] === fileURLToPath(import.meta.url);

if (isMain) {
  const port = Number(process.env.DESIGN_UI_API_PORT ?? "4174");
  createApiServer().listen(port, "127.0.0.1", () => {
    console.log(`Design UI API listening on http://127.0.0.1:${port}`);
  });
}
