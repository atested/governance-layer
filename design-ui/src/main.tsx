// DESIGN-UI-011: switched from default imports
//   import React from "react"
//   import ReactDOM from "react-dom/client"
// to named imports
//   import { StrictMode } from "react"
//   import { createRoot } from "react-dom/client"
// to bypass Vite 7's CJS-interop shim around the React 19 ESM exports.
// Under that shim, when the dependency optimizer ends up in certain
// states, the dev-mode transform of main.tsx 500's and Safari ends up
// fetching a literal `/react-dom/client` (shown as "client" in the
// Network panel, 404). The named-import form does not go through the
// CJS shim and avoids both failure modes. Behaviour is unchanged.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "dockview/dist/styles/dockview.css";
import "./styles/app.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
