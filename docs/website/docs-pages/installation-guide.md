# Installation guide

Atested is an HTTP proxy that sits between your AI agent and the model provider. Setup takes about five minutes.

## Requirements

- Python 3.9 or later
- An Anthropic API key (or another model provider's key)
- An AI agent that lets you configure its API endpoint (Claude Code, Cursor, Aider, or similar)

## Install

Clone the repository and install the Python dependencies.

```bash
git clone https://github.com/atested/governance-layer.git
cd governance-layer
python3 -m venv mcp/.venv
mcp/.venv/bin/python3 -m pip install -r mcp/requirements.txt
```

## Start the proxy

The proxy needs your API key as an environment variable.

```bash
ANTHROPIC_API_KEY=sk-ant-... python3 -m proxy.server
```

It starts on `http://127.0.0.1:8080` by default. You'll see a startup line confirming the port and the upstream provider URL.

Options:

- `--port 9090` to use a different port
- `--host 0.0.0.0` to bind to all interfaces
- `--upstream https://api.openai.com/v1` to point at a different provider
- `--user-identity "my-dev-machine"` to label this install in the chain (or set `ATESTED_USER_LABEL` in your environment)

## Point your agent at the proxy

This is the one configuration change. Tell your agent to send API traffic through Atested instead of directly to the model provider.

```bash
export ANTHROPIC_BASE_URL=http://localhost:8080/anthropic
```

For Claude Code, add this to your shell profile (`.bashrc`, `.zshrc`, or `.bash_profile`) so it persists across sessions.

For other agents, find the setting that controls the API endpoint and set it to `http://localhost:8080/anthropic`. The setting name varies by agent. If the agent uses the Anthropic SDK, `ANTHROPIC_BASE_URL` is usually the right environment variable.

## Verify governance is running

Run your agent normally. Open the dashboard to see what happened.

```bash
python3 dashboard/server.py
```

Open `http://localhost:9700` in a browser. You should see the Overview page with governance activity counts and a recent activity feed showing ALLOW and DENY decisions for your agent's tool calls.

If the dashboard shows data, governance is working. Every tool call your agent's model proposes is being classified, evaluated against policy, and recorded in the chain before the agent can act on it.

## Signing (optional)

Atested can sign chain records with an Ed25519 key. This makes the chain cryptographically verifiable by anyone who has the public key.

Generate a key:

```bash
openssl genpkey -algorithm Ed25519 -out signing.key
chmod 600 signing.key
```

Set the environment variable before starting the proxy:

```bash
export GOV_SIGNING_KEY_PATH=./signing.key
```

The proxy logs the key fingerprint on startup. Records from this point forward are signed. Older unsigned records remain valid; the verifier handles the boundary.

## Provider configuration

Atested supports Anthropic natively. Multi-provider support (OpenAI, Gemini, LiteLLM-compatible endpoints) is coming. The `--upstream` flag lets you point at any API that uses the standard tool call format, but classification accuracy depends on the provider's tool call structure matching what the classifier expects.

## What "done" looks like

When Atested is running correctly:

- Your agent works normally. It doesn't know governance is in the path.
- Every tool call the model proposes is classified by evidence (file paths, command strings, URLs) and evaluated against policy rules before the agent sees it.
- ALLOW decisions pass through. The agent executes the tool call.
- DENY decisions are replaced with a denial message. The agent sees the denial instead of the tool call and adapts.
- The dashboard shows every decision in real time. The chain records everything.
