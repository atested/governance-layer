#!/usr/bin/env python3
"""
peer_sharing.py — Peer-to-peer license sharing manager.

Manages both sharing and joining sides of the license sharing protocol.
Sharing machine starts a temporary HTTP server; requesting machine connects
via manual IP entry or UDP broadcast discovery.
"""

import json
import socket
import struct
import threading
import time
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_local_ip():
    """Best-effort local IP detection."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ---------------------------------------------------------------------------
# Sharing-side HTTP server
# ---------------------------------------------------------------------------

class _PeerSharingHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler for the temporary sharing server."""

    def log_message(self, format, *args):
        pass  # suppress default logging

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 4096:
            return None
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None

    def do_GET(self):
        mgr = self.server.manager

        if self.path == "/info":
            self._send_json({
                "hostname": mgr._sharing_hostname,
                "tier": mgr._sharing_tier,
                "license_id_prefix": (mgr._sharing_license_id or "")[:8],
                "fingerprint_prefix": (mgr._sharing_fingerprint or "")[:8],
            })
            return

        if self.path.startswith("/request-status/"):
            request_id = self.path[len("/request-status/"):]
            with mgr._lock:
                req = mgr._pending_requests.get(request_id)
            if not req:
                self._send_json({"error": "unknown request"}, 404)
                return
            resp = {"status": req["status"]}
            if req["status"] == "approved" and req.get("token"):
                resp["token"] = req["token"]
            self._send_json(resp)
            return

        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        mgr = self.server.manager

        if self.path == "/request-join":
            data = self._read_json()
            if data is None:
                self._send_json({"error": "invalid JSON"}, 400)
                return

            fingerprint = data.get("fingerprint", "")
            hostname = data.get("hostname", "unknown")
            request_id = str(uuid.uuid4())
            client_ip = self.client_address[0] if self.client_address else ""

            with mgr._lock:
                mgr._pending_requests[request_id] = {
                    "fingerprint": fingerprint,
                    "hostname": hostname,
                    "ip": client_ip,
                    "status": "pending",
                    "token": None,
                    "timestamp": time.time(),
                }

            self._send_json({"request_id": request_id, "status": "pending"})
            return

        self._send_json({"error": "not found"}, 404)


class _PeerSharingHTTPServer(HTTPServer):
    """HTTP server that holds a reference to the PeerSharingManager."""

    def __init__(self, manager, *args, **kwargs):
        self.manager = manager
        super().__init__(*args, **kwargs)


# ---------------------------------------------------------------------------
# PeerSharingManager
# ---------------------------------------------------------------------------

