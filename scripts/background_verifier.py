"""Usage-triggered background chain verification.

The verifier writes a status sidecar only. It never appends to the governance
chain and never runs while holding the chain append lock.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


DEFAULT_VERIFY_EVERY_RECORDS = 100


def verification_status_path(chain_path: Path) -> Path:
    return chain_path.parent / "chain_verification_status.json"


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _threshold(override: Optional[int] = None) -> int:
    if override is not None:
        return max(1, int(override))
    raw = os.environ.get("ATESTED_CHAIN_VERIFY_EVERY_RECORDS", "")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return DEFAULT_VERIFY_EVERY_RECORDS


def count_chain_records(chain_path: Path) -> int:
    if not chain_path.exists():
        return 0
    count = 0
    with chain_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def read_verification_status(chain_path: Path) -> dict[str, Any]:
    path = verification_status_path(chain_path)
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (json.JSONDecodeError, OSError):
        pass
    return {
        "schema_version": 1,
        "status": "not_run",
        "checked": False,
        "last_verified_count": 0,
        "latest_chain_event_count": count_chain_records(chain_path),
        "verify_every_records": _threshold(),
        "next_due_count": _threshold(),
        "break_count": 0,
        "breaks": [],
        "first_break_sequence": None,
        "last_verified_utc": None,
        "running": False,
    }


def trigger_after_append(chain_path: Path, *, threshold: Optional[int] = None) -> None:
    """Start verification in the background when enough new records exist."""

    every = _threshold(threshold)
    try:
        current_count = count_chain_records(chain_path)
        status = read_verification_status(chain_path)
        last_verified = int(status.get("last_verified_count") or 0)
    except Exception:
        return
    if current_count <= 0 or current_count - last_verified < every:
        return
    thread = threading.Thread(
        target=run_verification,
        args=(chain_path,),
        kwargs={"threshold": every, "background": True},
        daemon=True,
    )
    thread.start()


def _write_status_atomic(path: Path, status: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    tmp.replace(path)


def _remove_lock(lockdir: Path) -> None:
    try:
        lockdir.rmdir()
    except OSError:
        pass


def run_verification(
    chain_path: Path,
    *,
    threshold: Optional[int] = None,
    background: bool = False,
) -> dict[str, Any]:
    every = _threshold(threshold)
    status_path = verification_status_path(chain_path)
    lockdir = Path(str(status_path) + ".lock.d")
    try:
        lockdir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        status = read_verification_status(chain_path)
        status["running"] = True
        return status
    try:
        return _run_verification_locked(chain_path, every, background)
    finally:
        _remove_lock(lockdir)


def _run_verification_locked(chain_path: Path, every: int, background: bool) -> dict[str, Any]:
    from readout import check_chain_integrity

    status_path = verification_status_path(chain_path)
    try:
        current_count = count_chain_records(chain_path)
        result = check_chain_integrity(chain_path)
        breaks = result.get("breaks") or []
        first_break = breaks[0] if breaks else None
        status = {
            "schema_version": 1,
            "status": "ok" if result.get("status") == "ok" else "broken",
            "checked": True,
            "background": bool(background),
            "last_verified_count": current_count,
            "latest_chain_event_count": current_count,
            "verify_every_records": every,
            "next_due_count": current_count + every,
            "break_count": int(result.get("break_count") or 0),
            "breaks": breaks,
            "first_break_sequence": _break_sequence(first_break),
            "first_break_reason": first_break.get("reason") if isinstance(first_break, dict) else "",
            "last_verified_utc": _now_utc_z(),
            "running": False,
            "chain_path": str(chain_path),
        }
    except Exception as exc:
        current_count = count_chain_records(chain_path)
        status = {
            "schema_version": 1,
            "status": "error",
            "checked": False,
            "background": bool(background),
            "last_verified_count": 0,
            "latest_chain_event_count": current_count,
            "verify_every_records": every,
            "next_due_count": every,
            "break_count": 0,
            "breaks": [],
            "first_break_sequence": None,
            "first_break_reason": "",
            "last_verified_utc": _now_utc_z(),
            "running": False,
            "error": str(exc),
            "chain_path": str(chain_path),
        }
    _write_status_atomic(status_path, status)
    return status


def _break_sequence(first_break: Any) -> Optional[int]:
    if not isinstance(first_break, dict):
        return None
    value = first_break.get("sequence", first_break.get("line", first_break.get("break_at_line")))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
