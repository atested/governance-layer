/**
 * Configuration window — child window (depth 1).
 * D-042 redesign: v3 architecture surfaces — Policy Rules, Base Directories,
 * Discovered Tools, Signing, Proxy. Clickable panes open grandchild
 * drill-downs with detail and education.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';
import { installWindowTooltips, setTooltip, setTooltips } from '../tooltip-utils.js';
import { authorizeExport, downloadExport } from '../export-utils.js';

/**
 * Open the Configuration window.
 * @param {HTMLElement|null} trigger
 */
export function openConfigWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'cf-root';

  const result = _openAsChild('Configuration', 'Manage your policy rules and settings', trigger, content);
  if (!result) return;

  const state = { el: content, config: null, editMode: false };
  _loadData(state);
}

// ---------- Data ----------

async function _loadData(state) {
  state.el.innerHTML = '<div class="cf-loading">Loading configuration\u2026</div>';

  const res = await api.getConfig();
  if (!res.ok) {
    state.el.innerHTML = `<div class="cf-error">${_esc(res.error)}</div>`;
    return;
  }

  state.config = res.data;
  _renderAll(state);
  installWindowTooltips(state.el);
  _applyStaticTooltips(state);
}

// ---------- Render ----------

function _renderAll(state) {
  const cfg = state.config;
  const el = state.el;
  el.innerHTML = '';

  const rules = cfg.policy_rules?.rules || [];
  const baseDirs = cfg.policy_rules?.base_dirs || [];
  const mappings = cfg.learned_mappings || {};
  const mappingCount = Object.keys(mappings).length;
  const signing = cfg.signing || {};

  // Summary stat cards
  const stats = document.createElement('div');
  stats.className = 'cf-stats';
  stats.innerHTML = `
    <div class="cf-stat-card">
      <span class="cf-stat-label">Policy Rules</span>
      <span class="cf-stat-value">${rules.length}</span>
    </div>
    <div class="cf-stat-card">
      <span class="cf-stat-label">Base Directories</span>
      <span class="cf-stat-value">${baseDirs.length}</span>
    </div>
    <div class="cf-stat-card">
      <span class="cf-stat-label">Discovered Tools</span>
      <span class="cf-stat-value">${mappingCount}</span>
    </div>
    <div class="cf-stat-card">
      <span class="cf-stat-label">Signing</span>
      <span class="cf-stat-value ${signing.active ? 'cf-val-green' : 'cf-val-amber'}">${signing.active ? 'Active' : 'Inactive'}</span>
    </div>
  `;
  el.appendChild(stats);

  // Edit mode pane
  el.appendChild(_buildEditPane(state));

  // Policy Rules pane
  el.appendChild(_buildPolicyRulesPane(state, rules));

  // Base Directories pane (full width)
  el.appendChild(_buildBaseDirsPane(state, baseDirs));

  // Bottom row: Discovered Tools + Signing/Proxy
  const bottomRow = document.createElement('div');
  bottomRow.className = 'cf-bottom-row';
  bottomRow.appendChild(_buildDiscoveredToolsPane(state, mappings));
  bottomRow.appendChild(_buildSigningProxyPane(state, signing, cfg.proxy || {}));
  el.appendChild(bottomRow);
}

// ---------- Edit mode pane ----------

function _buildEditPane(state) {
  const pane = document.createElement('div');
  pane.className = 'cf-pane';
  pane.innerHTML = `
    <div class="cf-pane-accent cf-accent-amber"></div>
    <div class="cf-pane-header">Edit mode</div>
    <div class="cf-pane-body">
      <p class="cf-pane-copy">Editing requires your license key. All changes are recorded in the chain.</p>
      <div class="cf-edit-form">
        <input type="text" class="cf-input cf-edit-input" id="cf-license-key" placeholder="atested-xxxx-xxxx-xxxx">
        <button class="cf-btn cf-btn-primary" id="cf-unlock-btn">Unlock</button>
      </div>
      <div id="cf-unlock-result"></div>
    </div>
  `;
  setTooltip(pane.querySelector('#cf-license-key'), 'Enter a valid license key to unlock real configuration editing.');
  setTooltip(pane.querySelector('#cf-unlock-btn'), 'Verify the license key before enabling edit mode.');

  pane.querySelector('#cf-unlock-btn').addEventListener('click', () => _handleUnlock(state, pane));
  pane.querySelector('#cf-license-key').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') _handleUnlock(state, pane);
  });

  return pane;
}

async function _handleUnlock(state, pane) {
  const keyInput = pane.querySelector('#cf-license-key');
  const key = keyInput.value.trim() || (_isDemoSimulation() ? 'demo-unlock' : '');
  const resultEl = pane.querySelector('#cf-unlock-result');

  if (!key) {
    resultEl.className = 'cf-result-error';
    resultEl.textContent = 'Please enter a license key.';
    return;
  }

  const res = await api.postVerifyLicense({ license_key: key });
  if (!res.ok || !res.data?.valid) {
    resultEl.className = 'cf-result-error';
    resultEl.textContent = res.error || 'Invalid license key.';
    return;
  }

  state.editMode = true;
  resultEl.className = 'cf-result-success';
  resultEl.textContent = 'Edit mode active. Changes will be recorded in the chain.';
}

