"""User commands for TerraAI."""

from terraai.database import Database
from terraai.prompts.manager import PromptManager


class UserCommands:
    """User-facing commands."""

    def __init__(self, db: Database, prompts: PromptManager):
        self.db = db
        self.prompts = prompts
        self._noisy_users: set[tuple[str, str]] = set()  # (server, nick)

    def handle_optin(self, server: str, nick: str) -> str:
        """Handle .optin command."""
        from terraai.database import UserStore
        users = UserStore(self.db)
        users.opt_in(server, nick)
        return "You are now opted in. TerraAI will respond to you."

    def handle_optout(self, server: str, nick: str) -> str:
        """Handle .optout command."""
        from terraai.database import UserStore
        users = UserStore(self.db)
        users.opt_out(server, nick)
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
