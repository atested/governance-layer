import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { DockviewReact } from "dockview";
import type { DockviewApi, DockviewReadyEvent, IDockviewPanelHeaderProps, IDockviewPanelProps } from "dockview";
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

export const WORKSPACE_TAB_COMPONENT = "workspaceTab";

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
> & {
  maximizedPanelId: WorkspacePanelId | null;
  onClosePanel: (panelId: WorkspacePanelId) => void;
  onFocusPanel: (panelId: WorkspacePanelId) => void;
  onPopoutPanel: (panelId: WorkspacePanelId) => void;
  onToggleMaximize: (panelId: WorkspacePanelId) => void;
};

const DesignWorkspacePanelContext = createContext<DesignWorkspacePanelContextValue | null>(null);

function useWorkspacePanels() {
  const value = useContext(DesignWorkspacePanelContext);
  if (!value) throw new Error("Design workspace panels must be rendered inside DesignWorkspaceShell.");
  return value;
}

function DockviewPanelFrame({ children }: { children: ReactNode }) {
  return <div className="design-dockview-panel">{children}</div>;
}

function isWorkspacePanelId(value: string | null): value is WorkspacePanelId {
  return WORKSPACE_PANEL_IDS.includes(value as WorkspacePanelId);
}

function panelTitle(panelId: WorkspacePanelId, pendingCount: number) {
  if (panelId === "proposals") return proposalsTitle(pendingCount);
  return DEFAULT_WORKSPACE_LAYOUT_PANELS[panelId].title;
}

function stopPanelControlEvent(event: { stopPropagation: () => void }) {
  event.stopPropagation();
}

