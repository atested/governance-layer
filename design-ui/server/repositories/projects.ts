import type { DesignDatabase } from "../db.ts";
import { insertRecord, newId, nowIso } from "./base.ts";

export function createProject(db: DesignDatabase, input: { title: string; id?: string }) {
  const timestamp = nowIso();
  return insertRecord(db, "projects", {
    id: input.id ?? newId("project"),
    title: input.title,
    activeContextId: null,
    createdAt: timestamp,
    updatedAt: timestamp
  });
}

export function getProject(db: DesignDatabase, id: string) {
  return db.prepare("SELECT * FROM projects WHERE id = ?").get(id);
}
