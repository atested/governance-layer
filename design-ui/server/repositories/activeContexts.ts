import type { DesignDatabase } from "../db.ts";
import { encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createActiveContext(
  db: DesignDatabase,
  input: {
    projectId: string;
    label: string;
    discoveryItemIds?: string[];
    purposeItemIds?: string[];
    conceptIds?: string[];
    relationshipIds?: string[];
    id?: string;
  }
) {
  const timestamp = nowIso();
  return insertRecord(db, "active_contexts", {
    id: input.id ?? newId("context"),
    projectId: input.projectId,
    label: input.label,
    discoveryItemIds: encodeJson(input.discoveryItemIds ?? []),
    purposeItemIds: encodeJson(input.purposeItemIds ?? []),
    conceptIds: encodeJson(input.conceptIds ?? []),
    relationshipIds: encodeJson(input.relationshipIds ?? []),
    createdAt: timestamp,
    updatedAt: timestamp
  });
}

export function listActiveContexts(db: DesignDatabase, projectId: string) {
  return listByProject(db, "active_contexts", projectId);
}
