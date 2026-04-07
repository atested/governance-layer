# Git Hooks

This repo ships pre-commit hooks under `scripts/hooks/`. Because `.git/hooks/`
is not version-controlled, hooks must be installed once per clone.

## Install

From the repo root:

```bash
ln -sf ../../scripts/hooks/pre-commit .git/hooks/pre-commit
chmod +x scripts/hooks/pre-commit
```

The symlink ensures the hook tracks the version-controlled file.

## Hooks

### pre-commit

- **`scripts/hooks/pre-commit`** — runs `node --input-type=module --check`
  on every staged file matching `dashboard/ui/*.js` and refuses the commit
  on JS syntax error. Rationale: D-2026-0407-003 — a stray `}` in `app.js`
  broke the dashboard silently for ~3 days. This hook prevents recurrence.

  Requires `node` on PATH. If `node` is not installed, the hook fails the
  commit rather than silently passing — install node or remove the JS file
  from the commit.

## Verifying installation

```bash
git config --get core.hooksPath || echo ".git/hooks"
ls -l .git/hooks/pre-commit
```
