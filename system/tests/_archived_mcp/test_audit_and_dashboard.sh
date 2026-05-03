#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TMP_ROOT="$ROOT/out/test_audit_and_dashboard"
rm -rf "$TMP_ROOT"
mkdir -p "$TMP_ROOT"

# ---------------------------------------------------------------------------
# Test 1: Audit query tools return correct filtered results
# ---------------------------------------------------------------------------
python3 - "$ROOT" "$TMP_ROOT/audit_query" <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["GOV_GOVERNED_FAMILY"] = "audit_test"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "test_ctx"
os.environ["GOV_POLICY_VERSION"] = "test_v1"
os.environ["GOV_SIGNING_DEV_MODE"] = "1"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server

# Create some governed actions to query
server.certify_surface("audit_test")

target1 = tmp / "file1.txt"
res1 = server.fs_write(str(target1), "content-one", overwrite=False)
assert res1["policy_decision"] == "ALLOW", f"Expected ALLOW, got {res1['policy_decision']}"

target2 = tmp / "file2.txt"
res2 = server.fs_write(str(target2), "content-two", overwrite=False)
assert res2["policy_decision"] == "ALLOW"

# Test unfiltered audit query
result = server.audit_query()
assert result["total_matching"] > 0, "Expected at least one audit entry"
assert result["chain_event_count"] > 0
assert len(result["entries"]) > 0

# Test filter by tool_name
result = server.audit_query(tool_name="FS_WRITE")
for entry in result["entries"]:
    assert entry["event_category"] == "action_decision", f"Expected action_decision, got {entry['event_category']}"

# Test filter by event_category
result = server.audit_query(event_category="verification_transition")
for entry in result["entries"]:
    assert entry["event_category"] == "verification_transition"

# Test filter by policy_decision
result = server.audit_query(policy_decision="ALLOW")
assert result["total_matching"] >= 2, f"Expected at least 2 ALLOW entries, got {result['total_matching']}"

# Test pagination
result = server.audit_query(limit=1, offset=0)
assert len(result["entries"]) == 1
first_entry = result["entries"][0]

result2 = server.audit_query(limit=1, offset=1)
assert len(result2["entries"]) == 1
assert result2["entries"][0]["sequence_position"] != first_entry["sequence_position"]

print("AUDIT_QUERY=PASS")
PY

# ---------------------------------------------------------------------------
# Test 2: Audit record detail returns full record
# ---------------------------------------------------------------------------
python3 - "$ROOT" "$TMP_ROOT/audit_detail" <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["GOV_GOVERNED_FAMILY"] = "detail_test"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "test_ctx"
os.environ["GOV_POLICY_VERSION"] = "test_v1"
os.environ["GOV_SIGNING_DEV_MODE"] = "1"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server

server.certify_surface("detail_test")
target = tmp / "detail.txt"
res = server.fs_write(str(target), "detail-content", overwrite=False)
assert res["policy_decision"] == "ALLOW"

# Get the request_id from the activity feed
activity = server.governance_activity(limit=10)
action_entries = [e for e in activity["entries"] if e["event_category"] == "action_decision"]
assert len(action_entries) > 0, "Expected at least one action entry"

request_id = action_entries[0]["evidence"]["request_id"]
assert request_id, "Expected non-empty request_id"

# Look up by request_id
detail = server.audit_record_detail(request_id)
assert detail["found"] is True, f"Expected found=True for {request_id}"
assert detail["chain_record"]["request_id"] == request_id

# Look up nonexistent record
missing = server.audit_record_detail("nonexistent-id-12345")
assert missing["found"] is False

# Empty record_id
empty = server.audit_record_detail("")
assert empty.get("error") or empty.get("found") is False

print("AUDIT_RECORD_DETAIL=PASS")
PY

# ---------------------------------------------------------------------------
# Test 3: Audit report generation produces valid output
# ---------------------------------------------------------------------------
python3 - "$ROOT" "$TMP_ROOT/audit_report" <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["GOV_GOVERNED_FAMILY"] = "report_test"
os.environ["GOV_DEPLOYMENT_CONTEXT"] = "test_ctx"
os.environ["GOV_POLICY_VERSION"] = "test_v1"
os.environ["GOV_SIGNING_DEV_MODE"] = "1"

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server

server.certify_surface("report_test")
for i in range(3):
    target = tmp / f"report_{i}.txt"
    server.fs_write(str(target), f"content-{i}", overwrite=False)

# Test group_by=tool
report = server.audit_report(group_by="tool")
assert report["report_type"] == "audit_summary"
assert report["group_by"] == "tool"
assert report["total_records"] > 0
assert len(report["groups"]) > 0
assert "decision_summary" in report
assert report["decision_summary"].get("ALLOW", 0) >= 3

