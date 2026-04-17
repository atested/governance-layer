/**
 * <atd-status-grid>
 * Auto-fit responsive grid of status cards.
 * Spec v2 section 9.4.
 *
 * Slots:
 *   default - <atd-status-card> elements
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-md);
}
`;

export class AtdStatusGrid extends AtdBase {
  constructor() {
    super();
    this.addStyle(styles);
    this.shadowRoot.innerHTML = '<slot></slot>';
  }
}

customElements.define('atd-status-grid', AtdStatusGrid);
