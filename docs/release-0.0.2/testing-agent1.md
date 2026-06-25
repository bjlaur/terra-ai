# TerraAI 0.0.2 — Testing Results

OWL — 2026-06-25

## Unit Tests

**83 tests passing**

```
pytest tests/ -v
============================= 83 passed in 25.97s ==============================
```

### Breakdown
- `test_database.py` — SQLite CRUD, WAL mode
- `test_config.py` — TerraConfig loading, validation
- `test_context.py` — context assembly, session management
- `test_prompts.py` — system prompts, custom prompts
- `test_bot.py` — TerraAI class, message routing, should_respond
- `test_providers.py` — OpenRouter provider, registry, real API calls
- `test_providers_extended.py` — OpenAI, Ollama, Gemini, web search, registry fallback
- `test_tool.py` — test tool message sending, command handling

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

### SOPEL Bot Tests (pending verification)
- `test_sopel_connects_to_ergo` — SOPEL connects via SSL on 6697
- `test_bot_joins_channel` — bot appears in NAMES for `#terra-ai-agent1`
- `test_bot_responds_to_help` — `.help` gets a response
- `test_bot_responds_to_trigger` — `TerraAI: hello` gets AI response

## Test Configuration

- SOPEL: SSL on 6697, `verify_ssl = false` (self-signed ergo cert)
- Plugin set: admin, adminchannel, ping, reload, safety, tell, coretasks, terraai
- Channel: `#terra-ai-agent1`
- API: Real OpenRouter API calls (no mocking)
