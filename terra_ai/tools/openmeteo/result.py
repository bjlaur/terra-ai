"""Shared tool result format for TerraAI tools.

Every client-side tool returns one of these, serialized to JSON before
being sent back to the model as a tool result message.
"""

from dataclasses import dataclass, asdict, field
from typing import Any


@dataclass
class ToolResult:
    """One normalized tool result.

    Sent back to the model as a tool message (role=tool). The model uses
    `data` + `summary_hint` to compose the final IRC answer.
    """

    ok: bool
    tool: str
    source: str
    data: dict[str, Any] | None = None
    summary_hint: str | None = None
    error: str | None = None
    debug: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
