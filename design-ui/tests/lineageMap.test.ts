import assert from "node:assert/strict";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { initializeDatabase } from "../server/db.ts";
import { createActiveContext, replaceActiveContext } from "../server/repositories/activeContexts.ts";
import { createDiscoveryItem } from "../server/repositories/discoveryItems.ts";
import { createLineageEvent, listLineagePlayback } from "../server/repositories/lineageEvents.ts";
import { getProject } from "../server/repositories/projects.ts";
import { createProject } from "../server/repositories/projects.ts";
import { createProposal } from "../server/repositories/proposals.ts";
import { createPurposeItem } from "../server/repositories/purposeItems.ts";
import { createRelationship } from "../server/repositories/relationships.ts";
import { buildDesignMap, contextForNode } from "../server/services/mapBuilder.ts";

function withDatabase(run: (dbPath: string) => void) {
  const dir = mkdtempSync(path.join(tmpdir(), "design-ui-lineage-map-test-"));
  try {
    run(path.join(dir, "test.sqlite"));
  } finally {
    rmSync(dir, { force: true, recursive: true });
  }
}

test("lineage playback returns chronological display shape with proposal and message links", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Lineage Shape Test" });
    const projectId = String(project.id);
    const proposal = createProposal(db, {
      projectId,
      proposalType: "create_discovery",
      proposedChanges: { title: "First" },
      sourceMessageIds: ["chat-1"]
    });

    createLineageEvent(db, {
      projectId,
      subjectId: "item-1",
      eventType: "created",
      afterValue: { title: "First" },
      messageIds: ["chat-1"],
      proposalId: String(proposal.id)
    });
    createLineageEvent(db, {
      projectId,
      subjectId: "item-1",
      eventType: "edited",
      beforeValue: { title: "First" },
      afterValue: { title: "Second" }
    });

    const events = listLineagePlayback(db, projectId, "item-1");
    assert.equal(events.length, 2);
    assert.equal(events[0].eventType, "created");
    assert.deepEqual(events[0].messageIds, ["chat-1"]);
    assert.equal(events[0].proposalId, proposal.id);
    assert.deepEqual(events[1].beforeValue, { title: "First" });
    db.close();
  });
});

test("design map renders node types, relationships, disconnected ideas, and maturity", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Map Test" });
    const projectId = String(project.id);
    const tension = createDiscoveryItem(db, {
      projectId,
      title: "Surface collapse tension",
      discoveryType: "tension",
      state: "noticed"
    });
    const question = createDiscoveryItem(db, {
      projectId,
      title: "Can the map remain nonlinear?",
      discoveryType: "question",
      state: "raw"
    });
    const purpose = createPurposeItem(db, {
      projectId,
      title: "Both surfaces remain visible",
      purposeType: "constraint",
      state: "purpose_candidate"
    });
    createRelationship(db, {
      projectId,
      fromId: String(tension.id),
      toId: String(purpose.id),
      type: "supports",
      description: "Tension supports constraint"
    });

    const map = buildDesignMap(db, projectId);
    const tensionNode = map.nodes.find((node) => node.id === tension.id);
    const purposeNode = map.nodes.find((node) => node.id === purpose.id);
    const disconnectedNode = map.nodes.find((node) => node.id === question.id);

    assert.equal(tensionNode?.nodeType, "tension");
    assert.equal(tensionNode?.connected, true);
    assert.equal(purposeNode?.nodeType, "purpose_region");
    assert.equal(disconnectedNode?.nodeType, "disconnected_idea");
    assert.equal(disconnectedNode?.maturity, "raw");
    assert.equal(map.edges.length, 1);
    db.close();
  });
});

test("map node selection creates active context for /design preloading", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Context Test" });
    const projectId = String(project.id);
    const discovery = createDiscoveryItem(db, {
      projectId,
      title: "Disconnected idea",
      discoveryType: "observation"
    });

    const contextInput = contextForNode(db, projectId, String(discovery.id));
    const context = replaceActiveContext(db, { projectId, ...contextInput });
    const storedProject = getProject(db, projectId);

    assert.deepEqual(context.discoveryItemIds, [discovery.id]);
    assert.equal(storedProject?.activeContextId, context.id);
    const map = buildDesignMap(db, projectId);
    assert.equal(map.activeContext?.id, context.id);
    db.close();
  });
});

test("active contexts normalize array fields for API consumers", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Context Shape Test" });
    const context = createActiveContext(db, {
      projectId: String(project.id),
      label: "Cluster",
      discoveryItemIds: ["d1"],
      purposeItemIds: ["p1"],
      conceptIds: ["c1"],
      relationshipIds: ["r1"]
    });

    assert.deepEqual(context.discoveryItemIds, ["d1"]);
    assert.deepEqual(context.purposeItemIds, ["p1"]);
    assert.deepEqual(context.conceptIds, ["c1"]);
    assert.deepEqual(context.relationshipIds, ["r1"]);
    db.close();
  });
});