function _isDemoSimulation() {
  return window.location.pathname.startsWith('/demo/')
    || window.location.pathname === '/demo'
    || window.location.pathname.startsWith('/pricing/')
    || window.location.search.includes('demo=1');
}

// ---------- Policy Rules pane ----------

function _buildPolicyRulesPane(state, rules) {
  const pane = document.createElement('div');
  pane.className = 'cf-pane cf-pane-clickable';
  const previewCount = Math.min(rules.length, 4);

  pane.innerHTML = `
    <div class="cf-pane-accent cf-accent-green"></div>
    <div class="cf-pane-header-row">
      <span class="cf-pane-header">Policy rules</span>
      <span class="cf-pane-meta">${rules.length} rules \u00b7 first-match evaluation</span>
    </div>
    <div class="cf-pane-body">
      <div class="cf-rule-cards" id="cf-rule-cards-preview"></div>
      ${rules.length > previewCount ? `<div class="cf-preview-note">Showing ${previewCount} of ${rules.length} rules. Click for all rules.</div>` : ''}
    </div>
  `;

  const container = pane.querySelector('#cf-rule-cards-preview');
  for (let i = 0; i < previewCount; i++) {
    container.appendChild(_buildRuleCard(rules[i], i));
  }

  pane.addEventListener('click', () => _openPolicyRulesDetail(state, rules));
  setTooltip(pane, 'Open the full policy ruleset with details and export.');
  return pane;
}

function _buildRuleCard(rule, index) {
  const card = document.createElement('div');
  const match = rule.match || {};
  const decision = rule.decision || 'DENY';
  const decClass = decision === 'ALLOW' ? 'cf-rc-allow' : 'cf-rc-deny';
  card.className = `cf-rule-card ${decClass}`;

  // Conditions
  const conditions = [];
  if (match.action_type) conditions.push(`Action: ${match.action_type.join(', ')}`);
  if (match.confidence_tier) conditions.push(`Tier: ${match.confidence_tier.map(t => `T${t}`).join(', ')}`);
  if (match.scope) conditions.push(`Scope: ${match.scope.join(', ')}`);
  if (match.target_within_base_dirs === true) conditions.push('Target: within base dirs');
  if (match.target_within_base_dirs === false) conditions.push('Target: outside base dirs');
  if (match.no_hidden_paths) conditions.push('No hidden paths');
  if (match.no_executable_output) conditions.push('No executable output');

  card.innerHTML = `
    <div class="cf-rc-header">
      <span class="cf-rc-order">${index + 1}</span>
      <span class="cf-rc-id">${_esc(rule.id || '')}</span>
      <span class="cf-decision cf-decision-${decision.toLowerCase()}">${_esc(decision)}</span>
    </div>
    <div class="cf-rc-desc">${_esc(rule.description || '')}</div>
    ${conditions.length ? `<div class="cf-rc-conditions">${conditions.map(c => `<span class="cf-rc-cond">${_esc(c)}</span>`).join('')}</div>` : ''}
  `;
  return card;
}

// ---------- Base Directories pane ----------

function _buildBaseDirsPane(state, baseDirs) {
  const pane = document.createElement('div');
  pane.className = 'cf-pane cf-pane-clickable';
  const policyRules = state.config?.policy_rules || {};
  const denyHidden = policyRules.deny_hidden_paths !== false;
  const denyExec = policyRules.deny_executable_outputs !== false;

  const displayDirs = baseDirs.map(d =>
    d === '__GOV_CANONICAL_REPO_PATH__' ? '(repository root)' :
    d === '__GOV_RUNTIME_PATH__' ? '(runtime directory)' : d
  );

  pane.innerHTML = `
    <div class="cf-pane-accent cf-accent-green"></div>
    <div class="cf-pane-header-row">
      <span class="cf-pane-header">Base directories</span>
      <span class="cf-pane-meta">${baseDirs.length} directories</span>
    </div>
    <div class="cf-pane-body">
      <div class="cf-dirs-list">
        ${displayDirs.map(d => `<div class="cf-dir-entry">${_esc(d)}</div>`).join('')}
      </div>
      <div class="cf-constraints">
        <span class="cf-constraint ${denyHidden ? 'cf-constraint-on' : 'cf-constraint-off'}">${denyHidden ? 'Deny hidden paths' : 'Hidden paths allowed'}</span>
        <span class="cf-constraint ${denyExec ? 'cf-constraint-on' : 'cf-constraint-off'}">${denyExec ? 'Deny executable outputs' : 'Executable outputs allowed'}</span>
      </div>
    </div>
  `;

  pane.addEventListener('click', () => _openBaseDirsDetail(state, baseDirs, displayDirs));
  setTooltip(pane, 'Open authorized path scope details.');
  return pane;
}

