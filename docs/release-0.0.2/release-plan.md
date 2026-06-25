# Release Plan — 0.0.2

## Status

**Branch**: `master`
**Status**: Not started. 0.0.1 complete.

---

## What's in 0.0.2

See `feature.md` for full description.

### Core
1. Test tool — irssi-like terminal UI via Textual
2. Test tool tests — screenshots + visual inspection
3. Additional providers — Gemini, OpenAI, Ollama
4. Provider fallback chain
5. Web search — provider-native + DuckDuckGo fallback
6. ergo integration testing
7. Missing 0.0.1 commands (.noisy, .setlocation, .help, .effort, .compact, .stats)

### Out of Scope (deferred)
- Multi-server support
- Rate limiting
- Containerfile polish

---

## Release Checklist

### Every Few Commits
- [ ] `.agentic/TODO.md` updated
- [ ] `CHANGELOG.md` updated
- [ ] `docs/release-0.0.2/` updated

### Pre-Release
- [ ] All phases complete
- [ ] Test tool works interactively
- [ ] All providers tested
- [ ] Web search working
- [ ] ergo integration tests pass
- [ ] `docs/release-0.0.2/manual-testing-results.md` completed
- [ ] README.md updated with new commands
