import type { DesignDatabase } from "../db.ts";
import { decodeJson, encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export type LineageEvent = {
  id: string;
  projectId: string;
  subjectId: string;
  eventType: string;
  beforeValue: unknown;
  afterValue: unknown;
  messageIds: string[];
  proposalId: string | null;
  createdAt: string;
};

function normalizeLineageEvent(row: unknown): LineageEvent | undefined {
  if (!row || typeof row !== "object") return undefined;
  const event = row as Record<string, unknown>;
  return {
    id: String(event.id),
    projectId: String(event.projectId),
    subjectId: String(event.subjectId),
    eventType: String(event.eventType),
    beforeValue: event.beforeValue === null ? null : decodeJson(event.beforeValue, null),
    afterValue: event.afterValue === null ? null : decodeJson(event.afterValue, null),
    messageIds: decodeJson<string[]>(event.messageIds, []),
    proposalId: event.proposalId === null ? null : String(event.proposalId),
    createdAt: String(event.createdAt)
  };
}

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
  return listByProject(db, "lineage_events", projectId)
    .map(normalizeLineageEvent)
    .filter((event): event is LineageEvent => Boolean(event));
}

export function listLineagePlayback(db: DesignDatabase, projectId: string, subjectId?: string) {
  const rows = subjectId
    ? db
        .prepare(
          "SELECT * FROM lineage_events WHERE projectId = ? AND subjectId = ? ORDER BY createdAt ASC"
        )
        .all(projectId, subjectId)
    : db.prepare("SELECT * FROM lineage_events WHERE projectId = ? ORDER BY createdAt ASC").all(projectId);
  return rows.map(normalizeLineageEvent).filter((event): event is LineageEvent => Boolean(event));
}
