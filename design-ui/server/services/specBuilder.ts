import type { DesignDatabase } from "../db.ts";
import { listDiscoveryItems } from "../repositories/discoveryItems.ts";
import { listLineagePlayback } from "../repositories/lineageEvents.ts";
import { getProject } from "../repositories/projects.ts";
import { listPurposeItems } from "../repositories/purposeItems.ts";
import { listRelationships } from "../repositories/relationships.ts";
import { createSpecExport } from "../repositories/specExports.ts";

export const specSectionTitles = [
  "Purpose",
  "Core concept summary",
  "Relevant discovered structure",
  "Principles",
  "Operational intent",
  "Expectations",
  "Boundaries",
  "Constraints",
  "Key relationships",
  "Tensions",
  "Residual judgments",
  "Positive exemplars",
  "Negative exemplars",
  "Distinguishing properties",
  "Supporting lineage references",
  "Notes for Specification"
] as const;

export type SpecSectionTitle = (typeof specSectionTitles)[number];

export type DesignSpecification = {
  projectId: string;
  title: string;
  sections: Record<SpecSectionTitle, string[]>;
  sourcePurposeItemIds: string[];
  sourceLineageEventIds: string[];
  relationshipReferences: Array<{ id: string; fromId: string; toId: string; type: string; description: string }>;
  discoveryReferences: Array<{ id: string; title: string; discoveryType: string; state: string }>;
};

function text(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function lineForPurpose(item: Record<string, unknown>) {
  const body = text(item.body);
  return body ? `${text(item.title)}: ${body}` : text(item.title);
}

function emptySections(): Record<SpecSectionTitle, string[]> {
  const sections = {} as Record<SpecSectionTitle, string[]>;
  for (const title of specSectionTitles) {
    sections[title] = [];
  }
  return sections;
}

export function buildDesignSpecification(db: DesignDatabase, projectId: string): DesignSpecification {
  const project = getProject(db, projectId) as Record<string, unknown> | undefined;
  const purposeItems = listPurposeItems(db, projectId) as Array<Record<string, unknown>>;
  const discoveryItems = listDiscoveryItems(db, projectId) as Array<Record<string, unknown>>;
  const relationships = listRelationships(db, projectId) as Array<Record<string, unknown>>;
  const lineage = listLineagePlayback(db, projectId);
  const sections = emptySections();

  for (const item of purposeItems) {
    const purposeType = text(item.purposeType, "purpose_candidate");
    const line = lineForPurpose(item);
    if (!line) continue;

    if (purposeType === "purpose_candidate") sections.Purpose.push(line);
    else if (purposeType === "principle_candidate") sections.Principles.push(line);
    else if (purposeType === "operational_intent") sections["Operational intent"].push(line);
    else if (purposeType === "expectation") sections.Expectations.push(line);
    else if (purposeType === "boundary") sections.Boundaries.push(line);
    else if (purposeType === "constraint") sections.Constraints.push(line);
    else if (purposeType === "residual_judgment") sections["Residual judgments"].push(line);
    else if (purposeType === "positive_exemplar") sections["Positive exemplars"].push(line);
    else if (purposeType === "negative_exemplar") sections["Negative exemplars"].push(line);
    else if (purposeType === "distinguishing_property") sections["Distinguishing properties"].push(line);
    else if (purposeType === "design_decision") sections["Notes for Specification"].push(line);
    else sections["Core concept summary"].push(line);
  }

  sections["Core concept summary"].push(
    ...purposeItems
      .filter((item) => text(item.purposeType) === "spec_relevant_understanding")
      .map(lineForPurpose)
      .filter(Boolean)
  );

  sections["Relevant discovered structure"].push(
    ...discoveryItems.map((item) => {
      const label = text(item.title);
      return `Discovery reference only: ${label} (${text(item.discoveryType)}, ${text(item.state)})`;
    })
  );

  sections["Key relationships"].push(
    ...relationships.map((relationship) => {
      const description = text(relationship.description);
      const core = `${text(relationship.fromId)} ${text(relationship.type)} ${text(relationship.toId)}`;
      return description ? `${core}: ${description}` : core;
    })
  );

  sections.Tensions.push(
    ...discoveryItems
      .filter((item) => text(item.discoveryType) === "tension")
      .map((item) => `Discovery reference only: ${text(item.title)} (${text(item.state)})`)
  );

  sections["Supporting lineage references"].push(
    ...lineage.map((event) => {
      const proposal = event.proposalId ? `; proposal ${event.proposalId}` : "";
      const messages = event.messageIds.length > 0 ? `; messages ${event.messageIds.join(", ")}` : "";
      return `${event.eventType} ${event.subjectId} at ${event.createdAt}${proposal}${messages}`;
    })
  );

  sections["Notes for Specification"].push(
    "This export is compiled from committed Purpose state. Discovery content is included only as lineage or context reference."
  );

  return {
    projectId,
    title: text(project?.title, "Design Specification"),
    sections,
    sourcePurposeItemIds: purposeItems.map((item) => text(item.id)),
    sourceLineageEventIds: lineage.map((event) => event.id),
    relationshipReferences: relationships.map((relationship) => ({
      id: text(relationship.id),
      fromId: text(relationship.fromId),
      toId: text(relationship.toId),
      type: text(relationship.type),
      description: text(relationship.description)
    })),
    discoveryReferences: discoveryItems.map((item) => ({
      id: text(item.id),
      title: text(item.title),
      discoveryType: text(item.discoveryType),
      state: text(item.state)
    }))
  };
}

export function renderMarkdownSpec(spec: DesignSpecification) {
  const lines = [`# ${spec.title}`, ""];
  for (const title of specSectionTitles) {
    lines.push(`## ${title}`);
    const content = spec.sections[title];
    if (content.length === 0) {
      lines.push("_No committed content yet._");
    } else {
      lines.push(...content.map((entry) => `- ${entry}`));
    }
    lines.push("");
  }
  return lines.join("\n");
}

export function renderJsonSpec(spec: DesignSpecification) {
  return JSON.stringify(spec, null, 2);
}

export function persistSpecExport(
  db: DesignDatabase,
  projectId: string,
  format: "markdown" | "json"
) {
  const spec = buildDesignSpecification(db, projectId);
  const content = format === "markdown" ? renderMarkdownSpec(spec) : renderJsonSpec(spec);
  return createSpecExport(db, {
    projectId,
    format,
    content,
    sourcePurposeItemIds: spec.sourcePurposeItemIds,
    sourceLineageEventIds: spec.sourceLineageEventIds
  });
}