// ---------- Discovered Tools pane ----------

function _buildDiscoveredToolsPane(state, mappings) {
  const entries = Object.entries(mappings);
  const pane = document.createElement('div');
  pane.className = 'cf-pane cf-pane-clickable';

  pane.innerHTML = `
    <div class="cf-pane-accent cf-accent-green"></div>
    <div class="cf-pane-header">Discovered tools</div>
    <div class="cf-pane-body">
      <p class="cf-pane-subtitle">Auto-classified on first contact</p>
      <div class="cf-mappings-list">
        ${entries.length ? entries.slice(0, 6).map(([name, info]) =>
          `<div class="cf-mapping-row">
            <span class="cf-mapping-name">${_esc(name)}</span>
            <span class="cf-mapping-arrow">\u2192</span>
            <span class="cf-mapping-cat">${_esc(info.maps_to || 'Unknown')}</span>
          </div>`
        ).join('') : '<div class="cf-empty">No discovered tools yet.</div>'}
        ${entries.length > 6 ? `<div class="cf-preview-note">${entries.length - 6} more\u2026</div>` : ''}
      </div>
    </div>
  `;

  pane.addEventListener('click', () => _openDiscoveredToolsDetail(state, mappings));
  setTooltip(pane, 'Open discovered action mappings and classifier reasons.');
  return pane;
}

// ---------- Signing + Proxy pane ----------

function _buildSigningProxyPane(state, signing, proxy) {
  const pane = document.createElement('div');
  pane.className = 'cf-pane cf-pane-clickable';

  const fp = signing.fingerprint || 'N/A';
  const fpShort = fp.length > 24 ? fp.substring(0, 12) + '\u2026' + fp.substring(fp.length - 8) : fp;

  pane.innerHTML = `
    <div class="cf-pane-accent cf-accent-green"></div>
    <div class="cf-pane-header">Signing</div>
    <div class="cf-pane-body">
      <div class="cf-kv-list">
        <div class="cf-kv"><span class="cf-kv-label">Status</span><span class="cf-kv-value ${signing.active ? 'cf-val-green' : 'cf-val-amber'}">${signing.active ? 'Active' : 'Inactive'}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Key fingerprint</span><span class="cf-kv-value cf-kv-mono">${_esc(fpShort)}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Algorithm</span><span class="cf-kv-value">${_esc(signing.algorithm || 'Ed25519')}</span></div>
      </div>
      <div class="cf-divider"></div>
      <div class="cf-sub-header">Proxy</div>
      <div class="cf-kv-list">
        <div class="cf-kv"><span class="cf-kv-label">Port</span><span class="cf-kv-value cf-kv-mono">${proxy.port || 8080}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Provider</span><span class="cf-kv-value">${_esc(proxy.provider || 'Anthropic')}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Identity</span><span class="cf-kv-value">${_esc(proxy.identity || 'N/A')}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Status</span><span class="cf-kv-value cf-val-green">Running</span></div>
      </div>
    </div>
  `;

  // Clicking top half opens signing detail, bottom half opens proxy detail
  // For simplicity, clicking anywhere opens signing detail first
  pane.addEventListener('click', (e) => {
    const rect = pane.getBoundingClientRect();
    const divider = pane.querySelector('.cf-divider');
    if (divider) {
      const divRect = divider.getBoundingClientRect();
      if (e.clientY > divRect.top) {
        _openProxyDetail(state, proxy);
        return;
      }
    }
    _openSigningDetail(state, signing);
  });

  return pane;
}

function _applyStaticTooltips(state) {
  setTooltips(state.el, [
    ['.cf-stat-card:nth-child(1)', 'Number of declarative policy rules currently loaded.'],
    ['.cf-stat-card:nth-child(2)', 'Directories policy considers authorized for file operations.'],
    ['.cf-stat-card:nth-child(3)', 'Tools Atested has learned from observed activity.'],
    ['.cf-stat-card:nth-child(4)', 'Whether chain records are being signed.'],
    ['.cf-pane-header', 'Configuration section. Click panes for details where available.'],
    ['.cf-btn-export', 'Export this configuration data for external review.'],
  ]);
}

// ================================================================
// GRANDCHILD DRILL-DOWNS
// ================================================================

// ---------- Policy Rules detail ----------

