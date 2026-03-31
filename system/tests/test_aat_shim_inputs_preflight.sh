#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS_AAT_DIR="$ROOT/system/tests/fixtures/proof_bundle_with_aat_inputs/pass_aat_preferred/aat"

parse_kv() {
  local line="$1"
  local key="$2"
  printf '%s\n' "$line" | tr ' ' '\n' | rg "^${key}=" | head -n1 | cut -d= -f2-
}

run_preflight() {
  local bundle="$1"
  local out rc count line
  set +e
  out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$bundle" --preflight-inputs 2>&1)"
  rc=$?
  set -e

  count="$(printf '%s\n' "$out" | rg -c '^AAT_SHIM_INPUTS_PREFLIGHT ')"
  [[ "$count" -eq 1 ]] || {
    echo "FAIL: expected one preflight line, got $count"
    return 1
  }
  line="$(printf '%s\n' "$out" | rg '^AAT_SHIM_INPUTS_PREFLIGHT ' | head -n1)"
  printf '%s\n' "$line"
  return "$rc"
}

run_once() {
  local tmp ok_bundle bad_bundle out_ok out_bad rc_ok rc_bad
  tmp="$(mktemp -d "$ROOT/out/aat-shim-preflight.XXXXXX")"

  [[ -d "$PASS_AAT_DIR" ]] || { echo "FAIL: missing fixture dir"; return 1; }

  ok_bundle="$tmp/bundle_ok"
  bad_bundle="$tmp/bundle_bad"
  mkdir -p "$ok_bundle/aat" "$bad_bundle/aat"
  cp "$PASS_AAT_DIR"/*.json "$ok_bundle/aat/"

  # Controlled negative: only one required token present.
  cp "$PASS_AAT_DIR/action_record.json" "$bad_bundle/aat/"

  set +e
  out_ok="$(run_preflight "$ok_bundle")"
  rc_ok=$?
  out_bad="$(run_preflight "$bad_bundle")"
  rc_bad=$?
  set -e

  [[ "$rc_ok" -eq 0 ]] || { echo "FAIL: expected ok rc=0 got $rc_ok"; return 1; }
  [[ "$(parse_kv "$out_ok" "ok")" == "yes" ]] || { echo "FAIL: ok bundle should return ok=yes"; return 1; }
  [[ "$(parse_kv "$out_ok" "layout")" == "aat" ]] || { echo "FAIL: ok bundle should return layout=aat"; return 1; }
  [[ "$(parse_kv "$out_ok" "missing")" == "NONE" ]] || { echo "FAIL: ok bundle should return missing=NONE"; return 1; }

  [[ "$rc_bad" -eq 1 ]] || { echo "FAIL: expected bad rc=1 got $rc_bad"; return 1; }
  [[ "$(parse_kv "$out_bad" "ok")" == "no" ]] || { echo "FAIL: bad bundle should return ok=no"; return 1; }
  [[ "$(parse_kv "$out_bad" "layout")" == "aat" ]] || { echo "FAIL: bad bundle should return layout=aat"; return 1; }
  bad_missing="$(parse_kv "$out_bad" "missing")"
  [[ "$bad_missing" != "NONE" ]] || { echo "FAIL: bad bundle missing should not be NONE"; return 1; }
  printf '%s\n' "$bad_missing" | tr ',' '\n' | rg -n '^assumptions_unknowns_register\.json$' >/dev/null

  printf '%s\n' "$out_ok"
  printf '%s\n' "$out_bad"
  echo "CASE=AAT_SHIM_INPUTS_PREFLIGHT PASS"
  rm -rf "$tmp"
}

main() {
  local r1 r2 h1 h2
  r1="$(mktemp)"
  r2="$(mktemp)"

  run_once >"$r1"
  run_once >"$r2"

  h1="$(shasum -a 256 "$r1" | awk '{print $1}')"
  h2="$(shasum -a 256 "$r2" | awk '{print $1}')"

  cat "$r1"
  echo "RUN1_SHA256=$h1"
  echo "RUN2_SHA256=$h2"
  if [[ "$h1" != "$h2" ]]; then
    echo "DETERMINISTIC=NO"
    diff -u "$r1" "$r2" | sed -n '1,80p' || true
    rm -f "$r1" "$r2"
    exit 1
  fi
  echo "DETERMINISTIC=YES"
  rm -f "$r1" "$r2"
}

main "$@"
