# TASK_SEEDS.md

Defines the canonical format for task seed files used by the deterministic task scaffolder.

---

## Purpose

Task seed files provide explicit, reviewed specifications for generating new task files.
The scaffolder (`scripts/task_scaffold.py`) reads seed files and creates task files in `docs/dev/tasks/ready/`.

**Determinism**: Same seed + same repo state = same output (byte-for-byte).

**Fail-Closed**: Missing fields, collisions, or invalid formats cause hard failures with no partial writes.

---

## Seed File Location

Canonical seed files live in:
```
docs/dev/task-seeds/
```

Primary seed file (recommended):
```
docs/dev/task-seeds/SEED.md
```

---

## Seed Entry Format

Each seed file contains zero or more seed entries.

Each entry begins with:
```
=== SEED ===
```

Followed by required KEY: VALUE lines.

### Simple Fields

Format: `KEY: value`

Example:
```
STATUS: READY
TASK_ID: TASK_100
TITLE: Implement feature X
DEPENDENCIES: TASK_099, TASK_098
```

### Multi-Line Fields

Format: `KEY: |` followed by indented content lines.

Example:
```
GOAL: |
  Create a new feature that does X.
  Must integrate with system Y.
  Performance target: <100ms.
```

---

## Required Keys

All keys are required. Missing any key = FAIL.

| Key | Type | Description |
|---|---|---|
| `STATUS` | Simple | `READY` or `SKIP`. Only `READY` tasks are generated. |
| `TASK_ID` | Simple | `TASK_###` (explicit 3-digit ID) or `AUTO` (allocate next unused) |
| `TITLE` | Simple | Short task title (used to generate filename slug) |
| `EXECUTOR` | Simple | Optional. `Codex` or `UNASSIGNED` (default `UNASSIGNED`) |
| `GOAL` | Multi-line | What needs to be accomplished |
| `NON_GOALS` | Multi-line | What is explicitly out of scope |
| `ALLOWED_FILES` | Multi-line | Newline-delimited list of file paths allowed to modify |
| `FORBIDDEN_FILES` | Multi-line | Newline-delimited list of file paths forbidden to modify |
| `DEPENDENCIES` | Simple | Comma-separated TASK_IDs or `none` |
| `PROCEDURE` | Multi-line | Step-by-step implementation instructions |
| `ACCEPTANCE` | Multi-line | Criteria for completion |
| `EVIDENCE` | Multi-line | Required evidence artifacts |
| `RETURN_FORMAT` | Multi-line | Expected output format |

## Optional Keys

These keys are optional. Omitting them uses default values.

| Key | Type | Default | Description |
|---|---|---|---|
| `EXECUTOR` | Simple | `UNASSIGNED` | `Codex`, `Cecil`, or `UNASSIGNED`. Determines which executor lane picks up the task. |

---

## Field Details

### STATUS

Valid values:
- `READY`: Generate task file
- `SKIP`: Skip this seed entry (useful for deferring tasks)

### TASK_ID

Explicit ID:
```
TASK_ID: TASK_042
```

Auto-allocation:
```
TASK_ID: AUTO
```

When `AUTO`, the scaffolder scans `docs/dev/tasks/**` for existing `TASK_\d{3}` patterns,
finds the highest number, and allocates `TASK_{N+1}` (zero-padded to 3 digits).

Deterministic: Same repo state = same allocated ID.

### TITLE

Used to generate the filename slug.

Slug generation rules:
1. Convert to lowercase
2. Replace non-alphanumeric characters with underscores
3. Collapse consecutive underscores
4. Trim leading/trailing underscores
5. Truncate to 48 characters max

Example:
```
TITLE: Update API Documentation (Phase 2)
Slug: update_api_documentation_phase_2
Filename: TASK_042__update_api_documentation_phase_2.md
```

### EXECUTOR (Optional)

Specifies which executor lane should pick up the task.

Valid values:
- `Codex`: Task will be included in Codex batch runs (ops/CODEX_BATCH.txt)
- `Cecil`: Task reserved for Cecil (manual or Cecil runloop)
- `UNASSIGNED`: No specific executor assigned (default if omitted)

Example:
```
EXECUTOR: Codex
```

If omitted, the generated task will have `Executor: UNASSIGNED` and will NOT be included in Codex batch runs unless the batch filter is updated to include UNASSIGNED tasks.

**Evidence Path Auto-Inclusion:**

The scaffolder automatically appends `docs/dev/evidence/{TASK_ID}/**` to the ALLOWED_FILES list for all generated tasks, ensuring evidence bundles can be written without manually specifying the path in every seed.

### ALLOWED_FILES and FORBIDDEN_FILES

Newline-delimited lists of file paths.

Example:
```
ALLOWED_FILES: |
  docs/API.md
  docs/CHANGELOG.md
  mcp/README.md

FORBIDDEN_FILES: |
  docs/dev/ASSIGNMENTS.md
  system/scripts/critical.sh
```

If no forbidden files, use:
```
FORBIDDEN_FILES: |
  (none)
```

### DEPENDENCIES

Comma-separated list of TASK_IDs that must complete before this task.

Example:
```
DEPENDENCIES: TASK_040, TASK_041, TASK_042
```

If no dependencies:
```
DEPENDENCIES: none
```

### Multi-Line Content Fields

`GOAL`, `NON_GOALS`, `PROCEDURE`, `ACCEPTANCE`, `EVIDENCE`, `RETURN_FORMAT`:

All use `|` format with indented content.

Example:
```
PROCEDURE: |
  1. Read existing API.md
  2. Update endpoint descriptions
  3. Add examples for new endpoints
  4. Run doc linter
  5. Commit changes
```

