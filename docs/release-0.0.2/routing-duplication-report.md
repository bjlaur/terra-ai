# Routing Duplication Report

**Date:** 2026-06-27
**Scope:** terra-ai codebase (`test_tool/`, `terra_ai/`, `tests/`) vs SOPEL native routing
**Sources:** our code under `~/agentic-repos/terra-ai-agent2/`; canonical SOPEL in `~/git/sopel`

## Summary

We maintain **three parallel routing mechanisms** for decisions that SOPEL already
resolves natively. Two of them — a redundant trigger-phrase path, and a
manually-dispatched prefix path — duplicate SOPEL's `@rule` machinery. A third —
`_is_registered_sopel_command` plus `bot.rules` introspection — duplicates the
prefix-handler dispatch that SOPEL's `RulesManager` already does.

Removing the duplicates means:
- `plugin.py` handles route entirely via decorators (`@command`, `@rule_lazy`,
  `@rule("$nick ...")`), exactly as production uses them.
- The test console builds a real `PreTrigger` and runs `bot.rules.get_triggered_rules`
  + `rule.execute` — i.e. **the same dispatch loop** — instead of reimplementing it.
- The redundant `trigger_char` config field (a second copy of SOPEL's
  `settings.core.prefix`) and the whole `trigger_phrase` field (a second copy of
  SOPEL's `$nick` addressing) are removed from `TerraAISection`.

---

## Mechanism 1 — Command dispatch by name (`@sopel_plugin.command(...)`)

**Purpose:** "A message starting with the prefix and the word `optin` → `cmd_optin`."

**SOPEL does this natively** (`sopel/plugin.py::command`, `~/git/sopel`):
```python
@sopel_plugin.command("optin")          # no prefix char in the name
def cmd_optin(bot, trigger): ...
```
SOPEL strips `settings.core.prefix` from the line, matches the bare word `optin`,
and dispatches. The handler never sees the prefix char. `Trigger.group(2)` returns
the args.

**Our duplication — `plugin.py::_cmd_word` + manual `globals().get` dispatch:**
```python
# terra_ai/plugin.py:363
def _cmd_word(text):
    trigger_char = terra.prompts.trigger_char          # redundant config
    if text.startswith(trigger_char):
        rest = text[len(trigger_char):]
        return rest.split()[0].lower() if rest.strip() else ""
    return ""

# terra_ai/plugin.py:388-394
cmd = _cmd_word(text)
if cmd:
    handler = globals().get(f"cmd_{cmd}")             # manual dispatch!
    if handler:
        _notify_thinking(...)
        handler(bot, trigger)
        return list(bot.bot.messages)
```
This re-implements what SOPEL's `RulesManager.get_triggered_rules` already does
for `@command`-decorated handlers. **The only reason this exists is to serve the
test console**, which can't run the real dispatch loop. Fix: the console should run
the real dispatch loop.

---

## Mechanism 2 — Unknown-prefixed-command fallback (`@sopel_plugin.rule_lazy(...)`)

**Purpose:** "A message starting with the prefix and any unknown word → AI."

**SOPEL does this natively** (`terra_ai/plugin.py:249-255`, already correct):
```python
def _prefix_fallback_loader(settings):
    prefix = settings.core.prefix                    # SOPEL owns this
    pattern = rf'^(?:{prefix})(?P<command>\S+)(?:\s+(?P<args>.*))?$'
    return [re.compile(pattern)]

@sopel_plugin.rule_lazy(_prefix_fallback_loader)
def unknown_prefixed_command_to_ai(bot, trigger): ...
```
This handler is **already wired through SOPEL** — good. It also uses `_is_registered_sopel_command`
(line 258) to skip known commands; that's a legitimate SOPEL-rules query, not a
reimplementation.

**Our duplication — `plugin.py::handle_channel_message` lines 395-400:**
```python
# Unknown prefixed command → forward to AI as freeform
full_text = text[len(trigger_char):].strip() ...
trigger.group = lambda n: full_text if n == 1 else None
_notify_thinking(...)
addressed_freeform(bot, trigger)          # bypasses SOPEL dispatch
```
This is the *manual* version of what `unknown_prefixed_command_to_ai` already
does through SOPEL. When routing through the real dispatcher, this branch
disappears — `unknown_prefixed_command_to_ai` runs first for an unknown word, and
known words hit their `@command` handler directly.

---

## Mechanism 3 — Addressed-freeform routing (`@sopel_plugin.rule("$nick (.+)")`)

**Purpose:** "A message addressing the bot nick → AI."

**SOPEL does this natively** (`terra_ai/plugin.py:318`):
```python
@sopel_plugin.rule(r"$nick (.+)")
@sopel_plugin.allow_bots
def addressed_freeform(bot, trigger): ...
```
SOPEL expands `$nick` to the configured bot nick at load time. **No `trigger_phrase`
config exists or is needed.** The handler takes `trigger.group(1)` (the part after
the nick) and forwards to `handle_ai_message`.

**Our duplication — the `trigger_phrase` path in `handle_channel_message` (lines 402-406):**
```python
trigger_phrase = terra.config.trigger_phrase            # redundant config field
if text.lower().startswith(trigger_phrase.lower()):
    _notify_thinking(...)
    trigger.group = lambda n: text[len(trigger_phrase):].strip() if n == 1 else None
    addressed_freeform(bot, trigger)
    return list(bot.messages)
```
This whole block exists *only* so the test console can send a literal `TerraAI: hello`
string and get it routed. In production it's dead — SOPEL's `$nick` rule handles
addressing, never consulting any `trigger_phrase` config. **The field
`TerraAISection.trigger_phrase` (config.py:67) is pure duplication of SOPEL's nick rule.**

---

## Mechanism 4 — The redundant `trigger_char` config field

**Purpose:** "The prefix char that introduces commands."

**SOPEL's source of truth** — `bot.settings.core.prefix`, default `\.` (`~/git/sopel`);
already loaded into every `Trigger` SOPEL builds; `_prefix_fallback_loader` reads it
(our plugin.py:252). The prefix char is a *SOPEL core setting*, not a TerraAI concern.

**Our duplication — `TerraAISection.trigger_char` (`terra_ai/config.py:67-80`):**
A second, parallel field defaulting to `.`, passed into
`PromptManager(trigger_char=...)` (bot.py:30) and consumed by `FakeTrigger.group()`
(console.py:88-91), `_cmd_word` (plugin.py:368), and `handle_channel_message`
(plugin.py:385). Five read sites, all duplicating a SOPEL core setting that's
available for free as `bot.settings.core.prefix`.

Note: `PromptManager` uses the value to render `{triggerchar}` in prompts and to
normalize prompt triggers — see the §"What stays" section below.

---

## Mechanism 5 — Manual thinking-notify (`_notify_thinking`)

**SOPEL's analog:** nothing identical, but SOPEL runs `@command` handlers directly,
and the `_irc_error_handler` wrapper (plugin.py:17) already handles per-handler
errors and notices consistently. The thinking-notify is a legitimate behavior, but
duplicating it before *every* handler call (lines 393, 403, 426, 430) instead of
putting it *inside* the one place that dispatches means the dispatch shim owns
responsibility that belongs elsewhere.

When dispatching through SOPEL, `_notify_thinking` moves into the handlers that
actually start an AI call (the addressed freeform + Ai-command path in
`unknown_prefixed_command_to_ai` and inside the AI-call site), not the dispatcher.

---

## Cross-cutting: the `globals().get(f"cmd_{cmd}")` dispatcher

`handle_channel_message` (plugin.py:390) and `handle_pm_message` (plugin.py:424) both
do `globals().get(f"cmd_{cmd}")`. This is a hand-rolled version of SOPEL's
`RulesManager`, which already maps command names to their `@command`-decorated
handlers. It also means the test console's routing is **decoupled from SOPEL's
decorator configuration** — if a handler is renamed or a new `@command` is added,
this manual dispatcher silently misses it until a test fails.

---

## What stays (not duplication)

These are legitimate and should **not** be removed:

- **`_prefix_fallback_loader` + `unknown_prefixed_command_to_ai`** (plugin.py:245-313)
  — already routed through SOPEL via `@rule_lazy`. This is the *correct* pattern.
- **`addressed_freeform` with `@rule("$nick (.+)")`** (plugin.py:318-345) — already
  routed through SOPEL. Correct pattern.
- **`_irc_error_handler`** (plugin.py:17-30) — per-handler error wrapping, not routing.
- **`_KNOWN_NICK_COMMANDS`** (plugin.py:35-39) — used by `addressed_freeform` to
  avoid double-processing; a legitimate filter, not routing.
- **`PromptManager._trigger_char`** — used to render `{triggerchar}` in
  `SYSTEM_PROMPT_TEMPLATE` (defaults.py:31-33) and `FAKE_CONVERSATION`
  (defaults.py:9-11), and to normalize prompt triggers in `add_prompt`/`remove_prompt`
  (manager.py:66-67, 77-78). This is **prompt content**, not routing. It can stay as a
  value sourced from SOPEL's `settings.core.prefix` at runtime rather than a
  duplicate config field — but the *field* `TerraAISection.trigger_char` is the
  duplicate.

---

## Concrete duplication map (file:line)

| Duplication | Our location | SOPEL-native equivalent |
|---|---|---|
| `_cmd_word` prefix stripping | plugin.py:363-372 | SOPEL strips `core.prefix` before dispatch |
| `globals().get(f"cmd_{cmd}")` dispatch | plugin.py:390, 424 | `RulesManager.get_triggered_rules` |
| `trigger_phrase` addressed path | plugin.py:402-406 | `@rule(r"$nick (.+)")` (plugin.py:318) |
| manual unknown-prefix→AI branch | plugin.py:395-400 | `unknown_prefixed_command_to_ai` (plugin.py:272) |
| `TerraAISection.trigger_char` field | config.py:67-80 | `bot.settings.core.prefix` |
| `TerraAISection.trigger_phrase` field | config.py:67-70 | SOPEL's `$nick` addressing |
| `FakeTrigger` + `FakeTrigger.group()` | console.py:57-98 | SOPEL builds `Trigger(settings, pretrigger, match, account)` |
| `TerraAITestClient.send_message/send_pm` manual routing | console.py:177-213 | `bot.rules.get_triggered_rules` + `rule.execute` |
| `tests/conftest.py` `_make_test_config` trigger_char/trigger_phrase | conftest.py:52,54 | derive from bot config |
| `tests/test_commands.py` `trigger_char="-"` | test_commands.py:25 | derive from bot config |
| `tests/test_console.py` `client.trigger_char` / `client.terra.config.trigger_phrase` reads | test_console.py:52,72,83,... | derive from bot config |
| `tests/test_console_screenshots.py` same reads | test_console_screenshots.py:73,102,103,... | derive from bot config |
| `tests/test_ergo.py` `trigger_phrase: "TerraAI:"` in YAML | test_ergo.py:302,384 | remove (SOPEL uses `$nick`) |

---

## Recommended fix (single source of truth)

1. **plugin.py** — delete `handle_channel_message`, `handle_pm_message`, `_cmd_word`,
   `_notify_thinking`. Add one entry point `dispatch_line(bot, nick, line, is_pm)`
   that builds a real `PreTrigger(bot.settings.core.nick, line)` and runs
   `bot.rules.get_triggered_rules(bot, pretrigger)` → for each `(rule, match)`
   builds `Trigger(bot.settings, pretrigger, match, account=None)` and calls
   `rule.execute(SopelWrapper(bot, trigger), trigger)`. The existing
   `@command`/`@rule_lazy`/`@rule("$nick ...")` decorators do all the routing.

2. **config.py** — remove `trigger_phrase` and `trigger_char` from `TerraAISection`
   and the `load_config` fallback. (PromptManager keeps its `_trigger_char` value,
   sourced at runtime from `bot.settings.core.prefix` instead of a config field.)

3. **test_tool/console.py** — `FakeBot` exposes `settings` (a real `sopel.config.Config`
   with `core.prefix`) and `rules` (a real `RulesManager` populated by importing
   `terra_ai.plugin`). `TerraAITestClient.send_message/send_pm` call
   `terra_plugin.dispatch_line(...)`. Delete `FakeTrigger` (SOPEL builds the Trigger).

4. **tests/** — replace every `client.trigger_char` / `client.terra.config.trigger_phrase`
   read with a helper derived from the bot's real config; drop the redundant fields
   from `_make_test_config`; remove `trigger_phrase:` from `test_ergo.py` YAML.

After this, **all routing decisions are made by SOPEL's decorator-driven rules
manager** — in production and in the test console alike. No parallel reimplementation.
