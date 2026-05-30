import { randomUUID } from "node:crypto";
import type { SQLInputValue } from "node:sqlite";
import type { DesignDatabase } from "../db.ts";

export function nowIso() {
  return new Date().toISOString();
}

export function newId(prefix: string) {
  return `${prefix}_${randomUUID()}`;
}

export function encodeJson(value: unknown) {
  return JSON.stringify(value ?? []);
}

export function decodeJson<T>(value: unknown, fallback: T): T {
  if (typeof value !== "string") return fallback;
  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

export function insertRecord<T extends Record<string, unknown>>(
  db: DesignDatabase,
  table: string,
  record: T
) {
  const keys = Object.keys(record);
  const placeholders = keys.map(() => "?").join(", ");
  db.prepare(
    `INSERT INTO ${table} (${keys.join(", ")}) VALUES (${placeholders})`
  ).run(...keys.map((key) => record[key] as SQLInputValue));
  return record;
}

export function listByProject(db: DesignDatabase, table: string, projectId: string) {
  return db.prepare(`SELECT * FROM ${table} WHERE projectId = ? ORDER BY createdAt ASC`).all(projectId);
}

export function countByProject(db: DesignDatabase, table: string, projectId: string) {
  const row = db.prepare(`SELECT COUNT(*) AS count FROM ${table} WHERE projectId = ?`).get(projectId);
  return Number(row?.count ?? 0);
}
