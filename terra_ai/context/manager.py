"""Context manager for TerraAI."""

import uuid

from terra_ai.database import Database, HistoryStore
from terra_ai.prompts.manager import PromptManager


class ContextManager:
    """Manages conversation context assembly and history."""

    def __init__(self, db: Database, prompt_manager: PromptManager):
        self.db = db
        self.history = HistoryStore(db)
        self.prompts = prompt_manager

    def compose_context(self, server: str, channel: str,
                        user_message: str, nick: str) -> list[dict]:
        """Compose the full context for an AI call.

        Returns a list of message dicts ready for the AI provider.
        """
        messages = []

        # 1. System prompt: one `system` message per rule from SYSTEM_PROMPTS.
        seed = self.prompts.get_context_seed(server, channel)
        messages.extend(seed)

        # 3. Custom prompts as context
        custom_prompts = self.prompts.list_prompts(server)
        if custom_prompts:
            prompt_lines = []
            for p in custom_prompts:
                prompt_lines.append(f"{p['trigger']} -> {p['response']}")
            messages.append({
                "role": "system",
                "content": f"Registered prompts:\n" + "\n".join(prompt_lines),
                "source": "system",
            })

        # 4. Conversation history
        history = self.history.recent(server, channel)
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        # 5. Current user message — already <nick>-prefixed by the caller
        # (single chokepoint in TerraAI.handle_ai_message), so store as-is.
        messages.append({"role": "user", "content": user_message})

        return messages

    def save_exchange(self, server: str, channel: str, nick: str,
                      user_message: str, assistant_response: str,
                      source: str = "user"):
        """Save a user/assistant exchange to history.

        `user_message` is expected to already be <nick>-prefixed by the
        caller (single chokepoint in TerraAI.handle_ai_message); stored
        verbatim so replayed history matches what the AI saw at prompt time.
        """
        session_id = self._get_or_create_session(server, channel)
        self.history.append(server, channel, nick, "user", user_message, source=source)
        self.history.append(server, channel, nick, "assistant", assistant_response, source=source)

    def save_system_message(self, server: str, channel: str,
                            nick: str, content: str):
        """Save a system message to history (e.g. .setlocation)."""
        session_id = self._get_or_create_session(server, channel)
        self.history.append(server, channel, nick, "user", content, source="system")

    def compact(self, server: str, channel: str) -> str:
        """Mark current session as compacted and create a new one.

        Returns the new session_id.
        """
        new_session_id = str(uuid.uuid4())
        # Get current session
        row = self.db.conn.execute(
            "SELECT active_session_id FROM sessions WHERE server = ? AND channel = ?",
            (server, channel)
        ).fetchone()

        if row:
            old_session_id = row["active_session_id"]
            # Count rows before
            count_before = self.db.conn.execute(
                "SELECT COUNT(*) FROM conversation_history WHERE server = ? AND channel = ? AND session_id = ?",
                (server, channel, old_session_id)
            ).fetchone()[0]

            # Log compaction
            self.db.conn.execute(
                """INSERT INTO compactions (server, channel, old_session_id, new_session_id, rows_before, rows_after)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (server, channel, old_session_id, new_session_id, count_before, 0)
            )

            # Update session
            self.db.conn.execute(
                "UPDATE sessions SET active_session_id = ?, updated_at = datetime('now') WHERE server = ? AND channel = ?",
                (new_session_id, server, channel)
            )

            self.db.conn.commit()

        return new_session_id

    def _get_or_create_session(self, server: str, channel: str) -> str:
        """Get the active session ID or create a new one."""
        row = self.db.conn.execute(
            "SELECT active_session_id FROM sessions WHERE server = ? AND channel = ?",
            (server, channel)
        ).fetchone()
        if row:
            return row["active_session_id"]
        session_id = str(uuid.uuid4())
        self.db.conn.execute(
            "INSERT INTO sessions (server, channel, active_session_id) VALUES (?, ?, ?)",
            (server, channel, session_id)
        )
        self.db.conn.commit()
        return session_id
