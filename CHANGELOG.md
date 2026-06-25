# CHANGELOG.md

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
