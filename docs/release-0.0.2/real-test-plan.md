# Real/Mock Test Split — Plan

**Date:** 2026-06-26
**Status:** Implemented (2026-06-26)

---

## Design

### Rules

| Marker | `--real` not passed | `--real` passed |
|--------|---------------------|-----------------|
| `@pytest.mark.mock` | Runs (mock) | Runs (mock) — always mock |
| `@pytest.mark.real` | Skips | Runs (real API) |
| No marker | Runs (mock) | Runs (mock) |

### Stub pattern (no duplication)

Each test that can run both ways is a **single function** that takes a `terra` fixture. The fixture decides mock vs real based on markers + `--real` flag. No `_real`/`_mock` function pairs needed — the same test runs in both modes.

For tests that need different assertions for mock vs real (e.g. "response is non-empty" vs "response contains 'mocked'"), use a helper:

```python
def _assert_response(responses, terra):
    """Assert a non-empty response regardless of mock/real."""
    assert len(responses) > 0
    assert responses[0].strip() != ""
```

For tests that need completely different setup (e.g. real tests need `real_terra` fixture with key), use `pytest.skip` inside the test:

```python
def test_effort_level(terra, request):
    if not request.config.getoption("--real"):
        pytest.skip("need --real for API test")
    # ... real API assertions
```

### conftest changes

The `terra` fixture will:
1. Check for `@pytest.mark.mock` → always mock
2. Check for `@pytest.mark.real` + `--real` + key → real
3. Otherwise → mock

A new `pytest.mark.real` without `--real` → skip via `pytest.skip` in the fixture or test.

---

## Test inventory

### Tests currently marked `@pytest.mark.real` → rename to `_real` stubs needed

These are already real-only. They need mock versions added.

| File | Test | What it does |
|------|------|--------------|
| `test_console.py` | `TestTestTool::test_async_ai_call` | Trigger phrase → AI response |
| `test_console.py` | `TestTestTool::test_unknown_command_routes_to_ai` | `.unknown` → AI |
| `test_console.py` | `TestPM::test_pm_trigger_routes_to_ai` | PM trigger → AI |
| `test_console.py` | `TestPM::test_pm_unknown_command_routes_to_ai` | PM `.unknown` → AI |
| `test_console.py` | `TestPM::test_ai_command_context_free` | `.ai` in PM |
| `test_console.py` | `TestPM::test_pm_direct_message` | Plain PM text → AI |
| `test_console.py` | `TestPM::test_pm_setlocation_forwards_to_ai` | PM `.setlocation` → AI |
| `test_console.py` | `TestNoisy::test_noisy_on_sends_notice` | Noisy notice on AI call |
| `test_console.py` | `TestRealAPI::test_real_effort_level` | `.effort low` → AI confirms |
| `test_console.py` | `TestRealAPI::test_real_unknown_command_goes_to_ai` | `.unknown` → AI responds |
| `test_console.py` | `TestRealAPI::test_real_noisy_toggle` | `.noisy` toggle |
| `test_console.py` | `TestRealAPI::test_real_setlocation_goes_to_ai` | `.setlocation` → AI responds |
| `test_console.py` | `TestRealAPI::test_real_pm_trigger_responds` | PM trigger → AI responds |
| `test_console.py` | `TestRealAPI::test_real_pm_effort_level` | PM `.effort low` → confirms |
| `test_console.py` | `TestRealAPI::test_real_noisy_sends_notice_on_ai_message` | Noisy notice on AI |
| `test_providers.py` | `test_real_chat` | Real provider chat |
| `test_providers.py` | `test_real_chat_with_system_prompt` | Real provider with system prompt |

### Tests currently unmarked (mock by default) → need `@pytest.mark.mock` + `_real` versions

These run as mock now. They should be marked `@pytest.mark.mock` and real versions added.

