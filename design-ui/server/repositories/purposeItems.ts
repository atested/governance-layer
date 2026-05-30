import type { DesignDatabase } from "../db.ts";
import { encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createPurposeItem(
  db: DesignDatabase,
  input: {
    projectId: string;
    title: string;
    body?: string;
    purposeType: string;
    state?: string;
    createdFromMessageIds?: string[];
    tags?: string[];
    id?: string;
  }
) {
  const timestamp = nowIso();
  return insertRecord(db, "purpose_items", {
    id: input.id ?? newId("purpose"),
    projectId: input.projectId,
    title: input.title,
    body: input.body ?? "",
    purposeType: input.purposeType,
    state: input.state ?? "purpose_candidate",
    createdFromMessageIds: encodeJson(input.createdFromMessageIds ?? []),
    lineageEventIds: encodeJson([]),
    tags: encodeJson(input.tags ?? []),
    createdAt: timestamp,
    updatedAt: timestamp
  });
}

export function listPurposeItems(db: DesignDatabase, projectId: string) {
  return listByProject(db, "purpose_items", projectId);
}
