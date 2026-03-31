#!/usr/bin/env python3
"""Shared coverage_stamp_v1 canonicalization and validation helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

COVERAGE_STAMP_VERSION = "coverage_stamp_v1"

SURFACE_ORDER = (
    "web",
    "filesystem",
    "shell",
    "routing",
    "model",
    "memory",
    "network",
    "toolchain",
)

COVERAGE_REASON_OK = "COVERAGE_STAMP_OK"
COVERAGE_REASON_MISSING = "COVERAGE_STAMP_MISSING"
COVERAGE_REASON_MALFORMED = "COVERAGE_STAMP_MALFORMED"
COVERAGE_REASON_VERSION_UNSUPPORTED = "COVERAGE_STAMP_VERSION_UNSUPPORTED"
COVERAGE_REASON_SURFACE_UNKNOWN = "COVERAGE_STAMP_SURFACE_UNKNOWN"
COVERAGE_REASON_PARTIAL = "COVERAGE_STAMP_PARTIAL"
COVERAGE_REASON_ORDER_INVALID = "COVERAGE_STAMP_ORDER_INVALID"

_ALLOWED_TOP_LEVEL_KEYS = {
    "coverage_stamp_version",
    "generated_by",
    "generated_from",
    "overall_status",
    "surfaces",
}
_ALLOWED_SURFACE_KEYS = {
    "capability_surface",
    "coverage",
    "evidence_sources",
    "notes",
    "surface_id",
}
_ALLOWED_COVERAGE_KEYS = {"observation", "enforcement", "provenance"}


@dataclass
class CoverageValidation:
    ok: bool
    reason_code: str
    overall_status: str
    normalized: dict[str, Any] | None
    message: str


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def _surface_index(surface_id: str) -> int:
    return SURFACE_ORDER.index(surface_id)


def _validate_surface_entry(item: Any) -> tuple[bool, str, dict[str, Any] | None, str]:
    if not isinstance(item, dict):
        return False, COVERAGE_REASON_MALFORMED, None, "surface entry must be an object"

    extra = sorted(set(item.keys()) - _ALLOWED_SURFACE_KEYS)
    if extra:
        return False, COVERAGE_REASON_MALFORMED, None, f"surface entry has unknown key: {extra[0]}"

    surface_id = item.get("surface_id")
    capability_surface = item.get("capability_surface")
    coverage = item.get("coverage")
    evidence_sources = item.get("evidence_sources", [])
    notes = item.get("notes")

    if not isinstance(surface_id, str) or not surface_id:
        return False, COVERAGE_REASON_MALFORMED, None, "surface_id missing or invalid"
    if surface_id not in SURFACE_ORDER:
        return False, COVERAGE_REASON_SURFACE_UNKNOWN, None, f"unknown surface_id: {surface_id}"
    if not isinstance(capability_surface, str) or capability_surface != surface_id:
        return False, COVERAGE_REASON_MALFORMED, None, "capability_surface must equal surface_id"
    if not isinstance(coverage, dict):
        return False, COVERAGE_REASON_MALFORMED, None, "coverage missing or invalid"

    coverage_extra = sorted(set(coverage.keys()) - _ALLOWED_COVERAGE_KEYS)
    if coverage_extra:
        return False, COVERAGE_REASON_MALFORMED, None, f"coverage has unknown key: {coverage_extra[0]}"

    cov_fields = {}
    for key in ("observation", "enforcement", "provenance"):
        value = coverage.get(key)
        if not isinstance(value, bool):
            return False, COVERAGE_REASON_MALFORMED, None, f"coverage.{key} must be bool"
        cov_fields[key] = value

    if not isinstance(evidence_sources, list) or not all(isinstance(x, str) and x for x in evidence_sources):
        return False, COVERAGE_REASON_MALFORMED, None, "evidence_sources must be list[str]"
    if evidence_sources != sorted(evidence_sources):
        return False, COVERAGE_REASON_ORDER_INVALID, None, "evidence_sources not in canonical order"

    normalized = {
        "capability_surface": surface_id,
        "coverage": cov_fields,
        "evidence_sources": list(evidence_sources),
        "surface_id": surface_id,
    }
    if notes is not None:
        if not isinstance(notes, str):
            return False, COVERAGE_REASON_MALFORMED, None, "notes must be string when present"
        normalized["notes"] = notes

    return True, COVERAGE_REASON_OK, normalized, "ok"


def validate_coverage_stamp(raw: Any, required: bool = False) -> CoverageValidation:
    if raw is None:
        if required:
            return CoverageValidation(False, COVERAGE_REASON_MISSING, "missing", None, "coverage stamp required but absent")
        return CoverageValidation(True, COVERAGE_REASON_MISSING, "missing", None, "coverage stamp absent (optional)")

    if not isinstance(raw, dict):
        return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, "coverage stamp must be object")

    extra_top = sorted(set(raw.keys()) - _ALLOWED_TOP_LEVEL_KEYS)
    if extra_top:
        return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, f"coverage stamp has unknown key: {extra_top[0]}")

    version = raw.get("coverage_stamp_version")
    if version != COVERAGE_STAMP_VERSION:
        return CoverageValidation(
            False,
            COVERAGE_REASON_VERSION_UNSUPPORTED,
            "missing",
            None,
            "coverage_stamp_version mismatch",
        )

    generated_by = raw.get("generated_by", "")
    generated_from = raw.get("generated_from", [])
    if not isinstance(generated_by, str) or not generated_by:
        return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, "generated_by invalid")
    if not isinstance(generated_from, list) or not all(isinstance(x, str) and x for x in generated_from):
        return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, "generated_from invalid")
    if generated_from != sorted(generated_from):
        return CoverageValidation(False, COVERAGE_REASON_ORDER_INVALID, "missing", None, "generated_from not in canonical order")
    if len(set(generated_from)) != len(generated_from):
        return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, "generated_from has duplicate values")

    surfaces = raw.get("surfaces")
    if not isinstance(surfaces, list) or not surfaces:
        return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, "surfaces missing or invalid")

    normalized_surfaces = []
    seen = set()
    for item in surfaces:
        ok, reason, normalized, message = _validate_surface_entry(item)
        if not ok:
            return CoverageValidation(False, reason, "missing", None, message)
        sid = normalized["surface_id"]
        if sid in seen:
            return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, f"duplicate surface_id: {sid}")
        seen.add(sid)
        normalized_surfaces.append(normalized)

    in_order = [s["surface_id"] for s in normalized_surfaces]
    sorted_order = sorted(in_order, key=_surface_index)
    if in_order != sorted_order:
        return CoverageValidation(False, COVERAGE_REASON_ORDER_INVALID, "missing", None, "surfaces not in canonical order")

    all_true = True
    for item in normalized_surfaces:
        cov = item["coverage"]
        all_true = all_true and cov["observation"] and cov["enforcement"] and cov["provenance"]

    overall_status = "complete" if all_true else "partial"
    reason_code = COVERAGE_REASON_OK if all_true else COVERAGE_REASON_PARTIAL
    if required and not all_true:
        return CoverageValidation(False, COVERAGE_REASON_PARTIAL, overall_status, None, "required coverage stamp is partial")

    if "overall_status" in raw:
        claimed = raw.get("overall_status")
        if not isinstance(claimed, str):
            return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, "overall_status invalid")
        if claimed != overall_status:
            return CoverageValidation(False, COVERAGE_REASON_MALFORMED, "missing", None, "overall_status mismatch")

    normalized = {
        "coverage_stamp_version": COVERAGE_STAMP_VERSION,
        "generated_by": generated_by,
        "generated_from": list(generated_from),
        "overall_status": overall_status,
        "surfaces": normalized_surfaces,
    }
    return CoverageValidation(True, reason_code, overall_status, normalized, "ok")
