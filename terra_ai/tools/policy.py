"""Server-wide administrative policy for local tools."""

from terra_ai.database import Database, ToolPolicyStore
from terra_ai.tools.schemas import LOCAL_TOOLS


class ToolPolicy:
    """Expose valid local tools and their server-wide enabled state."""

    def __init__(self, db: Database):
        self.store = ToolPolicyStore(db)

    @staticmethod
    def valid_names() -> set[str]:
        return {
            tool["function"]["name"]
            for tool in LOCAL_TOOLS
            if "function" in tool
        }

    def disable(self, server: str, tool_name: str) -> None:
        self.store.disable(server, tool_name)

    def enable(self, server: str, tool_name: str) -> None:
        self.store.enable(server, tool_name)

    def disabled_names(self, server: str) -> set[str]:
        return self.store.disabled_names(server)

    def statuses(self, server: str) -> list[tuple[str, bool]]:
        disabled = self.disabled_names(server)
        return [
            (name, name in disabled)
            for name in sorted(self.valid_names())
        ]
