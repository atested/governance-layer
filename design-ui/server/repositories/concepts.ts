import type { DesignDatabase } from "../db.ts";
import { encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createConcept(
  db: DesignDatabase,
  input: {
    projectId: string;
    name: string;
    summary?: string;
    discoveryItemIds?: string[];
    purposeItemIds?: string[];
    relationshipIds?: string[];
    maturity?: string;
    id?: string;
  }
) {
  const timestamp = nowIso();
  return insertRecord(db, "concepts", {
    id: input.id ?? newId("concept"),
    projectId: input.projectId,
    name: input.name,
    summary: input.summary ?? "",
    discoveryItemIds: encodeJson(input.discoveryItemIds ?? []),
    purposeItemIds: encodeJson(input.purposeItemIds ?? []),
    relationshipIds: encodeJson(input.relationshipIds ?? []),
    maturity: input.maturity ?? "raw",
    createdAt: timestamp,
    updatedAt: timestamp
  });
}

export function listConcepts(db: DesignDatabase, projectId: string) {
  return listByProject(db, "concepts", projectId);
}
