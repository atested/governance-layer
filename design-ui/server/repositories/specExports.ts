import type { DesignDatabase } from "../db.ts";
import { encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createSpecExport(
  db: DesignDatabase,
  input: {
    projectId: string;
    format: "markdown" | "json";
    content: string;
    sourcePurposeItemIds?: string[];
    sourceLineageEventIds?: string[];
    id?: string;
  }
) {
  return insertRecord(db, "spec_exports", {
    id: input.id ?? newId("export"),
    projectId: input.projectId,
    format: input.format,
    content: input.content,
    sourcePurposeItemIds: encodeJson(input.sourcePurposeItemIds ?? []),
    sourceLineageEventIds: encodeJson(input.sourceLineageEventIds ?? []),
    createdAt: nowIso()
  });
}

export function listSpecExports(db: DesignDatabase, projectId: string) {
  return listByProject(db, "spec_exports", projectId);
}
