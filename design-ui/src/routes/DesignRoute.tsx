import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  acceptProposal,
  createItem,
  createProject,
  createProposal,
  getDesignMap,
  listChatMessages,
  listItems,
  listLineageEvents,
  listProjects,
  listProposals,
  rejectProposal,
  sendChatMessage,
  updateItem
} from "../api/client";
import type {
  ActiveContext,
  ChatMessage,
  DesignProposal,
  DiscoveryItem,
  LineageEvent,
  PurposeItem
} from "../types/design";

type Focus = "discovery" | "purpose";

type ItemDraft = {
  title: string;
  body: string;
};

const emptyDraft: ItemDraft = { title: "", body: "" };

function proposalChange(proposal: DesignProposal) {
  return proposal.proposedChanges && typeof proposal.proposedChanges === "object"
    ? (proposal.proposedChanges as Record<string, unknown>)
    : {};
}

function proposalTitle(proposal: DesignProposal) {
  const changes = proposalChange(proposal);
  return typeof changes.title === "string" ? changes.title : proposal.proposalType;
}

function ProposalPreviewPanel({
  proposals,
  onAccept,
  onReject
}: {
  proposals: DesignProposal[];
  onAccept: (proposalId: string) => Promise<void>;
  onReject: (proposalId: string) => Promise<void>;
}) {
  const pending = proposals.filter((proposal) => proposal.status === "pending");
  return (
    <aside className="proposal-panel">
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

function DiscoverySurface({
  items,
  draft,
  setDraft,
  onCreate,
  onEdit,
  onShowLineage,
  onPromote
}: {
  items: DiscoveryItem[];
  draft: ItemDraft;
  setDraft: (draft: ItemDraft) => void;
  onCreate: () => Promise<void>;
  onEdit: (item: DiscoveryItem) => Promise<void>;
  onShowLineage: (item: DiscoveryItem) => Promise<void>;
  onPromote: (item: DiscoveryItem) => Promise<void>;
}) {
  return (
    <section className="design-surface" data-testid="discovery-surface">
      <h2>Discovery</h2>
      <form
        className="item-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onCreate();
        }}
      >
        <input
          aria-label="Discovery title"
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          placeholder="Observation, question, anomaly..."
          value={draft.title}
        />
        <textarea
          aria-label="Discovery body"
          onChange={(event) => setDraft({ ...draft, body: event.target.value })}
          placeholder="Discovery notes"
          value={draft.body}
        />
        <button type="submit">Add Discovery</button>
      </form>
      <div className="item-list">
        {items.map((item) => (
          <article className="item-card" key={item.id}>
            <input
              aria-label={`Edit discovery ${item.id}`}
              defaultValue={item.title}
              onBlur={(event) => void onEdit({ ...item, title: event.target.value })}
            />
            <p>{item.body || item.discoveryType}</p>
            <div className="item-actions">
              <span>{item.state}</span>
              <button type="button" onClick={() => void onShowLineage(item)}>
                Lineage
              </button>
              <button type="button" onClick={() => void onPromote(item)}>
                Promote
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function PurposeSurface({
  items,
  draft,
  setDraft,
  onCreate,
  onEdit,
  onShowLineage,
  onDemote
}: {
  items: PurposeItem[];
  draft: ItemDraft;
  setDraft: (draft: ItemDraft) => void;
  onCreate: () => Promise<void>;
  onEdit: (item: PurposeItem) => Promise<void>;
  onShowLineage: (item: PurposeItem) => Promise<void>;
  onDemote: (item: PurposeItem) => Promise<void>;
}) {
  return (
    <section className="design-surface" data-testid="purpose-surface">
      <h2>Purpose</h2>
      <form
        className="item-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onCreate();
        }}
      >
        <input
          aria-label="Purpose title"
          onChange={(event) => setDraft({ ...draft, title: event.target.value })}
          placeholder="Purpose candidate, constraint, boundary..."
          value={draft.title}
        />
        <textarea
          aria-label="Purpose body"
          onChange={(event) => setDraft({ ...draft, body: event.target.value })}
          placeholder="Purpose notes"
          value={draft.body}
        />
        <button type="submit">Add Purpose</button>
      </form>
      <div className="item-list">
        {items.map((item) => (
          <article className="item-card" key={item.id}>
            <input
              aria-label={`Edit purpose ${item.id}`}
              defaultValue={item.title}
              onBlur={(event) => void onEdit({ ...item, title: event.target.value })}
            />
            <p>{item.body || item.purposeType}</p>
            <div className="item-actions">
              <span>{item.state}</span>
              <button type="button" onClick={() => void onShowLineage(item)}>
                Lineage
              </button>
              <button type="button" onClick={() => void onDemote(item)}>
                Demote
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export function DesignRoute() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [focus, setFocus] = useState<Focus>("discovery");
  const [discoveryItems, setDiscoveryItems] = useState<DiscoveryItem[]>([]);
  const [purposeItems, setPurposeItems] = useState<PurposeItem[]>([]);
  const [proposals, setProposals] = useState<DesignProposal[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [activeContext, setActiveContext] = useState<ActiveContext | null>(null);
  const [selectedLineageLabel, setSelectedLineageLabel] = useState("Project Playback");
  const [lineageEvents, setLineageEvents] = useState<LineageEvent[]>([]);
  const [discoveryDraft, setDiscoveryDraft] = useState(emptyDraft);
  const [purposeDraft, setPurposeDraft] = useState(emptyDraft);
  const [chatDraft, setChatDraft] = useState("");

  const loadProjectData = async (id: string) => {
    const [discovery, purpose, proposalRows, chatRows, lineageRows, map] = await Promise.all([
      listItems(id, "discovery"),
      listItems(id, "purpose"),
      listProposals(id),
      listChatMessages(id),
      listLineageEvents(id),
      getDesignMap(id)
    ]);
    const context = map.activeContext;
    setActiveContext(context);
    setDiscoveryItems(
      context && context.discoveryItemIds.length > 0
        ? discovery.filter((item) => context.discoveryItemIds.includes(item.id))
        : discovery
    );
    setPurposeItems(
      context && context.purposeItemIds.length > 0
        ? purpose.filter((item) => context.purposeItemIds.includes(item.id))
        : purpose
    );
    setProposals(proposalRows);
    setMessages(chatRows);
    setLineageEvents(lineageRows.events);
  };

  useEffect(() => {
    let cancelled = false;
    async function initialize() {
      const projects = await listProjects();
      const project = projects[0] ?? (await createProject("Design UI v1"));
      if (cancelled) return;
      setProjectId(project.id);
      await loadProjectData(project.id);
    }
    void initialize();
    return () => {
      cancelled = true;
    };
  }, []);

  const pendingCount = useMemo(
    () => proposals.filter((proposal) => proposal.status === "pending").length,
    [proposals]
  );

  const refresh = async () => {
    if (projectId) await loadProjectData(projectId);
  };

  const createManualItem = async (kind: "discovery" | "purpose") => {
    if (!projectId) return;
    const draft = kind === "discovery" ? discoveryDraft : purposeDraft;
    if (!draft.title.trim()) return;
    await createItem(projectId, kind, {
      title: draft.title,
      body: draft.body,
      discoveryType: "observation",
      purposeType: "purpose_candidate"
    });
    if (kind === "discovery") setDiscoveryDraft(emptyDraft);
    else setPurposeDraft(emptyDraft);
    await refresh();
  };

  const submitChat = async (event: FormEvent) => {
    event.preventDefault();
    if (!projectId || !chatDraft.trim()) return;
    await sendChatMessage(projectId, chatDraft);
    setChatDraft("");
    await refresh();
  };

  const accept = async (proposalId: string) => {
    if (!projectId) return;
    await acceptProposal(projectId, proposalId);
    await refresh();
  };

  const reject = async (proposalId: string) => {
    if (!projectId) return;
    await rejectProposal(projectId, proposalId);
    await refresh();
  };

  const proposePromotion = async (item: DiscoveryItem) => {
    if (!projectId) return;
    await createProposal(projectId, {
      proposalType: "promote_to_purpose",
      rationale: "Manual promotion requested from Discovery.",
      proposedChanges: {
        sourceId: item.id,
        title: item.title,
        body: item.body,
        purposeType: "purpose_candidate"
      }
    });
    await refresh();
  };

  const proposeDemotion = async (item: PurposeItem) => {
    if (!projectId) return;
    await createProposal(projectId, {
      proposalType: "demote_to_discovery",
      rationale: "Manual demotion requested from Purpose.",
      proposedChanges: {
        sourceId: item.id,
        title: item.title,
        body: item.body,
        discoveryType: "observation"
      }
    });
    await refresh();
  };

  const showLineage = async (item: DiscoveryItem | PurposeItem) => {
    if (!projectId) return;
    const lineage = await listLineageEvents(projectId, item.id);
    setSelectedLineageLabel(item.title);
    setLineageEvents(lineage.events);
  };

  return (
    <section className="design-workspace">
      <div className="focus-bar" role="group" aria-label="Surface focus">
        <button
          className={focus === "discovery" ? "active" : ""}
          onClick={() => setFocus("discovery")}
          type="button"
        >
          Discovery Focus
        </button>
        <button
          className={focus === "purpose" ? "active" : ""}
          onClick={() => setFocus("purpose")}
          type="button"
        >
          Purpose Focus
        </button>
        <span>{pendingCount} pending</span>
        {activeContext ? <span>Context: {activeContext.label}</span> : null}
      </div>

      <div className={`surface-layout focus-${focus}`}>
        <DiscoverySurface
          draft={discoveryDraft}
          items={discoveryItems}
          onCreate={() => createManualItem("discovery")}
          onEdit={(item) =>
            projectId
              ? updateItem(projectId, "discovery", item.id, { title: item.title }).then(refresh)
              : Promise.resolve()
          }
          onPromote={proposePromotion}
          onShowLineage={showLineage}
          setDraft={setDiscoveryDraft}
        />
        <PurposeSurface
          draft={purposeDraft}
          items={purposeItems}
          onCreate={() => createManualItem("purpose")}
          onDemote={proposeDemotion}
          onEdit={(item) =>
            projectId
              ? updateItem(projectId, "purpose", item.id, { title: item.title }).then(refresh)
              : Promise.resolve()
          }
          onShowLineage={showLineage}
          setDraft={setPurposeDraft}
        />
      </div>

      <div className="design-bottom">
        <section className="chat-panel">
          <h2>Chat</h2>
          <div className="message-list">
            {messages.map((message) => (
              <p className={`message message-${message.role}`} key={message.id}>
                <b>{message.role}</b> {message.content}
              </p>
            ))}
          </div>
          <form className="chat-form" onSubmit={submitChat}>
            <textarea
              aria-label="Chat message"
              onChange={(event) => setChatDraft(event.target.value)}
              placeholder="Ask a question, or try purpose:, constraint:, boundary:, connect X to Y"
              value={chatDraft}
            />
            <button type="submit">Send</button>
          </form>
        </section>
        <ProposalPreviewPanel proposals={proposals} onAccept={accept} onReject={reject} />
        <aside className="lineage-panel" data-testid="lineage-panel">
          <h3>{selectedLineageLabel}</h3>
          {lineageEvents.length === 0 ? <p className="muted">No lineage events yet.</p> : null}
          <ol className="lineage-list">
            {lineageEvents.map((event) => (
              <li key={event.id}>
                <b>{event.eventType}</b>
                <span>{event.subjectId}</span>
                <small>
                  {event.createdAt}
                  {event.proposalId ? ` · proposal ${event.proposalId}` : ""}
                  {event.messageIds.length > 0 ? ` · messages ${event.messageIds.join(", ")}` : ""}
                </small>
              </li>
            ))}
          </ol>
        </aside>
      </div>
    </section>
  );
}
