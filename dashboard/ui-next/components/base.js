/**
 * Base class for all Atested Web Components.
 * Handles Shadow DOM creation and design token adoption.
 */

import { tokenSheet } from '../tokens.js';

export class AtdBase extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.adoptedStyleSheets = [tokenSheet];
  }

  /**
   * Add a component-specific stylesheet to this component's Shadow DOM.
   * Call in the subclass constructor after super().
   */
  addStyle(css) {
    const sheet = new CSSStyleSheet();
    sheet.replaceSync(css);
    this.shadowRoot.adoptedStyleSheets = [
      ...this.shadowRoot.adoptedStyleSheets,
      sheet
    ];
  }

  /**
   * Emit a custom event that bubbles and crosses Shadow DOM boundaries.
   */
  emit(name, detail = null) {
    this.dispatchEvent(new CustomEvent(name, {
      bubbles: true,
      composed: true,
      detail
    }));
  }
}
