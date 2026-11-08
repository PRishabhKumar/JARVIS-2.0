from __future__ import annotations

import asyncio
import os
from pathlib import Path


class CommandBroker:
    """No model-authored argv, shell, executable names, install strings or script bodies."""

    def __init__(self, profiles=None):
        self.profiles = profiles or {}

    async def run(self, profile_id: str):
        argv = self.profiles.get(profile_id)
        if not argv:
            raise FileNotFoundError("command profile unavailable")
        if not Path(argv[0]).is_absolute():
            raise ValueError("profile executable must be resolved by trusted provider")
        env = {
            k: v
            for k, v in os.environ.items()
            if k in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "LANG", "USERPROFILE"}
        }
        env["LC_ALL"] = "C"
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=env,
        )
        data = bytearray()
        try:
            async with asyncio.timeout(8):
                while True:
                    chunk = await proc.stdout.read(4096)
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > 20000:
                        raise ValueError("bounded command output exceeded")
                code = await proc.wait()
            return code, data.decode("utf-8", errors="replace")
        finally:
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), 1)
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