---

## Collision Detection

The scaffolder refuses to proceed if:

1. **TASK_ID collision**: Any existing file under `docs/dev/tasks/**` contains the same TASK_ID
2. **Filename collision**: Output filename already exists
3. **Seed validation failure**: Missing required key, invalid STATUS, etc.

Exit code: Non-zero on any collision or validation failure.

---

## Determinism Rules

1. **No timestamps**: Generated task files contain no creation timestamps
2. **Top-to-bottom processing**: Seed entries processed in file order
3. **Stable slug normalization**: Slug generation is deterministic
4. **AUTO allocation**: Based on current repo state scan (deterministic)
5. **No inference**: Only what's explicitly in the seed is generated

---

## Executor Assignment

Seeds may include:
```
EXECUTOR: Codex
```

If omitted, scaffolder defaults to:
```
EXECUTOR: UNASSIGNED
```

Codex batch selection requires `Executor: Codex`, so Codex-intended seeds should set `EXECUTOR: Codex`.

## Generated task metadata

Generated task files include:
- `Executor: <seed EXECUTOR or UNASSIGNED>`
- `Branch: codex/TASK_###` (never `n/a`)
- `## Files allowed to touch` allowlist header
- Plain allowlist lines (no bullet markers)
- `docs/dev/evidence/TASK_###/**` automatically appended when `EVIDENCE` is non-empty

---

## Queue Integration

**Phase A**: The scaffolder does NOT modify `docs/dev/WORK_QUEUE.md`.

Queue updates deferred to Phase A2.

---

## Example Seed Entry

```
=== SEED ===
STATUS: READY
TASK_ID: AUTO
TITLE: Add health check endpoint
EXECUTOR: Codex
GOAL: |
  Create a /health endpoint that returns service status.
  Must include:
  - HTTP 200 on healthy
  - JSON response with version and uptime
  - Integration with existing router

NON_GOALS: |
  - Advanced metrics (deferred to TASK_TBD)
  - Authentication (public endpoint)

ALLOWED_FILES: |
  mcp/server.py
  mcp/routes/health.py
  tests/test_health.py

FORBIDDEN_FILES: |
  docs/dev/ASSIGNMENTS.md

DEPENDENCIES: none

PROCEDURE: |
  1. Create mcp/routes/health.py
  2. Implement /health handler
  3. Register route in mcp/server.py
  4. Write tests in tests/test_health.py
  5. Run test suite
  6. Update API docs

ACCEPTANCE: |
  - GET /health returns 200
  - Response includes {"status": "ok", "version": "X.Y.Z", "uptime": N}
  - All tests pass

EVIDENCE: |
  - Test output showing passing tests
  - curl example showing JSON response
  - Git diff showing implementation

RETURN_FORMAT: |
  Summary:
  - Endpoint: /health
  - Status code: 200
  - Response format: JSON
  - Tests: passing
```

**Note:** The scaffolder will automatically append `docs/dev/evidence/TASK_###/**` to the ALLOWED_FILES list in the generated task file.

---

## Usage

### Dry-Run (Validate Only)

```bash
python3 scripts/task_scaffold.py \
  --seed docs/dev/task-seeds/SEED.md \
  --dry-run
```

Validates seed file and repo state. Prints planned outputs. No writes.

### Write (Generate Task Files)

```bash
python3 scripts/task_scaffold.py \
  --seed docs/dev/task-seeds/SEED.md \
  --write \
  --emit ops/TASK_SCAFFOLD_LAST.json
```

Generates task files and optional JSON summary.

Preflight checks (for `--write`):
- Must be in repo root
- `git status --porcelain` must be empty (clean tree)
- No collisions with existing tasks

---

## Output Summary Format

When `--emit <path>` is used with `--write`, a deterministic JSON summary is generated:

```json
{
  "seed_file": "docs/dev/task-seeds/SEED.md",
  "repo_head": "4d3074e",
  "created_count": 2,
  "created_tasks": [
    {
      "task_id": "TASK_100",
      "filename": "docs/dev/tasks/ready/TASK_100__add_health_check_endpoint.md"
    },
    {
      "task_id": "TASK_101",
      "filename": "docs/dev/tasks/ready/TASK_101__update_api_docs.md"
    }
  ]
}
```

No timestamps included (deterministic).

---

## Failure Modes

| Condition | Behavior | Exit Code |
|---|---|---|
| Missing required key | Print error, FAIL | Non-zero |
| Invalid STATUS value | Print error, FAIL | Non-zero |
| TASK_ID collision | Print error, FAIL | Non-zero |
| Filename collision | Print error, FAIL | Non-zero |
| Dirty git tree (with `--write`) | Print error, FAIL | Non-zero |
| Invalid seed file format | Print error, FAIL | Non-zero |
| AUTO allocation scan fails | Print error, FAIL | Non-zero |

All failures are hard failures. No partial writes.

---

## Phase A Scope

**In Scope:**
- Seed file parsing
- Task file generation
- Collision detection
- Deterministic output
- JSON summary emission

**Out of Scope (Future Phases):**
- WORK_QUEUE.md updates (Phase A2)
- Executor assignment (Future)
- ASSIGNMENTS.md updates (Cecil only, at merge time)
- Branch creation (Manual)
- Evidence bundle generation (Task executor responsibility)

---

## See Also

- `docs/dev/EVIDENCE-CONTRACT.md`: Evidence bundle requirements
- `scripts/task_scaffold.py`: Scaffolder implementation
- `docs/dev/task-seeds/SEED_EXAMPLE.md`: Example seed file
