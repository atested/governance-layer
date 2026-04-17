/**
 * <atd-data-table>
 * Sortable, paginated table with data-driven rendering.
 * Spec v2 section 9.5.
 *
 * Used by: Activity, Audit, Approvals, Health, Configuration, Feedback, Notifications.
 *
 * Attributes:
 *   columns    - JSON string: [{key, label, sortable?, width?}]
 *   page-size  - Rows per page (default: 50)
 *   sortable   - Enable column sort headers (default: true)
 *
 * Properties (set via JS):
 *   data        - Array of row objects
 *   totalCount  - Total rows for pagination (if server-side; defaults to data.length)
 *   currentPage - Current page number (1-based)
 *   cellRenderer - Optional function(row, column) returning HTML string for custom cells
 *
 * Events:
 *   table:sort      - { column: string, direction: "asc"|"desc" }
 *   table:page      - { page: number }
 *   table:row-click  - { row: object, index: number }
 *
 * Row highlighting:
 *   Rows with row._variant = "deny" get red tint.
 *   Rows with row._variant = "ungoverned" get amber tint.
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: block;
  font-family: var(--font-body);
}

.table-wrap {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  overflow-x: auto;
  overflow-y: hidden;
  background: var(--surface);
  -webkit-overflow-scrolling: touch;
}

table {
  width: 100%;
  border-collapse: collapse;
}

/* Header */
thead th {
  text-align: left;
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: var(--space-sm) var(--space-md);
  border-bottom: 1px solid var(--line);
  background: var(--surface-raised);
  user-select: none;
  white-space: nowrap;
}

thead th.sortable {
  cursor: pointer;
}
thead th.sortable:hover {
  color: var(--ink);
}

.sort-arrow {
  display: inline-block;
  margin-left: 4px;
  font-size: 0.7em;
  opacity: 0.4;
}
.sort-arrow.active {
  opacity: 1;
  color: var(--accent);
}

/* Body */
tbody td {
  font-size: var(--text-sm);
  color: var(--ink);
  padding: var(--space-sm) var(--space-md);
  border-bottom: 1px solid var(--line);
  vertical-align: top;
}

tbody tr {
  cursor: pointer;
  transition: background 0.1s;
}

tbody tr:hover {
  background: var(--surface-raised);
}

tbody tr:last-child td {
  border-bottom: none;
}

/* Row variants */
tbody tr.row--deny {
  background: var(--danger-soft);
}
tbody tr.row--deny:hover {
  background: rgba(239, 68, 68, 0.18);
}

tbody tr.row--ungoverned {
  background: var(--warn-soft);
}
tbody tr.row--ungoverned:hover {
  background: rgba(245, 158, 66, 0.18);
}

/* Empty state */
.empty {
  padding: var(--space-2xl);
  text-align: center;
  color: var(--muted);
  font-size: var(--text-sm);
  font-style: italic;
}

/* Pagination footer */
.footer {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-sm) var(--space-md);
  border-top: 1px solid var(--line);
  background: var(--surface-raised);
  gap: var(--space-md);
}

.footer button {
  font-family: var(--font-body);
  font-size: var(--text-xs);
  font-weight: 500;
  padding: 3px 12px;
  border-radius: 999px;
  cursor: pointer;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink);
  transition: background 0.15s, border-color 0.15s;
}

.footer button:hover:not(:disabled) {
  border-color: var(--muted);
  background: var(--surface);
}

