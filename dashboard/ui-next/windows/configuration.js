/**
 * Configuration window — child window (depth 1).
 * Spec v2 section 7.6.
 *
 * View and manage the capability registry. View mode shows registry
 * status and governed tools. Edit mode (after license key verification)
 * allows modifying directories and constraints.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import '../components/status-card.js';
import '../components/status-grid.js';
import '../components/data-table.js';
import '../components/pill.js';
import '../components/loading-indicator.js';

const VIEW_COLUMNS = [
  { key: 'name', label: 'Tool', sortable: false },
  { key: 'risk_level', label: 'Risk Level', sortable: false, width: '100px' },
  { key: 'allowed_dirs', label: 'Allowed Directories', sortable: false },
  { key: 'deny_hidden', label: 'deny_hidden', sortable: false, width: '90px' },
  { key: 'deny_overwrite', label: 'deny_overwrite', sortable: false, width: '100px' },
  { key: 'deny_exec', label: 'deny_exec', sortable: false, width: '80px' },
  { key: 'max_bytes', label: 'Max Bytes', sortable: false, width: '90px' },
];

/**
 * Open the Configuration window.
 * @param {HTMLElement|null} trigger
 */
export function openConfigWindow(trigger) {
  const content = _buildContent();
  const result = _openAsChild('Configuration', trigger, content);
  if (!result) return;

  const state = { el: content, config: null, editMode: false, originalRegistry: null };
  _wireControls(state);
  _loadData(state);
}

function _buildContent() {
  const el = document.createElement('div');
  el.className = 'cf-content';
  el.innerHTML = `
    <div class="cf-header">
      <span class="cf-eyebrow">System</span>
      <span class="cf-heading">Configuration</span>
      <span class="cf-edit-badge" id="cf-edit-badge" style="display:none">Edit Mode Active</span>
    </div>
    <div id="cf-registry-status"></div>
    <div class="cf-unlock-card" id="cf-unlock-card">
      <h3 class="cf-section-title">Unlock Editing</h3>
      <div class="cf-unlock-form">
        <input type="text" class="cf-input" id="cf-license-key" placeholder="atested-xxxx-xxxx-xxxx">
        <atd-pill variant="primary" id="cf-unlock-btn">Unlock Editing</atd-pill>
      </div>
      <div id="cf-unlock-result"></div>
    </div>
    <div id="cf-tools-section">
      <h3 class="cf-section-title">Governed Tools</h3>
      <div id="cf-tools-wrap">
        <atd-loading-indicator label="Loading configuration"></atd-loading-indicator>
      </div>
    </div>
    <div id="cf-edit-actions" style="display:none">
      <atd-pill variant="primary" id="cf-save-btn">Save Configuration</atd-pill>
      <atd-pill variant="outline" id="cf-cancel-btn">Cancel</atd-pill>
      <div id="cf-save-result"></div>
    </div>
  `;
  return el;
}

function _wireControls(state) {
  state.el.querySelector('#cf-unlock-btn').addEventListener('click', () => _handleUnlock(state));
  state.el.querySelector('#cf-save-btn').addEventListener('click', () => _handleSave(state));
  state.el.querySelector('#cf-cancel-btn').addEventListener('click', () => _exitEditMode(state));
}

async function _loadData(state) {
  const res = await api.getConfig();
  if (!res.ok) {
    state.el.querySelector('#cf-tools-wrap').innerHTML = `<div class="cf-error">${_esc(res.error)}</div>`;
    return;
  }
  state.config = res.data;
  _renderRegistryStatus(state);
  _renderToolsTable(state);
}

function _renderRegistryStatus(state) {
  const container = state.el.querySelector('#cf-registry-status');
  container.innerHTML = '';
  const cfg = state.config;

  const grid = document.createElement('atd-status-grid');
  const cards = [
    { label: 'Registry Hash', value: (cfg.registry_hash || '--').substring(0, 16) + '...' },
    { label: 'License Status', value: cfg.license_posture?.license_status?.toUpperCase() || '--' },
    { label: 'Tier', value: cfg.license_posture?.tier || '--' },
  ];
  if (cfg.license_posture?.trial_days_remaining != null) {
    cards.push({
      label: 'Trial Days',
      value: String(cfg.license_posture.trial_days_remaining),
      variant: cfg.license_posture.trial_days_remaining < 7 ? 'warning' : undefined,
    });
  }
  for (const c of cards) {
    const card = document.createElement('atd-status-card');
    card.setAttribute('label', c.label);
    card.setAttribute('value', c.value);
    if (c.variant) card.setAttribute('variant', c.variant);
    grid.appendChild(card);
  }
  container.appendChild(grid);
}

