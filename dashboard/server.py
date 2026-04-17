#!/usr/bin/env python3
"""
Atested Dashboard — lightweight HTTP server.

Serves the dashboard UI files and JSON API endpoints backed by the
governance chain readout functions.  Started by the governance_dashboard
MCP tool; not intended for direct invocation by operators.
"""

import importlib
import json
import os
import secrets
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

REPO = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO / "scripts"
MCP_DIR = REPO / "mcp"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from storage_contract import runtime_root

RUNTIME = runtime_root(REPO)
CHAIN = RUNTIME / "LOGS" / "decision-chain.jsonl"
RECORDS_DIR = RUNTIME / "LOGS" / "records"

# Lazy-loaded helpers
_verification_tracker = None
_approval_store = None


def _get_verification_tracker():
    global _verification_tracker
    if _verification_tracker is None:
        from verification import load_verification_state_from_chain
        _verification_tracker = (
            load_verification_state_from_chain(str(CHAIN))
            if CHAIN.exists()
            else __import__("verification").VerificationStateTracker()
        )
    return _verification_tracker


def _get_approval_store():
    global _approval_store
    if _approval_store is None:
        from approval_store import load_approval_store_from_chain, ApprovalStore
        _approval_store = (
            load_approval_store_from_chain(str(CHAIN))
            if CHAIN.exists()
            else ApprovalStore()
        )
    return _approval_store


def _invalidate_approval_store():
    global _approval_store
    _approval_store = None


# ---------------------------------------------------------------------------
# Source file auto-reload
# ---------------------------------------------------------------------------

# Modules to reload when their source files change on disk (dependency order).
_RELOAD_MODULES = [
    "storage_contract",
    "verification",
    "approval_store",
    "chain_health",
    "readout",
]

_source_mtimes: dict[str, float] = {}
_reload_lock = threading.Lock()


def _check_and_reload():
    """Reload Python modules and recompute asset version if source files changed."""
    global _ASSET_VERSION, _verification_tracker, _approval_store

    py_changed = False
    ui_changed = False

    # Check Python source files in scripts/ and mcp/
    for search_dir in (SCRIPTS_DIR, MCP_DIR):
        if not search_dir.exists():
            continue
        for py_file in search_dir.glob("*.py"):
            key = str(py_file)
            try:
                mtime = py_file.stat().st_mtime
            except OSError:
                continue
            prev = _source_mtimes.get(key)
            _source_mtimes[key] = mtime
            if prev is not None and prev != mtime:
                py_changed = True

    # Check UI assets
    for name in ("app.js", "styles.css", "index.html"):
        p = DASHBOARD_UI_DIR / name
        key = str(p)
        try:
            mtime = p.stat().st_mtime
        except OSError:
            continue
        prev = _source_mtimes.get(key)
        _source_mtimes[key] = mtime
        if prev is not None and prev != mtime:
            ui_changed = True

    if py_changed:
        with _reload_lock:
            for mod_name in _RELOAD_MODULES:
                mod = sys.modules.get(mod_name)
                if mod is not None:
                    try:
                        importlib.reload(mod)
                    except Exception as exc:
                        print(f"Auto-reload {mod_name}: {exc}", file=sys.stderr)
            # Invalidate cached state objects so they're rebuilt from fresh modules
            _verification_tracker = None
            _approval_store = None

    if ui_changed:
        _ASSET_VERSION = _compute_asset_version()


def _governed_family():
    return str(os.environ.get("GOV_GOVERNED_FAMILY", "mcp_tools_v1")).strip() or "mcp_tools_v1"


def _deployment_context():
    return str(os.environ.get("GOV_DEPLOYMENT_CONTEXT", "default")).strip() or "default"


def _policy_version():
    return str(os.environ.get("GOV_POLICY_VERSION", "baseline-v1")).strip() or "baseline-v1"


def _json_response(handler, data, status=200):
    body = json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    cors_origin = handler._cors_origin() if hasattr(handler, "_cors_origin") else ""
    if cors_origin:
        handler.send_header("Access-Control-Allow-Origin", cors_origin)
    handler.end_headers()
    handler.wfile.write(body)


import threading
import time as _time_mod

_chain_lock = threading.Lock()


def _acquire_chain_file_lock():
    """Acquire cross-process mkdir lock (same protocol as mcp/server.py)."""
    lockdir = Path(str(CHAIN) + ".lock.d")
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


def _release_chain_file_lock(lockdir):
    try:
        (lockdir / "lock_owner.json").unlink(missing_ok=True)
        lockdir.rmdir()
    except OSError:
        pass