function _openPolicyRulesDetail(state, rules) {
  const content = document.createElement('div');
  content.className = 'cf-gc';

  content.innerHTML = `
    <div class="cf-gc-accent cf-accent-green"></div>
    <div class="cf-gc-header">Policy rules</div>
    <div class="cf-gc-section">
      <p class="cf-gc-explain">Your policy rules are evaluated in order. When Atested intercepts an operation, it classifies the operation and then walks through these rules top to bottom. The first rule whose conditions match determines the decision. If no rule matches, the default decision is <strong>DENY</strong>.</p>
      <p class="cf-gc-explain">This is called <em>first-match evaluation</em>. The order of your rules matters. More specific rules should come before more general ones.</p>
    </div>
  `;

  // Export control
  const exportSection = document.createElement('div');
  exportSection.className = 'cf-gc-section';
  const exportControl = document.createElement('div');
  exportControl.className = 'cf-export-control';
  const exportFormat = document.createElement('select');
  exportFormat.className = 'cf-select cf-export-format';
  exportFormat.innerHTML = `
    <option value="json">JSON</option>
    <option value="csv">CSV</option>
    <option value="excel">Excel</option>
  `;
  setTooltip(exportFormat, 'Choose JSON, CSV, or Excel-compatible export format.');
  const exportBtn = document.createElement('button');
  exportBtn.className = 'cf-btn cf-btn-export';
  exportBtn.textContent = 'Export';
  setTooltip(exportBtn, 'Export the policy rules in the selected format.');
  exportBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    _exportPolicyRules(state.config?.policy_rules || {}, exportFormat.value || 'json');
  });
  exportControl.appendChild(exportFormat);
  exportControl.appendChild(exportBtn);
  exportSection.appendChild(exportControl);
  content.appendChild(exportSection);

  // Full rule cards
  const cardsSection = document.createElement('div');
  cardsSection.className = 'cf-gc-section';
  const cards = document.createElement('div');
  cards.className = 'cf-rule-cards';
  rules.forEach((r, i) => cards.appendChild(_buildRuleCard(r, i)));
  cardsSection.appendChild(cards);
  content.appendChild(cardsSection);

  // Default decision note
  const defaultNote = document.createElement('div');
  defaultNote.className = 'cf-gc-section';
  const defaultDecision = state.config?.policy_rules?.default_decision || 'DENY';
  defaultNote.innerHTML = `<p class="cf-gc-note">Default decision (when no rule matches): <strong class="cf-decision cf-decision-${defaultDecision.toLowerCase()}">${_esc(defaultDecision)}</strong></p>`;
  content.appendChild(defaultNote);

  modalManager.open({ title: 'Policy Rules', subtitle: 'Your declarative governance rules', trigger: state.el, content });
}

async function _exportPolicyRules(policyRules, format = 'json') {
  const rules = policyRules?.rules || [];
  const date = new Date().toISOString().slice(0, 10);
  const columns = [
    { key: 'order', label: '#' },
    { key: 'id', label: 'ID' },
    { key: 'description', label: 'Description' },
    { key: 'decision', label: 'Decision' },
    { key: 'tiers', label: 'Tier' },
    { key: 'action_types', label: 'Action types' },
  ];
  const rows = rules.map((rule, idx) => ({
    order: idx + 1,
    id: rule.id || '',
    description: rule.description || '',
    decision: rule.decision || 'DENY',
    tiers: (rule.match?.confidence_tier || []).join(', '),
    action_types: Array.isArray(rule.match?.action_type) ? rule.match.action_type.join(', ') : (rule.match?.action_type || ''),
  }));
  const auth = await authorizeExport({
    surface: 'configuration',
    format,
    filters: { artifact: 'policy_rules' },
    record_count: rules.length,
    chain_source: 'live',
  });
  if (!auth.ok) return;
  downloadExport(format, `atested-policy-rules-${date}`, columns, rows, {
    sheetName: 'Policy Rules',
    jsonData: () => policyRules,
  });
}

// ---------- Base Directories detail ----------

function _openBaseDirsDetail(state, baseDirs, displayDirs) {
  const content = document.createElement('div');
  content.className = 'cf-gc';

  content.innerHTML = `
    <div class="cf-gc-accent cf-accent-green"></div>
    <div class="cf-gc-header">Base directories</div>
    <div class="cf-gc-section">
      <p class="cf-gc-explain">These are the directories Atested considers authorized for your AI applications to access. Operations targeting paths within these directories are evaluated by your policy rules. Operations targeting paths outside these directories are denied.</p>
      <p class="cf-gc-explain">The repository root and runtime directory are always included. Additional directories can be added to extend the authorized scope.</p>
    </div>
    <div class="cf-gc-section">
      <div class="cf-dirs-detail">
        ${displayDirs.map((d, i) => {
          const raw = baseDirs[i];
          const isSpecial = raw.startsWith('__');
          return `<div class="cf-dir-detail-row">
            <span class="cf-dir-path">${_esc(d)}</span>
            ${isSpecial ? `<span class="cf-dir-badge">built-in</span>` : ''}
          </div>`;
        }).join('')}
      </div>
    </div>
  `;

  modalManager.open({ title: 'Base Directories', subtitle: 'Your authorized file system paths', trigger: state.el, content });
}

