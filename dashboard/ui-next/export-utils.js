import * as api from './api.js';

const EXCEL_HEADER = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">`;

export async function authorizeExport(metadata = {}) {
  const licenseKey = await _showExportAuthDialog(metadata);
  if (licenseKey == null) return { ok: false, cancelled: true };
  const res = await api.postExportAuthorize({ license_key: licenseKey, metadata });
  if (!res.ok) {
    _showExportAuthError(res.error || 'Export authorization failed.');
    return res;
  }
  return {
    ok: true,
    data: res.data,
    token: res.data?.export_token || '',
  };
}

export function downloadExport(format, filenameBase, columns, rows, opts = {}) {
  const safeBase = filenameBase || 'atested-export';
  if (format === 'excel') {
    downloadExcel(`${safeBase}.xls`, opts.sheetName || 'Export', columns, rows, opts.note || '');
    return;
  }
  if (format === 'csv') {
    downloadCSV(`${safeBase}.csv`, columns, rows, opts.note || '');
    return;
  }
  const payload = typeof opts.jsonData === 'function'
    ? opts.jsonData()
    : (opts.jsonData || { columns, rows });
  downloadJSON(`${safeBase}.json`, payload);
}

export function downloadJSON(filename, data) {
  _downloadBlob(filename, 'application/json', JSON.stringify(data, null, 2));
}

export function downloadCSV(filename, columns, rows, note = '') {
  const header = columns.map(col => _csvEscape(col.label || col.key || '')).join(',');
  const body = rows.map(row => columns.map(col => _csvEscape(_cell(row[col.key]))).join(',')).join('\n');
  let csv = `${header}\n${body}`;
  if (note) csv += `\n# ${note}`;
  _downloadBlob(filename, 'text/csv;charset=utf-8', csv);
}

export function downloadExcel(filename, sheetName, columns, rows, note = '') {
  const tableRows = [];
  tableRows.push(`<Row>${columns.map(col => _excelCell(col.label || col.key || '', true)).join('')}</Row>`);
  for (const row of rows) {
    tableRows.push(`<Row>${columns.map(col => _excelCell(_cell(row[col.key]))).join('')}</Row>`);
  }
  if (note) tableRows.push(`<Row>${_excelCell(note)}</Row>`);
  const xml = `${EXCEL_HEADER}<Worksheet ss:Name="${_xmlEscape(sheetName)}"><Table>${tableRows.join('')}</Table></Worksheet></Workbook>`;
  _downloadBlob(filename, 'application/vnd.ms-excel', xml);
}

