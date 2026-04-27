/**
 * <atd-pill>
 * Rounded bordered button.
 *
 * Attributes:
 *   variant  - "primary" | "danger" | "outline" (default: "outline")
 *   disabled - When present, button is disabled
 *
 * Events:
 *   click - standard click (does not fire when disabled)
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: inline-block;
}

button {
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 500;
  padding: 6px 16px;
  border-radius: 2px;
  cursor: pointer;
  border: 1px dashed transparent;
  transition: background 0.15s, border-color 0.15s, color 0.15s, opacity 0.15s;
  line-height: 1.4;
}

button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

/* Outline (default) */
button.outline {
  background: transparent;
  border-color: var(--muted);
  color: var(--ink);
}
button.outline:hover:not(:disabled) {
  border-color: var(--muted);
  background: var(--surface-raised);
}

/* Primary */
button.primary {
  background: var(--accent);
  color: #fff;
}
button.primary:hover:not(:disabled) {
  background: #5580aa;
}

/* Danger */
button.danger {
  background: var(--danger);
  color: #fff;
}
button.danger:hover:not(:disabled) {
  background: #d63d3d;
}
`;

export class AtdPill extends AtdBase {
  static get observedAttributes() { return ['variant', 'disabled']; }

  constructor() {
    super();
    this.addStyle(styles);
    this._render();
  }

  _render() {
    const variant = this.getAttribute('variant') || 'outline';
    const disabled = this.hasAttribute('disabled');

    this.shadowRoot.innerHTML = `
      <button class="${variant}"${disabled ? ' disabled' : ''}>
        <slot></slot>
      </button>
    `;
  }

  attributeChangedCallback() {
    this._render();
  }
}

customElements.define('atd-pill', AtdPill);
