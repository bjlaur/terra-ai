# 0.0.2 Feature — Test Tool + Provider Expansion

## What We're Building

 builds on 0.0.1 by adding the interactive test tool, additional AI providers with fallback, web search, and integration testing.

## Scope

### In 0.0.2
- **Test tool** — irssi-like terminal UI using Textual for interactive testing
- **Test tool tests** — automated tests with screenshots + visual inspection
- **Additional providers** — Gemini, OpenAI, Ollama alongside OpenRouter
- **Provider fallback chain** — try next provider if primary fails
- **Web search** — provider-native (Gemini grounding, OpenRouter plugins) + DuckDuckGo fallback
- **ergo integration testing** — real IRC server for end-to-end tests
- **Missing 0.0.1 commands** — `.noisy`, `.setlocation`, `.help`, `.effort`, `.compact`, `.stats`

### Architecture additions
- Test tool: `test_tool/irc_client.py`
- New providers: `terraai/providers/gemini.py`, `openai.py`, `ollama.py`
- Web search: `terraai/tools/web_search.py`
- Integration tests: `tests/test_ergo.py`

### Deferred to later
- Multi-server support (add `server` column to all queries)
- Rate limiting
- Containerfile polish (based on user's run script pattern)
