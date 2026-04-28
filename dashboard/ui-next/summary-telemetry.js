/**
 * Anonymous summary telemetry.
 *
 * This module never stores or transmits individual interaction events. UI code
 * only increments in-memory counters. Flushes send aggregate counters and then
 * clear local memory.
 */

import * as api from './api.js';

const _pending = {
  window_opens: {},
  report_runs: {},
  range_shortcuts: {},
  trouble_reports: {},
  ui_actions: {},
};

let _flushTimer = null;
let _flushing = false;

export function recordUiAggregate(bucket, key, amount = 1) {
  if (!_pending[bucket]) return;
  const cleanKey = String(key || 'unknown').slice(0, 80);
  _pending[bucket][cleanKey] = (_pending[bucket][cleanKey] || 0) + Math.max(1, Number(amount) || 1);
  _scheduleFlush();
}

export async function flushTelemetrySummary() {
  if (_flushing || !_hasPending()) return;
  _flushing = true;
  const increments = _drainPending();
  try {
    const res = await api.postTelemetrySummary({ increments });
    if (!res.ok) {
      _restorePending(increments);
      return;
    }
    if (res.data?.recorded === false) return;
  } catch {
    _restorePending(increments);
  } finally {
    _flushing = false;
  }
}

export function installSummaryTelemetry() {
  window.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      flushTelemetrySummary();
    }
  });
  window.addEventListener('beforeunload', () => {
    if (!_hasPending()) return;
    flushTelemetrySummary();
  });
}

function _scheduleFlush() {
  if (_flushTimer) return;
  _flushTimer = window.setTimeout(() => {
    _flushTimer = null;
    flushTelemetrySummary();
  }, 60000);
}

function _hasPending() {
  return Object.values(_pending).some(bucket => Object.keys(bucket).length > 0);
}

function _drainPending() {
  const copy = {};
  for (const [bucket, values] of Object.entries(_pending)) {
    copy[bucket] = { ...values };
    _pending[bucket] = {};
  }
  return copy;
}

function _restorePending(increments) {
  for (const [bucket, values] of Object.entries(increments || {})) {
    if (!_pending[bucket]) continue;
    for (const [key, value] of Object.entries(values || {})) {
      _pending[bucket][key] = (_pending[bucket][key] || 0) + value;
    }
  }
}
