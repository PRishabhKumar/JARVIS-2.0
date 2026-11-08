from __future__ import annotations

import asyncio
import os
from pathlib import Path
import psutil
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema, TEXT


def register(registry, settings, scope):
    apps = {key: tuple(argv) for key, argv in settings.apps.items()}
    for argv in apps.values():
        if not argv or not Path(argv[0]).is_absolute() or not Path(argv[0]).is_file():
            raise ValueError("application executable must be an existing absolute path")
        if Path(argv[0]).suffix.lower() in {".bat", ".cmd", ".ps1", ".sh"}:
            raise ValueError("script launch profiles are not allowed")

    async def launch(args):
        argv = apps.get(args["app_id"])
        if not argv:
            return ToolResult.error("APP_NOT_ALLOWLISTED", "denied")
        env = {
            k: v
            for k, v in os.environ.items()
            if k
            in {
                "PATH",
                "HOME",
                "USERPROFILE",
                "SYSTEMROOT",
                "WINDIR",
                "TEMP",
                "TMP",
                "DISPLAY",
                "WAYLAND_DISPLAY",
                "XDG_RUNTIME_DIR",
                "DBUS_SESSION_BUS_ADDRESS",
            }
        }
        import subprocess

        proc = psutil.Popen(
            list(argv),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        await asyncio.sleep(0.15)
        if proc.poll() is not None:
            return ToolResult.error("LAUNCH_EXITED", "uncertain", exit_code=proc.returncode)
        created = proc.create_time()
        if not proc.is_running():
            return ToolResult.error("LAUNCH_NOT_VERIFIED", "uncertain")
        return ToolResult(
            status="succeeded",
            structured_data={
                "pid": proc.pid,
                "start_time": created,
                "app_id": args["app_id"],
                "verification": "process exists, not window focus",
            },
            changed_resources=["process:" + str(proc.pid)],
            verified=True,
        )

    async def verify(args, result):
        data = result.structured_data
        try:
            p = psutil.Process(data["pid"])
            return p.is_running() and p.create_time() == data["start_time"]
        except (psutil.Error, KeyError):
            return False

    async def list_apps(args):
        return ToolResult.ok(app_ids=sorted(apps), note="User-configured allowlist only")

    registry.register(
        ToolSpec(
            tool_id="app.list_allowlisted",
            domain="addition_01",
            module=__name__,
            description="List locally approved app IDs",
            input_schema=schema(),
        ),
        list_apps,
    )
    registry.register(
        ToolSpec(
            tool_id="app.launch_allowlisted",
            domain="addition_01",
            module=__name__,
            description="Launch a user-configured application ID, no model arguments",
            input_schema=schema({"app_id": TEXT}, ["app_id"]),
            risk=Risk.R1,
            effect="local_write",
            rollback="no automatic rollback; app may create state",
            verification="Re-read PID and process creation time",
        ),
        launch,
        verifier=verify,
        preview=lambda a: (
            f"Launch allowlisted app {a['app_id']!r}; configured profile {list(apps.get(a['app_id'], ()))!r}. No window-focus guarantee."
        ),
    )
