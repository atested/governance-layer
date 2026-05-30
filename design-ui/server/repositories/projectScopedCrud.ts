import type { SQLInputValue } from "node:sqlite";
import type { DesignDatabase } from "../db.ts";

const projectScopedTables = new Set([
  "chat_messages",
  "discovery_items",
  "purpose_items",
  "concepts",
  "relationships",
  "proposals",
  "lineage_events",
  "active_contexts",
  "spec_exports"
]);

function assertProjectScopedTable(table: string) {
  if (!projectScopedTables.has(table)) {
    throw new Error(`Unsupported project-scoped table: ${table}`);
  }
}

export function getProjectScopedRecord(
  db: DesignDatabase,
  table: string,
  projectId: string,
  id: string
) {
  assertProjectScopedTable(table);
  return db.prepare(`SELECT * FROM ${table} WHERE projectId = ? AND id = ?`).get(projectId, id);
}

export function updateProjectScopedRecord(
  db: DesignDatabase,
  table: string,
  projectId: string,
  id: string,
  changes: Record<string, SQLInputValue>
) {
  assertProjectScopedTable(table);
  const keys = Object.keys(changes);
  if (keys.length === 0) {
    return getProjectScopedRecord(db, table, projectId, id);
  }

  const assignments = keys.map((key) => `${key} = ?`).join(", ");
  db.prepare(`UPDATE ${table} SET ${assignments} WHERE projectId = ? AND id = ?`).run(
    ...keys.map((key) => changes[key]),
    projectId,
    id
  );
  return getProjectScopedRecord(db, table, projectId, id);
}

export function deleteProjectScopedRecord(
  db: DesignDatabase,
  table: string,
  projectId: string,
  id: string
) {
  assertProjectScopedTable(table);
  const result = db.prepare(`DELETE FROM ${table} WHERE projectId = ? AND id = ?`).run(projectId, id);
  return result.changes > 0;
}
