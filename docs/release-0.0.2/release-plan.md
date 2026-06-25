# Release Plan — 0.0.2

## Status

**Branch**: `release-0.0.2`
**Status**: In progress. Core features implemented, testing underway.

---

## What's in 0.0.2

See `feature.md` for full description.

### Core
1. Test tool — irssi-like terminal UI via Textual ✅
2. Test tool tests — screenshots + visual inspection ✅
3. Additional providers — Gemini, OpenAI, Ollama ✅
4. Provider fallback chain ✅
5. Web search — provider-native + DuckDuckGo fallback ✅
6. ergo integration testing ✅
7. Missing 0.0.1 commands (.noisy, .setlocation, .help, .effort, .compact, .stats, .clear) ✅

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
- [ ] All phases complete
- [ ] Test tool works interactively (in progress — see testing-agent2.md)
- [ ] All providers tested (--real tests need run)
- [ ] Web search working
- [ ] ergo integration tests pass
- [ ] README.md updated with new commands (done: .clear added)
