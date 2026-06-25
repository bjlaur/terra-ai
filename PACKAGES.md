# TerraAI Package Dependencies

Arch packages for the Containerfile. Installed via pacman, not pip.

## Required (0.0.1)

| Package | Source | Purpose |
|---------|--------|---------|
| `sopel` | AUR (yay) | IRC bot framework |
| `python-yaml` | extra | Config parsing |
| `python-openai` | extra | AI provider client |

## Future

| Package | Source | Purpose | For |
|---------|--------|---------|-----|
| `python-aiohttp` | extra | Async HTTP | Web search |
| `python-beautifulsoup4` | extra | HTML scraping | Web search fallback |
| `python-dotenv` | extra | .env loading | Local dev |
| `python-textual` | extra | TUI framework | Test tool |
