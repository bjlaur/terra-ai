# Release Plan — 0.0.1

## Status

**Branch**: `master`
**Status**: Not started. Plan approved, ready to implement.

---

## What's in 0.0.1

Minimal viable SOPEL plugin. One provider, basic commands, SQLite persistence.

See `feature.md` for full description.

### Core
1. SOPEL plugin entry point — trigger phrase, `.ai` command
2. OpenRouter provider only (default, no fallback chain)
3. SQLite: 3 tables (users, conversation_history, prompts)
4. Fake conversation injection as context seed
5. Commands: `.optin`, `.optout`, `.ai`, `.addprompt`, `.rmprompt`, `.listprompts`
6. pytest suite

### Out of Scope (deferred)
- Web search
- Test tool (Textual)
- ergo integration tests
- `.compact`, `.stats`, `.noisy`, `.setlocation`, `.help`
- Provider fallback chain
- sessions/compactions/performance_stats tables
- Multi-server support

---

## Release Checklist

### Every Few Commits
- [ ] `.agentic/plan.md` updated
- [ ] `.agentic/TODO.md` updated
- [ ] `CHANGELOG.md` updated
- [ ] `python -m py_compile terraai/<file>.py` passes
- [ ] `pytest tests/` passes

### Pre-Release
- [ ] All phases complete
- [ ] Containerfile builds
- [ ] `docs/release-0.0.1/manual-testing-results.md` completed
- [ ] README.md written
