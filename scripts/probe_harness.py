#!/usr/bin/env python3
"""
probe_harness.py — Minimal bounded probe runner for verification Lane B.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import uuid

from verification import ProbeResult


REPO = Path(__file__).resolve().parents[1]
CAP_REGISTRY_PATH = REPO / "capabilities" / "capability-registry.json"


def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_probe(probe_definition: str, governed_family: str) -> ProbeResult:
    if probe_definition != "capability_registry_probe":
        raise ValueError(f"unsupported probe_definition: {probe_definition}")

    raw = CAP_REGISTRY_PATH.read_bytes()
    parseable = True
    try:
        json.loads(raw.decode("utf-8"))
    except Exception:
        parseable = False

    evidence = {
        "file_hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "parseable": parseable,
        "path": str(CAP_REGISTRY_PATH),
    }

    return ProbeResult(
        probe_id=str(uuid.uuid4()),
        governed_family=str(governed_family),
        property_tested="capability_registry_probe",
        evidence=evidence,
        passed=parseable,
        nonce=None,
        timestamp_utc=_now_utc_z(),
    )
