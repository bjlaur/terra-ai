# TerraAI Package Dependencies

Arch packages for the Containerfile. Installed via pacman, not pip.

```bash
sudo pacman -S --noconfirm python-yaml python-openai python-httpx
```

## Required (0.0.1)

| Package | Source | Purpose |
|---------|--------|---------|
| `sopel` | AUR (yay) | IRC bot framework |
| `python-yaml` | extra | Config parsing |
| `python-openai` | extra | AI provider client |
| `python-httpx` | extra | HTTP client (OpenRouter provider) |

## Future

| Package | Source | Purpose | For |
|---------|--------|---------|-----|
| `python-aiohttp` | extra | Async HTTP | Web search |
| `python-beautifulsoup4` | extra | HTML scraping | Web search fallback |
| `python-dotenv` | extra | .env loading | Local dev |
| `python-textual` | extra | TUI framework | Test tool |
