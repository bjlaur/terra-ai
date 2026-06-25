"""Admin commands for TerraAI."""

from terraai.database import Database
from terraai.prompts.manager import PromptManager


class AdminCommands:
    """Management commands that never reach the AI."""

    def __init__(self, db: Database, prompts: PromptManager):
        self.db = db
        self.prompts = prompts

    def handle_listprompts(self, server: str, nick: str) -> str:
        """Handle .listprompts command."""
        prompts = self.prompts.list_prompts(server)
        if not prompts:
            return "No prompts configured."

        lines = []
        for i, p in enumerate(prompts, 1):
            lines.append(f"#{i} {p['trigger']}: {p['response']}")
        return "\n".join(lines)

    def handle_rmprompt(self, server: str, nick: str, args: str) -> str:
        """Handle .rmprompt <number> command."""
        try:
            index = int(args.strip()) - 1  # 1-indexed to 0-indexed
        except (ValueError, AttributeError):
            return "Usage: .rmprompt <number>"

        if self.prompts.remove_prompt_by_index(server, index):
            prompts = self.prompts.list_prompts(server)
            if 0 <= index < len(prompts):
                return f"Removed #{index + 1} ({prompts[index]['trigger']})"
            return f"Removed #{index + 1}"
        return "No such prompt."

    def handle_addprompt(self, server: str, nick: str, args: str) -> str:
        """Handle .addprompt <trigger> <text> command."""
        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: .addprompt <trigger> <text>"

        trigger, response = parts
        if self.prompts.add_prompt(server, trigger, response, nick):
            return f"Added {trigger}."
        return "Trigger already exists."

    def handle_compact(self, server: str, channel: str, nick: str) -> str:
        """Handle .compact command."""
        from terraai.context.manager import ContextManager
        context = ContextManager(self.db, self.prompts)
        new_session = context.compact(server, channel)
        return f"Context compacted. New session: {new_session[:8]}..."

    def handle_stats(self, server: str, channel: str) -> str:
        """Handle .stats command."""
        rows = self.db.conn.execute(
            """SELECT provider, model, COUNT(*) as calls,
                      AVG(processing_time_ms) as avg_ms,
                      AVG(total_tokens) as avg_tokens
               FROM performance_stats
               WHERE server = ? AND channel = ?
               GROUP BY provider, model""",
            (server, channel)
        ).fetchall()

        if not rows:
            return "No stats yet."

        lines = ["Performance Stats:"]
        for row in rows:
            lines.append(
                f"  {row['provider']}/{row['model']}: "
                f"{row['calls']} calls, "
                f"avg {row['avg_ms']:.0f}ms, "
                f"avg {row['avg_tokens']:.0f} tokens"
            )
        return "\n".join(lines)

    def handle_help(self) -> str:
        """Handle .help command."""
        return (
            "Commands: .optin, .optout, .noisy, .ai <prompt>, "
            ".addprompt <trigger> <text>, .rmprompt <number>, .listprompts, "
            ".setlocation <city, state>, .compact, .stats, .help, .effort [level]"
        )
