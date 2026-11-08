from __future__ import annotations

import psutil
from jarvis.contracts import ToolSpec, ToolResult
from jarvis.registry import schema, LIMIT


def endpoint(addr):
    return {"ip": addr.ip, "port": addr.port} if addr else None


def register(registry, settings, scope):
    async def connections(args):
        try:
            items = psutil.net_connections(kind="inet")
        except psutil.AccessDenied:
            return ToolResult.error("NETWORK_INSPECTION_PERMISSION_REQUIRED", "denied")
        limit = args.get("limit", 50)
        result = [
            {"pid": c.pid, "status": c.status, "local": endpoint(c.laddr), "remote": endpoint(c.raddr)}
            for c in items[:limit]
        ]
        return ToolResult.ok(connections=result, truncated=len(items) > limit, geoip_enabled=False)

    async def ports(args):
        r = await connections(args)
        if r.status != "succeeded":
            return r
        return ToolResult.ok(
            listeners=[c for c in r.structured_data["connections"] if c["status"] == "LISTEN"], bounded=True
        )

    async def interfaces(args):
        addresses, status = psutil.net_if_addrs(), psutil.net_if_stats()
        return ToolResult.ok(
            interfaces=[
                {
                    "name": n,
                    "up": status[n].isup if n in status else None,
                    "mtu": status[n].mtu if n in status else None,
                    "addresses": [{"family": str(a.family), "address": a.address} for a in addresses[n]][:8],
                }
                for n in list(addresses)[:20]
            ]
        )

    async def diagnostics(args):
        return ToolResult.ok(
            counters=psutil.net_io_counters()._asdict(),
            interfaces={
                n: {"up": s.isup, "speed_mbps": s.speed} for n, s in list(psutil.net_if_stats().items())[:20]
            },
            note="Local status only; no remote probe, DNS query or network mutation",
        )

    for name, domain, description, fn, params in [
        (
            "network.connections",
            "source_22",
            "Read bounded connection metadata; GeoIP is disabled",
            connections,
            schema({"limit": LIMIT}),
        ),
        (
            "network.ports",
            "source_16",
            "Read sampled listening ports and process owners",
            ports,
            schema({"limit": LIMIT}),
        ),
        (
            "network.interfaces",
            "source_17",
            "Inspect network interfaces; cannot configure them",
            interfaces,
            schema(),
        ),
        (
            "network.diagnostics",
            "source_20",
            "Read local interface health/counters; no remote probe",
            diagnostics,
            schema(),
        ),
    ]:
        registry.register(
            ToolSpec(
                tool_id=name, domain=domain, module=__name__, description=description, input_schema=params
            ),
            fn,
        )
