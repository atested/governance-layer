/**
 * Design token stylesheet for adoptedStyleSheets sharing.
 * All Web Components adopt this sheet so design tokens are
 * available inside Shadow DOM without duplication.
 */

const tokenCSS = `
:host {
  --bg: #1a1d23;
  --surface: #22262e;
  --surface-raised: #2a2f38;
  --ink: #e4e6eb;
  --muted: #8b919a;
  --line: rgba(255, 255, 255, 0.08);
  --accent: #5b8af5;
  --accent-soft: rgba(91, 138, 245, 0.12);
  --ok: #4ade80;
  --ok-soft: rgba(74, 222, 128, 0.10);
  --warn: #f59e42;
  --warn-soft: rgba(245, 158, 66, 0.10);
  --danger: #ef4444;
  --danger-soft: rgba(239, 68, 68, 0.10);
  --shadow: 0 4px 24px rgba(0, 0, 0, 0.25);

  --radius: 12px;
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 10px;

  --font-body: "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
  --text-xs: 0.82rem;
  --text-sm: 0.9rem;
  --text-base: 1rem;
  --text-lg: 1.35rem;
  --text-stat: 1.7rem;

  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 12px;
  --space-lg: 16px;
  --space-xl: 20px;
  --space-2xl: 24px;

  --shell-max-width: 1400px;
  --chrome-height: 48px;
}
`;

export const tokenSheet = new CSSStyleSheet();
tokenSheet.replaceSync(tokenCSS);
