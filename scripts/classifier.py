#!/usr/bin/env python3
"""
classifier.py — Evidence-based operation classifier for GovMCP v2.

Classifies any tool call by examining its parameters (evidence inference)
rather than relying on tool names or agent-declared manifests.

Returns a classification dict:
    {
        "action_type": str,       # read, write, delete, execute, network, ...
        "targets": [str, ...],    # file paths, URLs, commands, etc.
        "scope": str,             # local, repository, system, remote, privileged
        "confidence_tier": int,   # 1=direct, 2=inferred, 3=opaque, 4=uninspectable
        "evidence": {             # what the classifier observed
            "source": str,        # how classification was determined
            "details": dict,      # classifier-specific metadata
        },
        "original_tool": str,     # the tool name as received
    }

Design reference: docs/design/govmcp-v2-design-revised.md §4.2
"""

import re
from pathlib import PurePosixPath
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Action types
# ---------------------------------------------------------------------------

ACTION_READ = "read"
ACTION_WRITE = "write"
ACTION_DELETE = "delete"
ACTION_EXECUTE = "execute"
ACTION_NETWORK = "network"
ACTION_MOVE = "move"
ACTION_LIST = "list"
ACTION_CREATE_DIR = "create_directory"
ACTION_CONFIG = "configuration_change"
ACTION_CREDENTIAL = "credential_access"
ACTION_AGENT_INTERNAL = "agent_internal"
ACTION_UNKNOWN = "unknown"

# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------

SCOPE_LOCAL = "local"
SCOPE_REPOSITORY = "repository"
SCOPE_SYSTEM = "system"
SCOPE_REMOTE = "remote"
SCOPE_PRIVILEGED = "privileged"

# ---------------------------------------------------------------------------
# Confidence tiers
# ---------------------------------------------------------------------------

TIER_DIRECT = 1       # Effects fully visible in parameters
TIER_INFERRED = 2     # Primary effects reliably inferred
TIER_OPAQUE = 3       # Entry point visible, internal behavior unknown
TIER_UNINSPECTABLE = 4  # Encoded/obfuscated/adversarial

# ---------------------------------------------------------------------------
# Evidence extraction patterns
# ---------------------------------------------------------------------------

_URL_PATTERN = re.compile(
    r"https?://[^\s\"'<>]+", re.IGNORECASE
)

_SENSITIVE_PATH_PATTERNS = [
    re.compile(r"^/etc/"),
    re.compile(r"^~?/\.ssh/"),
    re.compile(r"^~?/\.gnupg/"),
    re.compile(r"^~?/\.aws/"),
    re.compile(r"^~?/\.config/"),
    re.compile(r"/\.env$"),
    re.compile(r"/credentials"),
    re.compile(r"/secrets?/"),
    re.compile(r"/tokens?$"),
    re.compile(r"/private[_-]?key"),
]

_NETWORK_COMMANDS = frozenset({
    "curl", "wget", "ssh", "scp", "rsync", "nc", "ncat", "telnet",
    "ftp", "sftp", "ping", "dig", "nslookup", "host",
})

_DESTRUCTIVE_COMMANDS = frozenset({
    "rm", "rmdir", "shred", "unlink",
})

_PACKAGE_MANAGERS = frozenset({
    "npm", "yarn", "pnpm", "pip", "pip3", "pipx", "conda",
    "gem", "cargo", "go", "brew", "apt", "apt-get", "yum", "dnf",
    "pacman", "apk",
})

_INTERPRETERS = frozenset({
    "python", "python3", "node", "ruby", "perl", "php", "lua",
    "deno", "bun", "bash", "sh", "zsh", "fish", "dash",
})

_BASE64_PATTERN = re.compile(
    r"^[A-Za-z0-9+/]{20,}={0,2}$"
)

_HEX_BLOB_PATTERN = re.compile(
    r"^[0-9a-fA-F]{40,}$"
)

