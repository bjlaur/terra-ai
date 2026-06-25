# TerraAI — Development Guide

## KISS

**Keep It Simple, Stupid.** This is the project mantra. Every design decision should lean toward simplicity over cleverness. Don't build features we don't need yet. Don't overengineer. Don't add complexity for hypothetical future use. Solve the current problem, the simplest way possible.

## Project Rules

1. **No pip install into system Python.** Dependencies are managed via the Containerfile. If a new dependency is needed, add it to `requirements.txt` and tell the user.
2. **Commit messages:** ~8 words, imperative mood, no body.
3. **Every commit must update** `.agentic/plan.md`, `.agentic/TODO.md`, and `CHANGELOG.md` to reflect the current state.
4. **Always ask before committing/pushing.** No silent commits. No push to origin without explicit request.
5. **Sign your work** in docs with `OWL — <description>`.
6. **READ ALL PROMPTS before acting** — not just the latest one.
7. **NEVER use AskUserQuestion** — print questions as plain text.
8. **Wait for confirmation before moving/deleting files.**
9. **ALWAYS `pwd && git remote -v` before any git command.**
10. **Runtime files in `data/`**, configs committed only as `.example`.
11. **Test for everything.** Don't ask the user to manually verify something that hasn't already passed its own test. Write a test first, then implement. Only skip tests with a very good reason.
12. **All tests that hit AI MUST use real APIs.** No mocking of AI provider calls. If the test needs AI, it calls the real API. Set the required API key in `.env` (gitignored). If the API key is not set, the test fails (no skip).
13. **Write a report if you make a mistake.** If you make an avoidable mistake (didn't read docs, didn't follow instructions, used the wrong repo, etc.), write a report in `docs/misc/claude-didn't-listen.md` immediately. See that file for the format.
14. **NEVER hardcode the bot nick.** Always read it from SOPEL config (`bot.settings.core.nick`) or from the TerraAI config (`config.bot["bot_nick"]`). The string "TerraAI" must never appear in test IRC messages, assertions, or handler logic.
15. **NEVER hardcode the command prefix.** Always read it from SOPEL config (`bot.settings.core.prefix` / `help_prefix`). The characters `-` and `.` must never appear as hardcoded prefixes in test IRC messages, assertions, or handler logic. Use a variable that references the config value.

## Git Identity

- user.email: `owl@terra-ai`
- user.name: `OWL`
- agent name: `agent1`

## Verification

After code changes (Python files):
```bash
python -m py_compile terraai/<file>.py
```

Run full test suite:
```bash
pytest tests/
```

## Release Process

1. Create `docs/release-X.Y.Z/release-plan.md`
2. Create `docs/release-X.Y.Z/feature.md`
3. Create `docs/release-X.Y.Z/testing.md` — manual testing checklist (see jbrowse format: harness / manual / --real test columns)
4. Implement features
5. Run tests against real APIs (not just mocks)
6. Create `docs/release-X.Y.Z/testing-results.md` — results of all tests
7. When all tests pass → commit, tag, update CHANGELOG.md

## File Naming Conventions

- `testing.md` — manual testing checklist. Follow the jbrowse format: `/mnt/jbrowse/docs/release-X.Y.Z/ipc-fastfollower-testing.md` (legend, columns: Harness / Manual / --real test / Why no harness? / Dev notes / Agent notes, rounds per agent). **Dev notes column is for the human developer only — agents must leave it blank.**
- `testing-results.md` — actual results from running tests
- NOT `test-requests.md`, NOT `manual-testing-results.md`

## Architecture

- Plugin entry point: [terraai/bot.py](terraai/bot.py) — SOPEL decorators
- Core class: `TerraAI` — holds all logic (DB, providers, context, prompts)
- Providers: [terraai/providers/](terraai/providers/) — OpenRouter (default), Gemini, OpenAI, Ollama
- Database: [terraai/database.py](terraai/database.py) — 7 tables, WAL mode, multi-server support
- Context: [terraai/context/](terraai/context/) — history assembly, session_id, compactions
