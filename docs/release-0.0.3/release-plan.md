# Release Plan — 0.0.3

## Goal

Harden the bot for real-world usage. Prevent unbounded data growth, handle provider failures gracefully, and add confidence via automated end-to-end tests.

## Features

### 1. Conversation TTL
**Effort**: Small
**Files**: `terraai/database.py`, `terraai/config.py`, `config/terraai.yaml.example`

- Add `conversation_ttl_days` config field (default `0` = disabled)
- On every write to `conversation_history`, prune rows older than `ttl_days` for that channel
- Also run a startup cleanup on bot boot
- Migration: no schema change (just a config value + delete query)

### 2. Opt-in Default Config Flag
**Effort**: Tiny
**Files**: `terraai/config.py`, `terraai/database.py`, `config/terraai.yaml.example`

- Add `default_optin` config field (default `1` = opted in, matching current behavior)
- When a nick is seen for the first time, use `default_optin` instead of hardcoded `1`
- Lets deployments choose opt-out-by-default for privacy

### 3. Better Provider Error Handling
**Effort**: Medium
**Files**: `terraai/providers/base.py`, `terraai/providers/registry.py`, `terraai/bot.py`

- Retry transient errors (5xx, timeouts, rate limits) with exponential backoff — max 3 retries
- Distinguish transient from permanent errors (4xx auth failures should not retry)
- On permanent failure: tell user which provider failed and why (without leaking API keys)
- On all providers failing: emit existing "AI backend unavailable" message
- Log retry attempts at DEBUG level

### 4. Automated Dogfooding
**Effort**: Medium
**Files**: `tests/test_dogfood.py`

- E2E tests that drive the bot through the same code path as real IRC
- Use the in-process fake bot (Mode 1 from plan §11)
- Test sequences:
  - Opt-in → send trigger → get AI response → opt-out → send trigger → no response
  - `.addprompt` → trigger custom prompt → verify no AI call
  - `.setlocation` → verify stored prompt
  - `.noisy` toggle → verify status notices
  - Multi-message conversation → verify context accumulates
  - `.ai` command → verify no history included
- Assert on response content, DB state, and API call counts (via mocks)

## Out of Scope (deferred)

- Model-per-channel routing
- Web dashboard
- Containerfile polish (deployment via Coolify, TBD)
- Conversation export (implement when needed)

## Done (moved to 0.0.1)

- SOPEL plugin entry point
- OpenRouter provider
- SQLite persistence (7 tables)
- Fake conversation injection
- Commands: .optin, .optout, .ai, .addprompt, .rmprompt, .listprompts
- pytest suite (60 tests)

## Done (moved to 0.0.2)

- Additional providers: Gemini, OpenAI, Ollama + fallback chain
- Web search via DuckDuckGo
- Test tool (Textual IRC client) + screenshot tests
- ergo integration tests (smoke, IRC protocol, SOPEL bot connect/join)
- SOPEL + TerraAI test config examples committed
- Missing 0.0.1 commands: .noisy, .setlocation, .help, .effort, .compact, .stats
- 83 unit tests + 9 ergo integration tests passing

## Done (carried from 0.0.2, unblocked by other agent)

- SOPEL bot message dispatch fix (IRCv3)
- SSL/TLS for ergo
- Context compaction (.compact command)
