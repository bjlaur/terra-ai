# Plan: Fix effort, then profile all tests

## Context

User wants faster tests. But first: `.effort` is broken — it stores a value that never reaches the AI provider. We must fix that, then use `.effort low` when running timing tests so real API calls are fast and cheap.

Research Source: `~/openrouter_reasoning_effort_notes.md`

---

## Branch

```bash
cd /home/agent/agentic-repos/terra-ai-agent1
git checkout -b agent1/test-profiling
```

## Step 1: Fix `.effort` — unify the two attributes

**Bug:** `.effort low` writes to `self.prompts.effort` (PromptManager) but `handle_ai_message` passes `self._effort` (TerraAI instance). These are two separate attributes.

**Fix in `terra_ai/plugin.py`:**

```python
# In TerraAI.handle_ai_message(), change:
response = provider.chat(msg_objs, effort=self._effort)
# To:
response = provider.chat(msg_objs, effort=self.prompts.effort)
```

Also remove the duplicate `self._effort = config.bot.get("effort", "high")` init in `TerraAI.__init__` — just use `self.prompts.effort` everywhere.

## Step 2: Wire effort into OpenRouter provider

**Current state:** `OpenRouterProvider.chat()` accepts `effort` kwarg and ignores it.

**Fix:** Add a `reasoning` config to the payload based on the model. Source: `~/openrouter_reasoning_effort_notes.md` — "Do not blindly send reasoning controls. Gate by model."

**File:** `terra_ai/providers/openrouter.py`

Add a static mapping function:

```python
def _reasoning_for_model(model: str, effort: str) -> dict | None:
    effort = effort.lower()
    # owl-alpha: reasoning not exposed via chat-completions metadata
    if model == "openrouter/owl-alpha":
        return None
    # Gemini 2.5+: use thinking budget (max_tokens)
    if model.startswith("google/gemini-2.5"):
        budgets = {"low": 1024, "medium": 4096, "high": 8192, "xhigh": 16384, "max": 24576}
        return {"max_tokens": budgets.get(effort, 4096), "exclude": True}
    # Claude: max_tokens + effort
    if model.startswith("anthropic/"):
        return {"enabled": True, "effort": effort, "exclude": True}
    # OpenAI reasoning models (o3, o4-mini, gpt-5)
    if model.startswith("openai/o") or model.startswith("openai/gpt-5"):
        return {"effort": effort, "exclude": True}
    # Gemini 2.0 flash, GPT-4o, GPT-4o-mini: no reasoning support
    return None
```

Then in `chat()`:

```python
reasoning = _reasoning_for_model(self._model, effort)
if reasoning:
    payload["reasoning"] = reasoning
```

## Step 3: Add test for `.effort` working end-to-end

**File:** `tests/test_integration.py` (or new test)

```python
class TestEffortWire:
    def test_effort_reaches_provider(self, monkeypatch, terra):
        """Verify .effort low causes reasoning config in API payload."""
        captured = {}

        def fake_chat(self, messages, system_prompt=None, effort="high"):
            captured["effort"] = effort
            captured["reasoning_in_payload"] = "reasoning" in self._last_payload
            return "ok"

        monkeypatch.setattr(type(terra.provider), "chat", fake_chat)
        terra.prompts.set_effort("low")
        terra.handle_ai_message("irc.example.com", "#chan", "nick", "hello")
        assert captured["effort"] == "low"

    def test_effort_ignored_for_unsupported_models(self, monkeypatch, terra):
        """Verify owl-alpha does not get reasoning field."""
        terra.provider._model = "openrouter/owl-alpha"
        captured_payload = {}

        original_chat = type(terra.provider).chat
        def spy_chat(self, messages, system_prompt=None, effort="high"):
            captured_payload.update(self._last_payload or {})
            return original_chat(self, messages, system_prompt, effort)

        monkeypatch.setattr(type(terra.provider), "chat", spy_chat)
        terra.prompts.set_effort("low")
        terra.handle_ai_message("irc.example.com", "#chan", "nick", "hello")
        assert "reasoning" not in captured_payload
```

Also add provider-level unit test: `_reasoning_for_model` returns correct dict (or None) per model slug.

## Step 4: Run all tests with timing

```bash
cd /home/agent/agentic-repos/terra-ai-agent1
pytest tests/ --ignore=tests/test_ergo.py --durations=0 --tb=no -v 2>&1 | tee /tmp/timing-all.txt
```

## Step 5: If there are failures, re-run only those with short tb

```bash
pytest tests/path/to/test_file.py::TestClass::test_name --tb=short -v
```

## Step 6: Write test-time.md report

Create `tests/test-time.md` with structure:

```markdown
# Test Timing Report

Date: 2026-06-26
Branch: agent1/test-profiling

## Summary

| Category | Count | Total Time | Avg Time |
|----------|-------|------------|----------|
| Fast (<0.1s) | ... | ... | ... |
| Medium (0.1-1s) | ... | ... | ... |
| Slow (1-10s) | ... | ... | ... |
| Very Slow (>10s) | ... | ... | ... |

## All Tests (by file)

[one table per test file, columns: Test | Time (s) | Category]

## Bottleneck Analysis

[top offenders with root cause]
```

## Step 7: Analyze top slow tests

Expected candidates:

| Test | Est. Slowness | Root Cause |
|------|---------------|------------|
| `TestInteractiveMode::test_interactive_accepts_pm` | ~33s | expect_timeout=30 + post_wait=2 + subprocess |
| `TestInteractiveMode::test_interactive_noisy_notice` | ~33s | expect_timeout=30 + post_wait=2 + subprocess |
| `TestInteractiveMode` (other 6 tests) | 10-15s each | pty + subprocess + read loop |

## Verification

After all steps:
- `cat tests/test-time.md` shows complete timing data
- `pytest tests/ --ignore=tests/test_ergo.py` passes with 0 failures
- Check `pwd && git branch --show-current` to confirm branch

## Future optimization ideas (AFTER report, NOT now)

- Reduce timeouts in `_run_interactive_poll` (30s → 5s)
- Reduce timeouts in `_run_interactive` (10s → 3s)
- Eliminate unnecessary `post_wait` sleeps
- Share subprocess across tests via session-scoped fixture
- Mock openrouter provider in `test_async_ai_call` to remove real API dependency
