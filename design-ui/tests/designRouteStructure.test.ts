import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const routeSource = readFileSync(new URL("../src/routes/DesignRoute.tsx", import.meta.url), "utf8");
const packageSource = readFileSync(new URL("../package.json", import.meta.url), "utf8");
const cssSource = readFileSync(new URL("../src/styles/app.css", import.meta.url), "utf8");
const chatPanel = readFileSync(new URL("../src/panels/ChatPanel.tsx", import.meta.url), "utf8");
const discoveryPanel = readFileSync(new URL("../src/panels/DiscoveryPanel.tsx", import.meta.url), "utf8");
const purposePanel = readFileSync(new URL("../src/panels/PurposePanel.tsx", import.meta.url), "utf8");
const proposalsPanel = readFileSync(new URL("../src/panels/ProposalsPanel.tsx", import.meta.url), "utf8");
const lineagePanel = readFileSync(new URL("../src/panels/LineagePanel.tsx", import.meta.url), "utf8");
const workspaceShell = readFileSync(new URL("../src/workspace/DesignWorkspaceShell.tsx", import.meta.url), "utf8");

test("/design route keeps Discovery and Purpose surfaces present", () => {
  assert.match(routeSource, /<DesignWorkspaceShell/);
  assert.match(workspaceShell, /<DiscoveryPanel/);
  assert.match(workspaceShell, /<PurposePanel/);
  assert.match(discoveryPanel, /data-testid="discovery-surface"/);
  assert.match(purposePanel, /data-testid="purpose-surface"/);
});

test("/design route includes manual fallback and proposal approval controls", () => {
  assert.match(discoveryPanel, /Add Discovery/);
  assert.match(purposePanel, /Add Purpose/);
  assert.match(discoveryPanel, /Promote/);
  assert.match(purposePanel, /Demote/);
  assert.match(proposalsPanel, /Accept/);
  assert.match(proposalsPanel, /Reject/);
});

test("/design route includes lineage panel and active context loading", () => {
  assert.match(workspaceShell, /<LineagePanel/);
  assert.match(lineagePanel, /data-testid="lineage-panel"/);
  assert.match(routeSource, /listLineageEvents/);
  assert.match(routeSource, /getDesignMap/);
  assert.match(routeSource, /activeContext/);
});

test("/design active context constrains both surfaces without hiding them", () => {
  assert.match(routeSource, /context \? discovery\.filter/);
  assert.match(routeSource, /context \? purpose\.filter/);
  assert.doesNotMatch(routeSource, /context && context\.discoveryItemIds\.length/);
  assert.doesNotMatch(routeSource, /context && context\.purposeItemIds\.length/);
});

test("/design uses GoldenLayout workspace shell without removing route-owned state", () => {
  assert.match(packageSource, /"golden-layout"/);
  assert.doesNotMatch(packageSource, /"dockview"/);
  assert.match(workspaceShell, /GoldenLayout/);
  assert.match(workspaceShell, /data-testid="design-workspace-shell"/);
  assert.match(workspaceShell, /WORKSPACE_PANEL_IDS = \["chat", "discovery", "purpose", "proposals", "lineage"\]/);
  assert.match(workspaceShell, /registerComponentFactoryFunction/);
  assert.match(workspaceShell, /buildDefaultWorkspaceLayout/);
  assert.match(workspaceShell, /data-testid="workspace-reset-layout"/);
  assert.match(routeSource, /acceptProposal/);
  assert.match(routeSource, /rejectProposal/);
  assert.match(routeSource, /listProposals/);
});

test("default workspace layout registers primary panels and support panels", () => {
  assert.match(workspaceShell, /workspaceComponent\("chat", pendingCount, "33%"\)/);
  assert.match(workspaceShell, /workspaceComponent\("discovery", pendingCount, "34%"\)/);
  assert.match(workspaceShell, /workspaceComponent\("purpose", pendingCount, "33%"\)/);
  assert.match(workspaceShell, /workspaceComponent\("proposals", pendingCount\)/);
  assert.match(workspaceShell, /workspaceComponent\("lineage", pendingCount\)/);
  assert.match(workspaceShell, /type: "row"[\s\S]*size: "76%"/);
  assert.match(workspaceShell, /type: "stack"[\s\S]*size: "24%"/);
  assert.match(workspaceShell, /borderGrabWidth: 18/);
  assert.match(workspaceShell, /popout: "Open in new window"/);
  assert.match(workspaceShell, /close: "Hide panel"/);
});

