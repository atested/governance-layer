#!/usr/bin/env python3
"""INV-010 enforcement: no direct chain writers outside the audited helpers.

INV-010 requires every writer to decision-chain.jsonl to use the lock
protocol (cross-process mkdir lock + in-process serialization + read-head-
inside-lock + atomic O_APPEND). Five Python helpers and one shell writer
were audited and confirmed conformant in D-2026-0407-004. This test fails
loudly if a new direct O_APPEND-on-CHAIN writer appears outside that
allowlist, preventing regressions of the D-021 race condition.

Reference: docs/INVARIANTS.md (INV-010)
"""

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Allowlisted chain writers per D-2026-0407-004 audit. Adding a new entry
# here requires a visible, auditable edit — that is the point. Each entry
# is (relative file path, function/identifier comment for documentation).
ALLOWLIST = {
    "dashboard/server.py",       # _append_chain_record_atomic
    "proxy/server.py",           # ChainRecorder.append_atomic
    "scripts/atested_cli.py",    # _append_chain_record_atomic
    "scripts/remote_import.py",  # append_import_envelope
    "scripts/append-record-runtime.sh",  # production shell writer
    "scripts/append-record.sh",  # in-repo test fixture writer (audited, conformant)
}

# Pattern: any open() with O_APPEND on a variable named CHAIN (case-insensitive
# enough to catch CHAIN, chain_path, self._chain_path) within the production
# source tree. Tightened to look for O_APPEND in the same line as a chain
# reference rather than just any O_APPEND, to avoid flagging unrelated logs.
PY_PATTERN = re.compile(r"O_APPEND.*CHAIN|CHAIN.*O_APPEND", re.IGNORECASE)
SH_PATTERN = re.compile(r">>\s*[\"']?\$?\{?CHAIN", re.IGNORECASE)

# Directories to scan. Exclude tests/, fixtures, out-of-tree dirs, and archived code.
SCAN_DIRS = ["dashboard", "proxy", "scripts"]


def _scan_file(path: Path):
    """Return list of (lineno, line) tuples that look like direct chain writes."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits = []
    pattern = SH_PATTERN if path.suffix == ".sh" else PY_PATTERN
    for i, line in enumerate(text.splitlines(), start=1):
        if pattern.search(line):
            hits.append((i, line.strip()))
    return hits


def test_inv010_no_unauthorized_chain_writers():
    """Fail if a non-allowlisted file directly writes to decision-chain.jsonl."""
    violations = []
    for d in SCAN_DIRS:
        root = REPO / d
        if not root.exists():
            continue
        for ext in ("*.py", "*.sh"):
            for path in root.rglob(ext):
                rel = str(path.relative_to(REPO))
                hits = _scan_file(path)
                if not hits:
                    continue
                if rel in ALLOWLIST:
                    continue
                for lineno, line in hits:
                    violations.append(f"{rel}:{lineno}: {line}")

    assert not violations, (
        "INV-010 violation: direct chain writer found outside the allowlist.\n"
        "Each new chain writer must use the lock protocol (see "
        "docs/INVARIANTS.md INV-010) and be "
        "added to ALLOWLIST in this test file.\n\nOffending lines:\n  "
        + "\n  ".join(violations)
    )


if __name__ == "__main__":
    test_inv010_no_unauthorized_chain_writers()
    print("PASS: test_inv010_no_unauthorized_chain_writers")
