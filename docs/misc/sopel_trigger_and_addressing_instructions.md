# Sopel: `-` trigger, plugin access, and `BotNick:` queries

This is a direct implementation guide for Claude Code. Do not redesign this. Sopel already has built-in support for all three pieces:

1. global command trigger/prefix configuration
2. prefix-aware plugin commands via `@plugin.command(...)`
3. bot-nick-addressed messages via `@plugin.nickname_command(...)` and/or `@plugin.rule(r'$nick ...')`

## Goal

Make the bot respond to both styles:

```irc
-ask what is up?
BotNick: ask what is up?
BotNick: what is up?
```

The `-ask ...` form is a normal Sopel command using the configured prefix.
The `BotNick: ask ...` form is a Sopel nickname command.
The fully freeform `BotNick: anything ...` form requires a generic rule using `$nick`.

---

## 1. Configure Sopel to use `-` as the trigger character

Edit the Sopel config file, typically one of these:

```text
~/.sopel/default.cfg
~/.sopel/<profile>.cfg
```

In the `[core]` section, set:

```ini
[core]
prefix = -
help_prefix = -
```

`prefix` is a regular expression in Sopel. A literal hyphen is fine by itself here. This is also acceptable if you want to be extra explicit:

```ini
[core]
prefix = \-
help_prefix = -
```

If you want both the default dot prefix and hyphen prefix:

```ini
[core]
prefix = \.|\-
help_prefix = -
```

Important notes:

- Do not put the command name in `prefix`.
- Do not make a plugin manually parse `-` unless there is a very specific reason.
- Do not use capturing groups in the prefix regex. Capturing groups can interfere with Sopel command argument parsing.
- Keep `help_prefix` in sync with the human-facing prefix so `.help` / `-help` output examples make sense.

Expected result:

```irc
-help
-ask hello
```

---

## 2. Reference the configured trigger in a plugin

Usually, do **not** reference it directly.

Use `@plugin.command('name')`. Sopel applies the configured `[core] prefix` automatically.

Example:

```python
from sopel import plugin


@plugin.command('hello')
def hello(bot, trigger):
    bot.say(f'hello, {trigger.nick}')
```

With this config:

```ini
[core]
prefix = -
help_prefix = -
```

The command is invoked as:

```irc
-hello
```

Do not write code that assumes the command prefix is literally `-`, unless you are only generating human-facing help text.

If the plugin needs the configured values for display/debugging:

```python
prefix_regex = bot.settings.core.prefix
help_prefix = bot.settings.core.help_prefix
```

For user-visible usage strings, prefer `help_prefix`, because `prefix` is a regex and may look like `\.|\-`.

---

## 3. Normal command form: `-ask query here`

Use `@plugin.command('ask')`.

Sopel’s command match groups are:

- `trigger.group(1)` = command name that matched
- `trigger.group(2)` = rest of the line after the command, excluding leading whitespace
- `trigger.group(3)` through `trigger.group(6)` = first few whitespace-separated params

Example:

```python
from sopel import plugin


@plugin.command('ask')
def ask_command(bot, trigger):
    text = (trigger.group(2) or '').strip()

    if not text:
        bot.reply('usage: -ask <query>')
        return

    bot.say(f'query received: {text}')
```

Expected behavior:

```irc
<user> -ask what is jellyfin?
<bot> query received: what is jellyfin?
```

---

## 4. Bot-nick command form: `BotNick: ask query here`

Use `@plugin.nickname_command('ask')`.

This responds to variants like:

```irc
BotNick: ask what is jellyfin?
BotNick, ask what is jellyfin?
BotNick ask what is jellyfin?
```

Example:

```python
from sopel import plugin


@plugin.nickname_command('ask')
def ask_nick_command(bot, trigger):
    text = (trigger.group(2) or '').strip()

    if not text:
        bot.reply('usage: BotNick: ask <query>')
        return

    bot.say(f'query received: {text}')
```

Sopel handles the bot nickname matching. Do not hardcode the bot nick.

---

## 5. Share one handler between `-ask ...` and `BotNick: ask ...`

This is the clean version for supporting both:

```python
from sopel import plugin


def handle_query(bot, trigger, text: str):
    text = text.strip()

    if not text:
        bot.reply('usage: -ask <query>  OR  BotNick: ask <query>')
        return

    # Replace this with the actual LLM/API/plugin logic.
    bot.say(f'query received: {text}')


@plugin.command('ask')
@plugin.nickname_command('ask')
def ask(bot, trigger):
    text = trigger.group(2) or ''
    handle_query(bot, trigger, text)
```

This supports:

