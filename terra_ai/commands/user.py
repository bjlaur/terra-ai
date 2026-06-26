"""User commands for TerraAI."""

from terra_ai.database import Database
from terra_ai.prompts.manager import PromptManager


class UserCommands:
    """User-facing commands."""

    def __init__(self, db: Database, prompts: PromptManager):
        self.db = db
        self.prompts = prompts
        self._noisy_users: set[tuple[str, str]] = set()  # (server, nick)

    def handle_optin(self, server: str, nick: str) -> str:
        """Handle .optin command."""
        from terra_ai.database import UserStore
        users = UserStore(self.db)
        users.opt_in(server, nick)
        return "You are now opted in. TerraAI will respond to you."

    def handle_optout(self, server: str, nick: str, args: str = "",
                      admin_nicks: list[str] | None = None) -> str:
        """Handle .optout command.

        Without args: opts out the sender.
        With <nick> (admin only): opts out the specified nick.
        """
        from terra_ai.database import UserStore
        users = UserStore(self.db)

        target = nick
        if args:
            if admin_nicks and nick in admin_nicks:
                target = args.strip()
                users.opt_out(server, target)
                return f"{target} has been opted out."
            else:
                return "Only admins can opt out other users."

        users.opt_out(server, target)
        return "You are opted out. Your history has been forgotten."

    def handle_noisy(self, server: str, nick: str) -> str:
        """Handle .noisy command — toggle verbose status notices."""
        key = (server, nick)
        if key in self._noisy_users:
            self._noisy_users.discard(key)
            return "Noisy mode OFF."
        self._noisy_users.add(key)
        return "Noisy mode ON."

    def is_noisy(self, server: str, nick: str) -> bool:
        """Check if user has noisy mode enabled."""
        return (server, nick) in self._noisy_users

    def handle_setlocation(self, server: str, channel: str, nick: str,
                           args: str) -> str | None:
        """Handle .setlocation <city, state> command.

        Hybrid: stores as custom prompt (if args provided), then returns
        None so the caller forwards the message to AI. The AI responds
        naturally; we do NOT inject a "Your location is set to..." confirmation.
        """
        location = args.strip()
        if location:
            # Store as custom prompt so future AI calls include this context
            self.prompts.add_prompt(server, ".setlocation", location, nick)

        # Return None — let the caller forward to AI for the actual response
        return None

    def handle_ai(self) -> str:
        """Handle .ai command — just return usage note."""
        return "Usage: .ai <prompt>"

    def handle_effort(self, args: str) -> str:
        """Handle .effort [level] command."""
        level = args.strip().lower()
        if not level:
            return f"Effort level: {self.prompts.effort}"

        if self.prompts.set_effort(level):
            return f"Effort level: {level}"
        return f"Invalid effort level. Choose from: low, medium, high, xhigh, max"
