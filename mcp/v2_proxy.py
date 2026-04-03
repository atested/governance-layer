#!/usr/bin/env python3
"""
v2_proxy.py — Governed MCP proxy server (GovMCP v2).

Connects to upstream MCP servers, discovers their tools, and re-exports
them through the governance mediation pipeline. The agent sees the same
tools it would without governance — governance is invisible.

Architecture:
    Agent ──► GovernedProxy ──► [classify → evaluate → record] ──► Upstream MCP

MCP Protocol Resolution:
    The MCP protocol requires servers to declare tools at connection time
    via tools/list. This proxy resolves the "arbitrary tool" problem by:

    1. Connecting to upstream MCP servers as a client (ClientSession)
    2. Calling list_tools() to discover available tools
    3. Registering those tools on our own Server instance unchanged
    4. Intercepting every call_tool() to route through mediation
    5. Forwarding allowed calls to the original upstream server

    The agent sees identical tool names, descriptions, and schemas.
    The governance boundary is structurally invisible.

    This is the "dynamic discovery and registration" approach from the
    implementation plan. It works because:
    - MCP's list_tools returns full JSON schemas for each tool
    - The low-level Server API lets us return those schemas verbatim
    - call_tool receives (name, arguments) which we can classify and forward

Design reference: docs/design/govmcp-v2-design-revised.md
"""

import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

REPO = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from classifier import classify
from policy_eval_v2 import evaluate, load_policy_rules
from mediation import InMemoryChainRecorder, ChainRecorder

# MCP imports — guarded for environments without the SDK
try:
    from mcp.server.lowlevel import Server
    from mcp.client.session import ClientSession
    from mcp import types as mcp_types
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class GovernedProxy:
    """MCP proxy that mediates all tool calls through governance.

    Connects to one or more upstream MCP servers, discovers their tools,
    and re-exports them. Every tool call is classified by evidence,
    evaluated against policy, and recorded to the governance chain
    before execution.

    Usage:
        proxy = GovernedProxy(policy=my_policy)
        await proxy.discover_tools(upstream_session)
        # proxy.server is now an MCP Server with all upstream tools governed
    """

    def __init__(
        self,
        name: str = "governed-proxy",
        *,
        policy: Optional[dict] = None,
        chain_recorder: Optional[Any] = None,
        session_id: str = "",
        user_identity: str = "",
    ):
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not available — install mcp>=1.26.0")

        self._server = Server(name)
        self._upstream_tools: dict = {}           # name → mcp_types.Tool
        self._upstream_session_map: dict = {}     # name → ClientSession
        self._policy = policy
        self._chain = chain_recorder or InMemoryChainRecorder()
        self._session_id = session_id
        self._user_identity = user_identity
        self._setup_handlers()

    def _setup_handlers(self):
        """Register MCP protocol handlers."""

        @self._server.list_tools()
        async def handle_list_tools():
            return list(self._upstream_tools.values())

        @self._server.call_tool()
        async def handle_call_tool(name: str, arguments: dict):
            arguments = arguments or {}
            return await self._mediated_call(name, arguments)

    async def discover_tools(self, session: "ClientSession") -> list:
        """Discover tools from an upstream MCP server.

        Calls list_tools() on the upstream session and registers each
        discovered tool. If the same tool name exists from a different
        upstream, the later registration wins.

        Returns:
            List of discovered mcp_types.Tool objects.
        """
        result = await session.list_tools()
        discovered = []
        for tool in result.tools:
            self._upstream_tools[tool.name] = tool
            self._upstream_session_map[tool.name] = session
            discovered.append(tool)
        return discovered

    async def _mediated_call(self, name: str, arguments: dict) -> list:
        """Route a tool call through governance mediation.

        Flow:
            1. Classify by evidence inference
            2. Evaluate against policy rules
            3. Record decision to chain
            4. If ALLOW → forward to upstream
            5. If DENY → return structured denial
        """
        # 1. Classify
        classification = classify(name, arguments)

        # 2. Chain linkage
        prev_hash = self._chain.get_prev_hash()

        # 3. Evaluate policy
        record = evaluate(
            classification,
            policy=self._policy,
            prev_record_hash=prev_hash,
            user_identity=self._user_identity,
            session_id=self._session_id,
        )

        # 4. Record
        self._chain.append(record)

        # 5. Execute or deny
        if record["policy_decision"] == "ALLOW":
            return await self._forward_to_upstream(name, arguments)
        else:
            return self._build_denial(name, classification, record)

    async def _forward_to_upstream(self, name: str, arguments: dict) -> list:
        """Forward an allowed tool call to the upstream server."""
        session = self._upstream_session_map.get(name)
        if session is None:
            return [mcp_types.TextContent(
                type="text",
                text=json.dumps({
                    "error": "UPSTREAM_NOT_FOUND",
                    "tool": name,
                }),
            )]
        try:
            result = await session.call_tool(name, arguments)
            return result.content
        except Exception as exc:
            return [mcp_types.TextContent(
                type="text",
                text=json.dumps({
                    "error": "UPSTREAM_EXECUTION_FAILED",
                    "tool": name,
                    "detail": str(exc),
                }),
            )]

    @staticmethod
    def _build_denial(name: str, classification: dict, record: dict) -> list:
        """Build a structured denial response."""
        return [mcp_types.TextContent(
            type="text",
            text=json.dumps({
                "governance_decision": "DENY",
                "tool": name,
                "classification": {
                    "action_type": classification["action_type"],
                    "scope": classification["scope"],
                    "confidence_tier": classification["confidence_tier"],
                },
                "reasons": record.get("policy_reasons", []),
                "matched_rule": record.get("matched_rule", ""),
            }),
        )]

    @property
    def server(self) -> "Server":
        """The underlying MCP Server instance."""
        return self._server

    @property
    def tools(self) -> dict:
        """Currently registered upstream tools (name → Tool)."""
        return dict(self._upstream_tools)

    @property
    def chain_records(self) -> list:
        """Decision records (if using InMemoryChainRecorder)."""
        if isinstance(self._chain, InMemoryChainRecorder):
            return self._chain.records
        return []
