#!/usr/bin/env python3
import asyncio
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx
import uvicorn
import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.routes import build_resource_metadata_url
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from jwt import exceptions as jwt_exceptions

import server as govmcp_server

_AUTH_MODE_BEARER = "bearer"
_AUTH_MODE_OIDC = "oidc"
_DEFAULT_OIDC_SIGNING_ALGS = ("RS256",)
_OIDC_COMPAT_ROUTES_REGISTERED = False
_OIDC_DIAGNOSTIC_LOG = "oidc_live_diagnostics.jsonl"
_DIAGNOSTIC_ALLOWED_CORS_ORIGINS = ("http://localhost:6274",)
_REMOTE_TRANSPORT = "streamable-http"
_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _env_host() -> str:
    return str(os.environ.get("GOVMCP_HOST", "127.0.0.1")).strip() or "127.0.0.1"


def _env_port() -> int:
    raw = str(os.environ.get("GOVMCP_PORT", "8000")).strip() or "8000"
    try:
        port = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"GOVMCP_PORT_INVALID:{raw}") from exc
    if port <= 0 or port > 65535:
        raise RuntimeError(f"GOVMCP_PORT_INVALID:{raw}")
    return port


def _env_log_level() -> str:
    level = str(os.environ.get("GOVMCP_LOG_LEVEL", "INFO")).strip().upper() or "INFO"
    if level not in _VALID_LOG_LEVELS:
        raise RuntimeError(f"GOVMCP_LOG_LEVEL_INVALID:{level}")
    return level


def _env_streamable_http_path() -> str:
    path = str(os.environ.get("GOVMCP_STREAMABLE_HTTP_PATH", "/mcp")).strip() or "/mcp"
    if not path.startswith("/"):
        path = "/" + path
    return path


def _runtime_root() -> str:
    default_root = Path(__file__).resolve().parents[1] / "gov_runtime"
    raw = str(os.environ.get("GOV_RUNTIME_DIR", str(default_root))).strip() or str(default_root)
    return str(Path(raw).resolve()).replace("\\", "/")


def _base_remote_runtime_contract() -> dict[str, object]:
    contract_fn = getattr(govmcp_server, "remote_runtime_contract", None)
    if callable(contract_fn):
        contract = contract_fn()
        if isinstance(contract, dict):
            return contract
    return {
        "transport": _REMOTE_TRANSPORT,
        "host": _env_host(),
        "port": _env_port(),
        "streamable_http_path": _env_streamable_http_path(),
        "runtime_root": _runtime_root(),
        "runtime_root_source": "env:GOV_RUNTIME_DIR" if os.environ.get("GOV_RUNTIME_DIR") else "repo_default:gov_runtime",
        "auth_state": "restocked_remote_surface",
        "deployment_state": "restocked_remote_surface",
    }


def _apply_runtime_settings() -> None:
    settings = govmcp_server.mcp.settings
    for key, value in {
        "host": _env_host(),
        "port": _env_port(),
        "log_level": _env_log_level(),
        "streamable_http_path": _env_streamable_http_path(),
    }.items():
        try:
            setattr(settings, key, value)
        except Exception:
            continue


def _public_base_url_required() -> str:
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
    return f"https://{parsed.netloc}{path}" if path else f"https://{parsed.netloc}"


def _auth_mode() -> str:
    raw = str(os.environ.get("GOVMCP_REMOTE_AUTH_MODE", _AUTH_MODE_BEARER)).strip().lower() or _AUTH_MODE_BEARER
    if raw not in {_AUTH_MODE_BEARER, _AUTH_MODE_OIDC}:
        raise RuntimeError(f"GOVMCP_REMOTE_AUTH_MODE_INVALID:{raw}")
    return raw


