# TerraAI Package Dependencies

Arch packages for the Containerfile. Installed via pacman, not pip.

```bash
sudo pacman -S --noconfirm python-yaml python-openai python-httpx python-aiohttp python-beautifulsoup4 python-dotenv python-textual python-pytest python-pytest-asyncio
```

## Required (0.0.1)

| Package | Source | Purpose |
|---------|--------|---------|
| `sopel` | AUR (yay) | IRC bot framework |
| `python-yaml` | extra | Config parsing |
| `python-openai` | extra | AI provider client |
| `python-httpx` | extra | HTTP client (OpenRouter provider) |

## Required (0.0.2)

| Package | Source | Purpose |
|---------|--------|---------|
| `python-textual` | extra | TUI framework (test tool) |
| `python-aiohttp` | extra | Async HTTP (web search) |
| `python-beautifulsoup4` | extra | HTML scraping (web search fallback) |
| `python-dotenv` | extra | .env loading (local dev) |
| `ergo` | AUR (yay) | IRC server for integration testing |
| `python-pytest` | extra | Test runner |
| `python-pytest-asyncio` | extra | Async test support (Textual) |
| `google-generativeai` | pip | Gemini provider (no Arch package) |

## Future

| Package | Source | Purpose | For |
|---------|--------|---------|-----|
| `ollama` | AUR (yay) | Local LLM server | Ollama provider |
