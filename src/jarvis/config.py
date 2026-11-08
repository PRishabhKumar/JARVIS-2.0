from __future__ import annotations

import json
from pathlib import Path
from pydantic import Field
from .contracts import StrictModel


class Settings(StrictModel):
    roots: list[str] = Field(default_factory=lambda: [str(Path.cwd())], min_length=1)
    model: str = "gemini-3.8-live"
    state_dir: str = Field(default_factory=lambda: str(Path.home() / ".jarvis"))
    apps: dict[str, list[str]] = Field(default_factory=dict)
    allow_mutations: bool = False
    confirmation_threshold: str = "R2"
    max_calls: int = Field(default=25, ge=1, le=100)

    @classmethod
    def load(cls, path: str | None = None):
        import os
        from .storage.credentials import _load_env_if_needed

        _load_env_if_needed()

        data: dict = {}
        if path:
            p = Path(path)
            if p.stat().st_size > 65536:
                raise ValueError("configuration too large")
            data = json.loads(p.read_text(encoding="utf-8"))

        if "roots" not in data and os.environ.get("JARVIS_ROOTS"):
            raw_roots = os.environ["JARVIS_ROOTS"].strip("\"'")
            valid_roots = [
                r.strip()
                for r in raw_roots.replace(";", ",").split(",")
                if r.strip() and Path(r.strip()).is_dir()
            ]
            if valid_roots:
                data["roots"] = valid_roots
        if "model" not in data and os.environ.get("JARVIS_MODEL"):
            data["model"] = os.environ["JARVIS_MODEL"].strip("\"'")
        if "state_dir" not in data and os.environ.get("JARVIS_STATE_DIR"):
            data["state_dir"] = os.environ["JARVIS_STATE_DIR"].strip("\"'")
        if "allow_mutations" not in data and os.environ.get("JARVIS_ALLOW_MUTATIONS"):
            data["allow_mutations"] = os.environ["JARVIS_ALLOW_MUTATIONS"].strip().lower() in ("true", "1", "yes")
        if "confirmation_threshold" not in data and os.environ.get("JARVIS_CONFIRMATION_THRESHOLD"):
            raw_t = os.environ["JARVIS_CONFIRMATION_THRESHOLD"].strip().upper()
            if raw_t in ("R0", "R1", "R2", "R3"):
                data["confirmation_threshold"] = raw_t
        if "max_calls" not in data and os.environ.get("JARVIS_MAX_CALLS"):
            try:
                data["max_calls"] = int(os.environ["JARVIS_MAX_CALLS"])
            except ValueError:
                pass
        if "apps" not in data and os.environ.get("JARVIS_APPS_CONFIG"):
            raw_apps = os.environ["JARVIS_APPS_CONFIG"].strip()
            if (raw_apps.startswith("'") and raw_apps.endswith("'")) or (
                raw_apps.startswith('"') and raw_apps.endswith('"')
            ):
                raw_apps = raw_apps[1:-1]
            try:
                data["apps"] = json.loads(raw_apps)
            except Exception:
                try:
                    import re

                    fixed = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", raw_apps)
                    data["apps"] = json.loads(fixed)
                except Exception:
                    pass

        return cls.model_validate(data) if data else cls()


class PathScope:
    """Resolved read scope. Mutations are limited to dedicated providers; no generic file write."""

    SECRET_NAMES = {
        ".env",
        ".ssh",
        ".aws",
        ".azure",
        ".gnupg",
        ".netrc",
        ".git-credentials",
        "credentials",
        "credentials.json",
        "secrets.json",
        "id_rsa",
        "id_ed25519",
    }

    def __init__(self, roots: list[str], private_paths: list[str] | None = None):
        self.roots = tuple(Path(r).expanduser().resolve(strict=True) for r in roots)
        if any(not r.is_dir() for r in self.roots):
            raise ValueError("roots must be existing directories")
        self.private = tuple(Path(p).expanduser().resolve() for p in (private_paths or []))

    def resolve(self, value: str, *, exists=True) -> Path:
        raw = Path(value).expanduser()
        if not raw.is_absolute():
            raw = self.roots[0] / raw
        resolved = raw.resolve(strict=exists)
        if not any(resolved.is_relative_to(r) for r in self.roots):
            raise PermissionError("path outside allowed roots")
        if any(resolved == p or resolved.is_relative_to(p) for p in self.private):
            raise PermissionError("application private state is excluded")
        for part in (*raw.parts, *resolved.parts):
            lower = part.lower()
            if (
                lower in self.SECRET_NAMES
                or lower.startswith(".env.")
                or lower.endswith((".pem", ".key", ".pfx"))
            ):
                raise PermissionError("credential location excluded")
        return resolved
