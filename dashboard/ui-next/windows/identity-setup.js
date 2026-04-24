/**
 * Identity Setup window — child window (depth 1).
 * Spec v2 section 7.10.
 *
 * Opens when identity is not configured and operator clicks the
 * "Set up identity" chrome prompt. Provides instructions for
 * operator enrollment via the CLI.
 */

import { modalManager } from '../modal-manager.js';

/**
 * Open the Identity Setup window.
 * @param {HTMLElement|null} trigger
 */
export function openIdentitySetupWindow(trigger) {
  const content = _buildContent();
  _openAsChild('Identity Setup', 'Configure your operator identity', trigger, content);
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'is-content';
  el.innerHTML = `
    <div class="is-header">
      <span class="is-eyebrow">Getting Started</span>
      <span class="is-heading">Set Up Operator Identity</span>
    </div>

    <div class="is-card">
      <h3 class="is-section-title">Why Identity Matters</h3>
      <p class="is-text">
        Operator identity binds approvals in the governance chain to authenticated
        humans. Without identity, approvals record only an unverified operator string.
        With identity, every approval is cryptographically bound to a registered operator
        via TOTP authentication.
      </p>
    </div>

    <div class="is-card">
      <h3 class="is-section-title">How to Set Up Identity</h3>
      <p class="is-text">
        Operator identity is established during license activation. The enrollment
        process is handled through the Atested CLI.
      </p>

      <div class="is-steps">
        <div class="is-step">
          <span class="is-step-num">1</span>
          <div class="is-step-body">
            <strong>Activate your license</strong>
            <p>Run <code>atested activate &lt;license-key&gt;</code> in your terminal.
            This registers your operator identity and provisions TOTP credentials.</p>
          </div>
        </div>

        <div class="is-step">
          <span class="is-step-num">2</span>
          <div class="is-step-body">
            <strong>Scan the QR code</strong>
            <p>During activation, a QR code will be displayed. Scan it with your
            authenticator app (Google Authenticator, Authy, 1Password, etc.).</p>
          </div>
        </div>

        <div class="is-step">
          <span class="is-step-num">3</span>
          <div class="is-step-body">
            <strong>Unlock your session</strong>
            <p>Run <code>atested unlock</code> and enter the current TOTP code from
            your authenticator app. Your dashboard will reflect the unlocked state.</p>
          </div>
        </div>
      </div>
    </div>

    <div class="is-card">
      <h3 class="is-section-title">Session Model</h3>
      <p class="is-text">
        Once enrolled, unlock sessions are governed by two timers:
      </p>
      <div class="is-timers">
        <div class="is-timer-row">
          <span class="is-timer-label">Idle timer</span>
          <span class="is-timer-value">30 minutes</span>
          <span class="is-timer-note">Resets on each approval action</span>
        </div>
        <div class="is-timer-row">
          <span class="is-timer-label">Hard ceiling</span>
          <span class="is-timer-value">1 hour</span>
          <span class="is-timer-note">From initial unlock, does not reset</span>
        </div>
      </div>
      <p class="is-text is-text-muted">
        Either timer expiring locks the session. You can also manually lock at any time.
      </p>
    </div>

    <div class="is-card is-card-muted">
      <p class="is-text is-text-muted">
        If you have already activated a license and enrolled, try running
        <code>atested unlock</code> to start a session. The identity zone in the
        chrome bar will update to reflect your operator name and session state.
      </p>
    </div>
  `;
  return el;
}

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, subtitle, trigger, content });
  return modalManager.open({ title, subtitle, trigger, content });
}

// Styles
const isStyles = document.createElement('style');
isStyles.textContent = `
  .is-content { font-family: "Inter", system-ui, sans-serif; }
  .is-header { margin-bottom: 16px; }
  .is-eyebrow {
    display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #8b919a; margin-bottom: 4px;
  }
  .is-heading { font-size: 1.25rem; font-weight: 600; color: #e4e6eb; }
  .is-section-title {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #60a5fa; margin: 0 0 10px; font-weight: 600;
  }
  .is-card {
    background: #22262e; border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px; padding: 16px 20px; margin-bottom: 14px;
  }
  .is-card-muted {
    background: rgba(96,165,250,0.06);
    border-color: rgba(96,165,250,0.15);
  }
  .is-text {
    font-size: 0.82rem; color: #e4e6eb; line-height: 1.6; margin: 0 0 10px;
  }
  .is-text:last-child { margin-bottom: 0; }
  .is-text-muted { color: #8b919a; }
  .is-text code {
    background: #1a1d23; padding: 2px 6px; border-radius: 2px;
    font-family: "JetBrains Mono", monospace; font-size: 0.78rem; color: #60a5fa;
  }
  .is-steps { display: flex; flex-direction: column; gap: 12px; margin-top: 10px; }
  .is-step {
    display: flex; gap: 12px; align-items: flex-start;
  }
  .is-step-num {
    flex: 0 0 28px; height: 28px; background: #60a5fa;
    color: #fff; border-radius: 50%; display: flex; align-items: center;
    justify-content: center; font-size: 0.78rem; font-weight: 700;
  }
  .is-step-body { flex: 1; }
  .is-step-body strong { display: block; font-size: 0.82rem; color: #e4e6eb; margin-bottom: 4px; }
  .is-step-body p { font-size: 0.78rem; color: #8b919a; margin: 0; line-height: 1.5; }
  .is-step-body code {
    background: #1a1d23; padding: 2px 6px; border-radius: 2px;
    font-family: "JetBrains Mono", monospace; font-size: 0.72rem; color: #60a5fa;
  }
  .is-timers {
    background: #1a1d23; border-radius: 2px; overflow: hidden; margin-top: 8px;
  }
  .is-timer-row {
    display: flex; align-items: center; gap: 12px; padding: 8px 14px;
    font-size: 0.82rem; border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .is-timer-row:last-child { border-bottom: none; }
  .is-timer-label { flex: 0 0 100px; color: #e4e6eb; font-weight: 500; }
  .is-timer-value { flex: 0 0 80px; color: #60a5fa; font-family: "JetBrains Mono", monospace; font-size: 0.78rem; }
  .is-timer-note { flex: 1; color: #8b919a; font-size: 0.78rem; }
`;
document.head.appendChild(isStyles);