function _renderToolsTable(state) {
  const wrap = state.el.querySelector('#cf-tools-wrap');
  wrap.innerHTML = '';

  const registry = state.config?.registry;
  if (!registry) {
    wrap.innerHTML = '<p class="cf-empty">No registry data</p>';
    return;
  }

  // Extract tools from registry
  const tools = _extractTools(registry);
  if (!tools.length) {
    wrap.innerHTML = '<p class="cf-empty">No governed tools configured</p>';
    return;
  }

  if (state.editMode) {
    _renderEditForm(wrap, tools, state);
  } else {
    _renderViewTable(wrap, tools);
  }
}

function _extractTools(registry) {
  // Registry structure varies; extract tool definitions
  const tools = [];
  const actions = registry.actions || registry.tools || {};
  if (Array.isArray(actions)) {
    return actions.map(a => _normalizeToolEntry(a));
  }
  for (const [name, def] of Object.entries(actions)) {
    tools.push(_normalizeToolEntry({ name, ...def }));
  }
  return tools;
}

function _normalizeToolEntry(t) {
  const caps = t.caps || t.constraints || {};
  return {
    name: t.name || t.tool_name || '--',
    risk_level: t.risk_level || t.risk || '--',
    allowed_dirs: (t.base_dirs || t.allowed_directories || []).join(', ') || '--',
    _dirs_array: t.base_dirs || t.allowed_directories || [],
    deny_hidden: caps.deny_hidden !== false,
    deny_overwrite: caps.overwrite_allowed === false || caps.deny_overwrite === true,
    deny_exec: caps.deny_exec !== false,
    max_bytes: caps.max_bytes || caps.max_size || '--',
    _raw: t,
  };
}

function _renderViewTable(wrap, tools) {
  const table = document.createElement('atd-data-table');
  table.setAttribute('columns', JSON.stringify(VIEW_COLUMNS));
  table.setAttribute('sortable', 'false');
  table.setAttribute('page-size', '50');

  table.cellRenderer = (row, col) => {
    if (col.key === 'name') return `<strong>${_esc(row.name)}</strong>`;
    if (col.key === 'deny_hidden' || col.key === 'deny_overwrite' || col.key === 'deny_exec') {
      const val = row[col.key];
      const color = val ? '#4ade80' : '#8b919a';
      return `<span style="color:${color}">${val ? 'Yes' : 'No'}</span>`;
    }
    return null;
  };

  table.data = tools;
  table.totalCount = tools.length;
  wrap.appendChild(table);
}

function _renderEditForm(wrap, tools, state) {
  const form = document.createElement('div');
  form.className = 'cf-edit-list';

  for (let i = 0; i < tools.length; i++) {
    const t = tools[i];
    const row = document.createElement('div');
    row.className = 'cf-edit-tool';
    row.dataset.toolIndex = i;
    row.innerHTML = `
      <div class="cf-edit-tool-header">
        <strong>${_esc(t.name)}</strong>
        <span class="cf-edit-risk">${_esc(t.risk_level)}</span>
      </div>
      <div class="cf-edit-dirs" data-tool-index="${i}">
        ${t._dirs_array.map((d, di) => `
          <div class="cf-edit-dir-row">
            <input type="text" class="cf-input cf-dir-input" value="${_esc(d)}" data-dir-index="${di}">
            <button class="cf-remove-dir" data-dir-index="${di}">Remove</button>
          </div>
        `).join('')}
        <button class="cf-add-dir" data-tool-index="${i}">Add Directory</button>
      </div>
      <div class="cf-edit-caps">
        <label><input type="checkbox" class="cf-cap" data-cap="deny_hidden" ${t.deny_hidden ? 'checked' : ''}> deny_hidden</label>
        <label><input type="checkbox" class="cf-cap" data-cap="deny_overwrite" ${t.deny_overwrite ? 'checked' : ''}> deny_overwrite</label>
        <label><input type="checkbox" class="cf-cap" data-cap="deny_exec" ${t.deny_exec ? 'checked' : ''}> deny_exec</label>
        <label>Max Bytes: <input type="number" class="cf-input cf-max-bytes" value="${t.max_bytes !== '--' ? t.max_bytes : ''}" style="width:100px"></label>
      </div>
    `;

    // Wire "Add Directory" button
    row.querySelector('.cf-add-dir').addEventListener('click', () => {
      const dirsContainer = row.querySelector('.cf-edit-dirs');
      const addBtn = dirsContainer.querySelector('.cf-add-dir');
      const newRow = document.createElement('div');
      newRow.className = 'cf-edit-dir-row';
      newRow.innerHTML = `
        <input type="text" class="cf-input cf-dir-input" value="" placeholder="/path/to/directory">
        <button class="cf-remove-dir">Remove</button>
      `;
      newRow.querySelector('.cf-remove-dir').addEventListener('click', () => newRow.remove());
      dirsContainer.insertBefore(newRow, addBtn);
      newRow.querySelector('.cf-dir-input').focus();
    });

    // Wire existing "Remove" buttons
    row.querySelectorAll('.cf-remove-dir').forEach(btn => {
      btn.addEventListener('click', () => btn.closest('.cf-edit-dir-row').remove());
    });

    form.appendChild(row);
  }

  wrap.appendChild(form);
}