| File | Test | What it does |
|------|------|--------------|
| `test_console.py` | `TestTestTool::test_send_message` | `.optin` → "opted in" |
| `test_console.py` | `TestTestTool::test_regular_message_ignored` | No trigger → no response |
| `test_console.py` | `TestTestTool::test_help_command` | `.help` → command list |
| `test_console.py` | `TestPM::test_pm_management_command` | PM `.optin` → "opted in" |
| `test_console.py` | `TestPM::test_pm_help_command` | PM `.help` → command list |
| `test_console.py` | `TestPM::test_clear_command` | `.clear` → "cleared" |
| `test_console.py` | `TestPM::test_compact_admin_only_for_non_admin` | `.compact` admin gate |
| `test_console.py` | `TestNoisy::test_noisy_toggle` | `.noisy` toggle ON/OFF |
| `test_console.py` | `TestNoisy::test_noisy_off_no_notice` | No notice when OFF |
| `test_console.py` | `TestInteractiveMode::test_interactive_launches_and_exits` | Launch + quit |
| `test_console.py` | `TestInteractiveMode::test_interactive_accepts_input` | Type + submit |
| `test_console.py` | `TestInteractiveMode::test_interactive_accepts_pm` | `/msg` → PM |
| `test_console.py` | `TestInteractiveMode::test_interactive_empty_input` | Empty input |
| `test_console.py` | `TestInteractiveMode::test_interactive_ctrl_d_exits` | Ctrl+D exits |
| `test_console_screenshots.py` | All 9 tests | UI behavior via pilot |

### Tests that already have both versions (refactor needed)

None currently. The old `TestRealAPI` class was a separate class — the new design merges them into the same test class with markers.

### Tests we are NOT working on (and why)

| File | Test | Why not |
|------|------|---------|
| `test_commands.py` | All | Pure unit tests for prompts/context — no AI call, no provider. Mock/real split not applicable. |
| `test_database.py` | All | Pure DB tests — no AI call. Mock/real split not applicable. |
| `test_ergo.py` | All | Integration tests requiring a running Ergobot IRC server. Out of scope for this rewrite. |
| `test_integration.py` | `test_is_opted_in_default`, `test_is_opted_in_after_optout`, `test_should_respond_*` | Pure routing logic — no AI call. |
| `test_integration.py` | `test_effort_*` | Tests effort config — no AI call. |
| `test_integration.py` | `test_reasoning_for_model_*` | Tests model config — no AI call. |
| `test_integration.py` | `test_handle_optin`, `test_handle_optout` | Pure routing — no AI call. |
| `test_integration.py` | `test_add_and_list_prompts`, `test_rmprompt`, `test_help` | Pure routing — no AI call. |
| `test_providers.py` | `test_name`, `test_is_available_*` | Pure config — no AI call. |
| `test_providers.py` | `test_chat`, `test_chat_without_system_prompt` | Uses `mock_client_cls` fixture — already mock-only. |
| `test_providers.py` | `test_get_returns_none_when_empty`, `test_set_and_get`, `test_to_dict`, `test_repr` | Pure config — no AI call. |
| `test_providers_extended.py` | All | Provider fallback tests — use mock clients. |

---

## Implementation steps

1. **Update `conftest.py`** — `terra` fixture respects `@pytest.mark.mock` / `@pytest.mark.real` per the rules above.

2. **Refactor `test_console.py`**:
   - Remove `TestRealAPI` class — fold into existing test classes.
   - Add `@pytest.mark.mock` to tests that are mock-only by nature (routing tests that don't need AI).
   - Add `@pytest.mark.real` to tests that should also run against real API.
   - Tests that work identically in both modes just need the marker — no code change.

3. **Refactor `test_integration.py`**:
   - `test_handle_ai_message`, `test_addressed_freeform_allows_bots` → add `@pytest.mark.real` + mock versions.

4. **Refactor `test_providers.py`**:
   - `test_real_chat`, `test_real_chat_with_system_prompt` → add `@pytest.mark.mock` versions.

5. **Update `pytest.ini`** — add `mock` marker.

6. **Run all mock tests** — `pytest` (default).
7. **Run all real tests** — `pytest --real -m real` (requires key).
8. **Run everything** — `pytest --real`.

---

## Key decisions

- **No `_real`/`_mock` function pairs.** The same test function runs in both modes. The `terra` fixture decides.
- **Tests that can't hit AI stay unmarked** (default mock). They don't need real versions.
- **`@pytest.mark.mock` is opt-in** — explicit is better than implicit. Tests that should always be mock get the marker.
- **`@pytest.mark.real` without `--real` → skip** — handled by the fixture or `pytest.skip` in the test.
