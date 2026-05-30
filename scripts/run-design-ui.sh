#!/usr/bin/env bash
# run-design-ui.sh — start Design UI v1 locally.
#
# DESIGN-UI-010.
#
# Callable from any directory via absolute path. The script resolves its
# own location to find the repository root, so the operator does not need
# to cd anywhere first.
#
# What it does:
#   1. Resolve repo root from the script's own location.
#   2. Refuse to run if design-ui/package.json is missing.
#   3. Refuse to run if Node or npm are not on PATH.
#   4. Run `npm install` once if design-ui/node_modules does not exist.
#   5. Print the URLs the operator will open in a browser.
#   6. Exec the existing `npm run dev` package script (which spawns both
#      the Vite web server and the API server via design-ui/scripts/dev.mjs).
#
# What it does NOT do:
#   - Install Node or npm. If either is missing, the operator must install
#     them themselves; the script prints an actionable message and exits.
#   - Install global npm packages. Everything stays local to design-ui/.
#   - Touch any other part of the repository.
#
# Environment variables honoured:
#   DESIGN_UI_API_PORT   API port (default 4174, set by design-ui/server/index.ts).
#                        Web/Vite port is fixed at 5173 in vite.config.ts.

set -euo pipefail

# ----------------------------------------------------------------------------
# 1. Resolve script directory deterministically.
# ----------------------------------------------------------------------------
# `${BASH_SOURCE[0]}` is the path used to invoke the script. We follow any
# symlink so a `~/bin/run-design-ui.sh -> /Volumes/.../scripts/run-design-ui.sh`
# still resolves to the real repo. `cd -P` collapses any remaining symlinks
# in parent directories.
SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    # Resolve relative symlink targets against the link's own directory.
    case "$SOURCE" in
        /*) ;;
        *) SOURCE="$DIR/$SOURCE" ;;
    esac
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# ----------------------------------------------------------------------------
# 2. Repo root is the parent of scripts/.
# ----------------------------------------------------------------------------
REPO_ROOT="$(cd -P "$SCRIPT_DIR/.." && pwd)"
DESIGN_UI_DIR="$REPO_ROOT/design-ui"

# ----------------------------------------------------------------------------
# 3. Fail clearly if design-ui/ is missing.
# ----------------------------------------------------------------------------
if [ ! -f "$DESIGN_UI_DIR/package.json" ]; then
    cat >&2 <<EOF
run-design-ui.sh: design-ui/ not found.

Expected: $DESIGN_UI_DIR/package.json

This script must live in scripts/ of the governance-layer repo and the
design-ui/ application directory must be a sibling of scripts/. If you
moved the script, copy it back or invoke it via its original path.
EOF
    exit 2
fi

# ----------------------------------------------------------------------------
# 4. Fail clearly if Node or npm are unavailable.
# ----------------------------------------------------------------------------
if ! command -v node >/dev/null 2>&1; then
    echo "run-design-ui.sh: 'node' not found on PATH." >&2
    echo "Install Node (https://nodejs.org/) and try again." >&2
    exit 3
fi
if ! command -v npm >/dev/null 2>&1; then
    echo "run-design-ui.sh: 'npm' not found on PATH." >&2
    echo "npm ships with Node; reinstall Node if your install does not include it." >&2
    exit 3
fi

# ----------------------------------------------------------------------------
# 5. Install dependencies the first time (or after node_modules is cleared).
# ----------------------------------------------------------------------------
cd "$DESIGN_UI_DIR"

if [ ! -d node_modules ]; then
    echo "run-design-ui.sh: installing Design UI dependencies (first run)…"
    npm install
fi

# ----------------------------------------------------------------------------
# 6. Print access URLs before handing off to npm.
# ----------------------------------------------------------------------------
WEB_PORT=5173                                  # Vite host:port, fixed in vite.config.ts
API_PORT="${DESIGN_UI_API_PORT:-4174}"         # API host:port, env-overridable

cat <<EOF

Starting Design UI v1
  Web:  http://127.0.0.1:${WEB_PORT}/
        /design  -> http://127.0.0.1:${WEB_PORT}/design
        /map     -> http://127.0.0.1:${WEB_PORT}/map
        /spec    -> http://127.0.0.1:${WEB_PORT}/spec
  API:  http://127.0.0.1:${API_PORT}/api

Stop with Ctrl-C.

EOF

# ----------------------------------------------------------------------------
# 7. Hand off to the existing dev launcher.
# ----------------------------------------------------------------------------
# `exec` replaces this shell so Ctrl-C reaches npm directly; npm's dev script
# (design-ui/scripts/dev.mjs) already cleans up both child processes on
# SIGINT/SIGTERM.
exec npm run dev
