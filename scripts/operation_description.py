#!/usr/bin/env python3
"""
operation_description.py — deterministic, context-aware English descriptions
for governed operations (QS-062).

The classifier produces machine-shaped output (action_type / targets / scope /
tier). That output is correct but unreadable: an operator approving a denied
operation sees `Bash` and a JSON blob of arguments, not "Push commits to
origin/main". This module turns the (tool_name, args, classification) triple
into one short English sentence that:

  * tells the operator *what the operation does*, in plain language;
  * differentiates the same function in different contexts
    (cat VERSION  vs.  cat ~/.codex/config.toml);
  * is fully deterministic — pure template matching, no LLM, no external IO;
  * never produces an empty string. Unrecognised commands fall back to
    "Execute: <first token>" so an operator can still tell something
    happened, and the approval-store still has a stable scope key.

The output is stored as ``operation_description`` on every classification,
threaded through the chain record by ``policy_eval_v2.evaluate``, displayed
on the dashboard's Activity view, and used as the scope key when an
operator approves an otherwise-denied operation.

Adding a new recogniser
-----------------------
1. Add a recognise_* helper that returns a string or None.
2. Wire it into ``describe_operation`` between the existing recognisers and
   the unknown-command fallback.
3. Add a test case in tests/test_operation_description.py.
"""

from __future__ import annotations

import os
import re
from typing import Optional, Tuple
from urllib.parse import urlsplit


# ---------------------------------------------------------------------------
# Path / URL recognisers shared by every command-level handler.
# ---------------------------------------------------------------------------


# Known host → readable label. The lookup is exact-host first, then suffix.
# Add an entry here when a target appears often enough that the generic
# "external request to <host>" wording is unhelpful.
_KNOWN_HOSTS: dict[str, str] = {
    "api.github.com": "GitHub API",
    "github.com": "GitHub",
    "raw.githubusercontent.com": "GitHub raw content",
    "api.anthropic.com": "Anthropic API",
    "api.openai.com": "OpenAI API",
    "generativelanguage.googleapis.com": "Gemini API",
    "registry.npmjs.org": "npm registry",
    "pypi.org": "PyPI",
    "files.pythonhosted.org": "PyPI files",
    "registry.modelcontextprotocol.io": "MCP registry",
}

# localhost:port → readable label. Lets the generator answer "what is on
# this port" without an external service catalogue. Add entries as new
# local services appear in the deployment.
_KNOWN_LOCAL_PORTS: dict[int, str] = {
    8080: "governance proxy",
    11434: "local Ollama service",
    3000: "local web service",
    5173: "local Vite dev server",
    8000: "local dev server",
    8888: "local Jupyter server",
}

# Path → readable label for common files an operator is likely to inspect.
# Keys are matched against the basename or against a path suffix.
_KNOWN_FILE_LABELS: list[Tuple[str, str]] = [
    # (matcher_pattern, label) — matcher is a substring/suffix
    ("VERSION", "VERSION file"),
    ("LICENSE", "LICENSE"),
    ("README.md", "README"),
    ("README", "README"),
    ("CHANGELOG.md", "changelog"),
    (".env", "environment file"),
    ("pyproject.toml", "Python project config"),
    ("requirements.txt", "Python requirements"),
    ("package.json", "Node package manifest"),
    ("package-lock.json", "Node lockfile"),
    ("Cargo.toml", "Rust project config"),
    ("Cargo.lock", "Rust lockfile"),
    ("Dockerfile", "Dockerfile"),
    ("docker-compose.yml", "Docker Compose config"),
    ("Makefile", "Makefile"),
    ("setup.py", "Python setup script"),
    (".gitignore", "gitignore"),
    (".gitconfig", "Git configuration"),
    (".bashrc", "shell rc file"),
    (".zshrc", "shell rc file"),
    (".bash_profile", "shell profile"),
]

