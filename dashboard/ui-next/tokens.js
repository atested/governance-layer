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
  --line: rgba(255, 255, 255, 0.12);
  --accent: #60a5fa;
  --accent-soft: rgba(96, 165, 250, 0.12);
  --ok: #22c55e;
  --ok-soft: rgba(34, 197, 94, 0.10);
  --warn: #f5a623;
  --warn-soft: rgba(245, 166, 35, 0.10);
  --danger: #ef4444;
  --danger-soft: rgba(239, 68, 68, 0.10);
  --shadow: none;

  --radius: 2px;
  --radius-sm: 2px;
  --radius-md: 2px;
  --radius-lg: 2px;

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