# Test group_by=decision
report = server.audit_report(group_by="decision")
assert report["group_by"] == "decision"
assert len(report["groups"]) > 0

# Test group_by=category
report = server.audit_report(group_by="category")
assert report["group_by"] == "category"
assert len(report["groups"]) > 0

# Test group_by=user
report = server.audit_report(group_by="user")
assert report["group_by"] == "user"

# Test invalid group_by falls back to tool
report = server.audit_report(group_by="invalid_value")
assert report["group_by"] == "tool"

print("AUDIT_REPORT=PASS")
PY

# ---------------------------------------------------------------------------
# Test 4: Dashboard server starts and serves API
# ---------------------------------------------------------------------------
python3 - "$ROOT" "$TMP_ROOT/dashboard" <<'PY'
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)
os.environ["DASHBOARD_PORT"] = "9799"

dashboard_script = root / "dashboard" / "server.py"
assert dashboard_script.exists(), f"Dashboard server not found at {dashboard_script}"

# Start dashboard server
proc = subprocess.Popen(
    [sys.executable, str(dashboard_script)],
    env={**os.environ},
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

try:
    time.sleep(1)
    assert proc.poll() is None, "Dashboard server exited unexpectedly"

    # Test index.html is served
    resp = urllib.request.urlopen("http://localhost:9799/index.html")
    html = resp.read().decode("utf-8")
    assert "Atested Dashboard" in html, "Expected dashboard title in HTML"

    # Test API endpoints
    resp = urllib.request.urlopen("http://localhost:9799/api/status")
    data = json.loads(resp.read())
    assert "chain_event_count" in data
    assert "chain_integrity" in data

    resp = urllib.request.urlopen("http://localhost:9799/api/activity?limit=5")
    data = json.loads(resp.read())
    assert "entries" in data
    assert "total_matching" in data

    resp = urllib.request.urlopen("http://localhost:9799/api/approvals")
    data = json.loads(resp.read())
    assert "active_approvals" in data

    resp = urllib.request.urlopen("http://localhost:9799/api/verification")
    data = json.loads(resp.read())
    assert "surfaces" in data

    resp = urllib.request.urlopen("http://localhost:9799/api/audit/query")
    data = json.loads(resp.read())
    assert "entries" in data
    assert "filters" in data

    resp = urllib.request.urlopen("http://localhost:9799/api/audit/report?group_by=tool")
    data = json.loads(resp.read())
    assert data["report_type"] == "audit_summary"
    assert data["group_by"] == "tool"

    resp = urllib.request.urlopen("http://localhost:9799/api/users")
    data = json.loads(resp.read())
    assert "unique_users" in data

    print("DASHBOARD_SERVER=PASS")
finally:
    proc.terminate()
    proc.wait(timeout=5)
PY

# ---------------------------------------------------------------------------
# Test 5: Dashboard MCP tool returns URL
# ---------------------------------------------------------------------------
python3 - "$ROOT" "$TMP_ROOT/dashboard_tool" <<'PY'
import os
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
tmp = Path(sys.argv[2])
runtime_dir = tmp / "runtime"
runtime_dir.mkdir(parents=True, exist_ok=True)

os.environ["GOV_RUNTIME_DIR"] = str(runtime_dir)
os.environ["GOV_CANONICAL_REPO_PATH"] = str(root)
os.environ["GOV_RUNTIME_PATH"] = str(runtime_dir)

sys.path.insert(0, str(root / "scripts"))
sys.path.insert(0, str(root / "mcp"))
sys.path.insert(0, str(root))

from mcp import server

result = server.atested_dashboard()
assert result["status"] == "started", f"Expected started, got {result}"
assert "url" in result
assert result["url"].startswith("http://localhost:")
port = result["port"]

# Second call should return already_running
result2 = server.atested_dashboard()
assert result2["status"] == "already_running", f"Expected already_running, got {result2}"
assert result2["port"] == port

# Verify the server is actually serving
import urllib.request
time.sleep(0.5)
resp = urllib.request.urlopen(result["url"] + "/api/status")
import json
data = json.loads(resp.read())
assert "chain_event_count" in data

# Clean up
server._DASHBOARD_PROCESS.terminate()
server._DASHBOARD_PROCESS.wait(timeout=5)
server._DASHBOARD_PROCESS = None
server._DASHBOARD_PORT = None

print("DASHBOARD_TOOL=PASS")
PY

echo "AUDIT_AND_DASHBOARD=PASS"
