from __future__ import annotations

import platform
import subprocess
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema, TEXT


def register(registry, settings, scope):
    async def lock_workstation(args):
        os_name = platform.system()
        if os_name == "Windows":
            import ctypes
            res = ctypes.windll.user32.LockWorkStation()
            if res:
                return ToolResult.ok(action="lock", note="Workstation locked successfully")
            return ToolResult.error("LOCK_FAILED", "failed")
        elif os_name == "Darwin":
            try:
                proc = subprocess.run(["pmset", "displaysleepnow"], timeout=3)
                if proc.returncode == 0:
                    return ToolResult.ok(action="lock", note="macOS display sleep/lock activated")
            except Exception:
                pass
            return ToolResult.error("LOCK_FAILED", "failed")
        elif os_name == "Linux":
            for cmd in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"]):
                try:
                    proc = subprocess.run(cmd, timeout=3)
                    if proc.returncode == 0:
                        return ToolResult.ok(action="lock", note="Linux session locked")
                except Exception:
                    continue
            return ToolResult.error("LOCK_FAILED", "failed")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    async def schedule_restart(args):
        delay = args.get("delay_seconds", 60)
        message = args.get("message", "JARVIS scheduled system restart")
        os_name = platform.system()

        if os_name == "Windows":
            try:
                proc = subprocess.run(
                    ["shutdown.exe", "/r", "/t", str(delay), "/c", message],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    return ToolResult.ok(
                        action="restart",
                        delay_seconds=delay,
                        message=message,
                        cancel_hint="Call power.cancel_shutdown to abort this restart",
                    )
                return ToolResult.error("RESTART_SCHEDULE_FAILED", "failed", output=proc.stderr.strip())
            except Exception as e:
                return ToolResult.error("RESTART_SCHEDULE_FAILED", "failed", message=str(e))
        return ToolResult.error("OS_UNSUPPORTED", "unsupported", message="Restart scheduling only configured for Windows in this build")

    async def schedule_shutdown(args):
        delay = args.get("delay_seconds", 60)
        message = args.get("message", "JARVIS scheduled system shutdown")
        os_name = platform.system()

        if os_name == "Windows":
            try:
                proc = subprocess.run(
                    ["shutdown.exe", "/s", "/t", str(delay), "/c", message],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if proc.returncode == 0:
                    return ToolResult.ok(
                        action="shutdown",
                        delay_seconds=delay,
                        message=message,
                        cancel_hint="Call power.cancel_shutdown to abort this shutdown",
                    )
                return ToolResult.error("SHUTDOWN_SCHEDULE_FAILED", "failed", output=proc.stderr.strip())
            except Exception as e:
                return ToolResult.error("SHUTDOWN_SCHEDULE_FAILED", "failed", message=str(e))
        return ToolResult.error("OS_UNSUPPORTED", "unsupported", message="Shutdown scheduling only configured for Windows in this build")

    async def cancel_shutdown(args):
        os_name = platform.system()
        if os_name == "Windows":
            try:
                proc = subprocess.run(["shutdown.exe", "/a"], capture_output=True, text=True, timeout=5)
                if proc.returncode == 0:
                    return ToolResult.ok(action="cancelled", note="Scheduled restart or shutdown aborted")
                return ToolResult.error("CANCEL_FAILED", "failed", message="No scheduled shutdown was pending or access denied")
            except Exception as e:
                return ToolResult.error("CANCEL_FAILED", "failed", message=str(e))
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    registry.register(
        ToolSpec(
            tool_id="power.lock",
            domain="addition_12",
            module=__name__,
            description="Lock user workstation session immediately",
            input_schema=schema(),
            risk=Risk.R1,
            effect="local_write",
            rollback="user unlocks workstation manually with credentials",
            verification="Confirm lock signal sent to OS",
        ),
        lock_workstation,
        preview=lambda a: "Lock the current workstation desktop",
    )

    registry.register(
        ToolSpec(
            tool_id="power.restart",
            domain="addition_12",
            module=__name__,
            description="Schedule a system restart with countdown delay and abort window",
            input_schema=schema(
                {"delay_seconds": {"type": "integer", "minimum": 0, "maximum": 3600}, "message": TEXT}
            ),
            risk=Risk.R3,
            effect="local_write",
            rollback="call power.cancel_shutdown within the delay countdown",
            verification="Confirm shutdown scheduler accepted restart command",
        ),
        schedule_restart,
        preview=lambda a: f"Restart system in {a.get('delay_seconds', 60)}s (abortable via power.cancel_shutdown)",
    )

    registry.register(
        ToolSpec(
            tool_id="power.shutdown",
            domain="addition_12",
            module=__name__,
            description="Schedule a system shutdown with countdown delay and abort window",
            input_schema=schema(
                {"delay_seconds": {"type": "integer", "minimum": 0, "maximum": 3600}, "message": TEXT}
            ),
            risk=Risk.R3,
            effect="local_write",
            rollback="call power.cancel_shutdown within the delay countdown",
            verification="Confirm shutdown scheduler accepted shutdown command",
        ),
        schedule_shutdown,
        preview=lambda a: f"Shut down system in {a.get('delay_seconds', 60)}s (abortable via power.cancel_shutdown)",
    )

    registry.register(
        ToolSpec(
            tool_id="power.cancel_shutdown",
            domain="addition_12",
            module=__name__,
            description="Cancel a previously scheduled system restart or shutdown",
            input_schema=schema(),
            risk=Risk.R1,
            effect="local_write",
            rollback="re-schedule shutdown if needed",
            verification="Confirm cancellation accepted by OS",
        ),
        cancel_shutdown,
        preview=lambda a: "Cancel pending scheduled system shutdown or restart",
    )

