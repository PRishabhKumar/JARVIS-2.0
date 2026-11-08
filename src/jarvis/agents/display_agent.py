from __future__ import annotations

import platform
import subprocess
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema


def _get_brightness_windows() -> tuple[int, bool] | None:
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                "Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness -ErrorAction SilentlyContinue | Select-Object -ExpandProperty CurrentBrightness",
            ],
            capture_output=True,
            text=True,
            timeout=4,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            val = int(proc.stdout.strip().splitlines()[0])
            return val, True
    except Exception:
        pass
    return None


def _set_brightness_windows(level: int) -> bool:
    clamped = max(0, min(100, level))
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"$inst = Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods -ErrorAction SilentlyContinue; if ($inst) {{ Invoke-CimMethod -InputObject $inst -MethodName WmiSetBrightness -Arguments @{{Timeout = [uint32]1; Brightness = [byte]{clamped}}} | Out-Null; exit 0 }} else {{ exit 1 }}",
            ],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _get_resolution_windows() -> dict | None:
    try:
        import ctypes
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        monitors = user32.GetSystemMetrics(80)  # SM_CMONITORS
        return {"width": w, "height": h, "monitors": max(1, monitors)}
    except Exception:
        return None


def register(registry, settings, scope):
    async def get_brightness(args):
        os_name = platform.system()
        if os_name == "Windows":
            res = _get_brightness_windows()
            if res:
                level, active = res
                return ToolResult.ok(brightness=level, active=active, provider="Windows WMI WmiMonitorBrightness")
            return ToolResult.error("BRIGHTNESS_UNAVAILABLE", "unsupported", message="Display does not support WMI software brightness control")
        elif os_name == "Darwin":
            try:
                proc = subprocess.run(["brightness", "-l"], capture_output=True, text=True, timeout=2)
                if proc.returncode == 0 and "brightness" in proc.stdout:
                    for line in proc.stdout.splitlines():
                        if "brightness" in line:
                            val = float(line.split()[-1])
                            return ToolResult.ok(brightness=int(val * 100), provider="macOS brightness CLI")
            except Exception:
                pass
            return ToolResult.error("BRIGHTNESS_UNAVAILABLE", "unsupported")
        elif os_name == "Linux":
            try:
                proc = subprocess.run(["brightnessctl", "g"], capture_output=True, text=True, timeout=2)
                proc_max = subprocess.run(["brightnessctl", "m"], capture_output=True, text=True, timeout=2)
                if proc.returncode == 0 and proc_max.returncode == 0:
                    cur = int(proc.stdout.strip())
                    mx = int(proc_max.stdout.strip())
                    pct = int(cur * 100 / mx) if mx > 0 else 0
                    return ToolResult.ok(brightness=pct, provider="Linux brightnessctl")
            except Exception:
                pass
            return ToolResult.error("BRIGHTNESS_UNAVAILABLE", "unsupported")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    async def set_brightness(args):
        level = args["level"]
        os_name = platform.system()
        if os_name == "Windows":
            ok = _set_brightness_windows(level)
            if ok:
                return ToolResult.ok(level=level, provider="Windows WMI WmiMonitorBrightnessMethods")
            return ToolResult.error("BRIGHTNESS_SET_FAILED", "failed", message="Could not set brightness on this display")
        elif os_name == "Darwin":
            try:
                proc = subprocess.run(["brightness", str(level / 100.0)], timeout=2)
                if proc.returncode == 0:
                    return ToolResult.ok(level=level, provider="macOS brightness CLI")
            except Exception:
                pass
            return ToolResult.error("BRIGHTNESS_SET_FAILED", "failed")
        elif os_name == "Linux":
            try:
                proc = subprocess.run(["brightnessctl", "s", f"{level}%"], timeout=2)
                if proc.returncode == 0:
                    return ToolResult.ok(level=level, provider="Linux brightnessctl")
            except Exception:
                pass
            return ToolResult.error("BRIGHTNESS_SET_FAILED", "failed")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    async def get_resolution(args):
        os_name = platform.system()
        if os_name == "Windows":
            info = _get_resolution_windows()
            if info:
                return ToolResult.ok(**info, provider="Windows User32")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    registry.register(
        ToolSpec(
            tool_id="display.get_brightness",
            domain="addition_04",
            module=__name__,
            description="Get primary display brightness percentage (0-100) and capability state",
            input_schema=schema(),
            risk=Risk.R0,
            effect="read",
        ),
        get_brightness,
        preview=lambda a: "Inspect current display brightness level",
    )

    registry.register(
        ToolSpec(
            tool_id="display.set_brightness",
            domain="addition_04",
            module=__name__,
            description="Set primary display brightness to a specified percentage (0 to 100)",
            input_schema=schema({"level": {"type": "integer", "minimum": 0, "maximum": 100}}, ["level"]),
            risk=Risk.R1,
            effect="local_write",
            rollback="restore previous brightness level",
            verification="Confirm brightness setting applied",
        ),
        set_brightness,
        preview=lambda a: f"Set display brightness to {a['level']}%",
    )

    registry.register(
        ToolSpec(
            tool_id="display.get_resolution",
            domain="addition_04",
            module=__name__,
            description="Inspect display resolution and monitor count",
            input_schema=schema(),
            risk=Risk.R0,
            effect="read",
        ),
        get_resolution,
        preview=lambda a: "Inspect display resolution and monitor count",
    )

