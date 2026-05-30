import { useEffect, useMemo, useState } from "react";
import { getHealth } from "./api/client";
import { DesignRoute } from "./routes/DesignRoute";
import { MapRoute } from "./routes/MapRoute";
import { SpecRoute } from "./routes/SpecRoute";

type RouteKey = "/design" | "/map" | "/spec";

const routeLabels: Record<RouteKey, string> = {
  "/design": "Design",
  "/map": "Map",
  "/spec": "Spec"
};

function currentRoute(): RouteKey {
  const path = window.location.pathname;
  if (path === "/map" || path === "/spec" || path === "/design") return path;
  return "/design";
}

export function App() {
  const [route, setRoute] = useState<RouteKey>(currentRoute());
  const [health, setHealth] = useState<"checking" | "ok" | "down">("checking");

  useEffect(() => {
    getHealth()
      .then(() => setHealth("ok"))
      .catch(() => setHealth("down"));
  }, []);

  useEffect(() => {
    const onPopState = () => setRoute(currentRoute());
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const body = useMemo(() => {
    if (route === "/map") return <MapRoute />;
    if (route === "/spec") return <SpecRoute />;
    return <DesignRoute />;
  }, [route]);

  const navigate = (next: RouteKey) => {
    window.history.pushState({}, "", next);
    setRoute(next);
  };

  return (
    <main className="app-shell">
      <header className="app-header">
        <div>
          <h1>Design UI v1</h1>
          <p>Foundation scaffold for discovery, purpose, map, and spec work.</p>
        </div>
        <div className={`health health-${health}`}>API {health}</div>
      </header>
      <nav className="app-nav" aria-label="Primary">
        {(Object.keys(routeLabels) as RouteKey[]).map((path) => (
          <button
            className={path === route ? "active" : ""}
            key={path}
            onClick={() => navigate(path)}
            type="button"
          >
            {routeLabels[path]}
          </button>
        ))}
      </nav>
      {body}
    </main>
  );
}
