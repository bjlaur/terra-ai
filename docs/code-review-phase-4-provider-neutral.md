# Phase 4: Provider-Neutral Refactor

Phase 4 removes OpenRouter construction and private implementation details from
TerraAI's core while preserving the current OpenRouter-only runtime. The
contract deliberately permits a future local or in-process model: providers do
not need an API key, HTTP transport, remote health check, or OpenAI-compatible
wire format.

## Shared provider contract

Every provider now exposes public `name`, `model`, `configured`,
`capabilities`, and `chat` members. `configured` describes only whether the
adapter has its required local configuration; it never performs a remote
availability probe. Capabilities currently declare local function tools and
provider-native search. Effort/reasoning remains deferred and is not presented
as a completed neutral capability.

`TerraAI` receives a provider registry instead of constructing OpenRouter. It
uses only the shared public contract for prompt composition, tool selection,
calls, logging, and telemetry. Runtime-specific validation and OpenRouter
construction now live at the plugin setup boundary.

A network-free in-process provider contract test has no credentials, HTTP
client, health endpoint, OpenRouter fields, or private `_model`. It exercises
the complete core call and proves that all four capability combinations select
only the corresponding prompts and local tools.

## Tools and prompts

Provider-neutral local function schemas are now separate from native provider
tools. OpenRouter owns and inserts its web-search schema exactly once, alongside
the local tools supplied by core. The original system-prompt wording and order
remain unchanged; prompts describing weather tools or native search are omitted
when the active provider does not declare that feature.

The existing tool-management implementation remains unchanged in behavior for
this phase. Review established that `disable-tool`, `enable-tool`, and
`list-tools` were intended as admin-only, server-wide policy, but the current
code incorrectly stores per-nick overrides without an admin guard. Correcting
that ownership and schema is recorded for Phase 5 and requires fresh permission
before replacing the incompatible SQLite table.

## Provider scope

The standalone Gemini adapter and its active dependency/documentation claims
were removed under the recorded user permission. This does not remove Gemini
model identifiers routed through OpenRouter.

OpenAI and Ollama remain experimental adapters and are not runtime-selectable.
They cheaply satisfy the public contract, include system messages, avoid remote
configuration probes, and explicitly reject local tools and non-default effort
instead of silently ignoring them. No provider-selection UI, fallback feature,
or dormant-provider feature parity was added.

The registry retains its dormant fallback construction API so future selection
work remains possible, but the plugin creates only one OpenRouter provider and
active documentation does not advertise a working fallback chain.

## Verification

- Focused provider, prompt, tool, plugin, and E2E tests: **119 passed**.
- Complete offline gate: **180 passed, 22 skipped**.
- Real-service gate: all **16 scenarios passed**. The runner output detached
  after 13 successful scenarios; the exact three remaining nodes were selected
  directly and passed, without rerunning completed scenarios.
- Ergo/Sopel gate: **21 passed, 1 expected xfail** in 54.28 seconds. The xfail
  remains the live model's unreliable production of a response over 450 bytes.
- `git diff --check` passed.

Phase 5 routing and general cleanup has not started.
