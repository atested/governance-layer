/**
 * <atd-decision-tag>
 * ALLOW/DENY badge.
 * Spec v2 section 9.9.
 *
 * Attributes:
 *   decision - "ALLOW" | "DENY" | other
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: inline-block;
}

.tag {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  line-height: 1.4;
  text-transform: uppercase;
}

.tag--allow {
  color: var(--ok);
  background: var(--ok-soft);
}

.tag--deny {
  color: var(--danger);
  background: var(--danger-soft);
}

.tag--other {
  color: var(--muted);
  background: var(--line);
}
`;

export class AtdDecisionTag extends AtdBase {
  static get observedAttributes() { return ['decision']; }

  constructor() {
    super();
    this.addStyle(styles);
    this._render();
  }

  _render() {
    const decision = (this.getAttribute('decision') || '').toUpperCase();
    const variant = decision === 'ALLOW' ? 'allow' : decision === 'DENY' ? 'deny' : 'other';
    const label = decision || '--';

    this.shadowRoot.innerHTML = `<span class="tag tag--${variant}">${this._esc(label)}</span>`;
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

customElements.define('atd-decision-tag', AtdDecisionTag);
