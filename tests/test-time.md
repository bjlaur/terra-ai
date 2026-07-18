# Test Timing Report

Date: 2026-06-26
Branch: agent1/test-profiling
Commit: 6ed7679 (effort fix)

## Current State (Post-Optimization)

After applying three optimizations, the default test run dropped from **~204s to ~83s**.

**Optimizations applied:**
1. 4 interactive tests marked `@pytest.mark.slow` (skipped by default): `test_interactive_tab_completes_trigger`, `test_interactive_tab_completes_midline`, `test_interactive_ctrl_d_exits`, `test_interactive_history_navigation`
2. Parametric mock/real fixture in `conftest.py` — routing tests are now mocked by default
3. 8 tests marked `@pytest.mark.real` (skipped by default): `test_async_ai_call`, `test_unknown_command_routes_to_ai`, `test_pm_trigger_routes_to_ai`, `test_pm_unknown_command_routes_to_ai`, `test_ai_command_context_free`, `test_pm_direct_message`, `test_pm_setlocation_forwards_to_ai`, `test_noisy_on_sends_notice`

**Default run (mocked, no slow/real):**

| Metric | Value |
|--------|-------|
| Passed | 95 |
| Failed | 2 |
| Skipped | 9 |
| Deselected | 12 |
| Total time | **~83s** |

**12 deselected = 4 slow + 8 real**

**2 failures (deferred — subprocess mock issue):**
- `test_interactive_accepts_pm`
- `test_interactive_noisy_notice`

**Note:** The per-test timing table below reflects the **ORIGINAL (pre-optimization) run** for reference. The "Very Slow" and "Slow" categories for routing/AI tests are now instant in mock mode.

## Ergo Integration Tests (2026-06-26)

Ergo tests run separately: `pytest tests/test_ergo.py` (requires ergo on localhost:6667).

| Test | Time (s) | Status | Notes |
|------|----------|--------|-------|
| TestErgoSmoke::test_ergo_port_open | 0.00 | ✅ | |
| TestErgoSmoke::test_ergo_config_exists | 0.00 | ✅ | |
| TestErgoSmoke::test_can_connect_socket | 0.00 | ✅ | |
| TestErgoIRCProtocol::test_register_nick | 10.01 | ✅ | Socket timeout loop |
| TestErgoIRCProtocol::test_join_channel | 20.02 | ✅ | Socket timeout loop |
| TestErgoIRCProtocol::test_send_and_receive_message | 42.04 | ✅ | Slow — 2s socket timeouts |
| TestErgoIRCProtocol::test_private_message | 21.02 | ✅ | Same pattern |
| TestErgoSopelBot::test_sopel_connects_to_ergo | 1.00 | ✅ | 10s setup (session) |
| TestErgoSopelBot::test_bot_joins_channel | 1.00 | ✅ | |
| TestErgoSopelBot::test_bot_responds_to_help | 2.01 | ✅ | |
| TestErgoSopelBot::test_bot_responds_to_trigger | 2.00 | ✅ | Real AI call |
| TestErgoSopelBot::test_bot_responds_to_unknown_command | 32.03 | ❌ | 451 ERR_NOTREGISTERED |
| TestErgoSopelBot::test_bot_ignores_regular_messages | 5.00 | ✅ | |
| TestErgoSopelBot::test_bot_noisy_toggle | 2.00 | ✅ | |
| TestErgoSopelBot::test_bot_optin_optout | 16.09 | ❌ | 451 ERR_NOTREGISTERED |
| **Total** | **~164s** | **13 pass, 2 fail** | |

### Ergo Optimizations Applied
- Session-scoped `sopel_bot_process` fixture (saved ~60s vs per-test startup)
- Removed `admin_nicks` from test yaml (broke plugin load after rework)
- Fixed `shutdown()` signature for SOPEL 8.0

### Ergo Deferred
- `test_bot_responds_to_unknown_command` + `test_bot_optin_optout`: ergo rejects PRIVMSG with 451 before NICK/USER registration completes. May need to allow unregistered users or fix test client to wait for 001.

## Summary (Original Pre-Optimization)

| Category | Count | Total Time | Avg Time |
|----------|-------|------------|----------|
| Very Slow (>10s) | 8 | ~161s | ~20s |
| Slow (1-10s) | 16 | ~44s | ~2.8s |
| Medium (0.1-1s) | 20 | ~11s | ~0.55s |
| Fast (<0.1s) | 80 | ~3s | ~0.04s |
| **Total** | **127** | **~219s** | **~1.7s** |

Overall suite time: **204s (3m 24s)** excluding ergo tests.

## All Tests (by file) — Original Run

### test_commands.py (14 tests) — FAST

