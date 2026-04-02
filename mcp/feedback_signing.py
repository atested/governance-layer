#!/usr/bin/env python3
"""Signed feedback and telemetry artifact builders for Atested."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


ATESTED_VERSION = "1.0.0"


def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _sign_artifact(artifact_bytes: bytes, signing_key_path: str) -> Dict[str, Any]:
    """Sign artifact bytes with Ed25519. Returns signature + key_id or error."""
    if not signing_key_path:
        return {"signed": False, "error": "no signing key configured"}
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        pk_bytes = Path(signing_key_path).read_bytes()
        pk = serialization.load_pem_private_key(pk_bytes, password=None)
        if not isinstance(pk, Ed25519PrivateKey):
            return {"signed": False, "error": "signing key is not Ed25519"}
        raw_pub = pk.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        key_id = "ed25519:" + hashlib.sha256(raw_pub).hexdigest()
        sig = pk.sign(artifact_bytes)
        signature = _b64url_nopad(sig)
        # Also export the public key PEM for verification by the remote endpoint
        pub_pem = pk.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        return {"signed": True, "signature": signature, "signing_key_id": key_id, "public_key_pem": pub_pem}
    except Exception as exc:
        return {"signed": False, "error": str(exc)}


def build_feedback_artifact(
    message: str,
    experience_note: str = "",
    permission_to_use: bool = False,
    runtime_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build a signed feedback artifact.
    
    Args:
        message: Free-form feedback text from the operator.
        experience_note: Optional case study text ("What has Atested helped you avoid or improve?").
        permission_to_use: If True, Atested may use the feedback anonymously in product materials.
        runtime_root: Path to the governance runtime directory.
    
    Returns:
        Dict with the complete signed artifact.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact_id = f"fb_{uuid.uuid4().hex[:16]}"
    
    # Resolve installation metadata
    from licensing import resolve_posture
    posture = {}
    if runtime_root and runtime_root.exists():
        try:
            posture = resolve_posture(runtime_root)
        except Exception:
            pass
    
    artifact = {
        "artifact_type": "feedback",
        "artifact_id": artifact_id,
        "artifact_version": "1.0",
        "timestamp": now,
        "message": message,
        "version": ATESTED_VERSION,
        "tier": posture.get("license_tier", "unknown"),
        "license_status": posture.get("license_status", "unknown"),
    }
    
    if experience_note:
        artifact["experience_note"] = experience_note
        artifact["permission_to_use"] = permission_to_use
    
    # Compute artifact hash
    artifact_bytes = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    artifact_hash = f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}"
    artifact["artifact_hash"] = artifact_hash
    
    # Sign
    signing_key_path = os.environ.get("GOV_SIGNING_KEY_PATH", "")
    sig_result = _sign_artifact(artifact_bytes, signing_key_path)
    artifact["signature"] = sig_result.get("signature")
    artifact["signing_key_id"] = sig_result.get("signing_key_id")
    if sig_result.get("public_key_pem"):
        artifact["public_key_pem"] = sig_result["public_key_pem"]
    artifact["signed"] = sig_result.get("signed", False)
    
    return artifact


def build_telemetry_artifact(
    chain_path: Optional[Path] = None,
    runtime_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build a signed telemetry artifact with aggregated usage counts.
    
    Scans the decision chain to produce:
    - total_allow: cumulative ALLOW decisions
    - total_deny: cumulative DENY decisions (prevented actions)
    - total_deterministic: cumulative deterministic decisions
    - total_judgment: cumulative judgment decisions
    - version, timestamp, chain_hash, signature
    
    No user identities, file paths, action targets, or org names are included.
    """
    from collections import Counter
    
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    artifact_id = f"tm_{uuid.uuid4().hex[:16]}"
    
    total_allow = 0
    total_deny = 0
    total_deterministic = 0
    total_judgment = 0
    chain_hash = None
    
    if chain_path and chain_path.exists():
        last_line = ""
        for line in chain_path.read_text(encoding="utf-8").strip().splitlines():
            if not line.strip():
                continue
            last_line = line.strip()
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            decision = rec.get("policy_decision", "")
            if decision == "ALLOW":
                total_allow += 1
            elif decision == "DENY":
                total_deny += 1
            # Classify deterministic vs judgment
            # Judgment decisions have approval-related fields or explicit judgment markers
            if decision in ("ALLOW", "DENY"):
                if rec.get("approval_id") or rec.get("requires_judgment"):
                    total_judgment += 1
                else:
                    total_deterministic += 1
        # Chain hash from last record
        if last_line:
            try:
                chain_hash = json.loads(last_line).get("record_hash")
            except json.JSONDecodeError:
                pass
    
    # Resolve posture for version/tier (no identifying info sent)
    from licensing import resolve_posture
    posture = {}
    if runtime_root and runtime_root.exists():
        try:
            posture = resolve_posture(runtime_root)
        except Exception:
            pass
    
    artifact = {
        "artifact_type": "telemetry",
        "artifact_id": artifact_id,
        "artifact_version": "1.0",
        "timestamp": now,
        "total_allow": total_allow,
        "total_deny": total_deny,
        "total_deterministic": total_deterministic,
        "total_judgment": total_judgment,
        "version": ATESTED_VERSION,
        "chain_hash": chain_hash,
    }
    
    # Compute artifact hash
    artifact_bytes = json.dumps(artifact, sort_keys=True, separators=(",", ":")).encode("utf-8")
    artifact_hash = f"sha256:{hashlib.sha256(artifact_bytes).hexdigest()}"
    artifact["artifact_hash"] = artifact_hash
    
    # Sign
    signing_key_path = os.environ.get("GOV_SIGNING_KEY_PATH", "")
    sig_result = _sign_artifact(artifact_bytes, signing_key_path)
    artifact["signature"] = sig_result.get("signature")
    artifact["signing_key_id"] = sig_result.get("signing_key_id")
    if sig_result.get("public_key_pem"):
        artifact["public_key_pem"] = sig_result["public_key_pem"]
    artifact["signed"] = sig_result.get("signed", False)
    
    return artifact


def write_artifact(artifact: Dict[str, Any], artifact_dir: Path) -> Path:
    """Write an artifact to disk with 0600 permissions. Returns the file path."""
    import stat as _stat
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_id = artifact.get("artifact_id", f"unknown_{uuid.uuid4().hex[:8]}")
    out_path = artifact_dir / f"{artifact_id}.json"
    content = json.dumps(artifact, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    fd = os.open(str(out_path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC,
                  _stat.S_IRUSR | _stat.S_IWUSR)
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    return out_path


def send_artifact_to_remote(artifact: Dict[str, Any], endpoint_url: str) -> Dict[str, Any]:
    """POST a signed artifact to the remote endpoint. Returns response data."""
    import urllib.request
    import urllib.error
    
    # Strip public_key_pem from the sent payload — send it separately in a header
    payload = {k: v for k, v in artifact.items() if k != "public_key_pem"}
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json",
    }
    # Include public key for verification
    if artifact.get("public_key_pem"):
        headers["X-Signing-Public-Key"] = _b64url_nopad(artifact["public_key_pem"].encode("utf-8"))
    
    try:
        req = urllib.request.Request(endpoint_url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))
            return {"sent": True, "status": resp.status, "response": resp_data}
    except urllib.error.HTTPError as exc:
        try:
            err_body = exc.read().decode("utf-8")
            err_data = json.loads(err_body)
        except Exception:
            err_data = {"raw": err_body if 'err_body' in dir() else str(exc)}
        return {"sent": False, "status": exc.code, "error": err_data}
    except Exception as exc:
        return {"sent": False, "status": None, "error": str(exc)}
