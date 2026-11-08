from __future__ import annotations

import locale
import platform
from datetime import datetime
import psutil
from jarvis.contracts import ToolSpec, ToolResult
from jarvis.registry import schema


def register(registry, settings, scope):
    async def get_time(args):
        current = datetime.now().astimezone()
        return ToolResult.ok(iso=current.isoformat(), timezone=str(current.tzinfo))

    async def hardware(args):
        return ToolResult.ok(
            os=platform.system(),
            release=platform.release(),
            machine=platform.machine(),
            logical_cpus=psutil.cpu_count(),
            physical_cpus=psutil.cpu_count(logical=False),
            ram_bytes=psutil.virtual_memory().total,
        )

    async def memory(args):
        return ToolResult.ok(
            memory=psutil.virtual_memory()._asdict(),
            swap=psutil.swap_memory()._asdict(),
            note="Diagnostic only; caches are not cleared",
        )

    async def battery(args):
        b = psutil.sensors_battery()
        if b is None:
            return ToolResult.error("BATTERY_SENSOR_UNAVAILABLE", "unsupported")
        return ToolResult.ok(percent=b.percent, plugged=b.power_plugged, seconds_left=b.secsleft)

    async def clock_locale(args):
        return ToolResult.ok(
            time=datetime.now().astimezone().isoformat(),
            locale=locale.getlocale(),
            note="Read-only; no clock change",
        )

    for name, domain, description, fn in [
        ("system.get_time", "extra", "Read the local clock and time zone", get_time),
        (
            "hardware.inventory",
            "source_33",
            "Read CPU, OS and memory inventory (no device serials)",
            hardware,
        ),
        ("memory.diagnostics", "source_29", "Read memory/swap usage; never clear caches", memory),
        ("health.battery", "addition_11", "Read battery sensor if the OS exposes one", battery),
        ("clock.inspect", "addition_19", "Inspect local clock, time zone and locale", clock_locale),
    ]:
        registry.register(
            ToolSpec(
                tool_id=name, domain=domain, module=__name__, description=description, input_schema=schema()
            ),
            fn,
        )
