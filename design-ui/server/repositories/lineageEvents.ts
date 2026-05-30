import type { DesignDatabase } from "../db.ts";
import { encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createLineageEvent(
  db: DesignDatabase,
  input: {
    projectId: string;
    subjectId: string;
    eventType: string;
    beforeValue?: unknown;
    afterValue?: unknown;
    messageIds?: string[];
    proposalId?: string | null;
    id?: string;
  }
) {
  return insertRecord(db, "lineage_events", {
    id: input.id ?? newId("lineage"),
    projectId: input.projectId,
    subjectId: input.subjectId,
    eventType: input.eventType,
    beforeValue: input.beforeValue === undefined ? null : JSON.stringify(input.beforeValue),
    afterValue: input.afterValue === undefined ? null : JSON.stringify(input.afterValue),
    messageIds: encodeJson(input.messageIds ?? []),
    proposalId: input.proposalId ?? null,
    createdAt: nowIso()
  });
}

export function listLineageEvents(db: DesignDatabase, projectId: string) {
  return listByProject(db, "lineage_events", projectId);
}
