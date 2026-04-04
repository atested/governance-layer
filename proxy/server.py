#!/usr/bin/env python3
"""
server.py — Atested API governance proxy.

An HTTP proxy that sits between an AI agent and its model provider (Anthropic).
Intercepts tool_use blocks from streaming and non-streaming responses,
classifies each operation by evidence inference, evaluates policy, records
decisions in the governance chain, and allows or denies before execution.

Usage:
    ANTHROPIC_API_KEY=sk-... python -m proxy.server [--port 8080]

Agent configuration:
    ANTHROPIC_BASE_URL=http://localhost:8080/anthropic

Architecture:
    Agent → Proxy → Anthropic API
    Proxy intercepts model responses containing tool_use blocks.
    ALLOW: pass tool_use through to agent.
    DENY: replace tool_use with denial text, agent never sees tool call.
"""

import argparse
import asyncio
import json
import logging
import os
import platform
import sys
import time as _time_mod
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any, Optional

import httpx

# Add scripts to path for classifier, policy_eval, etc.
REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from classifier import classify
from policy_eval_v2 import evaluate, load_policy_rules, _compute_record_hash
from approval_store import ApprovalStore, load_approval_store_from_chain

# Storage contract for chain path
sys.path.insert(0, str(REPO / "mcp"))
from storage_contract import runtime_root

logger = logging.getLogger("atested.proxy")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_PORT = 8080
DEFAULT_HOST = "127.0.0.1"
ANTHROPIC_API_BASE = "https://api.anthropic.com"

# ---------------------------------------------------------------------------
# Chain recorder (thread-safe, append-only JSONL)
# ---------------------------------------------------------------------------


