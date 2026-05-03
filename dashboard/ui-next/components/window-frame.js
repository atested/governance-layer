/**
 * <atd-window-frame>
 * Modal container for child and grandchild windows.
 * Spec v2 section 9.1.
 *
 * Attributes:
 *   window-title - Window title displayed in the title bar
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
  border: 1px dashed var(--line);
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
  padding-top: calc(var(--chrome-height) + 6px);
}
:host([depth="1"]) .frame {
  width: 90vw;
  max-width: 1300px;
  height: 85vh;
}


/* Grandchild window: 80% of child dimensions */
:host([depth="2"]) {
  inset: 0;
  padding-top: calc(var(--chrome-height) + 6px);
}
:host([depth="2"]) .frame {
  width: calc(90vw * 0.8);
  max-width: calc(1300px * 0.8);
  height: calc(85vh * 0.8);
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
  border: 1px dashed var(--line);
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

/* ---- Title bar message state ---- */
.title-bar--message {
  transition: background 0.2s ease;
}
.title-bar--message .title {
  color: #fff;
}
.title-bar--message .subtitle {
  color: rgba(255, 255, 255, 0.92);
}
.title-bar--message .close-btn {
  color: rgba(255, 255, 255, 0.7);
  border-color: rgba(255, 255, 255, 0.3);
}
.title-bar--message .close-btn:hover {
  color: #fff;
  border-color: rgba(255, 255, 255, 0.6);
}
.title-bar--amber { background: #92400e; }
.title-bar--blue { background: #1e40af; }
.title-bar--red { background: #991b1b; }
.title-bar--green { background: #166534; }

.msg-action {
  display: inline;
  background: none;
  border: none;
  color: #fff;
  font-family: var(--font-body);
  font-size: 0.78rem;
  font-weight: 600;
  text-decoration: underline;
  cursor: pointer;
  padding: 0;
  margin-left: 6px;
}
.msg-action:hover { opacity: 0.85; }
.msg-dismiss {
  background: none;
  border: none;
  color: rgba(255, 255, 255, 0.6);
  font-size: 0.85rem;
  cursor: pointer;
  padding: 0 4px;
  margin-left: 8px;
  line-height: 1;
}
.msg-dismiss:hover { color: #fff; }

.content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-xl);
}
`;

export class AtdWindowFrame extends AtdBase {
  static get observedAttributes() { return ['window-title', 'subtitle', 'depth']; }

  constructor() {
    super();
    this.addStyle(styles);
    this._render();
  }

  _render() {
    const title = this.getAttribute('window-title') || '';
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
    if (name === 'window-title') {
      const titleEl = this.shadowRoot.querySelector('.title');
      if (titleEl) titleEl.textContent = this.getAttribute('window-title') || '';
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

  /**
   * Show a message in the title bar with a cognitive-color background.
   * @param {string} text - Message content
   * @param {'amber'|'blue'|'red'|'green'} color - Background color
   * @param {object} [options]
   * @param {number} [options.duration] - Auto-clear after N ms (0 = persist)
   * @param {boolean} [options.dismissable] - Show dismiss button
   * @param {{ label: string, onClick: Function }} [options.action] - Inline action
   */
  setTitleMessage(text, color = 'amber', options = {}) {
    const titleBar = this.shadowRoot.querySelector('.title-bar');
    if (!titleBar) return;

    // Store original subtitle on first call
    if (!this._savedSubtitle) {
      this._savedSubtitle = this.getAttribute('subtitle') || '';
    }

    // Clear any existing timer
    if (this._msgTimer) { clearTimeout(this._msgTimer); this._msgTimer = null; }

    // Apply message state
    titleBar.classList.add('title-bar--message');
    titleBar.classList.remove('title-bar--amber', 'title-bar--blue', 'title-bar--red', 'title-bar--green');
    titleBar.classList.add(`title-bar--${color}`);

    // Update subtitle to show message
    const group = this.shadowRoot.querySelector('.title-group');
    let subEl = this.shadowRoot.querySelector('.subtitle');
    if (!subEl) {
      subEl = document.createElement('span');
      subEl.className = 'subtitle';
      group.appendChild(subEl);
    }
    subEl.textContent = `\u2014 ${text}`;

    // Remove old action/dismiss elements
    group.querySelectorAll('.msg-action, .msg-dismiss').forEach(el => el.remove());

    // Action button
    if (options.action) {
      const btn = document.createElement('button');
      btn.className = 'msg-action';
      btn.textContent = options.action.label;
      btn.addEventListener('click', (e) => { e.stopPropagation(); options.action.onClick(); });
      group.appendChild(btn);
    }

    // Dismiss button
    if (options.dismissable) {
      const dismiss = document.createElement('button');
      dismiss.className = 'msg-dismiss';
      dismiss.textContent = '\u2715';
      dismiss.setAttribute('aria-label', 'Dismiss message');
      dismiss.addEventListener('click', (e) => { e.stopPropagation(); this.clearTitleMessage(); });
      group.appendChild(dismiss);
    }

    // Duration auto-clear
    if (options.duration && options.duration > 0) {
      this._msgTimer = setTimeout(() => this.clearTitleMessage(), options.duration);
    }
  }

  /** Revert the title bar to its default state. */
  clearTitleMessage() {
    const titleBar = this.shadowRoot.querySelector('.title-bar');
    if (!titleBar) return;
    if (this._msgTimer) { clearTimeout(this._msgTimer); this._msgTimer = null; }

    titleBar.classList.remove('title-bar--message', 'title-bar--amber', 'title-bar--blue', 'title-bar--red', 'title-bar--green');

    // Restore original subtitle
    const sub = this._savedSubtitle || '';
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

    // Remove action/dismiss elements
    const group = this.shadowRoot.querySelector('.title-group');
    if (group) group.querySelectorAll('.msg-action, .msg-dismiss').forEach(el => el.remove());

    this._savedSubtitle = null;
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
  }
}

customElements.define('atd-window-frame', AtdWindowFrame);