def _diagnostics_enabled() -> bool:
    raw = str(os.environ.get("GOVMCP_OIDC_DIAGNOSTICS", "")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _diagnostics_log_path() -> Path | None:
    runtime_dir = os.environ.get("GOV_RUNTIME_DIR")
    if not runtime_dir:
        return None
    return Path(runtime_dir) / "LOGS" / _OIDC_DIAGNOSTIC_LOG


def _diagnostic_value(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_diagnostic_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _diagnostic_value(item) for key, item in value.items()}
    return str(value)


def _diagnostic_log(event: str, **fields) -> None:
    if not _diagnostics_enabled():
        return
    payload = {
        "ts": int(time.time()),
        "event": event,
        **{key: _diagnostic_value(value) for key, value in fields.items()},
    }
    line = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    print(line, file=sys.stderr, flush=True)
    log_path = _diagnostics_log_path()
    if log_path is None:
        return
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.write("\n")
    except OSError:
        pass


def _extract_user_identity(token: str, mode: str) -> str:
    """Derive a user identity string from an auth token.

    For OIDC: decode the ``sub`` claim (unverified — the token was already
    validated by the TokenVerifier middleware).
    For bearer: return a stable hash prefix of the token value.
    """
    if mode == _AUTH_MODE_OIDC:
        try:
            claims = jwt.decode(token, options={"verify_signature": False})
            sub = str(claims.get("sub", "")).strip()
            if sub:
                return f"oidc:{sub}"
        except Exception:
            pass
        return "oidc:unknown"
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return f"bearer:{token_hash}"


def _streamable_http_path() -> str:
    return str(_base_remote_runtime_contract()["streamable_http_path"])


def _request_targets_mcp(request: Request) -> bool:
    return request.url.path == _streamable_http_path()


def _prevalidation_auth_trace_fields(request: Request) -> dict[str, object]:
    authz = request.headers.get("authorization")
    header_present = authz is not None
    header_value = authz or ""
    bearer_prefix_present = header_value.startswith("Bearer ")
    extracted_token = header_value.split(" ", 1)[1].strip() if bearer_prefix_present else ""
    token_extracted = bool(extracted_token)

    if not header_present:
        rejection_stage = "pre_validation"
        rejection_reason = "authorization_header_missing"
        validator_entered = False
    elif not bearer_prefix_present:
        rejection_stage = "pre_validation"
        rejection_reason = "authorization_header_not_bearer"
        validator_entered = False
    elif not token_extracted:
        rejection_stage = "pre_validation"
        rejection_reason = "bearer_token_extraction_failed"
        validator_entered = False
    else:
        rejection_stage = "validation"
        rejection_reason = None
        validator_entered = True

    return {
        "path": request.url.path,
        "authorization_header_present": header_present,
        "bearer_prefix_present": bearer_prefix_present,
        "bearer_token_extracted": token_extracted,
        "validator_entered": validator_entered,
        "rejection_stage": rejection_stage,
        "rejection_reason": rejection_reason,
    }


def _jwt_claim_preview(token: str) -> dict[str, object]:
    preview = {
        "jwt_like": token.count(".") == 2,
        "claim_preview_available": False,
    }
    if token.count(".") != 2:
        return preview
    try:
        claims = jwt.decode(token, options={"verify_signature": False, "verify_aud": False, "verify_iss": False})
    except Exception:
        return preview
    aud = claims.get("aud")
    if isinstance(aud, list):
        aud_preview = [str(item) for item in aud]
    elif aud is None:
        aud_preview = None
    else:
        aud_preview = [str(aud)]
    scope_claim = claims.get("scope")
    scope_list = scope_claim.split() if isinstance(scope_claim, str) else []
    return {
        "jwt_like": True,
        "claim_preview_available": True,
        "iss": claims.get("iss"),
        "aud": aud_preview,
        "scope_count": len(scope_list),
        "scope_present": bool(scope_list),
        "azp_present": bool(claims.get("azp")),
        "sub_present": bool(claims.get("sub")),
        "exp_present": "exp" in claims,
    }


def _token_validation_failure_reason(exc: Exception) -> str:
    if isinstance(exc, jwt_exceptions.InvalidIssuerError):
        return "issuer"
    if isinstance(exc, jwt_exceptions.InvalidAudienceError):
        return "audience"
    if isinstance(exc, jwt_exceptions.ExpiredSignatureError):
        return "expired"
    if isinstance(exc, jwt_exceptions.ImmatureSignatureError):
        return "nbf_or_iat"
    if isinstance(exc, jwt_exceptions.DecodeError):
        return "token_shape"
    if isinstance(exc, jwt_exceptions.InvalidSignatureError):
        return "signature"
    if isinstance(exc, jwt_exceptions.InvalidAlgorithmError):
        return "algorithm"
    return exc.__class__.__name__


def _load_bearer_token() -> tuple[str, str]:
    direct = str(os.environ.get("GOVMCP_REMOTE_AUTH_TOKEN", "")).strip()
    token_file = str(os.environ.get("GOVMCP_REMOTE_AUTH_TOKEN_FILE", "")).strip()

    if direct and token_file:
        raise RuntimeError("GOVMCP_REMOTE_AUTH_CONFIG_CONFLICT")
    if token_file:
        try:
            token = Path(token_file).read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError(f"GOVMCP_REMOTE_AUTH_TOKEN_FILE_UNREADABLE:{exc}") from exc
        if not token:
            raise RuntimeError("GOVMCP_REMOTE_AUTH_TOKEN_FILE_EMPTY")
        return token, "env:GOVMCP_REMOTE_AUTH_TOKEN_FILE"
    if direct:
        return direct, "env:GOVMCP_REMOTE_AUTH_TOKEN"
    raise RuntimeError("GOVMCP_REMOTE_AUTH_TOKEN_MISSING")


def _auth_contract() -> dict[str, str]:
    mode = _auth_mode()
    if mode == _AUTH_MODE_BEARER:
        token, source = _load_bearer_token()
        return {
            "auth_mode": "shared_bearer_token",
            "auth_required": "yes",
            "auth_token_source": source,
            "auth_token_length": str(len(token)),
            "auth_transition_role": "transitional_local_ops_and_non_connector_remote_use",
        }

    issuer = _oidc_issuer_url()
    audience = _oidc_audience()
    scopes = _oidc_required_scopes()
    return {
        "auth_mode": "oidc_external_issuer",
        "auth_required": "yes",
        "auth_issuer_url": issuer,
        "auth_audience": audience,
        "auth_required_scopes": " ".join(scopes),
        "auth_transition_role": "connector_facing_remote_auth",
        "auth_signing_algorithms": " ".join(_oidc_signing_algorithms()),
    }


def remote_runtime_contract() -> dict[str, object]:
    contract = _base_remote_runtime_contract()
    contract.update(_auth_contract())
    if _auth_mode() == _AUTH_MODE_OIDC:
        public_base_url = _public_base_url_required()
        resource_server_url = f"{public_base_url}{contract['streamable_http_path']}"
        contract["oidc_protected_resource_metadata_url"] = str(build_resource_metadata_url(resource_server_url))
    return contract


def _oidc_issuer_url() -> str:
    raw = str(os.environ.get("GOVMCP_OIDC_ISSUER_URL", "")).strip()
    if not raw:
        raise RuntimeError("GOVMCP_OIDC_ISSUER_URL_MISSING")
    parsed = urlparse(raw)
    host = parsed.hostname or ""
    localhost_ok = host == "localhost" or host.startswith("127.")
    if parsed.scheme != "https" and not localhost_ok:
        raise RuntimeError("GOVMCP_OIDC_ISSUER_URL_MUST_BE_HTTPS")
    if not parsed.netloc:
        raise RuntimeError("GOVMCP_OIDC_ISSUER_URL_INVALID")
    if parsed.query or parsed.fragment:
        raise RuntimeError("GOVMCP_OIDC_ISSUER_URL_INVALID")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}" if path else f"{parsed.scheme}://{parsed.netloc}"