// ---------- Discovered Tools detail ----------

function _openDiscoveredToolsDetail(state, mappings) {
  const entries = Object.entries(mappings);
  const content = document.createElement('div');
  content.className = 'cf-gc';

  content.innerHTML = `
    <div class="cf-gc-accent cf-accent-green"></div>
    <div class="cf-gc-header">Discovered tools</div>
    <div class="cf-gc-section">
      <p class="cf-gc-explain">When Atested encounters an action it hasn\u2019t seen before, it automatically classifies it to the nearest governance category. This ensures new actions are governed immediately without requiring manual configuration.</p>
      <p class="cf-gc-explain">The classification is based on the action\u2019s name and behavior patterns. If an auto-classification is wrong, you can override it in edit mode.</p>
    </div>
  `;

  if (!entries.length) {
    const empty = document.createElement('div');
    empty.className = 'cf-gc-section';
    empty.innerHTML = '<p class="cf-gc-note">No actions have been auto-classified yet. Actions will appear here as Atested encounters them during operation.</p>';
    content.appendChild(empty);
  } else {
    const tableSection = document.createElement('div');
    tableSection.className = 'cf-gc-section';

    const table = document.createElement('table');
    table.className = 'cf-tools-table';
    table.innerHTML = `<thead><tr>
      <th>Action</th>
      <th style="width:120px">Mapped to</th>
      <th style="width:100px">Reason</th>
      <th style="width:130px">First seen</th>
    </tr></thead>`;

    const tbody = document.createElement('tbody');
    for (const [name, info] of entries) {
      const tr = document.createElement('tr');
      const reasonLabel = (info.reason || '').replace('pattern_match:', 'Pattern: ').replace('no_pattern_match', 'Default mapping');
      tr.innerHTML = `
        <td class="cf-cell-tool">${_esc(name)}</td>
        <td>${_esc(info.maps_to || 'Unknown')}</td>
        <td class="cf-cell-muted">${_esc(reasonLabel)}</td>
        <td class="cf-cell-muted">${_esc(_formatHumanDate(info.first_seen_utc))}</td>
      `;
      tbody.appendChild(tr);
    }
    table.appendChild(tbody);
    tableSection.appendChild(table);
    content.appendChild(tableSection);
  }

  modalManager.open({ title: 'Discovered Actions', subtitle: 'Auto-classified actions in your installation', trigger: state.el, content });
}

// ---------- Signing detail ----------

function _openSigningDetail(state, signing) {
  const content = document.createElement('div');
  content.className = 'cf-gc';

  const fp = signing.fingerprint || 'N/A';

  content.innerHTML = `
    <div class="cf-gc-accent cf-accent-green"></div>
    <div class="cf-gc-header">Signing</div>
    <div class="cf-gc-section">
      <p class="cf-gc-explain">Every record in your governance chain is signed with an Ed25519 cryptographic key. This means anyone with your public key can independently verify that the records were produced by your installation and have not been altered.</p>
    </div>
    <div class="cf-gc-section">
      <div class="cf-gc-sub-header">How it works</div>
      <p class="cf-gc-explain">Atested generates an Ed25519 key pair. Each record written to the chain is signed with the private key, and the signature is embedded in the record alongside a key identifier. The hash chain links records together, so tampering with any record breaks the chain from that point forward. Signing adds attribution on top of tamper-evidence.</p>
    </div>
    <div class="cf-gc-section">
      <div class="cf-gc-sub-header">Your key</div>
      <div class="cf-kv-list">
        <div class="cf-kv"><span class="cf-kv-label">Status</span><span class="cf-kv-value ${signing.active ? 'cf-val-green' : 'cf-val-amber'}">${signing.active ? 'Active' : 'Inactive'}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Algorithm</span><span class="cf-kv-value">${_esc(signing.algorithm || 'Ed25519')}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Fingerprint</span><span class="cf-kv-value cf-kv-mono cf-kv-copyable" title="Click to copy">${_esc(fp)}</span></div>
      </div>
    </div>
    <div class="cf-gc-section">
      <div class="cf-gc-sub-header">Unsigned records</div>
      <p class="cf-gc-explain">Records created before signing was enabled exist in your chain without signatures. The chain verifier handles both signed and unsigned records. New records are always signed when a key is configured.</p>
    </div>
    <div class="cf-gc-section">
      <div class="cf-gc-sub-header">Why signing matters</div>
      <p class="cf-gc-explain">Signing is what makes Atested\u2019s audit trail independently verifiable. Without signing, the chain is tamper-evident through hash chaining but not independently attributable to your installation. With signing, a third party can verify both the integrity and the origin of every record.</p>
    </div>
  `;

  // Copy fingerprint on click
  const fpEl = content.querySelector('.cf-kv-copyable');
  if (fpEl) {
    fpEl.addEventListener('click', () => {
      navigator.clipboard?.writeText(fp).then(() => {
        fpEl.textContent = 'Copied!';
        setTimeout(() => { fpEl.textContent = fp; }, 1500);
      });
    });
  }

  modalManager.open({ title: 'Signing', subtitle: 'How Atested verifies your chain', trigger: state.el, content });
}

