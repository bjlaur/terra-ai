# TerraAI

A SOPEL plugin that turns an IRC bot into a provider-agnostic AI assistant.

## Features

- Responds to `TerraAI:` trigger and `.` shorthand
- Provider-agnostic: OpenRouter (default), Gemini, OpenAI, Ollama
- SQLite persistence for conversation history, prompts, and user preferences
- Custom prompts via `.addprompt`, `.rmprompt`, `.listprompts`
- User opt-in/opt-out
- Context compaction with AI-driven pruning
- Web search (provider-native + DuckDuckGo fallback)
- Performance stats tracking

## Requirements

- Arch Linux (or any Linux with pacman)
- Python 3.12+
- SOPEL 8.0+

## Installation

```bash
# Install dependencies
sudo pacman -S --noconfirm python-yaml python-openai python-httpx

# Install SOPEL from AUR
yay -S --needed --noconfirm sopel

# Configure
cp config/terraai.yaml.example config/terraai.yaml
# Edit config/terraai.yaml with your API key

# Run
sopel -c config/terraai.yaml
```

## Docker

```bash
docker build -t terra-ai .
docker run -v ./data:/home/terra-ai/data -v ./config:/home/terra-ai/config terra-ai
```

## Development

```bash
# Run tests
pytest tests/

# Check compilation
python -m py_compile terraai/*.py terraai/**/*.py
```

## Commands

| Command | Description |
|---------|-------------|
| `TerraAI: <text>` | Talk to the bot directly (trigger phrase in channels) |
| `/msg TerraAI <text>` | Send a private message (no trigger phrase needed) |
| `.<text>` | Shorthand (unknown .commands are forwarded to AI) |
| `.ai <prompt>` | Context-free AI prompt |
| `.optin` / `.optout` | Toggle AI responses |
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

## Architecture

```
terraai/
├── bot.py              # Core plugin logic
├── plugin.py           # SOPEL @rule decorators
├── config.py           # Configuration loading
├── database.py         # SQLite layer (7 tables)
├── providers/          # AI provider abstraction
├── prompts/            # Prompt management
├── context/            # Conversation context
└── commands/           # Command handlers
```

## License

MIT
