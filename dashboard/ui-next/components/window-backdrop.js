/**
 * <atd-window-backdrop>
 * Overlay behind windows that communicates locked state.
 * Spec v2 section 9.2.
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  position: fixed;
  inset: 0;
  z-index: var(--z-index, 100);
}
.backdrop {
  width: 100%;
  height: 100%;
}
:host([depth="1"]) .backdrop {
  background: rgba(0, 0, 0, 0.5);
}
:host([depth="2"]) .backdrop {
  background: rgba(0, 0, 0, 0.3);
}
.backdrop {
  animation: fadeIn 0.15s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
`;

export class AtdWindowBackdrop extends AtdBase {
  static get observedAttributes() { return ['depth']; }

  constructor() {
    super();
    this.addStyle(styles);
    this.shadowRoot.innerHTML = '<div class="backdrop"></div>';
    this.shadowRoot.querySelector('.backdrop').addEventListener('click', () => {
      this.emit('backdrop:click');
    });
  }
}

customElements.define('atd-window-backdrop', AtdWindowBackdrop);