// ---------- Proxy detail ----------

function _openProxyDetail(state, proxy) {
  const content = document.createElement('div');
  content.className = 'cf-gc';

  content.innerHTML = `
    <div class="cf-gc-accent cf-accent-green"></div>
    <div class="cf-gc-header">Proxy configuration</div>
    <div class="cf-gc-section">
      <div class="cf-kv-list">
        <div class="cf-kv"><span class="cf-kv-label">Port</span><span class="cf-kv-value cf-kv-mono">${proxy.port || 8080}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Host</span><span class="cf-kv-value cf-kv-mono">${_esc(proxy.host || '127.0.0.1')}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Provider</span><span class="cf-kv-value">${_esc(proxy.provider || 'Anthropic')}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Upstream</span><span class="cf-kv-value cf-kv-mono">${_esc(proxy.upstream || 'https://api.anthropic.com')}</span></div>
        <div class="cf-kv"><span class="cf-kv-label">Identity</span><span class="cf-kv-value">${_esc(proxy.identity || 'N/A')}</span></div>
      </div>
    </div>
    <div class="cf-gc-section">
      <div class="cf-gc-sub-header">How the proxy works</div>
      <p class="cf-gc-explain">The Atested proxy sits between your AI application and the model provider. It intercepts action requests from the model, classifies each operation, evaluates it against your policy rules, and records the decision in the governance chain. Allowed operations pass through unchanged. Denied operations are replaced with a denial message that the model sees and can respond to.</p>
    </div>
    <div class="cf-gc-section">
      <div class="cf-gc-sub-header">Setup</div>
      <p class="cf-gc-explain">Point your AI application at the proxy instead of the provider directly:</p>
      <pre class="cf-code-block">ANTHROPIC_BASE_URL=http://localhost:${proxy.port || 8080}/anthropic</pre>
      <p class="cf-gc-explain">The proxy handles authentication forwarding. Your API key is passed through to the upstream provider.</p>
    </div>
    <div class="cf-gc-section">
      <div class="cf-gc-sub-header">Supported providers</div>
      <p class="cf-gc-explain">Anthropic is the primary supported provider. The proxy architecture supports additional providers through route mapping. Each provider gets its own path prefix (e.g., <code>/anthropic</code>) to keep API routing clean.</p>
    </div>
    <div class="cf-gc-section">
      <div class="cf-gc-sub-header">Security</div>
      <p class="cf-gc-explain">The proxy binds to <code>127.0.0.1</code> by default, meaning it only accepts connections from the local machine. This is intentional. The proxy should run on the same machine as your AI application.</p>
    </div>
  `;

  modalManager.open({ title: 'Proxy', subtitle: 'Installation and provider configuration', trigger: state.el, content });
}

// ---------- Utility ----------

function _openAsChild(title, subtitle, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, subtitle, trigger, content });
  return modalManager.open({ title, subtitle, trigger, content });
}

function _formatHumanDate(isoStr) {
  if (!isoStr) return 'N/A';
  try {
    const d = new Date(isoStr);
    const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    return `${months[d.getMonth()]} ${d.getDate()}, ${hh}:${mm}`;
  } catch { return isoStr; }
}

function _esc(str) {
  const el = document.createElement('span');
  el.textContent = str || '';
  return el.innerHTML;
}