def _oidc_audience() -> str:
    raw = str(os.environ.get("GOVMCP_OIDC_AUDIENCE", "")).strip()
    if not raw:
        raise RuntimeError("GOVMCP_OIDC_AUDIENCE_MISSING")
    return raw


def _oidc_required_scopes() -> list[str]:
    raw = str(os.environ.get("GOVMCP_OIDC_REQUIRED_SCOPES", "")).strip()
    if not raw:
        return []
    return [part for part in raw.split() if part]


def _oidc_signing_algorithms() -> tuple[str, ...]:
    raw = str(os.environ.get("GOVMCP_OIDC_SIGNING_ALGORITHMS", "")).strip()
    if not raw:
        return _DEFAULT_OIDC_SIGNING_ALGS
    algs = tuple(part for part in raw.replace(",", " ").split() if part)
    if not algs:
        raise RuntimeError("GOVMCP_OIDC_SIGNING_ALGORITHMS_INVALID")
    return algs


@dataclass
class _OIDCDiscoveryConfig:
    issuer: str
    jwks_uri: str
    authorization_endpoint: str
    token_endpoint: str
    metadata: dict[str, object]


class _OIDCTokenVerifier(TokenVerifier):
    def __init__(self, issuer_url: str, audience: str):
        self.issuer_url = issuer_url
        self.audience = audience
        self.allowed_algorithms = _oidc_signing_algorithms()
        self._discovery: _OIDCDiscoveryConfig | None = None
        self._jwk_client: jwt.PyJWKClient | None = None

    def _discover(self) -> _OIDCDiscoveryConfig:
        if self._discovery is not None:
            return self._discovery

        discovery_url = f"{self.issuer_url}/.well-known/openid-configuration"
        try:
            response = httpx.get(discovery_url, timeout=5.0)
            response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"GOVMCP_OIDC_DISCOVERY_FAILED:{exc}") from exc

        payload = response.json()
        issuer = str(payload.get("issuer", "")).strip()
        jwks_uri = str(payload.get("jwks_uri", "")).strip()
        if issuer.rstrip("/") != self.issuer_url.rstrip("/"):
            raise RuntimeError("GOVMCP_OIDC_DISCOVERY_ISSUER_MISMATCH")
        if not jwks_uri:
            raise RuntimeError("GOVMCP_OIDC_JWKS_URI_MISSING")
        self._discovery = _OIDCDiscoveryConfig(
            issuer=issuer,
            jwks_uri=jwks_uri,
            authorization_endpoint=str(payload.get("authorization_endpoint", "")).strip(),
            token_endpoint=str(payload.get("token_endpoint", "")).strip(),
            metadata=payload,
        )
        self._jwk_client = jwt.PyJWKClient(jwks_uri, cache_jwk_set=True, lifespan=300, timeout=5.0)
        return self._discovery

    def _verify_sync(self, token: str) -> AccessToken | None:
        discovery = self._discover()
        assert self._jwk_client is not None
        claim_preview = _jwt_claim_preview(token)
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self.allowed_algorithms),
                audience=self.audience,
                issuer=discovery.issuer,
            )
        except Exception as exc:
            _diagnostic_log(
                "oidc_validation_failed",
                issuer_expected=discovery.issuer,
                audience_expected=self.audience,
                failure_reason=_token_validation_failure_reason(exc),
                **claim_preview,
            )
            return None

        scope_claim = claims.get("scope")
        scopes: list[str] = []
        if isinstance(scope_claim, str):
            scopes.extend(part for part in scope_claim.split() if part)
        permissions = claims.get("permissions")
        if isinstance(permissions, list):
            scopes.extend(str(part) for part in permissions if str(part))
        scopes = sorted(set(scopes))

        client_id = (
            str(claims.get("azp") or claims.get("client_id") or claims.get("sub") or "oidc-subject").strip()
            or "oidc-subject"
        )
        expires_at = claims.get("exp")
        expires_at_int = int(expires_at) if isinstance(expires_at, (int, float)) else None
        required_scopes = _oidc_required_scopes()
        missing_scopes = [scope for scope in required_scopes if scope not in scopes]
        if missing_scopes:
            _diagnostic_log(
                "oidc_validation_failed",
                issuer_expected=discovery.issuer,
                audience_expected=self.audience,
                failure_reason="scope",
                required_scopes=required_scopes,
                missing_scopes=missing_scopes,
                **claim_preview,
            )
            return None
        _diagnostic_log(
            "oidc_validation_passed",
            issuer_expected=discovery.issuer,
            audience_expected=self.audience,
            validated_scope_count=len(scopes),
            scopes=scopes,
            client_id_present=bool(client_id),
            **claim_preview,
        )
        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at_int,
            resource=self.audience,
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        return await asyncio.to_thread(self._verify_sync, token)


