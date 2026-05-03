# Testing

## Canonical Test Commands

### Full suite (Python + shell)

```bash
python3 -m pytest tests/ -v
```

This runs all Python unit/integration tests and all shell contract tests
discovered in `tests/` and `system/tests/`. Shell tests are parameterized
via `tests/test_shell_contracts.py` and marked with `@pytest.mark.shell`.

### Python tests only (fastest)

```bash
python3 -m pytest tests/ -v -m "not shell"
```

### Shell contract tests only

```bash
python3 -m pytest tests/ -v -m shell
```

### Interpreter notes

MCP-dependent tests have been archived to `tests/_archived_mcp/` and
`system/tests/_archived_mcp/` (excluded from collection via `norecursedirs`
in pytest.ini). The remaining test suite runs cleanly on Python 3.9+.

For a clean collection with zero errors, use the project venv:

```bash
./venv/bin/python -m pytest tests/ -v
```

### Markers

| Marker | Description |
|--------|-------------|
| `shell` | Shell-based contract tests (subprocess execution) |
| `system` | System-level integration tests |
| `slow` | Tests taking more than 10 seconds |

### Current baseline

Reported in `STATE_CURRENT.md` under "Test Baseline". Run the canonical
command and compare against the recorded baseline to detect regressions.
