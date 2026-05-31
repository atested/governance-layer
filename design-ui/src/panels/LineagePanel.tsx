import type { LineageEvent } from "../types/design";

export type LineagePanelProps = {
  label: string;
  events: LineageEvent[];
};

export function LineagePanel({ label, events }: LineagePanelProps) {
  return (
    <aside className="workspace-panel lineage-panel" data-testid="lineage-panel">
      <p className="lineage-context">{label}</p>
      {events.length === 0 ? <p className="muted">No lineage events yet.</p> : null}
      <ol className="lineage-list">
        {events.map((event) => (
          <li key={event.id}>
            <b>{event.eventType}</b>
            <span>{event.subjectId}</span>
            <small>
              {event.createdAt}
              {event.proposalId ? (
                <>
                  {" "}
                  &middot; proposal {event.proposalId}
                </>
              ) : null}
              {event.messageIds.length > 0 ? (
                <>
                  {" "}
                  &middot; messages {event.messageIds.join(", ")}
                </>
              ) : null}
            </small>
          </li>
        ))}
      </ol>
    </aside>
  );
}
