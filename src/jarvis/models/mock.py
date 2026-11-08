from __future__ import annotations

import asyncio
from uuid import uuid4
from .base import SessionEvent
from jarvis.contracts import ToolCall

# Explicit demo fixtures, not a natural-language intent router. No substring routing.
FIXTURES = {
    "What time is it?": ("system.get_time", {}),
    "List this folder": ("filesystem.list_directory", {"path": "."}),
    "Show processes": ("process.list", {"limit": 5}),
    "Show hardware": ("hardware.inventory", {}),
}


class MockSession:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.results = []

    async def send_text(self, text):
        item = FIXTURES.get(text)
        if not item:
            await self.queue.put(SessionEvent("text", "Mock mode uses explicit fixtures only. Try 'What time is it?', 'List this folder', 'Show processes', 'Show hardware', or /call tool.id {JSON}. Use --mode live for free-form intent."))
            await self.queue.put(SessionEvent("done"))
            return
        await self.queue.put(SessionEvent("call", call=ToolCall(call_id=uuid4().hex, name=item[0], arguments=item[1])))

    async def send_tool_result(self, call_id, name, result):
        self.results.append((call_id, name, result))
        if result.status == "succeeded" and name == "system.get_time":
            text = "The local time is " + result.structured_data["iso"]
        else:
            import json
            text = json.dumps(result.model_dump(), indent=2)
        await self.queue.put(SessionEvent("text", text))
        await self.queue.put(SessionEvent("done"))

    async def receive_events(self):
        while True:
            item = await self.queue.get()
            if item.kind == "done":
                return
            yield item

    async def close(self):
        pass
