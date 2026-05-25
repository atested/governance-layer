#!/usr/bin/env node
// QS-038 / Advisory #5 — dashboard JS module-link smoke test.
//
// Statically walks the ES-module import graph starting from the dashboard
// entry point(s) and fails if any relative import does not resolve to a
// file on disk. This catches the QS-025 black-screen class of bug — a
// renamed, moved, or deleted module silently breaking the import chain —
// before deployment.
//
// It is deliberately NOT a browser test. It performs pure module-link
// resolution: parse import/export-from/side-effect/dynamic-import
// specifiers, resolve relative paths, assert the target files exist, and
// recurse. No DOM, no `window`, no module execution.

import { readFileSync, existsSync, statSync } from "node:fs";
import { dirname, resolve, relative } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const UI_ROOT = resolve(SCRIPT_DIR, "..", "dashboard", "ui-next");

// index.html loads `<script type="module" src="./app.js">`. app.js is the
// single ES-module entry; font-loader.js is a classic script with no
// imports. Add entry points here if index.html gains more module roots.
const ENTRY_POINTS = ["app.js"];

// Matches `from '...'`, side-effect `import '...'`, and dynamic
// `import('...')`. The optional `\(?` covers the dynamic form.
const SPEC_RE = /\b(?:from|import)\s*\(?\s*["']([^"']+)["']/g;

function stripComments(source) {
  // Remove block comments, then line comments. The line-comment pattern
  // keeps `://` (URLs in string literals) intact. Good enough for import
  // extraction — import statements never contain `//`.
  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1");
}

function extractSpecifiers(source) {
  const specs = new Set();
  const cleaned = stripComments(source);
  let match;
  while ((match = SPEC_RE.exec(cleaned)) !== null) {
    specs.add(match[1]);
  }
  return specs;
}

const visited = new Set();
const missing = []; // { importer, specifier, resolved }

function walk(absFile) {
  if (visited.has(absFile)) return;
  visited.add(absFile);

  let source;
  try {
    source = readFileSync(absFile, "utf8");
  } catch {
    return; // existence is validated by the caller before recursing
  }

  for (const spec of extractSpecifiers(source)) {
    // Only relative/absolute specifiers are local module links. Bare
    // specifiers (npm packages) are out of scope for this smoke test.
    if (!spec.startsWith(".") && !spec.startsWith("/")) continue;

    const resolved = resolve(dirname(absFile), spec);
    if (!existsSync(resolved) || !statSync(resolved).isFile()) {
      missing.push({
        importer: relative(UI_ROOT, absFile),
        specifier: spec,
        resolved: relative(UI_ROOT, resolved),
      });
      continue;
    }
    walk(resolved);
  }
}

let entryError = false;
for (const entry of ENTRY_POINTS) {
  const abs = resolve(UI_ROOT, entry);
  if (!existsSync(abs)) {
    console.error(`ENTRY MISSING: ${entry} (looked in ${UI_ROOT})`);
    entryError = true;
    continue;
  }
  walk(abs);
}

if (entryError || missing.length > 0) {
  console.error(
    `\nmodule-link smoke FAILED: ${missing.length} unresolved import(s)`,
  );
  for (const x of missing) {
    console.error(`  ${x.importer} imports '${x.specifier}' -> missing ${x.resolved}`);
  }
  process.exit(1);
}

console.log(
  `module-link smoke OK: ${visited.size} modules reachable from ` +
    `${ENTRY_POINTS.join(", ")}; all relative imports resolve`,
);