def _get_chain_head_hash():
    """Read the record_hash from the last line of the chain.

    Must be called under both _chain_lock and the cross-process file lock
    to prevent concurrent writers from reading the same prev_record_hash.
    """
    if not CHAIN.exists():
        return None
    last_line = ""
    with open(CHAIN, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if not last_line:
        return None
    try:
        return json.loads(last_line).get("record_hash")
    except json.JSONDecodeError:
        return None


def _append_chain_record_atomic(event):
    """Atomically read head hash, set prev_record_hash, and append to chain.

    Uses both a threading lock (intra-process) and a cross-process mkdir
    lock to ensure no two writers read the same prev_record_hash.
    """
    from event_model import _compute_event_record_hash
    import stat as _stat

    CHAIN.parent.mkdir(parents=True, exist_ok=True)
    with _chain_lock:
        lockdir = _acquire_chain_file_lock()
        try:
            # Read head hash INSIDE the lock
            event["prev_record_hash"] = _get_chain_head_hash()
            event["record_hash"] = _compute_event_record_hash(event)
            line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
            fd = os.open(str(CHAIN), os.O_WRONLY | os.O_APPEND | os.O_CREAT,
                          _stat.S_IRUSR | _stat.S_IWUSR)
            try:
                os.write(fd, line.encode("utf-8"))
            finally:
                os.close(fd)
        finally:
            _release_chain_file_lock(lockdir)


DASHBOARD_UI_DIR = REPO / "dashboard" / "ui"
DASHBOARD_UI_NEXT_DIR = REPO / "dashboard" / "ui-next"

# Cache-busting version derived from static asset content hashes.
# Computed once at import time; changes whenever files are modified and
# the server is restarted.
def _compute_asset_version() -> str:
    import hashlib
    h = hashlib.sha256()
    for name in ("app.js", "styles.css"):
        p = DASHBOARD_UI_DIR / name
        if p.exists():
            h.update(p.read_bytes())
    return h.hexdigest()[:12]

_ASSET_VERSION = _compute_asset_version()

# Static UI filenames served without authentication
_STATIC_FILES = {"index.html", "app.js", "styles.css", ""}

_DASHBOARD_TOKEN = None
_DASHBOARD_PORT = None

CSP_HEADER = (
    "default-src 'self'; "
    "font-src https://fonts.googleapis.com https://fonts.gstatic.com; "
    "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'"
)


class DashboardHandler(SimpleHTTPRequestHandler):
    """Serves dashboard UI files and /api/* JSON endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_UI_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, must-revalidate")
        super().end_headers()

    def _check_auth(self):
        """Return True if the request carries a valid bearer token."""
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        return auth[len("Bearer "):] == _DASHBOARD_TOKEN

    def _origin_allowed(self):
        """Return True if the Origin header (if present) is localhost."""
        origin = self.headers.get("Origin", "")
        if not origin:
            return True
        allowed = {
            f"http://127.0.0.1:{_DASHBOARD_PORT}",
            f"http://localhost:{_DASHBOARD_PORT}",
        }
        return origin in allowed

    def _cors_origin(self):
        """Return the specific allowed Origin value for CORS, or empty string."""
        origin = self.headers.get("Origin", "")
        allowed = {
            f"http://127.0.0.1:{_DASHBOARD_PORT}",
            f"http://localhost:{_DASHBOARD_PORT}",
        }
        return origin if origin in allowed else ""

    def do_GET(self):
        _check_and_reload()
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            if not self._check_auth():
                _json_response(self, {"error": "Unauthorized"}, 401)
                return
            self._handle_api(parsed)
        elif parsed.path in ("/", "/index.html", ""):
            self._serve_index_html()
        else:
            super().do_GET()

    def _serve_index_html(self):
        """Serve index.html with the dashboard token injected as a meta tag."""
        index_path = DASHBOARD_UI_DIR / "index.html"
        try:
            html = index_path.read_text(encoding="utf-8")
        except OSError:
            self.send_error(404)
            return
        # Inject token meta tag before </head>
        token_meta = f'  <meta name="dashboard-token" content="{_DASHBOARD_TOKEN}">\n'
        html = html.replace("</head>", token_meta + "</head>", 1)
        # Cache-busting: append version query to static asset URLs
        html = html.replace("./styles.css", f"./styles.css?v={_ASSET_VERSION}")
        html = html.replace("./app.js", f"./app.js?v={_ASSET_VERSION}")
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Security-Policy", CSP_HEADER)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        _check_and_reload()
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            if not self._check_auth():
                _json_response(self, {"error": "Unauthorized"}, 401)
                return
            if parsed.path == "/api/observe":
                self._handle_observe()
            elif parsed.path == "/api/approvals/add":
                self._handle_approve()
            elif parsed.path == "/api/approvals/revoke":
                self._handle_revoke()
            elif parsed.path == "/api/health/acknowledge":
                self._handle_acknowledge()
            elif parsed.path == "/api/config/update":
                self._handle_config_update()
            elif parsed.path == "/api/config/verify-license":
                self._handle_config_verify_license()
            elif parsed.path == "/api/feedback/submit":
                self._handle_feedback_submit()
            elif parsed.path == "/api/telemetry/submit":
                self._handle_telemetry_submit()
            elif parsed.path == "/api/telemetry/opt-in":
                self._handle_telemetry_opt_in()
            elif parsed.path == "/api/notifications/dismiss":
                self._handle_notification_dismiss()
            elif parsed.path == "/api/notifications/viewed":
                self._handle_notifications_viewed()
            elif parsed.path == "/api/disclosure/acknowledge":
                self._handle_disclosure_acknowledge()
            elif parsed.path == "/api/identity/lock":
                self._handle_identity_lock()
            else:
                _json_response(self, {"error": "method not allowed"}, 405)
        else:
            self.send_error(405)

    def do_OPTIONS(self):
        cors_origin = self._cors_origin()
        self.send_response(204)
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()


    def _handle_observe(self):
        """POST /api/observe — record an ungoverned operation observation.

        Accepts JSON body: {"operation_type": "...", "target": "...", "source": "..."}
        This is the HTTP endpoint for non-MCP integrations.
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        op_type = str(data.get("operation_type", "")).strip().lower()
        from event_model import UNGOVERNED_OPERATION_TYPES, build_non_action_event
        if op_type not in UNGOVERNED_OPERATION_TYPES:
            _json_response(self, {
                "error": "INVALID_OPERATION_TYPE",
                "valid_types": sorted(UNGOVERNED_OPERATION_TYPES),
            }, 400)
            return

        payload = {"operation_type": op_type}
        target = str(data.get("target", "")).strip()
        source = str(data.get("source", "")).strip()
        observed_at = str(data.get("observed_at", "")).strip()
        if target:
            payload["target"] = target
        if source:
            payload["source"] = source
        if observed_at:
            payload["observed_at"] = observed_at

        # Append to chain (lightweight — no policy eval)
        try:
            event = build_non_action_event(
                "ungoverned_operation_observed",
                payload,
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)
            _json_response(self, {
                "recorded": True,
                "event_id": event.get("event_id"),
                "operation_type": op_type,
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_approve(self):
        """POST /api/approvals/add — approve a file (record approval event)."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        artifact_identity = str(data.get("artifact_identity", "")).strip()
        operator = str(data.get("operator", "")).strip() or "dashboard_operator"
        if not artifact_identity:
            _json_response(self, {"error": "artifact_identity is required"}, 400)
            return

        try:
            from event_model import build_non_action_event
            payload = {
                "artifact_identity": artifact_identity,
                "approving_operator": operator,
                "governed_family": _governed_family(),
                "deployment_context": _deployment_context(),
                "policy_version": _policy_version(),
            }
            event = build_non_action_event(
                "opaque_artifact_approval",
                payload,
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)
            _invalidate_approval_store()
            _json_response(self, {
                "approved": True,
                "event_id": event.get("event_id"),
                "artifact_identity": artifact_identity,
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_revoke(self):
        """POST /api/approvals/revoke — revoke an existing file approval."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        artifact_identity = str(data.get("artifact_identity", "")).strip()
        operator = str(data.get("operator", "")).strip() or "dashboard_operator"
        if not artifact_identity:
            _json_response(self, {"error": "artifact_identity is required"}, 400)
            return

        try:
            from event_model import build_non_action_event
            payload = {
                "artifact_identity": artifact_identity,
                "revoking_operator": operator,
                "governed_family": _governed_family(),
                "deployment_context": _deployment_context(),
                "policy_version": _policy_version(),
            }
            event = build_non_action_event(
                "opaque_artifact_revocation",
                payload,
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)
            _invalidate_approval_store()
            _json_response(self, {
                "revoked": True,
                "event_id": event.get("event_id"),
                "artifact_identity": artifact_identity,
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_acknowledge(self):
        """POST /api/health/acknowledge — acknowledge a health alert."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        alert_source = str(data.get("source", "")).strip()
        if not alert_source:
            _json_response(self, {"error": "source required"}, 400)
            return

        from chain_health import append_stability_event
        stability_log = RUNTIME / "LOGS" / "chain_stability.jsonl"
        evt = append_stability_event(stability_log, "alert_acknowledged", {
            "source": alert_source,
            "message": str(data.get("message", "")),
        })
        _json_response(self, {"acknowledged": True, "event_id": evt["stability_event_id"]})

    def _handle_config_update(self):
        """POST /api/config/update — validate and write an updated capability registry.

        Accepts JSON body: {"registry": {...}, "license_key": "..."}
        If no license_key is provided (trial mode), enforces trial limits:
          - max 3 additional allow_base_dirs beyond defaults per tool
          - no cap field changes
          - basic boolean toggles only
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 65536:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        registry = data.get("registry")
        if not isinstance(registry, dict):
            _json_response(self, {"error": "registry must be a JSON object"}, 400)
            return

        license_key = str(data.get("license_key", "")).strip()

        from registry_integrity import validate_registry_schema
        from licensing import validate_license_key, resolve_posture

        # Determine access tier
        licensed = False
        license_info = None
        if license_key:
            license_info = validate_license_key(license_key)
            if license_info is None:
                _json_response(self, {"error": "invalid license key"}, 403)
                return
            licensed = True

        # Schema validation is always required
        valid, schema_error = validate_registry_schema(registry)
        if not valid:
            _json_response(self, {"error": schema_error}, 400)
            return

        # Trial-mode constraints
        if not licensed:
            posture = resolve_posture(RUNTIME)
            if posture.get("license_status") not in ("trial", "personal"):
                _json_response(self, {
                    "error": "license required for registry edits",
                    "license_status": posture.get("license_status"),
                }, 403)
                return

            # Load existing registry to compute diffs
            registry_path = REPO / "capabilities" / "capability-registry.json"
            existing = {}
            if registry_path.exists():
                try:
                    existing = json.loads(registry_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    existing = {}

            existing_tools = {t["tool"]: t for t in existing.get("tools", []) if isinstance(t, dict)}
            _DEFAULT_MAX_EXTRA_DIRS = 3
            _CAP_FIELDS = {"max_bytes", "max_bytes_hard", "max_entries", "max_entries_hard"}

            for tool_entry in registry.get("tools", []):
                if not isinstance(tool_entry, dict):
                    continue
                tool_name = tool_entry.get("tool", "")
                existing_entry = existing_tools.get(tool_name, {})

                # Check for cap field changes (not allowed on trial)
                for cap_field in _CAP_FIELDS:
                    if cap_field in tool_entry and tool_entry[cap_field] != existing_entry.get(cap_field):
                        _json_response(self, {
                            "error": f"trial: cap field '{cap_field}' changes require a license",
                            "tool": tool_name,
                        }, 403)
                        return

                # Check extra allow_base_dirs
                new_dirs = set(tool_entry.get("allow_base_dirs", []))
                old_dirs = set(existing_entry.get("allow_base_dirs", []))
                extra_dirs = new_dirs - old_dirs
                if len(extra_dirs) > _DEFAULT_MAX_EXTRA_DIRS:
                    _json_response(self, {
                        "error": (
                            f"trial: max {_DEFAULT_MAX_EXTRA_DIRS} additional directories "
                            f"per tool; {len(extra_dirs)} requested for '{tool_name}'"
                        ),
                        "tool": tool_name,
                    }, 403)
                    return

        # Write the registry atomically
        registry_path = REPO / "capabilities" / "capability-registry.json"
        try:
            import hashlib
            import tempfile
            import stat as _stat

            content = json.dumps(registry, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
            content_bytes = content.encode("utf-8")
            fd, tmp_path = tempfile.mkstemp(
                dir=str(registry_path.parent), suffix=".tmp"
            )
            try:
                os.write(fd, content_bytes)
                os.fchmod(fd, _stat.S_IRUSR | _stat.S_IWUSR)
                os.close(fd)
                os.rename(tmp_path, str(registry_path))
            except Exception:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise

            new_hash = "sha256:" + hashlib.sha256(content_bytes).hexdigest()
        except OSError as exc:
            _json_response(self, {"error": f"write failed: {exc}"}, 500)
            return

        result = {
            "success": True,
            "registry_hash": new_hash,
            "tools_count": len(registry.get("tools", [])),
        }
        if license_info:
            result["license_tier"] = license_info.get("tier")
        _json_response(self, result)

    def _handle_config_verify_license(self):
        """POST /api/config/verify-license — validate a license key.

        Accepts JSON body: {"license_key": "..."}
        Returns {"valid": true/false, "tier": "...", "expiry": "..."}
        """
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        license_key = str(data.get("license_key", "")).strip()
        if not license_key:
            _json_response(self, {"error": "license_key required"}, 400)
            return

        from licensing import validate_license_key
        info = validate_license_key(license_key)
        if info is None:
            _json_response(self, {"valid": False, "tier": None, "expiry": None})
            return

        _json_response(self, {
            "valid": True,
            "tier": info.get("tier"),
            "expiry": info.get("expiry_iso"),
        })

    def _handle_feedback_submit(self):
        """POST /api/feedback/submit — create and optionally send a feedback artifact."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 16384:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        message = str(data.get("message", "")).strip()
        if not message:
            _json_response(self, {"error": "message required"}, 400)
            return

        experience_note = str(data.get("experience_note", "")).strip()
        permission_to_use = bool(data.get("permission_to_use", False))
        send_to_remote = bool(data.get("send_to_remote", False))

        try:
            sys.path.insert(0, str(MCP_DIR))
            from feedback_signing import build_feedback_artifact, write_artifact, send_artifact_to_remote

            artifact = build_feedback_artifact(
                message=message,
                experience_note=experience_note,
                permission_to_use=permission_to_use,
                runtime_root=RUNTIME,
            )

            feedback_dir = RUNTIME / "LOGS" / "feedback"
            out_path = write_artifact(artifact, feedback_dir)

            # Append chain event
            from event_model import build_non_action_event
            event = build_non_action_event(
                "feedback_submitted",
                {
                    "artifact_id": artifact["artifact_id"],
                    "artifact_hash": artifact["artifact_hash"],
                    "sent_to_remote": send_to_remote,
                },
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)

            result = {
                "artifact_id": artifact["artifact_id"],
                "artifact_hash": artifact["artifact_hash"],
                "signed": artifact.get("signed", False),
                "stored_at": str(out_path),
            }

            if send_to_remote and artifact.get("signed"):
                remote_result = send_artifact_to_remote(
                    artifact, "https://license.atested.com/api/feedback"
                )
                result["remote"] = remote_result

            _json_response(self, result)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_telemetry_submit(self):
        """POST /api/telemetry/submit — create and optionally send a telemetry artifact."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        send_to_remote = bool(data.get("send_to_remote", False))

        try:
            sys.path.insert(0, str(MCP_DIR))
            from feedback_signing import build_telemetry_artifact, write_artifact, send_artifact_to_remote

            artifact = build_telemetry_artifact(
                chain_path=CHAIN,
                runtime_root=RUNTIME,
            )

            telemetry_dir = RUNTIME / "LOGS" / "telemetry"
            out_path = write_artifact(artifact, telemetry_dir)

            # Append chain event
            from event_model import build_non_action_event
            event = build_non_action_event(
                "telemetry_submitted",
                {
                    "artifact_id": artifact["artifact_id"],
                    "artifact_hash": artifact["artifact_hash"],
                    "sent_to_remote": send_to_remote,
                },
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)

            result = {
                "artifact_id": artifact["artifact_id"],
                "artifact_hash": artifact["artifact_hash"],
                "signed": artifact.get("signed", False),
                "stored_at": str(out_path),
                "total_allow": artifact["total_allow"],
                "total_deny": artifact["total_deny"],
                "total_deterministic": artifact["total_deterministic"],
                "total_judgment": artifact["total_judgment"],
            }

            if send_to_remote and artifact.get("signed"):
                remote_result = send_artifact_to_remote(
                    artifact, "https://license.atested.com/api/telemetry"
                )
                result["remote"] = remote_result

            _json_response(self, result)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_telemetry_opt_in(self):
        """POST /api/telemetry/opt-in — toggle telemetry opt-in."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 1024:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        opted_in = bool(data.get("opted_in", False))
        opt_in_file = RUNTIME / "telemetry_opt_in"

        try:
            opt_in_file.parent.mkdir(parents=True, exist_ok=True)
            opt_in_file.write_text("1" if opted_in else "0", encoding="utf-8")

            from event_model import build_non_action_event
            event = build_non_action_event(
                "telemetry_opt_in_changed",
                {"opted_in": opted_in},
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)

            _json_response(self, {"opted_in": opted_in})
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # Notification & disclosure endpoints (Phase 5)
    # ------------------------------------------------------------------

    def _handle_notifications_get(self):
        """GET /api/notifications — return active notifications derived from health signals."""
        try:
            from chain_health import collect_health_signals
            stability_log = RUNTIME / "LOGS" / "chain_stability.jsonl"
            chain_meta = RUNTIME / "LOGS" / "chain_meta.json"
            h = collect_health_signals(CHAIN, stability_log, chain_meta, RUNTIME)

            notifications = []

            # Chain integrity alerts
            if h.get("chain", {}).get("status") == "broken":
                notifications.append({
                    "id": "chain_broken",
                    "severity": "security",
                    "title": "Chain Integrity Compromised",
                    "message": "The governance chain has detected integrity failures. Investigate immediately.",
                    "persistent": True,
                })
            elif h.get("chain", {}).get("status") == "repaired":
                notifications.append({
                    "id": "chain_repaired",
                    "severity": "routine",
                    "title": "Chain Repaired",
                    "message": "The governance chain was broken and has been repaired.",
                    "persistent": False,
                })

            # DENY rate anomaly
            if h.get("deny_rate", {}).get("anomaly"):
                notifications.append({
                    "id": "deny_rate_anomaly",
                    "severity": "critical",
                    "title": "DENY Rate Anomaly",
                    "message": "The recent DENY rate is significantly above the historical average.",
                    "persistent": False,
                })

            # Observation gap
            if h.get("observations", {}).get("gap_detected"):
                notifications.append({
                    "id": "observation_gap",
                    "severity": "critical",
                    "title": "Observation Gap Detected",
                    "message": "No ungoverned operation observations received recently. Check hook configuration.",
                    "persistent": False,
                })

            # License expiry warning
            license_info = h.get("license", {})
            if license_info.get("status") == "expired":
                notifications.append({
                    "id": "license_expired",
                    "severity": "critical",
                    "title": "License Expired",
                    "message": "Your Atested license has expired.",
                    "persistent": False,
                })
            elif license_info.get("trial_days_remaining") is not None:
                days = license_info["trial_days_remaining"]
                if days <= 7:
                    notifications.append({
                        "id": "trial_expiring",
                        "severity": "routine",
                        "title": "Trial Expiring Soon",
                        "message": f"Your trial expires in {days} day{'s' if days != 1 else ''}.",
                        "persistent": False,
                    })

            # Health alerts promoted to notifications
            for alert in h.get("alerts", []):
                notifications.append({
                    "id": f"alert_{alert.get('source', 'unknown')}",
                    "severity": "critical" if alert.get("severity") == "critical" else "routine",
                    "title": alert.get("source", "Alert"),
                    "message": alert.get("message", ""),
                    "persistent": False,
                })

            # Filter out dismissed notifications
            dismissed = self._load_dismissed_notifications()
            active = [n for n in notifications if n["id"] not in dismissed]

            _json_response(self, {
                "notifications": active,
                "total": len(notifications),
                "dismissed_count": len(dismissed),
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _load_dismissed_notifications(self):
        """Load set of dismissed notification IDs from the dismissal file."""
        dismiss_file = RUNTIME / "notification_dismissals.json"
        if not dismiss_file.exists():
            return set()
        try:
            data = json.loads(dismiss_file.read_text(encoding="utf-8"))
            return set(data.get("dismissed", []))
        except (json.JSONDecodeError, OSError):
            return set()

    def _handle_notification_dismiss(self):
        """POST /api/notifications/dismiss — dismiss a notification by ID."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        notification_id = str(data.get("notification_id", "")).strip()
        if not notification_id:
            _json_response(self, {"error": "notification_id is required"}, 400)
            return

        try:
            # Persist dismissal
            dismiss_file = RUNTIME / "notification_dismissals.json"
            dismissed = set()
            if dismiss_file.exists():
                try:
                    existing = json.loads(dismiss_file.read_text(encoding="utf-8"))
                    dismissed = set(existing.get("dismissed", []))
                except (json.JSONDecodeError, OSError):
                    pass
            dismissed.add(notification_id)
            dismiss_file.parent.mkdir(parents=True, exist_ok=True)
            dismiss_file.write_text(
                json.dumps({"dismissed": sorted(dismissed)}, indent=2),
                encoding="utf-8",
            )

            # Record to chain
            from event_model import build_non_action_event
            event = build_non_action_event(
                "notification_dismissed",
                {
                    "notification_id": notification_id,
                    "governed_family": _governed_family(),
                    "deployment_context": _deployment_context(),
                },
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)

            _json_response(self, {
                "dismissed": True,
                "notification_id": notification_id,
                "event_id": event.get("event_id"),
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_notifications_viewed(self):
        """POST /api/notifications/viewed — record that notifications were viewed."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        try:
            from event_model import build_non_action_event
            event = build_non_action_event(
                "notifications_viewed",
                {
                    "count": data.get("count", 0),
                    "governed_family": _governed_family(),
                    "deployment_context": _deployment_context(),
                },
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)

            _json_response(self, {
                "recorded": True,
                "event_id": event.get("event_id"),
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_disclosure_acknowledge(self):
        """POST /api/disclosure/acknowledge — record first-run disclosure acknowledgement."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length > 4096:
                _json_response(self, {"error": "payload too large"}, 413)
                return
            body = self.rfile.read(length)
            data = json.loads(body) if body else {}
        except (json.JSONDecodeError, ValueError):
            _json_response(self, {"error": "invalid JSON"}, 400)
            return

        try:
            from event_model import build_non_action_event
            event = build_non_action_event(
                "disclosure_shown",
                {
                    "operator": str(data.get("operator", "")).strip() or "dashboard_operator",
                    "governed_family": _governed_family(),
                    "deployment_context": _deployment_context(),
                    "policy_version": _policy_version(),
                },
                prev_record_hash=None,
            )
            _append_chain_record_atomic(event)

            _json_response(self, {
                "acknowledged": True,
                "event_id": event.get("event_id"),
            })
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_disclosure_status(self):
        """GET /api/disclosure/status — check if disclosure has been acknowledged."""
        try:
            from readout import load_chain_rows
            rows = load_chain_rows(CHAIN)
            acknowledged = any(
                r.get("event_type") == "disclosure_shown" for r in rows
            )
            _json_response(self, {"acknowledged": acknowledged})
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    # ------------------------------------------------------------------
    # Identity session endpoints (Phase 6)
    # ------------------------------------------------------------------

    def _handle_identity_session(self):
        """GET /api/identity/session — return operator identity state.

        When the identity backend is not yet implemented, returns
        { configured: false } for graceful degradation.
        """
        try:
            session_file = RUNTIME / "identity_session.json"
            if not session_file.exists():
                _json_response(self, {"configured": False})
                return

            data = json.loads(session_file.read_text(encoding="utf-8"))
            if not data.get("configured"):
                _json_response(self, {"configured": False})
                return

            # Return session state
            import time
            result = {
                "configured": True,
                "operator_name": data.get("operator_name", ""),
                "operator_email": data.get("operator_email", ""),
                "locked": data.get("locked", True),
            }

            if not data.get("locked", True):
                unlock_time = data.get("unlock_time")
                idle_time = data.get("last_activity_time")
                now = time.time()

                # Hard ceiling: 1 hour from unlock
                if unlock_time:
                    ceiling_remaining = max(0, (unlock_time + 3600) - now)
                    result["ceiling_remaining_s"] = int(ceiling_remaining)
                    # Auto-lock if ceiling exceeded
                    if ceiling_remaining <= 0:
                        data["locked"] = True
                        session_file.write_text(
                            json.dumps(data, indent=2), encoding="utf-8"
                        )
                        result["locked"] = True

                # Idle timer: 30 minutes from last activity
                if idle_time:
                    idle_remaining = max(0, (idle_time + 1800) - now)
                    result["idle_remaining_s"] = int(idle_remaining)
                    if idle_remaining <= 0:
                        data["locked"] = True
                        session_file.write_text(
                            json.dumps(data, indent=2), encoding="utf-8"
                        )
                        result["locked"] = True

            _json_response(self, result)
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def _handle_identity_lock(self):
        """POST /api/identity/lock — manually lock the operator session."""
        try:
            session_file = RUNTIME / "identity_session.json"
            if not session_file.exists():
                _json_response(self, {"error": "identity not configured"}, 400)
                return

            data = json.loads(session_file.read_text(encoding="utf-8"))
            if not data.get("configured"):
                _json_response(self, {"error": "identity not configured"}, 400)
                return

            data["locked"] = True
            data.pop("unlock_time", None)
            data.pop("last_activity_time", None)
            session_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

            _json_response(self, {"locked": True, "operator_name": data.get("operator_name", "")})
        except Exception as exc:
            _json_response(self, {"error": str(exc)}, 500)

    def log_message(self, format, *args):
        pass  # Silence request logs

    def _handle_api(self, parsed):
        params = parse_qs(parsed.query)

        def qs(key, default=""):
            v = params.get(key, [default])
            return v[0] if v else default

        def qs_int(key, default=0):
            try:
                return int(qs(key, str(default)))
            except (ValueError, TypeError):
                return default

        path = parsed.path

        if path == "/api/status":
            from readout import assemble_governance_status_record
            window = qs_int("window") or None
            data = assemble_governance_status_record(
                CHAIN, _get_verification_tracker(), _get_approval_store(),
                window=window,
            )
            _json_response(self, data)

        elif path == "/api/activity":
            from readout import governance_activity_view
            data = governance_activity_view(
                CHAIN,
                limit=qs_int("limit", 50),
                offset=qs_int("offset", 0),
                governed_family=qs("governed_family") or None,
                event_category=qs("event_category") or None,
                resolution=qs("resolution") or None,
                start_time=qs("start_time") or None,
                end_time=qs("end_time") or None,
            )
            _json_response(self, data)

        elif path == "/api/approvals":
            from readout import governance_approvals_view
            data = governance_approvals_view(CHAIN, _get_approval_store())
            _json_response(self, data)

        elif path == "/api/verification":
            from readout import governance_verification_view
            data = governance_verification_view(
                CHAIN, _get_verification_tracker(),
                governed_family=qs("governed_family") or None,
            )
            _json_response(self, data)

        elif path == "/api/audit/query":
            from readout import audit_query
            data = audit_query(
                CHAIN, RECORDS_DIR,
                start_time=qs("start_time") or None,
                end_time=qs("end_time") or None,
                user_identity=qs("user_identity") or None,
                tool_name=qs("tool_name") or None,
                policy_decision=qs("policy_decision") or None,
                event_category=qs("event_category") or None,
                limit=qs_int("limit", 100),
                offset=qs_int("offset", 0),
            )
            _json_response(self, data)

        elif path == "/api/audit/record":
            from readout import audit_record_detail
            rid = qs("record_id")
            if not rid:
                _json_response(self, {"error": "record_id required"}, 400)
                return
            data = audit_record_detail(CHAIN, RECORDS_DIR, record_id=rid)
            _json_response(self, data)

        elif path == "/api/audit/report":
            from readout import audit_report
            data = audit_report(
                CHAIN, RECORDS_DIR,
                start_time=qs("start_time") or None,
                end_time=qs("end_time") or None,
                group_by=qs("group_by", "tool"),
            )
            _json_response(self, data)

        elif path == "/api/transparency":
            from readout import load_chain_rows, compute_transparency_metric
            rows = load_chain_rows(CHAIN)
            data = compute_transparency_metric(
                rows,
                start_time=qs("start_time") or None,
                end_time=qs("end_time") or None,
            )
            _json_response(self, data)

        elif path == "/api/health":
            from chain_health import collect_health_signals
            stability_log = RUNTIME / "LOGS" / "chain_stability.jsonl"
            chain_meta = RUNTIME / "LOGS" / "chain_meta.json"
            data = collect_health_signals(CHAIN, stability_log, chain_meta, RUNTIME)
            _json_response(self, data)

        elif path == "/api/health/acknowledge":
            # POST-only, but handle GET gracefully
            _json_response(self, {"error": "use POST"}, 405)

        elif path == "/api/users":
            from readout import load_chain_rows
            from collections import Counter
            users = Counter()
            rows = load_chain_rows(CHAIN)
            for rec in rows:
                uid = rec.get("user_identity")
                if uid:
                    users[uid] += 1
            if RECORDS_DIR.exists():
                for rfile in RECORDS_DIR.glob("*.record.json"):
                    try:
                        rec = json.loads(rfile.read_text(encoding="utf-8"))
                        uid = rec.get("user_identity")
                        if uid:
                            users[uid] += 1
                    except (json.JSONDecodeError, OSError):
                        continue
            _json_response(self, {
                "unique_users": len(users),
                "users": [{"identity": k, "count": v} for k, v in users.most_common()],
            })

        elif path == "/api/update-check":
            import urllib.request
            import urllib.error
            try:
                req = urllib.request.Request(
                    "https://api.github.com/repos/atested/governance-layer/releases/latest",
                    headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "atested-dashboard"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    release = json.loads(resp.read().decode("utf-8"))
                tag = release.get("tag_name", "").lstrip("v")
                _json_response(self, {
                    "latest_version": tag,
                    "current_version": "1.0.0",
                    "update_available": tag != "1.0.0" and bool(tag),
                    "release_url": release.get("html_url", ""),
                    "published_at": release.get("published_at", ""),
                })
            except Exception:
                _json_response(self, {
                    "latest_version": None,
                    "current_version": "1.0.0",
                    "update_available": False,
                    "release_url": "",
                    "error": "could not check for updates",
                })

        elif path == "/api/feedback":
            feedback_dir = RUNTIME / "LOGS" / "feedback"
            artifacts = []
            if feedback_dir.exists():
                for fp in sorted(feedback_dir.glob("fb_*.json"), reverse=True):
                    try:
                        artifacts.append(json.loads(fp.read_text(encoding="utf-8")))
                    except (json.JSONDecodeError, OSError):
                        continue
            _json_response(self, {"artifacts": artifacts[:100]})

        elif path == "/api/telemetry":
            telemetry_dir = RUNTIME / "LOGS" / "telemetry"
            artifacts = []
            if telemetry_dir.exists():
                for fp in sorted(telemetry_dir.glob("tm_*.json"), reverse=True):
                    try:
                        artifacts.append(json.loads(fp.read_text(encoding="utf-8")))
                    except (json.JSONDecodeError, OSError):
                        continue
            _json_response(self, {"artifacts": artifacts[:100]})

        elif path == "/api/telemetry/status":
            opt_in_file = RUNTIME / "telemetry_opt_in"
            opted_in = opt_in_file.exists() and opt_in_file.read_text(encoding="utf-8").strip() == "1"
            _json_response(self, {"opted_in": opted_in})

        elif path == "/api/notifications":
            self._handle_notifications_get()

        elif path == "/api/disclosure/status":
            self._handle_disclosure_status()

        elif path == "/api/identity/session":
            self._handle_identity_session()

        elif path == "/api/config":
            try:
                from registry_integrity import validate_registry_schema
                from licensing import resolve_posture

                registry_path = REPO / "capabilities" / "capability-registry.json"
                messaging_map_path = REPO / "capabilities" / "messaging-tool-map.v1.json"

                # Read capability registry
                registry_data = {}
                registry_hash = None
                if registry_path.exists():
                    try:
                        raw = registry_path.read_bytes()
                        import hashlib
                        registry_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
                        registry_data = json.loads(raw.decode("utf-8"))
                    except (json.JSONDecodeError, OSError) as exc:
                        registry_data = {"error": str(exc)}

                # Read messaging map
                messaging_map = {}
                if messaging_map_path.exists():
                    try:
                        messaging_map = json.loads(
                            messaging_map_path.read_text(encoding="utf-8")
                        )
                    except (json.JSONDecodeError, OSError):
                        messaging_map = {}

                # Resolve license posture
                posture = resolve_posture(RUNTIME)

                _json_response(self, {
                    "registry": registry_data,
                    "registry_hash": registry_hash,
                    "messaging_map": messaging_map,
                    "license_posture": posture,
                })
            except Exception as exc:
                _json_response(self, {"error": str(exc)}, 500)

        else:
            _json_response(self, {"error": "unknown endpoint"}, 404)


def main():
    global _DASHBOARD_TOKEN, _DASHBOARD_PORT, DASHBOARD_UI_DIR, _ASSET_VERSION

    # --ui-next flag: serve the new UI from dashboard/ui-next/
    if "--ui-next" in sys.argv:
        DASHBOARD_UI_DIR = DASHBOARD_UI_NEXT_DIR
        _ASSET_VERSION = _compute_asset_version()
        print("Dashboard: serving ui-next/", file=sys.stderr)

    port = int(os.environ.get("DASHBOARD_PORT", "9700"))
    _DASHBOARD_PORT = port

    # Generate a random bearer token for this session
    token = secrets.token_hex(32)
    _DASHBOARD_TOKEN = token
    print(f"Dashboard auth token: {token}", file=sys.stderr)

    # Write token to runtime dir so callers (e.g. MCP tool) can retrieve it
    runtime_dir = os.environ.get("GOV_RUNTIME_DIR", "")
    if runtime_dir:
        token_path = Path(runtime_dir) / "dashboard_token"
        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(token, encoding="utf-8")
        except OSError as exc:
            print(f"Warning: could not write dashboard_token: {exc}", file=sys.stderr)

    # Snapshot current source file mtimes so the first request doesn't
    # trigger a spurious reload.
    _check_and_reload()

    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