class ChainRecorder:
    """Appends v2 decision records to the governance chain file.

    Uses the same cross-process mkdir lock as mcp/server.py and
    dashboard/server.py to prevent concurrent writers from reading
    the same prev_record_hash (D-024 / D-026 fix).
    """

    def __init__(self, chain_path: Path):
        self._chain_path = chain_path
        self._lock = threading.Lock()

    def append_atomic(self, record: dict) -> None:
        """Atomically read prev_record_hash, set it, recompute hash, and append.

        This ensures no two processes can read the same head hash.
        """
        import stat as _stat
        logger.info("Chain append: tool=%s decision=%s chain=%s",
                     record.get("original_tool", "?"),
                     record.get("policy_decision", "?"),
                     self._chain_path)
        self._chain_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            lockdir = self._acquire_file_lock()
            try:
                record["prev_record_hash"] = self._last_hash()
                record["record_hash"] = _compute_record_hash(record)
                line = json.dumps(
                    record, sort_keys=True, separators=(",", ":"),
                    ensure_ascii=False,
                )
                fd = os.open(
                    str(self._chain_path),
                    os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                    _stat.S_IRUSR | _stat.S_IWUSR,
                )
                try:
                    os.write(fd, (line + "\n").encode("utf-8"))
                finally:
                    os.close(fd)
            finally:
                self._release_file_lock(lockdir)

    def _last_hash(self) -> Optional[str]:
        """Read the record_hash from the last line. Must be called under lock."""
        if not self._chain_path.exists():
            return None
        try:
            last_line = ""
            with open(self._chain_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    stripped = line.strip()
                    if stripped:
                        last_line = stripped
            if not last_line:
                return None
            return json.loads(last_line).get("record_hash")
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def _acquire_file_lock(self) -> Path:
        """Acquire cross-process mkdir lock (same protocol as mcp/server.py)."""
        lockdir = Path(str(self._chain_path) + ".lock.d")
        lock_meta = lockdir / "lock_owner.json"
        max_wait = 50

        def _try_acquire():
            try:
                lockdir.mkdir(exist_ok=False)
                try:
                    meta = json.dumps({"pid": os.getpid(), "ts": _time_mod.time()})
                    lock_meta.write_text(meta, encoding="utf-8")
                except OSError:
                    pass
                return True
            except FileExistsError:
                return False

        def _holder_is_alive():
            try:
                data = json.loads(lock_meta.read_text(encoding="utf-8"))
                pid = data.get("pid")
                if not isinstance(pid, int):
                    return True
                os.kill(pid, 0)
                return True
            except (OSError, json.JSONDecodeError, KeyError):
                return False

        waited = 0
        while True:
            if _try_acquire():
                return lockdir
            waited += 1
            if waited >= max_wait:
                if not _holder_is_alive():
                    try:
                        lock_meta.unlink(missing_ok=True)
                        lockdir.rmdir()
                    except OSError:
                        pass
                    if _try_acquire():
                        return lockdir
                raise TimeoutError(f"timed out waiting for chain lock ({lockdir})")
            _time_mod.sleep(0.1)

    @staticmethod
    def _release_file_lock(lockdir: Path) -> None:
        try:
            (lockdir / "lock_owner.json").unlink(missing_ok=True)
            lockdir.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Anthropic response parser
# ---------------------------------------------------------------------------


def extract_tool_use_blocks(content: list) -> list[dict]:
    """Extract tool_use blocks from a Messages API response content array."""
    return [b for b in content if isinstance(b, dict) and b.get("type") == "tool_use"]


def replace_tool_use_with_denial(
    content: list, tool_use_id: str, tool_name: str, reason: str, matched_rule: str,
) -> list:
    """Replace a tool_use block with a text block containing the denial message."""
    result = []
    for block in content:
        if (
            isinstance(block, dict)
            and block.get("type") == "tool_use"
            and block.get("id") == tool_use_id
        ):
            result.append({
                "type": "text",
                "text": (
                    f"[Governance] Operation denied: {tool_name}\n"
                    f"Reason: {reason}\n"
                    f"Rule: {matched_rule}\n"
                    f"The operation was classified and denied by policy before execution."
                ),
            })
        else:
            result.append(block)
    return result


# ---------------------------------------------------------------------------
# Governance mediation (decision-only, no execution)
# ---------------------------------------------------------------------------


def _load_approval_store(chain_path: Path) -> ApprovalStore:
    """Load the approval store from the governance chain."""
    if chain_path.exists():
        return load_approval_store_from_chain(str(chain_path))
    return ApprovalStore()


def _governed_family() -> str:
    return str(os.environ.get("GOV_GOVERNED_FAMILY", "mcp_tools_v1")).strip() or "mcp_tools_v1"


def _deployment_context() -> str:
    return str(os.environ.get("GOV_DEPLOYMENT_CONTEXT", "default")).strip() or "default"


def _policy_version() -> str:
    return str(os.environ.get("GOV_POLICY_VERSION", "baseline-v1")).strip() or "baseline-v1"


def _check_approval(
    approval_store: ApprovalStore,
    tool_name: str,
    targets: list[str],
) -> Optional[dict]:
    """Check if an operation is approved by tool name or target path.

    Tries the tool name first, then each target path. Returns the approval
    record if found, None otherwise.
    """
    family = _governed_family()
    context = _deployment_context()
    version = _policy_version()

    # Check tool name as artifact_identity
    approval = approval_store.lookup(tool_name, family, context, version)
    if approval:
        return approval

    # Check each target as artifact_identity
    for target in targets:
        if target:
            approval = approval_store.lookup(target, family, context, version)
            if approval:
                return approval

    return None


def mediate_decision(
    tool_name: str,
    args: dict,
    *,
    policy: dict,
    chain_recorder: Optional[ChainRecorder] = None,
    approval_store: Optional[ApprovalStore] = None,
    session_id: str = "",
    user_identity: str = "",
) -> dict:
    """Classify, evaluate, and record a governance decision.

    Returns the decision record. Does NOT execute the tool — in the API proxy
    model, the agent executes its own tools. The proxy only decides.

    If approval_store is provided and the policy decision is DENY, checks
    whether the operation has been approved. Approved operations are overridden
    to ALLOW with resolution "approved_lookup".
    """
    classification = classify(tool_name, args)

    # Build the record with a placeholder prev_record_hash — the atomic
    # append will set the real value inside the cross-process lock.
    record = evaluate(
        classification,
        policy=policy,
        prev_record_hash=None,
        user_identity=user_identity,
        session_id=session_id,
    )

    # Check approval store for denied operations
    if record["policy_decision"] == "DENY" and approval_store is not None:
        targets = classification.get("targets", [])
        approval = _check_approval(approval_store, tool_name, targets)
        if approval:
            logger.info(
                "Approval override: %s approved by %s (event %s)",
                tool_name,
                approval.get("approving_operator", "?"),
                approval.get("event_id", "?"),
            )
            record["policy_decision"] = "ALLOW"
            record["policy_reasons"] = []
            record["matched_rule"] = "approved_lookup"
            record["approval_event_id"] = approval.get("event_id")
            record["record_hash"] = _compute_record_hash(record)

    if chain_recorder is not None:
        chain_recorder.append_atomic(record)

    return record


# ---------------------------------------------------------------------------
# SSE streaming parser
# ---------------------------------------------------------------------------


class StreamingToolCollector:
    """Collects tool_use blocks from an SSE stream and governs them.

    The Anthropic streaming API sends events like:
        event: content_block_start
        data: {"type":"content_block_start","index":0,"content_block":{"type":"tool_use","id":"...","name":"...","input":{}}}

        event: content_block_delta
        data: {"type":"content_block_delta","index":0,"delta":{"type":"input_json_delta","partial_json":"..."}}

        event: content_block_stop
        data: {"type":"content_block_stop","index":0}

    This collector buffers tool_use blocks. When a block is complete
    (content_block_stop), it governs it and decides whether to pass or deny.
    """

    def __init__(self, policy: dict, chain_recorder: Optional[ChainRecorder],
                 session_id: str = "", user_identity: str = "",
                 approval_store: Optional[ApprovalStore] = None):
        self._policy = policy
        self._chain_recorder = chain_recorder
        self._session_id = session_id
        self._user_identity = user_identity
        self._approval_store = approval_store

        # Active tool_use blocks being collected, keyed by index
        self._active_blocks: dict[int, dict] = {}
        # JSON fragments for each block index
        self._json_fragments: dict[int, list[str]] = {}
        # Governance decisions, keyed by block index
        self._decisions: dict[int, dict] = {}
        # Denied block indices
        self._denied_indices: set[int] = set()
        # Replacement events for denied blocks
        self._replacements: dict[int, list[bytes]] = {}

    def process_event(self, event_type: str, data: dict) -> Optional[str]:
        """Process an SSE event. Returns action: 'pass', 'buffer', or 'replace'.

        'pass': Forward this event to the client as-is.
        'buffer': Hold this event (part of a tool_use being collected).
        'replace': This event should be replaced with denial content.
        """
        msg_type = data.get("type", "")

        if msg_type == "content_block_start":
            block = data.get("content_block", {})
            if block.get("type") == "tool_use":
                idx = data.get("index", 0)
                self._active_blocks[idx] = {
                    "type": "tool_use",
                    "id": block.get("id", ""),
                    "name": block.get("name", ""),
                    "input": {},
                }
                self._json_fragments[idx] = []
                return "buffer"
            return "pass"

        if msg_type == "content_block_delta":
            idx = data.get("index", 0)
            if idx in self._active_blocks:
                delta = data.get("delta", {})
                if delta.get("type") == "input_json_delta":
                    self._json_fragments.setdefault(idx, []).append(
                        delta.get("partial_json", "")
                    )
                return "buffer"
            return "pass"

        if msg_type == "content_block_stop":
            idx = data.get("index", 0)
            if idx in self._active_blocks:
                block = self._active_blocks.pop(idx)
                fragments = self._json_fragments.pop(idx, [])

                # Reconstruct the full input JSON
                full_json = "".join(fragments)
                if full_json:
                    try:
                        block["input"] = json.loads(full_json)
                    except json.JSONDecodeError:
                        block["input"] = {"_raw": full_json}

                # Govern the complete tool_use block
                record = mediate_decision(
                    block["name"],
                    block.get("input", {}),
                    policy=self._policy,
                    chain_recorder=self._chain_recorder,
                    approval_store=self._approval_store,
                    session_id=self._session_id,
                    user_identity=self._user_identity,
                )
                self._decisions[idx] = record

                if record["policy_decision"] == "DENY":
                    self._denied_indices.add(idx)
                    # Build replacement SSE events
                    reasons = record.get("policy_reasons", [])
                    reason_text = reasons[0].get("detail", "policy denied") if reasons else "policy denied"
                    self._replacements[idx] = _build_denial_sse_events(
                        idx, block["id"], block["name"],
                        reason_text, record.get("matched_rule", ""),
                    )
                    return "replace"
                else:
                    return "pass"
            return "pass"

        return "pass"

    def get_buffered_events(self, idx: int) -> list[bytes]:
        """Get the original buffered SSE events for an allowed tool block."""
        # Not used in the current flow — allowed blocks are reconstructed
        return []

    def get_replacement_events(self, idx: int) -> list[bytes]:
        """Get replacement SSE events for a denied tool block."""
        return self._replacements.get(idx, [])

    def is_denied(self, idx: int) -> bool:
        return idx in self._denied_indices

    def get_decision(self, idx: int) -> Optional[dict]:
        return self._decisions.get(idx)


def _build_denial_sse_events(
    index: int, tool_use_id: str, tool_name: str,
    reason: str, matched_rule: str,
) -> list[bytes]:
    """Build SSE events that replace a denied tool_use with a text block."""
    denial_text = (
        f"[Governance] Operation denied: {tool_name}\n"
        f"Reason: {reason}\n"
        f"Rule: {matched_rule}\n"
        f"The operation was classified and denied by policy before execution."
    )
    events = []

    # content_block_start with text type instead of tool_use
    start_data = json.dumps({
        "type": "content_block_start",
        "index": index,
        "content_block": {"type": "text", "text": ""},
    })
    events.append(f"event: content_block_start\ndata: {start_data}\n\n".encode())

    # content_block_delta with the denial text
    delta_data = json.dumps({
        "type": "content_block_delta",
        "index": index,
        "delta": {"type": "text_delta", "text": denial_text},
    })
    events.append(f"event: content_block_delta\ndata: {delta_data}\n\n".encode())

    # content_block_stop
    stop_data = json.dumps({
        "type": "content_block_stop",
        "index": index,
    })
    events.append(f"event: content_block_stop\ndata: {stop_data}\n\n".encode())

    return events


# ---------------------------------------------------------------------------
# HTTP proxy handler
# ---------------------------------------------------------------------------


class GovernanceProxy:
    """HTTP proxy that governs Anthropic API tool calls."""

    def __init__(
        self,
        *,
        upstream_base: str = ANTHROPIC_API_BASE,
        policy: Optional[dict] = None,
        chain_recorder: Optional[ChainRecorder] = None,
        chain_path: Optional[Path] = None,
        session_id: str = "",
        user_identity: str = "",
    ):
        self._upstream_base = upstream_base.rstrip("/")
        self._policy = policy or self._load_default_policy()
        self._chain_recorder = chain_recorder
        self._chain_path = chain_path
        self._session_id = session_id
        self._user_identity = user_identity
        self._approval_store: Optional[ApprovalStore] = None
        self._approval_store_mtime: float = 0.0
        self._approval_lock = threading.Lock()

    def _get_approval_store(self) -> Optional[ApprovalStore]:
        """Return a cached approval store, reloading when the chain file changes."""
        if self._chain_path is None:
            return None
        with self._approval_lock:
            try:
                mtime = self._chain_path.stat().st_mtime if self._chain_path.exists() else 0.0
            except OSError:
                return self._approval_store
            if mtime != self._approval_store_mtime or self._approval_store is None:
                self._approval_store = _load_approval_store(self._chain_path)
                self._approval_store_mtime = mtime
                logger.info("Approval store reloaded: %d active approvals",
                            len(self._approval_store.all_approvals()))
        return self._approval_store

    @staticmethod
    def _load_default_policy() -> dict:
        policy = load_policy_rules()
        runtime = runtime_root(REPO)
        policy = dict(policy)
        policy["base_dirs"] = [str(REPO), str(runtime)]
        return policy

    def _prepare_request(self, method: str, path: str, headers: dict,
                         body: bytes) -> tuple[str, dict, bool, bool]:
        """Parse request and determine routing. Returns (url, headers, is_messages, is_streaming)."""
        # Strip query parameters for endpoint detection (SDK may send ?beta=...)
        path_base = path.split("?")[0]
        is_messages = path_base.rstrip("/").endswith("/v1/messages")
        upstream_url = f"{self._upstream_base}{path}"
        forward_headers = {
            k: v for k, v in headers.items()
            if k.lower() not in ("host", "transfer-encoding", "connection")
        }
        is_streaming = False
        if is_messages and body:
            try:
                req_body = json.loads(body)
                is_streaming = req_body.get("stream", False)
            except (json.JSONDecodeError, AttributeError):
                pass
        return upstream_url, forward_headers, is_messages, is_streaming

    async def handle_request(self, method: str, path: str, headers: dict,
                             body: bytes) -> tuple[int, dict, bytes]:
        """Handle a proxied HTTP request (non-streaming or buffered fallback).

        For non-messages endpoints, forwards as-is.
        For messages endpoints, intercepts and governs tool_use blocks.
        For streaming, use handle_streaming_to_writer() instead for real-time output.
        """
        url, fwd_headers, is_messages, is_streaming = self._prepare_request(
            method, path, headers, body
        )

        if is_messages and is_streaming:
            return await self._handle_streaming_buffered(
                url, fwd_headers, body
            )
        else:
            return await self._handle_non_streaming(
                url, method, fwd_headers, body, is_messages
            )

    async def handle_streaming_to_writer(
        self, path: str, headers: dict, body: bytes,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a streaming request, forwarding text events in real time.

        Text blocks are written to the client immediately as they arrive.
        Tool_use blocks are buffered until complete, governed, then flushed
        (ALLOW) or replaced with denial text (DENY).
        """
        url, fwd_headers, is_messages, _ = self._prepare_request(
            "POST", path, headers, body
        )

        collector = StreamingToolCollector(
            self._policy, self._chain_recorder,
            self._session_id, self._user_identity,
            approval_store=self._get_approval_store(),
        )
        buffered_events: dict[int, list[bytes]] = {}
        _tool_use_count = 0

        logger.info("Streaming handler entered for path=%s", path)

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", url, headers=fwd_headers, content=body,
            ) as resp:
                if resp.status_code != 200:
                    content = await resp.aread()
                    writer.write(f"HTTP/1.1 {resp.status_code} Error\r\n".encode())
                    writer.write(b"content-type: application/json\r\n")
                    writer.write(f"content-length: {len(content)}\r\n".encode())
                    writer.write(b"\r\n")
                    writer.write(content)
                    await writer.drain()
                    return

                # Send streaming response headers immediately
                writer.write(b"HTTP/1.1 200 OK\r\n")
                writer.write(b"content-type: text/event-stream\r\n")
                writer.write(b"cache-control: no-cache\r\n")
                writer.write(b"connection: keep-alive\r\n")
                for key in ("x-request-id", "request-id"):
                    val = resp.headers.get(key)
                    if val:
                        writer.write(f"{key}: {val}\r\n".encode())
                writer.write(b"\r\n")
                await writer.drain()

                current_event_type = ""
                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()
                    if not line:
                        continue

                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                        continue

                    if not line.startswith("data:"):
                        continue

                    data_str = line[5:].strip()

                    if data_str == "[DONE]":
                        logger.info("Stream complete: %d tool_use blocks mediated", _tool_use_count)
                        writer.write(b"event: done\ndata: [DONE]\n\n")
                        await writer.drain()
                        continue

                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        chunk = f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                        writer.write(chunk)
                        await writer.drain()
                        continue

                    action = collector.process_event(current_event_type, data)

                    if action == "buffer":
                        idx = data.get("index", 0)
                        msg_type = data.get("type", "")
                        if msg_type == "content_block_start":
                            _tool_use_count += 1
                            block_name = data.get("content_block", {}).get("name", "?")
                            logger.info("Tool use #%d detected: %s (idx=%d)", _tool_use_count, block_name, idx)
                        buffered_events.setdefault(idx, []).append(
                            f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                        )

                    elif action == "replace":
                        idx = data.get("index", 0)
                        decision = collector.get_decision(idx)
                        logger.info("Tool DENIED (idx=%d): %s", idx, decision.get("matched_rule", "") if decision else "?")
                        for event_bytes in collector.get_replacement_events(idx):
                            writer.write(event_bytes)
                        await writer.drain()
                        buffered_events.pop(idx, None)

                    elif action == "pass":
                        msg_type = data.get("type", "")
                        idx = data.get("index", 0)

                        if msg_type == "content_block_stop" and idx in buffered_events:
                            decision = collector.get_decision(idx)
                            if decision:
                                logger.info("Tool ALLOWED (idx=%d): %s → %s",
                                            idx, decision.get("original_tool", "?"),
                                            decision.get("policy_decision", "?"))
                            # Tool_use ALLOWED — flush buffered events
                            for event_bytes in buffered_events.pop(idx):
                                writer.write(event_bytes)
                            writer.write(
                                f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                            )
                            await writer.drain()
                        else:
                            # Text or other non-tool event — stream immediately
                            writer.write(
                                f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                            )
                            await writer.drain()

    async def _handle_non_streaming(
        self, url: str, method: str, headers: dict, body: bytes,
        is_messages: bool,
    ) -> tuple[int, dict, bytes]:
        """Forward a non-streaming request and govern the response."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.request(
                method, url, headers=headers, content=body,
            )

        resp_headers = dict(resp.headers)
        resp_body = resp.content

        logger.info("Non-streaming response: status=%d is_messages=%s", resp.status_code, is_messages)
        if not is_messages or resp.status_code != 200:
            return resp.status_code, resp_headers, resp_body

        # Parse the response and govern tool_use blocks
        try:
            data = json.loads(resp_body)
        except json.JSONDecodeError:
            return resp.status_code, resp_headers, resp_body

        content = data.get("content", [])
        tool_blocks = extract_tool_use_blocks(content)

        if not tool_blocks:
            return resp.status_code, resp_headers, resp_body

        # Govern each tool_use block
        modified = False
        approval_store = self._get_approval_store()
        for block in tool_blocks:
            record = mediate_decision(
                block["name"],
                block.get("input", {}),
                policy=self._policy,
                chain_recorder=self._chain_recorder,
                approval_store=approval_store,
                session_id=self._session_id,
                user_identity=self._user_identity,
            )

            if record["policy_decision"] == "DENY":
                reasons = record.get("policy_reasons", [])
                reason_text = reasons[0].get("detail", "policy denied") if reasons else "policy denied"
                data["content"] = replace_tool_use_with_denial(
                    data["content"],
                    block["id"],
                    block["name"],
                    reason_text,
                    record.get("matched_rule", ""),
                )
                modified = True

        if modified:
            # If we removed tool_use blocks, update stop_reason
            remaining_tool_use = [
                b for b in data["content"]
                if isinstance(b, dict) and b.get("type") == "tool_use"
            ]
            if not remaining_tool_use and data.get("stop_reason") == "tool_use":
                data["stop_reason"] = "end_turn"
            resp_body = json.dumps(data).encode()
            resp_headers["content-length"] = str(len(resp_body))

        return resp.status_code, resp_headers, resp_body

    async def _handle_streaming_buffered(
        self, url: str, headers: dict, body: bytes,
    ) -> tuple[int, dict, bytes]:
        """Handle a streaming request with full buffering (fallback for tests).

        Returns the complete response as bytes. For real-time streaming,
        use handle_streaming_to_writer() instead.
        """
        collector = StreamingToolCollector(
            self._policy, self._chain_recorder,
            self._session_id, self._user_identity,
            approval_store=self._get_approval_store(),
        )

        output_chunks: list[bytes] = []
        # Track which block indices are tool_use blocks being buffered
        buffered_events: dict[int, list[bytes]] = {}
        resp_status = 200
        resp_headers: dict = {}

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST", url, headers=headers, content=body,
            ) as resp:
                resp_status = resp.status_code
                resp_headers = dict(resp.headers)

                if resp_status != 200:
                    content = await resp.aread()
                    return resp_status, resp_headers, content

                current_event_type = ""
                async for raw_line in resp.aiter_lines():
                    line = raw_line.strip()

                    if not line:
                        # Empty line = end of SSE event
                        continue

                    if line.startswith("event:"):
                        current_event_type = line[6:].strip()
                        continue

                    if line.startswith("data:"):
                        data_str = line[5:].strip()

                        if data_str == "[DONE]":
                            output_chunks.append(b"event: done\ndata: [DONE]\n\n")
                            continue

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            # Forward unparseable data as-is
                            output_chunks.append(
                                f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                            )
                            continue

                        action = collector.process_event(current_event_type, data)

                        if action == "buffer":
                            idx = data.get("index", 0)
                            buffered_events.setdefault(idx, []).append(
                                f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                            )

                        elif action == "replace":
                            idx = data.get("index", 0)
                            # Emit denial replacement events
                            for event_bytes in collector.get_replacement_events(idx):
                                output_chunks.append(event_bytes)
                            # Clear buffered events for this block
                            buffered_events.pop(idx, None)

                        elif action == "pass":
                            msg_type = data.get("type", "")
                            idx = data.get("index", 0)

                            if msg_type == "content_block_stop" and idx in buffered_events:
                                # This was a tool_use that was ALLOWED — flush buffered events
                                for event_bytes in buffered_events.pop(idx):
                                    output_chunks.append(event_bytes)
                                # Also emit the stop event
                                output_chunks.append(
                                    f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                                )
                            else:
                                output_chunks.append(
                                    f"event: {current_event_type}\ndata: {data_str}\n\n".encode()
                                )

        # Build the full SSE response
        full_body = b"".join(output_chunks)

        # For streaming, set appropriate headers
        stream_headers = {
            "content-type": "text/event-stream",
            "cache-control": "no-cache",
            "connection": "keep-alive",
        }
        # Preserve auth-related headers from upstream
        for key in ("x-request-id", "request-id"):
            if key in resp_headers:
                stream_headers[key] = resp_headers[key]

        return resp_status, stream_headers, full_body


