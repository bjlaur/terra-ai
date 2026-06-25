# TODO.md

## terra-ai TODO list

This file is the active roadmap. Completed items move to the changelog.
Only pending/unfinished work stays in the active sections below.

---

## Every commit MUST update `TODO.md`, `CHANGELOG.md`, and `.agentic/plan.md`.

---

## Active: 0.0.1 — Minimal SOPEL Plugin

### Phase 1 — Scaffold ✅
- [x] `config/terraai.yaml.example` — defaults with comments
- [x] `Containerfile` — Arch Linux + chaotic-aur + yay + sopel
- [x] `terraai/__init__.py` — `__version__ = "0.0.1"`
- [x] `terraai/config.py` — dataclass + YAML load + validation
- [x] `.gitignore` — data/, *.pyc, __pycache__/, config/terraai.yaml

### Phase 2 — Database Layer ✅
- [x] `terraai/database.py` — 7 tables, WAL mode, all stores
- [x] `tests/test_database.py` — 22 tests passing

### Phase 3 — Provider ✅
- [x] `terraai/providers/base.py` — AIProvider ABC
- [x] `terraai/providers/openrouter.py` — OpenRouter implementation
- [x] `terraai/providers/registry.py` — Provider registry
- [x] `tests/test_providers.py` — 10 tests passing

### Phase 4 — Prompts + Context ✅
- [x] `terraai/prompts/defaults.py` — fake conversation as context seed
- [x] `terraai/prompts/manager.py` — CRUD + prompt matching
- [x] `terraai/context/manager.py` — context assembly + history save
- [x] `tests/test_commands.py` — 12 tests passing

### Phase 5 — Bot Wiring ✅
- [x] `terraai/bot.py` — core plugin logic
- [x] `terraai/plugin.py` — SOPEL @rule decorators
- [x] `terraai/commands/admin.py` — management commands
- [x] `terraai/commands/user.py` — user commands
- [x] `tests/test_integration.py` — 8 tests passing

### Phase 6 — Docs + Release
- [ ] `README.md`
- [ ] Update `CHANGELOG.md` with 0.0.1 content
- [ ] `docs/release-0.0.1/manual-testing-results.md` — fill in test results

---

## Pending (after 0.0.1)

See `docs/future-release/release-plan.md` for the full deferred features list.

High priority:
- Test tool (Textual, irssi-like) + screenshot tests
- Additional providers (Gemini, OpenAI, Ollama) + fallback chain
- Web search (provider-native + DuckDuckGo fallback)
- ergo integration testing
- Context compaction (.compact)
- User experience commands (.noisy, .setlocation, .help)
- Performance stats (.stats)
- Multi-server support
- Rate limiting
- Containerfile polish
