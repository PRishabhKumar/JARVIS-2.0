from __future__ import annotations

import platform
import shutil
from pathlib import Path
import psutil
from jarvis.contracts import ToolResult
from .broker import CommandBroker


async def services():
    os_name = platform.system()
    if os_name == "Windows":
        try:
            result = []
            for item in psutil.win_service_iter():
                result.append({"name": item.name(), "status": item.status()})
                if len(result) == 100:
                    break
            return ToolResult.ok(services=result, bounded=True, provider="Windows SCM/psutil")
        except psutil.AccessDenied:
            return ToolResult.error("PERMISSION_DENIED", "denied")
    if os_name == "Linux":
        exe = shutil.which("systemctl")
        if not exe or not Path("/run/systemd/system").exists():
            return ToolResult.error(
                "SYSTEMD_NOT_ACTIVE",
                "unsupported",
                reason="This provider requires systemd; other init providers are not yet implemented",
            )
        argv = [exe, "list-units", "--type=service", "--no-pager", "--no-legend", "--plain"]
    elif os_name == "Darwin":
        exe = shutil.which("launchctl")
        if not exe:
            return ToolResult.error("LAUNCHCTL_UNAVAILABLE", "unsupported")
        argv = [exe, "list"]
    else:
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")
    code, text = await CommandBroker({"services": argv}).run("services")
    if code:
        return ToolResult.error("SERVICE_PROVIDER_FAILED")
    return ToolResult.ok(service_rows=text.splitlines()[:100], provider=os_name, bounded=True)
