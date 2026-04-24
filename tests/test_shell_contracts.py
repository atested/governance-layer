"""Shell contract test discovery and execution.

Discovers test_*.sh scripts in tests/ and system/tests/ and runs them
as individual pytest test cases. Each shell test is a subprocess call
marked with @pytest.mark.shell so it can be selectively included or
excluded:

    pytest tests/ -m "not shell"     # skip shell tests
    pytest tests/ -m shell           # only shell tests

Shell tests are included in the default pytest run but may fail if
environment prerequisites are not met (MCP server running, specific
fixtures present, etc.). Failures in shell tests are reported but
do not block the Python test baseline.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO / "tests"
SYSTEM_TESTS_DIR = REPO / "system" / "tests"


def _discover_shell_tests(directory: Path) -> list[Path]:
    """Find all test_*.sh files in a directory."""
    if not directory.exists():
        return []
    return sorted(directory.glob("test_*.sh"))


def _shell_test_id(script: Path) -> str:
    """Generate a readable test ID from script path."""
    rel = script.relative_to(REPO)
    return str(rel)


# Discover shell tests at module load time
_TESTS_SHELL = _discover_shell_tests(TESTS_DIR)
_SYSTEM_SHELL = _discover_shell_tests(SYSTEM_TESTS_DIR)
_ALL_SHELL = _TESTS_SHELL + _SYSTEM_SHELL


@pytest.mark.shell
@pytest.mark.parametrize(
    "script",
    _ALL_SHELL,
    ids=[_shell_test_id(s) for s in _ALL_SHELL],
)
def test_shell_contract(script):
    """Run a shell test script and verify it exits 0."""
    if not os.access(script, os.X_OK):
        # Try running with bash if not executable
        cmd = ["bash", str(script)]
    else:
        cmd = [str(script)]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
        cwd=str(REPO),
        env={**os.environ, "REPO_ROOT": str(REPO)},
    )

    if result.returncode != 0:
        output = (result.stdout + result.stderr)[-2000:]  # last 2000 chars
        pytest.fail(
            f"Shell test exited with code {result.returncode}\n"
            f"Output:\n{output}"
        )
