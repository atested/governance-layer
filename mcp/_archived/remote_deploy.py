#!/usr/bin/env python3
import json
import os
import sys
from urllib.parse import urlparse

import uvicorn

import remote_server


def _public_base_url() -> str:
    raw = str(os.environ.get("GOVMCP_PUBLIC_BASE_URL", "")).strip()
    if not raw:
        raise RuntimeError("GOVMCP_PUBLIC_BASE_URL_MISSING")
    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise RuntimeError("GOVMCP_PUBLIC_BASE_URL_MUST_BE_HTTPS")
    if not parsed.netloc:
        raise RuntimeError("GOVMCP_PUBLIC_BASE_URL_INVALID")
    if parsed.query or parsed.fragment:
        raise RuntimeError("GOVMCP_PUBLIC_BASE_URL_INVALID")
    path = parsed.path.rstrip("/")
    normalized = f"https://{parsed.netloc}{path}" if path else f"https://{parsed.netloc}"
    return normalized


def deployment_runtime_contract() -> dict[str, object]:
    base = remote_server.remote_runtime_contract()
    public_base_url = _public_base_url()
    streamable_http_path = str(base["streamable_http_path"])
    auth_mode = str(base["auth_mode"])
    client_auth_requirement = "Authorization: Bearer <configured token>"
    if auth_mode == "oidc_external_issuer":
        client_auth_requirement = "OAuth 2.0 / OIDC access token from configured issuer"
    return {
        **base,
        "deployment_mode": "single_process_uvicorn_behind_external_https_terminator",
        "tls_termination": "external_required",
        "public_base_url": public_base_url,
        "public_mcp_url": f"{public_base_url}{streamable_http_path}",
        "local_bind_url": f"http://{base['host']}:{base['port']}{streamable_http_path}",
        "client_auth_requirement": client_auth_requirement,
    }


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--print-contract":
        print(json.dumps(deployment_runtime_contract(), sort_keys=True, separators=(",", ":")))
        return 0

    contract = deployment_runtime_contract()
    app = remote_server.build_remote_app()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=str(contract["host"]),
            port=int(contract["port"]),
            log_level=str(os.environ.get("GOVMCP_LOG_LEVEL", "INFO")).strip().lower() or "info",
        )
    )
    server.run()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc
