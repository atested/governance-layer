#!/usr/bin/env python3
"""
test_v2_proxy.py — Tests for the GovMCP v2 governed proxy.

Tests dynamic tool discovery, mediated execution, and governance
transparency using real classifier and policy evaluator.

For proxy tests that require MCP types, we use the actual MCP SDK
types to verify schema fidelity. Tests that need a ClientSession
use an async mock that mimics the MCP client protocol.
"""

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock

REPO = Path(__file__).resolve().parents[1]
MCP_DIR = REPO / "mcp"
SCRIPTS = REPO / "scripts"
for p in (MCP_DIR, SCRIPTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Check MCP availability
try:
    from mcp import types as mcp_types
    from v2_proxy import GovernedProxy
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from mediation import InMemoryChainRecorder
from policy_eval_v2 import load_policy_rules

_POLICY = load_policy_rules()
_REPO_STR = str(REPO)


def _make_policy_with_base_dirs(base_dirs):
    p = dict(_POLICY)
    p["base_dirs"] = base_dirs
    return p


_TEST_POLICY = _make_policy_with_base_dirs([_REPO_STR])


def _run_async(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_session(tools, call_results=None):
    """Create a mock ClientSession with predefined tools and call results.

    Args:
        tools: List of (name, description, input_schema) tuples.
        call_results: Dict mapping tool_name → return content list.
    """
    session = AsyncMock()

    # Build Tool objects
    mock_tools = []
    for name, desc, schema in tools:
        tool = mcp_types.Tool(
            name=name,
            description=desc,
            inputSchema=schema,
        )
        mock_tools.append(tool)

    # list_tools returns ListToolsResult
    list_result = MagicMock()
    list_result.tools = mock_tools
    session.list_tools = AsyncMock(return_value=list_result)

    # call_tool returns CallToolResult
    call_results = call_results or {}
    async def mock_call_tool(name, arguments=None):
        result = MagicMock()
        if name in call_results:
            result.content = call_results[name]
        else:
            result.content = [mcp_types.TextContent(
                type="text",
                text=json.dumps({"result": "ok", "tool": name}),
            )]
        return result

    session.call_tool = AsyncMock(side_effect=mock_call_tool)
    return session


# ===================================================================
# Tool discovery
# ===================================================================

@unittest.skipUnless(MCP_AVAILABLE, "MCP SDK not available")
class TestToolDiscovery(unittest.TestCase):
    """Proxy discovers and registers upstream tools."""

    def test_discover_single_upstream(self):
        """Discovers tools from a single upstream server."""
        session = _make_mock_session([
            ("read_file", "Read a file", {"type": "object", "properties": {"path": {"type": "string"}}}),
            ("write_file", "Write a file", {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}),
        ])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        discovered = _run_async(proxy.discover_tools(session))

        self.assertEqual(len(discovered), 2)
        self.assertIn("read_file", proxy.tools)
        self.assertIn("write_file", proxy.tools)

    def test_discovered_tools_preserve_schema(self):
        """Discovered tools have identical schemas to upstream."""
        schema = {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path"],
        }
        session = _make_mock_session([
            ("read_file", "Read a file from disk", schema),
        ])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        tool = proxy.tools["read_file"]
        self.assertEqual(tool.name, "read_file")
        self.assertEqual(tool.description, "Read a file from disk")
        self.assertEqual(tool.inputSchema, schema)

    def test_discover_multiple_upstreams(self):
        """Tools from multiple upstream servers are merged."""
        session1 = _make_mock_session([
            ("tool_a", "First tool", {"type": "object"}),
        ])
        session2 = _make_mock_session([
            ("tool_b", "Second tool", {"type": "object"}),
        ])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session1))
        _run_async(proxy.discover_tools(session2))

        self.assertEqual(len(proxy.tools), 2)
        self.assertIn("tool_a", proxy.tools)
        self.assertIn("tool_b", proxy.tools)

    def test_empty_upstream(self):
        """Handles upstream with no tools."""
        session = _make_mock_session([])
        proxy = GovernedProxy(policy=_TEST_POLICY)
        discovered = _run_async(proxy.discover_tools(session))
        self.assertEqual(len(discovered), 0)
        self.assertEqual(len(proxy.tools), 0)


# ===================================================================
# Mediated execution — ALLOW
# ===================================================================

