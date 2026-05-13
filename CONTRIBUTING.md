# Contributing to Atested

Thank you for your interest in contributing.

## Reporting Bugs

Open a [GitHub Issue](https://github.com/atested/governance-layer/issues) with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version and OS

## Suggesting Features

Open a GitHub Issue with the `enhancement` label. Describe the use case, not just the solution.

## Code Contributions

1. Fork the repo and create a branch from `main`.
2. Write tests for any new functionality.
3. Run the test suite: `python3 -m pytest tests/ -q --ignore=tests/test_shell_contracts.py`
4. Ensure your code passes the CI checks.
5. Open a pull request against `main`.

### Code Style

- Python 3.11+.
- No type stubs or runtime type-checking libraries required. Use type hints where they clarify intent.
- Tests go in `tests/`. Test filenames match `test_*.py`.
- Keep functions short. Prefer pure functions where practical.

### Commit Messages

- Start with a verb: "Add", "Fix", "Remove", "Update".
- One logical change per commit.

## Security Vulnerabilities

Do not open a public issue for security vulnerabilities. See [SECURITY.md](SECURITY.md).

## License

This project is licensed under the [Business Source License 1.1](LICENSE). By contributing, you agree that your contributions will be licensed under the same terms.