def _oidc_auth_settings() -> AuthSettings:
    public_base_url = _public_base_url_required()
    resource_server_url = f"{public_base_url}{_base_remote_runtime_contract()['streamable_http_path']}"
    return AuthSettings(
        issuer_url=_oidc_issuer_url(),
        resource_server_url=resource_server_url,
        required_scopes=_oidc_required_scopes() or None,
    )


def _oidc_discovery_config() -> _OIDCDiscoveryConfig:
    verifier = _OIDCTokenVerifier(_oidc_issuer_url(), _oidc_audience())
    return verifier._discover()


def _protected_resource_metadata_path() -> str:
    streamable_http_path = str(_base_remote_runtime_contract()["streamable_http_path"])
    return str(build_resource_metadata_url(f"https://metadata.local{streamable_http_path}")).replace("https://metadata.local", "", 1)


def _protected_resource_server_url() -> str:
    public_base_url = _public_base_url_required()
    streamable_http_path = str(_base_remote_runtime_contract()["streamable_http_path"])
    return f"{public_base_url}{streamable_http_path}"


def _protected_resource_metadata_payload() -> dict[str, object]:
    discovery = _oidc_discovery_config()
    payload: dict[str, object] = {
        # Inspector expects the protected resource to remain the MCP endpoint URL.
        # The Auth0 API audience remains a separate runtime/verifier contract.
        "resource": _protected_resource_server_url(),
        "authorization_servers": [discovery.issuer],
        "bearer_methods_supported": ["header"],
    }
    scopes = _oidc_required_scopes()
    if scopes:
        payload["scopes_supported"] = scopes
    return payload


