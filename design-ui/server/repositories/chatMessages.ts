import type { DesignDatabase } from "../db.ts";
import { encodeJson, insertRecord, listByProject, newId, nowIso } from "./base.ts";

export function createChatMessage(
  db: DesignDatabase,
  input: {
    projectId: string;
    role: "operator" | "assistant" | "system";
    content: string;
    sourceRefs?: string[];
    id?: string;
  }
) {
  return insertRecord(db, "chat_messages", {
    id: input.id ?? newId("chat"),
    projectId: input.projectId,
    role: input.role,
    content: input.content,
    sourceRefs: encodeJson(input.sourceRefs ?? []),
    createdAt: nowIso()
  });
}

export function listChatMessages(db: DesignDatabase, projectId: string) {
  return listByProject(db, "chat_messages", projectId);
}
