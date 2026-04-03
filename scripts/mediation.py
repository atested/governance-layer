#!/usr/bin/env python3
"""
mediation.py — GovMCP v2 mediation pipeline.

The core governance flow for any tool call:
    classify → evaluate policy → record decision → execute or deny

This is a pure Python module with no MCP dependency. It can be used by
any integration layer (MCP proxy, HTTP API, CLI) to mediate operations.

Design reference: docs/design/govmcp-v2-design-revised.md §4
"""

import json
import threading
from pathlib import Path
from typing import Any, Callable, Optional

from classifier import classify
from policy_eval_v2 import evaluate, load_policy_rules


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

class MediationResult:
    """Result of a mediated tool call."""

    __slots__ = (
        "decision", "classification", "decision_record",
        "execution_result", "execution_error",
    )

    def __init__(
        self,
        decision: str,
        classification: dict,
        decision_record: dict,
        execution_result: Any = None,
        execution_error: Optional[str] = None,
    ):
        self.decision = decision
        self.classification = classification
        self.decision_record = decision_record
        self.execution_result = execution_result
        self.execution_error = execution_error

    @property
    def allowed(self) -> bool:
        return self.decision == "ALLOW"

    @property
    def denied(self) -> bool:
        return self.decision == "DENY"


# ---------------------------------------------------------------------------
# Chain recorders
# ---------------------------------------------------------------------------

class ChainRecorder:
    """Appends v2 decision records to the governance chain file."""

    def __init__(self, chain_path: Path):
        self._chain_path = chain_path
        self._lock = threading.Lock()

    def append(self, record: dict) -> None:
        with self._lock:
            line = json.dumps(
                record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            )
            self._chain_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._chain_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def get_prev_hash(self) -> Optional[str]:
        with self._lock:
            return self._last_hash()

    def _last_hash(self) -> Optional[str]:
        if not self._chain_path.exists():
            return None
        try:
            text = self._chain_path.read_text(encoding="utf-8").strip()
            if not text:
                return None
            last_line = text.rsplit("\n", 1)[-1]
            return json.loads(last_line).get("record_hash")
        except (OSError, json.JSONDecodeError, KeyError):
            return None


class InMemoryChainRecorder:
    """In-memory chain recorder for testing and embedded use."""

    def __init__(self):
        self.records = []
        self._lock = threading.Lock()

    def append(self, record: dict) -> None:
        with self._lock:
            self.records.append(record)

    def get_prev_hash(self) -> Optional[str]:
        with self._lock:
            if not self.records:
                return None
            return self.records[-1].get("record_hash")


# ---------------------------------------------------------------------------
# Mediation pipeline
# ---------------------------------------------------------------------------

def mediate(
    tool_name: str,
    args: dict,
    execute_fn: Callable[[str, dict], Any],
    *,
    policy: Optional[dict] = None,
    chain_recorder: Optional[Any] = None,
    session_id: str = "",
    user_identity: str = "",
) -> MediationResult:
    """Mediate a tool call through the full governance pipeline.

    1. Classify the operation by evidence inference (Phase 0 classifier)
    2. Evaluate against policy rules (Phase 0 evaluator)
    3. Record the decision to the governance chain
    4. If ALLOW: call execute_fn and return its result
    5. If DENY: return denial without executing

    Args:
        tool_name: The tool name as provided by the agent/runtime.
        args: The tool's parameters.
        execute_fn: Called as execute_fn(tool_name, args) if policy allows.
        policy: Policy rules dict. If None, loads from default path.
        chain_recorder: ChainRecorder or InMemoryChainRecorder. If None,
                        decisions are not persisted (useful for dry-run).
        session_id: Session identifier for decision records.
        user_identity: Operator/user identity for decision records.

    Returns:
        MediationResult with decision, classification, record, and
        execution outcome.
    """
    # Step 1: Classify by evidence inference
    classification = classify(tool_name, args)

    # Step 2: Chain linkage
    prev_hash = None
    if chain_recorder is not None:
        prev_hash = chain_recorder.get_prev_hash()

    # Step 3: Evaluate policy
    decision_record = evaluate(
        classification,
        policy=policy,
        prev_record_hash=prev_hash,
        user_identity=user_identity,
        session_id=session_id,
    )

    decision = decision_record["policy_decision"]

    # Step 4: Record to chain
    if chain_recorder is not None:
        chain_recorder.append(decision_record)

    # Step 5: Execute or deny
    if decision == "ALLOW":
        try:
            result = execute_fn(tool_name, args)
            return MediationResult(
                decision=decision,
                classification=classification,
                decision_record=decision_record,
                execution_result=result,
            )
        except Exception as exc:
            return MediationResult(
                decision=decision,
                classification=classification,
                decision_record=decision_record,
                execution_error=str(exc),
            )
    else:
        return MediationResult(
            decision=decision,
            classification=classification,
            decision_record=decision_record,
        )