@unittest.skipUnless(MCP_AVAILABLE, "MCP SDK not available")
class TestMediatedAllow(unittest.TestCase):
    """Tool calls that pass policy are forwarded to upstream."""

    def test_allowed_read_forwards_to_upstream(self):
        """A read within base dirs is forwarded and upstream result returned."""
        upstream_content = [mcp_types.TextContent(
            type="text",
            text="file contents here",
        )]
        session = _make_mock_session(
            [("read_file", "Read a file", {"type": "object", "properties": {"path": {"type": "string"}}})],
            call_results={"read_file": upstream_content},
        )

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        result = _run_async(proxy._mediated_call(
            "read_file", {"path": os.path.join(_REPO_STR, "README.md")},
        ))

        # Result should be the upstream content
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].text, "file contents here")

        # Upstream session.call_tool should have been called
        session.call_tool.assert_awaited_once_with("read_file", {"path": os.path.join(_REPO_STR, "README.md")})

    def test_allowed_call_records_to_chain(self):
        """Allowed calls are recorded in the governance chain."""
        session = _make_mock_session([
            ("list_dir", "List a directory", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))
        _run_async(proxy._mediated_call(
            "list_dir", {"path": _REPO_STR},
        ))

        self.assertEqual(len(proxy.chain_records), 1)
        self.assertEqual(proxy.chain_records[0]["policy_decision"], "ALLOW")


# ===================================================================
# Mediated execution — DENY
# ===================================================================

@unittest.skipUnless(MCP_AVAILABLE, "MCP SDK not available")
class TestMediatedDeny(unittest.TestCase):
    """Tool calls that fail policy are blocked — upstream is never called."""

    def test_denied_read_sensitive_path(self):
        """Read targeting sensitive path → DENY, upstream NOT called."""
        session = _make_mock_session([
            ("read_file", "Read a file", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        result = _run_async(proxy._mediated_call(
            "read_file", {"path": "/etc/shadow"},
        ))

        # Should return a denial
        self.assertEqual(len(result), 1)
        denial = json.loads(result[0].text)
        self.assertEqual(denial["governance_decision"], "DENY")
        self.assertEqual(denial["tool"], "read_file")

        # Upstream must NOT have been called
        session.call_tool.assert_not_awaited()

    def test_denied_call_records_to_chain(self):
        """Denied calls are recorded in the governance chain."""
        session = _make_mock_session([
            ("read_file", "Read a file", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))
        _run_async(proxy._mediated_call(
            "read_file", {"path": "/etc/shadow"},
        ))

        self.assertEqual(len(proxy.chain_records), 1)
        self.assertEqual(proxy.chain_records[0]["policy_decision"], "DENY")

    def test_denied_includes_classification(self):
        """Denial response includes classification details."""
        session = _make_mock_session([
            ("run_script", "Run a script", {"type": "object", "properties": {"command": {"type": "string"}}}),
        ])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        result = _run_async(proxy._mediated_call(
            "run_script", {"command": "python3 evil.py"},
        ))

        denial = json.loads(result[0].text)
        self.assertIn("classification", denial)
        self.assertEqual(denial["classification"]["confidence_tier"], 3)


# ===================================================================
# Chain record metadata
# ===================================================================

@unittest.skipUnless(MCP_AVAILABLE, "MCP SDK not available")
class TestChainRecordMetadata(unittest.TestCase):
    """v2 chain records include classification metadata."""

    def test_record_includes_classification(self):
        session = _make_mock_session([
            ("read_file", "Read", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])
        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))
        _run_async(proxy._mediated_call(
            "read_file", {"path": os.path.join(_REPO_STR, "README.md")},
        ))

        record = proxy.chain_records[0]
        cls = record["classification"]
        self.assertEqual(cls["action_type"], "read")
        self.assertEqual(cls["confidence_tier"], 1)
        self.assertIn("targets", cls)
        self.assertIn("scope", cls)

    def test_record_includes_evidence(self):
        session = _make_mock_session([
            ("read_file", "Read", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])
        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))
        _run_async(proxy._mediated_call(
            "read_file", {"path": os.path.join(_REPO_STR, "README.md")},
        ))

        record = proxy.chain_records[0]
        self.assertIn("evidence", record)
        self.assertIn("source", record["evidence"])

    def test_record_preserves_original_tool_name(self):
        """The original tool name from upstream is preserved in the record."""
        session = _make_mock_session([
            ("my_custom_reader", "Read stuff", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])
        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))
        _run_async(proxy._mediated_call(
            "my_custom_reader", {"path": os.path.join(_REPO_STR, "README.md")},
        ))

        record = proxy.chain_records[0]
        self.assertEqual(record["original_tool"], "my_custom_reader")

    def test_chain_linkage_across_calls(self):
        """Sequential proxy calls maintain chain linkage."""
        session = _make_mock_session([
            ("read_file", "Read", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])
        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        # Two calls
        _run_async(proxy._mediated_call(
            "read_file", {"path": os.path.join(_REPO_STR, "README.md")},
        ))
        _run_async(proxy._mediated_call(
            "read_file", {"path": os.path.join(_REPO_STR, "CLAUDE.md")},
        ))

        self.assertEqual(len(proxy.chain_records), 2)
        first_hash = proxy.chain_records[0]["record_hash"]
        second_prev = proxy.chain_records[1]["prev_record_hash"]
        self.assertEqual(second_prev, first_hash)

    def test_user_identity_and_session_propagated(self):
        """User identity and session ID are propagated to chain records."""
        session = _make_mock_session([
            ("read_file", "Read", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])
        proxy = GovernedProxy(
            policy=_TEST_POLICY,
            user_identity="alice@example.com",
            session_id="sess-proxy-001",
        )
        _run_async(proxy.discover_tools(session))
        _run_async(proxy._mediated_call(
            "read_file", {"path": os.path.join(_REPO_STR, "README.md")},
        ))

        record = proxy.chain_records[0]
        self.assertEqual(record["user_identity"], "alice@example.com")
        self.assertEqual(record["session_id"], "sess-proxy-001")


# ===================================================================
# Transparency — agent sees same tools
# ===================================================================

@unittest.skipUnless(MCP_AVAILABLE, "MCP SDK not available")
class TestAgentTransparency(unittest.TestCase):
    """The agent sees exactly the same tools as upstream — governance is invisible."""

    def test_tool_names_identical(self):
        """Tool names exposed by proxy match upstream exactly."""
        upstream_tools = [
            ("Read", "Read a file", {"type": "object"}),
            ("Write", "Write a file", {"type": "object"}),
            ("Bash", "Run a command", {"type": "object"}),
            ("Glob", "Search files", {"type": "object"}),
            ("Grep", "Search content", {"type": "object"}),
        ]
        session = _make_mock_session(upstream_tools)

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        proxy_names = set(proxy.tools.keys())
        upstream_names = {name for name, _, _ in upstream_tools}
        self.assertEqual(proxy_names, upstream_names)

    def test_tool_schemas_identical(self):
        """Tool input schemas exposed by proxy match upstream exactly."""
        schema = {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path"},
                "offset": {"type": "integer", "default": 0},
                "limit": {"type": "integer", "default": 2000},
            },
            "required": ["file_path"],
        }
        session = _make_mock_session([("Read", "Read a file", schema)])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        self.assertEqual(proxy.tools["Read"].inputSchema, schema)

    def test_tool_descriptions_identical(self):
        """Tool descriptions exposed by proxy match upstream exactly."""
        session = _make_mock_session([
            ("Read", "Reads a file from the local filesystem. You can access any file.", {"type": "object"}),
        ])

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        self.assertEqual(
            proxy.tools["Read"].description,
            "Reads a file from the local filesystem. You can access any file.",
        )


# ===================================================================
# Error handling
# ===================================================================

@unittest.skipUnless(MCP_AVAILABLE, "MCP SDK not available")
class TestProxyErrorHandling(unittest.TestCase):
    """Proxy handles upstream errors gracefully."""

    def test_upstream_exception_returns_error(self):
        """If upstream call_tool raises, proxy returns error content."""
        session = _make_mock_session([
            ("read_file", "Read a file", {"type": "object", "properties": {"path": {"type": "string"}}}),
        ])
        session.call_tool = AsyncMock(side_effect=RuntimeError("connection lost"))

        proxy = GovernedProxy(policy=_TEST_POLICY)
        _run_async(proxy.discover_tools(session))

        # Use a path within base dirs so the call is ALLOWED and reaches upstream
        result = _run_async(proxy._mediated_call(
            "read_file", {"path": os.path.join(_REPO_STR, "README.md")},
        ))
        error = json.loads(result[0].text)
        self.assertEqual(error["error"], "UPSTREAM_EXECUTION_FAILED")
        self.assertIn("connection lost", error["detail"])

    def test_unknown_tool_returns_error(self):
        """Calling an undiscovered tool returns error."""
        proxy = GovernedProxy(policy=_TEST_POLICY)

        # Call a tool that was never registered
        result = _run_async(proxy._mediated_call(
            "nonexistent_tool", {"path": os.path.join(_REPO_STR, "README.md")},
        ))

        # Should be allowed by policy but fail at upstream lookup
        content = json.loads(result[0].text)
        self.assertEqual(content["error"], "UPSTREAM_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
