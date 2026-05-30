import type { DesignDatabase } from "../db.ts";
import { createChatMessage } from "../repositories/chatMessages.ts";
import { createProposal } from "../repositories/proposals.ts";

function clean(value: string) {
  return value.trim().replace(/\s+/g, " ");
}

function stripPrefix(content: string, prefix: string) {
  return clean(content.slice(prefix.length));
}

export function generateStubProposals(
  db: DesignDatabase,
  input: {
    projectId: string;
    operatorMessageId: string;
    content: string;
  }
) {
  const content = clean(input.content);
  const lower = content.toLowerCase();
  const proposals = [];

  if (content.includes("?")) {
    proposals.push(
      createProposal(db, {
        projectId: input.projectId,
        proposalType: "create_discovery",
        rationale: "Question detected in chat.",
        sourceMessageIds: [input.operatorMessageId],
        proposedChanges: {
          title: content,
          body: content,
          discoveryType: "question",
          createdFromMessageIds: [input.operatorMessageId]
        }
      })
    );
  }

  if (lower.startsWith("purpose:")) {
    const title = stripPrefix(content, "purpose:");
    proposals.push(
      createProposal(db, {
        projectId: input.projectId,
        proposalType: "create_purpose",
        rationale: "Purpose prefix detected in chat.",
        sourceMessageIds: [input.operatorMessageId],
        proposedChanges: {
          title,
          body: title,
          purposeType: "purpose_candidate",
          createdFromMessageIds: [input.operatorMessageId]
        }
      })
    );
  }

  if (lower.startsWith("constraint:")) {
    const title = stripPrefix(content, "constraint:");
    proposals.push(
      createProposal(db, {
        projectId: input.projectId,
        proposalType: "create_purpose",
        rationale: "Constraint prefix detected in chat.",
        sourceMessageIds: [input.operatorMessageId],
        proposedChanges: {
          title,
          body: title,
          purposeType: "constraint",
          createdFromMessageIds: [input.operatorMessageId]
        }
      })
    );
  }

  if (lower.startsWith("boundary:")) {
    const title = stripPrefix(content, "boundary:");
    proposals.push(
      createProposal(db, {
        projectId: input.projectId,
        proposalType: "create_purpose",
        rationale: "Boundary prefix detected in chat.",
        sourceMessageIds: [input.operatorMessageId],
        proposedChanges: {
          title,
          body: title,
          purposeType: "boundary",
          createdFromMessageIds: [input.operatorMessageId]
        }
      })
    );
  }

  const connectMatch = content.match(/^connect\s+(.+?)\s+to\s+(.+)$/i);
  if (connectMatch) {
    proposals.push(
      createProposal(db, {
        projectId: input.projectId,
        proposalType: "connect_items",
        rationale: "Connection command detected in chat.",
        sourceMessageIds: [input.operatorMessageId],
        proposedChanges: {
          fromId: clean(connectMatch[1]),
          toId: clean(connectMatch[2]),
          type: "related_to",
          description: `Connect ${clean(connectMatch[1])} to ${clean(connectMatch[2])}`
        }
      })
    );
  }

  return proposals;
}

export function createStubChatTurn(
  db: DesignDatabase,
  input: {
    projectId: string;
    content: string;
  }
) {
  const operatorMessage = createChatMessage(db, {
    projectId: input.projectId,
    role: "operator",
    content: input.content
  });
  const proposals = generateStubProposals(db, {
    projectId: input.projectId,
    operatorMessageId: String(operatorMessage.id),
    content: input.content
  });
  const assistantMessage = createChatMessage(db, {
    projectId: input.projectId,
    role: "assistant",
    content:
      proposals.length === 0
        ? "No structured proposal was detected by the v1 stub."
        : `Created ${proposals.length} pending proposal${proposals.length === 1 ? "" : "s"} for review.`
  });

  return { operatorMessage, assistantMessage, proposals };
}
