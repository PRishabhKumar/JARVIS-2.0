from dataclasses import dataclass
from typing import AsyncIterator, Protocol
from jarvis.contracts import ToolCall, ToolResult


@dataclass(frozen=True)
class SessionEvent:
    kind: str
    text: str = ""
    call: ToolCall | None = None
    audio: bytes = b""


class ModelSession(Protocol):
    async def send_text(self, text: str) -> None: ...
    def receive_events(self) -> AsyncIterator[SessionEvent]: ...
    async def send_tool_result(self, call_id: str, name: str, result: ToolResult) -> None: ...
    async def close(self) -> None: ...
