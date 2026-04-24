#!/usr/bin/env python3
"""
policy_eval_v2.py — Action-based policy evaluator for GovMCP v2.

Takes classifier output + policy rules → decision record.
Reuses path validation logic from v1 (canonicalize, under_base,
is_hidden_segment) but routes by action type and evidence dimensions
instead of capability class.

Design reference: docs/design/govmcp-v2-design-revised.md §4.3
"""

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Reuse v1 path validation primitives
from policy_eval_shared import (
    canonicalize,
    under_base,
    is_hidden_segment,
    sanitize_base_dir,
    resolve_base_dirs,
)


# ---------------------------------------------------------------------------
# Policy rules loading
# ---------------------------------------------------------------------------

_DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "capabilities" / "policy-rules.json"
)


def load_policy_rules(path: Optional[Path] = None) -> dict:
    """Load policy rules from JSON file.

    Fail-closed: if the file is missing, unreadable, or malformed,
    returns a deny-all policy (empty rules list) instead of crashing
    the request path.  The error is logged so operators notice.
    """
    p = path or _DEFAULT_POLICY_PATH
    try:
        with open(p, "r", encoding="utf-8") as f:
            rules = json.load(f)
    except FileNotFoundError:
        _log_policy_error(f"Policy rules file not found: {p}")
        return _DENY_ALL_POLICY
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        _log_policy_error(f"Malformed policy rules in {p}: {exc}")
        return _DENY_ALL_POLICY
    except OSError as exc:
        _log_policy_error(f"Cannot read policy rules {p}: {exc}")
        return _DENY_ALL_POLICY

    if not isinstance(rules, dict) or "rules" not in rules:
        _log_policy_error(f"Invalid policy rules structure in {p}")
        return _DENY_ALL_POLICY
    if not isinstance(rules["rules"], list):
        _log_policy_error(f"policy rules 'rules' key is not a list in {p}")
        return _DENY_ALL_POLICY
    return rules


# Deny-all fallback: empty rules list means default-DENY catches everything
_DENY_ALL_POLICY = {"rules": [], "_fallback": True}


def _log_policy_error(msg: str) -> None:
    """Log a policy load error to stderr (import-time safe)."""
    import logging
    logging.getLogger("policy_eval_v2").error("[FAIL-CLOSED] %s", msg)


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------

def _match_rule(rule: dict, classification: dict, context: dict) -> bool:
    """Check if a classification matches a rule's conditions.

    Returns True if ALL match conditions are satisfied.
    """
    match = rule.get("match", {})

    # Action type match
    if "action_type" in match:
        if classification["action_type"] not in match["action_type"]:
            return False

    # Confidence tier match
    if "confidence_tier" in match:
        if classification["confidence_tier"] not in match["confidence_tier"]:
            return False

    # Scope match
    if "scope" in match:
        if classification["scope"] not in match["scope"]:
            return False

    # Target within base dirs check
    if "target_within_base_dirs" in match:
        required = match["target_within_base_dirs"]
        actual = context.get("targets_within_base_dirs", False)
        if required != actual:
            return False

    # No hidden paths check
    if "no_hidden_paths" in match:
        required = match["no_hidden_paths"]
        has_hidden = context.get("has_hidden_paths", False)
        if required and has_hidden:
            return False

    # No executable output check
    if "no_executable_output" in match:
        required = match["no_executable_output"]
        is_exec = context.get("is_executable_output", False)
        if required and is_exec:
            return False

    return True


# ---------------------------------------------------------------------------
# Target evaluation (reuses v1 path validation)
# ---------------------------------------------------------------------------

def _evaluate_targets(
    classification: dict,
    base_dirs: list[str],
    deny_hidden: bool,
    deny_executable: bool,
) -> dict:
    """Evaluate classification targets against path-based policy constraints.

    Returns a context dict with computed boolean properties used by rule matching.
    """
    targets = classification.get("targets", [])
    resolved_bases = resolve_base_dirs(base_dirs)

    context = {
        "targets_within_base_dirs": True,  # assume true until proven false
        "has_hidden_paths": False,
        "is_executable_output": False,
        "path_violations": [],
    }

    if not targets:
        # No targets to validate — conservative: not within base dirs
        context["targets_within_base_dirs"] = True  # no paths = no violation
        return context

    for target in targets:
        # Skip non-path targets (URLs, commands, patterns)
        if not _looks_like_path(target):
            continue

        try:
            canon = canonicalize(target)
        except (ValueError, OSError):
            context["targets_within_base_dirs"] = False
            context["path_violations"].append({
                "target": target,
                "reason": "path_canonicalization_failed",
            })
            continue

        # Check hidden paths
        if deny_hidden and is_hidden_segment(canon):
            context["has_hidden_paths"] = True
            context["path_violations"].append({
                "target": target,
                "reason": "hidden_path",
            })

        # Check base directory containment
        in_base = False
        for base_s in resolved_bases:
            try:
                base = canonicalize(base_s)
                if under_base(canon, base):
                    in_base = True
                    break
            except (ValueError, OSError):
                continue

        if not in_base:
            context["targets_within_base_dirs"] = False
            context["path_violations"].append({
                "target": target,
                "reason": "outside_base_dirs",
            })

    return context


