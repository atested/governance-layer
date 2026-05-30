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

// DESIGN-UI-012: theme preference state.
//
// "system" means "follow the OS via the prefers-color-scheme media query"
// and is represented in the DOM by the ABSENCE of a data-theme attribute on
// <html>. "light" and "dark" are explicit operator overrides that beat the
// media query via [data-theme="…"] selector specificity in app.css.
type ThemePreference = "system" | "light" | "dark";
const THEME_STORAGE_KEY = "design-ui:theme";
const themeLabels: Record<ThemePreference, string> = {
  system: "System",
  light: "Light",
  dark: "Dark"
};

function readStoredTheme(): ThemePreference {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (raw === "light" || raw === "dark" || raw === "system") return raw;
  } catch {
    /* localStorage unavailable (private mode); fall through to system. */
  }
  return "system";
}

function applyTheme(theme: ThemePreference) {
  // "system" removes the override and lets prefers-color-scheme decide.
  if (theme === "system") {
    document.documentElement.removeAttribute("data-theme");
  } else {
    document.documentElement.setAttribute("data-theme", theme);
  }
}

function currentRoute(): RouteKey {
  const path = window.location.pathname;
  if (path === "/map" || path === "/spec" || path === "/design") return path;
  return "/design";
}

export function App() {
  const [route, setRoute] = useState<RouteKey>(currentRoute());
  const [health, setHealth] = useState<"checking" | "ok" | "down">("checking");
  const [theme, setThemeState] = useState<ThemePreference>(readStoredTheme);

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

  // DESIGN-UI-012: apply the picked theme and persist the choice so the
  // boot script in index.html can reapply it on the next reload before
  // first paint.
  useEffect(() => {
    applyTheme(theme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme);
    } catch {
      /* private mode — operator change applies for the session only. */
    }
  }, [theme]);

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
        <div className="app-header-tools">
          <div
            aria-label="Theme"
            className="theme-picker"
            data-testid="theme-picker"
            role="group"
          >
            {(Object.keys(themeLabels) as ThemePreference[]).map((value) => (
              <button
                aria-pressed={theme === value}
                className={theme === value ? "active" : ""}
                data-theme-option={value}
                key={value}
                onClick={() => setThemeState(value)}
                type="button"
              >
                {themeLabels[value]}
              </button>
            ))}
          </div>
          <div className={`health health-${health}`}>API {health}</div>
        </div>
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
