# Release Plan — 0.0.2

## Status

**Branch**: `release-0.0.2`
**Status**: Substantially complete. Ergo smoke/protocol/bot-connect tests passing. SOPEL bot message dispatch blocked on IRCv3 issue. Agent2 completed routing fixes, .clear command, and manual testing rounds 1–3.

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
- [x] Web search working
- [x] ergo smoke + IRC protocol tests pass (7/7)
- [ ] ergo SOPEL bot end-to-end tests pass (2/4 — message dispatch blocked on IRCv3)
- [x] `docs/release-0.0.2/testing-agent1.md` completed
- [x] README.md updated with new commands (.clear)
