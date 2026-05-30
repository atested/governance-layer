import { randomUUID } from "node:crypto";
import type { DesignUiApiClient } from "./client.ts";
import {
  forbiddenPatchFields,
  requiredToolNames,
  toolInputSchemas,
  type DesignUiMcpToolName,
  type McpOrigin,
  type ToolInput
} from "./schemas.ts";
import { params } from "./client.ts";

type ToolDefinition = {
  name: DesignUiMcpToolName;
  description: string;
  inputSchema: unknown;
};

type Project = {
  id: string;
  title: string;
  activeContextId?: string | null;
  createdAt: string;
  updatedAt: string;
};

type DesignMap = {
  nodes: Array<{
    id: string;
    label: string;
    nodeType: string;
    maturity: string;
    connected: boolean;
    sourceKind: "concept" | "discovery" | "purpose";
    sourceId: string;
  }>;
  edges: Array<{ id: string; fromId: string; toId: string; type: string; description: string }>;
  activeContext: {
    id: string;
    label: string;
    discoveryItemIds: string[];
    purposeItemIds: string[];
    conceptIds: string[];
    relationshipIds: string[];
  } | null;
};

const descriptions: Record<DesignUiMcpToolName, string> = {
  get_active_project: "Read the current Design UI project selected by v1 project behavior.",
  get_active_context: "Read the active Design Map context for a project.",
  list_discovery_items: "Read committed Discovery items, optionally filtered by context/type/state.",
  list_purpose_items: "Read committed Purpose items, optionally filtered by context/type/state.",
  list_relationships: "Read committed relationship edges from the Design Map projection.",
  list_map_nodes: "Read Design Map nodes and edges with optional filters.",
  get_spec_preview: "Read the current Design Specification preview from committed state.",
  get_validation_results: "Read advisory validation results for Design Specification handoff quality.",
  create_design_proposal: "Create a pending Discovery or Purpose proposal; does not commit state.",
  create_relationship_proposal: "Create a pending relationship proposal; does not commit state.",
  create_promotion_proposal: "Create a pending Discovery-to-Purpose promotion proposal.",
  create_demotion_proposal: "Create a pending Purpose-to-Discovery demotion proposal.",
  create_update_proposal: "Create a pending update proposal for a committed design object."
};

export const designUiMcpTools: ToolDefinition[] = requiredToolNames.map((name) => ({
  name,
  description: descriptions[name],
  inputSchema: toolInputSchemas[name]
}));

export async function executeDesignUiTool(
  client: DesignUiApiClient,
  name: string,
  input: ToolInput = {}
): Promise<Record<string, unknown>> {
  if (!isToolName(name)) {
    throw new Error(`Unknown Design UI MCP tool: ${name}`);
  }

  if (name === "get_active_project") return getActiveProject(client, input);
  if (name === "get_active_context") return getActiveContext(client, input);
  if (name === "list_discovery_items") return listDiscoveryItems(client, input);
  if (name === "list_purpose_items") return listPurposeItems(client, input);
  if (name === "list_relationships") return listRelationships(client, input);
  if (name === "list_map_nodes") return listMapNodes(client, input);
  if (name === "get_spec_preview") return getSpecPreview(client, input);
  if (name === "get_validation_results") return getValidationResults(client, input);
  if (name === "create_design_proposal") return createDesignProposal(client, input, name);
  if (name === "create_relationship_proposal") return createRelationshipProposal(client, input, name);
  if (name === "create_promotion_proposal") return createPromotionProposal(client, input, name);
  if (name === "create_demotion_proposal") return createDemotionProposal(client, input, name);
  return createUpdateProposal(client, input, name);
}

function isToolName(value: string): value is DesignUiMcpToolName {
  return (requiredToolNames as readonly string[]).includes(value);
}

function requestId(input: ToolInput) {
  return stringValue(input.requestId, randomUUID());
}

