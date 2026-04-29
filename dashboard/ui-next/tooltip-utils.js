const TOOLTIP_STYLE = `
  .atd-tooltip-root [data-tooltip] {
    cursor: help;
  }
  .atd-floating-tooltip {
    position: fixed;
    inset: 0 auto auto 0;
    z-index: 100000;
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
    transform: translateY(4px);
    transition: opacity 0.12s ease, transform 0.12s ease, visibility 0.12s ease;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  }
  .atd-floating-tooltip.atd-floating-tooltip-visible {
    opacity: 1;
    visibility: visible;
    transform: translateY(0);
  }
`;

let _tooltipEl = null;
let _activeTarget = null;
let _lastMouse = { x: 0, y: 0 };

export function installWindowTooltips(root) {
  if (!root) return;
  root.classList.add('atd-tooltip-root');
  _ensureTooltipStyle(root.ownerDocument || document);
  if (root.dataset.tooltipsInstalled === 'true') return;
  root.addEventListener('mouseover', _onMouseOver, true);
  root.addEventListener('mousemove', _onMouseMove, true);
  root.addEventListener('mouseout', _onMouseOut, true);
  root.addEventListener('focusin', _onFocusIn, true);
  root.addEventListener('focusout', _onFocusOut, true);
  root.dataset.tooltipsInstalled = 'true';
}

export function setTooltip(el, text, opts = {}) {
  if (!el) return;
  if (!text) {
    delete el.dataset.tooltip;
    el.classList.remove('atd-tip-right');
    return;
  }
  el.dataset.tooltip = text;
  if (!el.hasAttribute('aria-label') && opts.aria !== false) {
    const existing = el.textContent?.trim();
    if (!existing || existing.length < 80) el.setAttribute('aria-label', text);
  }
  if (opts.right) el.classList.add('atd-tip-right');
  else el.classList.remove('atd-tip-right');
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

function _ensureTooltipStyle(doc) {
  if (doc.querySelector('style[data-atd-tooltip-style="true"]')) return;
  const style = doc.createElement('style');
  style.dataset.atdTooltipStyle = 'true';
  style.textContent = TOOLTIP_STYLE;
  (doc.head || doc.documentElement).appendChild(style);
}

function _ensureTooltipEl(doc) {
  if (_tooltipEl?.ownerDocument === doc) return _tooltipEl;
  _tooltipEl = doc.createElement('div');
  _tooltipEl.className = 'atd-floating-tooltip';
  doc.body.appendChild(_tooltipEl);
  return _tooltipEl;
}

function _tooltipTarget(node) {
  return node?.closest?.('[data-tooltip]') || null;
}

function _showTooltip(target, source = {}) {
  const text = target?.dataset?.tooltip;
  if (!text) return;
  const doc = target.ownerDocument || document;
  const tip = _ensureTooltipEl(doc);
  _activeTarget = target;
  tip.textContent = text;
  tip.classList.add('atd-floating-tooltip-visible');
  _positionTooltip(target, source);
}

function _hideTooltip(target = null) {
  if (target && _activeTarget && target !== _activeTarget && !_activeTarget.contains(target)) return;
  if (_tooltipEl) _tooltipEl.classList.remove('atd-floating-tooltip-visible');
  _activeTarget = null;
}

function _positionTooltip(target, source = {}) {
  if (!_tooltipEl || !target) return;
  const rect = target.getBoundingClientRect();
  const margin = 12;
  const pointerX = Number.isFinite(source.clientX) ? source.clientX : Math.round(rect.left + rect.width / 2);
  const pointerY = Number.isFinite(source.clientY) ? source.clientY : rect.top;
  const tipRect = _tooltipEl.getBoundingClientRect();
  const docEl = target.ownerDocument.documentElement;
  let left = pointerX + 12;
  let top = Math.min(pointerY - tipRect.height - 14, rect.top - tipRect.height - 10);
  if (target.classList.contains('atd-tip-right')) {
    left = rect.right - tipRect.width;
    top = rect.top + Math.max(0, (rect.height - tipRect.height) / 2);
  }
  if (left + tipRect.width > docEl.clientWidth - margin) left = docEl.clientWidth - tipRect.width - margin;
  if (left < margin) left = margin;
  if (top < margin) top = Math.min(rect.bottom + 10, docEl.clientHeight - tipRect.height - margin);
  _tooltipEl.style.left = `${Math.round(left)}px`;
  _tooltipEl.style.top = `${Math.round(top)}px`;
}

function _onMouseOver(event) {
  const target = _tooltipTarget(event.target);
  if (!target || target === _activeTarget) return;
  _showTooltip(target, event);
}

function _onMouseMove(event) {
  _lastMouse = { x: event.clientX, y: event.clientY };
  if (_activeTarget) _positionTooltip(_activeTarget, event);
}

function _onMouseOut(event) {
  const target = _tooltipTarget(event.target);
  if (!target) return;
  const related = _tooltipTarget(event.relatedTarget);
  if (related === target) return;
  _hideTooltip(target);
}

function _onFocusIn(event) {
  const target = _tooltipTarget(event.target);
  if (!target) return;
  _showTooltip(target, { clientX: _lastMouse.x, clientY: _lastMouse.y });
}

function _onFocusOut(event) {
  const target = _tooltipTarget(event.target);
  if (!target) return;
  _hideTooltip(target);
}
