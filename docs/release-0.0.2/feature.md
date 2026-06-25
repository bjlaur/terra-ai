# 0.0.2 Feature — Test Tool + Provider Expansion + Ergo Integration

OWL — Updated 2026-06-25

## What We're Building

0.0.2 builds on 0.0.1 by adding the interactive test tool, additional AI providers with fallback, web search, and integration testing with ergochat.

## Scope

### In 0.0.2
- **Test tool** — irssi-like terminal UI using Textual for interactive testing
- **Test tool tests** — automated tests with screenshots + visual inspection
- **Additional providers** — Gemini, OpenAI, Ollama alongside OpenRouter
- **Provider fallback chain** — try next provider if primary fails
- **Web search** — DuckDuckGo (free, no API key)
- **Ergo integration testing** — real IRC server for end-to-end tests
  - Smoke tests: port, config, socket
  - IRC protocol tests: register, join, channel messages, private messages
  - SOPEL bot tests: real SOPEL process with TerraAI plugin, SSL/TLS to ergo
- **SOPEL + TerraAI test configs** — committed .example files for deployment
  - `config/sopel-test.cfg.example` — minimal plugin set (admin, adminchannel, ping, reload, safety, tell, coretasks, terraai)
  - `config/terraai-test.yaml.example` — test TerraAI config (separate DB path)
  - `.agentic/ircd.yaml.example` — ergo IRC server config example
- **Missing 0.0.1 commands** — `.noisy`, `.setlocation`, `.help`, `.effort`, `.compact`, `.stats`

### Architecture additions
- Test tool: `test_tool/irc_client.py`
- New providers: `terraai/providers/gemini.py`, `openai.py`, `ollama.py`
- Web search: `terraai/tools/web_search.py`
- Integration tests: `tests/test_ergo.py`
- Config examples: `config/sopel-test.cfg.example`, `config/terraai-test.yaml.example`

### SOPEL Plugin Selection
Only admin-essential plugins loaded (no games/bloat):
- `admin` — bot admin commands (join, part, quit)
- `adminchannel` — channel management (op, kick, mode)
- `ping` — CTCP ping response
- `reload` — hot-reload plugins
- `safety` — URL safety
- `tell` — message relay
- `coretasks` — SOPEL core (required)
- `terraai` — our plugin

No SOPEL built-in `help` — TerraAI has its own `.help`.

### Deferred to later
- Multi-server support (add `server` column to all queries)
- Rate limiting
- Containerfile polish (based on user's run script pattern)
