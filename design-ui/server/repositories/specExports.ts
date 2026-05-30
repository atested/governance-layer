import type { DesignDatabase } from "../db.ts";
import { decodeJson, encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export type SpecExport = {
  id: string;
  projectId: string;
  format: "markdown" | "json";
  content: string;
  sourcePurposeItemIds: string[];
  sourceLineageEventIds: string[];
  createdAt: string;
};

function normalizeSpecExport(row: unknown): SpecExport | undefined {
  if (!row || typeof row !== "object") return undefined;
  const exportRow = row as Record<string, unknown>;
  return {
    id: String(exportRow.id),
    projectId: String(exportRow.projectId),
    format: exportRow.format === "json" ? "json" : "markdown",
    content: String(exportRow.content ?? ""),
    sourcePurposeItemIds: decodeJson<string[]>(exportRow.sourcePurposeItemIds, []),
    sourceLineageEventIds: decodeJson<string[]>(exportRow.sourceLineageEventIds, []),
    createdAt: String(exportRow.createdAt)
  };
}

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
  const row = insertRecord(db, "spec_exports", {
    id: input.id ?? newId("export"),
    projectId: input.projectId,
    format: input.format,
    content: input.content,
    sourcePurposeItemIds: encodeJson(input.sourcePurposeItemIds ?? []),
    sourceLineageEventIds: encodeJson(input.sourceLineageEventIds ?? []),
    createdAt: nowIso()
  });
  const specExport = normalizeSpecExport(row);
  if (!specExport) throw new Error("Failed to normalize spec export");
  return specExport;
}

export function listSpecExports(db: DesignDatabase, projectId: string) {
  return listByProject(db, "spec_exports", projectId)
    .map(normalizeSpecExport)
    .filter((specExport): specExport is SpecExport => Boolean(specExport));
}
