# CHANGELOG.md

## 0.0.2 — In Progress

Test tool, provider expansion, routing fixes, new commands.

### Features
- Test tool — irssi-like terminal UI (`test_tool/chat.py`) for interactive testing
- Additional providers — Gemini, OpenAI, Ollama alongside OpenRouter
- Provider fallback chain — try next provider if primary fails
- Web search — provider-native + DuckDuckGo fallback
- `.clear` command — wipe conversation history and start fresh session
- `.setlocation` hybrid routing — stores prompt locally, forwards to AI for response
- `.effort [level]` — set reasoning effort (low/medium/high/xhigh/max)
- Unknown `.command` routing — anything starting with `.` that isn't a management command goes to AI
- Tab completion — `Ter<Tab>` completes to `TerraAI: ` (with trigger suffix)
- Custom prompt local matching removed — `.wea` and similar now route to AI

### Bug Fixes
- `.effort` no response — added "effort" to MANAGEMENT_COMMANDS set
- `.setlocation` (no args) — now correctly forwards to AI instead of erroring
- Tab completion — changed from "TerraAI" to "TerraAI: " (trigger phrase)

### Testing
- 80+ unit tests passing
- `--real` API tests passing (4/4): effort level, unknown command routing, noisy toggle, setlocation
- Interactive tests passing (launch, input, tab completion)
- Manual testing rounds 1–3 documented in `docs/release-0.0.2/testing-agent2.md`
- Deferred tests tracked in `docs/release-0.0.2/deferred-testing-agent2.md`

---

## 0.0.1 — TBD

Initial release. Minimal SOPEL plugin with one provider and basic commands.

### Features
- Responds to `TerraAI:` trigger phrase
- OpenRouter provider (default)
- SQLite persistence: users, conversation_history, prompts
- Fake conversation injected as context seed
- Commands: `.optin`, `.optout`, `.ai`, `.addprompt`, `.rmprompt`, `.listprompts`
- pytest suite with mocked provider (60 tests)

### Testing
- 60 unit tests passing (database, providers, prompts, context, bot)