# Well-known Tier 2 commands with understood side effects
_TIER2_COMMAND_MAP = {
    "git": {
        "push": {"action": ACTION_NETWORK, "scope": SCOPE_REMOTE},
        "pull": {"action": ACTION_NETWORK, "scope": SCOPE_REMOTE},
        "fetch": {"action": ACTION_NETWORK, "scope": SCOPE_REMOTE},
        "clone": {"action": ACTION_NETWORK, "scope": SCOPE_REMOTE},
        "commit": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "add": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "checkout": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "reset": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "merge": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "rebase": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "branch": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "tag": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "stash": {"action": ACTION_WRITE, "scope": SCOPE_REPOSITORY},
        "status": {"action": ACTION_READ, "scope": SCOPE_REPOSITORY},
        "log": {"action": ACTION_READ, "scope": SCOPE_REPOSITORY},
        "diff": {"action": ACTION_READ, "scope": SCOPE_REPOSITORY},
        "show": {"action": ACTION_READ, "scope": SCOPE_REPOSITORY},
    },
    "docker": {
        "run": {"action": ACTION_EXECUTE, "scope": SCOPE_SYSTEM},
        "build": {"action": ACTION_EXECUTE, "scope": SCOPE_SYSTEM},
        "push": {"action": ACTION_NETWORK, "scope": SCOPE_REMOTE},
        "pull": {"action": ACTION_NETWORK, "scope": SCOPE_REMOTE},
        "exec": {"action": ACTION_EXECUTE, "scope": SCOPE_SYSTEM},
        "rm": {"action": ACTION_DELETE, "scope": SCOPE_SYSTEM},
        "stop": {"action": ACTION_EXECUTE, "scope": SCOPE_SYSTEM},
        "kill": {"action": ACTION_EXECUTE, "scope": SCOPE_SYSTEM},
    },
    "make": {"__default__": {"action": ACTION_EXECUTE, "scope": SCOPE_LOCAL}},
    "pytest": {"__default__": {"action": ACTION_EXECUTE, "scope": SCOPE_LOCAL}},
    "jest": {"__default__": {"action": ACTION_EXECUTE, "scope": SCOPE_LOCAL}},
}


# ---------------------------------------------------------------------------
# Path extraction from parameters
# ---------------------------------------------------------------------------

def _extract_file_paths(args: dict) -> list[str]:
    """Extract file paths from tool parameters."""
    paths = []
    # Common parameter names for file paths
    for key in ("file_path", "path", "src", "dst", "source", "destination",
                "filename", "filepath", "target", "directory", "dir",
                "src_path", "dst_path", "old_path", "new_path"):
        val = args.get(key)
        if isinstance(val, str) and val and ("/" in val or val.startswith("~")):
            paths.append(val)
    return paths


def _extract_urls(args: dict) -> list[str]:
    """Extract URLs from tool parameters."""
    urls = []
    for val in args.values():
        if isinstance(val, str):
            urls.extend(_URL_PATTERN.findall(val))
    return urls


def _is_sensitive_path(path: str) -> bool:
    """Check if a path targets a sensitive location."""
    for pattern in _SENSITIVE_PATH_PATTERNS:
        if pattern.search(path):
            return True
    return False


def _path_scope(path: str) -> str:
    """Determine scope from a file path."""
    if _is_sensitive_path(path):
        return SCOPE_PRIVILEGED
    if path.startswith("/etc/") or path.startswith("/usr/") or path.startswith("/var/"):
        return SCOPE_SYSTEM
    return SCOPE_LOCAL


# ---------------------------------------------------------------------------
# Command analysis (for Bash/shell execution)
# ---------------------------------------------------------------------------

def _parse_command(command: str) -> dict:
    """Parse a shell command string into structured components."""
    command = command.strip()
    if not command:
        return {"program": "", "args": [], "raw": command}

    # Handle command chaining — analyze the first command
    # but note the full chain for evidence
    parts = command.split()
    program = parts[0].split("/")[-1]  # basename
    return {
        "program": program,
        "args": parts[1:],
        "raw": command,
    }


def _detect_encoded_payloads(args: dict) -> bool:
    """Detect base64-encoded or hex-encoded payloads that suggest obfuscation."""
    for val in args.values():
        if not isinstance(val, str):
            continue
        # Check each whitespace-delimited token
        for token in val.split():
            if len(token) > 40:
                if _BASE64_PATTERN.match(token):
                    return True
                if _HEX_BLOB_PATTERN.match(token):
                    return True
    return False


