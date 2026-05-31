import type { DesignProposal } from "../types/design";

export type ProposalsPanelProps = {
  proposals: DesignProposal[];
  onAccept: (proposalId: string) => Promise<void>;
  onReject: (proposalId: string) => Promise<void>;
};

function proposalChange(proposal: DesignProposal) {
  return proposal.proposedChanges && typeof proposal.proposedChanges === "object"
    ? (proposal.proposedChanges as Record<string, unknown>)
    : {};
}

function proposalTitle(proposal: DesignProposal) {
  const changes = proposalChange(proposal);
  return typeof changes.title === "string" ? changes.title : proposal.proposalType;
}

export function ProposalsPanel({
  proposals,
  onAccept,
  onReject
}: ProposalsPanelProps) {
  const pending = proposals.filter((proposal) => proposal.status === "pending");
  return (
    <aside className="proposal-panel" data-testid="proposals-panel">
      <h3>Pending Proposals</h3>
      {pending.length === 0 ? <p className="muted">No pending proposals.</p> : null}
      {pending.map((proposal) => (
        <article className="proposal-card" key={proposal.id}>
          <div className="proposal-card-header">
            <strong>{proposalTitle(proposal)}</strong>
            <span>{proposal.proposalType}</span>
          </div>
          <p>{proposal.rationale || "Manual proposal"}</p>
          <div className="preview-grid">
            <div>
              <b>Creates</b>
              {(proposal.preview?.creates ?? []).map((item) => (
                <span key={`${proposal.id}-create-${item.table}-${item.title}`}>
                  {item.table}: {item.title}
                </span>
              ))}
            </div>
            <div>
              <b>Changes</b>
              {(proposal.preview?.changes ?? []).map((item) => (
                <span key={`${proposal.id}-change-${item.table}-${item.id}`}>
                  {item.table}: {item.id} [{item.fields.join(", ")}]
                </span>
              ))}
            </div>
            <div>
              <b>Lineage</b>
              {(proposal.preview?.lineageEvents ?? []).map((event) => (
                <span key={`${proposal.id}-lineage-${event.eventType}-${event.subjectId}`}>
                  {event.eventType}: {event.subjectId}
                </span>
              ))}
            </div>
          </div>
          <div className="proposal-actions">
            <button type="button" onClick={() => void onAccept(proposal.id)}>
              Accept
            </button>
            <button type="button" onClick={() => void onReject(proposal.id)}>
              Reject
            </button>
          </div>
        </article>
      ))}
    </aside>
  );
}
