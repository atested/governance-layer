import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { DesignUiApiClient, DesignUiApiError, type FetchLike } from "../mcp/client.ts";
import { requiredToolNames } from "../mcp/schemas.ts";
import { designUiMcpTools, executeDesignUiTool } from "../mcp/tools.ts";

type RequestRecord = {
  url: string;
  method: string;
  body?: unknown;
};

function jsonResponse(body: unknown, init: ResponseInit = {}) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
    ...init
  });
}

function createFetchStub(handler: (url: URL, init: RequestInit, record: RequestRecord) => unknown) {
  const requests: RequestRecord[] = [];
  const fetchImpl: FetchLike = async (input, init = {}) => {
    const url = new URL(String(input));
    const body = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    const record = { url: url.toString(), method: init.method ?? "GET", body };
    requests.push(record);
    const result = handler(url, init, record);
    return result instanceof Response ? result : jsonResponse(result);
  };
  return { fetchImpl, requests };
}

function client(fetchImpl: FetchLike) {
  return new DesignUiApiClient({ baseUrl: "http://127.0.0.1:4174/api", fetchImpl });
}

const origin = {
  clientName: "codex",
  clientSessionId: "session-1",
  model: "gpt-test",
  userLabel: "Greg",
  requestId: "origin-request"
};

test("MCP tool list exposes every required Design UI tool", () => {
  assert.deepEqual(
    designUiMcpTools.map((tool) => tool.name),
    requiredToolNames
  );
  for (const tool of designUiMcpTools) {
    assert.equal(typeof tool.description, "string");
    assert.equal(typeof tool.inputSchema, "object");
  }
});

test("read tools call the Design UI API and return structured state", async () => {
  const { fetchImpl, requests } = createFetchStub((url) => {
    if (url.pathname === "/api/projects") {
      return [{ id: "project-1", title: "Design Project", createdAt: "now", updatedAt: "now" }];
    }
    if (url.pathname === "/api/items" && url.searchParams.get("kind") === "discovery") {
      return [
        { id: "discovery-1", title: "Visible question", discoveryType: "question", state: "open" },
        { id: "discovery-2", title: "Filtered observation", discoveryType: "observation", state: "closed" }
      ];
    }
    if (url.pathname === "/api/items" && url.searchParams.get("kind") === "purpose") {
      return [
        { id: "purpose-1", title: "Boundary", purposeType: "boundary", state: "open" },
        { id: "purpose-2", title: "Constraint", purposeType: "constraint", state: "open" }
      ];
    }
    if (url.pathname === "/api/map") {
      return {
        activeContext: {
          id: "context-1",
          label: "Focused Area",
          discoveryItemIds: ["discovery-1"],
          purposeItemIds: ["purpose-1"],
          conceptIds: ["concept-1"],
          relationshipIds: ["edge-1"]
        },
        nodes: [
          {
            id: "discovery-1",
            label: "Visible question",
            nodeType: "open_area",
            maturity: "open",
            connected: false,
            sourceKind: "discovery",
            sourceId: "discovery-1"
          },
          {
            id: "purpose-1",
            label: "Boundary",
            nodeType: "purpose_region",
            maturity: "stable",
            connected: true,
            sourceKind: "purpose",
            sourceId: "purpose-1"
          }
        ],
        edges: [{ id: "edge-1", fromId: "discovery-1", toId: "purpose-1", type: "supports", description: "" }]
      };
    }
    if (url.pathname === "/api/spec") {
      return {
        markdown: "# Design Specification",
        json: { sections: [] },
        spec: { sourcePurposeItemIds: ["purpose-1"], sourceLineageEventIds: ["lineage-1"] },
        validation: { passed: false, checks: { boundariesPresent: { status: "warning", message: "", relatedItemIds: [] } } }
      };
    }
    throw new Error(`Unexpected API path: ${url.pathname}`);
  });

  const api = client(fetchImpl);
  const activeProject = await executeDesignUiTool(api, "get_active_project", { requestId: "read-1" });
  const context = await executeDesignUiTool(api, "get_active_context", { projectId: "project-1" });
  const discovery = await executeDesignUiTool(api, "list_discovery_items", {
    projectId: "project-1",
    contextOnly: true,
    discoveryType: "question"
  });
  const purpose = await executeDesignUiTool(api, "list_purpose_items", {
    projectId: "project-1",
    contextOnly: true,
    purposeType: "boundary"
  });
  const relationships = await executeDesignUiTool(api, "list_relationships", {
    projectId: "project-1",
    relationshipType: "supports"
  });
  const map = await executeDesignUiTool(api, "list_map_nodes", { projectId: "project-1", connected: false });
  const spec = await executeDesignUiTool(api, "get_spec_preview", { projectId: "project-1", format: "both" });
  const validation = await executeDesignUiTool(api, "get_validation_results", { projectId: "project-1" });

  assert.equal((activeProject as { project: { id: string } }).project.id, "project-1");
  assert.equal((context as { activeContext: { id: string } }).activeContext.id, "context-1");
  assert.deepEqual((discovery as { items: Array<{ id: string }> }).items.map((item) => item.id), ["discovery-1"]);
  assert.deepEqual((purpose as { items: Array<{ id: string }> }).items.map((item) => item.id), ["purpose-1"]);
  assert.equal((relationships as { relationships: unknown[] }).relationships.length, 1);
  assert.deepEqual((map as { nodes: Array<{ id: string }> }).nodes.map((node) => node.id), ["discovery-1"]);
  assert.equal((spec as { markdown: string }).markdown, "# Design Specification");
  assert.equal((validation as { passed: boolean }).passed, false);
  assert.equal(requests.every((request) => request.method === "GET"), true);
});