| Test | Time (s) | Category |
|------|----------|----------|
| TestPromptManager::test_is_management_command | 0.01 | Fast |
| TestPromptManager::test_get_system_prompt | 0.01 | Fast |
| TestPromptManager::test_context_seed | 0.01 | Fast |
| TestPromptManager::test_add_and_match_prompt | 0.01 | Fast |
| TestPromptManager::test_match_prompt_not_found | 0.01 | Fast |
| TestPromptManager::test_remove_prompt | 0.01 | Fast |
| TestPromptManager::test_list_prompts | 0.01 | Fast |
| TestPromptManager::test_effort | 0.01 | Fast |
| TestContextManager::test_compose_context | 0.02 | Fast |
| TestContextManager::test_save_exchange | 0.05 | Fast |
| TestContextManager::test_compact | 0.07 | Fast |

### test_database.py (27 tests) — FAST

| Test | Time (s) | Category |
|------|----------|----------|
| All 27 tests | <0.05 each | Fast |

### test_integration.py (23 tests) — MOSTLY FAST

| Test | Time (s) | Category |
|------|----------|----------|
| TestTerraAI::test_is_admin | 0.01 | Fast |
| TestTerraAI::test_is_opted_in_default | 0.01 | Fast |
| TestTerraAI::test_is_opted_in_after_optout | 0.01 | Fast |
| TestTerraAI::test_should_respond_opted_out | 0.01 | Fast |
| TestTerraAI::test_should_respond_opted_in | 0.01 | Fast |
| TestTerraAI::test_should_respond_self | 0.02 | Fast |
| TestTerraAI::test_is_management_command | 0.01 | Fast |
| TestTerraAI::test_handle_ai_message | 0.01 | Fast |
| TestTerraAI::test_handle_management_optin | 0.01 | Fast |
| TestTerraAI::test_handle_management_optout | 0.01 | Fast |
| TestTerraAI::test_handle_management_setlocation | 0.01 | Fast |
| TestPluginRules (3 tests) | <0.02 each | Fast |
| TestAdminCommands (3 tests) | 0.02 each | Fast |
| TestUserCommands::test_effort | 0.01 | Fast |
| TestUserCommands::test_effort_invalid | 0.01 | Fast |
| TestEffortWire::test_effort_low_reaches_provider | 0.02 | Fast |
| TestEffortWire::test_effort_default_is_high | 0.01 | Fast |
| TestEffortWire::test_reasoning_for_model_gemini_25 | 0.01 | Fast |
| TestEffortWire::test_reasoning_for_model_claude | 0.01 | Fast |
| TestEffortWire::test_reasoning_for_model_openai_o3 | 0.01 | Fast |
| TestEffortWire::test_reasoning_for_model_gpt4o_none | 0.01 | Fast |
| TestEffortWire::test_reasoning_for_model_owl_gets_effort | 0.01 | Fast |

### test_providers.py (16 tests) — MIXED

| Test | Time (s) | Category |
|------|----------|----------|
| TestOpenRouterProvider::test_chat | 0.01 | Fast |
| TestOpenRouterProvider::test_chat_without_system_prompt | 0.01 | Fast |
| TestOpenRouterProvider::test_unavailable | 0.01 | Fast |
| TestOpenRouterProviderRealAPI::test_real_chat | 4.20 | Slow |
| TestOpenRouterProviderRealAPI::test_real_chat_with_system_prompt | 3.03 | Slow |

### test_providers_extended.py (17 tests) — FAST

| Test | Time (s) | Category |
|------|----------|----------|
| All 17 tests | <0.10 each | Fast |

### test_tool.py (40 tests) — MOSTLY SLOW

| Test | Time (s) | Category |
|------|----------|----------|
| TestTestTool::test_send_message | 0.01 | Fast |
| TestTestTool::test_regular_message_ignored | 0.01 | Fast |
| TestTestTool::test_async_ai_call | 3.32 | Slow |
| TestTestTool::test_send_as_different_nick | 2.16 | Slow |
| TestTestTool::test_unknown_command_routes_to_ai | 1.97 | Slow |
| TestTestTool::test_help_command | 0.02 | Fast |
| TestInteractiveMode::test_interactive_launches_and_exits | 1.21 | Medium |
| TestInteractiveMode::test_interactive_accepts_input | 1.21 | Medium |
| TestInteractiveMode::test_interactive_tab_completes_trigger | 13.02 | Slow |
| TestInteractiveMode::test_interactive_tab_completes_midline | 13.02 | Slow |
| TestInteractiveMode::test_interactive_accepts_pm | 5.14 | Slow |
| TestInteractiveMode::test_interactive_noisy_notice | 63.89 | Very Slow |
| TestInteractiveMode::test_interactive_empty_input | 1.25 | Medium |
| TestInteractiveMode::test_interactive_ctrl_d_exits | 13.46 | Slow |
| TestInteractiveMode::test_interactive_history_navigation | 13.03 | Slow |
| TestPM::test_pm_trigger_routes_to_ai | 2.27 | Slow |
| TestPM::test_pm_management_command | 0.15 | Fast |
| TestPM::test_pm_help_command | 0.15 | Fast |
| TestPM::test_pm_unknown_command_routes_to_ai | 1.57 | Slow |
| TestPM::test_ai_command_context_free | 1.75 | Slow |
| TestPM::test_pm_direct_message | 1.72 | Slow |
| TestPM::test_pm_setlocation_forwards_to_ai | 2.35 | Slow |
| TestPM::test_clear_command | 1.66 | Slow |
| TestPM::test_compact_admin_only_for_non_admin | 0.17 | Fast |
| TestNoisy::test_noisy_toggle | 0.01 | Fast |
| TestNoisy::test_noisy_off_no_notice | 0.02 | Fast |
| TestNoisy::test_noisy_on_sends_notice | 3.69 | Slow |
| TestRealAPI::test_real_effort_level | 0.23 | Medium |
| TestRealAPI::test_real_unknown_command_goes_to_ai | 3.40 | Slow |
| TestRealAPI::test_real_noisy_toggle | 0.23 | Medium |
| TestRealAPI::test_real_setlocation_goes_to_ai | 2.18 | Slow |
| TestRealAPI::test_real_pm_trigger_responds | 4.56 | Slow |
| TestRealAPI::test_real_pm_effort_level | 0.23 | Medium |
| TestRealAPI::test_real_noisy_sends_notice_on_ai_message | 23.19 | Very Slow |

