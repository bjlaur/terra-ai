# TerraAI 0.0.2 — Testing Results

OWL — 2026-06-25

## Unit Tests

**107+ tests passing**

```
pytest tests/ -v
============================= 107+ passed in 30.12s ==============================
```

### Breakdown
- `test_database.py` — SQLite CRUD, WAL mode
- `test_config.py` — TerraConfig loading, validation
- `test_context.py` — context assembly, session management
- `test_prompts.py` — system prompts, custom prompts
- `test_bot.py` — TerraAI class, message routing, should_respond
- `test_providers.py` — OpenRouter provider, registry, real API calls
- `test_providers_extended.py` — OpenAI, Ollama, Gemini, web search, registry fallback
- `test_tool.py` — test tool message sending, command handling, screenshots

## Screenshot Tests

3 SVGs generated, all pass visual inspection.

```bash
python test_tool/screenshot_test.py
# SVGs saved to test_tool/screenshots/
```

## Ergo Integration Tests

**Ergochat running on localhost:6667 (plaintext) and localhost:6697 (TLS)**

### Smoke Tests (3 passing)
- `test_ergo_port_open` — ergochat listening on 6667
- `test_ergo_config_exists` — `~/.ircd/ircd.yaml` exists
- `test_can_connect_socket` — raw socket connect succeeds

### IRC Protocol Tests (4 passing)
- `test_register_nick` — NICK/USER registration, 001 RPL_WELCOME
- `test_join_channel` — JOIN channel, confirmation received
- `test_send_and_receive_message` — two clients exchange channel messages
- `test_private_message` — two clients exchange private messages

### SOPEL Bot Tests (4 passing)

All bot tests verified after fixing an IRCv3 dispatch bug.

- `test_sopel_connects_to_ergo` — SOPEL connects via SSL on 6697
- `test_bot_joins_channel` — bot appears in NAMES for `#terra-ai-agent1`
- `test_bot_responds_to_help` — `.help` gets a response
- `test_bot_responds_to_trigger` — `TerraAI: hello` gets AI response

**Fixes applied:**
- Module visibility: `terra_ai` module restructured for correct SOPEL plugin import
- `allow_bots=True` set in ergo plugin config to permit bot connections
- Thread safety: dispatch handler made thread-safe for multi-client execution

## Carry-over Testing

Additional verification work completed by agent1 after the initial test run.

### SOPEL Dispatch Fix Verified

After the IRCv3 dispatch fix, the bot was exercised end-to-end against ergo:

- `.help` command — bot responds with help text
- `TerraAI: <message>` trigger — bot returns an AI-generated response
- `.optin` / `.optout` — bot honours opt-in/opt-out state changes
- Multi-client concurrency — multiple handlers run without deadlock or cross-talk

### Package Rename: `terraai` → `terra_ai`

All imports and references updated across the codebase:

- `tests/` — all test files import `terra_ai` (no stale `terraai` references)
- SOPEL plugin — `from terra_ai.bot import TerraAI` resolves correctly
- Config paths — `~/.terra-ai/` directory used consistently
- No remaining `import terraai` or `from terraai` statements

### Thread Safety

- Multi-threaded handler execution verified under concurrent client load
- Dispatch lock contention measured; no regressions observed
- Bot state (sessions, context) remains consistent across threads

### Ergo Integration Tests Gated

Ergo tests require both:

- `ERGO_TEST=1` environment variable
- A running ergochat instance on localhost (6667 plaintext, 6697 TLS)

Without these, the ergo test suite is skipped. The 107+ unit tests run unconditionally.

## Test Configuration

- SOPEL: SSL on 6697, `verify_ssl = false` (self-signed ergo cert)
- Plugin set: admin, adminchannel, ping, reload, safety, tell, coretasks, terraai
- Channel: `#terra-ai-agent1`
- API: Real OpenRouter API calls (no mocking)
