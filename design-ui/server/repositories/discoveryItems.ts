import type { DesignDatabase } from "../db.ts";
import { encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createDiscoveryItem(
  db: DesignDatabase,
  input: {
    projectId: string;
    title: string;
    body?: string;
    discoveryType: string;
    state?: string;
    createdFromMessageIds?: string[];
    tags?: string[];
    id?: string;
  }
) {
  const timestamp = nowIso();
  return insertRecord(db, "discovery_items", {
    id: input.id ?? newId("discovery"),
    projectId: input.projectId,
    title: input.title,
    body: input.body ?? "",
    discoveryType: input.discoveryType,
    state: input.state ?? "noticed",
    createdFromMessageIds: encodeJson(input.createdFromMessageIds ?? []),
    lineageEventIds: encodeJson([]),
    tags: encodeJson(input.tags ?? []),
    createdAt: timestamp,
    updatedAt: timestamp
  });
}

export function listDiscoveryItems(db: DesignDatabase, projectId: string) {
  return listByProject(db, "discovery_items", projectId);
}