function _downloadBlob(filename, mime, content) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function _csvEscape(value) {
  const str = _cell(value);
  if (/[",\n]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

function _excelCell(value, bold = false) {
  return `<Cell${bold ? ' ss:StyleID="header"' : ''}><Data ss:Type="String">${_xmlEscape(_cell(value))}</Data></Cell>`;
}

function _xmlEscape(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}

function _cell(value) {
  if (value == null) return '';
  if (Array.isArray(value)) return value.join(', ');
  return String(value);
}

function _isDemoSimulation() {
  return window.location.pathname.includes('/demo/');
}

function _showExportAuthDialog(metadata = {}) {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'atd-export-auth-overlay';
    const surface = _label(metadata.surface || 'export');
    overlay.innerHTML = `
      <div class="atd-export-auth-dialog" role="dialog" aria-modal="true" aria-label="Authorize export">
        <div class="atd-export-auth-title">Authorize Export</div>
        <div class="atd-export-auth-copy">
          Exporting ${_esc(surface)} data requires operator authentication. Atested records this export in the live chain.
        </div>
        <label class="atd-export-auth-label">
          License key
          <input class="atd-export-auth-input" type="password" autocomplete="off" placeholder="${_isDemoSimulation() ? 'Demo accepts any key' : 'atested-xxxx-xxxx-xxxx'}">
        </label>
        <div class="atd-export-auth-actions">
          <button class="atd-export-auth-cancel" type="button">Cancel</button>
          <button class="atd-export-auth-submit" type="button">Authorize</button>
        </div>
      </div>
    `;
    _ensureExportAuthStyles();
    document.body.appendChild(overlay);
    const input = overlay.querySelector('.atd-export-auth-input');
    const cleanup = value => {
      overlay.remove();
      resolve(value);
    };
    overlay.querySelector('.atd-export-auth-cancel').addEventListener('click', () => cleanup(null));
    overlay.addEventListener('click', e => {
      if (e.target === overlay) cleanup(null);
    });
    overlay.querySelector('.atd-export-auth-submit').addEventListener('click', () => {
      const value = input.value.trim();
      if (!value && !_isDemoSimulation()) {
        input.classList.add('atd-export-auth-input-error');
        input.focus();
        return;
      }
      cleanup(value || 'demo-export-key');
    });
    input.addEventListener('keydown', e => {
      if (e.key === 'Enter') overlay.querySelector('.atd-export-auth-submit').click();
      if (e.key === 'Escape') cleanup(null);
    });
    setTimeout(() => input.focus(), 0);
  });
}

function _showExportAuthError(message) {
  const box = document.createElement('div');
  box.className = 'atd-export-auth-toast';
  box.textContent = message;
  _ensureExportAuthStyles();
  document.body.appendChild(box);
  setTimeout(() => box.remove(), 4200);
}

function _ensureExportAuthStyles() {
  if (document.getElementById('atd-export-auth-styles')) return;
  const style = document.createElement('style');
  style.id = 'atd-export-auth-styles';
  style.textContent = `
    .atd-export-auth-overlay {
      align-items: center;
      background: rgba(5, 8, 12, 0.72);
      display: flex;
      inset: 0;
      justify-content: center;
      position: fixed;
      z-index: 2147483000;
    }
    .atd-export-auth-dialog {
      background: #161b22;
      border: 1px dashed #30363d;
      color: #e4e6eb;
      font-family: "Inter", system-ui, sans-serif;
      max-width: 420px;
      padding: 18px;
      width: min(420px, calc(100vw - 32px));
    }
    .atd-export-auth-title {
      color: #d2a8ff;
      font-size: 0.8rem;
      font-weight: 800;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
      text-transform: uppercase;
    }
    .atd-export-auth-copy {
      color: #b8bec8;
      font-size: 0.82rem;
      line-height: 1.5;
      margin-bottom: 14px;
    }
    .atd-export-auth-label {
      color: #8b919a;
      display: grid;
      font-size: 0.72rem;
      font-weight: 700;
      gap: 6px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }
    .atd-export-auth-input {
      background: #0d1117;
      border: 1px solid #30363d;
      color: #e4e6eb;
      font-family: "JetBrains Mono", monospace;
      font-size: 0.82rem;
      padding: 9px 10px;
    }
    .atd-export-auth-input-error { border-color: #f85149; }
    .atd-export-auth-actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 16px;
    }
    .atd-export-auth-actions button {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.14);
      color: #e4e6eb;
      cursor: pointer;
      font-family: "JetBrains Mono", monospace;
      font-size: 0.72rem;
      padding: 7px 11px;
      text-transform: uppercase;
    }
    .atd-export-auth-submit {
      background: rgba(210,168,255,0.14) !important;
      border-color: rgba(210,168,255,0.36) !important;
      color: #d2a8ff !important;
    }
    .atd-export-auth-toast {
      background: #161b22;
      border: 1px dashed #f85149;
      color: #ffb4ae;
      font-family: "JetBrains Mono", monospace;
      font-size: 0.78rem;
      max-width: 420px;
      padding: 10px 12px;
      position: fixed;
      right: 18px;
      top: 18px;
      z-index: 2147483001;
    }
  `;
  document.head.appendChild(style);
}

export function showPackagePasswordDialog() {
  return new Promise(resolve => {
    const overlay = document.createElement('div');
    overlay.className = 'atd-export-auth-overlay';
    const MIN_LEN = 12;
    overlay.innerHTML = `
      <div class="atd-export-auth-dialog" role="dialog" aria-modal="true" aria-label="Encrypt evidence package">
        <div class="atd-export-auth-title">Encrypt Evidence Package</div>
        <div class="atd-export-auth-copy">
          Set a password to encrypt this evidence package. The recipient will need this password to decrypt and view the evidence. Atested does not store or log the password.
        </div>
        <label class="atd-export-auth-label">
          Password (minimum ${MIN_LEN} characters)
          <input class="atd-export-auth-input atd-pkg-pw" type="password" autocomplete="off" placeholder="Enter a strong passphrase">
        </label>
        <label class="atd-export-auth-label" style="margin-top:10px">
          Confirm password
          <input class="atd-export-auth-input atd-pkg-pw-confirm" type="password" autocomplete="off" placeholder="Re-enter the passphrase">
        </label>
        <label class="atd-export-auth-label" style="margin-top:10px">
          Intended recipient (optional)
          <input class="atd-export-auth-input atd-pkg-recipient" type="text" autocomplete="off" placeholder="e.g. auditor@example.com">
        </label>
        <div class="atd-pkg-pw-hint" style="color:#8b919a;font-size:0.72rem;margin-top:8px;line-height:1.4">
          Use a long passphrase you can share securely with the recipient. No complexity rules — length is what matters.
        </div>
        <div class="atd-pkg-pw-error" style="color:#f85149;font-size:0.72rem;margin-top:6px;display:none"></div>
        <div class="atd-export-auth-actions">
          <button class="atd-export-auth-cancel" type="button">Cancel</button>
          <button class="atd-export-auth-submit" type="button">Create Package</button>
        </div>
      </div>
    `;
    _ensureExportAuthStyles();
    document.body.appendChild(overlay);
    const pwInput = overlay.querySelector('.atd-pkg-pw');
    const confirmInput = overlay.querySelector('.atd-pkg-pw-confirm');
    const recipientInput = overlay.querySelector('.atd-pkg-recipient');
    const errorEl = overlay.querySelector('.atd-pkg-pw-error');
    const cleanup = value => { overlay.remove(); resolve(value); };

    overlay.querySelector('.atd-export-auth-cancel').addEventListener('click', () => cleanup(null));
    overlay.addEventListener('click', e => { if (e.target === overlay) cleanup(null); });

    const submit = () => {
      const pw = pwInput.value;
      const confirm = confirmInput.value;
      errorEl.style.display = 'none';
      if (pw.length < MIN_LEN) {
        errorEl.textContent = `Password must be at least ${MIN_LEN} characters.`;
        errorEl.style.display = 'block';
        pwInput.focus();
        return;
      }
      if (pw !== confirm) {
        errorEl.textContent = 'Passwords do not match.';
        errorEl.style.display = 'block';
        confirmInput.focus();
        return;
      }
      cleanup({ password: pw, intended_recipient: recipientInput.value.trim() });
    };

    overlay.querySelector('.atd-export-auth-submit').addEventListener('click', submit);
    confirmInput.addEventListener('keydown', e => {
      if (e.key === 'Enter') submit();
      if (e.key === 'Escape') cleanup(null);
    });
    pwInput.addEventListener('keydown', e => { if (e.key === 'Escape') cleanup(null); });
    setTimeout(() => pwInput.focus(), 0);
  });
}

function _label(value) {
  return String(value || '').replace(/[_-]/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function _esc(value) {
  return String(value || '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[ch]));
}
