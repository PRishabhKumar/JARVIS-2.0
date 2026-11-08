from __future__ import annotations

import importlib.metadata
import os
import platform
import shutil
from pathlib import Path
import psutil
from jarvis.contracts import ToolSpec, ToolResult, Risk
from jarvis.registry import schema
from jarvis.providers.status import services


def register(registry, settings, scope):
    async def service_status(args):
        return await services()

    async def software(args):
        entries = []
        for dist in importlib.metadata.distributions():
            entries.append({"name": dist.metadata.get("Name", "unknown"), "version": dist.version})
            if len(entries) >= 100:
                break
        return ToolResult.ok(
            packages=entries, coverage="current Python environment only; not OS app inventory"
        )

    async def packages(args):
        names = {
            "Windows": ("winget", "choco"),
            "Darwin": ("brew", "port"),
            "Linux": ("apt", "dnf", "pacman", "zypper", "apk", "snap", "flatpak"),
        }
        return ToolResult.ok(
            detected=[name for name in names.get(platform.system(), ()) if shutil.which(name)],
            note="Detection only. No installation/update provider in this build",
        )

    async def sessions(args):
        return ToolResult.ok(
            sessions=[
                {"name": u.name, "terminal": u.terminal, "started": u.started} for u in psutil.users()[:50]
            ],
            note="Current sessions, not historical login audit",
        )

    async def environment(args):
        # Values may contain tokens; never return them, even when the variable name looks safe.
        return ToolResult.ok(
            names=sorted(os.environ)[:100],
            values_redacted=True,
            path_entries=len(os.environ.get("PATH", "").split(os.pathsep)),
        )

    async def linux_modules(args):
        p = Path("/proc/modules")
        if platform.system() != "Linux" or not p.is_file():
            return ToolResult.error("LINUX_MODULE_INTERFACE_UNAVAILABLE", "unsupported")
        rows = p.read_text()[:16000].splitlines()[:100]
        return ToolResult.ok(modules=[r.split()[:3] for r in rows], note="No module loaded/unloaded")

    async def linux_capabilities(args):
        p = Path("/proc/self/status")
        if platform.system() != "Linux" or not p.is_file():
            return ToolResult.error("LINUX_CAPABILITY_INTERFACE_UNAVAILABLE", "unsupported")
        fields = dict(line.split(":", 1) for line in p.read_text().splitlines() if line.startswith("Cap"))
        return ToolResult.ok(
            capabilities={k: v.strip() for k, v in fields.items()}, target="JARVIS process only"
        )

    async def ipc(args):
        if platform.system() != "Linux":
            return ToolResult.error("LINUX_SYSVIPC_INTERFACE_UNAVAILABLE", "unsupported")
        data = {}
        for kind in ("shm", "msg", "sem"):
            p = Path("/proc/sysvipc") / kind
            if p.is_file():
                with p.open() as f:
                    data[kind] = f.read(12000).splitlines()[:30]
        if not data:
            return ToolResult.error("SYSVIPC_NOT_EXPOSED", "unsupported")
        return ToolResult.ok(ipc=data, note="Inspection only; no IPC removal")

    for name, domain, desc, fn, risk in [
        (
            "services.status",
            "source_31",
            "Inspect Windows SCM, macOS launchctl or active Linux systemd",
            service_status,
            Risk.R0,
        ),
        (
            "software.python_inventory",
            "addition_08",
            "List Python packages only, not installed OS applications",
            software,
            Risk.R0,
        ),
        (
            "packages.detect",
            "addition_09",
            "Detect trusted package-manager availability; do not install",
            packages,
            Risk.R0,
        ),
        ("sessions.list", "addition_13", "Read current user sessions; requires consent", sessions, Risk.R1),
        (
            "environment.inspect",
            "addition_14",
            "List environment variable NAMES only; redact all values",
            environment,
            Risk.R0,
        ),
        (
            "drivers.linux_modules",
            "source_30",
            "Inspect Linux loaded modules; not driver mutation",
            linux_modules,
            Risk.R0,
        ),
        (
            "security.linux_capabilities",
            "source_27",
            "Inspect Linux capabilities of this process only",
            linux_capabilities,
            Risk.R0,
        ),
        ("ipc.inspect", "source_06", "Inspect exposed Linux SysV IPC tables without cleanup", ipc, Risk.R0),
    ]:
        registry.register(
            ToolSpec(
                tool_id=name,
                domain=domain,
                module=__name__,
                description=desc,
                input_schema=schema(),
                risk=risk,
            ),
            fn,
        )
