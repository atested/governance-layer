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
      <div class="card"${tooltip ? ` title="${this._esc(tooltip)}"` : ''}>
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
      el.title = this.getAttribute('tooltip') || '';
    }
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }
}

customElements.define('atd-status-card', AtdStatusCard);
