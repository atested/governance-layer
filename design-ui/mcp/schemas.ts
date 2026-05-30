export const DEFAULT_API_URL = "http://127.0.0.1:4174/api";

export const requiredToolNames = [
  "get_active_project",
  "get_active_context",
  "list_discovery_items",
  "list_purpose_items",
  "list_relationships",
  "list_map_nodes",
  "get_spec_preview",
  "get_validation_results",
  "create_design_proposal",
  "create_relationship_proposal",
  "create_promotion_proposal",
  "create_demotion_proposal",
  "create_update_proposal"
] as const;

export type DesignUiMcpToolName = (typeof requiredToolNames)[number];

export type McpOrigin = {
  clientName: string;
  clientSessionId?: string;
  model?: string;
  userLabel?: string;
  requestId?: string;
};

export type ToolInput = Record<string, unknown>;

export type JsonSchema = {
  type: "object";
  properties: Record<string, unknown>;
  required?: string[];
  additionalProperties?: boolean;
};

const requestIdProperty = {
  type: "string",
  description: "Optional caller-provided request correlation id."
};

const projectIdProperty = {
  type: "string",
  description: "Design UI project id."
};

const originProperty = {
  type: "object",
  description: "MCP origin attribution for proposals.",
  properties: {
    clientName: { type: "string" },
    clientSessionId: { type: "string" },
    model: { type: "string" },
    userLabel: { type: "string" },
    requestId: { type: "string" }
  },
  required: ["clientName"],
  additionalProperties: false
};

export const toolInputSchemas: Record<DesignUiMcpToolName, JsonSchema> = {
  get_active_project: {
    type: "object",
    properties: { requestId: requestIdProperty },
    additionalProperties: false
  },
  get_active_context: {
    type: "object",
    properties: { projectId: projectIdProperty, requestId: requestIdProperty },
    required: ["projectId"],
    additionalProperties: false
  },
  list_discovery_items: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      contextOnly: { type: "boolean" },
      state: { type: "string" },
      discoveryType: { type: "string" },
      requestId: requestIdProperty
    },
    required: ["projectId"],
    additionalProperties: false
  },
  list_purpose_items: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      contextOnly: { type: "boolean" },
      state: { type: "string" },
      purposeType: { type: "string" },
      requestId: requestIdProperty
    },
    required: ["projectId"],
    additionalProperties: false
  },
  list_relationships: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      itemId: { type: "string" },
      relationshipType: { type: "string" },
      requestId: requestIdProperty
    },
    required: ["projectId"],
    additionalProperties: false
  },
  list_map_nodes: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      nodeType: {
        type: "string",
        enum: [
          "concept",
          "discovery_cluster",
          "purpose_region",
          "tension",
          "open_area",
          "disconnected_idea"
        ]
      },
      maturity: { type: "string" },
      connected: { type: "boolean" },
      requestId: requestIdProperty
    },
    required: ["projectId"],
    additionalProperties: false
  },
  get_spec_preview: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      format: { type: "string", enum: ["markdown", "json", "both"] },
      requestId: requestIdProperty
    },
    required: ["projectId"],
    additionalProperties: false
  },
  get_validation_results: {
    type: "object",
    properties: { projectId: projectIdProperty, requestId: requestIdProperty },
    required: ["projectId"],
    additionalProperties: false
  },
  create_design_proposal: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      targetKind: { type: "string", enum: ["discovery", "purpose"] },
      title: { type: "string" },
      body: { type: "string" },
      discoveryType: { type: "string" },
      purposeType: { type: "string" },
      rationale: { type: "string" },
      sourceMessageIds: { type: "array", items: { type: "string" } },
      origin: originProperty,
      requestId: requestIdProperty
    },
    required: ["projectId", "targetKind", "title", "rationale", "origin"],
    additionalProperties: false
  },
  create_relationship_proposal: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      fromId: { type: "string" },
      toId: { type: "string" },
      relationshipType: { type: "string" },
      description: { type: "string" },
      rationale: { type: "string" },
      sourceMessageIds: { type: "array", items: { type: "string" } },
      origin: originProperty,
      requestId: requestIdProperty
    },
    required: ["projectId", "fromId", "toId", "rationale", "origin"],
    additionalProperties: false
  },
  create_promotion_proposal: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      sourceDiscoveryItemId: { type: "string" },
      title: { type: "string" },
      body: { type: "string" },
      purposeType: { type: "string" },
      rationale: { type: "string" },
      sourceMessageIds: { type: "array", items: { type: "string" } },
      origin: originProperty,
      requestId: requestIdProperty
    },
    required: ["projectId", "sourceDiscoveryItemId", "rationale", "origin"],
    additionalProperties: false
  },
  create_demotion_proposal: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      sourcePurposeItemId: { type: "string" },
      title: { type: "string" },
      body: { type: "string" },
      discoveryType: { type: "string" },
      rationale: { type: "string" },
      sourceMessageIds: { type: "array", items: { type: "string" } },
      origin: originProperty,
      requestId: requestIdProperty
    },
    required: ["projectId", "sourcePurposeItemId", "rationale", "origin"],
    additionalProperties: false
  },
  create_update_proposal: {
    type: "object",
    properties: {
      projectId: projectIdProperty,
      targetTable: {
        type: "string",
        enum: ["discovery_items", "purpose_items", "concepts", "relationships"]
      },
      targetId: { type: "string" },
      patch: { type: "object" },
      rationale: { type: "string" },
      sourceMessageIds: { type: "array", items: { type: "string" } },
      origin: originProperty,
      requestId: requestIdProperty
    },
    required: ["projectId", "targetTable", "targetId", "patch", "rationale", "origin"],
    additionalProperties: false
  }
};

export const forbiddenPatchFields = new Set([
  "id",
  "projectId",
  "createdAt",
  "createdFromMessageIds",
  "lineageEventIds",
  "proposalId"
]);
