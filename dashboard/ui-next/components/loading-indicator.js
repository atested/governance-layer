/**
 * <atd-loading-indicator> — Animated loading indicator.
 * Spec v2 section 9.16.
 *
 * Renders a pulsing dot animation with optional label text.
 * Used inside window content areas between open and data arrival.
 *
 * Attributes:
 *   label — text to show below the animation (default: "Loading")
 */

import { AtdBase } from './base.js';

const STYLE = `
  :host {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 40px 0;
    gap: 12px;
  }
  .dots {
    display: flex;
    gap: 6px;
  }
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent, #60a5fa);
    opacity: 0.3;
    animation: pulse 1.2s ease-in-out infinite;
  }
  .dot:nth-child(2) { animation-delay: 0.2s; }
  .dot:nth-child(3) { animation-delay: 0.4s; }
  @keyframes pulse {
    0%, 100% { opacity: 0.3; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.3); }
  }
  .label {
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    color: var(--muted, #8b919a);
  }
`;

class AtdLoadingIndicator extends AtdBase {
  constructor() {
    super();
    this.addStyle(STYLE);
    this.shadowRoot.innerHTML = `
      <div class="dots">
        <div class="dot"></div>
        <div class="dot"></div>
        <div class="dot"></div>
      </div>
      <span class="label"></span>
    `;
  }

  static get observedAttributes() { return ['label']; }

  attributeChangedCallback() {
    this._render();
  }

  connectedCallback() {
    this._render();
  }

  _render() {
    const label = this.getAttribute('label') || 'Loading';
    this.shadowRoot.querySelector('.label').textContent = label;
  }
}

customElements.define('atd-loading-indicator', AtdLoadingIndicator);
