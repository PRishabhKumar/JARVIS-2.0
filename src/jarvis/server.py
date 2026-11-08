from __future__ import annotations

import hmac
import time
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import Field
from .contracts import StrictModel


class Heartbeat(StrictModel):
    device_id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    state: str = Field(pattern=r"^(local_only|active|stopped)$")


def create_app(token: str):
    if len(token) < 32:
        raise ValueError("server credential must be at least 32 characters")
    app = FastAPI(title="JARVIS coordination preview", docs_url=None, redoc_url=None, openapi_url=None)
    devices = {}

    async def authenticate(authorization: str = Header(default="")):
        if not hmac.compare_digest(authorization, "Bearer " + token):
            raise HTTPException(401, "Unauthorized")

    @app.get("/v1/health", dependencies=[Depends(authenticate)])
    async def health():
        return {
            "status": "ok",
            "version": "0.1.0",
            "remote_execution": False,
            "scope": "authenticated heartbeat only; task delegation not implemented",
        }

    @app.post("/v1/devices/heartbeat", dependencies=[Depends(authenticate)])
    async def heartbeat(message: Heartbeat):
        if message.device_id not in devices and len(devices) >= 8:
            raise HTTPException(429, "Device limit")
        devices[message.device_id] = {"state": message.state, "last_seen": time.monotonic()}
        return {"accepted": True}

    @app.get("/v1/devices", dependencies=[Depends(authenticate)])
    async def list_devices():
        return {
            "devices": [
                {
                    "device_id": name,
                    "state": v["state"],
                    "age_seconds": round(time.monotonic() - v["last_seen"]),
                }
                for name, v in devices.items()
            ]
        }

    return app


def serve(args):
    import uvicorn
    from .storage.credentials import get_secret

    if args.host not in {"127.0.0.1", "::1", "localhost"}:
        raise ValueError("non-loopback server binding disabled; use an authenticated TLS reverse proxy")
    uvicorn.run(
        create_app(get_secret("server")),
        host=args.host,
        port=args.port,
        access_log=False,
        log_level="warning",
    )
