/**
 * Chrome bar for the Atested operator UI.
 * Fixed-position horizontal bar above all other content.
 * Spec v2 section 3.
 *
 * Zones: Identity (left), Brand (center-left), License + Notification indicator + Banner (right).
 * Phase 1: all zones render placeholder content.
 * Chrome interactions are system-level and exempt from the strict launcher rule.
 */

import { Z_INDEX } from './modal-manager.js';

export function renderChrome() {
  const chrome = document.createElement('div');
  chrome.id = 'chrome-bar';
  chrome.innerHTML = `
    <div class="chrome-zone chrome-identity" tabindex="0" role="button" aria-label="Identity">
      <span class="chrome-identity-text">Set up identity</span>
    </div>
    <div class="chrome-brand">Atested</div>
    <div class="chrome-right">
      <div class="chrome-zone chrome-license" tabindex="0" role="button" aria-label="License">
        <span class="chrome-license-tier">Trial</span>
        <span class="chrome-license-dot" style="background: var(--ok)"></span>
      </div>
      <div class="chrome-zone chrome-notif-indicator" tabindex="0" role="button" aria-label="Notifications">
        <span class="chrome-notif-icon">&#x1F514;</span>
      </div>
      <div class="chrome-banner"></div>
    </div>
  `;

  // Style the chrome bar
  Object.assign(chrome.style, {
    position: 'fixed',
    top: '0',
    left: '0',
    right: '0',
    height: '48px',
    zIndex: String(Z_INDEX.CHROME),
    background: '#2a2f38',
    borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
    display: 'flex',
    alignItems: 'center',
    padding: '0 20px',
    fontFamily: '"Inter", system-ui, sans-serif',
    color: '#e4e6eb',
    fontSize: '0.88rem',
    userSelect: 'none',
  });

  return chrome;
}

// Inject chrome-specific styles into the document
const chromeStyles = document.createElement('style');
chromeStyles.textContent = `
  .chrome-zone {
    cursor: pointer;
    padding: 4px 10px;
    border-radius: 6px;
    transition: background 0.15s;
  }
  .chrome-zone:hover {
    background: rgba(255, 255, 255, 0.06);
  }
  .chrome-zone:focus-visible {
    outline: 2px solid #5b8af5;
    outline-offset: 2px;
  }
  .chrome-identity {
    margin-right: auto;
  }
  .chrome-identity-text {
    color: #8b919a;
    font-size: 0.82rem;
  }
  .chrome-identity:hover .chrome-identity-text {
    color: #5b8af5;
  }
  .chrome-brand {
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: -0.02em;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
  }
  .chrome-right {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-left: auto;
  }
  .chrome-license {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.82rem;
  }
  .chrome-license-tier {
    color: #8b919a;
  }
  .chrome-license-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    display: inline-block;
  }
  .chrome-notif-indicator {
    font-size: 0.9rem;
    position: relative;
  }
  .chrome-notif-icon {
    filter: grayscale(100%) brightness(0.7);
    font-size: 0.85rem;
  }
  .chrome-banner {
    /* Empty and invisible when no notifications */
  }
`;
document.head.appendChild(chromeStyles);
