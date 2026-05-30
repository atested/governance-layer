import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { initializeDatabase } from "../server/db.ts";
import { countByProject } from "../server/repositories/base.ts";
import { createDiscoveryItem, listDiscoveryItems } from "../server/repositories/discoveryItems.ts";
import { listLineageEvents } from "../server/repositories/lineageEvents.ts";
import { createProject } from "../server/repositories/projects.ts";
import { createProposal, getProposal } from "../server/repositories/proposals.ts";
import { listPurposeItems } from "../server/repositories/purposeItems.ts";
import { listRelationships } from "../server/repositories/relationships.ts";
import { acceptProposal, rejectProposal } from "../server/services/proposalCommitter.ts";
import { buildProposalPreview } from "../server/services/proposalPreview.ts";
import { createStubChatTurn } from "../server/services/stubProposalEngine.ts";

function withDatabase(run: (dbPath: string) => void) {
  const dir = mkdtempSync(path.join(tmpdir(), "design-ui-proposal-test-"));
  try {
    run(path.join(dir, "test.sqlite"));
  } finally {
    rmSync(dir, { force: true, recursive: true });
  }
}

test("pending proposal preview shows creates and lineage events", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Preview Test" });
    const proposal = createProposal(db, {
      projectId: String(project.id),
      proposalType: "create_discovery",
      proposedChanges: { title: "What changed?", discoveryType: "question" }
    });

    const preview = buildProposalPreview(proposal);
    assert.equal(preview.creates[0].table, "discovery_items");
    assert.equal(preview.creates[0].title, "What changed?");
    assert.equal(preview.lineageEvents[0].eventType, "created");
    db.close();
  });
});

test("accepting create_discovery applies object change, lineage, and proposal status", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Accept Test" });
    const projectId = String(project.id);
    const proposal = createProposal(db, {
      projectId,
      proposalType: "create_discovery",
      proposedChanges: {
        title: "Is the map a terrain?",
        body: "Discovery body",
        discoveryType: "question"
      }
    });

    acceptProposal(db, projectId, String(proposal.id));

    const discovery = listDiscoveryItems(db, projectId);
    const lineage = listLineageEvents(db, projectId);
    const resolved = getProposal(db, projectId, String(proposal.id));
    assert.equal(discovery.length, 1);
    assert.equal(discovery[0].title, "Is the map a terrain?");
    assert.equal(lineage.length, 1);
    assert.equal(lineage[0].eventType, "created");
    assert.equal(resolved?.status, "accepted");
    assert.equal(typeof resolved?.resolvedAt, "string");
    db.close();
  });
});

test("rejecting proposal does not mutate committed objects or lineage", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Reject Test" });
    const projectId = String(project.id);
    const proposal = createProposal(db, {
      projectId,
      proposalType: "create_purpose",
      proposedChanges: { title: "Do not commit", purposeType: "purpose_candidate" }
    });

    rejectProposal(db, projectId, String(proposal.id));

    assert.equal(countByProject(db, "purpose_items", projectId), 0);
    assert.equal(countByProject(db, "lineage_events", projectId), 0);
    const resolved = getProposal(db, projectId, String(proposal.id));
    assert.equal(resolved?.status, "rejected");
    assert.equal(typeof resolved?.resolvedAt, "string");
    db.close();
  });
});

test("promotion, demotion, connection, and update proposal types commit through boundary", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Supported Types Test" });
    const projectId = String(project.id);
    const discovery = createDiscoveryItem(db, {
      projectId,
      title: "Discovery to promote",
      discoveryType: "observation"
    });
    const promote = createProposal(db, {
      projectId,
      proposalType: "promote_to_purpose",
      proposedChanges: { sourceId: discovery.id, title: "Promoted purpose", purposeType: "purpose_candidate" }
    });
    acceptProposal(db, projectId, String(promote.id));
    const purpose = listPurposeItems(db, projectId)[0];

    const demote = createProposal(db, {
      projectId,
      proposalType: "demote_to_discovery",
      proposedChanges: { sourceId: purpose.id, title: "Demoted discovery", discoveryType: "observation" }
    });
    acceptProposal(db, projectId, String(demote.id));

    const connect = createProposal(db, {
      projectId,
      proposalType: "connect_items",
      proposedChanges: {
        fromId: discovery.id,
        toId: purpose.id,
        type: "related_to",
        description: "Connect discovery to purpose"
      }
    });
    acceptProposal(db, projectId, String(connect.id));

    const update = createProposal(db, {
      projectId,
      proposalType: "update_item",
      proposedChanges: {
        table: "purpose_items",
        id: purpose.id,
        patch: { title: "Updated purpose" }
      }
    });
    acceptProposal(db, projectId, String(update.id));

    assert.equal(listPurposeItems(db, projectId).some((item) => item.title === "Updated purpose"), true);
    assert.equal(listDiscoveryItems(db, projectId).some((item) => item.title === "Demoted discovery"), true);
    assert.equal(listRelationships(db, projectId).length, 1);
    assert.equal(listLineageEvents(db, projectId).length, 4);
    db.close();
  });
});

test("stub chat turn stores operator and assistant messages and creates pending proposals", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Stub Test" });
    const projectId = String(project.id);

    const turn = createStubChatTurn(db, {
      projectId,
      content: "purpose: preserve both surfaces"
    });

    assert.equal(turn.operatorMessage.role, "operator");
    assert.equal(turn.assistantMessage.role, "assistant");
    assert.equal(turn.proposals.length, 1);
    assert.equal(turn.proposals[0].status, "pending");
    assert.equal(countByProject(db, "purpose_items", projectId), 0);
    assert.equal(countByProject(db, "lineage_events", projectId), 0);
    db.close();
  });
});