# ---------------------------------------------------------------------------
# ASGI-like HTTP server using asyncio
# ---------------------------------------------------------------------------


class ProxyServer:
    """Minimal async HTTP server wrapping GovernanceProxy."""

    def __init__(self, proxy: GovernanceProxy, host: str, port: int):
        self._proxy = proxy
        self._host = host
        self._port = port

    async def _handle_client(self, reader: asyncio.StreamReader,
                              writer: asyncio.StreamWriter):
        try:
            # Read the request line
            request_line = await asyncio.wait_for(
                reader.readline(), timeout=30.0
            )
            if not request_line:
                writer.close()
                return

            parts = request_line.decode("utf-8", errors="replace").strip().split(" ")
            if len(parts) < 3:
                writer.close()
                return

            method = parts[0]
            raw_path = parts[1]

            # Strip the /anthropic prefix if present
            if raw_path.startswith("/anthropic"):
                path = raw_path[len("/anthropic"):]
                if not path:
                    path = "/"
            else:
                path = raw_path

            # Read headers
            headers: dict[str, str] = {}
            while True:
                header_line = await asyncio.wait_for(
                    reader.readline(), timeout=10.0
                )
                line_str = header_line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    break
                if ":" in line_str:
                    key, value = line_str.split(":", 1)
                    headers[key.strip().lower()] = value.strip()

            # Read body if content-length present or chunked transfer encoding
            body = b""
            content_length = int(headers.get("content-length", "0"))
            if content_length > 0:
                body = await asyncio.wait_for(
                    reader.readexactly(content_length), timeout=60.0
                )
            elif headers.get("transfer-encoding", "").lower() == "chunked":
                # Read chunked transfer encoding
                chunks = []
                while True:
                    size_line = await asyncio.wait_for(
                        reader.readline(), timeout=30.0
                    )
                    chunk_size = int(size_line.strip(), 16)
                    if chunk_size == 0:
                        await reader.readline()  # trailing CRLF
                        break
                    chunk_data = await asyncio.wait_for(
                        reader.readexactly(chunk_size), timeout=30.0
                    )
                    await reader.readline()  # trailing CRLF after chunk
                    chunks.append(chunk_data)
                body = b"".join(chunks)

            # Restore original-case headers for upstream
            forward_headers = {}
            for k, v in headers.items():
                if k == "x-api-key":
                    forward_headers["x-api-key"] = v
                elif k == "anthropic-version":
                    forward_headers["anthropic-version"] = v
                elif k == "anthropic-beta":
                    forward_headers["anthropic-beta"] = v
                elif k == "content-type":
                    forward_headers["content-type"] = v
                elif k == "authorization":
                    forward_headers["authorization"] = v
                elif k == "accept":
                    forward_headers["accept"] = v

            # Check if this is a streaming messages request
            # Strip query parameters for endpoint detection (SDK may send ?beta=...)
            is_streaming = False
            path_base = path.split("?")[0]
            is_messages = path_base.rstrip("/").endswith("/v1/messages")
            if is_messages and body:
                try:
                    is_streaming = json.loads(body).get("stream", False)
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.warning("Failed to parse request body for streaming detection: %s (body_len=%d)", e, len(body))

            logger.info("Request: %s %s messages=%s streaming=%s body_len=%d",
                        method, path[:60], is_messages, is_streaming, len(body))

            if is_streaming:
                # Stream directly to the client writer — text arrives in real time
                await self._proxy.handle_streaming_to_writer(
                    path, forward_headers, body, writer
                )
            else:
                # Non-streaming: buffer full response then send
                status, resp_headers, resp_body = await self._proxy.handle_request(
                    method, path, forward_headers, body
                )
                status_text = HTTPStatus(status).phrase if status in HTTPStatus._value2member_map_ else "OK"
                writer.write(f"HTTP/1.1 {status} {status_text}\r\n".encode())
                for k, v in resp_headers.items():
                    if k.lower() not in ("transfer-encoding",):
                        writer.write(f"{k}: {v}\r\n".encode())
                if "content-length" not in {k.lower() for k in resp_headers}:
                    writer.write(f"content-length: {len(resp_body)}\r\n".encode())
                writer.write(b"\r\n")
                writer.write(resp_body)
                await writer.drain()

        except (asyncio.TimeoutError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as exc:
            logger.error("Request handling error: %s", exc, exc_info=True)
            try:
                err_body = json.dumps({"error": str(exc)}).encode()
                writer.write(b"HTTP/1.1 502 Bad Gateway\r\n")
                writer.write(b"content-type: application/json\r\n")
                writer.write(f"content-length: {len(err_body)}\r\n".encode())
                writer.write(b"\r\n")
                writer.write(err_body)
                await writer.drain()
            except Exception:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def start(self):
        server = await asyncio.start_server(
            self._handle_client, self._host, self._port
        )
        logger.info(
            "Atested governance proxy listening on http://%s:%d",
            self._host, self._port,
        )
        logger.info(
            "Configure your agent: ANTHROPIC_BASE_URL=http://%s:%d/anthropic",
            self._host, self._port,
        )
        async with server:
            await server.serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Atested API governance proxy")
    parser.add_argument("--host", default=DEFAULT_HOST, help="Bind address")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Bind port")
    parser.add_argument("--upstream", default=ANTHROPIC_API_BASE,
                        help="Upstream API base URL")
    parser.add_argument("--user-identity", default="",
                        help="User identity for chain records (default: system hostname)")
    parser.add_argument("--session-id", default="", help="Session ID for chain records")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Verify API key is available
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — proxy will forward requests without adding auth")

    # Setup chain recorder
    runtime = runtime_root(REPO)
    chain_path = runtime / "LOGS" / "decision-chain.jsonl"
    chain_recorder = ChainRecorder(chain_path)

    # Resolve user identity: explicit flag > env var > hostname
    user_identity = (
        args.user_identity
        or os.environ.get("ATESTED_USER_LABEL", "")
        or platform.node()
    )
    logger.info("User identity: %s", user_identity)

    proxy = GovernanceProxy(
        upstream_base=args.upstream,
        chain_recorder=chain_recorder,
        chain_path=chain_path,
        session_id=args.session_id,
        user_identity=user_identity,
    )

    server = ProxyServer(proxy, args.host, args.port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Proxy shutting down")


if __name__ == "__main__":
    main()
