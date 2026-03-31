#!/usr/bin/env python3
import argparse
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional, Tuple


ROOT = pathlib.Path(__file__).resolve().parents[2]
WORK_QUEUE = ROOT / "docs/dev/WORK_QUEUE.md"
READY_DIR = ROOT / "docs/dev/tasks/ready"


def git(*args: str, check: bool = True) -> str:
    p = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {p.stderr.strip()}")
    return p.stdout


@dataclass
class ReadyTask:
    task_id: str
    title: str
    status: str
    spec_path: pathlib.Path


def parse_next_ready_tasks() -> list[ReadyTask]:
    txt = WORK_QUEUE.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(?ms)^## Next\s*$\n(.*?)(?=^##\s+|\Z)", txt)
    if not m:
      return []
    block = m.group(1)
    rows = []
    for line in block.splitlines():
        if not line.startswith("| TASK_"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 6:
            continue
        task_id, title, status = cols[0], cols[1], cols[2]
        if status != "Ready":
            continue
        spec_match = re.search(r"\((tasks/(?:ready|blocked)/[^)]+)\)", line)
        if not spec_match:
            continue
        spec = ROOT / "docs/dev" / spec_match.group(1).replace("tasks/", "tasks/")
        # fix duplicate docs/dev if already rooted under docs/dev
        if not spec.exists():
            spec = ROOT / spec_match.group(1)
        rows.append(ReadyTask(task_id, title, status, spec))
    rows.sort(key=lambda r: int(r.task_id.split("_")[1]))
    return rows


def parse_allowlist(spec_path: pathlib.Path) -> Tuple[list[str], Optional[str]]:
    txt = spec_path.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(?ms)^##\s+Files allowed to touch\s*$\n(.*?)(?=^##\s+|\Z)", txt)
    if not m:
        return [], "missing Files allowed to touch section"
    raw = m.group(1)
    paths: list[str] = []
    anomalies: list[str] = []
    for ln in raw.splitlines():
        s = ln.strip()
        if not s or s == "[]":
            continue
        if re.match(r"^\d+[.)]\s+", s):
            continue
        if s.startswith("- "):
            s = s[2:].strip()
        elif s.startswith("* "):
            s = s[2:].strip()
        else:
            anomalies.append(f"non-bullet line: {s}")
            continue
        if s.startswith("`") and s.endswith("`"):
            s = s[1:-1].strip()
        if any(tok in s for tok in [" and/or ", " through ", "TASK_NNN", "Everything outside "]):
            anomalies.append(f"prose-like entry: {s}")
        if s:
            paths.append(s)
    if not paths:
        return [], "no parseable allowlist entries"
    if anomalies:
        return paths, "; ".join(sorted(set(anomalies)))
    return paths, None


def remote_task_branches() -> dict[str, list[str]]:
    out = git("for-each-ref", "--format=%(refname:short)", "refs/remotes/origin/codex/TASK_*__*")
    m: dict[str, list[str]] = {}
    for line in out.splitlines():
        ref = line.strip()
        if not ref:
            continue
        mm = re.search(r"origin/codex/(TASK_\d+)__", ref)
        if not mm:
            continue
        m.setdefault(mm.group(1), []).append(ref)
    for k in m:
        m[k].sort()
    return m


def commit_subject(sha: str) -> str:
    return git("log", "-1", "--format=%s", sha, check=False).strip()


def branch_tip_sha(ref: str) -> str:
    return git("rev-parse", ref).strip()


def is_ancestor(commitish: str, ref: str) -> bool:
    p = subprocess.run(["git", "merge-base", "--is-ancestor", commitish, ref], cwd=ROOT)
    return p.returncode == 0


def provenance_hints(task: ReadyTask, refs: list[str]) -> list[str]:
    hints: list[str] = []
    for ref in refs:
        sha = branch_tip_sha(ref)
        merged = is_ancestor(sha, "origin/main")
        subj = commit_subject(sha) or "(unknown)"
        hints.append(f"{ref} tip {sha[:7]} {'merged' if merged else 'unmerged'}: {subj}")
    if not hints:
        # fallback: spec history hints
        out = git("log", "--oneline", "--", str(task.spec_path.relative_to(ROOT)), check=False)
        for line in out.splitlines()[:3]:
            if line.strip():
                hints.append(f"spec-history: {line.strip()}")
    return hints


def done_rows_missing_provenance() -> list[str]:
    txt = WORK_QUEUE.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"(?ms)^## Done\s*$\n(.*?)(?=^##\s+|\Z)", txt)
    if not m:
        return []
    block = m.group(1)
    out: list[str] = []
    for line in block.splitlines():
        if not line.startswith("| TASK_"):
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 5:
            continue
        task_id = cols[0]
        if task_id == "TASK_ID":
            continue
        notes = cols[4] if len(cols) >= 5 else ""
        if "origin/main via" not in notes and "pending merge" not in notes and "Branch " not in notes:
            out.append(f"{task_id}: missing provenance note")
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only WORK_QUEUE/task-spec drift scanner")
    ap.add_argument("--exit-on-drift", action="store_true", help="Exit 2 if any drift is detected")
    args = ap.parse_args()

    ready = parse_next_ready_tasks()
    remote_refs = remote_task_branches()

    sec_a: list[str] = []
    sec_b: list[str] = []
    sec_c: list[str] = []
    sec_d: list[str] = done_rows_missing_provenance()

    for t in ready:
        paths, allow_anom = parse_allowlist(t.spec_path)
        if allow_anom:
            sec_c.append(f"{t.task_id}: {allow_anom} ({t.spec_path.relative_to(ROOT)})")

        refs = remote_refs.get(t.task_id, [])
        if refs:
            unmerged = [r for r in refs if not is_ancestor(branch_tip_sha(r), "origin/main")]
            merged = [r for r in refs if is_ancestor(branch_tip_sha(r), "origin/main")]
            if unmerged:
                sec_b.append(f"{t.task_id}: pending merge branches: {', '.join(unmerged)}")
            if merged:
                hints = provenance_hints(t, merged[:2])
                sec_a.append(f"{t.task_id}: likely already implemented on origin/main ({'; '.join(hints)})")
            elif not unmerged:
                sec_a.append(f"{t.task_id}: unclear (published branches found but merge status unresolved)")
        else:
            sec_a.append(f"{t.task_id}: unclear (no published branch hint)")

    # stable output
    print("QUEUE_DRIFT_SCAN v1")
    print("A) READY tasks likely already implemented on origin/main")
    for line in sorted(sec_a):
        print(f"- {line}")
    print("B) READY tasks with published branches pending merge")
    for line in sorted(sec_b):
        print(f"- {line}")
    print("C) Task specs with non-parseable allowlists")
    for line in sorted(sec_c):
        print(f"- {line}")
    print("D) Tasks in Done lacking provenance note")
    for line in sorted(sec_d):
        print(f"- {line}")

    drift = bool(sec_a or sec_b or sec_c or sec_d)
    if drift and args.exit_on_drift:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
