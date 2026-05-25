#!/usr/bin/env python3
"""ATESTED_* / GOV_* env var compatibility helper (Python parity).

QS-039 #14. Mirrors the Rust crate's read_env_preferred
(quality-service/src/config.rs): prefer the canonical ATESTED_* name and
fall back to the legacy GOV_* alias, emitting a one-line stderr
deprecation warning when only the legacy name is set.

The GOV_* names predate the QS-029 ATESTED_* convention. The supervisor
exports both name styles for child processes (QS-033), so this fallback
keeps existing operator scripts and environments working through the
deprecation window.
"""

from __future__ import annotations

import os
import sys
from typing import Optional


def read_env_preferred(
    canonical: str, legacy: str, default: Optional[str] = None
) -> Optional[str]:
    """Return the value of `canonical`, else `legacy` (with a deprecation
    warning), else `default`. Matches os.environ.get semantics for the
    default."""
    value = os.environ.get(canonical)
    if value is not None:
        return value
    value = os.environ.get(legacy)
    if value is not None:
        print(
            f"warning: env var {legacy} is deprecated; use {canonical} "
            f"(the legacy name still works for one release window)",
            file=sys.stderr,
        )
        return value
    return default
