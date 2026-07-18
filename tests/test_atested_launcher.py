from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    launcher = repo / "atested"
    launcher.write_text((REPO / "atested").read_text(encoding="utf-8"), encoding="utf-8")
    launcher.chmod(0o755)
    (repo / "requirements.txt").write_text("cryptography\nhttpx\n", encoding="utf-8")
    (repo / "scripts" / "atested_cli.py").write_text(
        "import os, sys\n"
        "from pathlib import Path\n"
        "Path(sys.argv[1]).write_text(os.environ.get('ATESTED_FAKE_PYTHON', sys.executable), encoding='utf-8')\n",
        encoding="utf-8",
    )
    return repo


def _fake_python(path: Path, *, preflight_ok: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if preflight_ok:
        marker = str(path)
        body = f"""#!/usr/bin/env sh
if [ "$1" = "-c" ]; then exit 0; fi
script="$1"; shift
ATESTED_FAKE_PYTHON="{marker}" exec /usr/bin/python3 "$script" "$@"
"""
    else:
        body = """#!/usr/bin/env sh
echo "fake python missing cryptography" >&2
exit 1
"""
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _run_launcher(repo: Path, args: list[str], *, cwd: Path, path_prefix: Path | None = None, env=None):
    run_env = os.environ.copy()
    run_env.update(env or {})
    if path_prefix is not None:
        run_env["PATH"] = f"{path_prefix}{os.pathsep}{run_env.get('PATH', '')}"
    return subprocess.run(
        [str(repo / "atested"), *args],
        cwd=str(cwd),
        env=run_env,
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_launcher_prefers_repo_venv_when_path_python_lacks_dependencies(tmp_path):
    repo = _make_repo(tmp_path)
    marker = tmp_path / "interpreter.txt"
    fakebin = tmp_path / "fakebin"
    _fake_python(fakebin / "python3", preflight_ok=False)
    _fake_python(repo / ".venv" / "bin" / "python3", preflight_ok=True)

    result = _run_launcher(repo, [str(marker), "start", "--no-services"], cwd=repo, path_prefix=fakebin)

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == str(repo / ".venv" / "bin" / "python3")


def test_launcher_finds_repo_venv_from_other_working_directory(tmp_path):
    repo = _make_repo(tmp_path)
    marker = tmp_path / "outside-interpreter.txt"
    outside = tmp_path / "outside"
    outside.mkdir()
    fakebin = tmp_path / "fakebin"
    _fake_python(fakebin / "python3", preflight_ok=False)
    _fake_python(repo / ".venv" / "bin" / "python3", preflight_ok=True)

    result = _run_launcher(repo, [str(marker)], cwd=outside, path_prefix=fakebin)

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == str(repo / ".venv" / "bin" / "python3")


def test_launcher_honors_explicit_python_override_before_repo_venv(tmp_path):
    repo = _make_repo(tmp_path)
    marker = tmp_path / "override-interpreter.txt"
    override = tmp_path / "override-python"
    _fake_python(repo / ".venv" / "bin" / "python3", preflight_ok=False)
    _fake_python(override, preflight_ok=True)

    result = _run_launcher(repo, [str(marker)], cwd=repo, env={"ATESTED_PYTHON": str(override)})

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == str(override)


def test_launcher_falls_back_to_path_python_and_reports_missing_dependencies(tmp_path):
    repo = _make_repo(tmp_path)
    fakebin = tmp_path / "fakebin"
    _fake_python(fakebin / "python3", preflight_ok=False)

    result = _run_launcher(repo, [str(tmp_path / "unused")], cwd=repo, path_prefix=fakebin)

    assert result.returncode == 1
    assert "Missing Atested Python dependencies for interpreter: python3" in result.stderr
    assert ".venv/bin/python3 -m pip install -r" in result.stderr


def test_launcher_fallback_to_path_python_when_no_repo_venv_exists(tmp_path):
    repo = _make_repo(tmp_path)
    marker = tmp_path / "fallback-interpreter.txt"
    fakebin = tmp_path / "fakebin"
    _fake_python(fakebin / "python3", preflight_ok=True)

    result = _run_launcher(repo, [str(marker)], cwd=repo, path_prefix=fakebin)

    assert result.returncode == 0, result.stderr
    assert marker.read_text(encoding="utf-8") == str(fakebin / "python3")

