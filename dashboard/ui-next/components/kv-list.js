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
      return `
        <div class="row">
          <div class="key">${this._esc(item.key || '')}</div>
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
}

customElements.define('atd-kv-list', AtdKvList);
