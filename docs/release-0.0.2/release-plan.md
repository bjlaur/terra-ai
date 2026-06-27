# Release Plan — 0.0.2

## Status

**Branch**: `release-0.0.2`
**Status**: Complete. All planned features implemented. 137 tests passing (mock + real + ergo). Ready to publish.

---

## What's in 0.0.2

See `feature.md` for full description.

### Core
1. Test tool — irssi-like terminal UI via Textual
2. Test tool tests — screenshots + visual inspection
3. Additional providers — Gemini, OpenAI, Ollama
4. Provider fallback chain
5. Web search — DuckDuckGo fallback
6. ergo integration testing — smoke (3), IRC protocol (4), SOPEL bot (2 passing, 2 blocked)
7. Missing 0.0.1 commands (.noisy, .setlocation, .help, .effort, .compact, .stats, .clear)
8. SOPEL + TerraAI test config examples committed
9. Routing fixes (.setlocation hybrid, unknown .command fallback, .effort in MANAGEMENT_COMMANDS, tab completion)

### Out of Scope (deferred)
- Multi-server support
- Rate limiting
- Containerfile polish

---

## Release Checklist

### Every Few Commits
- [x] `.agentic/TODO.md` updated
- [x] `CHANGELOG.md` updated
- [x] `docs/release-0.0.2/` updated

### Pre-Release
- [x] Test tool works interactively
- [x] All providers tested
- [x] Web search working (OpenRouter server-side)
- [x] ergo smoke + IRC protocol tests pass (7/7)
- [x] ergo SOPEL bot end-to-end tests pass (16/16)
- [x] All 137 tests passing (mock + real + ergo)
- [x] PM routing (bare PMs → AI)
- [x] Timeout type fix (int cast for all providers)
- [x] Server-side web search via OpenRouter
- [x] 3 interactive tests still deferred (subprocess+curses+pty harness limitation)
- [ ] Custom prompts rework (needs discussion — not blocking release)