function stringValue(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function booleanValue(value: unknown) {
  return typeof value === "boolean" ? value : undefined;
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function requireString(input: ToolInput, field: string) {
  const value = stringValue(input[field]);
  if (!value) throw new Error(`${field} is required`);
  return value;
}

function origin(input: ToolInput): McpOrigin {
  const value = input.origin;
  if (!value || typeof value !== "object") throw new Error("origin is required");
  const candidate = value as Record<string, unknown>;
  const clientName = stringValue(candidate.clientName);
  if (!clientName) throw new Error("origin.clientName is required");
  return {
    clientName,
    clientSessionId: stringValue(candidate.clientSessionId) || undefined,
    model: stringValue(candidate.model) || undefined,
    userLabel: stringValue(candidate.userLabel) || undefined,
    requestId: stringValue(candidate.requestId) || stringValue(input.requestId) || undefined
  };
}

function withAttribution(
  proposedChanges: Record<string, unknown>,
  input: ToolInput,
  toolName: DesignUiMcpToolName
) {
  const toolOrigin = origin(input);
  return {
    ...proposedChanges,
    metadata: {
      ...(typeof proposedChanges.metadata === "object" && proposedChanges.metadata
        ? (proposedChanges.metadata as Record<string, unknown>)
        : {}),
      mcp: {
        createdBy: "mcp",
        createdVia: "mcp",
        clientName: toolOrigin.clientName,
        clientSessionId: toolOrigin.clientSessionId,
        model: toolOrigin.model,
        userLabel: toolOrigin.userLabel,
        requestId: toolOrigin.requestId,
        toolName,
        rationale: stringValue(input.rationale),
        createdAt: new Date().toISOString()
      }
    }
  };
}

async function getActiveProject(client: DesignUiApiClient, input: ToolInput) {
  const projects = await client.get<Project[]>("/projects");
  return {
    requestId: requestId(input),
    project: projects[0] ?? null
  };
}

async function getMap(client: DesignUiApiClient, projectId: string) {
  return client.get<DesignMap>(`/map?${params(projectId)}`);
}

async function getActiveContext(client: DesignUiApiClient, input: ToolInput) {
  const projectId = requireString(input, "projectId");
  const map = await getMap(client, projectId);
  return {
    requestId: requestId(input),
    activeContext: map.activeContext
  };
}

async function listDiscoveryItems(client: DesignUiApiClient, input: ToolInput) {
  const projectId = requireString(input, "projectId");
  let items = await client.get<Array<Record<string, unknown>>>(`/items?${params(projectId)}&kind=discovery`);
  if (input.contextOnly === true) {
    const map = await getMap(client, projectId);
    const ids = new Set(map.activeContext?.discoveryItemIds ?? []);
    items = items.filter((item) => ids.has(String(item.id)));
  }
  const state = stringValue(input.state);
  const discoveryType = stringValue(input.discoveryType);
  if (state) items = items.filter((item) => item.state === state);
  if (discoveryType) items = items.filter((item) => item.discoveryType === discoveryType);
  return { requestId: requestId(input), items };
}

async function listPurposeItems(client: DesignUiApiClient, input: ToolInput) {
  const projectId = requireString(input, "projectId");
  let items = await client.get<Array<Record<string, unknown>>>(`/items?${params(projectId)}&kind=purpose`);
  if (input.contextOnly === true) {
    const map = await getMap(client, projectId);
    const ids = new Set(map.activeContext?.purposeItemIds ?? []);
    items = items.filter((item) => ids.has(String(item.id)));
  }
  const state = stringValue(input.state);
  const purposeType = stringValue(input.purposeType);
  if (state) items = items.filter((item) => item.state === state);
  if (purposeType) items = items.filter((item) => item.purposeType === purposeType);
  return { requestId: requestId(input), items };
}

async function listRelationships(client: DesignUiApiClient, input: ToolInput) {
  const projectId = requireString(input, "projectId");
  const map = await getMap(client, projectId);
  let relationships = map.edges;
  const itemId = stringValue(input.itemId);
  const relationshipType = stringValue(input.relationshipType);
  if (itemId) relationships = relationships.filter((edge) => edge.fromId === itemId || edge.toId === itemId);
  if (relationshipType) relationships = relationships.filter((edge) => edge.type === relationshipType);
  return { requestId: requestId(input), relationships };
}

async function listMapNodes(client: DesignUiApiClient, input: ToolInput) {
  const projectId = requireString(input, "projectId");
  const map = await getMap(client, projectId);
  let nodes = map.nodes;
  const nodeType = stringValue(input.nodeType);
  const maturity = stringValue(input.maturity);
  const connected = booleanValue(input.connected);
  if (nodeType) nodes = nodes.filter((node) => node.nodeType === nodeType);
  if (maturity) nodes = nodes.filter((node) => node.maturity === maturity);
  if (connected !== undefined) nodes = nodes.filter((node) => node.connected === connected);
  const nodeIds = new Set(nodes.map((node) => node.id));
  const edges = map.edges.filter((edge) => nodeIds.has(edge.fromId) && nodeIds.has(edge.toId));
  return { requestId: requestId(input), nodes, edges };
}

async function getSpecPreview(client: DesignUiApiClient, input: ToolInput) {
  const projectId = requireString(input, "projectId");
  const format = stringValue(input.format, "both");
  const spec = await client.get<Record<string, unknown>>(`/spec?${params(projectId)}`);
  const payload = spec.spec as Record<string, unknown>;
  return {
    requestId: requestId(input),
    markdown: format === "markdown" || format === "both" ? spec.markdown : undefined,
    json: format === "json" || format === "both" ? spec.json : undefined,
    sourcePurposeItemIds: payload?.sourcePurposeItemIds ?? [],
    sourceLineageEventIds: payload?.sourceLineageEventIds ?? []
  };
}

async function getValidationResults(client: DesignUiApiClient, input: ToolInput) {
  const projectId = requireString(input, "projectId");
  const spec = await client.get<Record<string, unknown>>(`/spec?${params(projectId)}`);
  return {
    requestId: requestId(input),
    ...(spec.validation as Record<string, unknown>)
  };
}

async function createProposal(
  client: DesignUiApiClient,
  projectId: string,
  requestIdValue: string,
  proposalType: string,
  proposedChanges: Record<string, unknown>,
  rationale: string,
  sourceMessageIds: string[]
) {
  const proposal = await client.post<Record<string, unknown>>(`/proposals?${params(projectId)}`, {
    proposalType,
    proposedChanges,
    rationale,
    sourceMessageIds
  });
  return {
    requestId: requestIdValue,
    proposal
  };
}

async function createDesignProposal(client: DesignUiApiClient, input: ToolInput, toolName: DesignUiMcpToolName) {
  const id = requestId(input);
  const projectId = requireString(input, "projectId");
  const targetKind = requireString(input, "targetKind");
  const title = requireString(input, "title");
  const rationale = requireString(input, "rationale");
  if (targetKind !== "discovery" && targetKind !== "purpose") {
    throw new Error("targetKind must be discovery or purpose");
  }
  const proposedChanges =
    targetKind === "discovery"
      ? {
          title,
          body: stringValue(input.body),
          discoveryType: stringValue(input.discoveryType, "observation")
        }
      : {
          title,
          body: stringValue(input.body),
          purposeType: stringValue(input.purposeType, "purpose_candidate")
        };
  return createProposal(
    client,
    projectId,
    id,
    targetKind === "discovery" ? "create_discovery" : "create_purpose",
    withAttribution(proposedChanges, input, toolName),
    rationale,
    stringArray(input.sourceMessageIds)
  );
}

async function createRelationshipProposal(client: DesignUiApiClient, input: ToolInput, toolName: DesignUiMcpToolName) {
  const id = requestId(input);
  const projectId = requireString(input, "projectId");
  const proposedChanges = {
    fromId: requireString(input, "fromId"),
    toId: requireString(input, "toId"),
    type: stringValue(input.relationshipType, "related_to"),
    description: stringValue(input.description)
  };
  return createProposal(
    client,
    projectId,
    id,
    "connect_items",
    withAttribution(proposedChanges, input, toolName),
    requireString(input, "rationale"),
    stringArray(input.sourceMessageIds)
  );
}

async function createPromotionProposal(client: DesignUiApiClient, input: ToolInput, toolName: DesignUiMcpToolName) {
  const id = requestId(input);
  const projectId = requireString(input, "projectId");
  const proposedChanges = {
    sourceId: requireString(input, "sourceDiscoveryItemId"),
    title: stringValue(input.title),
    body: stringValue(input.body),
    purposeType: stringValue(input.purposeType, "purpose_candidate")
  };
  return createProposal(
    client,
    projectId,
    id,
    "promote_to_purpose",
    withAttribution(proposedChanges, input, toolName),
    requireString(input, "rationale"),
    stringArray(input.sourceMessageIds)
  );
}

async function createDemotionProposal(client: DesignUiApiClient, input: ToolInput, toolName: DesignUiMcpToolName) {
  const id = requestId(input);
  const projectId = requireString(input, "projectId");
  const proposedChanges = {
    sourceId: requireString(input, "sourcePurposeItemId"),
    title: stringValue(input.title),
    body: stringValue(input.body),
    discoveryType: stringValue(input.discoveryType, "observation")
  };
  return createProposal(
    client,
    projectId,
    id,
    "demote_to_discovery",
    withAttribution(proposedChanges, input, toolName),
    requireString(input, "rationale"),
    stringArray(input.sourceMessageIds)
  );
}

async function createUpdateProposal(client: DesignUiApiClient, input: ToolInput, toolName: DesignUiMcpToolName) {
  const id = requestId(input);
  const projectId = requireString(input, "projectId");
  const patch = input.patch && typeof input.patch === "object" ? (input.patch as Record<string, unknown>) : {};
  const forbidden = Object.keys(patch).filter((key) => forbiddenPatchFields.has(key));
  if (forbidden.length > 0) {
    throw new Error(`patch contains forbidden committed-state fields: ${forbidden.join(", ")}`);
  }
  const proposedChanges = {
    table: requireString(input, "targetTable"),
    id: requireString(input, "targetId"),
    patch
  };
  return createProposal(
    client,
    projectId,
    id,
    "update_item",
    withAttribution(proposedChanges, input, toolName),
    requireString(input, "rationale"),
    stringArray(input.sourceMessageIds)
  );
}
