# Example Task Seeds

This file contains two example task seeds for testing the task scaffolder.

---

=== SEED ===
STATUS: READY
TASK_ID: AUTO
TITLE: Add health check endpoint to MCP server
EXECUTOR: Codex
GOAL: |
  Create a /health endpoint that returns service status.
  Must include:
  - HTTP 200 response on healthy state
  - JSON response with version and uptime
  - Integration with existing FastAPI router

NON_GOALS: |
  - Advanced metrics collection (deferred to future task)
  - Authentication/authorization (public endpoint by design)
  - Database health checks (out of scope for Phase 1)

ALLOWED_FILES: |
  mcp/server.py
  mcp/routes/health.py
  tests/test_health.py
  docs/MCP_API.md

FORBIDDEN_FILES: |
  docs/dev/ASSIGNMENTS.md
  system/scripts/merge-queue.sh

DEPENDENCIES: none

PROCEDURE: |
  1. Create mcp/routes/health.py with health check handler
  2. Implement GET /health endpoint returning JSON status
  3. Register route in mcp/server.py FastAPI app
  4. Write unit tests in tests/test_health.py
  5. Run full test suite to verify integration
  6. Update docs/MCP_API.md with endpoint documentation
  7. Generate evidence bundle

ACCEPTANCE: |
  - GET /health returns 200 status code
  - Response JSON includes: {"status": "ok", "version": "X.Y.Z", "uptime_seconds": N}
  - All existing tests pass
  - New tests achieve >90% coverage of health.py
  - API documentation includes health endpoint specification

EVIDENCE: |
  - Test output showing passing health endpoint tests
  - curl example demonstrating JSON response format
  - Git diff showing implementation
  - Updated API documentation

RETURN_FORMAT: |
  Summary:
  - Endpoint: GET /health
  - Status: 200 OK
  - Response format: {"status": "ok", "version": "...", "uptime_seconds": ...}
  - Tests: All passing (X tests, Y% coverage)
  - Documentation: Updated in docs/MCP_API.md

=== SEED ===
STATUS: READY
TASK_ID: AUTO
TITLE: Document governance runtime directory structure
EXECUTOR: Codex
GOAL: |
  Create comprehensive documentation of the GOV_RUNTIME_DIR structure.
  Must explain:
  - Purpose of each subdirectory
  - File lifecycle and cleanup policies
  - How different components interact with runtime storage
  - Examples of typical directory contents

NON_GOALS: |
  - Implementation changes to runtime behavior (documentation only)
  - Migration tools for existing deployments (defer if needed)
  - Performance optimization of runtime storage (out of scope)

ALLOWED_FILES: |
  docs/RUNTIME_STRUCTURE.md
  docs/PLANNING.md
  README.md

FORBIDDEN_FILES: |
  docs/dev/ASSIGNMENTS.md
  .gov_runtime/

DEPENDENCIES: none

PROCEDURE: |
  1. Audit current .gov_runtime/ structure in governance-layer repo
  2. Document each subdirectory purpose and contents
  3. Create RUNTIME_STRUCTURE.md with clear examples
  4. Add cross-references from PLANNING.md and README.md
  5. Include cleanup policy documentation
  6. Add troubleshooting section for common issues
  7. Generate evidence bundle with documentation review

ACCEPTANCE: |
  - docs/RUNTIME_STRUCTURE.md exists and follows project doc standards
  - All runtime subdirectories are documented
  - File lifecycle policies are explicit
  - Examples show realistic directory contents
  - Cross-references from PLANNING.md and README.md are present
  - Documentation is clear to someone unfamiliar with the codebase

EVIDENCE: |
  - New RUNTIME_STRUCTURE.md file content
  - Git diff showing documentation additions
  - Cross-reference verification (grep output showing links)
  - Peer review feedback (if applicable)

RETURN_FORMAT: |
  Summary:
  - New file: docs/RUNTIME_STRUCTURE.md
  - Cross-references added to: docs/PLANNING.md, README.md
  - Sections documented: [list of runtime subdirectories]
  - Completeness: All runtime directories covered
