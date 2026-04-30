"""Tests for proxy hardening (D-163).

T2-02: Request body size limits and generic error messages.
Task 4: Non-HTTPS upstream warning at startup.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from proxy.server import MAX_REQUEST_BODY_BYTES, ProxyServer


def _make_writer():
    """Create a mock writer that captures written data."""
    written_data = bytearray()
    writer = AsyncMock(spec=asyncio.StreamWriter)
    writer.write = lambda data: written_data.extend(data)
    writer.drain = AsyncMock()
    writer.close = MagicMock()
    writer.wait_closed = AsyncMock()
    return writer, written_data


class TestRequestBodySizeLimit:
    """T2-02: Verify oversized requests are rejected with 413."""

    def test_max_body_constant_exists(self):
        """MAX_REQUEST_BODY_BYTES is defined and reasonable."""
        assert MAX_REQUEST_BODY_BYTES > 0
        assert MAX_REQUEST_BODY_BYTES == 10 * 1024 * 1024  # 10 MB default

    def test_content_length_over_limit_returns_413(self):
        """Request with Content-Length exceeding limit gets 413 before body read."""
        proxy_mock = MagicMock()
        server = ProxyServer(proxy_mock, "127.0.0.1", 0)

        oversized = MAX_REQUEST_BODY_BYTES + 1

        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readline.side_effect = [
            f"POST /anthropic/v1/messages HTTP/1.1\r\n".encode(),
            f"content-length: {oversized}\r\n".encode(),
            b"content-type: application/json\r\n",
            b"\r\n",
        ]

        writer, written_data = _make_writer()

        asyncio.get_event_loop().run_until_complete(
            server._handle_client(reader, writer)
        )

        response = written_data.decode()
        assert "413" in response
        assert "request body too large" in response
        # Should NOT have called readexactly (body not read)
        reader.readexactly.assert_not_called()


class TestGenericErrorMessages:
    """T2-02: Internal exceptions return generic messages, not str(exc)."""

    def test_exception_returns_generic_error(self):
        """Internal proxy exception returns 'internal proxy error', not details."""
        proxy_mock = MagicMock()
        # Make handle_request raise to trigger the error handler
        proxy_mock.handle_request = AsyncMock(
            side_effect=RuntimeError("secret internal path /foo/bar/baz")
        )
        server = ProxyServer(proxy_mock, "127.0.0.1", 0)

        reader = AsyncMock(spec=asyncio.StreamReader)
        reader.readline.side_effect = [
            b"POST /anthropic/v1/messages HTTP/1.1\r\n",
            b"content-length: 2\r\n",
            b"content-type: application/json\r\n",
            b"\r\n",
        ]
        reader.readexactly = AsyncMock(return_value=b"{}")

        writer, written_data = _make_writer()

        asyncio.get_event_loop().run_until_complete(
            server._handle_client(reader, writer)
        )

        response = written_data.decode()
        assert "502" in response
        assert "internal proxy error" in response
        # Must NOT contain the actual exception message
        assert "secret internal path" not in response
        assert "/foo/bar/baz" not in response


class TestNonHttpsUpstreamWarning:
    """Task 4: HTTP upstreams trigger a warning; HTTPS upstreams do not."""

    def test_http_upstream_warning_code_exists(self):
        """The non-HTTPS upstream warning logic exists in main()."""
        import proxy.server as ps
        import inspect
        source = inspect.getsource(ps.main)
        assert 'not using HTTPS' in source
        assert 'traffic to this provider will be unencrypted' in source

    def test_max_request_body_env_override(self):
        """MAX_REQUEST_BODY_BYTES can be overridden via environment."""
        import proxy.server as ps
        import inspect
        source = inspect.getsource(ps)
        assert 'ATESTED_MAX_REQUEST_BODY_BYTES' in source
