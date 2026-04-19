#!/usr/bin/env bash
# copy-pricing-sim.sh — Copy dashboard licensing files to atested.com pricing simulation.
# Usage: ./scripts/copy-pricing-sim.sh <governance-layer-root> <atested-root>
#
# One-directional: governance-layer → atested.com.
# Idempotent: safe to run repeatedly.

set -euo pipefail

GOV="${1:?Usage: $0 <governance-layer-root> <atested-root>}"
ATD="${2:?Usage: $0 <governance-layer-root> <atested-root>}"

SRC="$GOV/dashboard/ui-next"
DST="$ATD/pricing/sim"

# ---------- Verify source exists ----------

if [ ! -f "$SRC/windows/licensing.js" ]; then
  echo "ERROR: Cannot find $SRC/windows/licensing.js" >&2
  exit 1
fi

# ---------- Create target directories ----------

mkdir -p "$DST/windows" "$DST/components"

# ---------- Verbatim copies (no modifications) ----------

VERBATIM=(
  "tier-definitions.js"
  "questionnaire-engine.js"
  "question-catalog.js"
  "tokens.js"
  "modal-manager.js"
  "components/base.js"
  "components/window-frame.js"
  "components/window-backdrop.js"
  "components/loading-indicator.js"
)

for f in "${VERBATIM[@]}"; do
  cp "$SRC/$f" "$DST/$f"
  echo "  copied $f"
done

# ---------- Patched copy: windows/licensing.js ----------
# Replace _refreshLicenseState body (dynamic import of app.js) with async no-op

sed 's/async function _refreshLicenseState() {/async function _refreshLicenseState() { return; \/\/ sim no-op/' \
  "$SRC/windows/licensing.js" | \
  sed '/const { refreshLicenseState } = await import/d' | \
  sed '/^  refreshLicenseState();$/d' \
  > "$DST/windows/licensing.js"

echo "  copied windows/licensing.js (patched _refreshLicenseState)"

# ---------- Done ----------

echo ""
echo "Pricing simulation files copied to $DST"
echo "Hand-authored files (api.js, licensing-api.js, sim-entry.js, sim-bridge.css) are NOT touched."
