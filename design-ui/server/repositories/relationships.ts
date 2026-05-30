import type { DesignDatabase } from "../db.ts";
import { insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createRelationship(
  db: DesignDatabase,
  input: {
    projectId: string;
    fromId: string;
    toId: string;
    type: string;
    description?: string;
    id?: string;
  }
) {
  return insertRecord(db, "relationships", {
    id: input.id ?? newId("relationship"),
    projectId: input.projectId,
    fromId: input.fromId,
    toId: input.toId,
    type: input.type,
    description: input.description ?? "",
    createdAt: nowIso()
  });
}

export function listRelationships(db: DesignDatabase, projectId: string) {
  return listByProject(db, "relationships", projectId);
}
