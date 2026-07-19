# Phase 5: Sopel Routing and Tool Policy

Phase 5 removes custom routing assumptions, returns test dispatch to test
support, and corrects local-tool management to its intended admin-owned,
server-wide semantics. It does not redesign deferred prompt management,
history commands, statistics, effort controls, or provider selection.

## Sopel routing

- Explicit nick addressing always remains an AI prompt. The hardcoded
  `_KNOWN_NICK_COMMANDS` suppression is gone, so `TerraAI: optin` is not
  mistaken for a second command syntax.
- Unknown prefixed channel prompts use Sopel's `Trigger.is_privmsg` instead of
  assuming every channel begins with `#`. Contract coverage includes an
  `&local` channel.
- Provider-calling fallback rules use Sopel's default threaded execution. The
  previous `thread(False)` annotations could block the bot's main dispatch
  thread during network calls.
- Production `plugin.py` no longer contains a synthetic IRC dispatcher or
  stale console callbacks. The dispatcher lives entirely in `tests/support.py`
  and still enters through Sopel's real rule manager.
- The repeated noisy-callback closures remain local to their handlers by
  explicit user decision. Their small duplication preserves the option for
  handler-specific behavior.
- Prompt-management commands were not given new admin decorators. Their
  eventual authorization and system/user-system prompt semantics remain part
  of the deferred prompt-management redesign.

## Server-wide local-tool policy

The user explicitly approved an incompatible, targeted replacement of the
legacy per-user `tools` table. Database initialization now drops only that
table and its old index, then creates:

```sql
disabled_tools (
    server TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (server, tool_name)
)
```

Existing tool overrides are intentionally discarded and all tools begin
enabled. No database-file reset is required. Users, prompts, conversations,
sessions, compactions, and statistics remain untouched. A database test builds
a legacy file, runs initialization, and proves that an unrelated user survives
while only the old tool table is replaced.

`ToolPolicyStore` owns persistence and `ToolPolicy` owns valid local-tool names
and status presentation. `UserStore` and `UserCommands` no longer contain tool
policy. The three Sopel commands are admin-only and affect every user on the
current IRC network. Enabling a tool removes its disabled row; a missing row
means enabled.

## Verification

- Complete deterministic offline gate at Phase 5 closeout:
  **203 passed, 21 skipped**. All 21 skips are the separately selected
  always-real Ergo suite.
- Complete shared real-service plugin gate: **19 passed, 205 deselected**.
- Complete Ergo/Sopel gate: **20 passed, 1 expected xfail**. The xfail remains
  the live model's unreliable production of an over-450-byte response.
- `git diff --check` passed.

## Explicit weather source selection

This item was moved into Phase 5 by user direction. A capability-aware system
instruction is present only when both local tools and provider-native search
are available. It tells the model to honor an explicit request for web search
instead of `weather_forecast`. The same instruction defines a distinct hybrid
request: when a user explicitly asks for both sources or a web-search overread,
the model must run local weather and provider-native search, then synthesize
one reply.

One shared plugin-routed test body covers deterministic and real services.
Fast mode scripts OpenRouter's documented
`usage.server_tool_use.web_search_requests` metadata. Real mode observes the
same metadata through TerraAI's `Searching web...` noisy notice. Both modes
reject a `Fetching weather...` notice, and fast mode additionally proves that
no Open-Meteo HTTP request occurred. A second shared scenario requires both
`Searching web...` and `Fetching weather...`, so hybrid behavior cannot pass
from answer wording alone. Focused prompt/contract/fast coverage passed
**15 tests**; both identical live scenarios passed.

A one-run live benchmark using fresh per-test TerraAI/database fixtures and the
same configured model measured **6.50s** for local Open-Meteo, **6.88s** for
web-search-only, and **19.59s** for hybrid overread. These are observations of
live provider/network conditions, not stable performance guarantees.

The misleading reply-text-only Ergo test was deleted with explicit permission.
No Ergo duplicate replaces it because provider/tool selection is already
covered through `plugin.py`; retained Ergo tests continue to cover real
weather-tool progress and results through the IRC boundary.

## Authoritative admin prompts

The admin-only `-admin <prompt>` command uses the normal history-enabled AI
path, including provider tools, noisy notices, concise-response handling,
logging, persistence, and error reporting. Its sole semantic difference is
that the model and history receive the raw prompt without a `<nick>` prefix.
The base system rules already define an unprefixed user-role message as an
authoritative admin prompt. Opt-out still applies because all other ordinary
message behavior was intentionally preserved.

One shared fast/real plugin E2E body proves that the provider receives the raw
prompt and that history stores the same raw prompt. Plugin contract tests prove
admin denial, opt-out, empty-command usage, noisy callback wiring, and inclusion
of Sopel's admin check inside TerraAI's terminal error boundary.

## Phase 5 closeout

- TerraAI's error boundary now encloses Sopel's authorization wrapper on every
  TerraAI admin-only command. Normal permission decisions are unchanged.
- Help and usage output uses Sopel's configured `core.help_prefix`; routing
  continues to use Sopel's separate `core.prefix` regex.
- `addressed_freeform` intentionally retains `allow_bots` by user decision.
- The small repeated noisy-callback closures intentionally remain local to
  their handlers.

The cleanup phase is closed by user direction. The following audit findings
are explicitly deferred to the next cleanup iteration and are not claims about
currently supported behavior:

- Prompt-management semantics, including the known `rmprompt` behavior and its
  redundant parsing line.
- Clear/compact, statistics/telemetry, effort/reasoning, provider selection and
  fallback, and container/package implementation.
- Broader active README corrections for unfinished commands and false feature
  claims, TerraAISection's false zero-configuration wording, and the
  machine-specific path in the active Sopel test-config example.
- Simplifying repeated `UserCommands` local imports, removing the pointless
  Open-Meteo function alias/import-order smell, closing SQLite if schema
  initialization fails, and changing elapsed-time measurements to monotonic
  clocks.

No deferred code is authorized for deletion, and no SQLite file or unrelated
schema may be reset as part of this closeout.

## Deferred feature work

- Prompt management, `setlocation` persistence, clear/compact, telemetry,
  effort, container work, and provider selection remain deferred as recorded
  in the phased plan.
