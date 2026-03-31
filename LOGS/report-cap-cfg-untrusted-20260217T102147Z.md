# Cap-cfg Untrusted + Poisoned Intent Tests Report

Timestamp (UTC): 20260217T102147Z

## Changes

- policy-eval.py: registry loaded internally via `load_internal_registry()` (raw bytes → sha256 → parse JSON from same bytes); CLI argv[1] (legacy registry path) silently ignored.
- policy-eval.py: `cap_cfg` field in intent JSON detected and listed in `decision_record.untrusted_inputs`; never used for enforcement.
- policy-eval.py: new reason code `RC-UNKNOWN-TOOL` replaces `RC-FS-PATH-DISALLOWED` for unknown/unregistered tools.
- policy-eval.py: `load_internal_registry()` fails closed (sys.exit 2) if registry unreadable or invalid JSON.
- tests/fixtures/poison_capcfg_unknown_tool.json: fixture with tool=FS_DELETE + cap_cfg claiming FS_DELETE is allowed.
- tests/fixtures/poison_capcfg_weaken_caps.json: fixture with tool=FS_WRITE, path=/tmp, cap_cfg loosening allowlist to "/".
- tests/test_poisoned_intent.sh: harness for T-POISON-001 and T-POISON-002.

## Poisoned intent test run

```
--- T-POISON-001: unknown tool injection ---
PASS: T-POISON-001 decision DENY (contains "policy_decision": "DENY")
PASS: T-POISON-001 reason unknown tool (contains RC-UNKNOWN-TOOL)
PASS: T-POISON-001 no RC-FS-PATH-DISALLOWED (correctly absent: RC-FS-PATH-DISALLOWED)
PASS: T-POISON-001 untrusted_inputs cap_cfg (contains "cap_cfg")
PASS: T-POISON-001 hash (record_hash verified)

--- T-POISON-002: weaken caps injection ---
PASS: T-POISON-002 decision DENY (contains "policy_decision": "DENY")
PASS: T-POISON-002 reason path disallowed (contains RC-FS-PATH-DISALLOWED)
PASS: T-POISON-002 untrusted_inputs cap_cfg (contains "cap_cfg")
PASS: T-POISON-002 hash (record_hash verified)

Summary: pass=9 fail=0
```

## Record key fields

T-POISON-001 (FS_DELETE, unknown tool):
```
decision: DENY
reasons: ['RC-UNKNOWN-TOOL']
untrusted_inputs: ['cap_cfg']
cap_registry_hash: sha256:74effdfd975a8f1f1e48f832ddc00141...
```

T-POISON-002 (FS_WRITE, path outside allowlist):
```
decision: DENY
reasons: ['RC-FS-PATH-DISALLOWED']
untrusted_inputs: ['cap_cfg']
cap_registry_hash: sha256:74effdfd975a8f1f1e48f832ddc00141...
```

## FS_WRITE regression (tail)

```
Summary: pass=12 fail=0
```

## MCP smoke

```
PASS: MCP smoke (DENY + ALLOW + tamper + fs_list + fs_read tests passed, fail-closed verified)
```