async function _handleUnlock(state) {
  const key = state.el.querySelector('#cf-license-key').value.trim();
  const resultEl = state.el.querySelector('#cf-unlock-result');

  if (!key) {
    resultEl.className = 'cf-result-error';
    resultEl.textContent = 'Please enter a license key';
    return;
  }

  const res = await api.postVerifyLicense({ license_key: key });
  if (!res.ok || !res.data?.valid) {
    resultEl.className = 'cf-result-error';
    resultEl.textContent = res.error || 'Invalid license key';
    return;
  }

  state.editMode = true;
  state.originalRegistry = JSON.parse(JSON.stringify(state.config?.registry || {}));
  state.el.querySelector('#cf-edit-badge').style.display = 'inline-block';
  state.el.querySelector('#cf-unlock-card').style.display = 'none';
  state.el.querySelector('#cf-edit-actions').style.display = 'flex';
  _renderToolsTable(state);
}

async function _handleSave(state) {
  const resultEl = state.el.querySelector('#cf-save-result');
  resultEl.textContent = 'Saving...';
  resultEl.className = '';

  // Collect mutated state from the edit form DOM
  const updatedRegistry = _collectEditState(state);

  const res = await api.postConfigUpdate({ registry: updatedRegistry });
  if (res.ok) {
    resultEl.className = 'cf-result-success';
    resultEl.textContent = 'Configuration saved';
    state.originalRegistry = null; // Don't revert — save succeeded
    state.editMode = false;
    state.el.querySelector('#cf-edit-badge').style.display = 'none';
    state.el.querySelector('#cf-unlock-card').style.display = 'block';
    state.el.querySelector('#cf-edit-actions').style.display = 'none';
    _loadData(state);
  } else {
    resultEl.className = 'cf-result-error';
    resultEl.textContent = `Save failed: ${res.error}`;
  }
}

/**
 * Collect the current edit form state from the DOM and build an updated
 * registry object that mirrors the original structure.
 */
function _collectEditState(state) {
  const registry = JSON.parse(JSON.stringify(state.config?.registry || {}));
  const actions = registry.actions || registry.tools || {};
  const toolEntries = Array.isArray(actions) ? actions : Object.values(actions);
  const toolKeys = Array.isArray(actions) ? null : Object.keys(actions);

  const toolRows = state.el.querySelectorAll('.cf-edit-tool');
  toolRows.forEach((row, i) => {
    const entry = toolEntries[i];
    if (!entry) return;

    // Collect directories from all input rows
    const dirs = [];
    row.querySelectorAll('.cf-dir-input').forEach(input => {
      const val = input.value.trim();
      if (val) dirs.push(val);
    });

    // Update directory arrays (try both field names)
    if (entry.base_dirs !== undefined) entry.base_dirs = dirs;
    else if (entry.allowed_directories !== undefined) entry.allowed_directories = dirs;
    else entry.base_dirs = dirs;

    // Collect constraints
    const caps = entry.caps || entry.constraints || {};
    const denyHidden = row.querySelector('[data-cap="deny_hidden"]');
    const denyOverwrite = row.querySelector('[data-cap="deny_overwrite"]');
    const denyExec = row.querySelector('[data-cap="deny_exec"]');
    const maxBytes = row.querySelector('.cf-max-bytes');

    if (denyHidden) caps.deny_hidden = denyHidden.checked;
    if (denyOverwrite) {
      if (caps.overwrite_allowed !== undefined) caps.overwrite_allowed = !denyOverwrite.checked;
      else caps.deny_overwrite = denyOverwrite.checked;
    }
    if (denyExec) caps.deny_exec = denyExec.checked;
    if (maxBytes && maxBytes.value) caps.max_bytes = parseInt(maxBytes.value, 10);

    if (entry.caps !== undefined) entry.caps = caps;
    else if (entry.constraints !== undefined) entry.constraints = caps;
    else entry.caps = caps;

    // Write back
    if (toolKeys) {
      actions[toolKeys[i]] = entry;
    } else {
      toolEntries[i] = entry;
    }
  });

  if (Array.isArray(actions)) {
    if (registry.actions) registry.actions = toolEntries;
    else registry.tools = toolEntries;
  }

  return registry;
}

