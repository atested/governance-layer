# Integration Hooks

## Overview

A-tested v3 governance is enforced at the API proxy layer. Tool calls that pass
through the proxy are classified, evaluated against policy, recorded in the
governance chain, and either allowed or denied before execution.

The previous observation-only hook integration has been removed. Post-action
hooks cannot enforce policy because the operation has already happened by the
time the hook runs.

## Current Integration Boundary

Agents must route model-provider traffic through the governance proxy:

```bash
ANTHROPIC_BASE_URL=http://localhost:8080/anthropic
OPENAI_BASE_URL=http://localhost:8080/openai
GEMINI_BASE_URL=http://localhost:8080/gemini
```

The proxy mediates provider tool-call responses and writes governed decision
records. Local tool runtimes that need direct pre-execution governance must use
a future blocking pre-tool integration, not a post-action observation hook.

## Removed v2 Hook Path

The legacy observation endpoint, shell hook, and observation chain event are
removed. They were a v2 visibility mechanism and are not part of v3 governance.
