# How the classifier works

The classifier (`scripts/classifier.py`) takes a tool call (name and arguments) and returns a classification: what the tool call does, what it targets, how confident the classifier is, and what evidence supports the classification.

## The classification output

Every tool call produces a classification dict:

```
action_type:      read, write, delete, execute, network, move, list, create_directory, ...
targets:          ["/path/to/file", "https://example.com", ...]
scope:            local, repository, system, remote, privileged
confidence_tier:  1 (direct), 2 (inferred), 3 (opaque), 4 (uninspectable)
evidence:         { source: "how this was classified", details: { ... } }
original_tool:    "Bash" or "Write" or whatever the model called
```

The policy evaluator takes this classification and matches it against the policy rules. The classification is the evidence; the policy rules are the judgment.

## How evidence is extracted

The classifier looks at two things: the tool name and the tool's arguments.

From the arguments, it extracts targets. It checks standard parameter names: `file_path`, `path`, `src`, `dst`, `directory`, `command`, `url`, and about a dozen others. If the arguments contain file paths, the classifier knows the targets. If they contain a command string, the classifier parses the command.

From the tool name, it infers the action type. Tokens in the name are matched against indicator lists. A tool name containing "write," "edit," "modify," or "update" is classified as a write. A name containing "read," "get," "fetch," or "view" is classified as a read. A name containing "delete," "remove," or "rm" is classified as a delete. These indicators work across tool naming conventions because they match common English verbs.

## The four confidence tiers

**Tier 1: Directly observable.** The tool call's effects are fully visible in its parameters. A `Write(file_path="/src/app.js", content="...")` is Tier 1. The classifier sees the path, knows the action is a write, and can check the path against policy. Most file operations (Read, Write, Edit, Glob, Grep) land here.

**Tier 2: High-confidence inferred.** The tool call is a command execution, but the command is well-known and its behavior is predictable from the command string. `Bash("git push origin main")` is Tier 2. The classifier recognizes `git push` as a network-scope operation. It knows the patterns for about 40 common commands: git, curl, wget, ssh, npm, pip, docker, make, pytest, and others. Each command gets subcommand-level analysis (e.g., `git push` is network, `git status` is read-only).

**Tier 3: Opaque execution.** The entry point is visible but the behavior is unknown. `Bash("python3 deploy.py")` is Tier 3. The classifier sees that Python is being invoked with a script argument. It knows something will execute, but not what. Piped commands, subshells, and interpreter invocations all land here. The classifier flags these honestly: "I can see what's being launched but not what it does."

**Tier 4: Uninspectable.** The parameters contain encoded or obfuscated content. Base64 blobs, hex-encoded payloads, arguments that can't be parsed as text. The classifier detects encoding patterns and flags the operation as uninspectable. These get a flat DENY in the standard policy.

## How tiers map to policy

The default policy rules use tiers directly:

- Tier 4 operations are denied before any other rule is checked.
- Tier 1 and 2 reads within allowed directories are allowed.
- Tier 1 and 2 writes within allowed directories are allowed (with additional checks: no hidden paths, no executable outputs).
- Tier 3 operations are denied with a reason code suggesting approval review.
- Operations outside allowed directories are denied regardless of tier.

The operator can customize these mappings. An operator who trusts their Python scripts might add a rule allowing specific Tier 3 patterns. An operator in a high-security environment might restrict Tier 2 network operations to require approval.

## Agent-internal operations

Some tool calls have no external side effects. `TaskCreate`, `AskUserQuestion`, `WebSearch`, `EnterPlanMode`, and similar agent-internal tools don't write files, run commands, or touch the network. The classifier recognizes these by name and classifies them as `agent_internal` at Tier 1. The default policy allows them unconditionally because there's nothing to govern.

## Unknown tools

When the classifier encounters a tool it hasn't seen before, it doesn't reject it. Per INV-009, unknown tools are auto-classified to the nearest category based on whatever evidence the parameters provide. If the arguments contain file paths, the classifier infers a file operation. If the arguments contain URLs, it infers a network operation. If nothing is recognizable, the tool gets a Tier 3 opaque classification. Learned mappings are persisted so the same unknown tool gets consistent treatment on subsequent encounters.

## Sensitive paths

Certain paths are classified at `privileged` scope regardless of other evidence: `/etc/`, `~/.ssh/`, `~/.gnupg/`, `~/.aws/`, `~/.config/`, `.env` files, and paths containing `/credentials`, `/secrets`, `/tokens`, or `/private_key`. Operations targeting these paths hit the sensitive-path-deny rule early in the policy evaluation and are denied before general rules are checked.
