/**
 * Window title bar messaging utility.
 * Provides a stable API for setting/clearing title bar messages from
 * within window content. Messages are displayed with cognitive-color
 * backgrounds (amber, blue, red, green) and support auto-clear,
 * dismiss buttons, and inline action links.
 *
 * Usage:
 *   import { setTitleMessage, clearTitleMessage } from '../window-messaging.js';
 *   setTitleMessage(state.el, 'Feature X is available on Crew and above.', 'amber', {
 *     duration: 5000,
 *     dismissable: true,
 *     action: { label: 'See Licensing', onClick: () => openLicensingWindow() }
 *   });
 */

/**
 * Set a message on the title bar of the window containing this element.
 * @param {HTMLElement} contentEl - Any element inside the window content
 * @param {string} text - Message to display
 * @param {'amber'|'blue'|'red'|'green'} color - Cognitive color
 * @param {object} [options]
 * @param {number} [options.duration] - Auto-clear after N ms (0 = persist)
 * @param {boolean} [options.dismissable] - Whether user can dismiss
 * @param {{ label: string, onClick: Function }} [options.action] - Inline action
 */
export function setTitleMessage(contentEl, text, color = 'amber', options = {}) {
  const frame = contentEl.closest('atd-window-frame');
  if (frame && frame.setTitleMessage) {
    frame.setTitleMessage(text, color, options);
  }
}

/**
 * Clear the current title bar message, reverting to the default subtitle.
 * @param {HTMLElement} contentEl - Any element inside the window content
 */
export function clearTitleMessage(contentEl) {
  const frame = contentEl.closest('atd-window-frame');
  if (frame && frame.clearTitleMessage) {
    frame.clearTitleMessage();
  }
}