test("proposal tools create pending proposals only and preserve MCP attribution", async () => {
  const { fetchImpl, requests } = createFetchStub((url, _init, record) => {
    assert.equal(url.pathname, "/api/proposals");
    assert.equal(record.method, "POST");
    return {
      id: "proposal-1",
      status: "pending",
      proposalType: (record.body as { proposalType: string }).proposalType,
      proposedChanges: (record.body as { proposedChanges: Record<string, unknown> }).proposedChanges,
      preview: { creates: [], changes: [], lineageEvents: [] }
    };
  });

  const result = await executeDesignUiTool(client(fetchImpl), "create_design_proposal", {
    projectId: "project-1",
    targetKind: "discovery",
    title: "What should stabilize?",
    body: "Question body",
    discoveryType: "question",
    rationale: "Capture design uncertainty.",
    sourceMessageIds: ["message-1"],
    origin,
    requestId: "proposal-request"
  });

  const proposal = (result as { proposal: { status: string; proposedChanges: Record<string, unknown> } }).proposal;
  const metadata = proposal.proposedChanges.metadata as { mcp: Record<string, unknown> };
  assert.equal(proposal.status, "pending");
  assert.equal(metadata.mcp.createdBy, "mcp");
  assert.equal(metadata.mcp.clientName, "codex");
  assert.equal(metadata.mcp.toolName, "create_design_proposal");
  assert.equal(metadata.mcp.rationale, "Capture design uncertainty.");
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "http://127.0.0.1:4174/api/proposals?projectId=project-1");
  assert.equal(requests.some((request) => request.url.includes("/accept") || request.url.includes("/reject")), false);
});

test("all proposal tools use only proposal creation endpoints", async () => {
  const { fetchImpl, requests } = createFetchStub((_url, _init, record) => ({
    id: `${(record.body as { proposalType: string }).proposalType}-proposal`,
    status: "pending",
    proposedChanges: (record.body as { proposedChanges: Record<string, unknown> }).proposedChanges
  }));
  const api = client(fetchImpl);

  await executeDesignUiTool(api, "create_relationship_proposal", {
    projectId: "project-1",
    fromId: "discovery-1",
    toId: "purpose-1",
    relationshipType: "supports",
    rationale: "They belong together.",
    origin
  });
  await executeDesignUiTool(api, "create_promotion_proposal", {
    projectId: "project-1",
    sourceDiscoveryItemId: "discovery-1",
    rationale: "It has stabilized.",
    origin
  });
  await executeDesignUiTool(api, "create_demotion_proposal", {
    projectId: "project-1",
    sourcePurposeItemId: "purpose-1",
    rationale: "It needs more discovery.",
    origin
  });
  await executeDesignUiTool(api, "create_update_proposal", {
    projectId: "project-1",
    targetTable: "purpose_items",
    targetId: "purpose-1",
    patch: { title: "Updated title" },
    rationale: "Clarify language.",
    origin
  });

  assert.equal(requests.length, 4);
  assert.equal(requests.every((request) => request.method === "POST"), true);
  assert.equal(requests.every((request) => new URL(request.url).pathname === "/api/proposals"), true);
  assert.equal(
    requests.some((request) =>
      ["/api/items", "/api/map", "/api/spec"].some((forbiddenPath) => new URL(request.url).pathname.startsWith(forbiddenPath))
    ),
    false
  );
  assert.equal(requests.some((request) => request.url.includes("/accept") || request.url.includes("/reject")), false);
});

test("update proposals reject committed-state ownership fields", async () => {
  const { fetchImpl, requests } = createFetchStub(() => {
    throw new Error("proposal endpoint should not be called for invalid patches");
  });

  await assert.rejects(
    () =>
      executeDesignUiTool(client(fetchImpl), "create_update_proposal", {
        projectId: "project-1",
        targetTable: "purpose_items",
        targetId: "purpose-1",
        patch: { projectId: "other-project" },
        rationale: "Invalid ownership change.",
        origin
      }),
    /patch contains forbidden committed-state fields: projectId/
  );
  assert.equal(requests.length, 0);
});

test("API unavailable errors clearly tell the operator to start Design UI", async () => {
  const fetchImpl: FetchLike = async () => {
    throw new Error("ECONNREFUSED");
  };

  await assert.rejects(
    () => executeDesignUiTool(client(fetchImpl), "get_active_project", {}),
    (error) => {
      assert.equal(error instanceof DesignUiApiError, true);
      assert.match((error as Error).message, /Design UI API is unavailable/);
      assert.match((error as Error).message, /Start Design UI before using MCP tools/);
      return true;
    }
  );
});

test("MCP adapter does not import repository or SQLite implementation modules", () => {
  const files = ["client.ts", "server.ts", "tools.ts", "schemas.ts"];
  for (const file of files) {
    const source = readFileSync(new URL(`../mcp/${file}`, import.meta.url), "utf8");
    assert.doesNotMatch(source, /server\/repositories|server\/db|sqlite/i);
  }
});
