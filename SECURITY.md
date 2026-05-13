# Security Policy

## Reporting a Vulnerability

Report security vulnerabilities to **security@atested.com**.

Include:
- Description of the vulnerability
- Steps to reproduce
- Affected component (proxy, classifier, dashboard, chain integrity)
- Impact assessment if known

## Response

- **Acknowledgment**: within 48 hours.
- **Coordinated disclosure**: 90 days from report to public disclosure, unless agreed otherwise.
- We will credit reporters in the fix advisory unless they prefer to remain anonymous.

## Scope

- This repository (`atested/governance-layer`)
- The Atested proxy, classifier, policy evaluator, and dashboard
- The governance chain integrity guarantees
- [atested.com](https://atested.com)

## Out of Scope

- Social engineering attacks against maintainers
- Denial of service attacks
- Vulnerabilities in upstream dependencies (report those to the dependency maintainer)
- Issues in archived code (`mcp/_archived/`)

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
