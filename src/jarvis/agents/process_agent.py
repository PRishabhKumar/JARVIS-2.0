from __future__ import annotations

import asyncio
import os
import platform
import psutil
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema, LIMIT

PID = {"type": "integer", "minimum": 1, "maximum": 2147483647}


def identity(p):
    with p.oneshot():
        return {"pid": p.pid, "start_time": p.create_time(), "name": p.name(), "status": p.status()}


def register(registry, settings, scope):
    async def processes(args):
        items = []
        for p in psutil.process_iter():
            try:
                items.append(identity(p))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if len(items) >= args.get("limit", 50):
                break
            await asyncio.sleep(0)
        return ToolResult.ok(processes=items, truncated=len(items) >= args.get("limit", 50))

    async def zombies(args):
        if platform.system() == "Windows":
            return ToolResult.error("POSIX_ZOMBIE_STATE_NOT_EXPOSED", "unsupported")
        items = []
        for p in psutil.process_iter():
            try:
                if p.status() == psutil.STATUS_ZOMBIE:
                    items.append(identity(p))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if len(items) >= 100:
                break
            await asyncio.sleep(0)
        return ToolResult.ok(zombies=items, note="No parent or process is signalled")

    async def ancestry(args):
        try:
            p = psutil.Process(args["pid"])
            items = [identity(p)] + [identity(parent) for parent in p.parents()[:32]]
            return ToolResult.ok(ancestry=items)
        except psutil.NoSuchProcess:
            return ToolResult.error("PROCESS_NOT_FOUND")
        except psutil.AccessDenied:
            return ToolResult.error("PERMISSION_DENIED", "denied")

    async def priority(args):
        try:
            p = psutil.Process(args["pid"])
            out = identity(p)
            out["priority"] = int(p.nice())
            if hasattr(p, "cpu_affinity"):
                out["affinity"] = p.cpu_affinity()
            else:
                out["affinity_note"] = "OS API does not expose process affinity via psutil"
            return ToolResult.ok(process=out)
        except psutil.NoSuchProcess:
            return ToolResult.error("PROCESS_NOT_FOUND")
        except psutil.AccessDenied:
            return ToolResult.error("PERMISSION_DENIED", "denied")

    async def terminate_proc(args):
        pid = args["pid"]
        force = args.get("force", False)
        if pid in (0, 4) or pid == os.getpid():
            return ToolResult.error("PROTECTED_PROCESS", "denied", message=f"PID {pid} is protected")
        try:
            p = psutil.Process(pid)
            name = p.name()
            if force:
                p.kill()
            else:
                p.terminate()
            try:
                p.wait(timeout=1.5)
            except psutil.TimeoutExpired:
                if not force:
                    return ToolResult.error(
                        "TERMINATE_TIMEOUT", "uncertain", message="Process did not exit; retry with force=true"
                    )
            is_dead = not p.is_running()
            if is_dead:
                return ToolResult.ok(pid=pid, name=name, terminated=True, force=force)
            return ToolResult.error("TERMINATE_FAILED", "uncertain")
        except psutil.NoSuchProcess:
            return ToolResult.error("PROCESS_NOT_FOUND")
        except psutil.AccessDenied:
            return ToolResult.error("PERMISSION_DENIED", "denied")

    for name, domain, desc, params, fn in [
        (
            "process.list",
            "source_01",
            "List process identity/name/state; omit command lines and environment",
            schema({"limit": LIMIT}),
            processes,
        ),
        ("process.zombies", "source_02", "Inspect zombie state; never kill parents", schema(), zombies),
        (
            "process.priority",
            "source_03",
            "Inspect process priority and available affinity",
            schema({"pid": PID}, ["pid"]),
            priority,
        ),
        (
            "process.ancestry",
            "source_04",
            "Inspect process and parent identities",
            schema({"pid": PID}, ["pid"]),
            ancestry,
        ),
    ]:
        registry.register(
            ToolSpec(tool_id=name, domain=domain, module=__name__, description=desc, input_schema=params), fn
        )

    async def verify_terminated(args, result):
        if result.status != "succeeded":
            return True
        return not psutil.pid_exists(args["pid"])

    registry.register(
        ToolSpec(
            tool_id="process.terminate",
            domain="source_01",
            module=__name__,
            description="Terminate a process by PID with revalidation and confirmation",
            input_schema=schema({"pid": PID, "force": {"type": "boolean"}}, ["pid"]),
            risk=Risk.R2,
            effect="local_write",
            rollback="no automatic rollback; process termination cannot be undone",
            verification="Confirm process is no longer running",
        ),
        terminate_proc,
        preview=lambda a: f"Terminate process PID {a['pid']} (force={a.get('force', False)})",
        verifier=verify_terminated,
    )
