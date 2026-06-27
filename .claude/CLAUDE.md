# TerraAI Development Rules

## Environment

- **OPENROUTER_API_KEY**: Always available. Source it before running tests:
  ```bash
  source ~/.terra-ai/.env
  ```
  The key is in `~/.terra-ai/.env`. Never say "I don't have the key" — it's always there.

- **Running real API tests**: Always source the env first:
  ```bash
  source ~/.terra-ai/.env && pytest tests/test_tools.py --real -m real -v
  ```

## Code Rules

- **NEVER hardcode the command prefix** (`.` or `-`). SOPEL's `settings.core.prefix` owns it.
- **NO YAML config** — everything goes in SOPEL's `.cfg` `[terraai]` section.
- **Tests for tools use REAL HTTP**, not mocks.
- **No silent skips**: if a test needs credentials, fail loudly with instructions, never `pytest.skip()`.
- **All routing goes through SOPEL's dispatcher** — no manual shims.
