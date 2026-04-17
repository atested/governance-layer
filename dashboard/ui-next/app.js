/**
 * Atested Operator UI - Application entry point.
 *
 * Initializes the chrome bar, main page shell, and modal manager.
 * Triggers data loading for the main page via the data-access layer.
 */

import { renderChrome } from './chrome.js';
import { renderMainPage, loadMainPageData } from './main-page.js';
import { modalManager } from './modal-manager.js';

// Verify adoptedStyleSheets support
if (!('adoptedStyleSheets' in Document.prototype)) {
  console.warn(
    'Atested: adoptedStyleSheets not supported in this browser. ' +
    'The operator UI requires Chrome 73+, Firefox 101+, or Safari 16.4+.'
  );
}

function init() {
  // Render chrome bar (fixed position, always visible)
  const chrome = renderChrome();
  document.body.appendChild(chrome);

  // Wire chrome zone clicks to window launches
  chrome.querySelector('.chrome-identity').addEventListener('click', (e) => {
    _chromeOpen('Identity', e.currentTarget);
  });
  chrome.querySelector('.chrome-license').addEventListener('click', (e) => {
    _chromeOpen('Licensing', e.currentTarget);
  });
  chrome.querySelector('.chrome-notif-indicator').addEventListener('click', (e) => {
    _chromeOpen('Notifications', e.currentTarget);
  });

  // Render main page structure, then load live data
  const mainPage = renderMainPage();
  document.body.appendChild(mainPage);

  // Fetch data from the data-access layer (non-blocking)
  loadMainPageData().catch(err => {
    console.warn('Atested: main page data load failed:', err);
  });
}

/**
 * Chrome click handler: opens a window, replacing any existing depth-1 window.
 * Spec v2 section 3.6.
 */
function _chromeOpen(title, trigger) {
  if (modalManager.depth > 0) {
    modalManager.replaceChild({
      title,
      trigger,
      content: _chromePlaceholder(title),
    });
  } else {
    modalManager.open({
      title,
      trigger,
      content: _chromePlaceholder(title),
    });
  }
}

function _chromePlaceholder(title) {
  const el = document.createElement('div');
  el.innerHTML = `
    <p style="color: #8b919a; text-align: center; padding: 40px 0;">
      ${title} window (opened from chrome). Content built in later phases.
    </p>
  `;
  return el;
}

// Boot
init();
