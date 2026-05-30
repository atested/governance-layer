import { useEffect, useMemo, useState } from "react";
import { createProject, getDesignMap, listProjects, selectMapNode } from "../api/client";
import type { DesignMap, MapNode, MapNodeType } from "../types/design";

const nodeTypes: Array<MapNodeType | "all"> = [
  "all",
  "concept",
  "discovery_cluster",
  "purpose_region",
  "tension",
  "open_area",
  "disconnected_idea"
];

export function MapRoute() {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [map, setMap] = useState<DesignMap | null>(null);
  const [nodeType, setNodeType] = useState<MapNodeType | "all">("all");
  const [maturity, setMaturity] = useState("all");
  const [connection, setConnection] = useState<"all" | "connected" | "disconnected">("all");

  const loadMap = async (id: string) => {
    setMap(await getDesignMap(id));
  };

  useEffect(() => {
    let cancelled = false;
    async function initialize() {
      const projects = await listProjects();
      const project = projects[0] ?? (await createProject("Design UI v1"));
      if (cancelled) return;
      setProjectId(project.id);
      await loadMap(project.id);
    }
    void initialize();
    return () => {
      cancelled = true;
    };
  }, []);

  const maturities = useMemo(() => {
    const values = new Set((map?.nodes ?? []).map((node) => String(node.maturity)));
    return ["all", ...Array.from(values).sort()];
  }, [map]);

  const filteredNodes = useMemo(() => {
    return (map?.nodes ?? []).filter((node) => {
      if (nodeType !== "all" && node.nodeType !== nodeType) return false;
      if (maturity !== "all" && node.maturity !== maturity) return false;
      if (connection === "connected" && !node.connected) return false;
      if (connection === "disconnected" && node.connected) return false;
      return true;
    });
  }, [connection, map, maturity, nodeType]);

  const visibleNodeIds = new Set(filteredNodes.map((node) => node.id));
  const visibleEdges =
    map?.edges.filter((edge) => visibleNodeIds.has(edge.fromId) && visibleNodeIds.has(edge.toId)) ?? [];

  const chooseNode = async (node: MapNode) => {
    if (!projectId) return;
    const result = await selectMapNode(projectId, node.id);
    setMap(result.map);
    window.history.pushState({}, "", "/design");
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  return (
    <section className="map-workspace">
      <header className="map-header">
        <div>
          <h2>Design Map</h2>
          <p>Node-link view of concepts, regions, open areas, tensions, and disconnected ideas.</p>
        </div>
        {map?.activeContext ? <span>Active: {map.activeContext.label}</span> : null}
      </header>

      <div className="map-filters" aria-label="Map filters">
        <label>
          Type
          <select value={nodeType} onChange={(event) => setNodeType(event.target.value as MapNodeType | "all")}>
            {nodeTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label>
          Maturity
          <select value={maturity} onChange={(event) => setMaturity(event.target.value)}>
            {maturities.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label>
          Connection
          <select value={connection} onChange={(event) => setConnection(event.target.value as typeof connection)}>
            <option value="all">all</option>
            <option value="connected">connected</option>
            <option value="disconnected">disconnected</option>
          </select>
        </label>
      </div>

      <div className="map-canvas" data-testid="design-map">
        <div className="map-edge-list" aria-label="Relationships">
          {visibleEdges.length === 0 ? <p className="muted">No visible relationships.</p> : null}
          {visibleEdges.map((edge) => (
            <span key={edge.id}>
              {edge.fromId} {"->"} {edge.toId} · {edge.type}
            </span>
          ))}
        </div>
        <div className="map-node-grid">
          {filteredNodes.length === 0 ? <p className="muted">No map nodes match the current filters.</p> : null}
          {filteredNodes.map((node) => (
            <button
              className={`map-node ${node.connected ? "connected" : "disconnected"}`}
              key={node.id}
              onClick={() => void chooseNode(node)}
              type="button"
            >
              <strong>{node.label}</strong>
              <span>{node.nodeType}</span>
              <small>{node.maturity}</small>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