function WorkspacePanelTab({ api }: IDockviewPanelHeaderProps) {
  const panels = useWorkspacePanels();
  const panelId = api.id as WorkspacePanelId;
  const isMaximized = panels.maximizedPanelId === panelId;

  return (
    <div className="workspace-tab" data-testid={`workspace-tab-${panelId}`}>
      <button className="workspace-tab-title" onClick={() => panels.onFocusPanel(panelId)} type="button">
        {api.title ?? DEFAULT_WORKSPACE_LAYOUT_PANELS[panelId].title}
      </button>
      <div className="workspace-tab-actions" aria-label={`${api.title ?? panelId} panel controls`}>
        <button
          aria-label={`Pop out ${api.title ?? panelId}`}
          data-testid={`workspace-popout-${panelId}`}
          onClick={(event) => {
            stopPanelControlEvent(event);
            panels.onPopoutPanel(panelId);
          }}
          onPointerDown={stopPanelControlEvent}
          title="Pop out"
          type="button"
        >
          Pop
        </button>
        <button
          aria-label={`${isMaximized ? "Restore" : "Maximize"} ${api.title ?? panelId}`}
          data-testid={`workspace-maximize-${panelId}`}
          onClick={(event) => {
            stopPanelControlEvent(event);
            panels.onToggleMaximize(panelId);
          }}
          onPointerDown={stopPanelControlEvent}
          title={isMaximized ? "Restore" : "Maximize"}
          type="button"
        >
          {isMaximized ? "Restore" : "Max"}
        </button>
        <button
          aria-label={`Hide ${api.title ?? panelId}`}
          data-testid={`workspace-close-${panelId}`}
          onClick={(event) => {
            stopPanelControlEvent(event);
            panels.onClosePanel(panelId);
          }}
          onPointerDown={stopPanelControlEvent}
          title="Hide panel"
          type="button"
        >
          Hide
        </button>
      </div>
    </div>
  );
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

export const workspaceTabComponents = {
  [WORKSPACE_TAB_COMPONENT]: WorkspacePanelTab
};

function proposalsTitle(pendingCount: number) {
  return pendingCount > 0 ? `Proposals (${pendingCount})` : DEFAULT_WORKSPACE_LAYOUT_PANELS.proposals.title;
}

export function buildDefaultWorkspaceLayout(api: DockviewApi, pendingCount: number) {
  api.closeAllGroups();
  api.addPanel({
    id: "chat",
    component: "chat",
    tabComponent: WORKSPACE_TAB_COMPONENT,
    title: DEFAULT_WORKSPACE_LAYOUT_PANELS.chat.title,
    initialWidth: 620,
    minimumWidth: 420,
    minimumHeight: 360
  });
  api.addPanel({
    id: "discovery",
    component: "discovery",
    tabComponent: WORKSPACE_TAB_COMPONENT,
    title: DEFAULT_WORKSPACE_LAYOUT_PANELS.discovery.title,
    position: { referencePanel: "chat", direction: "right" },
    initialWidth: 640,
    minimumWidth: 420,
    minimumHeight: 300
  });
  api.addPanel({
    id: "purpose",
    component: "purpose",
    tabComponent: WORKSPACE_TAB_COMPONENT,
    title: DEFAULT_WORKSPACE_LAYOUT_PANELS.purpose.title,
    position: { referencePanel: "discovery", direction: "below" },
    initialHeight: 360,
    minimumWidth: 420,
    minimumHeight: 300
  });
  api.addPanel({
    id: "proposals",
    component: "proposals",
    tabComponent: WORKSPACE_TAB_COMPONENT,
    title: proposalsTitle(pendingCount),
    position: { referencePanel: "chat", direction: "below" },
    initialHeight: 280,
    minimumWidth: 360,
    minimumHeight: 220
  });
  api.addPanel({
    id: "lineage",
    component: "lineage",
    tabComponent: WORKSPACE_TAB_COMPONENT,
    title: DEFAULT_WORKSPACE_LAYOUT_PANELS.lineage.title,
    position: { referencePanel: "proposals", direction: "within" },
    inactive: true,
    minimumWidth: 320,
    minimumHeight: 220
  });
  api.getPanel("chat")?.api.setActive();
}

function addWorkspacePanel(api: DockviewApi, panelId: WorkspacePanelId, pendingCount: number) {
  const base = {
    id: panelId,
    component: panelId,
    tabComponent: WORKSPACE_TAB_COMPONENT,
    title: panelTitle(panelId, pendingCount),
    minimumWidth: panelId === "chat" || panelId === "discovery" || panelId === "purpose" ? 420 : 320,
    minimumHeight: panelId === "chat" ? 360 : 220
  };
  const activePanel = api.activePanel?.id;
  const firstPanel = WORKSPACE_PANEL_IDS.find((id) => api.getPanel(id));

  if (!firstPanel) {
    api.addPanel(base);
    api.getPanel(panelId)?.api.setActive();
    return;
  }

  if (panelId === "discovery" && api.getPanel("chat")) {
    api.addPanel({ ...base, position: { referencePanel: "chat", direction: "right" }, initialWidth: 640 });
  } else if (panelId === "purpose" && api.getPanel("discovery")) {
    api.addPanel({ ...base, position: { referencePanel: "discovery", direction: "below" }, initialHeight: 360 });
  } else if (panelId === "proposals" && api.getPanel("chat")) {
    api.addPanel({ ...base, position: { referencePanel: "chat", direction: "below" }, initialHeight: 280 });
  } else if (panelId === "lineage" && api.getPanel("proposals")) {
    api.addPanel({ ...base, position: { referencePanel: "proposals", direction: "within" } });
  } else {
    api.addPanel({ ...base, position: { referencePanel: activePanel ?? firstPanel, direction: "within" } });
  }
  api.getPanel(panelId)?.api.setActive();
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
  const [hiddenPanels, setHiddenPanels] = useState<WorkspacePanelId[]>([]);
  const [maximizedPanelId, setMaximizedPanelId] = useState<WorkspacePanelId | null>(null);
  const requestedPanel = new URLSearchParams(window.location.search).get("panel");
  const selectedPopoutPanel = isWorkspacePanelId(requestedPanel) ? requestedPanel : null;

  const onReady = (event: DockviewReadyEvent) => {
    setApi(event.api);
    buildDefaultWorkspaceLayout(event.api, pendingCount);
  };

  const focusPanel = (panelId: WorkspacePanelId) => {
    if (!api) return;
    const panel = api.getPanel(panelId);
    if (panel) {
      panel.api.setActive();
      return;
    }
    addWorkspacePanel(api, panelId, pendingCount);
    setHiddenPanels((current) => current.filter((id) => id !== panelId));
  };

  const resetLayout = () => {
    if (!api) return;
    buildDefaultWorkspaceLayout(api, pendingCount);
    setHiddenPanels([]);
    setMaximizedPanelId(null);
  };

  const closePanel = (panelId: WorkspacePanelId) => {
    const panel = api?.getPanel(panelId);
    if (!panel) return;
    panel.api.close();
    setHiddenPanels((current) => (current.includes(panelId) ? current : [...current, panelId]));
    if (maximizedPanelId === panelId) setMaximizedPanelId(null);
  };

  const toggleMaximize = (panelId: WorkspacePanelId) => {
    const panel = api?.getPanel(panelId);
    if (!panel) return;
    if (panel.api.isMaximized()) {
      panel.api.exitMaximized();
      setMaximizedPanelId(null);
      return;
    }
    if (api?.hasMaximizedGroup()) api.exitMaximizedGroup();
    panel.api.maximize();
    setMaximizedPanelId(panelId);
  };

  const popoutPanel = (panelId: WorkspacePanelId) => {
    const url = new URL(window.location.href);
    url.searchParams.set("panel", panelId);
    const popup = window.open(url.toString(), `design-ui-${panelId}`, "popup,width=1120,height=820");
    popup?.focus();
  };

  useEffect(() => {
    api?.getPanel("proposals")?.api.setTitle(proposalsTitle(pendingCount));
  }, [api, pendingCount]);

  useEffect(() => {
    if (!api) return;
    const disposable = api.onDidMaximizedGroupChange(() => {
      if (!api.hasMaximizedGroup()) setMaximizedPanelId(null);
    });
    return () => disposable.dispose();
  }, [api]);

  const panelContext = useMemo(
    () => ({
      chatPanel,
      discoveryPanel,
      lineagePanel,
      maximizedPanelId,
      onClosePanel: closePanel,
      onFocusPanel: focusPanel,
      onPopoutPanel: popoutPanel,
      onToggleMaximize: toggleMaximize,
      proposalsPanel,
      purposePanel
    }),
    [api, chatPanel, discoveryPanel, lineagePanel, maximizedPanelId, pendingCount, proposalsPanel, purposePanel]
  );

  const renderPanel = (panelId: WorkspacePanelId) => {
    switch (panelId) {
      case "chat":
        return <ChatPanel {...chatPanel} />;
      case "discovery":
        return <DiscoveryPanel {...discoveryPanel} />;
      case "purpose":
        return <PurposePanel {...purposePanel} />;
      case "proposals":
        return <ProposalsPanel {...proposalsPanel} />;
      case "lineage":
        return <LineagePanel {...lineagePanel} />;
    }
  };

  if (selectedPopoutPanel) {
    return (
      <DesignWorkspacePanelContext.Provider value={panelContext}>
        <section className="design-workspace design-workspace-popout">
          <div className="focus-bar workspace-toolbar" role="group" aria-label="Popout panel controls">
            <button onClick={() => window.close()} type="button">
              Close Window
            </button>
            <button
              onClick={() => {
                const url = new URL(window.location.href);
                url.searchParams.delete("panel");
                window.location.href = url.toString();
              }}
              type="button"
            >
              Open Workspace
            </button>
            <span>{pendingCount} pending</span>
            {activeContextLabel ? <span>Context: {activeContextLabel}</span> : null}
          </div>
          <div className="design-popout-panel" data-testid={`workspace-popout-panel-${selectedPopoutPanel}`}>
            <header className="workspace-popout-header">
              <h2>{panelTitle(selectedPopoutPanel, pendingCount)}</h2>
            </header>
            <DockviewPanelFrame>{renderPanel(selectedPopoutPanel)}</DockviewPanelFrame>
          </div>
        </section>
      </DesignWorkspacePanelContext.Provider>
    );
  }

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
          <div className="workspace-hidden-panels" data-testid="workspace-hidden-panels">
            <span>Hidden panels</span>
            {hiddenPanels.length === 0 ? <span>None</span> : null}
            {hiddenPanels.map((panelId) => (
              <button
                data-testid={`workspace-reopen-${panelId}`}
                key={panelId}
                onClick={() => focusPanel(panelId)}
                type="button"
              >
                Show {DEFAULT_WORKSPACE_LAYOUT_PANELS[panelId].title}
              </button>
            ))}
          </div>
          <span>{pendingCount} pending</span>
          {activeContextLabel ? <span>Context: {activeContextLabel}</span> : null}
        </div>
        <div className="design-dockview dockview-theme-light" data-testid="design-workspace-shell">
          <DockviewReact
            components={workspacePanelComponents}
            onReady={onReady}
            tabComponents={workspaceTabComponents}
          />
        </div>
      </section>
    </DesignWorkspacePanelContext.Provider>
  );
}
