from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Risk(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"


class ToolCall(StrictModel):
    call_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_.]+$")
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolResult(StrictModel):
    status: Literal["succeeded", "failed", "denied", "unsupported", "cancelled", "uncertain"]
    structured_data: dict[str, Any] = Field(default_factory=dict)
    changed_resources: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    error_code: str | None = None
    retryable: bool = False
    execution_uncertain: bool = False
    verified: bool = False
    trust_class: Literal["untrusted_content"] = "untrusted_content"

    @classmethod
    def ok(cls, **data):
        return cls(status="succeeded", structured_data=data, verified=True)

    @classmethod
    def error(cls, code, status="failed", **data):
        return cls(
            status=status, error_code=code, structured_data=data, execution_uncertain=status == "uncertain"
        )


class ToolSpec(StrictModel):
    tool_id: str
    version: str = "1.0"
    domain: str
    module: str
    description: str
    input_schema: dict[str, Any]
    risk: Risk = Risk.R0
    supported_os: tuple[str, ...] = ("Windows", "Darwin", "Linux")
    permission: str = "current user"
    timeout_seconds: float = 10.0
    output_limit: int = 24576
    effect: Literal["read", "local_write", "privileged"] = "read"
    rollback: str = "not applicable (read only)"
    verification: str = "provider observation and normalized result contract"
    audit_policy: str = "metadata only; no arguments, output, transcripts or audio"

    @property
    def schema_hash(self):
        return digest(self.model_dump(mode="json"))


class ExecutionContext(StrictModel):
    session_id: str
    maximum_effect: Literal["read", "local_write"] = "read"
    max_calls: int = Field(default=25, ge=1, le=100)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()
