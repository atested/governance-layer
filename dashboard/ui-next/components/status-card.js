/**
 * <atd-status-card>
 * Eyebrow label above a large value.
 * Spec v2 section 9.3.
 *
 * Attributes:
 *   label     - Eyebrow text (muted uppercase)
 *   value     - Large display value
 *   variant   - "default" | "danger" | "warning" | "success" (controls value color)
 *   clickable - When present, applies hover styling and emits card:click
 *   tooltip   - Optional tooltip text
 *
 * Events:
 *   card:click - emitted when clicked and clickable is present
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: block;
}

.card {
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: var(--radius-lg);
  padding: var(--space-lg) var(--space-xl);
  font-family: var(--font-body);
  position: relative;
}

:host([clickable]) .card {
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
:host([clickable]) .card:hover {
  border-color: var(--accent);
  background: var(--surface-raised);
}

.label {
  font-size: var(--text-xs);
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: var(--space-xs);
  line-height: 1.4;
}

.value {
  font-size: var(--text-stat);
  font-weight: 600;
  color: var(--ink);
  line-height: 1.2;
}

:host([variant="danger"]) .value { color: var(--danger); }
:host([variant="warning"]) .value { color: var(--warn); }
:host([variant="success"]) .value { color: var(--ok); }

.card[data-tooltip]::after {
  content: attr(data-tooltip);
  position: absolute;
  left: 50%;
  bottom: calc(100% + 8px);
  transform: translate(-50%, 4px);
  z-index: 20;
  box-sizing: border-box;
  width: max-content;
  max-width: 250px;
  padding: 7px 10px;
  background: #161b22;
  border: 1px dashed #30363d;
  border-radius: 2px;
  color: #d7dde6;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.68rem;
  font-weight: 400;
  line-height: 1.45;
  text-align: left;
  white-space: normal;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.08s ease, transform 0.08s ease;
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
}
.card[data-tooltip]::before {
  content: "";
  position: absolute;
  left: 50%;
  bottom: calc(100% + 2px);
  transform: translateX(-50%);
  z-index: 21;
  border: 6px solid transparent;
  border-top-color: #30363d;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.08s ease;
}
.card[data-tooltip]:hover::after,
.card[data-tooltip]:focus-visible::after,
.card[data-tooltip]:hover::before,
.card[data-tooltip]:focus-visible::before {
  opacity: 1;
}
.card[data-tooltip]:hover::after,
.card[data-tooltip]:focus-visible::after {
  transform: translate(-50%, 0);
}
`;

export class AtdStatusCard extends AtdBase {
  static get observedAttributes() { return ['label', 'value', 'variant', 'clickable', 'tooltip']; }

  constructor() {
    super();
    this.addStyle(styles);
    this._render();
  }

  _render() {
    const label = this.getAttribute('label') || '';
    const value = this.getAttribute('value') || '--';
    const tooltip = this.getAttribute('tooltip') || '';

    this.shadowRoot.innerHTML = `
      <div class="card"${tooltip ? ` data-tooltip="${this._escAttr(tooltip)}"` : ''}>
        <div class="label">${this._esc(label)}</div>
        <div class="value">${this._esc(value)}</div>
      </div>
    `;

    this.shadowRoot.querySelector('.card').addEventListener('click', () => {
      if (this.hasAttribute('clickable')) {
        this.emit('card:click');
      }
    });
  }

  attributeChangedCallback(name) {
    const el = this.shadowRoot.querySelector(`.${name === 'tooltip' ? 'card' : name}`);
    if (!el) return;
    if (name === 'label' || name === 'value') {
      el.textContent = this.getAttribute(name) || (name === 'value' ? '--' : '');
    } else if (name === 'tooltip') {
      const tooltip = this.getAttribute('tooltip') || '';
      if (tooltip) el.dataset.tooltip = tooltip;
      else delete el.dataset.tooltip;
    }
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }

  _escAttr(str) {
    return (str || '')
      .replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
}

customElements.define('atd-status-card', AtdStatusCard);