.footer button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.footer .page-info {
  font-size: var(--text-xs);
  color: var(--muted);
  user-select: none;
}
`;

export class AtdDataTable extends AtdBase {
  static get observedAttributes() { return ['columns', 'page-size', 'sortable']; }

  constructor() {
    super();
    this.addStyle(styles);

    this._data = [];
    this._totalCount = 0;
    this._currentPage = 1;
    this._sortColumn = null;
    this._sortDirection = 'asc';
    this._cellRenderer = null;

    this._render();
  }

  /* ----- Properties ----- */

  get data() { return this._data; }
  set data(val) {
    this._data = Array.isArray(val) ? val : [];
    if (!this._totalCountExplicit) this._totalCount = this._data.length;
    this._render();
  }

  get totalCount() { return this._totalCount; }
  set totalCount(val) {
    this._totalCountExplicit = true;
    this._totalCount = parseInt(val, 10) || 0;
    this._render();
  }

  get currentPage() { return this._currentPage; }
  set currentPage(val) {
    this._currentPage = Math.max(1, parseInt(val, 10) || 1);
    this._render();
  }

  get cellRenderer() { return this._cellRenderer; }
  set cellRenderer(fn) {
    this._cellRenderer = typeof fn === 'function' ? fn : null;
    this._render();
  }

  /* ----- Derived ----- */

  get _columns() {
    try {
      const raw = this.getAttribute('columns');
      return raw ? JSON.parse(raw) : [];
    } catch { return []; }
  }

  get _pageSize() {
    return parseInt(this.getAttribute('page-size'), 10) || 50;
  }

  get _isSortable() {
    return this.getAttribute('sortable') !== 'false';
  }

  get _totalPages() {
    return Math.max(1, Math.ceil(this._totalCount / this._pageSize));
  }

  /* ----- Rendering ----- */

  _render() {
    const columns = this._columns;
    if (!columns.length) {
      this.shadowRoot.innerHTML = '<div class="empty">No columns defined</div>';
      return;
    }

    const pageSize = this._pageSize;
    const page = this._currentPage;
    const totalPages = this._totalPages;

    // Visible rows for current page (client-side pagination)
    const start = (page - 1) * pageSize;
    const visibleRows = this._data.slice(start, start + pageSize);

    const headerHTML = columns.map(col => {
      const isSortable = this._isSortable && col.sortable !== false;
      const isActive = this._sortColumn === col.key;
      const arrow = isSortable ? this._sortArrow(col.key, isActive) : '';
      const widthAttr = col.width ? ` style="width:${this._esc(col.width)}"` : '';
      const cls = isSortable ? ' class="sortable"' : '';
      return `<th${cls}${widthAttr} data-key="${this._esc(col.key)}">${this._esc(col.label || col.key)}${arrow}</th>`;
    }).join('');

    let bodyHTML;
    if (!visibleRows.length) {
      bodyHTML = `<tr><td colspan="${columns.length}" class="empty">No data</td></tr>`;
    } else {
      bodyHTML = visibleRows.map((row, i) => {
        const globalIndex = start + i;
        const variantClass = row._variant ? ` row--${row._variant}` : '';
        const cells = columns.map(col => {
          let cellContent;
          if (this._cellRenderer) {
            cellContent = this._cellRenderer(row, col);
          }
          if (cellContent == null) {
            const val = row[col.key];
            cellContent = this._esc(val != null ? String(val) : '--');
          }
          return `<td>${cellContent}</td>`;
        }).join('');
        return `<tr class="data-row${variantClass}" data-index="${globalIndex}">${cells}</tr>`;
      }).join('');
    }

    const showPagination = totalPages > 1;
    const paginationHTML = showPagination ? `
      <div class="footer">
        <button class="prev-btn"${page <= 1 ? ' disabled' : ''}>Previous</button>
        <span class="page-info">Page ${page} of ${totalPages}</span>
        <button class="next-btn"${page >= totalPages ? ' disabled' : ''}>Next</button>
      </div>` : '';

    this.shadowRoot.innerHTML = `
      <div class="table-wrap">
        <table>
          <thead><tr>${headerHTML}</tr></thead>
          <tbody>${bodyHTML}</tbody>
        </table>
        ${paginationHTML}
      </div>
    `;

    this._attachListeners();
  }

  _sortArrow(key, isActive) {
    if (!isActive) return '<span class="sort-arrow">\u25B3</span>';
    const arrow = this._sortDirection === 'asc' ? '\u25B2' : '\u25BC';
    return `<span class="sort-arrow active">${arrow}</span>`;
  }

  _attachListeners() {
    // Sort headers
    this.shadowRoot.querySelectorAll('th.sortable').forEach(th => {
      th.addEventListener('click', () => {
        const key = th.dataset.key;
        if (this._sortColumn === key) {
          this._sortDirection = this._sortDirection === 'asc' ? 'desc' : 'asc';
        } else {
          this._sortColumn = key;
          this._sortDirection = 'asc';
        }
        this.emit('table:sort', { column: this._sortColumn, direction: this._sortDirection });
        this._render();
      });
    });

    // Row clicks
    this.shadowRoot.querySelectorAll('tr.data-row').forEach(tr => {
      tr.addEventListener('click', () => {
        const index = parseInt(tr.dataset.index, 10);
        const row = this._data[index];
        if (row) this.emit('table:row-click', { row, index });
      });
    });

    // Pagination
    const prevBtn = this.shadowRoot.querySelector('.prev-btn');
    const nextBtn = this.shadowRoot.querySelector('.next-btn');
    if (prevBtn) {
      prevBtn.addEventListener('click', () => {
        if (this._currentPage > 1) {
          this._currentPage--;
          this.emit('table:page', { page: this._currentPage });
          this._render();
        }
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', () => {
        if (this._currentPage < this._totalPages) {
          this._currentPage++;
          this.emit('table:page', { page: this._currentPage });
          this._render();
        }
      });
    }
  }

  attributeChangedCallback() {
    this._render();
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }
}

customElements.define('atd-data-table', AtdDataTable);
