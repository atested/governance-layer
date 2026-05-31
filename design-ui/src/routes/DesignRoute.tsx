// DESIGN-UI-011: split FormEvent into an explicit type-only import.
// FormEvent is exported by react only as a type (.d.ts), not as a
// runtime value. Importing it in the same `import { ... }` line as
// value hooks works under esbuild's auto-detection but can fail Vite
// 7's stricter import rewriting and leave the entry module 500'ing.
// Marking it `import type` removes the ambiguity for every transformer
// in the pipeline.
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
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
import { ChatPanel } from "../panels/ChatPanel";
import { DiscoveryPanel } from "../panels/DiscoveryPanel";
import { LineagePanel } from "../panels/LineagePanel";
import { ProposalsPanel } from "../panels/ProposalsPanel";
import { PurposePanel } from "../panels/PurposePanel";
import { emptyDraft } from "../panels/types";
import type {
  ActiveContext,
  ChatMessage,
  DesignProposal,
  DiscoveryItem,
  LineageEvent,
  PurposeItem
} from "../types/design";

type Focus = "discovery" | "purpose";

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
      context ? discovery.filter((item) => context.discoveryItemIds.includes(item.id)) : discovery
    );
    setPurposeItems(context ? purpose.filter((item) => context.purposeItemIds.includes(item.id)) : purpose);
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
        <DiscoveryPanel
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
        <PurposePanel
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
        <ChatPanel messages={messages} draft={chatDraft} setDraft={setChatDraft} onSubmit={submitChat} />
        <ProposalsPanel proposals={proposals} onAccept={accept} onReject={reject} />
        <LineagePanel label={selectedLineageLabel} events={lineageEvents} />
      </div>
    </section>
  );
}