def _oauth_authorization_server_metadata() -> dict[str, object]:
    public_base_url = _public_base_url_required()
    discovery = _oidc_discovery_config()
    if not discovery.authorization_endpoint:
        raise RuntimeError("GOVMCP_OIDC_AUTHORIZATION_ENDPOINT_MISSING")
    if not discovery.token_endpoint:
        raise RuntimeError("GOVMCP_OIDC_TOKEN_ENDPOINT_MISSING")
    metadata = dict(discovery.metadata)
    metadata["issuer"] = discovery.issuer
    metadata["authorization_endpoint"] = f"{public_base_url}/authorize"
    metadata["token_endpoint"] = f"{public_base_url}/token"
    token_auth_methods = metadata.get("token_endpoint_auth_methods_supported")
    if isinstance(token_auth_methods, list):
        normalized = [str(item) for item in token_auth_methods if str(item)]
    else:
        normalized = []
    if "none" not in normalized:
        normalized.append("none")
    metadata["token_endpoint_auth_methods_supported"] = normalized
    return metadata


def _proxy_response_headers(headers: httpx.Headers) -> dict[str, str]:
    allowed = {
        "cache-control",
        "content-type",
        "location",
        "pragma",
        "www-authenticate",
    }
    return {key: value for key, value in headers.items() if key.lower() in allowed}


def _diagnostic_cors_allowed_origins() -> tuple[str, ...]:
    """Diagnostic-only browser allowlist for MCP Inspector local origin."""
    return _DIAGNOSTIC_ALLOWED_CORS_ORIGINS


def _wrap_with_diagnostic_cors(app):
    return CORSMiddleware(
        app,
        allow_origins=list(_diagnostic_cors_allowed_origins()),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["authorization", "content-type", "accept"],
    )


def _register_oidc_compatibility_routes() -> None:
    global _OIDC_COMPAT_ROUTES_REGISTERED
    if _OIDC_COMPAT_ROUTES_REGISTERED:
        return

    @govmcp_server.mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
    async def oauth_authorization_server_metadata(_request: Request) -> Response:
        return Response(status_code=404)

    @govmcp_server.mcp.custom_route("/.well-known/openid-configuration", methods=["GET"])
    async def openid_configuration_metadata(_request: Request) -> Response:
        return Response(status_code=404)

    @govmcp_server.mcp.custom_route("/authorize", methods=["GET"])
    async def authorize_redirect(_request: Request) -> Response:
        return Response(status_code=404)

    @govmcp_server.mcp.custom_route("/token", methods=["POST"])
    async def token_passthrough(_request: Request) -> Response:
        return Response(status_code=404)

    _OIDC_COMPAT_ROUTES_REGISTERED = True


