from __future__ import annotations

import asyncio
import copy
import platform
import time
from collections import OrderedDict
from jsonschema import ValidationError
from .contracts import ToolCall, ToolResult, ExecutionContext, canonical


class AgentCoordinator:
    """The only dispatch boundary. Prose and tool-result content never enter this API as calls."""

    def __init__(self, registry, gate, store, context: ExecutionContext):
        self.registry, self.gate, self.store, self.context = registry, gate, store, context
        self.calls = 0
        self.cache = OrderedDict()
        self.lock = asyncio.Lock()
        self.active: asyncio.Task | None = None
        self.pending_tasks = set()

    def reject(self, code, status="failed"):
        self.store.audit(self.context.session_id, None, None, "reject", code)
        return ToolResult.error(code, status)

    def stop(self):
        self.gate.stop()
        if self.active and not self.active.done():
            self.active.cancel()
        for task in tuple(self.pending_tasks):
            if task is not asyncio.current_task() and not task.done():
                task.cancel()

    async def dispatch(self, raw: dict | ToolCall):
        try:
            # Snapshot mutable nested arguments before any suspension.
            payload = raw.model_dump() if isinstance(raw, ToolCall) else copy.deepcopy(raw)
            if len(canonical(payload).encode()) > 16384:
                return self.reject("ARGUMENT_LIMIT")
            call = ToolCall.model_validate(payload)
        except (ValueError, TypeError, RecursionError):
            return self.reject("MODEL_OUTPUT_INVALID")
        task = asyncio.current_task()
        self.pending_tasks.add(task)
        try:
            async with self.lock:
                return await self._dispatch(call)
        finally:
            self.pending_tasks.discard(task)

    async def _dispatch(self, call):
        start = time.monotonic()
        tool = self.registry.get(call.name)
        if not tool:
            return self.reject("CAPABILITY_NOT_FOUND")
        try:
            self.registry.validate(tool, call.arguments)
        except ValidationError:
            return self.reject("SCHEMA_INVALID")
        if platform.system() not in tool.spec.supported_os:
            return ToolResult.error("OS_UNSUPPORTED", "unsupported")
        binding = self.gate.binding(tool, call, self.context)
        if call.call_id in self.cache:
            previous_binding, previous_result = self.cache[call.call_id]
            return previous_result if binding == previous_binding else ToolResult.error("CALL_ID_CONFLICT")
        if self.gate.stopped:
            return ToolResult.error("TASK_CANCELLED", "cancelled")
        if self.calls >= self.context.max_calls:
            return ToolResult.error("BUDGET_EXCEEDED")
        self.calls += 1
        previous = self.store.reserve(self.context.session_id, call.call_id, binding, call.name)
        if previous:
            return ToolResult.error(
                "CALL_ID_CONFLICT" if previous[0] != binding else "REPLAY_BLOCKED", "denied"
            )
        decision = "deny"
        try:
            allowed, decision = await self.gate.authorize(tool, call, self.context)
            if not allowed:
                result = ToolResult.error(decision, "denied")
            else:
                self.active = asyncio.create_task(tool.executor(copy.deepcopy(call.arguments)))
                try:
                    async with asyncio.timeout(tool.spec.timeout_seconds):
                        result = await self.active
                        if not isinstance(result, ToolResult):
                            result = ToolResult.error("PROVIDER_CONTRACT_INVALID")
                        elif result.status == "succeeded":
                            if not await tool.verifier(call.arguments, result):
                                result = ToolResult.error(
                                    "POSTCONDITION_FAILED",
                                    "uncertain",
                                    message="Provider success was not verified",
                                )
                        if len(canonical(result.model_dump()).encode()) > tool.spec.output_limit:
                            result = ToolResult.error(
                                "OUTPUT_LIMIT", "uncertain" if tool.spec.effect != "read" else "failed"
                            )
                except TimeoutError:
                    result = ToolResult.error(
                        "TOOL_TIMEOUT", "uncertain" if tool.spec.effect != "read" else "failed"
                    )
        except asyncio.CancelledError:
            result = ToolResult.error(
                "TASK_CANCELLED",
                "uncertain"
                if tool.spec.effect != "read" and decision in ("allow", "confirmed")
                else "cancelled",
            )
        except PermissionError:
            result = ToolResult.error("PERMISSION_DENIED", "denied")
        except FileNotFoundError:
            result = ToolResult.error("RESOURCE_NOT_FOUND")
        except (ValueError, TypeError, OSError):
            result = ToolResult.error("PROVIDER_FAILED")
        except Exception:
            # SDK/OS exception strings may contain paths, credentials or private output.
            result = ToolResult.error(
                "INTERNAL_ERROR",
                "uncertain"
                if tool.spec.effect != "read" and decision in ("allow", "confirmed")
                else "failed",
            )
        finally:
            self.active = None
        self.store.finish(self.context.session_id, call.call_id, result.status)
        self.store.audit(
            self.context.session_id,
            call.name,
            tool.spec.risk.value,
            decision,
            result.status,
            int((time.monotonic() - start) * 1000),
        )
        self.cache[call.call_id] = (binding, result)
        if len(self.cache) > 100:
            self.cache.popitem(last=False)
        return result

    async def run_turn(self, session, text, emit=print):
        """Mock/provider-neutral text turn. Live streaming uses the same dispatch boundary."""
        await session.send_text(text)
        async for event in session.receive_events():
            if event.kind == "call":
                result = await self.dispatch(event.call)
                await session.send_tool_result(event.call.call_id, event.call.name, result)
            elif event.kind == "text":
                emit(event.text)
