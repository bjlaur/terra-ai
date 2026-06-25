# CHANGELOG.md

## 0.0.2 — TBD

Test tool, provider expansion, web search, ergo integration testing.

### Features
- Test tool (`test_tool/irc_client.py`) — irssi-like terminal UI via Textual
- Screenshot tests (`test_tool/screenshot_test.py`) — 3 SVGs, visual inspection
- Additional providers: Gemini, OpenAI, Ollama
- Provider fallback chain in registry
- Web search via DuckDuckGo (free, no API key)
- ergochat integration tests — smoke, IRC protocol, SOPEL bot end-to-end
- SOPEL test config examples committed (`config/sopel-test.cfg.example`, `config/terraai-test.yaml.example`)
- `python-textual` added to PACKAGES.md

### Testing
- 83 unit tests passing (database, providers, prompts, context, bot, providers_extended, test_tool)
- 3 ergo smoke tests (port open, config exists, socket connect)
- 4 ergo IRC protocol tests (register, join, channel message, private message)
- 2 ergo SOPEL bot tests passing (connects, joins channel)
- 2 ergo SOPEL bot tests failing (responds to .help, responds to TerraAI: trigger) — IRCv3 message dispatch blocked

---

## 0.0.1 — TBD

Initial release. Minimal SOPEL plugin with one provider and basic commands.

### Features
- Responds to `TerraAI:` trigger phrase and `.` shorthand
- OpenRouter provider (default)
- SQLite persistence: 7 tables (users, conversation_history, sessions, compactions, prompts, command_stats, performance_stats)
- Fake conversation injected as context seed
- Commands: `.optin`, `.optout`, `.ai`, `.addprompt`, `.rmprompt`, `.listprompts`, `.help`, `.effort`, `.compact`, `.stats`, `.setlocation`, `.noisy`
- pytest suite with real API calls (60 tests)

### Testing
- 60 unit tests passing (database, providers, prompts, context, bot)
