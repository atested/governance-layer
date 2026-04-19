#!/usr/bin/env bash
# copy-demo-sim.sh — Copy dashboard rendering files to atested.com demo simulation.
# Usage: ./scripts/copy-demo-sim.sh <governance-layer-root> <atested-root>
#
# One-directional: governance-layer → atested.com.
# Idempotent: safe to run repeatedly.
# Security: rendering code only — no server code, no auth, no chain code.

set -euo pipefail

GOV="${1:?Usage: $0 <governance-layer-root> <atested-root>}"
ATD="${2:?Usage: $0 <governance-layer-root> <atested-root>}"

SRC="$GOV/dashboard/ui-next"
DST="$ATD/demo/sim"

# ---------- Verify source exists ----------

if [ ! -f "$SRC/main-page.js" ]; then
  echo "ERROR: Cannot find $SRC/main-page.js" >&2
  exit 1
fi

# ---------- Create target directories ----------

mkdir -p "$DST/windows" "$DST/components"

# ---------- Verbatim copies (no modifications) ----------

VERBATIM=(
  "modal-manager.js"
  "tokens.js"
  "tier-definitions.js"
  "questionnaire-engine.js"
  "question-catalog.js"
  "components/base.js"
  "components/window-frame.js"
  "components/window-backdrop.js"
  "components/status-card.js"
  "components/status-grid.js"
  "components/decision-tag.js"
  "components/tier-badge.js"
  "components/pill.js"
  "components/data-table.js"
  "components/pagination.js"
  "components/kv-list.js"
  "components/code-block.js"
  "components/loading-indicator.js"
  "components/confirmation-dialog.js"
)

for f in "${VERBATIM[@]}"; do
  cp "$SRC/$f" "$DST/$f"
  echo "  copied $f"
done

# ---------- Copy licensing-api.js from pricing sim ----------

if [ -f "$ATD/pricing/sim/licensing-api.js" ]; then
  cp "$ATD/pricing/sim/licensing-api.js" "$DST/licensing-api.js"
  echo "  copied licensing-api.js (from pricing sim)"
else
  echo "  WARN: pricing/sim/licensing-api.js not found, skipping"
fi

# ---------- Patched copy: chrome.js ----------
# No patches needed — identity zone stays blank naturally

cp "$SRC/chrome.js" "$DST/chrome.js"
echo "  copied chrome.js (verbatim)"

# ---------- Patched copy: main-page.js ----------
# Patch: licensing launcher navigates to /pricing instead of opening window

sed "s|import { openLicensingWindow } from './windows/licensing.js';|// Licensing opens /pricing in demo\nconst openLicensingWindow = () => { window.location.href = '/pricing'; };|" \
  "$SRC/main-page.js" \
  > "$DST/main-page.js"

echo "  copied main-page.js (patched licensing launcher → /pricing)"

# ---------- Patched copy: windows/licensing.js ----------
# Replace _refreshLicenseState body (dynamic import of app.js) with async no-op

sed 's/async function _refreshLicenseState() {/async function _refreshLicenseState() { return; \/\/ sim no-op/' \
  "$SRC/windows/licensing.js" | \
  sed '/const { refreshLicenseState } = await import/d' | \
  sed '/^  refreshLicenseState();$/d' \
  > "$DST/windows/licensing.js"

echo "  copied windows/licensing.js (patched _refreshLicenseState)"

# ---------- Verbatim window copies ----------
# These windows either have no POST actions or their POSTs are
# handled gracefully by the fixture api.js returning success.

WINDOWS=(
  "activity.js"
  "approvals.js"
  "audit.js"
  "alerts.js"
  "health.js"
  "reports.js"
  "configuration.js"
  "communications.js"
  "notifications.js"
  "feedback.js"
  "identity-setup.js"
  "identity-session.js"
  "record-detail.js"
)

for f in "${WINDOWS[@]}"; do
  cp "$SRC/windows/$f" "$DST/windows/$f"
  echo "  copied windows/$f"
done

# ---------- Manifest ----------

echo ""
echo "Demo simulation files copied to $DST"
echo "Hand-authored files (api.js, demo-app.js, sim-bridge.css, fixtures/) are NOT touched."
echo ""
echo "Manifest:"
find "$DST" -type f -name '*.js' -o -name '*.css' | sort | while read f; do
  echo "  ${f#$DST/}"
done
