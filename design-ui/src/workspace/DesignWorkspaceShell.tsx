import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { DockviewReact } from "dockview";
import type { DockviewApi, DockviewReadyEvent, IDockviewPanelProps } from "dockview";
import { ChatPanel, type ChatPanelProps } from "../panels/ChatPanel";
import { DiscoveryPanel, type DiscoveryPanelProps } from "../panels/DiscoveryPanel";
import { LineagePanel, type LineagePanelProps } from "../panels/LineagePanel";
import { ProposalsPanel, type ProposalsPanelProps } from "../panels/ProposalsPanel";
import { PurposePanel, type PurposePanelProps } from "../panels/PurposePanel";

export const WORKSPACE_PANEL_IDS = ["chat", "discovery", "purpose", "proposals", "lineage"] as const;

export type WorkspacePanelId = (typeof WORKSPACE_PANEL_IDS)[number];

export const DEFAULT_WORKSPACE_LAYOUT_PANELS: Record<WorkspacePanelId, { title: string; role: string }> = {
  chat: { title: "Chat", role: "primary" },
  discovery: { title: "Discovery", role: "primary" },
  purpose: { title: "Purpose", role: "primary" },
  proposals: { title: "Proposals", role: "commit-gate" },
  lineage: { title: "Lineage", role: "secondary" }
};

export type DesignWorkspaceShellProps = {
  activeContextLabel: string | null;
  pendingCount: number;
  chatPanel: ChatPanelProps;
  discoveryPanel: DiscoveryPanelProps;
  purposePanel: PurposePanelProps;
  proposalsPanel: ProposalsPanelProps;
  lineagePanel: LineagePanelProps;
};

type DesignWorkspacePanelContextValue = Pick<
  DesignWorkspaceShellProps,
  "chatPanel" | "discoveryPanel" | "purposePanel" | "proposalsPanel" | "lineagePanel"
>;

const DesignWorkspacePanelContext = createContext<DesignWorkspacePanelContextValue | null>(null);

function useWorkspacePanels() {
  const value = useContext(DesignWorkspacePanelContext);
  if (!value) throw new Error("Design workspace panels must be rendered inside DesignWorkspaceShell.");
  return value;
}

function DockviewPanelFrame({ children }: { children: ReactNode }) {
  return <div className="design-dockview-panel">{children}</div>;
}

function ChatWorkspacePanel(_props: IDockviewPanelProps) {
  const panels = useWorkspacePanels();
  return (
    <DockviewPanelFrame>
      <ChatPanel {...panels.chatPanel} />
    </DockviewPanelFrame>
  );
}

function DiscoveryWorkspacePanel(_props: IDockviewPanelProps) {
  const panels = useWorkspacePanels();
  return (
    <DockviewPanelFrame>
      <DiscoveryPanel {...panels.discoveryPanel} />
    </DockviewPanelFrame>
  );
}

function PurposeWorkspacePanel(_props: IDockviewPanelProps) {
  const panels = useWorkspacePanels();
  return (
    <DockviewPanelFrame>
      <PurposePanel {...panels.purposePanel} />
    </DockviewPanelFrame>
  );
}

function ProposalsWorkspacePanel(_props: IDockviewPanelProps) {
  const panels = useWorkspacePanels();
  return (
    <DockviewPanelFrame>
      <ProposalsPanel {...panels.proposalsPanel} />
    </DockviewPanelFrame>
  );
}

function LineageWorkspacePanel(_props: IDockviewPanelProps) {
  const panels = useWorkspacePanels();
  return (
    <DockviewPanelFrame>
      <LineagePanel {...panels.lineagePanel} />
    </DockviewPanelFrame>
  );
}

export const workspacePanelComponents = {
  chat: ChatWorkspacePanel,
  discovery: DiscoveryWorkspacePanel,
  purpose: PurposeWorkspacePanel,
  proposals: ProposalsWorkspacePanel,
  lineage: LineageWorkspacePanel
};

function proposalsTitle(pendingCount: number) {
  return pendingCount > 0 ? `Proposals (${pendingCount})` : DEFAULT_WORKSPACE_LAYOUT_PANELS.proposals.title;
}

export function buildDefaultWorkspaceLayout(api: DockviewApi, pendingCount: number) {
  api.closeAllGroups();
  api.addPanel({
    id: "chat",
    component: "chat",
    title: DEFAULT_WORKSPACE_LAYOUT_PANELS.chat.title,
    initialWidth: 520
  });
  api.addPanel({
    id: "discovery",
    component: "discovery",
    title: DEFAULT_WORKSPACE_LAYOUT_PANELS.discovery.title,
    position: { referencePanel: "chat", direction: "right" },
    initialWidth: 440
  });
  api.addPanel({
    id: "purpose",
    component: "purpose",
    title: DEFAULT_WORKSPACE_LAYOUT_PANELS.purpose.title,
    position: { referencePanel: "discovery", direction: "right" },
    initialWidth: 440
  });
  api.addPanel({
    id: "proposals",
    component: "proposals",
    title: proposalsTitle(pendingCount),
    position: { referencePanel: "purpose", direction: "below" },
    initialHeight: 260
  });
  api.addPanel({
    id: "lineage",
    component: "lineage",
    title: DEFAULT_WORKSPACE_LAYOUT_PANELS.lineage.title,
    position: { referencePanel: "proposals", direction: "within" },
    inactive: true
  });
  api.getPanel("chat")?.api.setActive();
}

export function DesignWorkspaceShell({
  activeContextLabel,
  pendingCount,
  chatPanel,
  discoveryPanel,
  purposePanel,
  proposalsPanel,
  lineagePanel
}: DesignWorkspaceShellProps) {
  const [api, setApi] = useState<DockviewApi | null>(null);

  const panelContext = useMemo(
    () => ({ chatPanel, discoveryPanel, purposePanel, proposalsPanel, lineagePanel }),
    [chatPanel, discoveryPanel, lineagePanel, proposalsPanel, purposePanel]
  );

  const onReady = (event: DockviewReadyEvent) => {
    setApi(event.api);
    buildDefaultWorkspaceLayout(event.api, pendingCount);
  };

  const focusPanel = (panelId: WorkspacePanelId) => {
    api?.getPanel(panelId)?.api.setActive();
  };

  const resetLayout = () => {
    if (!api) return;
    buildDefaultWorkspaceLayout(api, pendingCount);
  };

  useEffect(() => {
    api?.getPanel("proposals")?.api.setTitle(proposalsTitle(pendingCount));
  }, [api, pendingCount]);

  return (
    <DesignWorkspacePanelContext.Provider value={panelContext}>
      <section className="design-workspace">
        <div className="focus-bar workspace-toolbar" role="group" aria-label="Workspace controls">
          <button onClick={() => focusPanel("chat")} type="button">
            Chat
          </button>
          <button onClick={() => focusPanel("discovery")} type="button">
            Discovery Focus
          </button>
          <button onClick={() => focusPanel("purpose")} type="button">
            Purpose Focus
          </button>
          <button onClick={() => focusPanel("proposals")} type="button">
            Proposals
          </button>
          <button data-testid="workspace-reset-layout" onClick={resetLayout} type="button">
            Reset Layout
          </button>
          <span>{pendingCount} pending</span>
          {activeContextLabel ? <span>Context: {activeContextLabel}</span> : null}
        </div>
        <div className="design-dockview dockview-theme-light" data-testid="design-workspace-shell">
          <DockviewReact components={workspacePanelComponents} onReady={onReady} />
        </div>
      </section>
    </DesignWorkspacePanelContext.Provider>
  );
}