class PeerSharingManager:
    """Manages peer-to-peer license sharing and joining."""

    def __init__(self):
        self._lock = threading.Lock()

        # Sharing state
        self._sharing_state = "idle"  # idle | listening | stopped
        self._sharing_server = None
        self._sharing_thread = None
        self._sharing_timer = None
        self._sharing_hostname = ""
        self._sharing_tier = ""
        self._sharing_license_id = ""
        self._sharing_fingerprint = ""
        self._sharing_license_key = ""
        self._sharing_address = ""
        self._sharing_port = 0
        self._pending_requests = {}

        # Beacon state
        self._beacon_thread = None
        self._beacon_stop = threading.Event()

        # Joining state
        self._joining_state = "idle"  # idle | discovering | requesting | approved | denied | timeout
        self._join_target_address = ""
        self._join_request_id = ""
        self._join_result = {}

        # Discovery state
        self._discovery_thread = None
        self._discovery_stop = threading.Event()
        self._discovered_peers = []
        self._discovery_lock = threading.Lock()

    # -----------------------------------------------------------------------
    # Sharing side
    # -----------------------------------------------------------------------

    def start_sharing(self, license_key, tier, license_id, hostname, fingerprint):
        """Start the temporary sharing server."""
        with self._lock:
            if self._sharing_state == "listening":
                return {
                    "address": self._sharing_address,
                    "port": self._sharing_port,
                }

        self._sharing_hostname = hostname
        self._sharing_tier = tier
        self._sharing_license_id = license_id
        self._sharing_fingerprint = fingerprint
        self._sharing_license_key = license_key
        self._pending_requests = {}

        server = _PeerSharingHTTPServer(
            self,
            ("0.0.0.0", 0),
            _PeerSharingHandler,
        )
        port = server.server_address[1]
        local_ip = _get_local_ip()
        address = f"{local_ip}:{port}"

        self._sharing_server = server
        self._sharing_port = port
        self._sharing_address = address

        # Start server thread
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        self._sharing_thread = t

        # 5-minute auto-shutdown timer
        timer = threading.Timer(300, self.stop_sharing)
        timer.daemon = True
        timer.start()
        self._sharing_timer = timer

        # Start UDP beacon (best-effort)
        self._start_beacon(port, hostname, tier)

        with self._lock:
            self._sharing_state = "listening"

        return {"address": address, "port": port}

    def stop_sharing(self):
        """Stop the sharing server and beacon."""
        with self._lock:
            self._sharing_state = "stopped"

        if self._sharing_timer:
            self._sharing_timer.cancel()
            self._sharing_timer = None

        self._beacon_stop.set()

        if self._sharing_server:
            try:
                self._sharing_server.shutdown()
            except Exception:
                pass
            self._sharing_server = None

    def get_sharing_status(self):
        """Return current sharing state."""
        with self._lock:
            state = self._sharing_state
            reqs = dict(self._pending_requests)
        return {
            "state": state,
            "address": self._sharing_address if state == "listening" else "",
            "port": self._sharing_port if state == "listening" else 0,
            "pending_requests": reqs,
        }

    def approve_request(self, request_id, token):
        """Approve a pending join request and attach the license token."""
        with self._lock:
            req = self._pending_requests.get(request_id)
            if not req:
                return False
            req["status"] = "approved"
            req["token"] = token
            return True

    def deny_request(self, request_id):
        """Deny a pending join request."""
        with self._lock:
            req = self._pending_requests.get(request_id)
            if not req:
                return False
            req["status"] = "denied"
            return True

    # -----------------------------------------------------------------------
    # UDP beacon
    # -----------------------------------------------------------------------

    def _start_beacon(self, port, hostname, tier):
        """Start broadcasting UDP presence beacon."""
        self._beacon_stop.clear()
        packet = json.dumps({
            "proto": "atested-share-v1",
            "port": port,
            "hostname": hostname,
            "tier": tier,
        }).encode("utf-8")

        def _broadcast():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock.settimeout(1.0)
                while not self._beacon_stop.is_set():
                    try:
                        sock.sendto(packet, ("255.255.255.255", 19273))
                    except OSError:
                        pass
                    self._beacon_stop.wait(2.0)
                sock.close()
            except Exception:
                pass

        t = threading.Thread(target=_broadcast, daemon=True)
        t.start()
        self._beacon_thread = t

    # -----------------------------------------------------------------------
    # Joining side
    # -----------------------------------------------------------------------

    def start_joining(self, target_address, fingerprint, hostname):
        """Connect to a sharing machine and request to join."""
        import urllib.request

        # Normalize address
        addr = target_address.strip()
        if not addr.startswith("http"):
            addr = f"http://{addr}"

        # GET /info
        try:
            req = urllib.request.Request(f"{addr}/info", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                remote_info = json.loads(resp.read())
        except Exception as exc:
            self._joining_state = "idle"
            return {"error": f"Could not reach {target_address}: {exc}"}

        # POST /request-join
        join_body = json.dumps({
            "fingerprint": fingerprint,
            "hostname": hostname,
        }).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{addr}/request-join",
                data=join_body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                join_resp = json.loads(resp.read())
        except Exception as exc:
            self._joining_state = "idle"
            return {"error": f"Join request failed: {exc}"}

        self._join_target_address = addr
        self._join_request_id = join_resp.get("request_id", "")
        self._joining_state = "requesting"
        self._join_result = {
            "request_id": self._join_request_id,
            "status": "pending",
            "remote_info": remote_info,
            "address": target_address,
        }
        return {
            "request_id": self._join_request_id,
            "remote_info": remote_info,
        }

    def poll_join_status(self):
        """Poll the sharing machine for join request status."""
        import urllib.request

        if not self._join_request_id or not self._join_target_address:
            return self._join_result or {"status": "idle"}

        try:
            url = f"{self._join_target_address}/request-status/{self._join_request_id}"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
        except Exception:
            # Server may have shut down
            if self._joining_state == "requesting":
                self._joining_state = "timeout"
                self._join_result["status"] = "timeout"
            return self._join_result

        status = data.get("status", "pending")
        self._join_result["status"] = status

        if status == "approved":
            self._joining_state = "approved"
            self._join_result["token"] = data.get("token", "")
        elif status == "denied":
            self._joining_state = "denied"

        return self._join_result

    # -----------------------------------------------------------------------
    # Discovery
    # -----------------------------------------------------------------------

    def start_discovery(self):
        """Start listening for UDP beacon broadcasts."""
        self._discovery_stop.clear()
        with self._discovery_lock:
            self._discovered_peers = []

        def _listen():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                # SO_REUSEPORT on macOS
                try:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except (AttributeError, OSError):
                    pass
                sock.bind(("", 19273))
                sock.settimeout(1.0)

                seen = set()
                while not self._discovery_stop.is_set():
                    try:
                        data, addr = sock.recvfrom(1024)
                        try:
                            pkt = json.loads(data)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        if pkt.get("proto") != "atested-share-v1":
                            continue
                        peer_addr = f"{addr[0]}:{pkt.get('port', 0)}"
                        if peer_addr not in seen:
                            seen.add(peer_addr)
                            with self._discovery_lock:
                                self._discovered_peers.append({
                                    "address": peer_addr,
                                    "hostname": pkt.get("hostname", ""),
                                    "tier": pkt.get("tier", ""),
                                })
                    except socket.timeout:
                        continue
                sock.close()
            except Exception:
                pass

        self._joining_state = "discovering"
        t = threading.Thread(target=_listen, daemon=True)
        t.start()
        self._discovery_thread = t

    def stop_discovery(self):
        """Stop the UDP discovery listener."""
        self._discovery_stop.set()
        if self._joining_state == "discovering":
            self._joining_state = "idle"

    def get_discovered_peers(self):
        """Return list of discovered peers."""
        with self._discovery_lock:
            return list(self._discovered_peers)
