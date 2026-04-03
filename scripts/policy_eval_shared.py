#!/usr/bin/env python3
"""
policy_eval_shared.py — Path validation primitives shared between v1 and v2.

Extracted from policy-eval.py to avoid duplication. These functions handle
path canonicalization, base directory validation, hidden path detection,
and directory traversal prevention.
"""

import os
import sys
from pathlib import Path


def is_hidden_segment(path: Path) -> bool:
    """Check if any segment of the path starts with a dot (hidden)."""
    return any(part.startswith(".") and part not in (".", "..") for part in path.parts)


def canonicalize(p: str) -> Path:
    """Canonicalize a path: expand ~ and resolve to absolute."""
    return Path(p).expanduser().resolve(strict=False)


def under_base(path: Path, base: Path) -> bool:
    """Check if path is under base directory.

    Handles case-insensitive filesystems (macOS).
    """
    try:
        path.relative_to(base)
        return True
    except ValueError:
        if sys.platform == "darwin":
            path_s = str(path).rstrip("/")
            base_s = str(base).rstrip("/")
            path_folded = path_s.casefold()
            base_folded = base_s.casefold()
            return path_folded == base_folded or path_folded.startswith(base_folded + "/")
        return False


def sanitize_base_dir(value: str) -> str:
    """Reject paths containing injection vectors (H4)."""
    if "\x00" in value:
        raise ValueError(f"null byte in base dir: {value!r}")
    for ch in (";", "|", "&", "`", "$", "\n", "\r"):
        if ch in value:
            raise ValueError(f"shell metacharacter in base dir: {value!r}")
    canon = Path(value).resolve(strict=False)
    if str(canon) == "/":
        raise ValueError(f"base dir resolves to filesystem root: {value!r}")
    return value


def resolve_base_dirs(base_dirs: list) -> list[str]:
    """Resolve base directory tokens to actual paths."""
    resolved = []
    for base in base_dirs:
        value = str(base)
        value = value.replace(
            "__GOV_CANONICAL_REPO_PATH__",
            os.environ.get("GOV_CANONICAL_REPO_PATH", str(Path(__file__).resolve().parents[1])),
        )
        value = value.replace(
            "__GOV_RUNTIME_PATH__",
            os.environ.get("GOV_RUNTIME_PATH", "/tmp/gov_runtime"),
        )
        try:
            value = sanitize_base_dir(value)
        except ValueError:
            continue
        resolved.append(value)
    return resolved
