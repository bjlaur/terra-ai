"""User commands for TerraAI."""

from terra_ai.database import Database
from terra_ai.prompts.manager import PromptManager
class UserCommands:
    """User-facing commands."""

    def __init__(self, db: Database, prompts: PromptManager):
        self.db = db
        self.prompts = prompts

    def _users(self) -> "UserStore":
        from terra_ai.database import UserStore
        return UserStore(self.db)

    def handle_optin(self, server: str, nick: str) -> str:
        """Handle .optin command."""
        from terra_ai.database import UserStore
        users = UserStore(self.db)
        users.opt_in(server, nick)
        return "You are now opted in. TerraAI will respond to you."

    def handle_optout(self, server: str, nick: str, args: str = "") -> str:
        """Handle .optout command.

        Without args: opts out the sender.
        With <nick>: opts out the specified nick (admin only — check in plugin handler).
        """
        from terra_ai.database import UserStore
        users = UserStore(self.db)

        target = nick
        if args:
            target = args.strip()
            users.opt_out(server, target)
            return f"{target} has been opted out."

        users.opt_out(server, target)
        return "You are opted out. Your history has been forgotten."

    def handle_noisy(self, server: str, nick: str) -> str:
        """Handle .noisy command — toggle verbose status notices."""
        users = self._users()
        enabled = users.toggle_noisy(server, nick)
        return f"Noisy mode {'ON' if enabled else 'OFF'}."

    def is_noisy(self, server: str, nick: str) -> bool:
        """Check if user has noisy mode enabled."""
        return self._users().is_noisy(server, nick)

    def handle_effort(self, args: str) -> str:
        """Handle .effort [level] command."""
        level = args.strip().lower()
        if not level:
            return f"Effort level: {self.prompts.effort}"

        if self.prompts.set_effort(level):
            return f"Effort level: {level}"
        return f"Invalid effort level. Choose from: low, medium, high, xhigh, max"
