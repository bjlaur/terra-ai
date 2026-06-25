# TODO.md

## terra-ai TODO list

This file is the active roadmap. Completed items move to the changelog.
Only pending/unfinished work stays in the active sections below.

---

## Every commit MUST update `TODO.md`, `CHANGELOG.md`, and `.agentic/plan.md`.

---

## Active: 0.0.1 — Minimal SOPEL Plugin

### Phase 1 — Scaffold
- [ ] `requirements.txt` — sopel, pyyaml, openai
- [ ] `config/terraai.yaml.example` — defaults with comments
- [ ] `Containerfile` — Arch Linux + chaotic-aur + yay + sopel + requirements
- [ ] `terraai/__init__.py` — `__version__ = "0.0.1"`
- [ ] `terraai/config.py` — dataclass + YAML load + validation
- [ ] `.gitignore` — data/, *.pyc, __pycache__/, config/terraai.yaml

### Phase 2 — Database Layer
- [ ] `terraai/database.py` — 3 tables (users, conversation_history, prompts), WAL mode
- [ ] `tests/test_database.py` — in-memory SQLite tests

### Phase 3 — Provider
- [ ] `terraai/providers/base.py` — AIProvider ABC
- [ ] `terraai/providers/openrouter.py` — OpenRouter implementation
- [ ] `tests/test_providers.py` — mock SDK calls

### Phase 4 — Prompts + Context
- [ ] `terraai/prompts/defaults.py` — fake conversation as context seed
- [ ] `terraai/prompts/manager.py` — CRUD + prompt matching
- [ ] `terraai/context/manager.py` — context assembly + history save
- [ ] Tests

### Phase 5 — Bot Wiring
- [ ] `terraai/bot.py` — SOPEL plugin, all decorators, command routing
- [ ] `terraai/commands/admin.py` — .listprompts, .rmprompt, .addprompt
- [ ] `terraai/commands/user.py` — .optin, .optout, .ai
- [ ] `tests/test_integration.py` — full happy-path mocks

### Phase 6 — Docs + Release
- [ ] `README.md`
- [ ] Update `CHANGELOG.md` with actual 0.0.1 content
- [ ] `docs/release-0.0.1/manual-testing-results.md` — fill in test results

---

## Pending (after 0.0.1)

See `docs/future-release/release-plan.md` for the full deferred features list.

High priority:
- Additional providers (Gemini, OpenAI, Ollama) + fallback chain
- Web search (provider-native + DuckDuckGo fallback)
- Test tool (Textual, irssi-like)
- ergo integration testing
- Context compaction (.compact)
- User experience commands (.noisy, .setlocation, .help)
- Performance stats (.stats)
- Multi-server support
- Rate limiting
- Containerfile polish
