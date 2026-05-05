# Installation guide

Atested is an HTTP proxy that sits between your AI agent and the model provider. Setup takes about five minutes.

## Requirements

- Python 3.9 or later
- An API key for Anthropic, OpenAI, or any provider whose API follows the standard chat completions format with tool calls
- An AI agent that allows configuring its API endpoint. Claude Code, Cursor, and Aider are tested. Other agents that expose an API endpoint setting work the same way.

## Install

Clone the repository and install the Python dependencies.

```bash
git clone https://github.com/atested/governance-layer.git atested
cd atested
python3 -m venv mcp/.venv
mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt
```

## Initialize

Run the init command to create the runtime directory, generate a signing key, and configure policy for your working directories.

```bash
python3 scripts/atested_cli.py init
```

By default, init configures the current working directory as an allowed base directory for your AI agent. To specify different directories:

```bash
python3 scripts/atested_cli.py init --dirs /path/to/project1 /path/to/project2
```

Init creates:

- `gov_runtime/` — runtime data directory (chain, logs, metadata)
- `gov_runtime/.atested-signing-key.pem` — Ed25519 key for signing chain records (permissions: 600)
- `capabilities/policy-rules.json` — updated with your working directories

## Provider setup

Atested governs tool calls at the API transport layer. Each provider has its own API structure, authentication, and tool call format. The proxy handles these differences internally. Configure the provider you use before starting the proxy.

### Anthropic

Set your API key. Anthropic is the default upstream, so no additional flags are needed.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

The proxy route is `/anthropic`. You will point your agent's base URL to `http://localhost:8080/anthropic`.

### OpenAI

Set your API key and specify the upstream URL.

```bash
export OPENAI_API_KEY=sk-...
```

Start the proxy with the `--upstream` flag:

```bash
python3 -m proxy.server --upstream https://api.openai.com/v1
```

The proxy route is `/openai`. You will point your agent's base URL to `http://localhost:8080/openai`.

OpenAI's tool call format differs from Anthropic's. The classifier handles the structural differences, but classification confidence may vary between providers because the evidence available in tool call parameters is provider-dependent.

### Other providers

Any provider whose API follows the standard chat completions format with tool calls can work with the `--upstream` flag. Classification accuracy depends on how much structural evidence the provider includes in its tool call payloads.

## Start the proxy

Run the proxy using the environment variables you configured in Provider setup. For Anthropic (the default):

```bash
python3 -m proxy.server
```

For OpenAI and other providers, include the `--upstream` flag as shown in your provider's section above.

The proxy starts on `http://127.0.0.1:8080` by default. You'll see a startup line confirming the port and the upstream provider URL.

Options:

- `--port 9090` to use a different port
- `--host 0.0.0.0` to bind to all interfaces
- `--user-identity "my-dev-machine"` to label this install in the chain (or set `ATESTED_USER_LABEL` in your environment)

## Point your agent at the proxy

This is the one configuration change. Tell your agent to send API traffic through Atested instead of directly to the model provider.

For Anthropic (Claude Code, agents using the Anthropic SDK):

```bash
export ANTHROPIC_BASE_URL=http://localhost:8080/anthropic
```

For OpenAI:

```bash
export OPENAI_BASE_URL=http://localhost:8080/openai
```

Add the export to your shell profile (`.bashrc`, `.zshrc`, or `.bash_profile`) so it persists across sessions.

For other agents, find the setting that controls the API endpoint and set it to the matching Atested route for your provider.

## Verify Atested is running

Run your agent normally. Open the Atested Dashboard to confirm governance is active.

```bash
python3 dashboard/server.py
```

Open `http://localhost:9700` in a browser. On the Overview page, look for:

- **Chain health** showing a green integrity indicator and a non-zero event count.
- **Governance activity** showing mediated operations, with ALLOW and DENY counts.
- **Recent activity feed** listing your agent's tool calls with their policy decisions.

If the dashboard shows activity, governance is working. Every tool call your agent's model proposes is being classified, evaluated against policy, and recorded in the chain before the agent can act on it.

## What "done" looks like

When Atested is running correctly:

- Your agent works normally. It doesn't know governance is in the path.
- Every tool call the model proposes is classified by evidence (file paths, command strings, URLs) and evaluated against policy rules before the agent sees it.
- ALLOW decisions pass through. The agent executes the tool call.
- DENY decisions are replaced with a denial message. The agent sees the denial instead of the tool call and adapts.
- The Atested Dashboard shows every decision in real time. The chain records everything, signed with your Ed25519 key.

## What to expect in the first session

The proxy governs by policy. Operations within your configured working directories are allowed automatically. Operations outside that scope, or opaque commands the proxy cannot fully inspect, are denied until you approve them.

Your first session will have the most approval prompts as the proxy encounters new tools and paths for the first time. After that, approvals should be rare. Each approval is you deciding what is acceptable in your environment.
