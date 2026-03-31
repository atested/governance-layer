# Operator UI Web Prototype

## Location

Prototype files live in:

- `docs/dev/operator-ui-prototype/`

Entry point:

- `docs/dev/operator-ui-prototype/index.html`

## How To View

Open `index.html` directly in a browser, or serve the repo root with a simple static server and visit:

- `http://localhost:8000/docs/dev/operator-ui-prototype/`

Example:

```bash
python3 -m http.server 8000
```

## Prototype Assumptions

- This is a static prototype only.
- All screens render from local fixture data in `fixtures.js`.
- Routing uses hash state so browser back/forward preserves prototype context without backend work.
- The prototype implements only the operator-facing screens from:
  - `docs/dev/OPERATOR_UI_IA__SPEC__v2.1.md`
  - `docs/dev/OPERATOR_UI_SCREEN_MAP__SPEC__v1.md`
- The audit surface remains a stub.
- No production backend, audit tooling, export flow, or speculative management features are included.
