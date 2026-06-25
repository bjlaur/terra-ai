# TerraAI — Development Guide

## KISS

**Keep It Simple, Stupid.** This is the project mantra. Every design decision should lean toward simplicity over cleverness. Don't build features we don't need yet. Don't overengineer. Don't add complexity for hypothetical future use. Solve the current problem, the simplest way possible.

## Project Rules

1. **No pip install into system Python.** Dependencies are managed via the Containerfile. If a new dependency is needed, add it to `requirements.txt` and tell the user.
2. **Commit messages:** ~8 words, imperative mood, no body.
3. **Every commit must update** `plan.md`, `.agentic/TODO.md`, and `CHANGELOG.md` to reflect the current state.
4. **Always ask before committing/pushing.** No silent commits. No push to origin without explicit request.
5. **Sign your work** in docs with `OWL — <description>`.
6. **READ ALL PROMPTS before acting** — not just the latest one.
7. **NEVER use AskUserQuestion** — print questions as plain text.
8. **Wait for confirmation before moving/deleting files.**
9. **ALWAYS `pwd && git remote -v` before any git command.**
10. **Runtime files in `data/`**, configs committed only as `.example`.

## Git Identity

Not yet configured. Set before committing:
```
git config user.email "you@example.com"
git config user.name "Your Name"
```

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
2. Implement features
3. Create `docs/release-X.Y.Z/manual-testing-results.md`
4. Follow retest checklist format (see plan.md §13.2)
5. When all tests pass → commit, tag, update CHANGELOG.md

## Architecture

- Plugin entry point: [terraai/bot.py](terraai/bot.py) — SOPEL decorators
- Core class: `TerraAI` — holds all logic (DB, providers, context, prompts)
- Providers: [terraai/providers/](terraai/providers/) — OpenRouter (default), Gemini, OpenAI, Ollama
- Database: [terraai/database.py](terraai/database.py) — 7 tables, WAL mode, multi-server support
- Context: [terraai/context/](terraai/context/) — history assembly, session_id, compactions
