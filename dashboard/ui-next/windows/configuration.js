/**
 * Configuration window — child window (depth 1).
 * D-042 redesign: v3 architecture surfaces — Policy Rules, Base Directories,
 * Discovered Tools, Signing, Proxy. Clickable panes open grandchild
 * drill-downs with detail and education.
 */

import * as api from '../api.js';
import { modalManager } from '../modal-manager.js';

/**
 * Open the Configuration window.
 * @param {HTMLElement|null} trigger
 */
export function openConfigWindow(trigger) {
  const content = document.createElement('div');
  content.className = 'cf-root';

  const result = _openAsChild('Configuration', trigger, content);
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

  pane.querySelector('#cf-unlock-btn').addEventListener('click', () => _handleUnlock(state, pane));
  pane.querySelector('#cf-license-key').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') _handleUnlock(state, pane);
  });

  return pane;
}

async function _handleUnlock(state, pane) {
  const key = pane.querySelector('#cf-license-key').value.trim();
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

// ---------- Policy Rules pane ----------

function _buildPolicyRulesPane(state, rules) {
  const pane = document.createElement('div');
  pane.className = 'cf-pane cf-pane-clickable';
  const previewCount = Math.min(rules.length, 6);

  pane.innerHTML = `
    <div class="cf-pane-accent cf-accent-green"></div>
    <div class="cf-pane-header-row">
      <span class="cf-pane-header">Policy rules</span>
      <span class="cf-pane-meta">${rules.length} rules \u00b7 first-match evaluation</span>
    </div>
    <div class="cf-pane-body">
      <table class="cf-rules-table">
        <thead><tr>
          <th style="width:30px">#</th>
          <th>Action pattern</th>
          <th style="width:120px">Target class</th>
          <th style="width:80px">Decision</th>
          <th style="width:60px">Tier</th>
        </tr></thead>
        <tbody></tbody>
      </table>
      ${rules.length > previewCount ? `<div class="cf-preview-note">Showing ${previewCount} of ${rules.length} rules. First match wins.</div>` : ''}
    </div>
  `;

  const tbody = pane.querySelector('tbody');
  for (let i = 0; i < previewCount; i++) {
    const r = rules[i];
    const match = r.match || {};
    const actionTypes = match.action_type ? match.action_type.join(', ') : match.scope ? match.scope.join(', ') : 'any';
    const targetClass = match.target_within_base_dirs === true ? 'within base dirs'
      : match.target_within_base_dirs === false ? 'outside base dirs'
      : match.scope ? match.scope.join(', ') : 'any';
    const decision = r.decision || 'DENY';
    const tiers = match.confidence_tier || [];

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="cf-cell-num">${i + 1}</td>
      <td title="${_escAttr(r.description || '')}">${_esc(actionTypes)}</td>
      <td>${_esc(targetClass)}</td>
      <td><span class="cf-decision cf-decision-${decision.toLowerCase()}">${_esc(decision)}</span></td>
      <td>${tiers.length ? tiers.map(t => `<span class="cf-tier cf-tier-${t}">T${t}</span>`).join(' ') : '\u2014'}</td>
    `;
    tbody.appendChild(tr);
  }

  pane.addEventListener('click', () => _openPolicyRulesDetail(state, rules));
  return pane;
}

// ---------- Base Directories pane ----------

function _buildBaseDirsPane(state, baseDirs) {
  const pane = document.createElement('div');
  pane.className = 'cf-pane cf-pane-clickable';

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
    </div>
  `;

  pane.addEventListener('click', () => _openBaseDirsDetail(state, baseDirs, displayDirs));
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

  // Full rules table
  const tableSection = document.createElement('div');
  tableSection.className = 'cf-gc-section';

  const exportBtn = document.createElement('button');
  exportBtn.className = 'cf-btn cf-btn-export';
  exportBtn.textContent = 'Export ruleset';
  exportBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    _exportPolicyRules(state.config?.policy_rules || {});
  });
  tableSection.appendChild(exportBtn);

  const table = document.createElement('table');
  table.className = 'cf-rules-table cf-rules-full';
  table.innerHTML = `<thead><tr>
    <th style="width:30px">#</th>
    <th style="width:120px">ID</th>
    <th>Description</th>
    <th style="width:80px">Decision</th>
    <th style="width:60px">Tier</th>
  </tr></thead>`;

  const tbody = document.createElement('tbody');
  rules.forEach((r, i) => {
    const match = r.match || {};
    const decision = r.decision || 'DENY';
    const tiers = match.confidence_tier || [];

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="cf-cell-num">${i + 1}</td>
      <td class="cf-cell-id">${_esc(r.id || '')}</td>
      <td>${_esc(r.description || '')}</td>
      <td><span class="cf-decision cf-decision-${decision.toLowerCase()}">${_esc(decision)}</span></td>
      <td>${tiers.length ? tiers.map(t => `<span class="cf-tier cf-tier-${t}">T${t}</span>`).join(' ') : '\u2014'}</td>
    `;

    // Click row to expand rule JSON
    tr.addEventListener('click', () => {
      const existing = tr.nextElementSibling;
      if (existing && existing.classList.contains('cf-rule-expand')) {
        existing.remove();
        return;
      }
      const expandRow = document.createElement('tr');
      expandRow.className = 'cf-rule-expand';
      expandRow.innerHTML = `<td colspan="5"><pre class="cf-rule-json">${_esc(JSON.stringify(r, null, 2))}</pre></td>`;
      tr.after(expandRow);
    });

    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  tableSection.appendChild(table);
  content.appendChild(tableSection);

  // Default decision note
  const defaultNote = document.createElement('div');
  defaultNote.className = 'cf-gc-section';
  const defaultDecision = state.config?.policy_rules?.default_decision || 'DENY';
  defaultNote.innerHTML = `<p class="cf-gc-note">Default decision (when no rule matches): <strong class="cf-decision cf-decision-${defaultDecision.toLowerCase()}">${_esc(defaultDecision)}</strong></p>`;
  content.appendChild(defaultNote);

  modalManager.open({ title: 'Policy Rules', trigger: state.el, content });
}

function _exportPolicyRules(policyRules) {
  const json = JSON.stringify(policyRules, null, 2);
  const blob = new Blob([json], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `atested-policy-rules-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
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

  modalManager.open({ title: 'Base Directories', trigger: state.el, content });
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
      <p class="cf-gc-explain">When Atested encounters a tool it hasn\u2019t seen before, it automatically classifies it to the nearest governance category. This ensures new tools are governed immediately without requiring manual configuration.</p>
      <p class="cf-gc-explain">The classification is based on the tool\u2019s name and behavior patterns. If an auto-classification is wrong, you can override it in edit mode.</p>
    </div>
  `;

  if (!entries.length) {
    const empty = document.createElement('div');
    empty.className = 'cf-gc-section';
    empty.innerHTML = '<p class="cf-gc-note">No tools have been auto-classified yet. Tools will appear here as Atested encounters them during operation.</p>';
    content.appendChild(empty);
  } else {
    const tableSection = document.createElement('div');
    tableSection.className = 'cf-gc-section';

    const table = document.createElement('table');
    table.className = 'cf-tools-table';
    table.innerHTML = `<thead><tr>
      <th>Tool</th>
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

  modalManager.open({ title: 'Discovered Tools', trigger: state.el, content });
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

  modalManager.open({ title: 'Signing', trigger: state.el, content });
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
      <p class="cf-gc-explain">The Atested proxy sits between your AI application and the model provider. It intercepts tool-use responses from the model, classifies each operation, evaluates it against your policy rules, and records the decision in the governance chain. Allowed operations pass through unchanged. Denied operations are replaced with a denial message that the model sees and can respond to.</p>
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

  modalManager.open({ title: 'Proxy', trigger: state.el, content });
}

// ---------- Utility ----------

function _openAsChild(title, trigger, content) {
  if (modalManager.depth > 0) return modalManager.replaceChild({ title, trigger, content });
  return modalManager.open({ title, trigger, content });
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
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
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
  .cf-val-green { color: #22c55e; }
  .cf-val-amber { color: #f59e42; }

  /* ---- Pane ---- */
  .cf-pane {
    background: #22262e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 16px;
  }
  .cf-pane-clickable {
    cursor: pointer;
    transition: border-color 0.12s, box-shadow 0.12s;
  }
  .cf-pane-clickable:hover {
    border-color: rgba(91,138,245,0.3);
    box-shadow: 0 0 0 1px rgba(91,138,245,0.15);
  }
  .cf-pane-accent { height: 6px; }
  .cf-accent-green { background: #22c55e; }
  .cf-accent-amber { background: #f59e42; }
  .cf-pane-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5b8af5;
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
    border-radius: 6px;
    color: #e4e6eb;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    padding: 7px 12px;
    box-sizing: border-box;
  }
  .cf-input:focus { outline: 2px solid #5b8af5; outline-offset: 1px; }
  .cf-result-success { color: #22c55e; font-size: 0.82rem; margin-top: 8px; }
  .cf-result-error { color: #f59e42; font-size: 0.82rem; margin-top: 8px; }

  /* ---- Buttons ---- */
  .cf-btn {
    border: none;
    border-radius: 6px;
    font-family: "Inter", system-ui, sans-serif;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 7px 18px;
    cursor: pointer;
    transition: background 0.1s;
    white-space: nowrap;
  }
  .cf-btn-primary { background: #5b8af5; color: #fff; }
  .cf-btn-primary:hover { background: #4a7ae5; }
  .cf-btn-export {
    background: rgba(245,158,66,0.12);
    color: #f59e42;
    border: 1px solid rgba(245,158,66,0.3);
    margin-bottom: 10px;
  }
  .cf-btn-export:hover { background: rgba(245,158,66,0.20); }

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
  .cf-rules-full tbody tr:hover { background: rgba(91,138,245,0.06); }
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
    border-radius: 999px;
  }
  .cf-decision-allow { background: rgba(34,197,94,0.12); color: #22c55e; }
  .cf-decision-deny { background: rgba(239,68,68,0.12); color: #ef4444; }

  /* Tier badges */
  .cf-tier {
    display: inline-block;
    font-size: 0.62rem;
    font-weight: 700;
    font-family: "JetBrains Mono", monospace;
    padding: 1px 6px;
    border-radius: 4px;
    margin-right: 2px;
  }
  .cf-tier-1 { background: rgba(34,197,94,0.12); color: #22c55e; }
  .cf-tier-2 { background: rgba(91,138,245,0.12); color: #5b8af5; }
  .cf-tier-3 { background: rgba(245,158,66,0.12); color: #f59e42; }
  .cf-tier-4 { background: rgba(239,68,68,0.12); color: #ef4444; }

  .cf-preview-note {
    font-size: 0.75rem;
    color: #6b7280;
    padding: 8px 0 0;
    font-style: italic;
  }

  /* ---- Rule JSON expand ---- */
  .cf-rule-expand td { padding: 0 8px 8px; }
  .cf-rule-json {
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
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
    border-radius: 6px;
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
    border-radius: 6px;
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
    color: #5b8af5;
    background: rgba(91,138,245,0.10);
    padding: 2px 8px;
    border-radius: 999px;
  }

  /* ---- Discovered tools ---- */
  .cf-mappings-list { display: flex; flex-direction: column; gap: 4px; }
  .cf-mapping-row {
    display: flex;
    align-items: center;
    gap: 10px;
    background: #1a1d23;
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 6px;
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
    color: #5b8af5;
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
  .cf-kv-copyable:hover { color: #5b8af5; }

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
    color: #5b8af5;
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
    border-radius: 4px 4px 0 0;
  }
  .cf-gc-header {
    font-size: 0.72rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #5b8af5;
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
    border-radius: 3px;
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
    border-radius: 6px;
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
    color: #f59e42;
    background: rgba(245,158,66,0.10);
    padding: 12px 16px;
    border-radius: 8px;
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
