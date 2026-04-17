# Policy rules reference

Atested's policy is a JSON file: `capabilities/policy-rules.json`. It's a list of rules evaluated in order. The first rule that matches a tool call's classification wins. The rule says ALLOW or DENY.

## The policy file

```json
{
  "policy_version": "2.0",
  "default_decision": "DENY",
  "default_reason": "No matching policy rule",
  "base_dirs": ["/your/project/root", "/your/runtime/dir"],
  "deny_hidden_paths": true,
  "deny_executable_outputs": true,
  "rules": [ ... ]
}
```

`default_decision` is what happens when no rule matches. It's DENY. If you remove all rules, everything is denied. This is the fail-closed default.

`base_dirs` is the list of directories your agent is allowed to work in. File operations targeting paths outside these directories are denied by the `outside-base-dirs-deny` rule at the bottom of the default ruleset. Two placeholder values (`__GOV_CANONICAL_REPO_PATH__` and `__GOV_RUNTIME_PATH__`) are resolved at load time to the governance-layer repository root and the runtime directory.

`deny_hidden_paths` and `deny_executable_outputs` are global constraints. When true, writes to hidden paths (files or directories starting with `.`) and writes that create executable files are denied even if the action would otherwise be allowed.

## Rule structure

Each rule has an id, a description, match conditions, a decision, and a reason.

```json
{
  "id": "write-source-allow",
  "description": "Allow writes within base dirs (non-hidden, non-executable)",
  "match": {
    "action_type": ["write"],
    "confidence_tier": [1, 2],
    "scope": ["local", "repository"],
    "target_within_base_dirs": true,
    "no_hidden_paths": true,
    "no_executable_output": true
  },
  "decision": "ALLOW",
  "reason": "Write within governed scope"
}
```

The `match` object tests conditions against the classifier's output. All conditions in the match must be true for the rule to apply. If the rule matches, its decision (ALLOW or DENY) is the final answer.

## Match conditions

- `action_type`: list of action types this rule applies to. The classifier produces one of: read, write, delete, execute, network, move, list, create_directory, configuration_change, credential_access, agent_internal, unknown.
- `confidence_tier`: list of tiers. [1, 2] means the rule applies to Tier 1 and Tier 2 classifications only.
- `scope`: list of scopes. The classifier assigns: local, repository, system, remote, privileged.
- `target_within_base_dirs`: if true, all targets must be within the `base_dirs` paths.
- `no_hidden_paths`: if true, none of the targets may be hidden paths.
- `no_executable_output`: if true, the operation must not create executable files.

## The default ruleset

The default rules, in evaluation order:

1. **tier4-deny.** Tier 4 (uninspectable) operations are denied. This fires before anything else.
2. **sensitive-path-deny.** Operations targeting sensitive paths (scope: privileged) are denied. Catches `/etc/`, `~/.ssh/`, `.env`, and similar.
3. **agent-internal-allow.** Agent-internal operations at Tier 1 (TaskCreate, WebSearch, AskUserQuestion, etc.) are allowed. These have no external effects.
4. **read-source-allow.** Reads at Tier 1-2 within base dirs are allowed.
5. **list-source-allow.** Directory listings and mkdir at Tier 1-2 within base dirs are allowed.
6. **write-source-allow.** Writes at Tier 1-2 within base dirs are allowed, with the hidden-path and executable-output constraints.
7. **move-source-allow.** Moves at Tier 1-2 within base dirs are allowed, with the hidden-path constraint.
8. **delete-source-allow.** Deletes at Tier 1-2 within base dirs are allowed, with the hidden-path constraint.
9. **network-deny.** Network operations at remote scope are denied. Curl, wget, ssh, and outbound requests require explicit approval.
10. **execute-tier2-allow.** Tier 2 executions at local/repository scope are allowed. This covers well-known commands like git, make, pytest that the classifier confidently recognized.
11. **tier3-approval-required.** Tier 3 (opaque) operations are denied with a reason suggesting the operator review and approve if appropriate.
12. **outside-base-dirs-deny.** Anything targeting paths outside base dirs is denied.

If nothing matches, the `default_decision` fires: DENY.

## Customizing the policy

Edit `capabilities/policy-rules.json` directly. Add rules, remove rules, reorder rules. The evaluator reads the file at startup and on dashboard-triggered reload.

Common customizations:

**Allow a specific Tier 3 command.** Add a rule before `tier3-approval-required` that matches the specific command pattern and allows it.

**Block all writes.** Move `write-source-allow` to after the default deny, or remove it entirely. All file writes become denied.

**Allow network access to specific hosts.** The classifier puts URLs in the `targets` list. A rule matching specific target patterns against an allowlist would let approved network destinations through while keeping the general network-deny in place. (Target pattern matching in rules is on the roadmap but not yet implemented. For now, use the approval mechanism for specific network operations.)

## How approvals interact with policy

When an operation is denied, the operator can approve it through the dashboard. The approval records the operation identifier, the operator's name, and a scope. Once approved, the proxy checks the approval store before applying a DENY decision. If the operation has an active approval, the DENY is overridden and the operation is allowed.

Approvals are recorded in the chain as `operation_approval` events. Revocations are recorded as `operation_revocation` events. Both are visible in the Approvals page and the audit trail.

This mechanism is how operators handle Tier 3 operations in practice. The default policy denies them. The operator reviews the specific operation, decides it's acceptable, and approves it. The approval persists until revoked.

## The capability registry

The `base_dirs`, `deny_hidden_paths`, `deny_executable_outputs`, and per-tool constraint overrides live in the policy-rules file but are conceptually the "capability registry." The Configuration page in the dashboard lets the operator view and edit these settings (with license key verification for edit access). Changes through the Configuration page write to the same `policy-rules.json` file and take effect on the next policy reload.
