import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { initializeDatabase } from "../server/db.ts";
import { countByProject } from "../server/repositories/base.ts";
import { createChatMessage, listChatMessages } from "../server/repositories/chatMessages.ts";
import {
  createDiscoveryItem,
  listDiscoveryItems
} from "../server/repositories/discoveryItems.ts";
import { createLineageEvent, listLineageEvents } from "../server/repositories/lineageEvents.ts";
import { createProject, getProject } from "../server/repositories/projects.ts";
import {
  deleteProjectScopedRecord,
  getProjectScopedRecord,
  updateProjectScopedRecord
} from "../server/repositories/projectScopedCrud.ts";
import { createProposal, listProposals } from "../server/repositories/proposals.ts";
import { createPurposeItem, listPurposeItems } from "../server/repositories/purposeItems.ts";

function withDatabase(run: (dbPath: string) => void) {
  const dir = mkdtempSync(path.join(tmpdir(), "design-ui-test-"));
  try {
    run(path.join(dir, "test.sqlite"));
  } finally {
    rmSync(dir, { force: true, recursive: true });
  }
}

test("database initializes and creates core tables", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const tableRows = db
      .prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
      .all();
    const tableNames = new Set(tableRows.map((row) => String(row.name)));

    for (const table of [
      "projects",
      "chat_messages",
      "discovery_items",
      "purpose_items",
      "concepts",
      "relationships",
      "proposals",
      "lineage_events",
      "active_contexts",
      "spec_exports"
    ]) {
      assert.equal(tableNames.has(table), true, `${table} table should exist`);
    }
    db.close();
  });
});

test("project can be created and read", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Design UI v1" });
    const stored = getProject(db, String(project.id));

    assert.equal(stored?.title, "Design UI v1");
    assert.equal(typeof stored?.createdAt, "string");
    assert.equal(typeof stored?.updatedAt, "string");
    db.close();
  });
});

test("chat message can be stored for a project", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Chat Test" });

    createChatMessage(db, {
      projectId: String(project.id),
      role: "operator",
      content: "What is becoming purpose-oriented here?"
    });

    const messages = listChatMessages(db, String(project.id));
    assert.equal(messages.length, 1);
    assert.equal(messages[0].projectId, project.id);
    assert.equal(messages[0].role, "operator");
    db.close();
  });
});

test("discovery and purpose items can be stored for a project", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Item Test" });

    createDiscoveryItem(db, {
      projectId: String(project.id),
      title: "Surface split tension",
      discoveryType: "tension"
    });
    createPurposeItem(db, {
      projectId: String(project.id),
      title: "Both surfaces remain visible",
      purposeType: "constraint"
    });

    const discoveryItems = listDiscoveryItems(db, String(project.id));
    const purposeItems = listPurposeItems(db, String(project.id));

    assert.equal(discoveryItems.length, 1);
    assert.equal(discoveryItems[0].projectId, project.id);
    assert.equal(purposeItems.length, 1);
    assert.equal(purposeItems[0].projectId, project.id);
    db.close();
  });
});

test("proposal storage does not mutate committed design state", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Proposal Boundary Test" });
    const projectId = String(project.id);

    const beforeDiscovery = countByProject(db, "discovery_items", projectId);
    const beforePurpose = countByProject(db, "purpose_items", projectId);
    const beforeConcepts = countByProject(db, "concepts", projectId);
    const beforeRelationships = countByProject(db, "relationships", projectId);
    const beforeLineage = countByProject(db, "lineage_events", projectId);

    createProposal(db, {
      projectId,
      proposalType: "create_discovery",
      rationale: "Question detected in chat",
      proposedChanges: {
        title: "Is this a map or a document tree?",
        discoveryType: "question"
      }
    });

    assert.equal(countByProject(db, "discovery_items", projectId), beforeDiscovery);
    assert.equal(countByProject(db, "purpose_items", projectId), beforePurpose);
    assert.equal(countByProject(db, "concepts", projectId), beforeConcepts);
    assert.equal(countByProject(db, "relationships", projectId), beforeRelationships);
    assert.equal(countByProject(db, "lineage_events", projectId), beforeLineage);

    const proposals = listProposals(db, projectId);
    assert.equal(proposals.length, 1);
    assert.equal(proposals[0].status, "pending");
    db.close();
  });
});

test("lineage event can be stored directly for foundation tests", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Lineage Test" });

    createLineageEvent(db, {
      projectId: String(project.id),
      subjectId: "discovery_example",
      eventType: "created",
      afterValue: { title: "Example" }
    });

    const events = listLineageEvents(db, String(project.id));
    assert.equal(events.length, 1);
    assert.equal(events[0].projectId, project.id);
    assert.equal(events[0].eventType, "created");
    db.close();
  });
});

test("project-scoped CRUD helper reads, updates, and deletes within project boundary", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "CRUD Test" });
    const otherProject = createProject(db, { title: "Other Project" });
    const item = createDiscoveryItem(db, {
      projectId: String(project.id),
      title: "Initial",
      discoveryType: "observation"
    });

    const inaccessible = getProjectScopedRecord(
      db,
      "discovery_items",
      String(otherProject.id),
      String(item.id)
    );
    assert.equal(inaccessible, undefined);

    const updated = updateProjectScopedRecord(
      db,
      "discovery_items",
      String(project.id),
      String(item.id),
      { title: "Updated" }
    );
    assert.equal(updated?.title, "Updated");

    const deletedFromWrongProject = deleteProjectScopedRecord(
      db,
      "discovery_items",
      String(otherProject.id),
      String(item.id)
    );
    assert.equal(deletedFromWrongProject, false);

    const deleted = deleteProjectScopedRecord(
      db,
      "discovery_items",
      String(project.id),
      String(item.id)
    );
    assert.equal(deleted, true);
    assert.equal(listDiscoveryItems(db, String(project.id)).length, 0);
    db.close();
  });
});
