/**
 * <atd-kv-list>
 * Key-value display for record detail fields.
 * Spec v2 section 9.14.
 *
 * Properties (set via JS):
 *   items - Array of { key: string, value: string, variant?: string }
 *           Variant: "code" (monospace), "danger" (red), "success" (green)
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: block;
  font-family: var(--font-body);
}

.list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.row {
  display: flex;
  padding: var(--space-sm) 0;
  border-bottom: 1px solid var(--line);
  gap: var(--space-lg);
  align-items: baseline;
}

.row:last-child {
  border-bottom: none;
}

.key {
  flex: 0 0 140px;
  font-size: var(--text-sm);
  color: var(--muted);
  text-align: left;
}

.key[data-tooltip] {
  position: relative;
  cursor: help;
}

.key[data-tooltip]::after {
  content: attr(data-tooltip);
  position: absolute;
  left: 0;
  bottom: calc(100% + 8px);
  z-index: 10000;
  width: max-content;
  max-width: 250px;
  padding: 8px 10px;
  background: #161b22;
  border: 1px dashed #30363d;
  border-radius: 2px;
  color: #e4e6eb;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.72rem;
  line-height: 1.35;
  white-space: normal;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transform: translateY(4px);
  transition: opacity 0.12s ease, transform 0.12s ease, visibility 0.12s ease;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.key[data-tooltip]:hover::after,
.key[data-tooltip]:focus-visible::after {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.value {
  flex: 1;
  font-size: var(--text-sm);
  color: var(--ink);
  word-break: break-word;
}

.value--code {
  font-family: var(--font-mono);
}

.value--danger {
  color: var(--danger);
}

.value--success {
  color: var(--ok);
}

.empty {
  color: var(--muted);
  font-size: var(--text-sm);
  font-style: italic;
  padding: var(--space-md) 0;
}
`;

export class AtdKvList extends AtdBase {
  constructor() {
    super();
    this.addStyle(styles);
    this._items = [];
    this._render();
  }

  get items() { return this._items; }

  set items(val) {
    this._items = Array.isArray(val) ? val : [];
    this._render();
  }

  _render() {
    if (!this._items.length) {
      this.shadowRoot.innerHTML = '<div class="empty">No data</div>';
      return;
    }

    const rows = this._items.map(item => {
      const variantClass = item.variant ? ` value--${item.variant}` : '';
      const tooltip = item.tooltip ? ` data-tooltip="${this._escAttr(item.tooltip)}" tabindex="0"` : '';
      return `
        <div class="row">
          <div class="key"${tooltip}>${this._esc(item.key || '')}</div>
          <div class="value${variantClass}">${this._esc(item.value != null ? String(item.value) : '--')}</div>
        </div>`;
    }).join('');

    this.shadowRoot.innerHTML = `<div class="list">${rows}</div>`;
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }

  _escAttr(str) {
    return this._esc(str).replace(/"/g, '&quot;');
  }
}

customElements.define('atd-kv-list', AtdKvList);