# Directory → readable label for common project directories. Used by
# `ls <dir>/` and as a hint when describing files inside them.
_KNOWN_DIR_LABELS: list[Tuple[str, str]] = [
    ("gov_runtime", "governance runtime directory"),
    ("capabilities", "capabilities directory"),
    ("scripts", "scripts directory"),
    ("proxy", "proxy source directory"),
    ("dashboard", "dashboard directory"),
    ("tests", "tests directory"),
    ("docs", "docs directory"),
    ("LOGS", "logs directory"),
    ("node_modules", "node_modules directory"),
    ("target", "Rust build directory"),
    ("dist", "dist build directory"),
    ("build", "build directory"),
    ("__pycache__", "Python cache directory"),
    (".git", "Git internals"),
]

# Path-shape → context label, used to describe sources/configs without
# enumerating every file. "proxy/server.py" → "proxy source".
_PATH_CONTEXT_LABELS: list[Tuple[re.Pattern, str]] = [
    (re.compile(r"(^|/)proxy/.*\.py$"), "proxy source"),
    (re.compile(r"(^|/)scripts/.*\.py$"), "script"),
    (re.compile(r"(^|/)dashboard/.*\.py$"), "dashboard source"),
    (re.compile(r"(^|/)dashboard/.*\.js$"), "dashboard UI source"),
    (re.compile(r"(^|/)tests/.*\.py$"), "test source"),
    (re.compile(r"(^|/)docs/.*\.md$"), "documentation"),
    (re.compile(r"(^|/)capabilities/.*\.json$"), "capability config"),
    (re.compile(r"\.codex/"), "Codex configuration"),
    (re.compile(r"\.claude/"), "Claude configuration"),
    (re.compile(r"\.ssh/"), "SSH configuration"),
    (re.compile(r"\.aws/"), "AWS configuration"),
    (re.compile(r"\.gnupg/"), "GnuPG configuration"),
]


_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_HOST_PORT_RE = re.compile(r"^([A-Za-z0-9.-]+)(?::(\d+))?")


