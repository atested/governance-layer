import assert from "node:assert/strict";
import { mkdtempSync, rmSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import test from "node:test";
import { initializeDatabase } from "../server/db.ts";
import { createDiscoveryItem } from "../server/repositories/discoveryItems.ts";
import { createLineageEvent } from "../server/repositories/lineageEvents.ts";
import { createProject } from "../server/repositories/projects.ts";
import { createPurposeItem } from "../server/repositories/purposeItems.ts";
import { createRelationship } from "../server/repositories/relationships.ts";
import { listSpecExports } from "../server/repositories/specExports.ts";
import {
  buildDesignSpecification,
  persistSpecExport,
  renderJsonSpec,
  renderMarkdownSpec,
  specSectionTitles
} from "../server/services/specBuilder.ts";
import { validateDesignSpecification } from "../server/services/specValidator.ts";

function withDatabase(run: (dbPath: string) => void) {
  const dir = mkdtempSync(path.join(tmpdir(), "design-ui-spec-test-"));
  try {
    run(path.join(dir, "test.sqlite"));
  } finally {
    rmSync(dir, { force: true, recursive: true });
  }
}

test("spec builder exports required sections from committed purpose state", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Spec Test" });
    const projectId = String(project.id);
    const purpose = createPurposeItem(db, {
      projectId,
      title: "Purpose is stabilized meaning",
      purposeType: "purpose_candidate"
    });
    createPurposeItem(db, {
      projectId,
      title: "Surfaces must remain visible",
      purposeType: "boundary"
    });
    createPurposeItem(db, {
      projectId,
      title: "The map is not a folder tree",
      purposeType: "negative_exemplar"
    });
    const discovery = createDiscoveryItem(db, {
      projectId,
      title: "Could collapse into note taking",
      discoveryType: "tension"
    });
    createRelationship(db, {
      projectId,
      fromId: String(discovery.id),
      toId: String(purpose.id),
      type: "supports",
      description: "Discovery tension supports purpose."
    });
    createLineageEvent(db, {
      projectId,
      subjectId: String(purpose.id),
      eventType: "created",
      afterValue: purpose
    });

    const spec = buildDesignSpecification(db, projectId);
    const markdown = renderMarkdownSpec(spec);
    const json = JSON.parse(renderJsonSpec(spec));

    for (const title of specSectionTitles) {
      assert.match(markdown, new RegExp(`## ${title}`));
    }
    assert.match(markdown, /Purpose is stabilized meaning/);
    assert.match(markdown, /Key relationships/);
    assert.match(markdown, /Supporting lineage references/);
    assert.equal(json.sourcePurposeItemIds.includes(purpose.id), true);
    assert.equal(spec.discoveryReferences.length, 1);
    assert.equal(spec.sections.Purpose.some((entry) => entry.includes("Could collapse")), false);
    assert.match(
      spec.sections["Relevant discovered structure"][0],
      /^Discovery reference only: Could collapse into note taking/
    );
    db.close();
  });
});

test("spec exports persist markdown and json records with source references", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Persist Export Test" });
    const projectId = String(project.id);
    const purpose = createPurposeItem(db, {
      projectId,
      title: "Committed purpose",
      purposeType: "purpose_candidate"
    });
    createLineageEvent(db, {
      projectId,
      subjectId: String(purpose.id),
      eventType: "created",
      afterValue: purpose
    });

    const markdownExport = persistSpecExport(db, projectId, "markdown");
    const jsonExport = persistSpecExport(db, projectId, "json");
    const exports = listSpecExports(db, projectId);

    assert.equal(markdownExport.format, "markdown");
    assert.equal(jsonExport.format, "json");
    assert.equal(exports.length, 2);
    assert.equal(exports[0].sourcePurposeItemIds.includes(purpose.id), true);
    assert.equal(exports[0].sourceLineageEventIds.length, 1);
    db.close();
  });
});

test("validation reports missing purpose, boundaries, examples, and confusion risk", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Validation Missing Test" });
    const result = validateDesignSpecification(db, String(project.id));

    assert.equal(result.passed, false);
    assert.equal(result.checks.purposeClarity.status, "fail");
    assert.equal(result.checks.boundariesPresent.status, "fail");
    assert.equal(result.checks.examplesAdequate.status, "warning");
    assert.equal(result.checks.confusionRiskAddressed.status, "warning");
    db.close();
  });
});

test("validation can pass when handoff quality signals are present", () => {
  withDatabase((dbPath) => {
    const db = initializeDatabase(dbPath);
    const project = createProject(db, { title: "Validation Pass Test" });
    const projectId = String(project.id);
    for (const [title, purposeType] of [
      ["Purpose exists", "purpose_candidate"],
      ["Expectation exists", "expectation"],
      ["Operational intent exists", "operational_intent"],
      ["Boundary exists", "boundary"],
      ["Positive example exists", "positive_exemplar"],
      ["Negative example exists", "negative_exemplar"],
      ["Residual judgment exists", "residual_judgment"],
      ["Distinguishing property exists", "distinguishing_property"]
    ]) {
      createPurposeItem(db, { projectId, title, purposeType });
    }

    const result = validateDesignSpecification(db, projectId);
    assert.equal(result.passed, true);
    assert.equal(Object.values(result.checks).every((check) => check.status === "pass"), true);
    db.close();
  });
});

test("/spec route renders builder, validation, export, and required sections", () => {
  const routeSource = readFileSync(new URL("../src/routes/SpecRoute.tsx", import.meta.url), "utf8");
  assert.match(routeSource, /data-testid="spec-preview"/);
  assert.match(routeSource, /data-testid="spec-validation"/);
  assert.match(routeSource, /createSpecExport/);
  assert.match(routeSource, /Purpose/);
  assert.match(routeSource, /Supporting lineage references/);
  assert.match(routeSource, /Validation/);
});