```irc
-ask what is jellyfin?
BotNick: ask what is jellyfin?
BotNick, ask what is jellyfin?
BotNick ask what is jellyfin?
```

---

## 6. Freeform addressed queries: `BotNick: query here`

If the desired behavior is:

```irc
BotNick: what is jellyfin?
```

without requiring the word `ask`, then `@plugin.nickname_command('ask')` is not enough. That decorator is for named commands after the nick.

Use a generic rule with Sopel’s `$nick` placeholder.

Example:

```python
from sopel import plugin


@plugin.rule(r'$nick\s+(.+)')
def addressed_freeform(bot, trigger):
    text = (trigger.group(1) or '').strip()

    if not text:
        return

    # Optional: avoid double-handling named commands if another handler catches them.
    if text.lower().startswith('ask '):
        text = text[4:].strip()

    bot.say(f'query received: {text}')
```

Expected behavior:

```irc
<user> BotNick: what is jellyfin?
<bot> query received: what is jellyfin?
```

Important: `$nick` is a Sopel special token. It expands to the bot’s configured nick and handles nick punctuation like `:` or `,`. Do not replace `$nick` with a hardcoded nickname.

---

## 7. Recommended final plugin pattern

Use this pattern if the bot should accept all three forms:

```python
from sopel import plugin


def handle_query(bot, trigger, text: str):
    text = text.strip()

    if not text:
        bot.reply('usage: -ask <query>  OR  BotNick: ask <query>  OR  BotNick: <query>')
        return

    # TODO: call the real backend here.
    bot.say(f'query received: {text}')


@plugin.command('ask')
@plugin.nickname_command('ask')
def ask(bot, trigger):
    """Handle explicit ask commands."""
    text = trigger.group(2) or ''
    handle_query(bot, trigger, text)


@plugin.rule(r'$nick\s+(.+)')
def addressed_freeform(bot, trigger):
    """Handle freeform messages addressed to the bot by nick."""
    text = (trigger.group(1) or '').strip()

    # Avoid double-processing if Sopel also invokes the nickname_command handler.
    # Depending on rule ordering and exact message, `BotNick: ask foo` may match this too.
    if text.lower().startswith('ask '):
        text = text[4:].strip()

    handle_query(bot, trigger, text)
```

If duplicate replies happen for `BotNick: ask foo`, split the behavior:

- Keep `@plugin.command('ask')` for `-ask foo`
- Keep `@plugin.nickname_command('ask')` for `BotNick: ask foo`
- In the freeform `$nick` handler, ignore messages beginning with known commands:

```python
KNOWN_NICK_COMMANDS = {'ask', 'help'}


@plugin.rule(r'$nick\s+(.+)')
def addressed_freeform(bot, trigger):
    text = (trigger.group(1) or '').strip()
    first_word = text.split(maxsplit=1)[0].lower() if text else ''

    if first_word in KNOWN_NICK_COMMANDS:
        return

    handle_query(bot, trigger, text)
```

---

## 8. Test checklist

After changing the config and plugin, restart Sopel or reload the plugin/config as appropriate.

Test these in IRC:

```irc
-help
-ask hello
BotNick: ask hello
BotNick, ask hello
BotNick ask hello
BotNick: hello
```

Expected:

- `-help` works, not only `.help`.
- `-ask hello` calls the `@plugin.command('ask')` handler.
- `BotNick: ask hello` calls the `@plugin.nickname_command('ask')` handler.
- `BotNick: hello` calls the `$nick` freeform rule handler.

---

## 9. Common mistakes to avoid

Do not do this:

```python
@plugin.rule(r'^-(ask)\s+(.+)')
```

unless you specifically want to bypass Sopel’s command system. Use this instead:

```python
@plugin.command('ask')
```

Do not hardcode the bot nick:

```python
@plugin.rule(r'^MyBot[:,]?\s+(.+)')
```

Use Sopel’s `$nick` placeholder instead:

```python
@plugin.rule(r'$nick\s+(.+)')
```

Do not display `bot.settings.core.prefix` directly to users if it is a regex like `\.|\-`. Use:

```python
bot.settings.core.help_prefix
```

---

## 10. Summary for implementation

Make these changes:

1. In Sopel config:

   ```ini
   [core]
   prefix = -
   help_prefix = -
   ```

2. In the plugin, use:

   ```python
   @plugin.command('ask')
   ```

   for `-ask ...`.

3. Use:

   ```python
   @plugin.nickname_command('ask')
   ```

   for `BotNick: ask ...`.

4. Use:

   ```python
   @plugin.rule(r'$nick\s+(.+)')
   ```

   for freeform `BotNick: ...` messages.

5. Do not manually parse the `-` prefix unless absolutely necessary.

