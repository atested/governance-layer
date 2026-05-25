#!/usr/bin/env python3
"""QA chain record-size invariant (Python parity with the Rust writer).

QS-039 #22. The Rust QA chain writer (quality-service/src/writer.rs)
rejects any record whose canonical-JSON line exceeds 4096 bytes — the
POSIX PIPE_BUF atomic-append guarantee the lock-free QA chain relies on.
This module is the Python counterpart so any Python code path that emits
QA chain records enforces the same limit instead of writing a torn record.

Scope note: this is deliberately NOT applied to the decision-chain
writers (proxy ChainRecorder, scripts/atested_cli, dashboard). Those use
the mkdir lock protocol rather than lock-free atomic append, and they
legitimately carry records well over 4KB (observed max ~62KB for
mediated_decision records with large tool inputs). The 4KB invariant is
specific to the QA chain.
"""

from __future__ import annotations

# Mirror of writer.rs: line.len() > 4096 is rejected.
MAX_QA_RECORD_BYTES = 4096


def enforce_qa_record_size(line: str, *, sequence: object = None) -> None:
    """Raise ValueError if a QA chain record line exceeds the 4KB limit.

    `line` is the canonical-JSON serialization of the record WITHOUT the
    trailing newline (matching how the Rust writer measures it).
    """
    size = len(line.encode("utf-8"))
    if size > MAX_QA_RECORD_BYTES:
        where = f" (sequence {sequence})" if sequence is not None else ""
        raise ValueError(
            f"QA chain record exceeds 4KB atomic append limit: {size} bytes{where}"
        )
