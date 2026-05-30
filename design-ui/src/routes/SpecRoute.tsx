import { useEffect, useMemo, useState } from "react";
import { createProject, createSpecExport, getSpecBuilder, listProjects } from "../api/client";
import type { SpecBuilderResponse, SpecSectionTitle, ValidationCheck } from "../types/design";

const sectionOrder: SpecSectionTitle[] = [
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
];

const checkLabels: Record<string, string> = {
  purposeClarity: "Purpose clarity",
  expectationClarity: "Expectation clarity",
  operationalIntentPreserved: "Operational intent",
  confusionRiskAddressed: "Confusion risk",
  examplesAdequate: "Examples",
  boundariesPresent: "Boundaries",
  residualJudgmentsPresent: "Residual judgments",
  downstreamRediscoveryRisk: "Downstream rediscovery risk"
};

function ValidationRow({ name, check }: { name: string; check: ValidationCheck }) {
  return (
    <li className={`validation-row validation-${check.status}`}>
      <strong>{checkLabels[name] ?? name}</strong>
      <span>{check.status}</span>
      <p>{check.message}</p>
      {check.relatedItemIds.length > 0 ? <small>Related: {check.relatedItemIds.join(", ")}</small> : null}
    </li>
  );
}

export function SpecRoute() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [builder, setBuilder] = useState<SpecBuilderResponse | null>(null);
  const [format, setFormat] = useState<"markdown" | "json">("markdown");
  const [exportStatus, setExportStatus] = useState("");

  const loadBuilder = async (id: string) => {
    setBuilder(await getSpecBuilder(id));
  };

  useEffect(() => {
    let cancelled = false;
    async function initialize() {
      const projects = await listProjects();
      const project = projects[0] ?? (await createProject("Design UI v1"));
      if (cancelled) return;
      setProjectId(project.id);
      await loadBuilder(project.id);
    }
    void initialize();
    return () => {
      cancelled = true;
    };
  }, []);

  const preview = useMemo(() => {
    if (!builder) return "";
    return format === "markdown" ? builder.markdown : builder.json;
  }, [builder, format]);

  const exportCurrent = async () => {
    if (!projectId) return;
    const result = await createSpecExport(projectId, format);
    setExportStatus(`Exported ${result.export.format} at ${result.export.createdAt}`);
    await loadBuilder(projectId);
  };

  return (
    <section className="spec-workspace">
      <header className="spec-header">
        <div>
          <h2>Design Specification Builder</h2>
          <p>Compiled from committed Purpose state with Discovery only as lineage or context reference.</p>
        </div>
        <div className="spec-actions">
          <select value={format} onChange={(event) => setFormat(event.target.value as "markdown" | "json")}>
            <option value="markdown">Markdown</option>
            <option value="json">JSON</option>
          </select>
          <button type="button" onClick={() => void exportCurrent()}>
            Export
          </button>
        </div>
      </header>

      {exportStatus ? <p className="export-status">{exportStatus}</p> : null}

      <div className="spec-layout">
        <section className="spec-preview" data-testid="spec-preview">
          <h3>Preview</h3>
          <pre>{preview || "No specification content yet."}</pre>
        </section>

        <aside className="validation-panel" data-testid="spec-validation">
          <h3>Validation</h3>
          {builder ? (
            <>
              <p className={builder.validation.passed ? "validation-pass" : "validation-warning"}>
                {builder.validation.passed ? "All checks pass." : "Warnings or failures need operator review."}
              </p>
              <ol>
                {Object.entries(builder.validation.checks).map(([name, check]) => (
                  <ValidationRow check={check} key={name} name={name} />
                ))}
              </ol>
            </>
          ) : (
            <p className="muted">Loading validation.</p>
          )}
        </aside>
      </div>

      <section className="spec-section-grid" data-testid="spec-sections">
        {builder
          ? sectionOrder.map((title) => (
              <article className="spec-section-card" key={title}>
                <h3>{title}</h3>
                {(builder.spec.sections[title] ?? []).length === 0 ? <p className="muted">No committed content.</p> : null}
                <ul>
                  {(builder.spec.sections[title] ?? []).map((entry) => (
                    <li key={entry}>{entry}</li>
                  ))}
                </ul>
              </article>
            ))
          : null}
      </section>

      <section className="export-list">
        <h3>Persisted Exports</h3>
        {builder?.exports.length === 0 ? <p className="muted">No exports persisted yet.</p> : null}
        {builder?.exports.map((item) => (
          <article className="export-card" key={item.id}>
            <strong>{item.format}</strong>
            <span>{item.createdAt}</span>
            <small>
              Purpose items: {item.sourcePurposeItemIds.length}; lineage references: {item.sourceLineageEventIds.length}
            </small>
          </article>
        ))}
      </section>
    </section>
  );
}
