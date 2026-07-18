"""Small SOPEL test doubles that dispatch through the real plugin rules."""

from sopel.plugins import exceptions as plugin_exceptions
from sopel.plugins import rules as plugin_rules
from sopel.plugins.rules import Manager

from terra_ai import plugin as terra_plugin


class _Core:
    nick = "TerraAI"
    prefix = r"\-"
    help_prefix = "-"
    alias_nicks = ()
    owner = ""
    admins = ()
    admin_accounts = ()
    owner_account = ""


class _Settings:
    core = _Core()


class FakeBot:
    """Minimum SOPEL-compatible bot needed by the real rule manager."""

    def __init__(self):
        self.settings = _Settings()
        self.nick = self.settings.core.nick
        self._rules_manager = Manager()
        self.messages: list[str] = []
        self.notices: list[tuple[str, str]] = []

    @property
    def rules(self):
        return self._rules_manager

    @property
    def isupport(self):
        return {"NETWORK": "test-network"}

    def register_callables(self, callables):
        for callable_ in callables:
            commands = getattr(callable_, "commands", [])
            nick_commands = getattr(callable_, "nickname_commands", [])
            lazy_rules = getattr(callable_, "rule_lazy_loaders", [])
            rules = getattr(callable_, "rules", []) or getattr(callable_, "rule", [])
            action_commands = getattr(callable_, "action_commands", [])

            if commands:
                self.rules.register_command(
                    plugin_rules.Command.from_callable(self.settings, callable_)
                )
            if nick_commands:
                self.rules.register_nick_command(
                    plugin_rules.NickCommand.from_callable(self.settings, callable_)
                )
            if action_commands:
                self.rules.register_action_command(
                    plugin_rules.ActionCommand.from_callable(self.settings, callable_)
                )
            if rules:
                self.rules.register(plugin_rules.Rule.from_callable(self.settings, callable_))
            if lazy_rules:
                try:
                    self.rules.register(
                        plugin_rules.Rule.from_callable_lazy(self.settings, callable_)
                    )
                except plugin_exceptions.PluginError:
                    # Some lazy loaders require a running bot. Ordinary rules
                    # still exercise the production dispatcher.
                    pass

    def say(self, message, destination=None, max_messages=1, truncation="", trailing=""):
        self.messages.append(message)

    def notice(self, message, destination=None):
        self.notices.append((destination or "", message))


def build_fake_bot() -> FakeBot:
    """Register every production plugin callable on a fresh fake bot."""
    bot = FakeBot()
    callables = [
        getattr(terra_plugin, name)
        for name in dir(terra_plugin)
        if getattr(getattr(terra_plugin, name), "_sopel_callable", False)
    ]
    bot.register_callables(callables)
    return bot


class PluginTestClient:
    """Convenience wrapper around :func:`terra_ai.plugin.dispatch_line`."""

    def __init__(self, bot: FakeBot | None = None):
        self.server = "test-network"
        self.channel = "#terra-ai"
        self.nick = "tester"
        self.bot = bot or build_fake_bot()

    def send_message(self, text: str) -> dict:
        return terra_plugin.dispatch_line(self.bot, self.nick, text, is_pm=False)

    def send_as(self, nick: str, text: str) -> dict:
        return terra_plugin.dispatch_line(self.bot, nick, text, is_pm=False)

    def send_pm(self, nick: str, text: str) -> dict:
        return terra_plugin.dispatch_line(self.bot, nick, text, is_pm=True)
