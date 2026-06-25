# TODO.md

## terra-ai TODO list

This file is the active roadmap. Completed items move to the changelog.
Only pending/unfinished work stays in the active sections below.

---

## Every commit MUST update `TODO.md`, `CHANGELOG.md`, and `plan.md`.

---

## Active: 0.0.1 — Initial SOPEL Plugin

### Phase 1 — Scaffold
- [ ] `requirements.txt` — sopel, pyyaml, openai, aiohttp
- [ ] `config/terraai.yaml.example` — defaults with comments
- [ ] `config/terraai-test.yaml.example` — test SOPEL config (ergo server)
- [ ] `Containerfile` — Arch Linux + chaotic-aur + yay + sopel + requirements
- [ ] `terraai/__init__.py` — `__version__ = "0.0.1"`
- [ ] `terraai/config.py` — dataclass + YAML load + validation
- [ ] `.gitignore` — data/, *.pyc, __pycache__/, config/terraai.yaml

### Phase 2 — Database Layer
- [ ] `terraai/database.py` — schema (6 tables with server column, WAL mode, sessions table), UserStore, HistoryStore, PromptStore, CommandStats, PerformanceStats
- [ ] `tests/test_database.py` — in-memory SQLite tests

### Phase 3 — Providers
- [ ] `terraai/providers/base.py` — AIProvider ABC
- [ ] `terraai/providers/openrouter.py`
- [ ] `terraai/providers/openai.py`
- [ ] `terraai/providers/gemini.py`
- [ ] `terraai/providers/ollama.py`
- [ ] `terraai/providers/registry.py` — registry + fallback chain
- [ ] Tests with mocked SDK calls

### Phase 4 — Prompts
- [ ] `terraai/prompts/defaults.py` — the fake conversation as context seed
- [ ] `terraai/prompts/manager.py` — CRUD + prompt matching
- [ ] Tests for PromptManager

### Phase 5 — Context Manager
- [ ] `terraai/context/manager.py` — context assembly + session_id + history save
- [ ] Tests

### Phase 6 — Bot Wiring
- [ ] `terraai/bot.py` — SOPEL plugin, all decorators, command routing
- [ ] `terraai/commands/admin.py` — .listprompts, .rmprompt, .addprompt, .compact
- [ ] `terraai/commands/user.py` — .optin, .optout, .noisy, .setlocation, .ai
- [ ] `tests/test_integration.py` — full happy-path mocks

### Phase 7 — Test Tool + IRC Server
- [ ] `test_tool/irc_client.py` — irssi-like terminal UI
- [ ] Default channel `#terra-ai`
- [ ] Set up ergo IRC server for integration testing
- [ ] Scripted integration tests

### Phase 8 — Doc
- [ ] `README.md`
- [ ] `CHANGELOG.md` — initial 0.0.1 entry
- [ ] `docs/release-0.0.1/`

### Phase 9 — Containerfile Polish
- [ ] NOPASSWD yay build, then remove NOPASSWD
- [ ] VOLUME for /home/terra-ai/data
- [ ] Healthcheck

---

## Pending (after 0.0.1)

### Conversation management
- [ ] `.compact` — AI-driven compaction with session_id rotation

### Provider enhancements
- [ ] Web search provider-native (Gemini grounding, OpenRouter plugins)
- [ ] Web search fallback (DuckDuckGo + scrape)

### User experience
- [ ] `.setlocation` — dual-mode (AI + custom prompt)
- [ ] Conversation TTL — auto-prune history older than N days
- [ ] Model-per-channel routing

### Deployment
- [ ] Run script (based on cachyos-agent-gui pattern)
- [ ] Arch PKGBUILD

### Web dashboard
- [ ] Read-only SQLite viewer for stats
