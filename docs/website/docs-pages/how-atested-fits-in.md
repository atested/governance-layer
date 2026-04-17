# How Atested fits in

Atested is an HTTP proxy. It sits between your AI agent and the model provider (Anthropic, OpenAI, or others). The agent sends API requests through Atested. Atested forwards them upstream, gets the model's response, and inspects it before passing it back.

## The interception point

When an AI agent calls a model, the model responds with a mix of text and tool calls. The text is the model thinking or talking. The tool calls are the model telling the agent to do something: write a file, run a command, make a network request. Tool calls have consequences. Text doesn't.

Atested intercepts at the API response. It buffers the response from the model, finds the `tool_use` blocks (the tool calls), and classifies each one. Text blocks stream through untouched. Only tool calls get inspected.

This happens before the agent sees the response. The agent doesn't know Atested is there. If a tool call is allowed, the agent receives it normally and executes it. If a tool call is denied, the agent receives a denial message in place of the tool call. The model proposed something; Atested decided whether to let the agent see it.

## What the proxy touches

Atested reads the content blocks in model responses. It parses `tool_use` blocks to extract tool names, arguments, file paths, URLs, and command strings. It classifies each tool call using this observable evidence and evaluates the classification against declarative policy rules.

The proxy does not modify the model's text output. It does not modify allowed tool calls. It replaces denied tool calls with a text block explaining the denial, including the reason code and the matched policy rule.

## What the proxy doesn't touch

Atested does not read or modify the agent's prompts, system messages, or conversation history going upstream. It does not inject instructions into the model's context. It does not cache or store conversation content. Request bodies pass through to the model provider unchanged.

Atested also does not control what happens after an allowed tool call reaches the agent. If the model proposes `Bash("rm -rf /")` and policy allows it, Atested records the ALLOW decision and the agent executes the command. Governance happens at the decision point, not at execution time. This is a real boundary, discussed further in "What Atested can and can't do."

## The one-environment-variable integration

The agent talks to the model through an API endpoint. Normally that endpoint is `https://api.anthropic.com` or equivalent. Atested changes it to `http://localhost:8080/anthropic`. That's the integration. One environment variable (`ANTHROPIC_BASE_URL`), one value change.

The proxy forwards requests to the real provider, so the agent's behavior is unchanged. Model selection, temperature, max tokens, system prompts, tools available to the model: all controlled by the agent as before. Atested doesn't alter what the model can do. It evaluates what the model proposes to do.

## Streaming

Atested supports streaming responses. Text chunks stream through with minimal latency (the proxy passes them as they arrive). Tool call blocks are buffered because classification requires the complete tool call (you can't classify half a file path). The buffer adds sub-millisecond overhead per tool call. In practice, the operator doesn't notice.

## What the operator's agent experiences

An agent running through Atested behaves normally for allowed operations. Tool calls go through, results come back, the model sees them and continues.

For denied operations, the agent receives a text block where the tool call would have been. The text says the operation was denied, names the policy rule, and gives the reason. The model reads this denial, understands the operation wasn't permitted, and adapts. Most agents handle denials gracefully. They try an alternative approach or ask the operator for guidance.

The agent never calls a special governance API. It never imports a governance library. It uses its normal tools (Read, Write, Bash, Grep, whatever) and the proxy handles governance transparently at the transport layer.
