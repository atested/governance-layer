const TOOLTIP_STYLE = `
  .atd-tooltip-root [data-tooltip] {
    position: relative;
  }
  .atd-tooltip-root [data-tooltip]::after {
    content: attr(data-tooltip);
    position: absolute;
    left: 50%;
    bottom: calc(100% + 8px);
    transform: translateX(-50%) translateY(4px);
    z-index: 10000;
    width: max-content;
    max-width: 250px;
    padding: 8px 10px;
    background: #161b22;
    border: 1px dashed #30363d;
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    line-height: 1.35;
    white-space: normal;
    text-transform: none;
    letter-spacing: 0;
    text-align: left;
    pointer-events: none;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.12s ease, transform 0.12s ease, visibility 0.12s ease;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  }
  .atd-tooltip-root [data-tooltip]::before {
    content: "";
    position: absolute;
    left: 50%;
    bottom: calc(100% + 3px);
    transform: translateX(-50%) translateY(4px);
    z-index: 10001;
    border: 5px solid transparent;
    border-top-color: #30363d;
    pointer-events: none;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.12s ease, transform 0.12s ease, visibility 0.12s ease;
  }
  .atd-tooltip-root [data-tooltip]:hover::after,
  .atd-tooltip-root [data-tooltip]:focus-visible::after,
  .atd-tooltip-root [data-tooltip]:hover::before,
  .atd-tooltip-root [data-tooltip]:focus-visible::before {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) translateY(0);
  }
  .atd-tooltip-root [data-tooltip].atd-tip-right::after,
  .atd-tooltip-root [data-tooltip].atd-tip-right::before {
    left: auto;
    right: 0;
    transform: translateY(4px);
  }
  .atd-tooltip-root [data-tooltip].atd-tip-right:hover::after,
  .atd-tooltip-root [data-tooltip].atd-tip-right:focus-visible::after,
  .atd-tooltip-root [data-tooltip].atd-tip-right:hover::before,
  .atd-tooltip-root [data-tooltip].atd-tip-right:focus-visible::before {
    transform: translateY(0);
  }
`;

export function installWindowTooltips(root) {
  if (!root) return;
  root.classList.add('atd-tooltip-root');
  if (root.querySelector(':scope > style[data-atd-tooltip-style="true"]')) {
    root.dataset.tooltipsInstalled = 'true';
    return;
  }
  const style = document.createElement('style');
  style.dataset.atdTooltipStyle = 'true';
  style.textContent = TOOLTIP_STYLE;
  root.prepend(style);
  root.dataset.tooltipsInstalled = 'true';
}

export function setTooltip(el, text, opts = {}) {
  if (!el || !text) return;
  el.dataset.tooltip = text;
  if (!el.hasAttribute('aria-label') && opts.aria !== false) {
    const existing = el.textContent?.trim();
    if (!existing || existing.length < 80) el.setAttribute('aria-label', text);
  }
  if (opts.right) el.classList.add('atd-tip-right');
}

export function setTooltips(root, entries) {
  if (!root) return;
  for (const [selector, text, opts] of entries) {
    root.querySelectorAll(selector).forEach(el => setTooltip(el, text, opts || {}));
  }
}

export function applyGenericWindowTooltips(root) {
  if (!root) return;
  installWindowTooltips(root);
  root.querySelectorAll('button:not([data-tooltip])').forEach(btn => {
    const label = btn.textContent?.trim() || btn.getAttribute('aria-label') || 'Action';
    setTooltip(btn, _genericButtonTip(label));
  });
  root.querySelectorAll('input:not([data-tooltip]), select:not([data-tooltip]), textarea:not([data-tooltip])').forEach(field => {
    const label = _fieldLabel(field);
    setTooltip(field, label ? `${label}.` : 'Enter or select a value for this control.');
  });
  root.querySelectorAll('th:not([data-tooltip])').forEach(th => {
    const label = th.textContent?.trim();
    if (label) setTooltip(th, `${label} column.`);
  });
}

function _genericButtonTip(label) {
  const lower = label.toLowerCase();
  if (lower === 'reports') return '';
  if (lower.includes('export')) return 'Export the current view for external review.';
  if (lower.includes('apply')) return 'Apply the selected controls.';
  if (lower.includes('clear')) return 'Clear the current controls.';
  if (lower.includes('generate')) return 'Generate results with the selected options.';
  if (lower.includes('acknowledge')) return 'Records that you have seen this alert.';
  if (lower.includes('revoke')) return 'Revocation is recorded in the chain.';
  if (lower.includes('approve')) return 'Approval is recorded in the chain.';
  if (lower.includes('save')) return 'Save the current changes.';
  if (lower.includes('cancel')) return 'Discard the current edit and close or reset this view.';
  return label;
}

function _fieldLabel(field) {
  const wrappingLabel = field.closest('label');
  if (wrappingLabel) {
    return wrappingLabel.textContent.replace(field.value || '', '').trim();
  }
  const id = field.id;
  if (id) {
    const explicit = field.ownerDocument.querySelector(`label[for="${_selectorString(id)}"]`);
    if (explicit) return explicit.textContent.trim();
  }
  return field.getAttribute('placeholder') || field.getAttribute('aria-label') || '';
}

function _selectorString(value) {
  return String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"');
}
