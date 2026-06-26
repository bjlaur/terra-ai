# TerraAI

A SOPEL plugin that turns an IRC bot into a provider-agnostic AI assistant.

## Features

- Responds to addressed queries (`TerraAI: <text>`) and `-` command shorthand
- Provider-agnostic with fallback chain: OpenRouter (default) → Gemini, OpenAI, Ollama
- Web search via DuckDuckGo instant answer API (no API key required)
- SQLite persistence for conversation history, prompts, and user preferences
- Custom prompts via `.addprompt`, `.rmprompt`, `.listprompts`
- Configurable bot nick via `{botnick}` variable in prompts (no hardcoded name)
- User opt-in/opt-out; admin opt-out of other nicks
- Context compaction with AI-driven pruning, history `.clear`
- Test tool (`test_tool/chat.py`) — irssi-style Textual terminal UI
- Screenshot regression tests (`test_tool/screenshot_test.py`) outputting SVGs
- Performance stats tracking

## Requirements

- Arch Linux (or any Linux with pacman)
- Python 3.12+
- SOPEL 8.0+

## Installation

Dependencies are managed via the Containerfile — do not install via pip or
system Python. See [Docker](#docker) to build and run the container.

In host or container, source your API key before running SOPEL:

```bash
source ~/.terra-ai/.env
```

`~/.terra-ai/.env` should set at least `OPENROUTER_API_KEY` (see
`env.example`). The Web search feature uses DuckDuckGo and needs no key. Then:

```bash
sopel -c config/terraai.yaml
```

## Docker

The plugin is not a standalone server; the Containerfile builds an Arch image
with SOPEL and all dependencies, then runs `sopel`.

```bash
docker build -t terra-ai .
docker run -v ./data:/home/terra-ai/data -v ./config:/home/terra-ai/config terra-ai
```

## Development

```bash
# Unit tests (fast; no external services)
pytest tests/ --ignore=tests/test_ergo.py

# Integration tests (requires ergochat running on localhost:6667)
ERGO_TEST=1 pytest tests/test_ergo.py -v

# Check compilation
python -m py_compile terra_ai/*.py terra_ai/**/*.py
```

## Commands

| Command | Description |
|---------|-------------|
| `<botnick>: <text>` | Talk to the bot directly (addressed query in channels) |
| `/msg <botnick> <text>` | Send a private message (no trigger phrase needed) |
| `-<command>` | Shorthand (SOPEL prefix is `-`) |
| `.<text>` | Shorthand (unknown .commands are forwarded to AI) |
| `.ai <prompt>` | Context-free AI prompt |
| `.optin` | Opt in to AI responses |
| `.optout` | Opt out of AI responses; `.optout <nick>` (admin only) opts out another nick |
| `.noisy` | Toggle status notices |
| `.setlocation <city, state>` | Set your location |
| `.addprompt <trigger> <text>` | Create custom prompt |
| `.rmprompt <number>` | Remove custom prompt |
| `.listprompts` | List all custom prompts |
| `.compact` | Compact conversation history |
| `.clear` | Clear conversation history and start fresh |
| `.stats` | Show performance stats |
| `.help` | Show available commands |
| `.effort [level]` | Set reasoning effort |

Management commands can also be addressed to the bot directly
(e.g. `<botnick>: optin`). The bot nick is configured in SOPEL and injected
into prompts as `{botnick}`.

## Architecture

```
terra_ai/               # SOPEL plugin package (loaded from repo root)
├── __init__.py         # Exposes handlers from plugin.py (SOPEL folder-plugin)
├── bot.py              # Core plugin logic (TerraAI dispatcher)
├── plugin.py           # SOPEL @command / @rule(@sopel_plugin) decorators
├── config.py           # Configuration loading (TerraConfig)
├── database.py         # SQLite layer (7 tables)
├── providers/          # AI provider abstraction
│   ├── base.py         # AIProvider / Message
│   ├── registry.py     # ProviderRegistry with fallback chain
│   ├── openrouter.py   # OpenRouter (default)
│   ├── gemini.py       # Gemini
│   ├── openai.py       # OpenAI
│   └── ollama.py       # Ollama
├── tools/
│   └── web_search.py   # DuckDuckGo instant-answer search (no key)
├── prompts/            # Prompt management + defaults
├── context/            # Conversation context / compaction
└── commands/           # Command handlers (user.py, admin.py)
```

## License

MIT