def _classify_command(command: str) -> dict:
    """Classify a shell command into action type, scope, and tier."""
    parsed = _parse_command(command)
    program = parsed["program"]
    args = parsed["args"]

    # Check for pipe chains or command substitution — increases opacity
    has_pipes = "|" in command
    has_subshell = "$(" in command or "`" in command
    has_redirect = ">" in command or ">>" in command

    # Network commands → Tier 2
    if program in _NETWORK_COMMANDS:
        urls = _URL_PATTERN.findall(command)
        return {
            "action_type": ACTION_NETWORK,
            "targets": urls or [command],
            "scope": SCOPE_REMOTE,
            "confidence_tier": TIER_INFERRED,
            "evidence_source": "command_network",
        }

    # Destructive commands → Tier 2
    if program in _DESTRUCTIVE_COMMANDS:
        targets = [a for a in args if not a.startswith("-")]
        return {
            "action_type": ACTION_DELETE,
            "targets": targets or [command],
            "scope": SCOPE_LOCAL,
            "confidence_tier": TIER_INFERRED,
            "evidence_source": "command_destructive",
        }

    # Package managers → Tier 2 (network + filesystem + possibly execute)
    if program in _PACKAGE_MANAGERS:
        return {
            "action_type": ACTION_EXECUTE,
            "targets": [command],
            "scope": SCOPE_REMOTE,
            "confidence_tier": TIER_INFERRED,
            "evidence_source": "command_package_manager",
        }

    # Well-known Tier 2 commands
    if program in _TIER2_COMMAND_MAP:
        subcmd_map = _TIER2_COMMAND_MAP[program]
        subcmd = args[0] if args else "__default__"
        info = subcmd_map.get(subcmd, subcmd_map.get("__default__"))
        if info:
            targets = [command]
            # Extract file targets from git commands
            if program == "git" and len(args) > 1:
                targets = [a for a in args[1:] if not a.startswith("-")] or [command]
            return {
                "action_type": info["action"],
                "targets": targets,
                "scope": info["scope"],
                "confidence_tier": TIER_INFERRED,
                "evidence_source": f"command_{program}",
            }

    # Interpreters running scripts → Tier 3 (opaque execution)
    if program in _INTERPRETERS:
        script = args[0] if args and not args[0].startswith("-") else None
        if script and script != "-c":
            return {
                "action_type": ACTION_EXECUTE,
                "targets": [script],
                "scope": SCOPE_LOCAL,
                "confidence_tier": TIER_OPAQUE,
                "evidence_source": "command_interpreter_script",
            }
        # Inline code execution (python -c "...") → still opaque
        return {
            "action_type": ACTION_EXECUTE,
            "targets": [command],
            "scope": SCOPE_LOCAL,
            "confidence_tier": TIER_OPAQUE,
            "evidence_source": "command_interpreter_inline",
        }

    # Complex pipelines → Tier 3
    if has_pipes or has_subshell:
        return {
            "action_type": ACTION_EXECUTE,
            "targets": [command],
            "scope": SCOPE_LOCAL,
            "confidence_tier": TIER_OPAQUE,
            "evidence_source": "command_pipeline",
        }

    # Simple commands with redirect → Tier 2 (inferred write)
    if has_redirect:
        return {
            "action_type": ACTION_WRITE,
            "targets": [command],
            "scope": SCOPE_LOCAL,
            "confidence_tier": TIER_INFERRED,
            "evidence_source": "command_redirect",
        }

    # Unrecognized command → Tier 3
    return {
        "action_type": ACTION_EXECUTE,
        "targets": [command],
        "scope": SCOPE_LOCAL,
        "confidence_tier": TIER_OPAQUE,
        "evidence_source": "command_unknown",
    }


# ---------------------------------------------------------------------------
# Main classifier
# ---------------------------------------------------------------------------

