/**
 * <atd-window-frame>
 * Modal container for child and grandchild windows.
 * Spec v2 section 9.1.
 *
 * Attributes:
 *   title  - Window title displayed in the title bar
 *   depth  - 1 (child) or 2 (grandchild), controls sizing and shadow
 *
 * Events:
 *   frame:close - emitted when close button is clicked
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  position: fixed;
  z-index: var(--z-index, 200);
  display: flex;
  align-items: flex-start;
  justify-content: center;
}

.frame {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.2s ease-out;
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Child window: 90% viewport width, max 1300px, 85% viewport height */
:host([depth="1"]) {
  inset: 0;
  padding-top: calc(var(--chrome-height) + 12px);
}
:host([depth="1"]) .frame {
  width: 90vw;
  max-width: 1300px;
  height: 85vh;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

/* Grandchild window: 80% of child dimensions */
:host([depth="2"]) {
  inset: 0;
  padding-top: calc(var(--chrome-height) + 12px);
}
:host([depth="2"]) .frame {
  width: calc(90vw * 0.8);
  max-width: calc(1300px * 0.8);
  height: calc(85vh * 0.8);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5);
}
:host([depth="2"]) .title-bar {
  border-bottom: 3px solid var(--grandchild-accent, var(--line));
}

.title-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-md) var(--space-xl);
  border-bottom: 1px solid var(--line);
  flex-shrink: 0;
  background: var(--surface-raised);
}

.title-group {
  display: flex;
  align-items: baseline;
  gap: 0;
  min-width: 0;
  overflow: hidden;
}
.title {
  font-family: var(--font-body);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--ink);
  margin: 0;
  user-select: none;
  flex-shrink: 0;
}
.subtitle {
  font-family: var(--font-body);
  font-size: 0.78rem;
  font-weight: 400;
  color: var(--muted);
  margin: 0;
  user-select: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.close-btn {
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  color: var(--muted);
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 2px 8px;
  transition: color 0.15s, border-color 0.15s;
}
.close-btn:hover {
  color: var(--ink);
  border-color: var(--muted);
}
.close-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-xl);
}
`;

export class AtdWindowFrame extends AtdBase {
  static get observedAttributes() { return ['title', 'subtitle', 'depth']; }

  constructor() {
    super();
    this.addStyle(styles);
    this._render();
  }

  _render() {
    const title = this.getAttribute('title') || '';
    const subtitle = this.getAttribute('subtitle') || '';
    const subtitleHtml = subtitle
      ? ` <span class="subtitle">\u2014 ${this._esc(subtitle)}</span>`
      : '';
    this.shadowRoot.innerHTML = `
      <div class="frame">
        <div class="title-bar">
          <div class="title-group">
            <span class="title">${this._esc(title)}</span>${subtitleHtml}
          </div>
          <button class="close-btn" aria-label="Close window">&times;</button>
        </div>
        <div class="content">
          <slot></slot>
        </div>
      </div>
    `;
    this.shadowRoot.querySelector('.close-btn').addEventListener('click', () => {
      this.emit('frame:close');
    });
  }

  attributeChangedCallback(name) {
    if (name === 'title') {
      const titleEl = this.shadowRoot.querySelector('.title');
      if (titleEl) titleEl.textContent = this.getAttribute('title') || '';
    }
    if (name === 'subtitle') {
      const sub = this.getAttribute('subtitle') || '';
      let subEl = this.shadowRoot.querySelector('.subtitle');
      if (sub) {
        if (!subEl) {
          subEl = document.createElement('span');
          subEl.className = 'subtitle';
          const group = this.shadowRoot.querySelector('.title-group');
          if (group) group.appendChild(subEl);
        }
        subEl.textContent = `\u2014 ${sub}`;
      } else if (subEl) {
        subEl.remove();
      }
    }
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }
}

customElements.define('atd-window-frame', AtdWindowFrame);