test("workspace can reset and recover hidden GoldenLayout panels", () => {
  assert.match(workspaceShell, /layout\.loadLayout\(buildDefaultWorkspaceLayout\(pendingCount\)\)/);
  assert.match(workspaceShell, /data-testid="workspace-hidden-panels"/);
  assert.match(workspaceShell, /data-testid=\{`workspace-reopen-\$\{panelId\}`\}/);
  assert.match(workspaceShell, /layout\.newComponent\(panelId/);
  assert.match(workspaceShell, /collectWorkspacePanelIds/);
});

test("primary and support surfaces are extracted into reusable panels", () => {
  assert.match(chatPanel, /export function ChatPanel/);
  assert.match(discoveryPanel, /export function DiscoveryPanel/);
  assert.match(purposePanel, /export function PurposePanel/);
  assert.match(proposalsPanel, /export function ProposalsPanel/);
  assert.match(lineagePanel, /export function LineagePanel/);
  assert.match(chatPanel, /export type ChatPanelProps/);
  assert.match(discoveryPanel, /export type DiscoveryPanelProps/);
  assert.match(purposePanel, /export type PurposePanelProps/);
  assert.match(proposalsPanel, /export type ProposalsPanelProps/);
  assert.match(lineagePanel, /export type LineagePanelProps/);
  assert.match(workspaceShell, /from "\.\.\/panels\/ChatPanel"/);
  assert.match(workspaceShell, /from "\.\.\/panels\/DiscoveryPanel"/);
  assert.match(workspaceShell, /from "\.\.\/panels\/PurposePanel"/);
  assert.match(workspaceShell, /from "\.\.\/panels\/ProposalsPanel"/);
  assert.match(workspaceShell, /from "\.\.\/panels\/LineagePanel"/);
});

test("extracted panels preserve current route controls and test ids", () => {
  assert.match(chatPanel, /data-testid="chat-panel"/);
  assert.match(chatPanel, /className="workspace-panel chat-panel"/);
  assert.match(chatPanel, /Chat message/);
  assert.match(chatPanel, /Send/);
  assert.match(discoveryPanel, /data-testid="discovery-surface"/);
  assert.match(discoveryPanel, /className="workspace-panel design-surface discovery-panel"/);
  assert.match(purposePanel, /data-testid="purpose-surface"/);
  assert.match(purposePanel, /className="workspace-panel design-surface purpose-panel"/);
  assert.match(proposalsPanel, /data-testid="proposals-panel"/);
  assert.match(lineagePanel, /data-testid="lineage-panel"/);
  assert.doesNotMatch(chatPanel, /<h2>Chat<\/h2>/);
  assert.doesNotMatch(discoveryPanel, /<h2>Discovery<\/h2>/);
  assert.doesNotMatch(purposePanel, /<h2>Purpose<\/h2>/);
  assert.doesNotMatch(proposalsPanel, /<h3>Pending Proposals<\/h3>/);
});

test("/map route is a node-link graph with filters and context loading", () => {
  const mapRoute = readFileSync(new URL("../src/routes/MapRoute.tsx", import.meta.url), "utf8");
  assert.match(mapRoute, /data-testid="design-map"/);
  assert.match(mapRoute, /map-node-grid/);
  assert.match(mapRoute, /map-edge-list/);
  assert.match(mapRoute, /selectMapNode/);
  assert.match(mapRoute, /nodeType/);
  assert.match(mapRoute, /maturity/);
  assert.match(mapRoute, /connected/);
  assert.doesNotMatch(mapRoute, /tree|folder/i);
});

test("workspace CSS hosts GoldenLayout without hiding surfaces", () => {
  assert.match(cssSource, /\.golden-workspace/);
  assert.match(cssSource, /\.workspace-panel/);
  assert.match(cssSource, /\.lm_splitter:hover/);
  assert.match(cssSource, /\.lm_controls > \*/);
  assert.match(cssSource, /\.lm_dropTargetIndicator/);
  assert.doesNotMatch(cssSource, /\.golden-panel-frame/);
  assert.doesNotMatch(cssSource, /display:\s*none/);
});
