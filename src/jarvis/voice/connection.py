from __future__ import annotations

import asyncio
from urllib.parse import urlparse


async def heartbeat_loop(url, credential, state, device_id):
    """HTTPS only, no redirects, no transcripts/audio/tools. Reconnects with a capped backoff."""
    import httpx

    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("satellite server must use a credential-free HTTPS URL")
    delay = 1
    async with httpx.AsyncClient(timeout=5, follow_redirects=False, trust_env=False) as client:
        while True:
            try:
                response = await client.post(
                    url.rstrip("/") + "/v1/devices/heartbeat",
                    headers={"Authorization": "Bearer " + credential},
                    json={"device_id": device_id, "state": state()},
                )
                if response.status_code in (401, 403):
                    print("[server authorization failed] Heartbeat disabled; local control is unaffected.")
                    return
                response.raise_for_status()
                delay = 1
                await asyncio.sleep(15)
            except (httpx.HTTPError, OSError):
                print("[server unavailable] Local wake/control remains local; retrying heartbeat only.")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