function _escAttr(str) {
  return (str || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ---------- Styles ----------

const cfStyles = document.createElement('style');
cfStyles.textContent = `
  .cf-root {
    font-family: "Inter", system-ui, sans-serif;
    color: #e4e6eb;
  }

  /* ---- Stat cards ---- */
  .cf-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }
  .cf-stat-card {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    padding: 14px 16px;
    text-align: center;
  }
  .cf-stat-label {
    display: block;
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    margin-bottom: 4px;
    font-weight: 500;
  }
  .cf-stat-value {
    font-size: 1.4rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .cf-val-green { color: #3fb950; }
  .cf-val-amber { color: #d29922; }

  /* ---- Pane ---- */
  .cf-pane {
    background: #22262e;
    border: 1px dashed rgba(255,255,255,0.12);
    border-radius: 2px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .cf-pane-clickable {
    cursor: pointer;
    transition: border-color 0.12s, box-shadow 0.12s;
  }
  .cf-pane-clickable:hover {
    border-color: rgba(102,153,204,0.3);
  }
  .cf-pane-accent { height: 6px; }
  .cf-accent-green { background: #3fb950; }
  .cf-accent-amber { background: #d29922; }
  .cf-pane-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
    padding: 12px 20px 4px;
  }
  .cf-pane-header-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px 4px;
  }
  .cf-pane-header-row .cf-pane-header { padding: 0; }
  .cf-pane-meta {
    font-size: 0.72rem;
    color: #8b919a;
    font-weight: 500;
  }
  .cf-pane-body { padding: 8px 20px 16px; }
  .cf-pane-copy {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.5;
    margin: 0 0 12px;
  }
  .cf-pane-subtitle {
    font-size: 0.75rem;
    color: #8b919a;
    margin: 0 0 10px;
    font-style: italic;
  }

  /* ---- Edit form ---- */
  .cf-edit-form { display: flex; gap: 8px; align-items: center; }
  .cf-edit-input { flex: 1; }
  .cf-input {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 7px 12px;
    box-sizing: border-box;
  }
  .cf-select {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 2px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 7px 12px;
    box-sizing: border-box;
  }
  .cf-input:focus { outline: 2px solid #6699cc; outline-offset: 1px; }
  .cf-select:focus { outline: 2px solid #6699cc; outline-offset: 1px; }
  .cf-result-success { color: #3fb950; font-size: 0.82rem; margin-top: 8px; }
  .cf-result-error { color: #d29922; font-size: 0.82rem; margin-top: 8px; }

  /* ---- Buttons ---- */
  .cf-btn {
    border: none;
    border-radius: 2px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 7px 18px;
    cursor: pointer;
    transition: background 0.1s;
    white-space: nowrap;
  }
  .cf-btn-primary { background: #6699cc; color: #fff; }
  .cf-btn-primary:hover { background: #5580aa; }
  .cf-btn-export {
    background: rgba(210,153,34,0.12);
    color: #d29922;
    border: 1px solid rgba(210,153,34,0.3);
    margin-bottom: 10px;
  }
  .cf-btn-export:hover { background: rgba(210,153,34,0.20); }
  .cf-export-control {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
  }
  .cf-export-format {
    min-width: 90px;
  }

  /* ---- Rules preview table ---- */
  .cf-rules-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .cf-rules-table thead th {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    font-weight: 600;
    text-align: left;
    padding: 4px 8px 6px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    white-space: nowrap;
  }
  .cf-rules-table tbody td {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 200px;
  }
  .cf-rules-full tbody tr {
    cursor: pointer;
    transition: background 0.1s;
  }
  .cf-rules-full tbody tr:hover { background: rgba(102,153,204,0.06); }
  .cf-cell-num {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #6b7280;
  }
  .cf-cell-id {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
  }
  .cf-cell-tool {
    font-family: "JetBrains Mono", monospace;
    color: #e4e6eb;
  }
  .cf-cell-muted { color: #8b919a; }

  /* Decision badges */
  .cf-decision {
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 1px 8px;
    border-radius: 2px;
  }
  .cf-decision-allow { color: #3fb950; }
  .cf-decision-deny { color: #f85149; }

  /* Tier badges */
  .cf-tier {
    display: inline-block;
    font-size: 0.62rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    padding: 1px 6px;
    border-radius: 2px;
    margin-right: 2px;
  }
  .cf-tier-1 { color: #3fb950; }
  .cf-tier-2 { color: #6699cc; }
  .cf-tier-3 { color: #d29922; }
  .cf-tier-4 { color: #f85149; }

  .cf-preview-note {
    font-size: 0.75rem;
    color: #6b7280;
    padding: 8px 0 0;
    font-style: italic;
  }

  /* ---- Rule cards ---- */
  .cf-rule-cards { display: flex; flex-direction: column; gap: 8px; }
  .cf-rule-card {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 2px;
    padding: 10px 14px;
    border-left: 3px solid #6b7280;
  }
  .cf-rc-allow { border-left-color: #3fb950; }
  .cf-rc-deny { border-left-color: #f85149; }
  .cf-rc-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 4px;
  }
  .cf-rc-order {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.68rem;
    color: #6b7280;
    min-width: 18px;
  }
  .cf-rc-id {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.75rem;
    color: #e4e6eb;
    flex: 1;
  }
  .cf-rc-desc {
    font-size: 0.78rem;
    color: #8b919a;
    line-height: 1.4;
    margin-bottom: 6px;
    padding-left: 26px;
  }
  .cf-rc-conditions {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    padding-left: 26px;
  }
  .cf-rc-cond {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.65rem;
    color: #8b919a;
    background: rgba(255,255,255,0.04);
    padding: 2px 7px;
    border-radius: 2px;
    border: 1px solid rgba(255,255,255,0.06);
  }

  /* ---- Constraints ---- */
  .cf-constraints {
    display: flex;
    gap: 8px;
    margin-top: 10px;
    flex-wrap: wrap;
  }
  .cf-constraint {
    font-size: 0.68rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    padding: 3px 10px;
    border-radius: 2px;
    border: 1px solid rgba(255,255,255,0.08);
  }
  .cf-constraint-on { color: #3fb950; border-color: rgba(63,185,80,0.25); }
  .cf-constraint-off { color: #8b919a; }

  /* ---- Rule JSON expand ---- */
  .cf-rule-expand td { padding: 0 8px 8px; }
  .cf-rule-json {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 2px;
    padding: 10px 14px;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.72rem;
    color: #8b919a;
    white-space: pre-wrap;
    word-break: break-all;
    margin: 0;
    max-height: 200px;
    overflow-y: auto;
  }

  /* ---- Base directories ---- */
  .cf-dirs-list { display: flex; flex-direction: column; gap: 4px; }
  .cf-dir-entry {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 2px;
    padding: 8px 14px;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.78rem;
    color: #e4e6eb;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .cf-dirs-detail { display: flex; flex-direction: column; gap: 6px; }
  .cf-dir-detail-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 2px;
    padding: 10px 14px;
  }
  .cf-dir-path {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.78rem;
    color: #e4e6eb;
  }
  .cf-dir-badge {
    font-size: 0.62rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #6699cc;
    padding: 2px 8px;
    border-radius: 2px;
  }

  /* ---- Discovered tools ---- */
  .cf-mappings-list { display: flex; flex-direction: column; gap: 4px; }
  .cf-mapping-row {
    display: flex;
    align-items: center;
    gap: 10px;
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 2px;
    padding: 7px 14px;
  }
  .cf-mapping-name {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.78rem;
    color: #e4e6eb;
    flex: 1;
  }
  .cf-mapping-arrow { color: #6b7280; font-size: 0.82rem; }
  .cf-mapping-cat {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.78rem;
    color: #6699cc;
  }
  .cf-tools-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
  }
  .cf-tools-table thead th {
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6b7280;
    font-weight: 600;
    text-align: left;
    padding: 4px 8px 6px;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }
  .cf-tools-table tbody td {
    padding: 6px 8px;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }

  /* ---- KV list ---- */
  .cf-kv-list { display: flex; flex-direction: column; }
  .cf-kv {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 5px 0;
  }
  .cf-kv-label { font-size: 0.78rem; color: #8b919a; }
  .cf-kv-value { font-size: 0.82rem; color: #e4e6eb; }
  .cf-kv-mono { font-family: "JetBrains Mono", monospace; font-size: 0.75rem; }
  .cf-kv-copyable { cursor: pointer; }
  .cf-kv-copyable:hover { color: #6699cc; }

  /* ---- Divider ---- */
  .cf-divider {
    height: 1px;
    background: rgba(255,255,255,0.06);
    margin: 10px 0;
  }
  .cf-sub-header {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #6699cc;
    font-weight: 600;
    margin-bottom: 6px;
  }

  /* ---- Bottom row ---- */
  .cf-bottom-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
  }

  /* ---- Grandchild ---- */
  .cf-gc { font-family: "Inter", system-ui, sans-serif; }
  .cf-gc-accent {
    height: 6px;
    margin: -24px -24px 0;
    border-radius: 2px 2px 0 0;
  }
  .cf-gc-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #6699cc;
    font-weight: 600;
    padding: 14px 0 10px;
  }
  .cf-gc-sub-header {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #8b919a;
    font-weight: 600;
    padding: 6px 0;
    margin-top: 4px;
  }
  .cf-gc-section { margin-bottom: 12px; }
  .cf-gc-explain {
    font-size: 0.82rem;
    color: #8b919a;
    line-height: 1.6;
    margin: 0 0 8px;
  }
  .cf-gc-explain strong { color: #e4e6eb; }
  .cf-gc-explain em { font-style: italic; }
  .cf-gc-explain code {
    font-family: "JetBrains Mono", monospace;
    font-size: 0.75rem;
    background: rgba(255,255,255,0.04);
    padding: 1px 5px;
    border-radius: 2px;
    color: #e4e6eb;
  }
  .cf-gc-note {
    font-size: 0.82rem;
    color: #6b7280;
    font-style: italic;
    margin: 0;
  }
  .cf-code-block {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 2px;
    padding: 10px 14px;
    font-family: "JetBrains Mono", monospace;
    font-size: 0.75rem;
    color: #e4e6eb;
    margin: 6px 0 10px;
    white-space: pre-wrap;
    word-break: break-all;
  }

  /* ---- Utility ---- */
  .cf-loading {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 40px 0;
  }
  .cf-empty {
    color: #8b919a;
    font-size: 0.82rem;
    text-align: center;
    padding: 16px 0;
    font-style: italic;
  }
  .cf-error {
    color: #d29922;
    padding: 12px 16px;
    border-radius: 2px;
    font-size: 0.82rem;
  }

  /* ---- Responsive ---- */
  @media (max-width: 600px) {
    .cf-stats { grid-template-columns: repeat(2, 1fr); }
    .cf-bottom-row { grid-template-columns: 1fr; }
    .cf-edit-form { flex-direction: column; }
  }
`;
document.head.appendChild(cfStyles);
