from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable
from jsonschema import Draft202012Validator
from .contracts import ToolSpec, ToolResult

Executor = Callable[[dict], Awaitable[ToolResult]]


@dataclass(frozen=True)
class RegisteredTool:
    spec: ToolSpec
    executor: Executor
    preview: Callable[[dict], str]
    verifier: Callable[[dict, ToolResult], Awaitable[bool]]


async def contract_verify(args, result):
    # Read observations are evidence, not proof of an external mutation.
    return result.status == "succeeded" and result.verified


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec, executor, *, preview=None, verifier=contract_verify):
        if spec.tool_id in self._tools:
            raise ValueError("duplicate tool ID")
        if not inspect.iscoroutinefunction(executor):
            raise TypeError("executor must be async")
        Draft202012Validator.check_schema(spec.input_schema)
        self._tools[spec.tool_id] = RegisteredTool(
            spec, executor, preview or (lambda args: f"{spec.tool_id}: {args}"), verifier
        )

    def get(self, name):
        return self._tools.get(name)

    def all(self):
        return list(self._tools.values())

    def validate(self, tool, arguments):
        Draft202012Validator(tool.spec.input_schema).validate(arguments)

    def declarations(self, *, writes=False):
        # Vendor-neutral canonical IDs. SDK name encoding belongs to the adapter.
        return [t.spec for t in self.all() if writes or t.spec.effect == "read"]


def schema(properties=None, required=()):
    return {
        "type": "object",
        "properties": properties or {},
        "required": list(required),
        "additionalProperties": False,
    }


TEXT = {"type": "string", "minLength": 1, "maxLength": 1024}
PATH = {"type": "string", "minLength": 1, "maxLength": 4096}
LIMIT = {"type": "integer", "minimum": 1, "maximum": 100}