function _exitEditMode(state) {
  state.editMode = false;
  if (state.originalRegistry) {
    state.config.registry = state.originalRegistry;
    state.originalRegistry = null;
  }
  state.el.querySelector('#cf-edit-badge').style.display = 'none';
  state.el.querySelector('#cf-unlock-card').style.display = 'block';
  state.el.querySelector('#cf-edit-actions').style.display = 'none';
  _renderToolsTable(state);
}

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, trigger, content });
  return modalManager.open({ title, trigger, content });
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

// Styles
const cfStyles = document.createElement('style');
cfStyles.textContent = `
  .cf-content { font-family: "Inter", system-ui, sans-serif; }
  .cf-header { margin-bottom: 16px; }
  .cf-eyebrow {
    display: block; font-size: 0.72rem; text-transform: uppercase;
    letter-spacing: 0.06em; color: #8b919a; margin-bottom: 4px;
  }
  .cf-heading { font-size: 1.25rem; font-weight: 600; color: #e4e6eb; margin-right: 12px; }
  .cf-edit-badge {
    display: inline-block; font-size: 0.72rem; font-weight: 600;
    color: #4ade80; padding: 2px 8px; border-radius: 999px;
    background: rgba(74,222,128,0.10);
  }
  .cf-section-title {
    font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
    color: #5b8af5; margin: 16px 0 10px; font-weight: 600;
  }
  .cf-unlock-card {
    background: #22262e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 14px 18px; margin-bottom: 20px;
  }
  .cf-unlock-form { display: flex; gap: 8px; align-items: center; }
  .cf-input {
    background: #1a1d23; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 6px; color: #e4e6eb; font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem; padding: 6px 10px;
  }
  .cf-input:focus { outline: 2px solid #5b8af5; outline-offset: 1px; }
  .cf-result-success { color: #4ade80; font-size: 0.82rem; margin-top: 8px; }
  .cf-result-error { color: #f59e42; font-size: 0.82rem; margin-top: 8px; }
  .cf-loading, .cf-empty {
    color: #8b919a; font-size: 0.82rem; text-align: center; padding: 24px 0; margin: 0;
  }
  .cf-error {
    color: #f59e42; background: rgba(245,158,66,0.10);
    padding: 12px 16px; border-radius: 8px; font-size: 0.82rem;
  }
  #cf-edit-actions { gap: 8px; margin-top: 16px; align-items: center; }
  .cf-edit-list { display: flex; flex-direction: column; gap: 16px; }
  .cf-edit-tool {
    background: #22262e; border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px; padding: 14px 18px;
  }
  .cf-edit-tool-header { display: flex; justify-content: space-between; margin-bottom: 10px; color: #e4e6eb; }
  .cf-edit-risk { font-size: 0.72rem; color: #8b919a; text-transform: uppercase; }
  .cf-edit-dir-row { display: flex; gap: 8px; align-items: center; margin-bottom: 6px; }
  .cf-dir-input { flex: 1; }
  .cf-remove-dir, .cf-add-dir {
    background: none; border: 1px solid rgba(255,255,255,0.08); color: #8b919a;
    border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 0.72rem;
  }
  .cf-remove-dir:hover { color: #ef4444; border-color: #ef4444; }
  .cf-add-dir:hover { color: #5b8af5; border-color: #5b8af5; }
  .cf-edit-caps { display: flex; gap: 16px; margin-top: 8px; font-size: 0.82rem; color: #e4e6eb; flex-wrap: wrap; }
  .cf-edit-caps label { display: flex; align-items: center; gap: 4px; }
  .cf-cap { accent-color: #5b8af5; }
`;
document.head.appendChild(cfStyles);
