import type { DesignDatabase } from "../db.ts";
import { listActiveContexts } from "../repositories/activeContexts.ts";
import { listConcepts } from "../repositories/concepts.ts";
import { listDiscoveryItems } from "../repositories/discoveryItems.ts";
import { getProject } from "../repositories/projects.ts";
import { listPurposeItems } from "../repositories/purposeItems.ts";
import { listRelationships } from "../repositories/relationships.ts";

export type MapNodeType =
  | "concept"
  | "discovery_cluster"
  | "purpose_region"
  | "tension"
  | "open_area"
  | "disconnected_idea";

export type MapNode = {
  id: string;
  label: string;
  nodeType: MapNodeType;
  maturity: string;
  connected: boolean;
  sourceKind: "concept" | "discovery" | "purpose";
  sourceId: string;
};

export type MapEdge = {
  id: string;
  fromId: string;
  toId: string;
  type: string;
  description: string;
};

function relationshipTouches(relationships: Array<Record<string, unknown>>, id: string) {
  return relationships.some((relationship) => relationship.fromId === id || relationship.toId === id);
}

function discoveryNodeType(item: Record<string, unknown>, connected: boolean): MapNodeType {
  if (!connected) return "disconnected_idea";
  if (item.discoveryType === "tension") return "tension";
  if (item.discoveryType === "question" || item.discoveryType === "unresolved_area") return "open_area";
  return "discovery_cluster";
}

export function buildDesignMap(db: DesignDatabase, projectId: string) {
  const concepts = listConcepts(db, projectId) as Array<Record<string, unknown>>;
  const discoveryItems = listDiscoveryItems(db, projectId) as Array<Record<string, unknown>>;
  const purposeItems = listPurposeItems(db, projectId) as Array<Record<string, unknown>>;
  const relationships = listRelationships(db, projectId) as Array<Record<string, unknown>>;
  const activeContexts = listActiveContexts(db, projectId);
  const project = getProject(db, projectId) as Record<string, unknown> | undefined;
  const edges: MapEdge[] = relationships.map((relationship) => ({
    id: String(relationship.id),
    fromId: String(relationship.fromId),
    toId: String(relationship.toId),
    type: String(relationship.type),
    description: String(relationship.description ?? "")
  }));

  const nodes: MapNode[] = [
    ...concepts.map((concept) => {
      const id = String(concept.id);
      return {
        id,
        label: String(concept.name),
        nodeType: "concept" as const,
        maturity: String(concept.maturity),
        connected: relationshipTouches(relationships, id),
        sourceKind: "concept" as const,
        sourceId: id
      };
    }),
    ...discoveryItems.map((item) => {
      const id = String(item.id);
      const connected = relationshipTouches(relationships, id);
      return {
        id,
        label: String(item.title),
        nodeType: discoveryNodeType(item, connected),
        maturity: String(item.state),
        connected,
        sourceKind: "discovery" as const,
        sourceId: id
      };
    }),
    ...purposeItems.map((item) => {
      const id = String(item.id);
      return {
        id,
        label: String(item.title),
        nodeType: relationshipTouches(relationships, id)
          ? ("purpose_region" as const)
          : ("disconnected_idea" as const),
        maturity: String(item.state),
        connected: relationshipTouches(relationships, id),
        sourceKind: "purpose" as const,
        sourceId: id
      };
    })
  ];

  return {
    nodes,
    edges,
    activeContexts,
    activeContext:
      typeof project?.activeContextId === "string" && project.activeContextId
        ? activeContexts.find((context) => context.id === project.activeContextId) ?? null
        : null
  };
}

export function contextForNode(db: DesignDatabase, projectId: string, nodeId: string) {
  const map = buildDesignMap(db, projectId);
  const node = map.nodes.find((candidate) => candidate.id === nodeId);
  if (!node) throw new Error("Map node not found");
  const relationshipIds = map.edges
    .filter((edge) => edge.fromId === node.id || edge.toId === node.id)
    .map((edge) => edge.id);
  return {
    label: node.label,
    discoveryItemIds: node.sourceKind === "discovery" ? [node.sourceId] : [],
    purposeItemIds: node.sourceKind === "purpose" ? [node.sourceId] : [],
    conceptIds: node.sourceKind === "concept" ? [node.sourceId] : [],
    relationshipIds
  };
}
