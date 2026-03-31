# Cap-registry-path Arg Audit Report

Timestamp (UTC): 20260217T103500Z

## Change

- policy-eval.py main(): when called with legacy 2-arg form, captures argv[1] into
  `caller_registry_path` and appends `{"cap_registry_path_arg": <path>, "note": "ignored; enforcement uses internal registry only"}` to `decision_record.untrusted_inputs`.
- Enforcement remains unchanged: internal CAP_REGISTRY_PATH only.
- tests/fixtures/permissive_registry.json: fixture with allow_base_dirs=["/"], all deny flags off.
- tests/test_poisoned_intent.sh: T-POISON-003 added; pass=14 fail=0.

## Test run

```
--- T-POISON-003: argv[1] permissive registry steering ---
PASS: T-POISON-003 decision DENY (contains "policy_decision": "DENY")
PASS: T-POISON-003 reason path disallowed (contains RC-FS-PATH-DISALLOWED)
PASS: T-POISON-003 untrusted_inputs registry arg (contains cap_registry_path_arg)
PASS: T-POISON-003 path arg logged (contains permissive_registry)
PASS: T-POISON-003 hash (record_hash verified)

Summary: pass=14 fail=0
```

FS_WRITE regression: pass=12 fail=0
