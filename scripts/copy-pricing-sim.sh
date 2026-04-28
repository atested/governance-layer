#!/usr/bin/env bash
set -euo pipefail
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
  "tooltip-utils.js"
  "components/base.js"
  "components/window-frame.js"
  "components/window-backdrop.js"
  "components/loading-indicator.js"
)

for f in "${VERBATIM[@]}"; do
  cp "$SRC/$f" "$DST/$f"
  echo "  copied $f"
done

# ---------- windows/licensing.js is NOT copied ----------
# The pricing sim's licensing.js contains hand-authored functions
# (embedLicensingLauncher, refreshForPlanChange, _embeddedState) that
# do not exist in the dashboard source. Overwriting it breaks the
# pricing page. Style changes must be applied manually.
echo "  SKIPPED windows/licensing.js (hand-authored, not copied)"

# ---------- Done ----------

echo ""
echo "Pricing simulation files copied to $DST"
echo "Hand-authored files (api.js, licensing-api.js, sim-entry.js, sim-bridge.css, windows/licensing.js) are NOT touched."
