import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { ComponentContainer, GoldenLayout } from "golden-layout";
import type { ComponentItemConfig, LayoutConfig } from "golden-layout";
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

type WorkspacePanelPropsState = Pick<
  DesignWorkspaceShellProps,
  "chatPanel" | "discoveryPanel" | "purposePanel" | "proposalsPanel" | "lineagePanel"
>;

type MountedGoldenPanel = {
  container: ComponentContainer;
  host: HTMLDivElement;
  panelId: WorkspacePanelId;
  root: Root;
};

function proposalsTitle(pendingCount: number) {
  return pendingCount > 0 ? `Proposals (${pendingCount})` : DEFAULT_WORKSPACE_LAYOUT_PANELS.proposals.title;
}

function panelTitle(panelId: WorkspacePanelId, pendingCount: number) {
  if (panelId === "proposals") return proposalsTitle(pendingCount);
  return DEFAULT_WORKSPACE_LAYOUT_PANELS[panelId].title;
}

function workspaceComponent(panelId: WorkspacePanelId, pendingCount: number, size?: string): ComponentItemConfig {
  return {
    type: "component",
    id: panelId,
    componentType: panelId,
    title: panelTitle(panelId, pendingCount),
    size,
    minSize: panelId === "chat" || panelId === "discovery" || panelId === "purpose" ? "360px" : "280px"
  };
}

export function buildDefaultWorkspaceLayout(pendingCount: number): LayoutConfig {
  return {
    root: {
      type: "column",
      content: [
        {
          type: "row",
          size: "76%",
          content: [
            workspaceComponent("chat", pendingCount, "33%"),
            workspaceComponent("discovery", pendingCount, "34%"),
            workspaceComponent("purpose", pendingCount, "33%")
          ]
        },
        {
          type: "stack",
          size: "24%",
          content: [workspaceComponent("proposals", pendingCount), workspaceComponent("lineage", pendingCount)]
        }
      ]
    },
    settings: {
      blockedPopoutsThrowError: false,
      closePopoutsOnUnload: true,
      constrainDragToContainer: true,
      popInOnClose: false,
      popoutWholeStack: false,
      reorderEnabled: true
    },
    dimensions: {
      borderGrabWidth: 18,
      borderWidth: 10,
      defaultMinItemHeight: "180px",
      defaultMinItemWidth: "300px",
      dragProxyHeight: 260,
      dragProxyWidth: 360,
      headerHeight: 32
    },
    header: {
      close: "Hide panel",
      maximise: "Maximize",
      minimise: "Restore",
      popout: "Open in new window",
      show: "top",
      tabDropdown: "More panels"
    }
  };
}

function collectWorkspacePanelIds(layoutConfig: unknown, found = new Set<WorkspacePanelId>()) {
  if (!layoutConfig || typeof layoutConfig !== "object") return found;
  const node = layoutConfig as { componentType?: unknown; content?: unknown };
  if (typeof node.componentType === "string" && WORKSPACE_PANEL_IDS.includes(node.componentType as WorkspacePanelId)) {
    found.add(node.componentType as WorkspacePanelId);
  }
  if (Array.isArray(node.content)) {
    for (const child of node.content) collectWorkspacePanelIds(child, found);
  }
  return found;
}

