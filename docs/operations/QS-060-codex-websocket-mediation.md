# QS-060 Codex WebSocket Mediation Status

Date: 2026-05-26

Codex Realtime traffic uses OpenAI WebSocket events. The current proxy routes
HTTP provider endpoints and mediates OpenAI Chat Completions, Responses API
function calls, and SSE tool-call streams. Before QS-060 there was no parser
coverage for OpenAI Realtime function-call events, so Codex WebSocket activity
could appear as provider-level OpenAI integrity/proxy observations instead of
governed ALLOW/DENY decisions.

QS-060 adds OpenAI Realtime function-call extraction coverage for
`response.output_item.done`, `response.function_call_arguments.done`, and
`response.done` events whose item is a `function_call` or `tool_call`. The
extracted call is classified and policy-evaluable through the same `ToolCall`
shape used by the HTTP OpenAI provider.

Remaining boundary: the raw TCP proxy server still does not implement a full
WebSocket tunnel. Until that tunnel is wired, `proxy_request_observed` records
for OpenAI WebSocket requests mean the proxy examined the request but did not
see tool calls in a response body to policy-evaluate. The dashboard text now
states that correctly instead of describing those events as outside the
mediation boundary.