def _remote_transport_security() -> TransportSecuritySettings:
    allowed_hosts = {"127.0.0.1:*", "localhost:*", "[::1]:*"}
    allowed_origins = {"http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"}

    raw_public_base_url = str(os.environ.get("GOVMCP_PUBLIC_BASE_URL", "")).strip()
    if raw_public_base_url:
        parsed = urlparse(raw_public_base_url)
        if parsed.scheme == "https" and parsed.netloc:
            allowed_hosts.add(parsed.netloc)
            allowed_origins.add(f"https://{parsed.netloc}")

    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(allowed_hosts),
        allowed_origins=sorted(allowed_origins),
    )


def _unauthorized(detail: str) -> JSONResponse:
    return JSONResponse(
        {"error": "unauthorized", "detail": detail},
        status_code=401,
        headers={"WWW-Authenticate": 'Bearer realm="govmcp-remote"'},
    )


def build_remote_app():
    _apply_runtime_settings()
    govmcp_server.mcp.settings.transport_security = _remote_transport_security()
    if _auth_mode() == _AUTH_MODE_OIDC:
        _register_oidc_compatibility_routes()
        govmcp_server.mcp.settings.auth = _oidc_auth_settings()
        govmcp_server.mcp._auth_server_provider = None
        govmcp_server.mcp._token_verifier = _OIDCTokenVerifier(_oidc_issuer_url(), _oidc_audience())
        govmcp_server.mcp._session_manager = None
        app = govmcp_server.mcp.streamable_http_app()

        @app.middleware("http")
        async def override_protected_resource_metadata(request: Request, call_next):
            if request.method == "GET" and request.url.path == _protected_resource_metadata_path():
                return JSONResponse(_protected_resource_metadata_payload())
            return await call_next(request)

        @app.middleware("http")
        async def inject_user_identity_oidc(request: Request, call_next):
            authz = request.headers.get("authorization", "")
            if authz.startswith("Bearer "):
                token = authz.split(" ", 1)[1].strip()
                identity = _extract_user_identity(token, _AUTH_MODE_OIDC)
                govmcp_server._current_user_identity.set(identity)
            return await call_next(request)

        @app.middleware("http")
        async def trace_prevalidation_auth_path(request: Request, call_next):
            if _request_targets_mcp(request):
                _diagnostic_log("oidc_mcp_prevalidation_auth_path", **_prevalidation_auth_trace_fields(request))
            return await call_next(request)

        return _wrap_with_diagnostic_cors(app)

    expected_token, _source = _load_bearer_token()
    govmcp_server.mcp.settings.auth = None
    govmcp_server.mcp._auth_server_provider = None
    govmcp_server.mcp._token_verifier = None
    govmcp_server.mcp._session_manager = None
    app = govmcp_server.mcp.streamable_http_app()

    @app.middleware("http")
    async def require_bearer_auth(request: Request, call_next):
        authz = request.headers.get("authorization", "")
        if not authz.startswith("Bearer "):
            return _unauthorized("missing bearer token")
        supplied = authz.split(" ", 1)[1].strip()
        if not supplied:
            return _unauthorized("empty bearer token")
        if not hmac.compare_digest(supplied, expected_token):
            return _unauthorized("invalid bearer token")
        identity = _extract_user_identity(supplied, _AUTH_MODE_BEARER)
        govmcp_server._current_user_identity.set(identity)
        return await call_next(request)

    return _wrap_with_diagnostic_cors(app)


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--print-config":
        print(json.dumps(remote_runtime_contract(), sort_keys=True, separators=(",", ":")))
        return 0
    app = build_remote_app()
    cfg = remote_runtime_contract()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=str(cfg["host"]),
            port=int(cfg["port"]),
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
