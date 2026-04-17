/**
 * <atd-tier-badge>
 * Confidence tier indicator.
 * Spec v2 section 9.10.
 *
 * Attributes:
 *   tier - 1, 2, 3, or 4
 *
 * Rendering:
 *   Tiers 1-2: green
 *   Tiers 3-4: amber
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: inline-block;
}

.badge {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  line-height: 1.4;
}

.badge--green {
  color: var(--ok);
  background: var(--ok-soft);
}

.badge--amber {
  color: var(--warn);
  background: var(--warn-soft);
}
`;

export class AtdTierBadge extends AtdBase {
  static get observedAttributes() { return ['tier']; }

  constructor() {
    super();
    this.addStyle(styles);
    this._render();
  }

  _render() {
    const tier = parseInt(this.getAttribute('tier'), 10);
    const valid = tier >= 1 && tier <= 4;
    const variant = valid && tier <= 2 ? 'green' : 'amber';
    const label = valid ? `Tier ${tier}` : '--';

    this.shadowRoot.innerHTML = `<span class="badge badge--${variant}">${label}</span>`;
  }

  attributeChangedCallback() {
    this._render();
  }
}

customElements.define('atd-tier-badge', AtdTierBadge);
