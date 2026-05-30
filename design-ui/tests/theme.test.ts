// DESIGN-UI-012: regression coverage for the theme layer.
//
// Static-text tests (no DOM): we assert the structural promises of the
// theme system are present in the source so a future refactor cannot
// silently delete the dark-mode contract:
//
//   1. app.css defines every required token at the :root level.
//   2. app.css ships a prefers-color-scheme: dark override that flips
//      every token under the same :root selector.
//   3. app.css exposes explicit [data-theme="light"] and
//      [data-theme="dark"] override blocks so the operator picker can
//      beat the media query.
//   4. The dark surface tokens use dark grays, not pure black (#000).
//   5. index.html embeds the synchronous no-flash boot script that
//      reads localStorage("design-ui:theme") and applies the matching
//      data-theme attribute before any CSS runs.
//   6. App.tsx renders a theme picker with System / Light / Dark
//      options, persists the choice under the same localStorage key,
//      and toggles the <html data-theme> attribute accordingly.
//   7. No raw hex literals remain in the production component CSS
//      rules — every colour reference goes through a var(--token).

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const css = readFileSync(new URL("../src/styles/app.css", import.meta.url), "utf8");
const html = readFileSync(new URL("../index.html", import.meta.url), "utf8");
const appTsx = readFileSync(new URL("../src/App.tsx", import.meta.url), "utf8");

const REQUIRED_TOKENS = [
  "--bg-primary",
  "--bg-secondary",
  "--surface-primary",
  "--surface-secondary",
  "--text-primary",
  "--text-secondary",
  "--border-color",
  "--success-bg",
  "--success-text",
  "--warning-bg",
  "--warning-text",
  "--error-bg",
];

test("app.css defines every required theme token at :root", () => {
  // Slice to the first :root block to make sure we're checking the base
  // layer rather than accidentally matching the same name later.
  const rootBlock = css.match(/:root\s*\{[\s\S]*?\}/);
  assert.ok(rootBlock, ":root block must be defined");
  for (const token of REQUIRED_TOKENS) {
    assert.match(
      rootBlock![0],
      new RegExp(`${token}\\s*:`),
      `:root must define ${token}`,
    );
  }
});

test("app.css ships a prefers-color-scheme dark override that redefines the tokens", () => {
  // The dark media query block must redefine the same tokens so a
  // system-dark-preference visit picks them up without any operator
  // action.
  const darkMediaBlock = css.match(
    /@media\s*\(\s*prefers-color-scheme:\s*dark\s*\)\s*\{[\s\S]*?:root\s*\{[\s\S]*?\}\s*\}/,
  );
  assert.ok(
    darkMediaBlock,
    "app.css must contain @media (prefers-color-scheme: dark) { :root { ... } }",
  );
  for (const token of REQUIRED_TOKENS) {
    assert.match(
      darkMediaBlock![0],
      new RegExp(`${token}\\s*:`),
      `prefers-color-scheme dark block must redefine ${token}`,
    );
  }
});

test("app.css exposes explicit operator overrides for both themes", () => {
  assert.match(css, /\[data-theme="light"\]\s*\{[\s\S]*?--bg-primary/);
  assert.match(css, /\[data-theme="dark"\]\s*\{[\s\S]*?--bg-primary/);
});

test("dark surface tokens use dark grays, not pure black", () => {
  // Pull the dark-theme override block and ensure no surface token
  // points at #000 / #000000 / black.
  const darkBlock = css.match(/\[data-theme="dark"\]\s*\{([\s\S]*?)\}/);
  assert.ok(darkBlock, "dark theme block must exist");
  const body = darkBlock![1];
  for (const blackForm of ["#000", "#000000", "black"]) {
    assert.doesNotMatch(
      body,
      new RegExp(`:\\s*${blackForm}\\b`),
      `dark theme must not use ${blackForm} as a surface colour`,
    );
  }
  // Surface primary must be a dark gray (starts with #1, #2, or #3 in hex).
  assert.match(body, /--surface-primary:\s*#[123]/);
  assert.match(body, /--bg-primary:\s*#[123]/);
});

test("index.html embeds the synchronous no-flash boot script", () => {
  // The script must read the same localStorage key the React picker
  // writes to, must set data-theme synchronously, and must guard against
  // localStorage throwing.
  assert.match(html, /design-ui:theme/);
  assert.match(html, /setAttribute\("data-theme"/);
  assert.match(html, /try\s*\{[\s\S]*?localStorage\.getItem/);
  assert.match(html, /catch/);
  // The boot script must NOT be a deferred module — it has to run before
  // first paint, which means a plain <script> in <head> with no defer.
  const beforeBody = html.split("<body>")[0];
  assert.match(beforeBody, /<script>[\s\S]*?localStorage[\s\S]*?<\/script>/);
});

test("App.tsx renders the theme picker with system/light/dark options", () => {
  // The picker container must be rendered with a stable testid the
  // future E2E layer can hook into.
  assert.match(appTsx, /data-testid="theme-picker"/);
  // The picker must declare a themeLabels record (the TypeScript type
  // annotation may sit between the identifier and `=`, hence the loose
  // pattern below). All three options must be keys of that record.
  const themeLabelsBlock = appTsx.match(/themeLabels[^=]*=\s*\{[\s\S]*?\};/);
  assert.ok(themeLabelsBlock, "themeLabels record must be declared in App.tsx");
  for (const opt of ["system", "light", "dark"]) {
    assert.match(
      themeLabelsBlock![0],
      new RegExp(`\\b${opt}\\s*:`),
      `themeLabels must include the ${opt} key`,
    );
  }
  // The picker must persist under the same key the boot script reads.
  assert.match(appTsx, /design-ui:theme/);
  assert.match(appTsx, /localStorage\.setItem/);
  // The picker must remove the attribute for "system" so the media query
  // takes over, and set it for explicit overrides.
  assert.match(appTsx, /removeAttribute\("data-theme"\)/);
  assert.match(appTsx, /setAttribute\("data-theme",/);
});

test("no raw hex literals remain in component-level CSS rules", () => {
  // Token definitions (lines that start with `--`) ARE allowed to use
  // hex literals — that's where the palette is centralised. Production
  // selector rules must reference var(--token) instead. This test
  // protects against a hard-coded colour quietly reappearing in a
  // future PR.
  const tokenLineRe = /^\s*--[a-z-]+\s*:/;
  const hexRe = /#[0-9a-fA-F]{3,8}/;
  const lines = css.split(/\r?\n/);
  const offenders: string[] = [];
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (tokenLineRe.test(line)) continue;
    if (line.trim().startsWith("/*") || line.trim().startsWith("*")) continue;
    if (line.trim().startsWith("//")) continue;
    if (hexRe.test(line)) {
      offenders.push(`line ${i + 1}: ${line.trim()}`);
    }
  }
  assert.deepEqual(
    offenders,
    [],
    `component rules must use var(--token), found raw hex literals:\n${offenders.join("\n")}`,
  );
});