def classify(tool_name: str, args: Optional[dict] = None) -> dict:
    """Classify a tool call by evidence inference.

    Args:
        tool_name: The tool name as provided by the agent/runtime.
        args: The tool's parameters/arguments.

    Returns:
        Classification dict with action_type, targets, scope,
        confidence_tier, evidence, and original_tool.
    """
    args = args or {}

    # Check for encoded/obfuscated payloads → Tier 4
    if _detect_encoded_payloads(args):
        return _result(
            action_type=ACTION_UNKNOWN,
            targets=[],
            scope=SCOPE_LOCAL,
            confidence_tier=TIER_UNINSPECTABLE,
            evidence_source="encoded_payload_detected",
            evidence_details={"tool_name": tool_name},
            original_tool=tool_name,
        )

    # --- Tier 1: Direct file path operations ---
    paths = _extract_file_paths(args)
    urls = _extract_urls(args)

    # Tool name hints at action type (evidence from parameters confirms)
    # Tokenize original name (preserving CamelCase boundaries)
    tool_tokens = _tokenize_tool_name(tool_name)
    tool_lower = tool_name.lower()

    # Explicit file read operations
    if paths and _tokens_indicate_read(tool_tokens):
        scope = _max_scope([_path_scope(p) for p in paths])
        return _result(
            action_type=ACTION_READ,
            targets=paths,
            scope=scope,
            confidence_tier=TIER_DIRECT,
            evidence_source="parameter_file_path",
            evidence_details={"paths": paths},
            original_tool=tool_name,
        )

    # Explicit file write operations
    if paths and _tokens_indicate_write(tool_tokens):
        scope = _max_scope([_path_scope(p) for p in paths])
        return _result(
            action_type=ACTION_WRITE,
            targets=paths,
            scope=scope,
            confidence_tier=TIER_DIRECT,
            evidence_source="parameter_file_path",
            evidence_details={"paths": paths, "has_content": "content" in args},
            original_tool=tool_name,
        )

    # Explicit file delete operations
    if paths and _tokens_indicate_delete(tool_tokens):
        scope = _max_scope([_path_scope(p) for p in paths])
        return _result(
            action_type=ACTION_DELETE,
            targets=paths,
            scope=scope,
            confidence_tier=TIER_DIRECT,
            evidence_source="parameter_file_path",
            evidence_details={"paths": paths},
            original_tool=tool_name,
        )

    # File move/rename
    if paths and _tokens_indicate_move(tool_tokens):
        scope = _max_scope([_path_scope(p) for p in paths])
        return _result(
            action_type=ACTION_MOVE,
            targets=paths,
            scope=scope,
            confidence_tier=TIER_DIRECT,
            evidence_source="parameter_file_path",
            evidence_details={"paths": paths},
            original_tool=tool_name,
        )

    # Directory listing / glob / search
    if _tokens_indicate_list(tool_tokens):
        targets = paths or [args.get("pattern", args.get("query", ""))]
        return _result(
            action_type=ACTION_LIST,
            targets=[t for t in targets if t],
            scope=SCOPE_LOCAL,
            confidence_tier=TIER_DIRECT,
            evidence_source="parameter_search",
            evidence_details={"pattern": args.get("pattern", "")},
            original_tool=tool_name,
        )

    # Mkdir
    if paths and _tokens_indicate_mkdir(tool_tokens):
        return _result(
            action_type=ACTION_CREATE_DIR,
            targets=paths,
            scope=SCOPE_LOCAL,
            confidence_tier=TIER_DIRECT,
            evidence_source="parameter_file_path",
            evidence_details={"paths": paths},
            original_tool=tool_name,
        )

    # --- Network operations (URLs in parameters) ---
    if urls:
        return _result(
            action_type=ACTION_NETWORK,
            targets=urls,
            scope=SCOPE_REMOTE,
            confidence_tier=TIER_DIRECT if not paths else TIER_INFERRED,
            evidence_source="parameter_url",
            evidence_details={"urls": urls},
            original_tool=tool_name,
        )

    # --- Tier 2: Command execution ---
    command = args.get("command", "")
    if command:
        cmd_class = _classify_command(command)
        return _result(
            action_type=cmd_class["action_type"],
            targets=cmd_class["targets"],
            scope=cmd_class["scope"],
            confidence_tier=cmd_class["confidence_tier"],
            evidence_source=cmd_class["evidence_source"],
            evidence_details={"command": command},
            original_tool=tool_name,
        )

    # --- File paths without clear action type ---
    if paths:
        # We have file paths but can't determine the action from the tool name.
        # Conservative: assume write (higher risk).
        scope = _max_scope([_path_scope(p) for p in paths])
        return _result(
            action_type=ACTION_WRITE,
            targets=paths,
            scope=scope,
            confidence_tier=TIER_INFERRED,
            evidence_source="parameter_file_path_ambiguous",
            evidence_details={"paths": paths, "tool_name": tool_name},
            original_tool=tool_name,
        )

    # --- Agent internal operations (planning, task management, etc.) ---
    if _is_agent_internal(tool_name, args):
        return _result(
            action_type=ACTION_AGENT_INTERNAL,
            targets=[],
            scope=SCOPE_LOCAL,
            confidence_tier=TIER_DIRECT,
            evidence_source="agent_internal_operation",
            evidence_details={"tool_name": tool_name, "arg_keys": list(args.keys())},
            original_tool=tool_name,
        )

    # --- No recognizable evidence → Tier 3 (opaque) ---
    return _result(
        action_type=ACTION_UNKNOWN,
        targets=[],
        scope=SCOPE_LOCAL,
        confidence_tier=TIER_OPAQUE,
        evidence_source="no_recognizable_evidence",
        evidence_details={"tool_name": tool_name, "arg_keys": list(args.keys())},
        original_tool=tool_name,
    )


# ---------------------------------------------------------------------------
# Tool name heuristics (secondary to parameter evidence)
# ---------------------------------------------------------------------------

_READ_INDICATORS = frozenset({
    "read", "get", "fetch", "load", "cat", "head", "tail", "view", "show",
    "inspect", "peek", "dump", "grep", "search", "find",
})

