/**
 * Modal manager for the Atested operator UI window model.
 * Manages depth stack (0=main, 1=child, 2=grandchild), z-index ordering,
 * focus trapping, Esc-to-close, backdrop clicks, and focus return.
 *
 * Spec v2 sections 4.1-4.5.
 *
 * Z-index tiers:
 *   Main page:          1
 *   Child backdrop:     100
 *   Child window:       200
 *   Grandchild backdrop: 300
 *   Grandchild window:  400
 *   Confirmation dialog backdrop: 450
 *   Confirmation dialog: 460
 *   Chrome:             1000
 */

import './components/window-frame.js';
import './components/window-backdrop.js';

const Z = {
  MAIN: 1,
  CHILD_BACKDROP: 100,
  CHILD: 200,
  GRANDCHILD_BACKDROP: 300,
  GRANDCHILD: 400,
  CONFIRM_BACKDROP: 450,
  CONFIRM: 460,
  CHROME: 1000,
};

export { Z as Z_INDEX };

class ModalManager {
  constructor() {
    /** @type {{ depth: number, frame: HTMLElement, backdrop: HTMLElement, trigger: HTMLElement|null, content: HTMLElement|null }[]} */
    this._stack = [];
    this._onKeyDown = this._onKeyDown.bind(this);
    document.addEventListener('keydown', this._onKeyDown);
  }

  /** Current stack depth (0 = nothing open, 1 = child, 2 = grandchild) */
  get depth() {
    return this._stack.length;
  }

  /**
   * Open a window at the next depth level.
   * @param {object} opts
   * @param {string} opts.title - Window title
   * @param {HTMLElement|null} opts.trigger - Element that triggered the open (for focus return)
   * @param {HTMLElement|string|null} opts.content - Content to place in the window
   * @returns {{ frame: HTMLElement, contentSlot: HTMLElement }} - References for the caller
   */
  open({ title, trigger = null, content = null }) {
    const depth = this._stack.length + 1;
    if (depth > 2) {
      console.error('ModalManager: maximum depth 2 exceeded');
      return null;
    }

    // Create backdrop
    const backdrop = document.createElement('atd-window-backdrop');
    backdrop.setAttribute('depth', String(depth));
    backdrop.style.setProperty('--z-index', String(depth === 1 ? Z.CHILD_BACKDROP : Z.GRANDCHILD_BACKDROP));
    backdrop.addEventListener('backdrop:click', () => this.closeTopmost());

    // Create frame
    const frame = document.createElement('atd-window-frame');
    frame.setAttribute('title', title);
    frame.setAttribute('depth', String(depth));
    frame.style.setProperty('--z-index', String(depth === 1 ? Z.CHILD : Z.GRANDCHILD));
    frame.addEventListener('frame:close', () => this.closeTopmost());

    // Insert content
    if (content) {
      if (typeof content === 'string') {
        frame.innerHTML = content;
      } else {
        frame.appendChild(content);
      }
    }

    // Lock parent content if opening child (depth 1)
    if (depth === 1) {
      const mainPage = document.getElementById('main-page');
      if (mainPage) mainPage.setAttribute('aria-hidden', 'true');
    }
    // Lock parent window if opening grandchild (depth 2)
    if (depth === 2 && this._stack.length > 0) {
      const parentFrame = this._stack[this._stack.length - 1].frame;
      parentFrame.setAttribute('aria-hidden', 'true');
      parentFrame.style.pointerEvents = 'none';
    }

    // Add to DOM
    document.body.appendChild(backdrop);
    document.body.appendChild(frame);

    // Push to stack
    this._stack.push({ depth, frame, backdrop, trigger, content: null });

    // Move focus into the window
    this._trapFocus(frame);

    return {
      frame,
      contentSlot: frame,
    };
  }

  /**
   * Close the topmost window.
   * @returns {boolean} true if a window was closed
   */
  closeTopmost() {
    if (this._stack.length === 0) return false;

    const entry = this._stack.pop();

    // Remove from DOM
    entry.frame.remove();
    entry.backdrop.remove();

    // Unlock parent
    if (entry.depth === 2 && this._stack.length > 0) {
      const parentFrame = this._stack[this._stack.length - 1].frame;
      parentFrame.removeAttribute('aria-hidden');
      parentFrame.style.pointerEvents = '';
    }
    if (entry.depth === 1) {
      const mainPage = document.getElementById('main-page');
      if (mainPage) mainPage.removeAttribute('aria-hidden');
    }

    // Return focus to trigger
    if (entry.trigger && entry.trigger.isConnected) {
      entry.trigger.focus();
    } else if (this._stack.length > 0) {
      this._trapFocus(this._stack[this._stack.length - 1].frame);
    }

    return true;
  }

  /**
   * Close all open windows (used for atomic navigation).
   */
  closeAll() {
    while (this._stack.length > 0) {
      this.closeTopmost();
    }
  }

  /**
   * Replace the current depth-1 window with a new one.
   * Used when chrome clicks open a window while another is already open.
   * Spec v2 section 3.6.
   */
  replaceChild({ title, trigger = null, content = null }) {
    // Close everything first
    this.closeAll();
    // Open the new child
    return this.open({ title, trigger, content });
  }

  /**
   * Handle Esc key: close the topmost window.
   */
  _onKeyDown(e) {
    if (e.key === 'Escape' && this._stack.length > 0) {
      e.preventDefault();
      e.stopPropagation();
      this.closeTopmost();
    }
  }

  /**
   * Set up focus trapping within a window frame.
   * Tab cycles within the frame's focusable elements.
   * Chrome elements (z-index above everything) remain focusable
   * because they are outside the trap boundary.
   */
  _trapFocus(frame) {
    // Focus the first focusable element in the frame
    requestAnimationFrame(() => {
      const focusable = this._getFocusableElements(frame);
      if (focusable.length > 0) {
        focusable[0].focus();
      } else {
        // If no focusable elements, focus the frame itself
        frame.setAttribute('tabindex', '-1');
        frame.focus();
      }
    });

    // Remove previous trap listener if any
    if (this._trapListener) {
      document.removeEventListener('keydown', this._trapListener, true);
    }

    this._trapListener = (e) => {
      if (e.key !== 'Tab') return;
      if (this._stack.length === 0) return;

      const topFrame = this._stack[this._stack.length - 1].frame;
      const chrome = document.getElementById('chrome-bar');
      const target = e.target;

      // Allow Tab within chrome (chrome is exempt from focus trap)
      if (chrome && chrome.contains(target)) return;

      const focusable = this._getFocusableElements(topFrame);
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (target === first || !topFrame.contains(target)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (target === last || !topFrame.contains(target)) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', this._trapListener, true);
  }

  /**
   * Get all focusable elements within an element, including those
   * inside Shadow DOMs.
   */
  _getFocusableElements(root) {
    const selectors = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const elements = [];

    // Check light DOM
    root.querySelectorAll(selectors).forEach(el => elements.push(el));

    // Check Shadow DOM of the root itself
    if (root.shadowRoot) {
      root.shadowRoot.querySelectorAll(selectors).forEach(el => elements.push(el));
      // Check slotted content
      root.shadowRoot.querySelectorAll('slot').forEach(slot => {
        slot.assignedElements().forEach(assigned => {
          assigned.querySelectorAll(selectors).forEach(el => elements.push(el));
          if (assigned.matches(selectors)) elements.push(assigned);
        });
      });
    }

    return elements;
  }
}

// Singleton
export const modalManager = new ModalManager();
