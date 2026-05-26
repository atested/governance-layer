#!/usr/bin/env python3
"""
approval_store.py — Minimal approval lookup for opaque artifact identities.

Implements the approved artifact identity store (spec §9.7) as a derived
index over approval and revocation events. The store is not an independent
authority — it must be consistent with the approval event history.

Approval scope (spec §9.4) is the conjunction of five fields:
  - artifact_identity: SHA-256 content hash of the artifact
  - approving_operator: operator who granted approval
  - governed_family: governed family/surface identifier
  - deployment_context: deployment/host environment
  - policy_version: policy/baseline version in effect

An approval applies only when all five fields match the current context.
Revocations remove approvals by matching artifact_identity +
governed_family + deployment_context + policy_version.

Scope mismatch is automatic — if any field doesn't match, the approval
simply doesn't apply (spec §9.5).

Signature verification (F-11): When require_signatures=True, approval and
revocation events must carry a valid Ed25519 signature. Events without a
signature or with an invalid signature are rejected (not ingested).
"""

import json
import logging
import hashlib
import fnmatch
from pathlib import Path
from typing import Any, Optional, Union

logger = logging.getLogger("atested.approval_store")

APPROVAL_STORE_VERSION = "0.1"
DEFAULT_APPROVAL_STORE_FILENAMES = (
    "approval-store.json",
    "approval-store.jsonl",
    "approval-store",
)


def _canonical_json(obj) -> str:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    )


def _normalize_artifact_identity(value: str) -> str:
    return str(value or "").strip().casefold()


def approval_store_hash(store: Optional["ApprovalStore"] = None) -> str:
    """Hash the active approval-store snapshot used for a decision."""
    approvals = [] if store is None else store.all_approvals()
    normalized = {
        "approval_store_version": APPROVAL_STORE_VERSION,
        "active_approvals": sorted(
            approvals,
            key=lambda row: _canonical_json(row),
        ),
    }
    return "sha256:" + hashlib.sha256(_canonical_json(normalized).encode("utf-8")).hexdigest()


def _verify_event_signature(event: dict, public_key) -> bool:
    """Verify Ed25519 signature on an approval/revocation event.

    Returns True if valid, False otherwise.
    """
    sig_b64 = event.get("signature")
    if not sig_b64 or not isinstance(sig_b64, str):
        return False
    try:
        import base64
        from event_model import canonical_json
        from cryptography.exceptions import InvalidSignature

        # Reconstruct signing preimage: record_hash, signature, signing_key_id → None
        copy = dict(event)
        copy["record_hash"] = None
        copy["signature"] = None
        copy["signing_key_id"] = None
        preimage = canonical_json(copy).encode("utf-8")

        # Decode signature (URL-safe base64, no padding)
        padding = "=" * ((4 - len(sig_b64) % 4) % 4)
        sig_bytes = base64.urlsafe_b64decode(sig_b64 + padding)

        public_key.verify(sig_bytes, preimage)
        return True
    except (InvalidSignature, Exception):
        return False


