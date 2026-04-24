/**
 * <atd-confirmation-dialog>
 * Transient confirmation surface for destructive actions.
 * Spec v2 section 9.15.
 *
 * Renders at intermediate z-index (above parent window, below chrome).
 * Does NOT count as a depth level in the window stack.
 * Uses window-frame visual appearance at compact size.
 *
 * Attributes:
 *   title         - Dialog title
 *   message       - Confirmation prompt text
 *   confirm-label - Confirm button text (default: "Confirm")
 *   cancel-label  - Cancel button text (default: "Cancel")
 *   variant       - "danger" | "default" (controls confirm button style)
 *
 * Events:
 *   dialog:confirm - when confirm button clicked
 *   dialog:cancel  - when cancel button clicked or Esc pressed
 */

import { AtdBase } from './base.js';
import { Z_INDEX } from '../modal-manager.js';

const styles = `
:host {
  position: fixed;
  inset: 0;
  z-index: ${Z_INDEX.CONFIRM};
  display: flex;
  align-items: center;
  justify-content: center;
}

.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: ${Z_INDEX.CONFIRM_BACKDROP};
}

.dialog {
  position: relative;
  z-index: ${Z_INDEX.CONFIRM};
  background: var(--surface);
  border: 1px dashed var(--line);
  border-radius: var(--radius);
  max-width: 400px;
  width: 90%;
}

.dialog-title {
  font-family: var(--font-body);
  font-size: var(--text-base);
  font-weight: 600;
  color: var(--ink);
  padding: var(--space-md) var(--space-xl);
  border-bottom: 1px solid var(--line);
  background: var(--surface-raised);
  border-radius: var(--radius) var(--radius) 0 0;
}

.dialog-body {
  padding: var(--space-xl);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  color: var(--ink);
  line-height: 1.5;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-sm);
  padding: var(--space-md) var(--space-xl);
  border-top: 1px solid var(--line);
}

button {
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 500;
  padding: 6px 16px;
  border-radius: 2px;
  cursor: pointer;
  border: 1px dashed transparent;
  transition: background 0.15s, border-color 0.15s;
}

button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.btn-cancel {
  background: transparent;
  border-color: var(--muted);
  color: var(--ink);
}
.btn-cancel:hover {
  border-color: var(--muted);
  background: var(--surface-raised);
}

.btn-confirm {
  background: var(--accent);
  color: #fff;
}
.btn-confirm:hover {
  background: #4a7ae4;
}

.btn-confirm.danger {
  background: var(--danger);
}
.btn-confirm.danger:hover {
  background: #dc2626;
}
`;

export class AtdConfirmationDialog extends AtdBase {
  static get observedAttributes() {
    return ['title', 'message', 'confirm-label', 'cancel-label', 'variant'];
  }

  constructor() {
    super();
    this.addStyle(styles);
    this._render();
    this._onEsc = this._onEsc.bind(this);
  }

  connectedCallback() {
    this._onTab = this._onTab.bind(this);
    document.addEventListener('keydown', this._onEsc, true);
    document.addEventListener('keydown', this._onTab, true);
    // Focus cancel button
    requestAnimationFrame(() => {
      const cancel = this.shadowRoot.querySelector('.btn-cancel');
      if (cancel) cancel.focus();
    });
  }

  disconnectedCallback() {
    document.removeEventListener('keydown', this._onEsc, true);
    document.removeEventListener('keydown', this._onTab, true);
  }

  _render() {
    const title = this.getAttribute('title') || 'Confirm';
    const message = this.getAttribute('message') || 'Are you sure?';
    const confirmLabel = this.getAttribute('confirm-label') || 'Confirm';
    const cancelLabel = this.getAttribute('cancel-label') || 'Cancel';
    const variant = this.getAttribute('variant') || 'default';

    this.shadowRoot.innerHTML = `
      <div class="overlay"></div>
      <div class="dialog" role="alertdialog" aria-modal="true" aria-label="${this._esc(title)}">
        <div class="dialog-title">${this._esc(title)}</div>
        <div class="dialog-body">${this._esc(message)}</div>
        <div class="dialog-actions">
          <button class="btn-cancel">${this._esc(cancelLabel)}</button>
          <button class="btn-confirm ${variant === 'danger' ? 'danger' : ''}">${this._esc(confirmLabel)}</button>
        </div>
      </div>
    `;

    this.shadowRoot.querySelector('.overlay').addEventListener('click', () => this._cancel());
    this.shadowRoot.querySelector('.btn-cancel').addEventListener('click', () => this._cancel());
    this.shadowRoot.querySelector('.btn-confirm').addEventListener('click', () => this._confirm());
  }

  _confirm() {
    this.emit('dialog:confirm');
    this.remove();
  }

  _cancel() {
    this.emit('dialog:cancel');
    this.remove();
  }

  _onEsc(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      e.stopPropagation();
      this._cancel();
    }
  }

  _onTab(e) {
    if (e.key !== 'Tab') return;
    const focusable = this.shadowRoot.querySelectorAll('button');
    if (focusable.length === 0) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = this.shadowRoot.activeElement || document.activeElement;

    // Trap focus within the dialog
    if (e.shiftKey) {
      if (active === first || !this.shadowRoot.contains(active)) {
        e.preventDefault();
        e.stopPropagation();
        last.focus();
      }
    } else {
      if (active === last || !this.shadowRoot.contains(active)) {
        e.preventDefault();
        e.stopPropagation();
        first.focus();
      }
    }
  }

  _esc(str) {
    const el = document.createElement('span');
    el.textContent = str || '';
    return el.innerHTML;
  }
}

customElements.define('atd-confirmation-dialog', AtdConfirmationDialog);
