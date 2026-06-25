# CHANGELOG.md

## 0.0.2 — In Progress

### Agent 1 (OWL) — Provider expansion, web search, ergo integration

#### Features
- Test tool (`test_tool/chat.py`, formerly `irc_client.py`) — irssi-like terminal UI via Textual
- Screenshot tests (`test_tool/screenshot_test.py`) — 3 SVGs, visual inspection
- Additional providers: Gemini, OpenAI, Ollama
- Provider fallback chain in registry
- Web search via DuckDuckGo (free, no API key)
- ergochat integration tests — smoke, IRC protocol, SOPEL bot end-to-end
- SOPEL test config examples committed (`config/sopel-test.cfg.example`, `config/terraai-test.yaml.example`)
- `python-textual` added to PACKAGES.md

#### Testing
- 83 unit tests passing (database, providers, prompts, context, bot, providers_extended, test_tool)
- 3 ergo smoke tests (port open, config exists, socket connect)
- 4 ergo IRC protocol tests (register, join, channel message, private message)
- 2 ergo SOPEL bot tests passing (connects, joins channel)
- 2 ergo SOPEL bot tests failing (responds to .help, responds to TerraAI: trigger) — IRCv3 message dispatch blocked

### Agent 2 — Routing fixes, new commands, PM support, manual testing

#### Features
- `.clear` command — wipe conversation history and start fresh session
- `.setlocation` hybrid routing — stores prompt locally, forwards to AI for response
- `.effort [level]` — set reasoning effort (low/medium/high/xhigh/max)
- Unknown `.command` routing — anything starting with `.` that isn't a management command goes to AI
- Tab completion — `Ter<Tab>` completes to `TerraAI: ` (mid-line too)
- Custom prompt local matching removed — `.wea` and similar now route to AI
- PM support — `/msg` sends direct-to-bot, no trigger phrase needed
- Noisy mode — "Thinking..." notice shown in channel with `-!-` prefix
- Async AI calls — UI no longer freezes during API calls
- Timestamps `[HH:MM]` on all messages
- Compact gate — `.compact` restricted to admin only
- Resize fix — terminal resize handled correctly

#### Bug Fixes
- `.effort` no response — added "effort" to MANAGEMENT_COMMANDS set
- `.setlocation` (no args) — now correctly forwards to AI instead of erroring
- Tab completion — changed from "TerraAI" to "TerraAI: " (trigger phrase)
- `.wea` / unknown `.command` no response — added `.command` → AI routing
- Resize cuts off text — KEY_RESIZE handler recreates windows + redraws
- Test tool duplicated routing — rework plan drafted to use single `dispatch()`

#### Testing
- 100+ unit tests passing
- `--real` API tests passing (7/7): effort, unknown command, noisy, setlocation, PM trigger, PM effort, noisy notice
- Screenshot tests passing (8 SVGs): resize, wrap, PM, noisy
- 63 manual tests documented in `docs/release-0.0.2/testing-agent2-v2.md`
- Rework plan drafted in `docs/release-0.0.2/rework-plan.md`
- Deferred tests tracked in `docs/release-0.0.2/deferred-testing-agent2.md`

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