def _looks_like_path(s: str) -> bool:
    """Heuristic: does this string look like a filesystem path?"""
    if not s:
        return False
    # Absolute paths, home-relative paths, or relative paths with /
    if s.startswith("/") or s.startswith("~") or s.startswith("./") or s.startswith("../"):
        return True
    # Avoid matching URLs, commands, patterns
    if s.startswith("http://") or s.startswith("https://"):
        return False
    if " " in s:  # likely a command, not a path
        return False
    # Contains path separators and looks file-like
    if "/" in s and not s.startswith("-"):
        return True
    return False


# ---------------------------------------------------------------------------
# Decision record construction
# ---------------------------------------------------------------------------

def _now_utc_z() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _compute_record_hash(record: dict) -> str:
    """Compute SHA-256 hash of the record with record_hash set to null."""
    hashable = dict(record)
    hashable["record_hash"] = None
    canonical = json.dumps(hashable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Main evaluator
# ---------------------------------------------------------------------------

def evaluate(
    classification: dict,
    policy: Optional[dict] = None,
    *,
    prev_record_hash: Optional[str] = None,
    user_identity: Optional[str] = None,
    session_id: Optional[str] = None,
) -> dict:
    """Evaluate a classified operation against policy rules.

    Args:
        classification: Output from classifier.classify()
        policy: Policy rules dict (loaded from policy-rules.json).
                If None, loads from default path.
        prev_record_hash: Hash of previous chain record for linkage.
        user_identity: Identity of the operator/user.
        session_id: Session identifier.

    Returns:
        Decision record dict with policy_decision, matched_rule,
        classification, and chain metadata.
    """
    if policy is None:
        policy = load_policy_rules()

    rules = policy.get("rules", [])
    base_dirs = policy.get("base_dirs", [])
    deny_hidden = policy.get("deny_hidden_paths", True)
    deny_executable = policy.get("deny_executable_outputs", True)

    # Evaluate targets against path constraints
    target_context = _evaluate_targets(
        classification, base_dirs, deny_hidden, deny_executable
    )

    # Match rules in order — first match wins
    matched_rule = None
    for rule in rules:
        if _match_rule(rule, classification, target_context):
            matched_rule = rule
            break

    # Determine decision
    if matched_rule:
        decision = matched_rule["decision"]
        reason = matched_rule.get("reason", "")
        rule_id = matched_rule.get("id", "")
    else:
        decision = policy.get("default_decision", "DENY")
        reason = policy.get("default_reason", "No matching policy rule")
        rule_id = "__default__"

    # Build policy reasons list (compatible with v1 format)
    policy_reasons = []
    if decision == "DENY":
        policy_reasons.append({
            "code": f"V2_{rule_id.upper().replace('-', '_')}",
            "detail": {
                "reason": reason,
                "rule_id": rule_id,
                "path_violations": target_context.get("path_violations", []),
            },
        })

    # Build decision record
    record = {
        "record_version": "2.0",
        "record_type": "mediated_decision",
        "timestamp_utc": _now_utc_z(),
        "request_id": str(uuid.uuid4()),
        "session_id": session_id or "",
        "user_identity": user_identity or "",
        "original_tool": classification.get("original_tool", ""),
        "classification": {
            "action_type": classification["action_type"],
            "targets": classification["targets"],
            "scope": classification["scope"],
            "confidence_tier": classification["confidence_tier"],
        },
        "evidence": classification.get("evidence", {}),
        "policy_decision": decision,
        "policy_reasons": policy_reasons,
        "matched_rule": rule_id,
        "prev_record_hash": prev_record_hash,
        "record_hash": None,
    }

    record["record_hash"] = _compute_record_hash(record)

    return record
