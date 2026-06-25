# 0.0.1 Feature — Minimal SOPEL Plugin

## What We're Building

A minimal SOPEL plugin that turns an IRC bot into an AI assistant. One provider, basic commands, SQLite persistence. Ship fast, iterate.

## Scope

### In 0.0.1
- Responds to `TerraAI:` trigger phrase
- `.ai` command for context-free prompts
- OpenRouter provider only (default)
- Fake conversation injected as context seed
- SQLite persistence: users, conversation_history, prompts
- Commands: `.optin`, `.optout`, `.ai`, `.addprompt`, `.rmprompt`, `.listprompts`
- pytest suite with mocked provider

### Architecture
- Plugin entry point: `terraai/bot.py`
- Core class: `TerraAI` (holds DB, provider, context)
- Provider: `terraai/providers/openrouter.py`
- Database: `terraai/database.py` (3 tables, WAL mode)
- Context: `terraai/context/manager.py` (fake conversation injection)
- Prompts: `terraai/prompts/manager.py` (CRUD + matching)

### Tables
- `users` — nick, opted_in, timestamps
- `conversation_history` — channel, nick, role, content, source, timestamp
- `prompts` — trigger, response, created_by, timestamp
