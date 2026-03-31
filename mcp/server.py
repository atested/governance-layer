#!/usr/bin/env python3
import base64
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
import uuid
from pathlib import Path
from typing import Any, Callable, Dict

from mcp.server.fastmcp import FastMCP

REPO = Path(__file__).resolve().parents[1]
APPEND = REPO / "scripts" / "append-record-runtime.sh"
CAP_REGISTRY_PATH = REPO / "capabilities" / "capability-registry.json"

VERIFY_CHAIN = REPO / "scripts" / "verify-chain.py"
RUNTIME = Path(os.environ.get("GOV_RUNTIME_DIR", "/Volumes/SSD/archive/gov/runtime")).resolve()
INTENTS_DIR = RUNTIME / "LOGS" / "intents"
RECORDS_DIR = RUNTIME / "LOGS" / "records"
CHAIN = RUNTIME / "LOGS" / "decision-chain.jsonl"

mcp = FastMCP("governance-broker")

def _load_cap_registry() -> dict:
    with open(CAP_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def _cap_container(reg: dict) -> dict:
    # Handle both dict and array structures
    if "tools" in reg and isinstance(reg["tools"], list):
        # Convert array to dict keyed by tool name
        return {t.get("tool") or t.get("capability_class"): t for t in reg["tools"]}
    if "FS_WRITE" in reg:
        return reg
    for k in ("tools", "capabilities"):
        if k in reg and isinstance(reg[k], dict) and "FS_WRITE" in reg[k]:
            return reg[k]
    return reg

_CAP_REG = _load_cap_registry()
_CAPS = _cap_container(_CAP_REG)

def get_capability(capability: str) -> dict:
    if capability not in _CAPS:
        raise KeyError(f"Unknown capability: {capability}")
    return _CAPS[capability]

def normalize_args(capability: str, args: dict) -> tuple:
    """Normalize args based on capability spec. Returns (norm_args, constraints_or_error)."""
    cap = get_capability(capability)
    caps = cap.get("caps", {}) or {}
    spec = cap.get("args", {}) or {}
    required = spec.get("required", []) or []

    missing = [k for k in required if k not in args or args.get(k) is None]
    if missing:
        return args, {"_missing": missing}

    out = dict(args)

    if capability == "FS_LIST":
        dflt = int(caps.get("max_entries_default", 100))
        hard = int(caps.get("max_entries_hard", 500))
        try:
            n = int(out.get("max_entries", dflt))
        except Exception:
            n = dflt
        if n < 1:
            n = 1
        if n > hard:
            n = hard
        out["max_entries"] = n

        if not bool(caps.get("include_hidden_allowed", False)):
            out["include_hidden"] = False

    if capability == "FS_READ":
        dflt = int(caps.get("max_bytes_default", cap.get("max_bytes_default", 4096)))
        hard = int(caps.get("max_bytes_hard", cap.get("max_bytes_hard", 65536)))
        try:
            mb = int(out.get("max_bytes", dflt))
        except Exception:
            mb = dflt
        if mb < 1:
            mb = 1
        if mb > hard:
            mb = hard
        out["max_bytes"] = mb

        try:
            off = int(out.get("offset", 0))
        except Exception:
            off = 0
        if off < int(caps.get("offset_min", 0)):
            off = int(caps.get("offset_min", 0))
        out["offset"] = off

        out["as_text"] = bool(out.get("as_text", True))

    if capability == "FS_WRITE":
        out["overwrite"] = bool(out.get("overwrite", False))
        if not bool(caps.get("request_executable_allowed", False)):
            out["request_executable"] = False
        else:
            out["request_executable"] = bool(out.get("request_executable", False))

    if capability == "FS_MKDIR":
        out["parents"] = bool(out.get("parents", False))
        out["exist_ok"] = bool(out.get("exist_ok", False))

    if capability == "FS_MOVE":
        out["overwrite"] = bool(out.get("overwrite", False))

    # Build constraints dict (excluding content)
    constraints = {}
    for k, v in out.items():
        if k != "content":
            constraints[k] = v

    return out, constraints

def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")



def _quarantine_chain(reason: str) -> str:
    # Move the current chain to a quarantine folder with timestamp.
    # Returns the quarantined file path (string). Does not delete evidence.
    if not CHAIN.exists():
        return ""
    qdir = RUNTIME / "LOGS" / "quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dst = qdir / f"decision-chain.{ts}.jsonl"
    CHAIN.rename(dst)
    # Write a small marker file alongside for operator context
    (qdir / f"decision-chain.{ts}.reason.txt").write_text(reason + "\n", encoding="utf-8")
    return str(dst)

def _verify_chain() -> None:
    # Fail closed if the runtime chain is broken.
    if not CHAIN.exists():
        return
    proc = subprocess.run(
        ["python3", str(VERIFY_CHAIN), str(CHAIN)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        msg = (proc.stdout.strip() or proc.stderr.strip() or "unknown")
        qpath = _quarantine_chain("CHAIN_VERIFY_FAIL: " + msg)
        raise RuntimeError("CHAIN_VERIFY_FAIL: " + msg + (" | quarantined=" + qpath if qpath else ""))

def _append_decision(intent_path: Path) -> Dict[str, Any]:
    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(RUNTIME)

    proc = subprocess.run(
        [str(APPEND), str(intent_path)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    rec = json.loads(proc.stdout.strip().splitlines()[-1])
    return rec

def governed_tool(
    tool_name: str,
    args: Dict[str, Any],
    intent: Dict[str, Any],
    action: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Governed tool wrapper implementing verify→append→verify invariants.

    Args:
        tool_name: Tool identifier (e.g., "FS_WRITE")
        args: Tool arguments to log in decision record
        intent: Intent structure for decision record
        action: Callable that performs the actual tool action if ALLOW.
                Takes the decision record and normalized args, returns action-specific result dict.

    Returns:
        Dict with policy_decision, policy_reasons, decision_record, and optional action results.
    """
    req_id = str(uuid.uuid4())

    # Normalize args from capability spec
    norm_args, norm_constraints = normalize_args(tool_name, args)
    if isinstance(norm_constraints, dict) and norm_constraints.get("_missing"):
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-MISSING-INTENT-FIELDS", "detail": {"missing": norm_constraints.get("_missing")}}],
            "decision_record": None,
        }

    intent_obj = {
        "tool": tool_name,
        "args": norm_args,
        "intent": intent,
    }

    INTENTS_DIR.mkdir(parents=True, exist_ok=True)
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)

    intent_path = INTENTS_DIR / f"{req_id}.intent.json"
    _write_json(intent_path, intent_obj)

    # Verify chain integrity BEFORE appending (fail closed)
    _verify_chain()

    # Append decision record to runtime chain (tamper-evident sequence)
    rec = _append_decision(intent_path)

    # Verify chain integrity AFTER appending (fail closed)
    _verify_chain()

    # Persist a pretty record copy (optional convenience, not part of the chain)
    record_path = RECORDS_DIR / f"{req_id}.record.json"
    _write_json(record_path, rec)

    decision = rec.get("policy_decision")
    if decision != "ALLOW":
        return {
            "policy_decision": decision,
            "policy_reasons": rec.get("policy_reasons", []),
            "decision_record": rec,
        }

    # Execute the action
    action_result = action(rec, norm_args)

    return {
        "policy_decision": "ALLOW",
        "policy_reasons": rec.get("policy_reasons", []),
        "decision_record": rec,
        **action_result
    }

@mcp.tool()
def fs_write(path: str, content: str, overwrite: bool = False, request_executable: bool = False) -> Dict[str, Any]:
    """
    Governed file write. Returns DENY with a full decision record on policy failure.
    On ALLOW, performs the write and returns write_result + decision_record.
    """
    args = {
        "path": path,
        "content": content,
        "overwrite": overwrite,
        "request_executable": request_executable,
    }

    intent = {
        "goal": "Write file via MCP fs_write tool.",
        "constraints": {
            "overwrite": bool(overwrite),
        },
        "requested_action": "FS_WRITE",
        "inputs": [],
        "expected_outputs": [
            {"ref": "file:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual file write if policy allows."""
        # Enforce executable restriction even if caller asks (Phase 1)
        if bool(_args.get("request_executable", False)):
            # If policy allowed but caller asks executable, treat as deny-at-action
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-EXECUTABLE-DISALLOWED", "detail": {"requested": True}}],
            }

        target = Path(path)
        if not target.is_absolute():
            # Phase 1: absolute paths only
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            }

        # Perform write
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "wb" if isinstance(content, (bytes, bytearray)) else "w"
        if (not bool(_args.get("overwrite", False))) and target.exists():
            return {
                "policy_decision": "DENY",
                "policy_reasons": [{"code": "RC-FS-OVERWRITE-DISALLOWED", "detail": {"path": str(target)}}],
            }

        if mode == "w":
            target.write_text(content, encoding="utf-8")
            n = len(content.encode("utf-8"))
        else:
            target.write_bytes(content)
            n = len(content)

        return {
            "write_result": {
                "bytes_written": n,
                "canonical_path": str(target.resolve()),
            }
        }

    return governed_tool("FS_WRITE", args, intent, _action)

@mcp.tool()
def fs_list(path: str, max_entries: int = 100, include_hidden: bool = False) -> Dict[str, Any]:
    """
    Governed directory listing (names/types only).
    Phase 2: include_hidden must be False.
    """
    # Pre-check: absolute path required
    target = Path(path)
    if not target.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            "decision_record": None,
        }

    # Clamp max_entries
    try:
        nmax = int(max_entries)
    except Exception:
        nmax = 100
    if nmax < 1:
        nmax = 1
    if nmax > 500:
        nmax = 500

    args = {
        "path": path,
        "max_entries": nmax,
        "include_hidden": bool(include_hidden),
    }

    intent = {
        "goal": "List directory via MCP fs_list tool.",
        "constraints": {
            "max_entries": nmax,
            "include_hidden": bool(include_hidden),
        },
        "requested_action": "FS_LIST",
        "inputs": [],
        "expected_outputs": [
            {"ref": "directory:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual directory listing if policy allows."""
        # Defense-in-depth: policy-eval should have denied include_hidden
        # This is an operational error if reached (policy should prevent)
        if bool(_args.get("include_hidden", False)):
            return {
                "list_error": {"code": "E-INCLUDE-HIDDEN-NOT-SUPPORTED", "detail": {"include_hidden": True}},
                "list_result": None,
            }

        # Check existence and type (runtime check for races)
        # Policy-eval checks this deterministically; this catches filesystem races
        if not target.exists() or not target.is_dir():
            return {
                "list_error": {"code": "E-NOT-A-DIRECTORY", "detail": {"path": str(target)}},
                "list_result": None,
            }

        # List directory entries
        entries = []
        max_entries = int(_args.get("max_entries", 100))
        with os.scandir(target) as it:
            for ent in it:
                name = ent.name
                # Phase 2: never include hidden entries
                if name.startswith("."):
                    continue
                if ent.is_dir(follow_symlinks=False):
                    typ = "dir"
                elif ent.is_file(follow_symlinks=False):
                    typ = "file"
                else:
                    typ = "other"
                entries.append({"name": name, "type": typ})
                if len(entries) >= max_entries:
                    break

        return {
            "list_result": {
                "canonical_path": str(target.resolve()),
                "entries": entries,
            }
        }

    return governed_tool("FS_LIST", args, intent, _action)

@mcp.tool()
def fs_read(path: str, max_bytes: int = 4096, offset: int = 0, as_text: bool = True) -> Dict[str, Any]:
    """
    Governed file read with strict caps.
    Returns content (capped) plus sha256 hash.
    """
    target = Path(path)
    if not target.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            "decision_record": None,
        }

    # Clamp max_bytes
    try:
        mb = int(max_bytes)
    except Exception:
        mb = 4096
    if mb < 1:
        mb = 1
    if mb > 65536:
        mb = 65536

    # Clamp offset
    try:
        off = int(offset)
    except Exception:
        off = 0
    if off < 0:
        off = 0

    args = {
        "path": path,
        "max_bytes": mb,
        "offset": off,
        "as_text": bool(as_text),
    }

    intent = {
        "goal": "Read file via MCP fs_read tool (capped).",
        "constraints": {
            "max_bytes": mb,
            "offset": off,
            "as_text": bool(as_text),
        },
        "requested_action": "FS_READ",
        "inputs": [],
        "expected_outputs": [
            {"ref": "file:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual file read if policy allows."""
        # Operational (race/perm) errors only; policy reasons come from policy-eval.py
        read_offset = int(_args.get("offset", 0))
        read_max_bytes = int(_args.get("max_bytes", 4096))
        read_as_text = bool(_args.get("as_text", True))

        try:
            data = b""
            with open(target, "rb") as f:
                f.seek(read_offset)
                data = f.read(read_max_bytes)
        except Exception as e:
            return {
                "read_error": {"code": "E-READ-FAILED", "detail": {"error": str(e)}},
                "read_result": None,
            }

        h = hashlib.sha256(data).hexdigest()
        result = {
            "canonical_path": str(target.resolve()),
            "bytes_read": len(data),
            "content_hash_sha256": "sha256:" + h,
            "offset": read_offset,
            "max_bytes": read_max_bytes,
        }

        if read_as_text:
            result["content"] = data.decode("utf-8", errors="replace")
        else:
            result["content_b64"] = base64.b64encode(data).decode("ascii")

        return {"read_result": result}

    return governed_tool("FS_READ", args, intent, _action)

@mcp.tool()
def fs_mkdir(path: str, parents: bool = False, exist_ok: bool = False) -> Dict[str, Any]:
    """
    Governed directory creation.
    parents=True creates intermediate directories (mkdir -p equivalent).
    exist_ok=True silently succeeds if directory already exists.
    Path must be within the registry allowlist; hidden paths are denied.
    """
    target = Path(path)
    if not target.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": path}}],
            "decision_record": None,
        }

    args = {
        "path": path,
        "parents": bool(parents),
        "exist_ok": bool(exist_ok),
    }

    intent = {
        "goal": "Create directory via MCP fs_mkdir tool.",
        "constraints": {
            "parents": bool(parents),
            "exist_ok": bool(exist_ok),
        },
        "requested_action": "FS_MKDIR",
        "inputs": [],
        "expected_outputs": [
            {"ref": "directory:path", "value": path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual directory creation if policy allows."""
        canonical = target.resolve()
        use_parents = bool(_args.get("parents", False))
        use_exist_ok = bool(_args.get("exist_ok", False))
        try:
            canonical.mkdir(parents=use_parents, exist_ok=use_exist_ok)
        except FileExistsError:
            return {
                "mkdir_error": {"code": "E-DIR-EXISTS", "detail": {"canonical_path": str(canonical)}},
                "mkdir_result": None,
            }
        except FileNotFoundError:
            return {
                "mkdir_error": {"code": "E-PARENT-NOT-FOUND", "detail": {"canonical_path": str(canonical)}},
                "mkdir_result": None,
            }
        except Exception as e:
            return {
                "mkdir_error": {"code": "E-MKDIR-FAILED", "detail": {"error": str(e)}},
                "mkdir_result": None,
            }
        return {
            "mkdir_result": {
                "canonical_path": str(canonical),
                "parents": use_parents,
                "exist_ok": use_exist_ok,
            }
        }

    return governed_tool("FS_MKDIR", args, intent, _action)


@mcp.tool()
def fs_move(src_path: str, dst_path: str, overwrite: bool = False) -> Dict[str, Any]:
    """
    Governed file/directory move.
    Both src and dst must be within the registry allowlist and within the same root.
    overwrite is denied by default (caps.overwrite_allowed=false).
    """
    src = Path(src_path)
    dst = Path(dst_path)
    if not src.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": src_path}}],
            "decision_record": None,
        }
    if not dst.is_absolute():
        return {
            "policy_decision": "DENY",
            "policy_reasons": [{"code": "RC-FS-PATH-ABSOLUTE-REQUIRED", "detail": {"path": dst_path}}],
            "decision_record": None,
        }

    args = {
        "src_path": src_path,
        "dst_path": dst_path,
        "overwrite": bool(overwrite),
    }

    intent = {
        "goal": "Move file or directory via MCP fs_move tool.",
        "constraints": {
            "overwrite": bool(overwrite),
        },
        "requested_action": "FS_MOVE",
        "inputs": [{"ref": "file:src_path", "value": src_path}],
        "expected_outputs": [
            {"ref": "file:dst_path", "value": dst_path}
        ]
    }

    def _action(rec: Dict[str, Any], _args: Dict[str, Any]) -> Dict[str, Any]:
        """Perform the actual move if policy allows."""
        use_overwrite = bool(_args.get("overwrite", False))
        src_canon = src.resolve()
        dst_canon = dst.resolve()

        if not src_canon.exists():
            return {
                "move_error": {"code": "E-SRC-NOT-FOUND", "detail": {"src_path": str(src_canon)}},
                "move_result": None,
            }

        if dst_canon.exists() and not use_overwrite:
            return {
                "move_error": {"code": "E-DST-EXISTS", "detail": {"dst_path": str(dst_canon)}},
                "move_result": None,
            }

        try:
            shutil.move(str(src_canon), str(dst_canon))
        except Exception as e:
            return {
                "move_error": {"code": "E-MOVE-FAILED", "detail": {"error": str(e)}},
                "move_result": None,
            }

        return {
            "move_result": {
                "canonical_src_path": str(src_canon),
                "canonical_dst_path": str(dst_canon),
                "overwrite": use_overwrite,
            }
        }

    return governed_tool("FS_MOVE", args, intent, _action)


if __name__ == "__main__":
    mcp.run()
