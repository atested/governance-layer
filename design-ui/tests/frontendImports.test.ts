// DESIGN-UI-011: regression coverage for the Vite 7 + React 19 dev-mode
// transform failure that produced a blank /design screen on Safari.
//
// Two source-level anti-patterns produced the failure:
//
//   1. main.tsx using `import React from "react"` + `import ReactDOM
//      from "react-dom/client"` (default-form), which routes the imports
//      through Vite's CJS-interop shim. The shim is fragile against
//      React 19's ESM exports; when the dependency optimizer ends up in
//      certain states, the dev-mode transform of main.tsx 500s and
//      Safari ends up trying to fetch /react-dom/client (shown as
//      "client" in the Network panel, 404).
//
//   2. DesignRoute.tsx importing FormEvent on the same line as runtime
//      hooks: `import { FormEvent, useEffect, useMemo, useState } from
//      "react"`. FormEvent is a .d.ts-only export — it isn't exported as
//      a runtime value by react. esbuild auto-detection usually strips
//      it but Vite 7's stricter import rewriting can fail the transform.
//
// These tests assert the corrected patterns are in the source so the
// bug cannot reappear silently the next time someone refactors these
// files.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const mainTsx = readFileSync(new URL("../src/main.tsx", import.meta.url), "utf8");
const viteConfigTs = readFileSync(new URL("../vite.config.ts", import.meta.url), "utf8");
const designRouteTsx = readFileSync(
  new URL("../src/routes/DesignRoute.tsx", import.meta.url),
  "utf8",
);

test("main.tsx uses named imports for React 19 + Vite 7", () => {
  // Required: named imports that bypass Vite's CJS-interop shim.
  assert.match(mainTsx, /import \{ StrictMode \} from "react";/);
  assert.match(mainTsx, /import \{ createRoot \} from "react-dom\/client";/);
  // Forbidden: default imports route React/ReactDOM through the CJS shim
  // and reintroduce the dev-mode 500 / "client" 404 failure.
  assert.doesNotMatch(mainTsx, /^import React from "react"/m);
  assert.doesNotMatch(mainTsx, /^import ReactDOM from "react-dom\/client"/m);
  // The entry must call createRoot directly (no ReactDOM.createRoot).
  assert.match(mainTsx, /createRoot\(/);
  assert.doesNotMatch(mainTsx, /ReactDOM\.createRoot/);
  // <StrictMode> must remain.
  assert.match(mainTsx, /<StrictMode>/);
});

test("Vite resolves Dockview package CSS through an exact alias", () => {
  assert.match(mainTsx, /import "dockview\/dist\/styles\/dockview\.css";/);
  assert.match(viteConfigTs, /"dockview\/dist\/styles\/dockview\.css"/);
  assert.match(viteConfigTs, /node_modules\/dockview\/dist\/styles\/dockview\.css/);
});

test("DesignRoute imports FormEvent as a type, not as a value", () => {
  // Required: FormEvent imported through `import type`.
  assert.match(designRouteTsx, /import type \{ FormEvent \} from "react";/);
  // Forbidden: FormEvent appearing in a value-mode `import { ... }` from
  // react. We allow the standalone `import type` line above; the regex
  // below specifically catches the mixed value+type pattern that was the
  // original bug.
  assert.doesNotMatch(
    designRouteTsx,
    /import \{[^}]*\bFormEvent\b[^}]*\} from "react"/,
  );
});

test("no other source file value-imports React-only type names", () => {
  // Belt-and-braces guard against the same anti-pattern reappearing in
  // a future route. The list mirrors the React .d.ts exports most often
  // misimported under isolatedModules.
  const typeOnlyNames = [
    "FormEvent", "ChangeEvent", "MouseEvent", "KeyboardEvent",
    "ReactNode", "ReactElement", "FC", "FunctionComponent",
    "ComponentProps", "PropsWithChildren", "RefObject",
    "MutableRefObject", "CSSProperties", "HTMLAttributes",
    "SyntheticEvent",
  ];
  const sources = [
    new URL("../src/App.tsx", import.meta.url),
    new URL("../src/routes/MapRoute.tsx", import.meta.url),
    new URL("../src/routes/SpecRoute.tsx", import.meta.url),
  ];
  for (const src of sources) {
    const text = readFileSync(src, "utf8");
    for (const name of typeOnlyNames) {
      // Catch the mixed `import { A, name, B } from "react"` shape. A
      // standalone `import type { name } from "react"` is fine and is
      // not matched here.
      const pattern = new RegExp(
        `import \\{[^}]*\\b${name}\\b[^}]*\\} from "react"`,
      );
      assert.doesNotMatch(
        text,
        pattern,
        `${src.pathname} value-imports ${name} from "react"`,
      );
    }
  }
});
