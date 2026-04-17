/**
 * <atd-code-block>
 * Pre-formatted JSON/code block with copy-to-clipboard button.
 *
 * Attributes:
 *   language - Language hint (e.g., "json"). Currently informational.
 *
 * Properties (set via JS):
 *   content - String content to display (alternative to slot)
 *
 * Slots:
 *   default - Code content (used if .content property is not set)
 *
 * Copy button transitions to a checkmark on success, reverts after 2s.
 */

import { AtdBase } from './base.js';

const styles = `
:host {
  display: block;
}

.block {
  position: relative;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: var(--space-xs) var(--space-sm);
  border-bottom: 1px solid var(--line);
  background: var(--surface);
}

.copy-btn {
  background: none;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  color: var(--muted);
  cursor: pointer;
  font-family: var(--font-body);
  font-size: var(--text-xs);
  padding: 2px 10px;
  transition: color 0.15s, border-color 0.15s;
  display: flex;
  align-items: center;
  gap: 4px;
}

.copy-btn:hover {
  color: var(--ink);
  border-color: var(--muted);
}

.copy-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.copy-btn.copied {
  color: var(--ok);
  border-color: var(--ok);
}

pre {
  margin: 0;
  padding: var(--space-lg);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--ink);
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}
`;

export class AtdCodeBlock extends AtdBase {
  static get observedAttributes() { return ['language']; }

  constructor() {
    super();
    this.addStyle(styles);
    this._content = null;
    this._render();
  }

  get content() { return this._content; }

  set content(val) {
    this._content = val;
    this._updatePre();
  }

  _render() {
    this.shadowRoot.innerHTML = `
      <div class="block">
        <div class="toolbar">
          <button class="copy-btn">
            <span class="icon">&#x1F4CB;</span>
            <span class="label">Copy</span>
          </button>
        </div>
        <pre><slot></slot></pre>
      </div>
    `;

    this.shadowRoot.querySelector('.copy-btn').addEventListener('click', () => this._copy());
  }

  _updatePre() {
    const pre = this.shadowRoot.querySelector('pre');
    if (!pre) return;
    if (this._content != null) {
      pre.textContent = typeof this._content === 'string'
        ? this._content
        : JSON.stringify(this._content, null, 2);
    }
  }

  async _copy() {
    const pre = this.shadowRoot.querySelector('pre');
    const btn = this.shadowRoot.querySelector('.copy-btn');
    if (!pre || !btn) return;

    const text = pre.textContent || '';
    try {
      await navigator.clipboard.writeText(text);
      btn.classList.add('copied');
      btn.querySelector('.icon').textContent = '\u2713';
      btn.querySelector('.label').textContent = 'Copied';
      this.emit('copy:success');
      setTimeout(() => {
        btn.classList.remove('copied');
        btn.querySelector('.icon').textContent = '\u{1F4CB}';
        btn.querySelector('.label').textContent = 'Copy';
      }, 2000);
    } catch (err) {
      this.emit('copy:error', { error: err.message });
    }
  }
}

customElements.define('atd-code-block', AtdCodeBlock);