function renderPanel(panelId: WorkspacePanelId, props: WorkspacePanelPropsState) {
  switch (panelId) {
    case "chat":
      return <ChatPanel {...props.chatPanel} />;
    case "discovery":
      return <DiscoveryPanel {...props.discoveryPanel} />;
    case "purpose":
      return <PurposePanel {...props.purposePanel} />;
    case "proposals":
      return <ProposalsPanel {...props.proposalsPanel} />;
    case "lineage":
      return <LineagePanel {...props.lineagePanel} />;
  }
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
  const hostRef = useRef<HTMLDivElement | null>(null);
  const layoutRef = useRef<GoldenLayout | null>(null);
  const mountedPanelsRef = useRef(new Map<ComponentContainer, MountedGoldenPanel>());
  const latestPanelPropsRef = useRef<WorkspacePanelPropsState>({
    chatPanel,
    discoveryPanel,
    lineagePanel,
    proposalsPanel,
    purposePanel
  });
  const [hiddenPanels, setHiddenPanels] = useState<WorkspacePanelId[]>([]);

  latestPanelPropsRef.current = {
    chatPanel,
    discoveryPanel,
    lineagePanel,
    proposalsPanel,
    purposePanel
  };

  const panelMetadata = useMemo(
    () =>
      WORKSPACE_PANEL_IDS.map((panelId) => ({
        id: panelId,
        title: panelTitle(panelId, pendingCount)
      })),
    [pendingCount]
  );

  const renderMountedPanel = (record: MountedGoldenPanel) => {
    record.root.render(renderPanel(record.panelId, latestPanelPropsRef.current));
  };

  const updateHiddenPanels = (layout: GoldenLayout) => {
    const visible = collectWorkspacePanelIds(layout.saveLayout().root);
    setHiddenPanels(WORKSPACE_PANEL_IDS.filter((panelId) => !visible.has(panelId)));
  };

  const registerPanels = (layout: GoldenLayout) => {
    for (const panelId of WORKSPACE_PANEL_IDS) {
      layout.registerComponentFactoryFunction(panelId, (container) => {
        const host = document.createElement("div");
        host.className = "golden-panel-host";
        container.element.appendChild(host);
        const root = createRoot(host);
        const record = { container, host, panelId, root };
        let destroyed = false;

        mountedPanelsRef.current.set(container, record);
        renderMountedPanel(record);

        const cleanup = () => {
          if (destroyed) return;
          destroyed = true;
          root.unmount();
          host.remove();
          mountedPanelsRef.current.delete(container);
        };

        container.on("destroy", cleanup);
        return { panelId };
      });
    }
  };

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    const layout = new GoldenLayout(host);
    const resizeObserver = new ResizeObserver(() => layout.updateRootSize());

    registerPanels(layout);
    layout.loadLayout(buildDefaultWorkspaceLayout(pendingCount));
    resizeObserver.observe(host);
    layout.on("stateChanged", () => updateHiddenPanels(layout));
    updateHiddenPanels(layout);
    layoutRef.current = layout;

    return () => {
      resizeObserver.disconnect();
      layout.destroy();
      for (const record of mountedPanelsRef.current.values()) {
        record.root.unmount();
        record.host.remove();
      }
      mountedPanelsRef.current.clear();
      layoutRef.current = null;
    };
  }, []);

  useEffect(() => {
    for (const record of mountedPanelsRef.current.values()) renderMountedPanel(record);
  }, [chatPanel, discoveryPanel, lineagePanel, proposalsPanel, purposePanel]);

  useEffect(() => {
    const layout = layoutRef.current;
    if (!layout) return;
    for (const panelId of WORKSPACE_PANEL_IDS) {
      layout.findFirstComponentItemById(panelId)?.container.setTitle(panelTitle(panelId, pendingCount));
    }
  }, [pendingCount]);

  const focusPanel = (panelId: WorkspacePanelId) => {
    const layout = layoutRef.current;
    if (!layout) return;
    const item = layout.findFirstComponentItemById(panelId);
    if (item) {
      item.focus();
      return;
    }
    layout.newComponent(panelId, undefined, panelTitle(panelId, pendingCount));
    updateHiddenPanels(layout);
  };

  const resetLayout = () => {
    const layout = layoutRef.current;
    if (!layout) return;
    layout.loadLayout(buildDefaultWorkspaceLayout(pendingCount));
    updateHiddenPanels(layout);
  };

  return (
    <section className="design-workspace">
      <div className="workspace-statusbar" role="group" aria-label="Workspace controls">
        <span>{pendingCount} pending</span>
        {activeContextLabel ? <span>Context: {activeContextLabel}</span> : null}
        <button data-testid="workspace-reset-layout" onClick={resetLayout} type="button">
          Reset Layout
        </button>
        {hiddenPanels.length > 0 ? (
          <div className="workspace-hidden-panels" data-testid="workspace-hidden-panels">
            <span>Hidden</span>
            {hiddenPanels.map((panelId) => (
              <button
                data-testid={`workspace-reopen-${panelId}`}
                key={panelId}
                onClick={() => focusPanel(panelId)}
                type="button"
              >
                {panelMetadata.find((panel) => panel.id === panelId)?.title ??
                  DEFAULT_WORKSPACE_LAYOUT_PANELS[panelId].title}
              </button>
            ))}
          </div>
        ) : (
          <div className="workspace-hidden-panels" data-testid="workspace-hidden-panels">
            <span>All panels visible</span>
          </div>
        )}
      </div>
      <div className="golden-workspace lm_goldenlayout" data-testid="design-workspace-shell" ref={hostRef} />
    </section>
  );
}
