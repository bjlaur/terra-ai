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

- Focused database, plugin-contract, and plugin E2E tests: **78 passed**.
- Complete deterministic offline gate: **190 passed, 22 skipped**. All 22
  skips are the separately selected always-real Ergo suite.
- Shared real-service plugin gate: **16 passed**.
- Ergo/Sopel gate: **21 passed, 1 expected xfail**. The xfail remains the live
  model's unreliable production of an over-450-byte response.
- `git diff --check` passed.

## Remaining decisions and deferred work

- `addressed_freeform` still opts into IRCv3 bot-tagged messages with
  `allow_bots`. This may be useful for bot interoperability but also creates a
  loop/cost/privacy risk and needs an explicit policy decision.
- The stale Ergo test named `test_bot_uses_web_search_for_weather` verifies
  only a weather response, not provider-native search. A future distinct test
  should cover an explicit user request for web search without duplicating the
  local-weather contract.
- Prompt management, `setlocation` persistence, clear/compact, telemetry,
  effort, container work, and provider selection remain deferred as recorded
  in the phased plan.