class ApprovalStore:
    """In-memory approval store derived from approval/revocation events.

    Each approval is keyed by the 4-field scope tuple:
    (artifact_identity, governed_family, deployment_context, policy_version).

    The value is the full approval record including approving_operator.

    When require_signatures=True and a public_key is provided, events must
    carry valid Ed25519 signatures to be ingested.
    """

    def __init__(self, *, require_signatures: bool = False, public_key=None):
        self._approvals: dict[tuple, dict] = {}
        self._pattern_approvals: list[dict] = []
        self._require_signatures = require_signatures
        self._public_key = public_key
        self._rejected_count = 0

    def ingest_approval(self, event: dict) -> bool:
        """Ingest an opaque_artifact_approval event.

        Returns True if accepted, False if rejected due to signature failure.
        """
        if self._require_signatures and self._public_key is not None:
            if not _verify_event_signature(event, self._public_key):
                self._rejected_count += 1
                logger.warning(
                    "Rejected unsigned/invalid-signature approval: %s",
                    event.get("event_id", "?"),
                )
                return False

        record = {
            "artifact_identity": event["artifact_identity"],
            "approving_operator": event["approving_operator"],
            "governed_family": event["governed_family"],
            "deployment_context": event["deployment_context"],
            "policy_version": event["policy_version"],
            "event_id": event.get("event_id"),
            "timestamp_utc": event.get("timestamp_utc"),
        }
        if isinstance(event.get("match"), dict):
            record["match"] = event["match"]
            self._pattern_approvals.append(record)
            return True

        key = self._scope_key(event)
        self._approvals[key] = record
        return True

    def ingest_revocation(self, event: dict) -> bool:
        """Ingest an opaque_artifact_revocation event, removing the approval.

        Returns True if accepted, False if rejected due to signature failure.
        """
        if self._require_signatures and self._public_key is not None:
            if not _verify_event_signature(event, self._public_key):
                self._rejected_count += 1
                logger.warning(
                    "Rejected unsigned/invalid-signature revocation: %s",
                    event.get("event_id", "?"),
                )
                return False

        key = self._scope_key(event)
        self._approvals.pop(key, None)
        self._pattern_approvals = [
            approval for approval in self._pattern_approvals
            if not self._event_scope_matches_approval(event, approval)
        ]
        return True

    @property
    def rejected_count(self) -> int:
        """Number of events rejected due to signature verification failure."""
        return self._rejected_count

    def lookup(
        self,
        artifact_identity: str,
        governed_family: str,
        deployment_context: str,
        policy_version: str,
    ) -> Optional[dict]:
        """Look up whether a valid approval exists for the given scope.

        Returns the approval record if all 5 scope fields match
        (artifact_identity + governed_family + deployment_context +
        policy_version conjunctively, with approving_operator stored
        in the record). Returns None if no matching approval exists.
        """
        key = (
            _normalize_artifact_identity(artifact_identity),
            governed_family,
            deployment_context,
            policy_version,
        )
        return self._approvals.get(key)

    def lookup_operation(
        self,
        tool_name: str,
        args: Optional[dict],
        targets: list[str],
        governed_family: str,
        deployment_context: str,
        policy_version: str,
        *,
        repo_path: str = "",
    ) -> Optional[dict]:
        """Look up an approval for a concrete tool call.

        This preserves the original exact lookup semantics and adds optional
        pattern entries loaded from a runtime approval-store file. Pattern
        approvals are still scoped before command/path matching is considered.
        """
        exact = self.lookup(tool_name, governed_family, deployment_context, policy_version)
        if exact:
            return exact
        for target in targets:
            if target:
                exact = self.lookup(target, governed_family, deployment_context, policy_version)
                if exact:
                    return exact

        args = args or {}
        for approval in self._pattern_approvals:
            if not self._scope_matches(
                approval, governed_family, deployment_context, policy_version,
            ):
                continue
            if _operation_matches_pattern(
                approval.get("match", {}),
                tool_name,
                args,
                targets,
                repo_path=repo_path,
            ):
                return approval
        return None

    def all_approvals(self) -> list[dict]:
        """Return all current approvals (for testing/inspection)."""
        return list(self._approvals.values()) + list(self._pattern_approvals)

    @staticmethod
    def _scope_matches(
        approval: dict,
        governed_family: str,
        deployment_context: str,
        policy_version: str,
    ) -> bool:
        return (
            approval.get("governed_family") == governed_family
            and approval.get("deployment_context") == deployment_context
            and approval.get("policy_version") == policy_version
        )

    @staticmethod
    def _event_scope_matches_approval(event: dict, approval: dict) -> bool:
        return (
            _normalize_artifact_identity(event.get("artifact_identity", ""))
            == _normalize_artifact_identity(approval.get("artifact_identity", ""))
            and event.get("governed_family") == approval.get("governed_family")
            and event.get("deployment_context") == approval.get("deployment_context")
            and event.get("policy_version") == approval.get("policy_version")
        )

    def _scope_key(self, event: dict) -> tuple:
        return (
            _normalize_artifact_identity(event["artifact_identity"]),
            event["governed_family"],
            event["deployment_context"],
            event["policy_version"],
        )


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalize_tool_names(value: Any) -> set[str]:
    return {str(item).strip().casefold() for item in _as_list(value) if str(item).strip()}


def _split_shell_chain(command: str) -> list[str]:
    """Split simple shell command chains without splitting quoted separators."""
    segments: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(command):
        c = command[i]
        if c == "'" and not in_double:
            in_single = not in_single
        elif c == '"' and not in_single:
            in_double = not in_double
        elif c == "\\" and not in_single and i + 1 < len(command):
            current.append(c)
            i += 1
            current.append(command[i])
            i += 1
            continue
        if not in_single and not in_double:
            if command[i:i + 2] in ("&&", "||"):
                segment = "".join(current).strip()
                if segment:
                    segments.append(segment)
                current = []
                i += 2
                continue
            if c == ";":
                segment = "".join(current).strip()
                if segment:
                    segments.append(segment)
                current = []
                i += 1
                continue
        current.append(c)
        i += 1
    segment = "".join(current).strip()
    if segment:
        segments.append(segment)
    return segments or [command.strip()]


def _target_within_roots(target: str, roots: list[str], *, repo_path: str) -> bool:
    target_s = str(target or "").strip()
    if not target_s:
        return False
    expanded_roots = []
    for root in roots:
        root_s = str(root or "").strip()
        if root_s == "__GOV_CANONICAL_REPO_PATH__":
            root_s = repo_path
        if root_s:
            expanded_roots.append(str(Path(root_s).expanduser().resolve()))
    try:
        target_resolved = str(Path(target_s).expanduser().resolve())
    except OSError:
        target_resolved = target_s
    return any(
        target_resolved == root or target_resolved.startswith(root.rstrip("/") + "/")
        for root in expanded_roots
    )


