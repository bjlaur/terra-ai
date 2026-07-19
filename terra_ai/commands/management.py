"""Management commands for TerraAI."""

from terra_ai.database import Database
from terra_ai.prompts.manager import PromptManager


class ManagementCommands:
    """Management commands that never reach the AI."""

    def __init__(self, db: Database, prompts: PromptManager, help_prefix: str = "-"):
        self.db = db
        self.prompts = prompts
        self.help_prefix = help_prefix

    def format_usage(self, command: str) -> str:
        """Format command usage with Sopel's configured display prefix."""
        return f"Usage: {self.help_prefix}{command}"

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
            return self.format_usage("rmprompt <number>")

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
            return self.format_usage("addprompt <trigger> <text>")

        trigger, response = parts
        if self.prompts.add_prompt(server, trigger, response, nick):
            return f"Added {trigger}."
        return "Trigger already exists."

    def handle_compact(self, server: str, channel: str, nick: str) -> str:
        """Handle .compact command."""
        from terra_ai.context.manager import ContextManager
        context = ContextManager(self.db, self.prompts)
        new_session = context.compact(server, channel)
        return f"Context compacted. New session: {new_session[:8]}..."

    def handle_clear(self, server: str, channel: str) -> str:
        """Handle .clear command — wipe conversation history and start fresh."""
        import uuid
        new_session_id = str(uuid.uuid4())
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE sessions SET active_session_id = ?, updated_at = datetime('now') "
                "WHERE server = ? AND channel = ?",
                (new_session_id, server, channel),
            )
        return f"Session cleared. New session: {new_session_id[:8]}..."

    def handle_stats(self, server: str, channel: str) -> str:
        """Handle .stats command."""
        rows = self.db.fetchall(
            """SELECT provider, model, COUNT(*) as calls,
                      AVG(processing_time_ms) as avg_ms,
                      AVG(total_tokens) as avg_tokens
               FROM performance_stats
               WHERE server = ? AND channel = ?
               GROUP BY provider, model""",
            (server, channel)
        )

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
        """Handle help command."""
        p = self.help_prefix
        return (
            f"Commands: {p}optin, {p}optout, {p}noisy, {p}ai <prompt>, "
            f"{p}addprompt <trigger> <text>, {p}rmprompt <number>, {p}listprompts, "
            f"{p}setlocation <city, state>, {p}compact, {p}clear, {p}stats, {p}help, {p}effort [level]"
        )