_WRITE_INDICATORS = frozenset({
    "write", "put", "save", "store", "set", "create", "touch", "append",
    "output", "emit", "tee", "edit", "modify", "update", "patch",
})

_DELETE_INDICATORS = frozenset({
    "delete", "remove", "rm", "unlink", "erase", "purge", "clean",
    "destroy", "drop",
})

_MOVE_INDICATORS = frozenset({
    "move", "mv", "rename", "relocate",
})

_LIST_INDICATORS = frozenset({
    "list", "ls", "dir", "glob", "scan", "enumerate", "browse",
    "tree", "walk", "find", "grep", "search",
})

_MKDIR_INDICATORS = frozenset({
    "mkdir", "make_dir", "create_dir", "create_directory", "makedirs",
})

# Agent internal operations: tools that are part of the agent's own workflow
# (planning, task management, session management, internal bookkeeping).
# These have no external side effects and should not require operator approval.
_AGENT_INTERNAL_TOOLS = frozenset({
    # Planning and task management
    "EnterPlanMode", "ExitPlanMode",
    "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
    # Agent orchestration
    "Agent",
    # Search and exploration (no side effects)
    "WebSearch", "WebFetch",
    # User interaction
    "AskUserQuestion",
    # Session and configuration
    "EnterWorktree",
    # Scheduling
    "CronCreate", "CronDelete", "CronList",
    # Task output
    "TaskOutput", "TaskStop",
    # Skills
    "Skill",
    # MCP resource listing
    "ListMcpResourcesTool", "ReadMcpResourceTool",
    # Notebook operations (with no file path — cell-level edits have paths)
    "NotebookEdit",
})

# Patterns that indicate agent-internal operations by name convention
_AGENT_INTERNAL_PATTERNS = [
    re.compile(r"^(Enter|Exit)(Plan|Worktree)", re.IGNORECASE),
    re.compile(r"^Task(Create|Update|Get|List|Output|Stop)$", re.IGNORECASE),
    re.compile(r"^Cron(Create|Delete|List)$", re.IGNORECASE),
    re.compile(r"^AskUser", re.IGNORECASE),
]


def _is_agent_internal(tool_name: str, args: dict) -> bool:
    """Check if a tool call is an agent-internal operation with no external side effects."""
    if tool_name in _AGENT_INTERNAL_TOOLS:
        return True
    for pattern in _AGENT_INTERNAL_PATTERNS:
        if pattern.search(tool_name):
            return True
    return False


def _tokenize_tool_name(name: str) -> set[str]:
    """Split tool name into tokens for keyword matching."""
    # Handle CamelCase, snake_case, kebab-case
    # Insert separator before uppercase letters
    spaced = re.sub(r"([a-z])([A-Z])", r"\1_\2", name)
    return {t.lower() for t in re.split(r"[_\-.\s]+", spaced) if t}


def _tokens_indicate_read(tokens: set) -> bool:
    return bool(tokens & _READ_INDICATORS) and not bool(tokens & _WRITE_INDICATORS)


def _tokens_indicate_write(tokens: set) -> bool:
    return bool(tokens & _WRITE_INDICATORS)


def _tokens_indicate_delete(tokens: set) -> bool:
    return bool(tokens & _DELETE_INDICATORS)


def _tokens_indicate_move(tokens: set) -> bool:
    return bool(tokens & _MOVE_INDICATORS)


def _tokens_indicate_list(tokens: set) -> bool:
    return bool(tokens & _LIST_INDICATORS)


def _tokens_indicate_mkdir(tokens: set) -> bool:
    return bool(tokens & _MKDIR_INDICATORS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SCOPE_ORDER = {
    SCOPE_LOCAL: 0,
    SCOPE_REPOSITORY: 1,
    SCOPE_SYSTEM: 2,
    SCOPE_REMOTE: 3,
    SCOPE_PRIVILEGED: 4,
}


def _max_scope(scopes: list[str]) -> str:
    """Return the highest-risk scope from a list."""
    if not scopes:
        return SCOPE_LOCAL
    return max(scopes, key=lambda s: _SCOPE_ORDER.get(s, 0))


def _result(
    action_type: str,
    targets: list,
    scope: str,
    confidence_tier: int,
    evidence_source: str,
    evidence_details: dict,
    original_tool: str,
) -> dict:
    return {
        "action_type": action_type,
        "targets": targets,
        "scope": scope,
        "confidence_tier": confidence_tier,
        "evidence": {
            "source": evidence_source,
            "details": evidence_details,
        },
        "original_tool": original_tool,
    }