def _cd_segment_allowed(segment: str, *, repo_path: str) -> bool:
    if not repo_path:
        return False
    parts = segment.split()
    if len(parts) != 2 or parts[0] != "cd":
        return False
    return _target_within_roots(parts[1], ["__GOV_CANONICAL_REPO_PATH__"], repo_path=repo_path)


def _command_matches(command: str, patterns: list[str], *, repo_path: str) -> bool:
    if not command or not patterns:
        return False
    matched = False
    for segment in _split_shell_chain(command):
        if _cd_segment_allowed(segment, repo_path=repo_path):
            continue
        if any(fnmatch.fnmatchcase(segment, pattern) for pattern in patterns):
            matched = True
            continue
        return False
    return matched


def _operation_matches_pattern(
    match: dict,
    tool_name: str,
    args: dict,
    targets: list[str],
    *,
    repo_path: str = "",
) -> bool:
    tool_names = _normalize_tool_names(match.get("tool_names") or match.get("tool_name"))
    if tool_names and str(tool_name).strip().casefold() not in tool_names:
        return False

    command_patterns = [str(p) for p in _as_list(match.get("command_patterns")) if str(p).strip()]
    if command_patterns:
        if not _command_matches(str(args.get("command", "")), command_patterns, repo_path=repo_path):
            return False

    target_roots = [str(p) for p in _as_list(match.get("target_roots")) if str(p).strip()]
    if target_roots:
        if not targets:
            return False
        if match.get("require_all_targets_within_roots", True):
            return all(_target_within_roots(t, target_roots, repo_path=repo_path) for t in targets)
        return any(_target_within_roots(t, target_roots, repo_path=repo_path) for t in targets)

    return bool(tool_names or command_patterns)


def load_approval_store_from_events(
    events: list[dict],
    *,
    require_signatures: bool = False,
    public_key=None,
) -> ApprovalStore:
    """Build an ApprovalStore from a list of approval/revocation events.

    Events are processed in order. Later revocations override earlier
    approvals for the same scope.
    """
    store = ApprovalStore(
        require_signatures=require_signatures, public_key=public_key,
    )
    for event in events:
        event_type = event.get("event_type")
        if event_type == "opaque_artifact_approval":
            store.ingest_approval(event)
        elif event_type == "opaque_artifact_revocation":
            store.ingest_revocation(event)
    return store


def _iter_sidecar_events(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    payload = json.loads(text)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        approvals = payload.get("approvals")
        if isinstance(approvals, list):
            return approvals
        if payload.get("event_type") == "opaque_artifact_approval":
            return [payload]
    raise ValueError(f"unsupported approval store format: {path}")


def load_approval_store_from_file(path: Union[str, Path], store: Optional[ApprovalStore] = None) -> ApprovalStore:
    """Load file-backed approvals from ``approval-store*.`` sidecars."""
    approval_store = store or ApprovalStore()
    for event in _iter_sidecar_events(Path(path)):
        if event.get("event_type", "opaque_artifact_approval") != "opaque_artifact_approval":
            continue
        approval_store.ingest_approval({
            "event_type": "opaque_artifact_approval",
            **event,
        })
    return approval_store


def default_approval_store_paths(chain_path: Union[str, Path]) -> list[Path]:
    chain = Path(chain_path)
    runtime = chain.parent.parent if chain.parent.name == "LOGS" else chain.parent
    return [runtime / name for name in DEFAULT_APPROVAL_STORE_FILENAMES]


def load_approval_store_from_runtime(
    chain_path: Union[str, Path],
    *,
    require_signatures: bool = False,
    public_key=None,
) -> ApprovalStore:
    """Load approvals from the chain plus runtime approval-store sidecars."""
    path = Path(chain_path)
    if path.exists():
        store = load_approval_store_from_chain(
            str(path), require_signatures=require_signatures, public_key=public_key,
        )
    else:
        store = ApprovalStore(require_signatures=require_signatures, public_key=public_key)
    for sidecar in default_approval_store_paths(path):
        if sidecar.exists():
            load_approval_store_from_file(sidecar, store)
    return store


def load_approval_store_from_chain(
    chain_path: str,
    *,
    require_signatures: bool = False,
    public_key=None,
) -> ApprovalStore:
    """Build an ApprovalStore from a JSONL decision chain file.

    Scans the chain for approval and revocation events and builds
    the derived index.
    """
    events = []
    with open(chain_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("event_type") in ("opaque_artifact_approval", "opaque_artifact_revocation"):
                events.append(rec)
    return load_approval_store_from_events(
        events, require_signatures=require_signatures, public_key=public_key,
    )
