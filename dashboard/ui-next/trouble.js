/**
 * Contextual Trouble button.
 *
 * Support reports are separate from telemetry and the governance chain. They
 * capture the current UI context so the operator can describe the problem
 * without restating where they were.
 */

import * as api from './api.js';
import { modalManager } from './modal-manager.js';
import { recordUiAggregate, flushTelemetrySummary } from './summary-telemetry.js';

let _installed = false;

export function installTroubleButton() {
  if (_installed) return;
  _installed = true;

  const btn = document.createElement('button');
  const chromeRight = document.querySelector('.chrome-right');
  btn.className = chromeRight ? 'chrome-trouble-btn' : 'chrome-trouble-btn trouble-floating-btn';
  btn.type = 'button';
  btn.textContent = 'Trouble';
  btn.setAttribute('aria-label', 'Report trouble with current context');
  btn.addEventListener('click', () => openTroubleDialog());
  if (chromeRight) chromeRight.insertBefore(btn, chromeRight.firstChild);
  else document.body.appendChild(btn);
}

export function openTroubleDialog() {
  const context = _captureContext();
  const overlay = document.createElement('div');
  overlay.className = 'trouble-overlay';
  overlay.innerHTML = `
    <div class="trouble-dialog" role="dialog" aria-modal="true" aria-labelledby="trouble-title">
      <div class="trouble-accent"></div>
      <div class="trouble-header">
        <div>
          <h2 id="trouble-title">Report trouble</h2>
          <p>Current screen context is attached automatically.</p>
        </div>
        <button class="trouble-close" type="button" aria-label="Close">x</button>
      </div>
      <div class="trouble-context">
        <span>Window</span><strong>${_esc(context.current_window)}</strong>
        <span>Path</span><strong>${_esc(context.path)}</strong>
      </div>
      <label class="trouble-label">
        Priority
        <select id="trouble-priority">
          <option value="normal">Normal</option>
          <option value="low">Low</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
      </label>
      <label class="trouble-label">
        What went wrong?
        <textarea id="trouble-description" rows="6" placeholder="Describe what happened and what you expected."></textarea>
      </label>
      <div class="trouble-actions">
        <span id="trouble-result"></span>
        <button class="trouble-submit" type="button">Send</button>
      </div>
    </div>
  `;

  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });
  overlay.querySelector('.trouble-close').addEventListener('click', close);
  overlay.querySelector('.trouble-submit').addEventListener('click', async () => {
    const submit = overlay.querySelector('.trouble-submit');
    const result = overlay.querySelector('#trouble-result');
    const description = overlay.querySelector('#trouble-description').value.trim();
    const priority = overlay.querySelector('#trouble-priority').value;
    if (!description) {
      result.className = 'trouble-error';
      result.textContent = 'Description required.';
      return;
    }
    submit.disabled = true;
    result.className = '';
    result.textContent = 'Sending...';
    const res = await api.postTroubleReport({ description, priority, context });
    if (res.ok) {
      recordUiAggregate('trouble_reports', 'submitted');
      await flushTelemetrySummary();
      result.className = 'trouble-success';
      result.textContent = `Sent: ${res.data.artifact_id || 'recorded'}`;
      window.setTimeout(close, 900);
    } else {
      submit.disabled = false;
      result.className = 'trouble-error';
      result.textContent = res.error || 'Send failed.';
    }
  });

  document.body.appendChild(overlay);
  overlay.querySelector('#trouble-description').focus();
}

function _captureContext() {
  const modal = modalManager.getContext();
  const active = document.activeElement;
  const selectedReport = document.querySelector('#rp-selected-title')?.textContent || '';
  const activeActivityRow = document.querySelector('.aw-row-active')?.textContent?.slice(0, 180) || '';
  return {
    captured_at_utc: new Date().toISOString(),
    path: window.location.pathname,
    current_window: modal.top_window,
    modal_stack: modal.windows,
    active_element: active ? {
      tag: active.tagName,
      id: active.id || '',
      class_name: typeof active.className === 'string' ? active.className.slice(0, 120) : '',
      label: active.getAttribute?.('aria-label') || active.textContent?.trim().slice(0, 80) || '',
    } : null,
    visible_state: {
      breadcrumb: document.querySelector('.chrome-brand')?.textContent || '',
      license: document.querySelector('.chrome-license-tier')?.textContent || '',
      selected_report: selectedReport,
      active_activity_row: activeActivityRow,
    },
  };
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str == null ? '' : String(str);
  return el.innerHTML;
}

const styles = document.createElement('style');
styles.textContent = `
  .chrome-trouble-btn {
    background: rgba(210, 153, 34, 0.12);
    border: 1px dashed rgba(210, 153, 34, 0.45);
    border-radius: 2px;
    color: #d29922;
    cursor: pointer;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    padding: 5px 10px;
  }
  .chrome-trouble-btn:hover,
  .chrome-trouble-btn:focus-visible {
    background: rgba(210, 153, 34, 0.2);
    outline: none;
  }
  .trouble-floating-btn {
    position: fixed;
    right: 18px;
    bottom: 18px;
    z-index: 1001;
    background: #2a2f38;
  }
  .trouble-overlay {
    position: fixed;
    inset: 0;
    z-index: 1500;
    background: rgba(0, 0, 0, 0.62);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
    font-family: "Inter", system-ui, sans-serif;
  }
  .trouble-dialog {
    width: min(560px, 100%);
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.14);
    border-radius: 2px;
    color: #e4e6eb;
    overflow: hidden;
    box-shadow: 0 24px 70px rgba(0,0,0,0.4);
  }
  .trouble-accent { height: 6px; background: #d29922; }
  .trouble-header {
    display: flex;
    justify-content: space-between;
    gap: 18px;
    padding: 18px 20px 10px;
  }
  .trouble-header h2 { margin: 0 0 4px; font-size: 1rem; }
  .trouble-header p { margin: 0; color: #8b919a; font-size: 0.82rem; }
  .trouble-close {
    width: 28px;
    height: 28px;
    background: transparent;
    border: 1px dashed rgba(255,255,255,0.12);
    color: #8b919a;
    cursor: pointer;
  }
  .trouble-context {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: 6px 12px;
    margin: 0 20px 14px;
    padding: 12px;
    background: #1a1d23;
    border: 1px dashed rgba(255,255,255,0.1);
    font-family: "JetBrains Mono", monospace;
    font-size: 0.74rem;
  }
  .trouble-context span { color: #8b919a; }
  .trouble-context strong { color: #e4e6eb; font-weight: 500; }
  .trouble-label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin: 0 20px 14px;
    color: #8b919a;
    font-size: 0.72rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  .trouble-label select,
  .trouble-label textarea {
    background: #1a1d23;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.84rem;
    padding: 8px 10px;
    resize: vertical;
    text-transform: none;
    letter-spacing: 0;
  }
  .trouble-actions {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 12px;
    padding: 0 20px 20px;
  }
  .trouble-submit {
    background: #6699cc;
    border: none;
    border-radius: 2px;
    color: white;
    cursor: pointer;
    font-weight: 700;
    padding: 8px 20px;
  }
  .trouble-submit:disabled { opacity: 0.6; cursor: wait; }
  #trouble-result { color: #8b919a; font-size: 0.8rem; }
  #trouble-result.trouble-error { color: #f85149; }
  #trouble-result.trouble-success { color: #3fb950; }
`;
document.head.appendChild(styles);
