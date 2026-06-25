# Agent1 (OWL) — Handoff

## Current State

Working on `agent1/release-0.0.2` branch (pushed to origin).
All changes merged to `release-0.0.2` on origin.

## What's Done (0.0.1 + 0.0.2)

### 0.0.1 — Minimal SOPEL Plugin ✅
- SOPEL plugin with `TerraAI:` trigger and `.` shorthand
- OpenRouter provider (default model: `openrouter/owl-alpha`)
- SQLite persistence: 7 tables (users, conversation_history, sessions, compactions, prompts, command_stats, performance_stats)
- Commands: `.optin`, `.optout`, `.ai`, `.addprompt`, `.rmprompt`, `.listprompts`, `.help`, `.effort`, `.compact`, `.stats`, `.setlocation`, `.noisy`
- Fake conversation injected as context seed
- 60 unit tests passing

### 0.0.2 — Test Tool + Provider Expansion (in progress)
- Test tool (`test_tool/irc_client.py`) — irssi-like terminal UI via Textual
- Screenshot tests (`test_tool/screenshot_test.py`) — 3 SVGs, all pass visual inspection
- Additional providers: Gemini, OpenAI, Ollama
- Provider fallback chain in registry
- Web search via DuckDuckGo (free, no API key)
- `python-textual` added to PACKAGES.md
- 82 tests passing

## What's Left

1. **Fix ergo test** — `tests/test_ergo.py:65` references `ergo_running()` but function is named `ergo_available()`. One-line fix.
2. **Ergo integration testing** — ergochat installed and running on localhost:6667. Config at `~/.ircd/ircd.yaml`. DB at `~/.ircd/ircd.db`.
3. **0.0.2 docs** — Update CHANGELOG.md, testing-results.md, feature.md
4. **Commit and push** — Then start 0.0.3

## Key Files

- Plan: `.agentic/plan.md`
- TODO: `.agentic/TODO.md`
- Workspace: `~/agentic-repos/terra-ai-owl/`
- Origin: `/home/agent/git/terra-ai/`
- Shared DB: `~/.terra-ai/terraai.db`
- Shared ergo config: `~/.ircd/ircd.yaml`
- Shared ergo certs: `~/.ircd/fullchain.pem`, `~/.ircd/privkey.pem`
- API key: `~/.terra-ai/.env` (also `/home/agent/git/terra-ai/.env`)

## Running Tests

```bash
cd ~/agentic-repos/terra-ai-owl
source ~/.terra-ai/.env && export OPENROUTER_API_KEY
pytest tests/ -v
```

## Running Screenshots

```bash
cd ~/agentic-repos/terra-ai-owl
source ~/.terra-ai/.env && export OPENROUTER_API_KEY
python test_tool/screenshot_test.py
# SVGs saved to test_tool/screenshots/
# Visual inspection required
```

## Ergo Server

```bash
# Start
cd ~/.ircd && ergochat run --conf ./ircd.yaml --quiet &

# Stop
pkill -f ergochat

# Test connection
ERGO_TEST=1 pytest tests/test_ergo.py -v
```

## Critical Rules

1. All tests that hit AI MUST use real APIs (no mocking)
2. Screenshot tests use `export_screenshot()` + visual inspection
3. `os.environ.pop("NO_COLOR", None)` before running Textual apps
4. File naming: `test-requests.md` (what to test), `testing-results.md` (results)
5. Doc update rules in `.agentic/DEVELOPMENT.md`
6. `.agentic/plan.md` only updates when the plan itself changes (not per-commit)

## Git Identity

- user.email: owl@terra-ai
- user.name: OWL
- agent name: agent1

## Branches

- `release-0.0.1` — merged, tagged
- `release-0.0.2` — merged, tests passing, needs ergo + docs
- `agent1/release-0.0.2` — OWL's work branch (pushed to origin)