## Categories

- **Fast**: < 0.1s (mocked, pure logic)
- **Medium**: 0.1s - 1s (real DB fixture, tempfiles)
- **Slow**: 1s - 10s (subprocess, pty, real AI API calls)
- **Very Slow**: > 10s (interactive polling, real AI API calls)

## Bottleneck Analysis

### Tier 1: Interactive Mode Tests (8 tests, ~130s total)

**Root cause:** Each test spawns a new `pty.openpty()` + `subprocess.Popen` pair. The polling loops use `time.sleep(0.5)` in a `while time.time() < deadline` loop with timeouts of 10-30s.

| Test | Time | Issue |
|------|------|-------|
| test_interactive_noisy_notice | 63.89s | expect_timeout=30, AI didn't respond in time |
| test_interactive_ctrl_d_exits | 13.46s | timeout=10, process exit detection |
| test_interactive_history_navigation | 13.03s | timeout=10, 3 inputs to process |
| test_interactive_tab_completes_trigger | 13.02s | timeout=10, 2 inputs |
| test_interactive_tab_completes_midline | 13.02s | timeout=10, 2 inputs |
| test_interactive_accepts_pm | 5.14s | expect_timeout=30 but AI responded faster |
| test_interactive_empty_input | 1.25s | timeout=10, 2 inputs |
| test_interactive_accepts_input | 1.21s | timeout=10, 2 inputs |
| test_interactive_launches_and_exits | 1.21s | timeout=10, 1 input |

**Fix ideas:**
- Reduce `_run_interactive` timeout from 10s → 3s
- Reduce `_run_interactive_poll` expect_timeout from 30s → 5s
- Eliminate `post_wait=2` (replace with drain-only)
- Share subprocess across tests via session-scoped fixture

### Tier 2: Real AI API Tests (12 tests, ~50s total)

**Root cause:** Tests hit real OpenRouter API. Response time varies (1-20s).

| Test | Time | Issue |
|------|------|-------|
| test_real_noisy_sends_notice_on_ai_message | 23.19s | Real AI call |
| test_real_pm_trigger_responds | 4.56s | Real AI call |
| test_real_unknown_command_goes_to_ai | 3.40s | Real AI call |
| test_noisy_on_sends_notice | 3.69s | Real AI call |
| test_async_ai_call | 3.32s | Real AI call |
| test_pm_trigger_routes_to_ai | 2.27s | Real AI call |
| test_pm_setlocation_forwards_to_ai | 2.35s | Real AI call |
| test_real_setlocation_goes_to_ai | 2.18s | Real AI call |
| test_pm_unknown_command_routes_to_ai | 1.57s | Real AI call |
| test_ai_command_context_free | 1.75s | Real AI call |
| test_pm_direct_message | 1.72s | Real AI call |
| test_clear_command | 1.66s | Real AI call |

**Fix ideas:**
- Mock provider for tests that only test routing (not AI quality)
- Use `.effort low` to reduce AI reasoning time
- Add `pytest.mark.real` marker to skip in normal runs

### Tier 3: Tab Completion Tests (2 tests, ~26s total)

**Root cause:** These send keystrokes to a curses input loop which does tab completion via subprocess. The 0.5s delay per input + 10s timeout adds up.

**Fix ideas:**
- Reduce timeout to 3s
- Test tab completion logic directly (unit test) instead of via pty

## Failures

| Test | Status | Notes |
|------|--------|-------|
| test_interactive_accepts_pm | FAIL (deferred) | Subprocess mock issue — works live per deferred docs |
| test_interactive_noisy_notice | FAIL (deferred) | Subprocess mock issue — works live per deferred docs |
| test_pm_setlocation_forwards_to_ai | FLAKY | Passes alone, fails in suite — test ordering / state issue |
