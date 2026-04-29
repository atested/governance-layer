const EXCEL_HEADER = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">`;

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
