#!/usr/bin/env python3
"""Local-first governance operations with truthful hosted-provider status."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Mapping

from governance_chain import GovernanceChainRecorder, validate_record
from operator_review import filter_activity
from policy_eval_v2 import evaluate
from scoped_evidence import build_scoped_evidence_package, verify_scoped_evidence_package


LOCAL_CAPABILITIES = (
    "policy_evaluation",
    "governance_recording",
    "dashboard_review",
    "report_generation",
    "evidence_verification",
)


class LocalGovernanceRuntime:
    """Coordinate governance functions which require no hosted service."""

    def __init__(
        self,
        chain_path: Path,
        *,
        hosted_reachable: bool = False,
        provider_operation: Callable[..., Any] | None = None,
        signing_key: Any = None,
    ) -> None:
        self.chain_path = Path(chain_path)
        self.hosted_reachable = bool(hosted_reachable)
        self.provider_operation = provider_operation
        self.signing_key = signing_key
        self.recorder = GovernanceChainRecorder(self.chain_path, signing_key=signing_key)

    def capability_status(self) -> dict[str, Any]:
        local_functions = {
            name: {"status": "available", "execution_basis": "local-data"}
            for name in LOCAL_CAPABILITIES
        }
        if self.signing_key is None:
            local_functions["report_generation"] = {
                "status": "unavailable",
                "execution_basis": "local-data",
                "reason_code": "LOCAL_SIGNING_KEY_UNAVAILABLE",
            }
        return {
            "connectivity": "hosted-reachable" if self.hosted_reachable else "local-only",
            "local_functions": local_functions,
            "provider_interaction": {
                "status": "available"
                if self.hosted_reachable and self.provider_operation is not None
                else "unavailable",
                "completed": False,
                "reason_code": None
                if self.hosted_reachable and self.provider_operation is not None
                else "HOSTED_PROVIDER_UNAVAILABLE",
            },
        }

    def evaluate_policy(
        self, classification: dict, policy: dict, *, user_identity: str, session_id: str = ""
    ) -> dict:
        return evaluate(
            deepcopy(classification), deepcopy(policy),
            user_identity=user_identity, session_id=session_id,
        )

    def record_decision(self, decision: Mapping[str, Any], *, subject_id: str) -> dict[str, Any]:
        return self.recorder.append_mediated_decision(
            subject_id=subject_id, payload=deepcopy(dict(decision))
        )

    def records(self) -> list[dict[str, Any]]:
        if not self.chain_path.exists():
            return []
        records: list[dict[str, Any]] = []
        previous = None
        for number, line in enumerate(self.chain_path.read_text(encoding="utf-8").splitlines(), start=1):
            try:
                record = json.loads(line)
                validate_record(record)
            except Exception as exc:
                raise ValueError(f"invalid local governance record at line {number}") from exc
            if record.get("prev_record_hash") != previous:
                raise ValueError(f"broken local governance linkage at line {number}")
            previous = record.get("record_hash")
            records.append(record)
        return records

    def dashboard_review(self, **filters: Any) -> list[dict[str, Any]]:
        projection = []
        for record in self.records():
            row = deepcopy(record.get("payload") or {})
            row.setdefault("record_id", record["record_id"])
            row.setdefault("timestamp_utc", record["recorded_at"])
            row.setdefault("subject_id", record["subject_id"])
            projection.append(row)
        return filter_activity(projection, **filters)

    def generate_report(
        self, *, scope: Mapping[str, Any], issuer: str, created_at: str | None = None
    ) -> bytes:
        return build_scoped_evidence_package(
            self.records(), scope=scope, signing_key=self.signing_key,
            issuer=issuer, created_at=created_at,
        )

    def verify_evidence(
        self, package_bytes: bytes, *, expected_scope: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return verify_scoped_evidence_package(package_bytes, expected_scope=expected_scope)

    def provider_interaction(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Never represent a provider-dependent action as locally completed."""
        if not self.hosted_reachable or self.provider_operation is None:
            return {
                "status": "unavailable",
                "completed": False,
                "reason_code": "HOSTED_PROVIDER_UNAVAILABLE",
            }
        result = self.provider_operation(*args, **kwargs)
        return {"status": "completed", "completed": True, "result": result}
