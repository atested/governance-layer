import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const routeSource = readFileSync(new URL("../src/routes/DesignRoute.tsx", import.meta.url), "utf8");
const cssSource = readFileSync(new URL("../src/styles/app.css", import.meta.url), "utf8");

test("/design route keeps Discovery and Purpose surfaces present", () => {
  assert.match(routeSource, /data-testid="discovery-surface"/);
  assert.match(routeSource, /data-testid="purpose-surface"/);
  assert.match(routeSource, /type Focus = "discovery" \| "purpose"/);
  assert.match(routeSource, /surface-layout focus-\$\{focus\}/);
  assert.doesNotMatch(routeSource, /<Tabs|role="tablist"/);
});

test("/design route includes manual fallback and proposal approval controls", () => {
  assert.match(routeSource, /Add Discovery/);
  assert.match(routeSource, /Add Purpose/);
  assert.match(routeSource, /Promote/);
  assert.match(routeSource, /Demote/);
  assert.match(routeSource, /Accept/);
  assert.match(routeSource, /Reject/);
});

test("focus CSS changes grid ratio without hiding either surface", () => {
  assert.match(cssSource, /\.surface-layout\.focus-discovery[\s\S]*grid-template-columns: minmax\(0, 3fr\) minmax\(240px, 1fr\)/);
  assert.match(cssSource, /\.surface-layout\.focus-purpose[\s\S]*grid-template-columns: minmax\(240px, 1fr\) minmax\(0, 3fr\)/);
  assert.doesNotMatch(cssSource, /display:\s*none/);
});
