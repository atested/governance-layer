#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PASS_AAT_DIR="$ROOT/system/tests/fixtures/proof_bundle_with_aat_inputs/pass_aat_preferred/aat"

parse_kv() {
  local line="$1"
  local key="$2"
  printf '%s\n' "$line" | tr ' ' '\n' | rg "^${key}=" | head -n1 | cut -d= -f2-
}

run_parity() {
  local bundle="$1"
  local out rc count line
  set +e
  out="$(bash "$ROOT/scripts/run_validate_proof_bundle_with_aat_shim.sh" --bundle-dir "$bundle" --preflight-inputs-parity 2>&1)"
  rc=$?
  set -e
  count="$(printf '%s\n' "$out" | rg -c '^AAT_SHIM_INPUTS_PARITY ')"
  [[ "$count" -eq 1 ]] || { echo "FAIL: expected one parity line"; return 1; }
  line="$(printf '%s\n' "$out" | rg '^AAT_SHIM_INPUTS_PARITY ' | head -n1)"
  printf '%s\n' "$line"
  return "$rc"
}

run_once() {
  local tmp pos_bundle inv_bundle amb_bundle out_pos out_inv out_amb rc_pos rc_inv rc_amb
  tmp="$(mktemp -d "$ROOT/out/aat-shim-parity.XXXXXX")"

  [[ -d "$PASS_AAT_DIR" ]] || { echo "FAIL: missing fixture dir"; return 1; }

  pos_bundle="$tmp/pos"
  inv_bundle="$tmp/inv"
  amb_bundle="$tmp/amb"
  mkdir -p "$pos_bundle/aat" "$inv_bundle/aat" "$amb_bundle/aat"
  cp "$PASS_AAT_DIR"/*.json "$pos_bundle/aat/"
  cp "$PASS_AAT_DIR"/*.json "$inv_bundle/aat/"
  cp "$PASS_AAT_DIR"/*.json "$amb_bundle/aat/"
  cp "$PASS_AAT_DIR"/*.json "$amb_bundle/"

  # Deterministic JSON corruption for INVALID case.
  printf '{\n' > "$inv_bundle/aat/action_record.json"

  set +e
  out_pos="$(run_parity "$pos_bundle")"; rc_pos=$?
  out_inv="$(run_parity "$inv_bundle")"; rc_inv=$?
  out_amb="$(run_parity "$amb_bundle")"; rc_amb=$?
  set -e

  [[ "$rc_pos" -eq 0 ]] || { echo "FAIL: positive rc expected 0"; return 1; }
  [[ "$(parse_kv "$out_pos" "ok")" == "yes" ]] || { echo "FAIL: positive ok"; return 1; }
  [[ "$(parse_kv "$out_pos" "reason")" == "OK" ]] || { echo "FAIL: positive reason"; return 1; }
  [[ "$(parse_kv "$out_pos" "detail")" == "NONE" ]] || { echo "FAIL: positive detail"; return 1; }

  [[ "$rc_inv" -eq 1 ]] || { echo "FAIL: invalid rc expected 1"; return 1; }
  [[ "$(parse_kv "$out_inv" "ok")" == "no" ]] || { echo "FAIL: invalid ok"; return 1; }
  [[ "$(parse_kv "$out_inv" "reason")" == "INVALID" ]] || { echo "FAIL: invalid reason"; return 1; }
  [[ "$(parse_kv "$out_inv" "detail")" == "action_record.json" ]] || { echo "FAIL: invalid detail"; return 1; }

  [[ "$rc_amb" -eq 2 ]] || { echo "FAIL: ambiguous rc expected 2"; return 1; }
  [[ "$(parse_kv "$out_amb" "ok")" == "no" ]] || { echo "FAIL: ambiguous ok"; return 1; }
  [[ "$(parse_kv "$out_amb" "reason")" == "AMBIGUOUS" ]] || { echo "FAIL: ambiguous reason"; return 1; }
  [[ "$(parse_kv "$out_amb" "detail")" == "LEGACY_AND_AAT_BOTH_PRESENT" ]] || { echo "FAIL: ambiguous detail"; return 1; }

  printf '%s\n' "$out_pos"
  printf '%s\n' "$out_inv"
  printf '%s\n' "$out_amb"
  echo "CASE=AAT_SHIM_INPUTS_PARITY_PREFLIGHT PASS"
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
