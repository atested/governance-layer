"""Size-based chain archive trigger.

Checks the chain file size against a configurable threshold and triggers
archiving via chain_archive.archive_chain() when the threshold is exceeded.
Respects a quiet period to avoid excessive archiving, with a hard ceiling
override at 2x threshold.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional


_DEFAULT_THRESHOLD_MB = 20.0
_DEFAULT_QUIET_MINUTES = 60


def should_archive(
    chain_path: Path,
    *,
    threshold_bytes: int,
    quiet_minutes: int,
    last_archive_time: float,
) -> tuple[bool, str]:
    """Check whether the chain should be archived.

    Returns (should_archive, reason).
    """
    try:
        size = chain_path.stat().st_size
    except OSError:
        return False, "chain_not_found"

    if size < threshold_bytes:
        return False, "below_threshold"

    hard_ceiling = threshold_bytes * 2
    now = time.time()
    within_quiet = (now - last_archive_time) < (quiet_minutes * 60)

    if size >= hard_ceiling:
        return True, "hard_ceiling"

    if within_quiet:
        return False, "quiet_period"

    return True, "threshold_exceeded"


def _last_archive_timestamp(chain_path: Path) -> float:
    """Get the timestamp of the most recent archive from manifests."""
    try:
        from chain_archive import list_archives
    except ImportError:
        return 0.0

    archives = list_archives(chain_path)
    if not archives:
        return 0.0

    # list_archives returns newest first
    latest = archives[0]
    ts_str = latest.get("archived_at_utc", "")
    if not ts_str:
        return 0.0

    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, TypeError):
        return 0.0


def trigger_archive_if_needed(
    chain_path: Path,
    *,
    threshold_mb: float = _DEFAULT_THRESHOLD_MB,
    quiet_minutes: int = _DEFAULT_QUIET_MINUTES,
    callback: Optional[Callable[[dict[str, Any]], None]] = None,
) -> Optional[dict[str, Any]]:
    """Check size thresholds and archive if needed.

    Args:
        chain_path: Path to the chain JSONL file.
        threshold_mb: Size threshold in MB (default 20).
        quiet_minutes: Minimum minutes between archives (default 60).
        callback: Optional function called with the archive manifest after
                  successful archiving (e.g. for artifact generation).

    Returns the archive manifest dict, or None if no archive was triggered.
    """
    threshold_bytes = int(threshold_mb * 1024 * 1024)
    last_archive = _last_archive_timestamp(chain_path)

    do_archive, reason = should_archive(
        chain_path,
        threshold_bytes=threshold_bytes,
        quiet_minutes=quiet_minutes,
        last_archive_time=last_archive,
    )

    if not do_archive:
        return None

    try:
        from chain_archive import archive_chain
    except ImportError:
        return None

    manifest = archive_chain(
        chain_path,
        reason=f"size_threshold:{reason}",
        payload={
            "trigger": "auto_size",
            "threshold_mb": threshold_mb,
            "quiet_minutes": quiet_minutes,
        },
    )

    if callback is not None:
        try:
            callback(manifest)
        except Exception:
            pass  # Artifact generation failure should not break archiving

    return manifest
