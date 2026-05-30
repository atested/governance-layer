import type { DesignDatabase } from "../db.ts";
import { decodeJson, encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export type ActiveContext = {
  id: string;
  projectId: string;
  label: string;
  discoveryItemIds: string[];
  purposeItemIds: string[];
  conceptIds: string[];
  relationshipIds: string[];
  createdAt: string;
  updatedAt: string;
};

function normalizeActiveContext(row: unknown): ActiveContext | undefined {
  if (!row || typeof row !== "object") return undefined;
  const context = row as Record<string, unknown>;
  return {
    id: String(context.id),
    projectId: String(context.projectId),
    label: String(context.label),
    discoveryItemIds: decodeJson<string[]>(context.discoveryItemIds, []),
    purposeItemIds: decodeJson<string[]>(context.purposeItemIds, []),
    conceptIds: decodeJson<string[]>(context.conceptIds, []),
    relationshipIds: decodeJson<string[]>(context.relationshipIds, []),
    createdAt: String(context.createdAt),
    updatedAt: String(context.updatedAt)
  };
}

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
  const row = insertRecord(db, "active_contexts", {
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
  const context = normalizeActiveContext(row);
  if (!context) throw new Error("Failed to normalize active context");
  return context;
}

export function listActiveContexts(db: DesignDatabase, projectId: string) {
  return listByProject(db, "active_contexts", projectId)
    .map(normalizeActiveContext)
    .filter((context): context is ActiveContext => Boolean(context));
}

export function getActiveContext(db: DesignDatabase, projectId: string, id: string) {
  return normalizeActiveContext(
    db.prepare("SELECT * FROM active_contexts WHERE projectId = ? AND id = ?").get(projectId, id)
  );
}

export function replaceActiveContext(
  db: DesignDatabase,
  input: {
    projectId: string;
    label: string;
    discoveryItemIds?: string[];
    purposeItemIds?: string[];
    conceptIds?: string[];
    relationshipIds?: string[];
  }
) {
  const timestamp = nowIso();
  const id = newId("context");
  db.prepare(
    `INSERT INTO active_contexts (
      id, projectId, label, discoveryItemIds, purposeItemIds, conceptIds, relationshipIds, createdAt, updatedAt
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
  ).run(
    id,
    input.projectId,
    input.label,
    encodeJson(input.discoveryItemIds ?? []),
    encodeJson(input.purposeItemIds ?? []),
    encodeJson(input.conceptIds ?? []),
    encodeJson(input.relationshipIds ?? []),
    timestamp,
    timestamp
  );
  db.prepare("UPDATE projects SET activeContextId = ?, updatedAt = ? WHERE id = ?").run(
    id,
    timestamp,
    input.projectId
  );
  const context = getActiveContext(db, input.projectId, id);
  if (!context) throw new Error("Failed to create active context");
  return context;
}
