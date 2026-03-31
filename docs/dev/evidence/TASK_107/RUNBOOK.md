# TASK_107 Evidence Helper Runbook

Use `evidence-log.sh` to append standardized command entries to `TESTS.txt`.

## Purpose

- Writes the command line with a leading `$ ` marker using shell-safe quoting.
- Captures command output.
- Writes a required `[exit=N]` marker on its own line.

## Usage

```bash
docs/dev/evidence/TASK_107/evidence-log.sh docs/dev/evidence/TASK_107/TESTS.txt -- <command> [args...]
```

## Examples

```bash
: > docs/dev/evidence/TASK_107/TESTS.txt
docs/dev/evidence/TASK_107/evidence-log.sh docs/dev/evidence/TASK_107/TESTS.txt -- echo "hello evidence"
docs/dev/evidence/TASK_107/evidence-log.sh docs/dev/evidence/TASK_107/TESTS.txt -- bash -lc 'exit 3'
```

This keeps `TESTS.txt` formatting consistent across runs and tasks.
