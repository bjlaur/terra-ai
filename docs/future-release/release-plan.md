# Next Release Plan — Post-0.0.2

## Context

0.0.1 was a minimal viable SOPEL plugin with one provider and basic commands. 0.0.2 added test tool, additional providers, web search, and ergo integration testing. This plan covers features deferred from 0.0.2 and new capabilities for subsequent releases.

---

## Release Candidates (Prioritized)

### 1. Context Compaction
**Priority**: MEDIUM
**Effort**: Medium

`.compact` command with AI-driven pruning, session_id rotation, revert support. Already partially implemented in 0.0.2 (sessions/compactions tables exist).

**Files**: `terraai/database.py`, `terraai/commands/admin.py`

---

### 2. Multi-Server Support
**Priority**: LOW
**Effort**: Small

Add `server` column to all tables. Scope all queries by server. Schema already includes `server` columns — queries need updating.

**Files**: `terraai/database.py`, all managers

---

### 3. Rate Limiting
**Priority**: LOW
**Effort**: Small

Configurable per-nick sliding window. Default off. Already in config schema (`rate_limit_enabled`, etc.) — needs enforcement in `bot.py`.

**Files**: `terraai/bot.py`

---

### 4. Containerfile Polish
**Priority**: LOW
**Effort**: Small

Multi-stage if size matters. `VOLUME ["/app/data"]`. Healthcheck.

**Files**: `Containerfile`

---

### 5. SOPEL Bot Message Dispatch Fix
**Priority**: HIGH
**Effort**: Medium

Bot connects + joins but doesn't dispatch PRIVMSG to plugins. Likely IRCv3 `echo-message`/`server-time` CAP issue. Blocks end-to-end bot testing.

**Files**: `config/sopel-test.cfg.example`, investigation

---

### 6. SSL/TLS for ergo
**Priority**: MEDIUM
**Effort**: Small

Plaintext 6667 works. SSL 6697 hangs on CAP negotiation with self-signed cert. Need proper cert or CAP workaround.

**Files**: ergo config, SOPEL config

---

## Recommended Execution Order

1. Fix SOPEL bot message dispatch (unblocks e2e tests)
2. SSL/TLS for ergo
3. Context compaction (finish remaining work)
4. Multi-server support
5. Rate limiting
6. Containerfile polish

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
