from __future__ import annotations

import asyncio
import os
import platform
import shutil
from pathlib import Path
import psutil
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema, TEXT, PATH


def register(registry, settings, scope):
    apps = {}
    for key, argv in settings.apps.items():
        if not argv or not Path(argv[0]).is_absolute() or not Path(argv[0]).is_file():
            continue
        if Path(argv[0]).suffix.lower() in {".bat", ".cmd", ".ps1", ".sh"}:
            continue
        apps[key] = tuple(argv)

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

    async def open_target(args):
        target_path = scope.resolve(args["target"])
        if not target_path.exists():
            return ToolResult.error("TARGET_NOT_FOUND", message=f"Target path not found: {target_path}")

        application = args.get("application", "default").lower()
        import subprocess

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
                "LOCALAPPDATA",
                "APPDATA",
                "PROGRAMFILES",
            }
        }

        cmd = []
        if application in ("vscode", "code"):
            code_bin = shutil.which("code.cmd") or shutil.which("code")
            if not code_bin:
                candidates = [
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "bin" / "code.cmd",
                    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code" / "Code.exe",
                    Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Microsoft VS Code" / "bin" / "code.cmd",
                    Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")) / "Microsoft VS Code" / "Code.exe",
                ]
                for c in candidates:
                    if c.is_file():
                        code_bin = str(c)
                        break
            if not code_bin:
                return ToolResult.error(
                    "VSCODE_NOT_FOUND",
                    message="VS Code executable ('code') not found in PATH or standard install directories",
                )
            cmd = [code_bin, str(target_path)]

        elif application == "explorer":
            explorer_bin = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "explorer.exe")
            cmd = [explorer_bin, str(target_path)]

        elif application == "notepad":
            notepad_bin = os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "notepad.exe")
            cmd = [notepad_bin, str(target_path)]

        elif application == "default":
            if platform.system() == "Windows":
                try:
                    os.startfile(str(target_path))
                    return ToolResult.ok(
                        target=str(target_path),
                        application="default_os_handler",
                        launched=True,
                    )
                except Exception as e:
                    return ToolResult.error("LAUNCH_FAILED", message=str(e))
            elif platform.system() == "Darwin":
                cmd = ["open", str(target_path)]
            else:
                cmd = ["xdg-open", str(target_path)]

        if cmd:
            try:
                proc = psutil.Popen(
                    cmd,
                    shell=False,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                )
                await asyncio.sleep(0.15)
                return ToolResult.ok(
                    target=str(target_path),
                    application=application,
                    pid=proc.pid,
                    launched=True,
                )
            except Exception as e:
                return ToolResult.error("LAUNCH_FAILED", message=str(e))

        return ToolResult.error("APPLICATION_UNSUPPORTED", message=f"Application {application} is not supported")

    registry.register(
        ToolSpec(
            tool_id="app.open_target",
            domain="extra",
            module=__name__,
            description="Open a file or folder in a specified application (vscode, explorer, notepad, or default)",
            input_schema=schema(
                {"target": PATH, "application": {"type": "string", "enum": ["vscode", "code", "explorer", "notepad", "default"]}},
                ["target"],
            ),
            risk=Risk.R1,
            effect="local_write",
            rollback="no automatic rollback",
        ),
        open_target,
    )
