from __future__ import annotations

import asyncio
import copy
import json
import time
from dataclasses import dataclass
from typing import Awaitable, Callable
from .contracts import ExecutionContext, Risk, ToolCall, digest


@dataclass(frozen=True)
class ApprovalRequest:
    binding: str
    tool_id: str
    risk: str
    preview: str
    expires_at: float
    phrase: str


Confirmation = Callable[[ApprovalRequest], Awaitable[bool]]


async def deny_confirmation(request):
    return False


RISK_RANKS = {
    Risk.R0: 0,
    Risk.R1: 1,
    Risk.R2: 2,
    Risk.R3: 3,
}


class PolicyGate:
    def __init__(self, confirm: Confirmation = deny_confirmation, threshold: Risk = Risk.R1):
        self.confirm = confirm
        self.threshold = threshold
        self.stopped = False
        self.epoch = 0

    def stop(self):
        self.stopped = True
        self.epoch += 1

    def reset(self):
        self.stopped = False

    @staticmethod
    def binding(tool, call: ToolCall, context: ExecutionContext):
        return digest(
            {
                "call": call.model_dump(),
                "schema": tool.spec.schema_hash,
                "session": context.session_id,
                "effect_ceiling": context.maximum_effect,
            }
        )

    async def authorize(self, tool, call, context):
        if self.stopped:
            return False, "TASK_CANCELLED"
        if tool.spec.effect != "read" and context.maximum_effect == "read":
            return False, "EFFECT_CEILING"
        if tool.spec.risk == Risk.R0 and tool.spec.effect == "read":
            return True, "allow"
        tool_rank = RISK_RANKS.get(tool.spec.risk, 1)
        threshold_rank = RISK_RANKS.get(self.threshold, 1)
        if tool_rank < threshold_rank:
            return True, "allow"
        binding = self.binding(tool, call, context)
        epoch = self.epoch
        frozen_args = copy.deepcopy(call.arguments)
        req = ApprovalRequest(
            binding,
            tool.spec.tool_id,
            tool.spec.risk.value,
            tool.preview(frozen_args),
            time.monotonic() + 60,
            "APPROVE " + binding[:12] if tool.spec.risk == Risk.R3 else "yes",
        )
        try:
            approved = await asyncio.wait_for(self.confirm(req), timeout=60)
        except TimeoutError:
            return False, "APPROVAL_EXPIRED"
        if self.stopped or epoch != self.epoch:
            return False, "TASK_CANCELLED"
        if time.monotonic() >= req.expires_at:
            return False, "APPROVAL_EXPIRED"
        if binding != self.binding(tool, call, context):
            return False, "APPROVAL_SCOPE_MISMATCH"
        # Never accept truthy model text as approval.
        if approved is not True:
            return False, "APPROVAL_DENIED"
        # Exercise canonical JSON validation before passing across the boundary.
        json.dumps(frozen_args, allow_nan=False)
        return True, "confirmed"
