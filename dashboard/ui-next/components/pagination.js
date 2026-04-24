/**
 * <atd-pagination>
 * Previous/Next controls with page indicator.
 *
 * Attributes:
 *   current-page - Current page number (1-based)
 *   total-pages  - Total number of pages
 *
 * Events:
 *   page-change - carries { page: number }
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-md);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  padding: var(--space-md) 0;
}

button {
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 500;
  padding: 4px 14px;
  border-radius: 2px;
  cursor: pointer;
  border: 1px dashed var(--line);
  background: transparent;
  color: var(--ink);
  transition: background 0.15s, border-color 0.15s;
  line-height: 1.4;
}

button:hover:not(:disabled) {
  border-color: var(--muted);
  background: var(--surface-raised);
}

button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.indicator {
  color: var(--muted);
  user-select: none;
}
`;

export class AtdPagination extends AtdBase {
  static get observedAttributes() { return ['current-page', 'total-pages']; }

  constructor() {
    super();
    this.addStyle(styles);
    this._render();
  }

  get currentPage() {
    return Math.max(1, parseInt(this.getAttribute('current-page'), 10) || 1);
  }

  get totalPages() {
    return Math.max(1, parseInt(this.getAttribute('total-pages'), 10) || 1);
  }

  _render() {
    const page = this.currentPage;
    const total = this.totalPages;

    this.shadowRoot.innerHTML = `
      <button class="prev"${page <= 1 ? ' disabled' : ''}>Previous</button>
      <span class="indicator">Page ${page} of ${total}</span>
      <button class="next"${page >= total ? ' disabled' : ''}>Next</button>
    `;

    this.shadowRoot.querySelector('.prev').addEventListener('click', () => {
      if (this.currentPage > 1) {
        this.emit('page-change', { page: this.currentPage - 1 });
      }
    });

    this.shadowRoot.querySelector('.next').addEventListener('click', () => {
      if (this.currentPage < this.totalPages) {
        this.emit('page-change', { page: this.currentPage + 1 });
      }
    });
  }

  attributeChangedCallback() {
    this._render();
  }
}

customElements.define('atd-pagination', AtdPagination);
