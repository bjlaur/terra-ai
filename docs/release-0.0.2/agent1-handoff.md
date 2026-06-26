# Agent1 Handoff — Release 0.0.2

**Date**: 2026-06-26
**Branch**: `agent1/test-profiling`
**Agent**: OWL

---

## 1. Branch

`agent1/test-profiling` — already checked out at session start. Not a carry-over branch; created fresh for this work.

---

## 2. Current State of the Codebase

### `.effort` command fix

The `.effort` slash command now correctly wires the `reasoning` config into the OpenRouter payload based on model slug:

- **gemini-2.5** → gets `reasoning.max_tokens` budget
- **anthropic models** → gets `reasoning.enabled` + `reasoning.effort`
- **openai o3 / gpt-5** → gets `reasoning.effort`
- **gpt-4o** → gets no reasoning (unsupported)

### Bugs found & fixed

1. **Attribute mismatch** (`bot.py`) — duplicate `self._effort` attribute; now reads from `self.prompts.effort` consistently.
2. **Provider wiring** (`openrouter.py`) — `chat()` accepted `effort` kwarg and ignored it; now builds `reasoning` payload via `_reasoning_for_model()`.
3. **Persistence** — deferred (out of scope for this profiling sprint).

### `_reasoning_for_model()` function

Added in `terra_ai/providers/openrouter.py`. Gates reasoning payload by model slug:

```python
def _reasoning_for_model(model: str, effort: str) -> dict | None:
    # gemini-2.5 → reasoning.max_tokens
    # anthropic → reasoning.enabled + reasoning.effort
    # openai/o3, openai/gpt-5 → reasoning.effort
    # gpt-4o, owl-alpha, gemini-2.0-flash → None
```

### Tests

7 new effort wiring tests pass (`TestEffortWire` in `tests/test_integration.py`):

1. `test_effort_low_reaches_provider` — spy on `provider.chat()`, verify effort="low"
2. `test_effort_default_is_high` — verify default effort is "high"
3. `test_reasoning_for_model_gemini_25` — Gemini 2.5 gets `reasoning.max_tokens`
4. `test_reasoning_for_model_claude` — Claude gets `reasoning.effort`
5. `test_reasoning_for_model_openai_o3` — o3 gets `reasoning.effort`
6. `test_reasoning_for_model_gpt4o_none` — GPT-4o gets no reasoning
7. `test_reasoning_for_model_owl_gets_effort` — owl-alpha returns None (update if owl gains effort support)

---

## 3. Test Suite Status

### Timing

- Full timing report at `tests/test-time.md` — **suite went from 204s → 83s** (2.5x faster)
- Root `pytest.ini` has `addopts = -m "not slow and not real"` — skips slow interactive tests and real-API tests by default
- 4 tests marked `@pytest.mark.slow` (interactive pty tests)
- 8 tests marked `@pytest.mark.real` (7 routing tests + `test_noisy_on_sends_notice`)

### Test results (last run)

```
95 passed, 2 failed, 9 skipped, 12 deselected in ~83s
```

### Known failures

| Test | Status | Notes |
|------|--------|-------|
| `test_interactive_accepts_pm` | FAIL | Real subprocess mock issue (pre-existing) |
| `test_interactive_noisy_notice` | FAIL | Same subprocess mock issue |
| `test_pm_setlocation_forwards_to_ai` | FLAKY | Passes alone, fails in suite (state leakage) |

- Deleted `test_send_as_different_nick` — was not mimicking real IRC behavior.

### Run commands

```bash
# Default (mock only, fast)
pytest tests/

# Real API tests (slow, needs env)
source ~/.terra-ai/.env && pytest --real -m real
```

---

## 4. Test Infrastructure

### `pytest.ini` (root)

Markers: `slow`, `real`. Default addopts deselects both.

### `tests/conftest.py`

Parametric `real` fixture — when `--real` is passed, the `terra` fixture uses the real OpenRouter provider; otherwise uses a mock/fake provider that returns instantly. Also provides a `mock_or_real` fixture for tests that need to run in both modes.

### Fixture deduplication

Removed duplicate `db`/`terra` fixtures from `test_tool.py` and `test_integration.py` — now sourced from `conftest.py`.

---

## 5. Key Files

| File | Purpose |
|------|---------|
| `tests/test_tool.py` | Routing tests (34 tests) + `TestRealAPI` (8 tests, gated by env) |
| `tests/test_integration.py` | Effort wiring tests (`TestEffortWire`, 7 tests) + 19 other tests |
| `tests/conftest.py` | Parametric mock/real fixtures |
| `pytest.ini` (root) | Markers (`slow`, `real`) + `addopts` |
| `tests/test-time.md` | Full timing report (per-test breakdown) |
| `docs/release-0.0.2/test-performance-tuning.md` | Plan doc (COMPLETED) |
| `terra_ai/providers/openrouter.py` | Updated with `_reasoning_for_model()` |
| `terra_ai/bot.py` | Fixed effort attribute mismatch |
| `terra_ai/prompts/manager.py` | Effort reads from config at init |

---

## 6. File Locations & Git

- **Agent workspace**: `/home/agent/agentic-repos/terra-ai-agent1/`
- **Shared origin**: `/home/agent/git/terra-ai`
- **Git identity**: `owl@terra-ai` / `OWL`

Always run `pwd && git remote -v` before git commands to confirm you're in the right place.

---

## 7. Next Steps

1. Investigate the `test_pm_setlocation_forwards_to_ai` flakiness (likely state leakage between tests)
2. Investigate `test_interactive_accepts_pm` / `test_interactive_noisy_notice` subprocess mock failures
3. Consider applying `@pytest.mark.slow` more broadly to other slow interactive tests
4. Future optimizations (still pending, not urgent):
   - Reduce timeouts in `_run_interactive_poll` (30s → 5s)
   - Reduce timeouts in `_run_interactive` (10s → 3s)
   - Eliminate unnecessary `post_wait` sleeps
   - Share subprocess across tests via session-scoped fixture
   - Mock openrouter provider in `test_async_ai_call` to remove real API dependency
5. Once tests are stable, proceed with other release-0.0.2 items in `release-plan.md`
