#!/usr/bin/env python3
import pathlib
import re
import sys
import tempfile
from typing import Optional

ROOT = pathlib.Path(__file__).resolve().parents[1]
OPS = ROOT / "docs/dev/OPS_CANONICAL.md"
INV_SCRIPT = ROOT / "system/scripts/inventory-snapshot.sh"
INV = ROOT / "docs/dev/inventory/INVENTORY_LATEST.md"
SCRIPTS_DIR = ROOT / "system/scripts"
MERGE_QUEUE = SCRIPTS_DIR / "merge-queue.sh"
FORBIDDEN_BLOCK_BEGIN = "FORBIDDEN_COMMANDS_LIST_BEGIN"
FORBIDDEN_BLOCK_END = "FORBIDDEN_COMMANDS_LIST_END"

def fail(msg: str) -> None:
  print(f"FAIL: {msg}")
  sys.exit(1)

def read_text(p: pathlib.Path) -> str:
  return p.read_text(encoding="utf-8", errors="replace")

def strip_documented_forbidden_blocks(text: str) -> str:
  pat = re.compile(
    rf"(?ms)^.*{re.escape(FORBIDDEN_BLOCK_BEGIN)}.*?$.*?^.*{re.escape(FORBIDDEN_BLOCK_END)}.*?$"
  )
  return re.sub(pat, "", text)

def has_forbidden_merge_main_behavior(text: str) -> bool:
  txt = strip_documented_forbidden_blocks(text)
  return bool(
    re.search(r'\bgit\s+merge\b', txt)
    or re.search(r'\bcheckout\s+main\b', txt)
    or re.search(r'\bgit\s+switch\s+main\b', txt)
  )

def verify_single_script(path: pathlib.Path, allowlist: set[str]) -> Optional[str]:
  txt = read_text(path)
  if has_forbidden_merge_main_behavior(txt) and path.name not in allowlist:
    return f"{path.name} contains merge/main behavior but is not allowlisted in OPS_CANONICAL.md"
  return None

def selftest() -> int:
  print("SELFTEST: verifier scoped ignore for documented forbidden blocks")
  codex_unattended = ROOT / "system/scripts/codex-unattended.sh"
  if not codex_unattended.exists():
    print("FAIL: missing codex-unattended.sh")
    return 1
  txt = read_text(codex_unattended)
  print(f"SELFTEST: codex-unattended markers present={FORBIDDEN_BLOCK_BEGIN in txt and FORBIDDEN_BLOCK_END in txt}")
  print(f"SELFTEST: codex-unattended forbidden-detected={has_forbidden_merge_main_behavior(txt)}")
  with tempfile.TemporaryDirectory() as td:
    p1 = pathlib.Path(td) / "docblock_ok.sh"
    p1.write_text(
      "#!/usr/bin/env bash\n"
      "# FORBIDDEN_COMMANDS_LIST_BEGIN\n"
      "# git merge main\n"
      "# git switch main\n"
      "# FORBIDDEN_COMMANDS_LIST_END\n"
      "echo ok\n",
      encoding="utf-8",
    )
    p2 = pathlib.Path(td) / "real_violation.sh"
    p2.write_text("#!/usr/bin/env bash\ngit switch main\n", encoding="utf-8")
    print(f"SELFTEST: docblock_ok forbidden-detected={has_forbidden_merge_main_behavior(read_text(p1))}")
    print(f"SELFTEST: real_violation forbidden-detected={has_forbidden_merge_main_behavior(read_text(p2))}")
    if has_forbidden_merge_main_behavior(read_text(p1)):
      print("FAIL: docblock false positive")
      return 1
    if not has_forbidden_merge_main_behavior(read_text(p2)):
      print("FAIL: missed real violation")
      return 1
  print("OK")
  return 0

def main() -> None:
  if len(sys.argv) >= 2 and sys.argv[1] == "--selftest":
    sys.exit(selftest())
  if len(sys.argv) >= 3 and sys.argv[1] == "--check-file":
    p = pathlib.Path(sys.argv[2])
    if not p.exists():
      fail(f"Missing file: {p}")
    print("FORBIDDEN" if has_forbidden_merge_main_behavior(read_text(p)) else "OK")
    return
  if not OPS.exists():
    fail("Missing docs/dev/OPS_CANONICAL.md")
  if not INV_SCRIPT.exists():
    fail("Missing system/scripts/inventory-snapshot.sh")
  if not INV.exists():
    fail("Missing docs/dev/inventory/INVENTORY_LATEST.md")

  ops_txt = read_text(OPS)

  # merge-queue classification requirement
  if MERGE_QUEUE.exists():
    if not re.search(r'\bmerge-queue\.sh\b', ops_txt):
      fail("merge-queue.sh exists but OPS_CANONICAL.md does not mention/classify it")

  # Disallow merge-to-main behaviors unless explicitly allowlisted
  allowlist = set()
  m = re.search(r'## Allowlist for scripts that may merge or touch main(.*?)\n## ', ops_txt, re.S)
  if m:
    block = m.group(1)
    for line in block.splitlines():
      line = line.strip()
      if line.startswith("- "):
        allowlist.add(line[2:].strip().split()[0])

  if SCRIPTS_DIR.exists():
    for p in sorted(SCRIPTS_DIR.glob("*.sh")):
      err = verify_single_script(p, allowlist)
      if err:
        fail(err)

  print("OK")

if __name__ == "__main__":
  main()
