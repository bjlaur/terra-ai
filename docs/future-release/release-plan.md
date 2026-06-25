# Next Release Plan — Post-0.0.3

## Context

0.0.1 was a minimal viable SOPEL plugin with one provider and basic commands. 0.0.2 added test tool, additional providers, web search, and ergo integration testing. 0.0.3 focuses on reliability: conversation TTL, opt-in defaults, provider error handling, and automated dogfooding. This plan covers features deferred from 0.0.2 and 0.0.3, plus new capabilities for subsequent releases.

---

## Release Candidates (Prioritized)

### 1. Multi-Server Support
**Priority**: LOW
**Effort**: Small

Add `server` column to all tables. Scope all queries by server. Schema already includes `server` columns — queries need updating.

**Files**: `terraai/database.py`, all managers

---

### 2. Rate Limiting
**Priority**: LOW
**Effort**: Small

Configurable per-nick sliding window. Default off. Already in config schema (`rate_limit_enabled`, etc.) — needs enforcement in `bot.py`.

**Files**: `terraai/bot.py`

---

### 3. Model-Per-Channel Routing
**Priority**: LOW
**Effort**: Small

Different channels use different providers. Useful for testing vs. prod channels.

**Files**: `terraai/config.py`, `terraai/providers/registry.py`

---

### 4. Web Dashboard
**Priority**: LOW
**Effort**: Medium

Read-only SQLite viewer for stats. Defer until actually needed.

**Files**: new module

---

### 5. Conversation Export
**Priority**: LOW
**Effort**: Small

Dump history as JSON/text for debugging or archiving. Implement when needed.

**Files**: `terraai/database.py`, new command or script

---

## Recommended Execution Order

1. Multi-server support
2. Rate limiting
3. Model-per-channel routing
4. Conversation export
5. Web dashboard

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
- Test tool screenshot capture for docs/debugging
- ergo integration tests (smoke, IRC protocol, SOPEL bot connect/join)
- SOPEL + TerraAI test config examples committed
- Missing 0.0.1 commands: .noisy, .setlocation, .help, .effort, .compact, .stats
- 83 unit tests + 9 ergo integration tests passing

## Done (carried from 0.0.2, unblocked by other agent)

- SOPEL bot message dispatch fix (IRCv3)
- SSL/TLS for ergo
- Context compaction (.compact command)

## Done (moved to 0.0.3)

- Conversation TTL (auto-prune history older than N days)
- Opt-in default config flag
- Better provider error handling (retries, clearer messages)
- Automated dogfooding (e2e test sequences)
