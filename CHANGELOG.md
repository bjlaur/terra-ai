# CHANGELOG.md

## 0.0.1 — TBD

Initial release. SOPEL plugin that turns an IRC bot into a provider-agnostic AI assistant.

### Features
- Responds to `TerraAI:` trigger and `.` / `-` shorthand
- Provider-agnostic: OpenRouter (default), Gemini, OpenAI, Ollama
- SQLite persistence: conversation history, custom prompts, user preferences, command stats
- Custom prompts via `.addprompt`, `.rmprompt`, `.listprompts`
- User opt-in/opt-out (`.optin`, `.optout`)
- Noisy mode (`.noisy`) for status notices
- `.ai` command for context-free prompts
- `.setlocation` for AI-managed location memory
- `.compact` for AI-driven context compaction with session_id rotation
- Web search: provider-native (Gemini, OpenRouter) + fallback (DuckDuckGo)
- Admin vs user prompt scope based on sender nick

### Testing
- pytest suite with mocked providers
- In-process test tool (irssi-like terminal UI)
- ergo IRC server integration tests

### Known gaps
- No context trimming (full history sent to AI)
- No token counting
- No rate limiting enabled by default
- No web dashboard
