# Design UI v1 — Local Launch

DESIGN-UI-010.

The `scripts/run-design-ui.sh` script starts Design UI v1 on this
machine. It is callable from any directory by its absolute path; it
resolves the repository root from its own location, so no `cd` is
needed first.

## Usage

```sh
# From the repo root
./scripts/run-design-ui.sh

# From anywhere, by absolute path
/Volumes/SSD/archive/gov/governance-layer/scripts/run-design-ui.sh
```

The script will:

1. Resolve the repository root from its own location.
2. Refuse to run, with an actionable message, if `design-ui/` is
   missing or if Node/npm are not on `PATH`.
3. Run `npm install` once, the first time it sees no
   `design-ui/node_modules` directory. Subsequent runs skip this.
4. Print the URLs the operator will open in the browser.
5. Hand off to `npm run dev`, which starts the Vite web server and
   the API server together (via `design-ui/scripts/dev.mjs`).

Stop the app with `Ctrl-C`. The dev launcher cleans up both child
processes on `SIGINT` / `SIGTERM`.

## Default URLs

| Surface | URL                                |
| ------- | ---------------------------------- |
| Design  | <http://127.0.0.1:5173/design>     |
| Map     | <http://127.0.0.1:5173/map>        |
| Spec    | <http://127.0.0.1:5173/spec>       |
| API     | <http://127.0.0.1:4174/api>        |

The web (Vite) port is fixed at 5173 in
`design-ui/vite.config.ts`. The API port defaults to 4174 and can
be overridden via `DESIGN_UI_API_PORT` before invoking the script.

## Failure modes

| Exit code | Cause                              |
| --------- | ---------------------------------- |
| 2         | `design-ui/package.json` missing   |
| 3         | `node` or `npm` not on `PATH`      |
| other     | Whatever `npm run dev` exits with  |

## What the script does NOT do

- Install Node, npm, or any global package. If Node is missing the
  operator installs it; the script tells them so and exits.
- Modify any file outside `design-ui/node_modules` (which is
  gitignored).
- Touch any governance-layer subsystem.
