#!/usr/bin/env python3
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "mcp" / "server.py"

RUNTIME = Path(os.environ.get("GOV_RUNTIME_DIR", str(REPO / ".gov_runtime"))).resolve()
CHAIN = RUNTIME / "LOGS" / "decision-chain.jsonl"


def chain_len() -> int:
    if not CHAIN.exists():
        return 0
    return len([l for l in CHAIN.read_text(encoding="utf-8").splitlines() if l.strip()])


async def main():
    env = os.environ.copy()
    env["GOV_RUNTIME_DIR"] = str(RUNTIME)

    (RUNTIME / "LOGS").mkdir(parents=True, exist_ok=True)
    (RUNTIME / "tmp").mkdir(parents=True, exist_ok=True)

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER)],
        env=env,
    )

    before_n = chain_len()

    # Test 1: DENY case
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()

            deny_path = "/tmp/governance-mcp-deny.txt"
            resp = await session.call_tool("fs_write", {
                "path": deny_path,
                "content": "x",
                "overwrite": False,
                "request_executable": False
            })
            deny_obj = json.loads(resp.content[0].text)
            assert deny_obj["policy_decision"] == "DENY"

            after_deny_n = chain_len()
            assert after_deny_n == before_n + 1

    # TAMPER TEST: break chain and confirm server fails closed
    if CHAIN.exists():
        lines = CHAIN.read_text(encoding="utf-8").splitlines()
        if lines:
            lines[0] = lines[0].replace("sha256:", "sha256:X", 1)
            CHAIN.write_text("\n".join(lines) + "\n", encoding="utf-8")

    tamper_before_n = chain_len()
    async with stdio_client(params) as (r2, w2):
        async with ClientSession(r2, w2) as session2:
            await session2.initialize()
            resp_t = await session2.call_tool("fs_write", {
                "path": "/tmp/governance-mcp-deny-2.txt",
                "content": "x",
                "overwrite": False,
                "request_executable": False
            })
            # MCP SDK returns isError=True results for tool failures
            assert resp_t.isError, "Expected error response on broken chain"
            assert "CHAIN_VERIFY_FAIL" in (resp_t.content[0].text if resp_t.content else ""), \
                f"Expected CHAIN_VERIFY_FAIL in error, got: {resp_t.content[0].text if resp_t.content else 'no content'}"

    tamper_after_n = chain_len()
    # After quarantine, the original chain file is moved, so chain_len() returns 0
    assert tamper_after_n == 0, f"Chain should be quarantined (moved), got {tamper_after_n} records"

    # Assert quarantine rotation occurred (evidence preserved)
    qdir = RUNTIME / "LOGS" / "quarantine"
    assert qdir.exists(), "Expected quarantine directory to exist"
    qchains = sorted(qdir.glob("decision-chain.*.jsonl"))
    assert len(qchains) >= 1, "Expected at least one quarantined chain file"

    # Test 2: runtime-root behavior (ALLOW when policy admits runtime path)
    async with stdio_client(params) as (r3, w3):
        async with ClientSession(r3, w3) as session3:
            await session3.initialize()

            before_allow_n = chain_len()
            allow_path = str((RUNTIME / "tmp" / "mcp-allow.txt").resolve())
            resp2 = await session3.call_tool("fs_write", {
                "path": allow_path,
                "content": "hello",
                "overwrite": True,
                "request_executable": False
            })
            allow_obj = json.loads(resp2.content[0].text)
            if allow_obj["policy_decision"] == "ALLOW":
                assert Path(allow_path).read_text(encoding="utf-8") == "hello"

                # Decision record must bind to capability registry version
                dr = allow_obj.get("decision_record") or {}
                assert isinstance(dr.get("cap_registry_hash"), str), f"Expected string cap_registry_hash, got {dr.get('cap_registry_hash')}"
                assert dr.get("cap_registry_hash", "").startswith("sha256:"), f"Expected sha256: prefix, got {dr.get('cap_registry_hash')}"

                # FS_LIST TEST: ALLOW list runtime/tmp and find mcp-allow.txt
                resp3 = await session3.call_tool("fs_list", {
                    "path": str((RUNTIME / "tmp").resolve()),
                    "max_entries": 200,
                    "include_hidden": False
                })
                list_obj = json.loads(resp3.content[0].text)
                assert list_obj["policy_decision"] == "ALLOW", f"Expected ALLOW for fs_list, got {list_obj}"
                names = [e.get("name") for e in list_obj.get("list_result", {}).get("entries", [])]
                assert "mcp-allow.txt" in names, f"Expected mcp-allow.txt in {names}"

                # FS_LIST TEST: DENY hidden path (create a hidden dir and attempt list)
                hdir = (RUNTIME / "tmp" / ".hidden_test_dir")
                hdir.mkdir(parents=True, exist_ok=True)
                resp4 = await session3.call_tool("fs_list", {
                    "path": str(hdir.resolve()),
                    "max_entries": 50,
                    "include_hidden": False
                })
                hidden_obj = json.loads(resp4.content[0].text)
                assert hidden_obj["policy_decision"] == "DENY", f"Expected DENY for hidden path, got {hidden_obj}"

                # FS_READ TEST: ALLOW read runtime/tmp/mcp-allow.txt
                resp_r = await session3.call_tool("fs_read", {
                    "path": allow_path,
                    "max_bytes": 4096,
                    "offset": 0,
                    "as_text": True
                })
                read_obj = json.loads(resp_r.content[0].text)
                assert read_obj["policy_decision"] == "ALLOW", f"Expected ALLOW for fs_read, got {read_obj}"
                rr = read_obj.get("read_result", {})
                assert rr.get("bytes_read", 0) >= 1, f"Expected bytes_read >= 1, got {rr}"
                assert rr.get("content_hash_sha256", "").startswith("sha256:"), f"Expected hash, got {rr}"
                assert "hello" in rr.get("content", ""), f"Expected 'hello' in content, got {rr}"

                # FS_READ TEST: DENY hidden file read
                hfile = (RUNTIME / "tmp" / ".hidden_read.txt")
                hfile.write_text("secret", encoding="utf-8")
                resp_r2 = await session3.call_tool("fs_read", {
                    "path": str(hfile.resolve()),
                    "max_bytes": 128,
                    "offset": 0,
                    "as_text": True
                })
                read_deny = json.loads(resp_r2.content[0].text)
                assert read_deny["policy_decision"] == "DENY", f"Expected DENY for hidden file, got {read_deny}"

                # FS_MKDIR TEST: ALLOW create directory within runtime/tmp
                mkdir_path = str((RUNTIME / "tmp" / "mcp-mkdir-test").resolve())
                import shutil
                if Path(mkdir_path).exists():
                    shutil.rmtree(mkdir_path)
                resp_m = await session3.call_tool("fs_mkdir", {
                    "path": mkdir_path,
                    "parents": False,
                    "exist_ok": False
                })
                mkdir_obj = json.loads(resp_m.content[0].text)
                assert mkdir_obj["policy_decision"] == "ALLOW", f"Expected ALLOW for fs_mkdir, got {mkdir_obj}"
                assert Path(mkdir_path).is_dir(), f"Expected directory to exist: {mkdir_path}"
                mr = mkdir_obj.get("mkdir_result", {})
                assert mr.get("canonical_path"), f"Expected canonical_path in mkdir_result, got {mr}"

                # FS_MKDIR TEST: DENY path outside allowed roots
                resp_md = await session3.call_tool("fs_mkdir", {
                    "path": "/tmp/mcp-mkdir-deny-test",
                    "parents": False,
                    "exist_ok": False
                })
                mkdir_deny = json.loads(resp_md.content[0].text)
                assert mkdir_deny["policy_decision"] == "DENY", f"Expected DENY for fs_mkdir outside root, got {mkdir_deny}"

                # FS_MOVE TEST: ALLOW move within runtime/tmp
                move_src = str((RUNTIME / "tmp" / "mcp-move-src.txt").resolve())
                move_dst = str((RUNTIME / "tmp" / "mcp-move-dst.txt").resolve())
                # Write source file first
                Path(move_src).write_text("move-me", encoding="utf-8")
                if Path(move_dst).exists():
                    Path(move_dst).unlink()
                resp_mv = await session3.call_tool("fs_move", {
                    "src_path": move_src,
                    "dst_path": move_dst,
                    "overwrite": False
                })
                move_obj = json.loads(resp_mv.content[0].text)
                assert move_obj["policy_decision"] == "ALLOW", f"Expected ALLOW for fs_move, got {move_obj}"
                assert not Path(move_src).exists(), "Expected src to be gone after move"
                assert Path(move_dst).read_text(encoding="utf-8") == "move-me", "Expected dst content after move"

                # FS_MOVE TEST: DENY move to path outside allowed roots
                resp_mvd = await session3.call_tool("fs_move", {
                    "src_path": move_dst,
                    "dst_path": "/tmp/mcp-move-deny.txt",
                    "overwrite": False
                })
                move_deny = json.loads(resp_mvd.content[0].text)
                assert move_deny["policy_decision"] == "DENY", f"Expected DENY for fs_move outside root, got {move_deny}"

                # FS_DELETE TEST: ALLOW delete file within runtime/tmp
                delete_path = str((RUNTIME / "tmp" / "mcp-delete-test.txt").resolve())
                Path(delete_path).write_text("to-be-deleted", encoding="utf-8")
                resp_del = await session3.call_tool("fs_delete", {
                    "path": delete_path,
                    "recursive": False
                })
                delete_obj = json.loads(resp_del.content[0].text)
                assert delete_obj["policy_decision"] == "ALLOW", f"Expected ALLOW for fs_delete, got {delete_obj}"
                assert not Path(delete_path).exists(), f"Expected file to be deleted: {delete_path}"

                # FS_DELETE TEST: DENY path outside allowed roots
                resp_deld = await session3.call_tool("fs_delete", {
                    "path": "/tmp/mcp-delete-deny.txt",
                    "recursive": False
                })
                delete_deny = json.loads(resp_deld.content[0].text)
                assert delete_deny["policy_decision"] == "DENY", f"Expected DENY for fs_delete outside root, got {delete_deny}"
            else:
                assert allow_obj["policy_decision"] == "DENY", f"Expected ALLOW or DENY for fs_write, got {allow_obj}"
                reasons = {r.get("code") for r in allow_obj.get("policy_reasons", [])}
                assert "RC-FS-PATH-DISALLOWED" in reasons, f"Expected RC-FS-PATH-DISALLOWED, got {allow_obj}"

    after_n = chain_len()
    if allow_obj["policy_decision"] == "ALLOW":
        # Chain grows by: 1 fs_write ALLOW + 2 fs_list + 2 fs_read + 2 fs_mkdir + 2 fs_move + 2 fs_delete = +11
        assert after_n == before_allow_n + 11, f"Expected chain to grow by 11 (1 fs_write + 2 fs_list + 2 fs_read + 2 fs_mkdir + 2 fs_move + 2 fs_delete), before={before_allow_n}, after={after_n}"
        mode = "ALLOW-mode"
    else:
        # Chain grows by one DENY record for fs_write probe.
        assert after_n == before_allow_n + 1, f"Expected chain to grow by 1 in deny-only mode, before={before_allow_n}, after={after_n}"
        mode = "DENY-mode (runtime path outside policy allowlist)"

    print(f"PASS: MCP smoke ({mode}; DENY + tamper fail-closed verified)")

if __name__ == "__main__":
    asyncio.run(main())
