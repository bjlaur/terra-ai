# 0.0.1 Feature — Minimal SOPEL Plugin

## What We're Building

A minimal SOPEL plugin that turns an IRC bot into an AI assistant. One provider, basic commands, SQLite persistence. Ship fast, iterate.

## Scope

### In 0.0.1
- Responds to `TerraAI:` trigger phrase
- `.ai` command for context-free prompts
- OpenRouter provider only (default, no fallback)
- Fake conversation injected as context seed
- SQLite persistence: 7 tables (see below)
- Commands: `.optin`, `.optout`, `.ai`, `.addprompt`, `.rmprompt`, `.listprompts`, `.help`, `.effort`, `.compact`, `.stats`, `.setlocation`, `.noisy`
- pytest suite with mocked provider (60 tests)
- Test tool (irssi-like terminal UI via Textual)

### Architecture
- Plugin entry point: `terraai/plugin.py` (SOPEL @rule decorators)
- Core class: `terraai/bot.py` (holds DB, provider, context)
- Provider: `terraai/providers/openrouter.py`
- Database: `terraai/database.py` (7 tables, WAL mode, multi-server)
- Context: `terraai/context/manager.py` (context assembly, session_id, compaction)
- Prompts: `terraai/prompts/manager.py` (CRUD + matching)
- Commands: `terraai/commands/admin.py`, `terraai/commands/user.py`

### Tables
- `users` — server, nick, opted_in, noisy, timestamps
- `conversation_history` — server, channel, nick, role, content, source, session_id, timestamp
- `sessions` — server, channel, active_session_id
- `compactions` — compaction audit trail
- `prompts` — server, trigger, response, created_by, timestamp
- `command_stats` — usage logging
- `performance_stats` — token counts, latency, response sizes

## Test Results

60 unit tests passing. See `manual-testing-results.md` for manual test status.
