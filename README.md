# TerraAI

A SOPEL plugin that turns an IRC bot into a provider-agnostic AI assistant.

## Features

- Responds to addressed queries (`TerraAI: <text>`) and `-` command shorthand
- Direct messages via `/msg <botnick> <text>` (no trigger phrase needed)
- OpenRouter runtime with a provider-neutral interface for future adapters
- Provider-native web search plus local Open-Meteo weather tools
- SQLite persistence for conversation history, prompts, and user preferences
- Custom prompts via `.addprompt`, `.rmprompt`, `.listprompts`
- Configurable bot nick via `{botnick}` variable in prompts (no hardcoded name)
- User opt-in/opt-out; admin opt-out of other nicks
- Context-free AI prompts (`.ai <prompt>`)
- Context compaction with AI-driven pruning, history `.clear`
- Noisy mode (`.noisy`) — shows a "Thinking..." notice before AI responses
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
`env.example`). Web search is provided by OpenRouter. Then:

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
# Complete deterministic suite; .env is not loaded and network is blocked
./test.sh fast

# The same plugin E2E scenarios using OpenRouter and Open-Meteo from .env
./test.sh real

# Temporarily override the configured model without editing tracked config
./test.sh real --model nvidia/nemotron-3-super-120b-a12b:free
TERRAI_TEST_MODEL=google/gemma-4-31b-it:free ./test.sh real

# Always-real IRC → Ergo → SOPEL → plugin → service → IRC system tests
./test.sh ergo

# Keep the system-test Ergo/SOPEL bot running for manual irssi testing
./test.sh manual

# All three gates in order
./test.sh all

# Run the normal real and Ergo suites once for each benchmark model.
# Test records, provider attempts, and end-to-end timings are written under
# benchmark-results/.
scripts/benchmark-models

# Benchmark a single model or choose an output directory
scripts/benchmark-models --model inclusionai/ling-3.0-flash:free
scripts/benchmark-models --output-dir benchmark-results/my-run

# Pace OpenRouter request starts at 20 RPM (one start every 3 seconds)
scripts/benchmark-models --model inclusionai/ling-3.0-flash:free --rpm 20

# Check compilation
python -m compileall -q terra_ai tests
```

`./test.sh real` and `./test.sh ergo` continue to run their full normal live
suites. Tests marked `benchmark` additionally record their prompts, exact
responses, pytest outcome, and send-to-final-response wall-clock latency when
`TERRAI_BENCHMARK_OUTPUT` is set by `scripts/benchmark-models`. Direct `--real`
tests also receive an enriched provider-attempt sink through
`TERRAI_BENCHMARK_PROVIDER_OUTPUT`; Ergo remains an integration result set and
is not used for provider-performance statistics.

## OpenRouter request pacing

TerraAI can evenly space OpenRouter request starts across concurrent SOPEL
handlers, local tool rounds, and concise rewrites. Existing installations remain
unpaced unless one of these `[terraai]` settings is enabled:

```ini
provider_requests_per_minute = 20
provider_min_interval = 0
```

The effective interval is the stricter of `60 / provider_requests_per_minute`
and `provider_min_interval`. A value of zero disables that individual
constraint. When pacing is enabled, an HTTP 429 or 503 is retried twice,
waiting one effective interval before each retry. Noisy mode shows a notice for
every actual pacing wait, with retry waits using the more specific retry notice.
With pacing disabled, TerraAI returns the first 429/503 without immediate
retries. Pacing is process-local and does not coordinate multiple TerraAI
processes that share an OpenRouter API key.

## Provider telemetry and benchmark artifacts

Normal TerraAI operation writes two rotating files under `log_dir`:

```text
provider-calls.jsonl      # one compact analytics row per OpenRouter HTTP attempt
openrouter-trace.jsonl    # full redacted request/response wire events
```

Compact provider logging is enabled by default and can be configured with:

```ini
provider_call_log_enabled = true
provider_call_log_max_bytes = 26214400
provider_call_log_backup_count = 2
```

A benchmark model directory contains:

```text
model.txt
real.log
real-tests.jsonl
real-provider-calls.jsonl
ergo.log
ergo-tests.jsonl
benchmark-results.json
```

`real-tests.jsonl` records one completed direct benchmark test per line.
`real-provider-calls.jsonl` records one enriched OpenRouter attempt per line.
After both suites finish, those streams are joined into the model's canonical
`benchmark-results.json`. The run-level `benchmark-results.json` then stitches
the completed per-model files together and recomputes aggregate min, mean,
median, nearest-rank p95, and max statistics. Ergo records remain under the
top-level `ergo` key and do not contribute provider-performance measurements.


## Commands

| Command | Description |
|---------|-------------|
| `<botnick>: <text>` | Talk to the bot directly (addressed query in channels) |
| `/msg <botnick> <text>` | Send a private message (no trigger phrase needed) |
| `-<command>` | Shorthand (SOPEL prefix is `-`) |
| `.<text>` | Shorthand (unknown .commands are forwarded to AI) |
| `.ai <prompt>` | Context-free AI prompt |
| `-admin <prompt>` | Send an authoritative admin prompt (admin only) |
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
│   ├── registry.py     # Active-provider holder
│   ├── openrouter.py   # Active OpenRouter runtime
│   ├── pacing.py      # Shared request-start pacing and cooldowns
│   ├── telemetry.py   # Structured provider-attempt sinks
│   ├── openai.py       # Experimental, not runtime-selectable
│   └── ollama.py       # Experimental, not runtime-selectable
├── tools/              # Provider-neutral local tools
├── prompts/            # Prompt management + defaults
├── context/            # Conversation context / compaction
└── commands/           # Command handlers (user.py, management.py)
```

## License

MIT
