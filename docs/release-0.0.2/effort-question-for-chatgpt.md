# Question: How to add reasoning effort to OpenRouter calls?

## Context

We have a Python project that calls OpenRouter's chat completions endpoint. We want to support a "reasoning effort" concept (low/medium/high/xhigh/max) that users can set via a chat command.

OpenRouter uses the OpenAI-compatible `/v1/chat/completions` endpoint. We pass a payload like:

```python
payload = {
    "model": self._model,  # e.g. "google/gemini-2.0-flash-001"
    "messages": [...],
}
```

## What we need

1. Does OpenRouter's API support a `reasoning_effort` parameter (or similar) in the request payload? If so, what are the valid values?

2. Which models support it? Specifically:
   - `google/gemini-2.0-flash-001`
   - `google/gemini-2.5-flash-preview`
   - OpenAI models via OpenRouter (e.g. `openai/gpt-4o`, `openai/gpt-4o-mini`)
   - Claude models via OpenRouter (e.g. `anthropic/claude-sonnet-4-6`)

3. If `reasoning_effort` is not the right field, what IS the correct way to control reasoning/thinking effort on OpenRouter? Some providers use different mechanisms (e.g. Gemini thinking budgets, OpenAI reasoning_effort, etc.)

4. How should we map our internal effort levels (low/medium/high/xhigh/max) to provider-specific values?

5. Should we include it in the payload at the top level, or does it need to go under a specific model's provider config (router ["provider"] field)?

Please provide a concrete payload example showing how to pass reasoning_effort to OpenRouter's /v1/chat/completions endpoint.