def _label_for_host(host: str, port: Optional[int]) -> str:
    """Map a host (and optional port) to a readable label."""
    host = (host or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        if port and port in _KNOWN_LOCAL_PORTS:
            return _KNOWN_LOCAL_PORTS[port]
        if port:
            return f"local service on port {port}"
        return "local service"
    if host in _KNOWN_HOSTS:
        return _KNOWN_HOSTS[host]
    # Suffix match (e.g. *.s3.amazonaws.com)
    for known_host, label in _KNOWN_HOSTS.items():
        if host.endswith("." + known_host):
            return label
    return host or "unknown host"


def _parse_url_or_endpoint(token: str) -> Tuple[str, Optional[int]]:
    """Return (host, port) from a URL or a bare host:port string.

    Accepts both ``https://api.github.com/repos/...`` and bare endpoints
    like ``localhost:11434/api/tags``.
    """
    token = token.strip().strip(",")
    if "://" in token:
        parts = urlsplit(token)
        host = parts.hostname or ""
        port = parts.port
        return host, port
    # Strip any leading scheme-less path off the endpoint
    head = token.split("/", 1)[0]
    m = _HOST_PORT_RE.match(head)
    if not m:
        return "", None
    host = m.group(1)
    port = int(m.group(2)) if m.group(2) else None
    return host, port


def _basename(path: str) -> str:
    return os.path.basename(path.rstrip("/")) or path


def _path_label(path: str) -> Optional[str]:
    """Return a context-rich label for a known file or directory path."""
    info = _path_label_info(path)
    return info[0] if info else None


def _path_label_info(path: str) -> Optional[Tuple[str, str]]:
    """Return (label, kind) for a known path.

    kind ∈ {"file", "directory", "context"} where:
      * "file" — the basename matched a per-file entry (already specific);
      * "directory" — the path matched a known directory;
      * "context" — the path shape matched a directory-category pattern
        (e.g. "proxy/*.py"), so the basename should be appended for
        differentiation.

    The kind lets callers (like _describe_read_file) decide whether to
    append the basename or not without re-running the matchers themselves.
    """
    if not path:
        return None
    base = _basename(path)
    # Directory match wins for trailing-slash hints
    if path.endswith("/"):
        for key, label in _KNOWN_DIR_LABELS:
            if base == key or path.rstrip("/").endswith("/" + key):
                return (label, "directory")
    # Specific-file match — label already names the file.
    for key, label in _KNOWN_FILE_LABELS:
        if base == key:
            return (label, "file")
    # Path-shape context — categorical label, needs basename for specificity.
    for pattern, label in _PATH_CONTEXT_LABELS:
        if pattern.search(path):
            return (label, "context")
    return None


def _short_path(path: str, max_len: int = 60) -> str:
    """Compress a long path for display while keeping the tail recognisable."""
    if len(path) <= max_len:
        return path
    return "…" + path[-(max_len - 1):]


# ---------------------------------------------------------------------------
# Tokeniser — small, focused, quote-aware. The classifier already has its
# own parser; this one cares about argv-style splitting for templating.
# ---------------------------------------------------------------------------


_TOKEN_RE = re.compile(
    r"""
    "([^"\\]*(?:\\.[^"\\]*)*)" |    # double-quoted
    '([^'\\]*(?:\\.[^'\\]*)*)' |    # single-quoted
    (\S+)                            # bare token
    """,
    re.VERBOSE,
)


def _tokenise(command: str) -> list[str]:
    """Split a shell command into argv tokens, honouring simple quoting."""
    tokens: list[str] = []
    for m in _TOKEN_RE.finditer(command):
        dq, sq, bare = m.groups()
        if dq is not None:
            tokens.append(dq)
        elif sq is not None:
            tokens.append(sq)
        elif bare is not None:
            tokens.append(bare)
    return tokens


def _program_basename(token: str) -> str:
    """Get the program name from a bare argv[0] (e.g. /usr/bin/python3 → python3)."""
    base = os.path.basename(token)
    return base or token


def _first_positional(tokens: list[str]) -> Optional[str]:
    """Return the first token that isn't a flag (-x or --foo)."""
    for t in tokens:
        if not t.startswith("-"):
            return t
    return None


# ---------------------------------------------------------------------------
# git recogniser
# ---------------------------------------------------------------------------


def _describe_git(tokens: list[str]) -> Optional[str]:
    """Describe a git invocation. tokens excludes argv[0]=='git'."""
    if not tokens:
        return "Run git (no subcommand)"
    verb = tokens[0]
    rest = tokens[1:]

    if verb == "push":
        # `git push origin main` / `git push --force origin feature/x`
        positional = [t for t in rest if not t.startswith("-")]
        if len(positional) >= 2:
            return f"Push commits to {positional[0]}/{positional[1]}"
        if len(positional) == 1:
            return f"Push commits to {positional[0]}"
        return "Push commits to remote"

    if verb == "pull":
        positional = [t for t in rest if not t.startswith("-")]
        if len(positional) >= 2:
            return f"Pull from {positional[0]}/{positional[1]}"
        return "Pull from remote"

    if verb == "fetch":
        positional = [t for t in rest if not t.startswith("-")]
        if positional:
            return f"Fetch from {positional[0]}"
        return "Fetch from remote"

    if verb == "clone":
        positional = [t for t in rest if not t.startswith("-")]
        if positional:
            host, _ = _parse_url_or_endpoint(positional[0])
            label = _label_for_host(host, None) if host else positional[0]
            return f"Clone repository from {label}"
        return "Clone repository"

    if verb == "add":
        positional = [t for t in rest if not t.startswith("-")]
        if not positional:
            return "Stage changes for commit"
        if len(positional) == 1:
            return f"Stage {positional[0]} for commit"
        return f"Stage {len(positional)} paths for commit"

    if verb == "commit":
        # Look for a -m message
        for i, t in enumerate(rest):
            if t == "-m" and i + 1 < len(rest):
                msg = rest[i + 1]
                return f"Commit changes: {msg[:60]}"
            if t.startswith("-m"):
                return f"Commit changes: {t[2:][:60]}"
        if "--amend" in rest:
            return "Amend previous commit"
        return "Commit staged changes"

    if verb == "checkout":
        positional = [t for t in rest if not t.startswith("-")]
        if "-b" in rest:
            new_branch = rest[rest.index("-b") + 1] if rest.index("-b") + 1 < len(rest) else "branch"
            return f"Create and switch to branch {new_branch}"
        if positional:
            return f"Check out {positional[0]}"
        return "Check out branch"

    if verb == "switch":
        positional = [t for t in rest if not t.startswith("-")]
        if positional:
            return f"Switch to branch {positional[0]}"
        return "Switch branch"

    if verb == "branch":
        positional = [t for t in rest if not t.startswith("-")]
        if "-d" in rest or "-D" in rest:
            return f"Delete branch {' '.join(positional) or '(unspecified)'}"
        if positional:
            return f"Create branch {positional[0]}"
        return "List branches"

    if verb == "merge":
        positional = [t for t in rest if not t.startswith("-")]
        if positional:
            return f"Merge {positional[0]} into current branch"
        return "Merge branch"

    if verb == "rebase":
        positional = [t for t in rest if not t.startswith("-")]
        if positional:
            return f"Rebase onto {positional[0]}"
        return "Rebase current branch"

    if verb == "reset":
        if "--hard" in rest:
            return "Hard-reset working tree"
        return "Reset staged changes"

    if verb == "stash":
        sub = rest[0] if rest else ""
        if sub == "pop":
            return "Restore latest stash"
        if sub == "list":
            return "List stashed changes"
        if sub == "drop":
            return "Drop latest stash"
        return "Stash working changes"

    if verb == "status":
        return "Check repository status"

    if verb == "log":
        return "View commit history"

    if verb == "diff":
        positional = [t for t in rest if not t.startswith("-")]
        if "--cached" in rest or "--staged" in rest:
            return "Show staged changes"
        if positional:
            return f"Show diff for {positional[0]}"
        return "Show uncommitted changes"

    if verb == "show":
        positional = [t for t in rest if not t.startswith("-")]
        if positional:
            return f"Show commit {positional[0]}"
        return "Show latest commit"

    if verb == "remote":
        sub = rest[0] if rest else ""
        if sub in ("add", "remove", "rm", "set-url"):
            return f"Modify git remote ({sub})"
        return "List git remotes"

    if verb == "tag":
        positional = [t for t in rest if not t.startswith("-")]
        if positional:
            return f"Create tag {positional[0]}"
        return "List git tags"

    if verb in ("rev-parse", "rev-list"):
        return "Inspect git ref"

    if verb == "config":
        return "Read or modify git config"

    if verb == "init":
        return "Initialise new git repository"

    return f"Run git {verb}"


# ---------------------------------------------------------------------------
# Network recognisers (curl / wget / http)
# ---------------------------------------------------------------------------


def _describe_curl_like(tool: str, tokens: list[str]) -> str:
    """Describe a curl/wget/http(ie) invocation."""
    url = None
    for t in tokens:
        if t.startswith(("http://", "https://")) or _looks_like_endpoint(t):
            url = t
            break

    method = "GET"
    for i, t in enumerate(tokens):
        if t in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
        elif t in ("-d", "--data", "--data-binary") and method == "GET":
            method = "POST"

    if url is None:
        return f"Run {tool} (no URL parsed)"

    host, port = _parse_url_or_endpoint(url)
    label = _label_for_host(host, port)

    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        verb = "Check" if method == "GET" else f"{method.title()} to"
        return f"{verb} {label}"

    if host in _KNOWN_HOSTS or any(host.endswith("." + h) for h in _KNOWN_HOSTS):
        if method == "GET":
            return f"{label} request"
        return f"{method.title()} to {label}"

    # Unknown external host
    if method == "GET":
        return f"External request to {host}"
    return f"{method.title()} to external host {host}"


def _looks_like_endpoint(token: str) -> bool:
    """Catch bare host:port style endpoints that curl accepts."""
    if "://" in token:
        return True
    if token.startswith("-"):
        return False
    head = token.split("/", 1)[0]
    if ":" in head and head.rsplit(":", 1)[1].isdigit():
        return True
    return False


# ---------------------------------------------------------------------------
# Package manager recognisers
# ---------------------------------------------------------------------------


def _describe_pip(tokens: list[str]) -> str:
    """Describe a pip / pip3 / pipx / uv command."""
    if not tokens:
        return "Run pip"
    verb = tokens[0]
    rest = tokens[1:]
    positional = [t for t in rest if not t.startswith("-")]
    if verb == "install":
        if not positional:
            return "Install Python packages"
        if len(positional) == 1:
            return f"Install Python package: {positional[0]}"
        return f"Install Python packages: {', '.join(positional[:3])}" + (
            "…" if len(positional) > 3 else ""
        )
    if verb == "uninstall":
        if positional:
            return f"Uninstall Python package: {positional[0]}"
        return "Uninstall Python packages"
    if verb == "list":
        return "List installed Python packages"
    if verb == "show":
        return f"Show Python package info: {positional[0] if positional else ''}".strip()
    if verb == "freeze":
        return "Freeze installed Python packages"
    return f"Run pip {verb}"


def _describe_npm(tool: str, tokens: list[str]) -> str:
    """Describe npm / yarn / pnpm."""
    if not tokens:
        return f"Run {tool}"
    verb = tokens[0]
    rest = tokens[1:]
    positional = [t for t in rest if not t.startswith("-")]
    if verb in ("install", "i", "add"):
        if not positional:
            return "Install Node.js dependencies"
        return f"Install Node.js package: {positional[0]}"
    if verb in ("uninstall", "remove", "rm"):
        if positional:
            return f"Uninstall Node.js package: {positional[0]}"
        return "Uninstall Node.js packages"
    if verb == "run":
        if positional:
            return f"Run npm script: {positional[0]}"
        return "Run npm script"
    if verb == "test":
        return "Run Node.js test suite"
    if verb == "build":
        return "Build Node.js project"
    if verb == "start":
        return "Start Node.js project"
    if verb == "audit":
        return "Audit Node.js dependencies"
    return f"Run {tool} {verb}"


def _describe_cargo(tokens: list[str]) -> str:
    """Describe a cargo invocation."""
    if not tokens:
        return "Run cargo"
    verb = tokens[0]
    rest = tokens[1:]
    release = "--release" in rest
    if verb == "build":
        return f"Build Rust project ({'release' if release else 'debug'})"
    if verb == "test":
        return "Run Rust test suite"
    if verb == "run":
        return f"Run Rust binary ({'release' if release else 'debug'})"
    if verb == "check":
        return "Type-check Rust project"
    if verb == "clippy":
        return "Lint Rust project (clippy)"
    if verb == "fmt":
        return "Format Rust project"
    if verb == "add":
        positional = [t for t in rest if not t.startswith("-")]
        if positional:
            return f"Add Rust crate: {positional[0]}"
        return "Add Rust crate"
    if verb == "update":
        return "Update Rust dependencies"
    return f"Run cargo {verb}"


def _describe_make(tokens: list[str]) -> str:
    """Describe a make invocation. tokens excludes argv[0]=='make'."""
    positional = [t for t in tokens if not t.startswith("-")]
    if not positional:
        return "Build project (make)"
    return f"Build project (make {positional[0]})"


def _describe_python(tool: str, tokens: list[str]) -> str:
    """Describe python / python3 invocations."""
    if not tokens:
        return f"Run {tool}"
    # -m module form
    for i, t in enumerate(tokens):
        if t == "-m" and i + 1 < len(tokens):
            module = tokens[i + 1]
            if module == "pytest":
                # First positional argument after pytest = target
                rest = tokens[i + 2:]
                target = _first_positional(rest)
                if target:
                    return f"Run Python tests: {target}"
                return "Run Python test suite"
            if module == "pip":
                return _describe_pip(tokens[i + 2:])
            if module == "venv":
                return "Create Python virtual environment"
            if module == "unittest":
                return "Run Python unit tests"
            if module == "http.server":
                return "Start local HTTP server (python)"
            return f"Run Python module: {module}"
        if t == "-c" and i + 1 < len(tokens):
            snippet = tokens[i + 1].splitlines()[0][:50]
            return f"Run Python inline: {snippet}"
    # Script form: python3 path/to/script.py [args]
    first = _first_positional(tokens)
    if first and first.endswith(".py"):
        base = _basename(first)
        # Describe well-known scripts by name when possible
        if "test" in base.lower():
            return f"Run Python script: {base}"
        return f"Run Python script: {base}"
    return f"Run {tool}"


def _describe_pytest(tokens: list[str]) -> str:
    """Describe a bare pytest invocation."""
    target = _first_positional(tokens)
    if target:
        return f"Run Python tests: {target}"
    return "Run Python test suite"


# ---------------------------------------------------------------------------
# Filesystem recognisers (cat / less / head / tail / ls / rm / mv / cp)
# ---------------------------------------------------------------------------


def _describe_read_file(tool: str, tokens: list[str]) -> str:
    """Describe cat/less/head/tail/bat etc."""
    paths = [t for t in tokens if not t.startswith("-")]
    if not paths:
        return f"Run {tool}"
    return _format_read(paths[0])


def _format_read(path: str) -> str:
    """Format a 'Read X' description from a single file path.

    Centralises the basename-suppression rule so the Bash `cat` path and the
    named-tool `Read` path stay consistent.
    """
    info = _path_label_info(path)
    base = _basename(path)
    if info is not None:
        label, kind = info
        # "file" kind (VERSION, README) — label is already specific.
        # "directory" kind — label names the directory.
        # "context" kind that ends in "configuration" — categorical and
        # complete on its own (e.g. "Codex configuration").
        # Everything else (source/test/docs categories) gets the basename
        # appended so the operator can distinguish individual files.
        if kind in ("file", "directory") or label.endswith("configuration"):
            return f"Read {label}"
        return f"Read {label}: {base}"
    return f"Read {_short_path(path)}"


def _describe_ls(tokens: list[str]) -> str:
    """Describe an `ls` invocation."""
    paths = [t for t in tokens if not t.startswith("-")]
    if not paths:
        return "List current directory"
    path = paths[0]
    label = _path_label(path if path.endswith("/") else path + "/")
    if label:
        return f"List {label}"
    return f"List {_short_path(path)}"


def _describe_rm(tokens: list[str]) -> str:
    """Describe `rm` — gravity matters here, so name the path even when
    bypassed by the proxy denylist."""
    paths = [t for t in tokens if not t.startswith("-")]
    recursive = any(t in ("-r", "-R", "-rf", "-fr") or "r" in t.lstrip("-") for t in tokens if t.startswith("-"))
    if not paths:
        return f"Delete files (rm{' -r' if recursive else ''})"
    base = _basename(paths[0])
    if recursive:
        return f"Recursively delete {base}"
    return f"Delete {base}"


def _describe_mv_cp(tool: str, tokens: list[str]) -> str:
    """Describe `mv`/`cp`. The last positional is the destination."""
    positional = [t for t in tokens if not t.startswith("-")]
    if len(positional) >= 2:
        verb = "Move" if tool == "mv" else "Copy"
        src = _basename(positional[0])
        dst = _basename(positional[-1])
        return f"{verb} {src} to {dst}"
    if positional:
        verb = "Move" if tool == "mv" else "Copy"
        return f"{verb} {_basename(positional[0])}"
    return f"Run {tool}"


def _describe_mkdir(tokens: list[str]) -> str:
    paths = [t for t in tokens if not t.startswith("-")]
    if paths:
        return f"Create directory {_basename(paths[0])}"
    return "Create directory"


def _describe_chmod(tokens: list[str]) -> str:
    positional = [t for t in tokens if not t.startswith("-")]
    if len(positional) >= 2:
        return f"Change permissions of {_basename(positional[-1])} to {positional[0]}"
    return "Change file permissions"


# ---------------------------------------------------------------------------
# Process / OS recognisers
# ---------------------------------------------------------------------------


def _describe_kill(tokens: list[str]) -> str:
    positional = [t for t in tokens if not t.startswith("-")]
    if positional:
        return f"Terminate process {positional[0]}"
    return "Terminate process"


def _describe_ssh(tokens: list[str]) -> str:
    positional = [t for t in tokens if not t.startswith("-")]
    if positional:
        return f"SSH to {positional[0]}"
    return "Open SSH session"


def _describe_docker(tokens: list[str]) -> str:
    if not tokens:
        return "Run docker"
    verb = tokens[0]
    if verb in ("build", "run", "exec", "stop", "rm", "rmi", "pull", "push", "ps"):
        return f"Run docker {verb}"
    return f"Run docker {verb}"


def _describe_brew(tokens: list[str]) -> str:
    if not tokens:
        return "Run brew"
    verb = tokens[0]
    rest = tokens[1:]
    positional = [t for t in rest if not t.startswith("-")]
    if verb == "install" and positional:
        return f"Install Homebrew package: {positional[0]}"
    if verb == "uninstall" and positional:
        return f"Uninstall Homebrew package: {positional[0]}"
    if verb == "update":
        return "Update Homebrew"
    return f"Run brew {verb}"


# ---------------------------------------------------------------------------
# Top-level command dispatcher (for Bash-shaped tools).
# ---------------------------------------------------------------------------


def _describe_command(command: str) -> str:
    """Describe a shell command string."""
    if not command or not command.strip():
        return "Execute: (empty command)"

    # Honour chained commands: describe the first non-trivial one and note
    # the chain. We don't try to summarise every clause — a long pipeline is
    # opaque by design and the description is for the operator to decide,
    # not for the classifier to expand.
    head = command
    chain_marker = ""
    for sep in ("&&", "||", ";"):
        if sep in command:
            head = command.split(sep, 1)[0].strip()
            chain_marker = f" + {sep} (chained)"
            break

    tokens = _tokenise(head)
    if not tokens:
        return f"Execute: {head.strip()[:40]}"

    program = _program_basename(tokens[0])
    rest = tokens[1:]

    handlers = {
        "git": lambda: _describe_git(rest),
        "curl": lambda: _describe_curl_like("curl", rest),
        "wget": lambda: _describe_curl_like("wget", rest),
        "http": lambda: _describe_curl_like("http", rest),
        "httpie": lambda: _describe_curl_like("http", rest),
        "pip": lambda: _describe_pip(rest),
        "pip3": lambda: _describe_pip(rest),
        "pipx": lambda: _describe_pip(rest),
        "uv": lambda: _describe_pip(rest),
        "npm": lambda: _describe_npm("npm", rest),
        "yarn": lambda: _describe_npm("yarn", rest),
        "pnpm": lambda: _describe_npm("pnpm", rest),
        "cargo": lambda: _describe_cargo(rest),
        "make": lambda: _describe_make(rest),
        "python": lambda: _describe_python("python", rest),
        "python3": lambda: _describe_python("python3", rest),
        "pytest": lambda: _describe_pytest(rest),
        "cat": lambda: _describe_read_file("cat", rest),
        "less": lambda: _describe_read_file("less", rest),
        "more": lambda: _describe_read_file("more", rest),
        "head": lambda: _describe_read_file("head", rest),
        "tail": lambda: _describe_read_file("tail", rest),
        "bat": lambda: _describe_read_file("bat", rest),
        "ls": lambda: _describe_ls(rest),
        "dir": lambda: _describe_ls(rest),
        "rm": lambda: _describe_rm(rest),
        "mv": lambda: _describe_mv_cp("mv", rest),
        "cp": lambda: _describe_mv_cp("cp", rest),
        "mkdir": lambda: _describe_mkdir(rest),
        "chmod": lambda: _describe_chmod(rest),
        "kill": lambda: _describe_kill(rest),
        "killall": lambda: _describe_kill(rest),
        "ssh": lambda: _describe_ssh(rest),
        "scp": lambda: _describe_ssh(rest),
        "docker": lambda: _describe_docker(rest),
        "brew": lambda: _describe_brew(rest),
    }

    handler = handlers.get(program)
    result = handler() if handler else None
    if result is None:
        # Echo the first recognisable token so the operator sees what
        # actually ran, but mark it as unrecognised so a future approval
        # is at least scoped to that program.
        result = f"Execute: {program}"

    return result + chain_marker


# ---------------------------------------------------------------------------
# Tool-name handlers for the non-Bash tools the proxy mediates.
# ---------------------------------------------------------------------------


def _describe_named_tool(tool_name: str, args: dict) -> Optional[str]:
    """Describe a non-Bash tool by name (Read, Write, WebFetch, ...).

    Returns None when the tool isn't one of the named-tool shapes we
    recognise; the caller then falls back to the command-style or generic
    description path.
    """
    name_lower = tool_name.lower()

    if tool_name in ("Read", "Cat", "ReadFile"):
        path = args.get("file_path") or args.get("path") or ""
        if path:
            return _format_read(path)
        return "Read file"

    if tool_name in ("Write", "WriteFile", "CreateFile"):
        path = args.get("file_path") or args.get("path") or ""
        if path:
            return f"Write {_basename(path)}"
        return "Write file"

    if tool_name in ("Edit", "EditFile", "PatchFile"):
        path = args.get("file_path") or args.get("path") or ""
        if path:
            return f"Edit {_basename(path)}"
        return "Edit file"

    if tool_name == "MultiEdit":
        path = args.get("file_path") or ""
        if path:
            return f"Apply multiple edits to {_basename(path)}"
        return "Apply multiple file edits"

    if tool_name == "NotebookEdit":
        path = args.get("notebook_path") or ""
        if path:
            return f"Edit notebook {_basename(path)}"
        return "Edit notebook"

    if tool_name in ("Glob", "Search"):
        pattern = args.get("pattern") or args.get("query") or ""
        if pattern:
            return f"Search for files matching {pattern}"
        return "Search for files"

    if tool_name in ("Grep", "CodeSearch"):
        pattern = args.get("pattern") or args.get("query") or ""
        path = args.get("path") or ""
        loc = f" in {_basename(path)}" if path else ""
        if pattern:
            return f"Search code for {pattern}{loc}"
        return "Search code"

    if tool_name in ("LS", "List", "ListDir"):
        path = args.get("path") or args.get("directory") or ""
        if path:
            label = _path_label(path if path.endswith("/") else path + "/")
            if label:
                return f"List {label}"
            return f"List {_short_path(path)}"
        return "List directory"

    if tool_name == "WebFetch":
        url = args.get("url") or ""
        if url:
            host, port = _parse_url_or_endpoint(url)
            return f"Fetch {_label_for_host(host, port)}"
        return "Fetch web resource"

    if tool_name == "WebSearch":
        query = args.get("query") or ""
        if query:
            return f"Search web for {query[:60]}"
        return "Search the web"

    if tool_name in ("Bash", "Shell", "Run", "Execute"):
        command = args.get("command") or args.get("script") or ""
        if command:
            return _describe_command(command)
        return f"Run {tool_name.lower()} (no command)"

    # Token-based fallbacks for less-common variants.
    if "read" in name_lower and ("path" in args or "file_path" in args):
        return _describe_named_tool("Read", args)
    if "write" in name_lower and ("path" in args or "file_path" in args):
        return _describe_named_tool("Write", args)
    if "fetch" in name_lower and args.get("url"):
        return _describe_named_tool("WebFetch", args)

    return None


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def describe_operation(
    tool_name: str,
    args: Optional[dict] = None,
    classification: Optional[dict] = None,
) -> str:
    """Return a short English description of an operation.

    Args:
        tool_name: The tool name as the proxy received it.
        args: The tool's arguments. May be None or empty.
        classification: Optional classifier output. Used as context when
            available (currently the function relies on tool_name and args
            directly, but the parameter is part of the contract so future
            recognisers can refine descriptions by action_type or scope
            without changing every call site).

    Returns:
        A non-empty English sentence. Never None, never empty.
    """
    args = args or {}

    # Tier-4 uninspectable operations: do not pretend we know what they do.
    if classification and classification.get("confidence_tier") == 4:
        return f"Execute opaque/encoded payload (via {tool_name})"

    # Named-tool descriptions take precedence — they have richer per-tool
    # arg shapes than a free-form shell command does.
    named = _describe_named_tool(tool_name, args)
    if named:
        return named

    # Fall back to command-style: any tool that ships a `command` arg gets
    # the shell-template treatment.
    for key in ("command", "script", "shell"):
        cmd = args.get(key)
        if isinstance(cmd, str) and cmd.strip():
            return _describe_command(cmd)

    # Last resort: name the tool so the operator at least sees what ran.
    return f"Execute: {tool_name}"
