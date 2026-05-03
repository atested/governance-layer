# Integration Hooks — Observation Endpoint Guide

## Overview

The Atested governance layer provides an **observation endpoint** that any AI
tool can call to report ungoverned operations. This enables the **Transparency
metric** — the ratio of governed operations to total observed operations.

```
Transparency % = governed_operations / (governed_operations + ungoverned_observations)
```

Without observation data, the dashboard shows "No observation data" rather than
a misleading 100%.

## What the Transparency Metric Measures

- **Governed operations**: Actions that flow through the governance chain
  (tool calls intercepted by the API proxy). These are automatically counted.
- **Ungoverned observations**: Native tool calls (Read, Write, Bash, etc.)
  reported by action hooks. These are only counted when hooks are configured.

A transparency of 85% means 85% of all observed operations went through the
governance layer. The remaining 15% were native tool calls that bypassed it.

## Why It Matters

Governance is only meaningful if it covers the operations that actually happen.
If an AI agent uses native tools for 90% of its work and governed tools for
10%, the governance chain captures only a fraction of reality. The transparency
metric makes this gap visible to operators.

## Observation Endpoints

### 1. Dashboard API endpoint

Tool name: `observe_ungoverned_operation`

Parameters:
| Parameter | Type | Required | Description |
|---|---|---|---|
| `operation_type` | string | yes | One of: `read`, `write`, `edit`, `delete`, `move`, `execute`, `glob`, `grep`, `list`, `other` |
| `target` | string | no | Path or resource identifier |
| `source` | string | no | Identifier for the reporting tool (e.g., `claude_code_hook`) |
| `observed_at` | string | no | ISO-8601 timestamp; defaults to current time |

### 2. HTTP POST (for any tool with webhook support)

```
POST /api/observe
Content-Type: application/json

{
  "operation_type": "write",
  "target": "/path/to/file.py",
  "source": "my_tool_hook"
}
```

Response:
```json
{
  "recorded": true,
  "event_id": "uuid-...",
  "operation_type": "write"
}
```

The HTTP endpoint runs on the dashboard server (default port 9700).

## Platform-Specific Integration

### Claude Code (PostToolUse Hook)

Claude Code supports hooks that fire after each tool use. Add the following
to your Claude Code hooks configuration (`.claude/hooks.json` or
`~/.claude/hooks.json`):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Read|Write|Edit|Bash|Glob|Grep",
        "hook": "curl -s -X POST http://localhost:9700/api/observe -H 'Content-Type: application/json' -d '{\"operation_type\": \"$TOOL_USE_NAME\", \"target\": \"$TOOL_USE_TARGET\", \"source\": \"claude_code_hook\"}'"
      }
    ]
  }
}
```

For a ready-to-use configuration, see `docs/claude_code_hooks.json` in this
repository.

**Operation type mapping for Claude Code native tools:**
| Claude Code Tool | operation_type |
|---|---|
| Read | `read` |
| Write | `write` |
| Edit | `edit` |
| Bash | `execute` |
| Glob | `glob` |
| Grep | `grep` |

### Generic HTTP POST (Any Tool)

Any tool that supports webhooks or post-action hooks can report ungoverned
operations by sending an HTTP POST:

```bash
curl -s -X POST http://localhost:9700/api/observe \
  -H "Content-Type: application/json" \
  -d '{
    "operation_type": "write",
    "target": "/path/to/file",
    "source": "my_tool"
  }'
```

For remote servers, replace `localhost:9700` with the appropriate host and
port.

### Shell Script Wrapper

For tools that don't support hooks natively, wrap the operation:

```bash
#!/bin/bash
# observe-and-run.sh — Run a command and report it as ungoverned
"$@"
STATUS=$?
curl -s -X POST http://localhost:9700/api/observe \
  -H "Content-Type: application/json" \
  -d "{\"operation_type\": \"execute\", \"target\": \"$1\", \"source\": \"shell_wrapper\"}" \
  > /dev/null 2>&1 &
exit $STATUS
```

## How to Interpret the Metric

| Transparency % | Interpretation |
|---|---|
| 95-100% | Excellent — nearly all operations are governed |
| 80-94% | Good — most operations governed, some native tool use |
| 50-79% | Moderate — significant ungoverned activity |
| < 50% | Low — most operations bypass governance |
| "No observation data" | Hooks not configured — metric unavailable |

## Time-Range Filtering

The transparency metric supports time-range filtering via the dashboard UI
or API:

```
GET /api/transparency?start_time=2026-03-31T00:00:00Z&end_time=2026-03-31T23:59:59Z
```

The dashboard's Overview page shows the metric for the current status window.
The `/api/transparency` endpoint accepts `start_time` and `end_time` parameters
for custom ranges.

## Important Notes

1. **Observation is voluntary** — this is not enforcement. It improves visibility
   but does not prevent ungoverned operations.
2. **Lightweight** — observation events are minimal chain records with no policy
   evaluation overhead.
3. **Platform-agnostic** — any tool that can make an HTTP POST can integrate.
4. **Privacy** — the `target` field is optional. Tools can report operation types
   without revealing paths if desired.
