import type { IncomingMessage, ServerResponse } from "node:http";

export function sendJson(response: ServerResponse, statusCode: number, body: unknown) {
  response.writeHead(statusCode, { "content-type": "application/json" });
  response.end(JSON.stringify(body));
}

export function handleHealth(_request: IncomingMessage, response: ServerResponse) {
  sendJson(response, 200, {
    ok: true,
    service: "design-ui-api",
    timestamp: new Date().toISOString()
  });
}
