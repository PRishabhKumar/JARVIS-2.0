from __future__ import annotations

import os
from pathlib import Path

ALLOWED = {"gemini", "server"}

ENV_MAPPING = {
    "gemini": ["GEMINI_API_KEY", "JARVIS_GEMINI_KEY"],
    "server": ["JARVIS_SERVER_TOKEN", "JARVIS_SERVER_KEY"],
}


def _load_env_if_needed():
    """Attempt to load .env from current directory or project root if not already loaded."""
    if getattr(_load_env_if_needed, "_loaded", False):
        return
    try:
        from dotenv import load_dotenv

        cwd = Path.cwd()
        for p in (cwd, cwd / "Code" / "jarvis", cwd.parent):
            env_file = p / ".env"
            if env_file.is_file():
                load_dotenv(env_file)
                break
    except ImportError:
        for p in (Path.cwd(), Path.cwd() / "Code" / "jarvis", Path.cwd().parent):
            env_file = p / ".env"
            if env_file.is_file():
                try:
                    for line in env_file.read_text(encoding="utf-8").splitlines():
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k not in os.environ and v:
                                os.environ[k] = v
                except Exception:
                    pass
                break
    _load_env_if_needed._loaded = True


def _backend():
    import keyring

    backend = keyring.get_keyring()
    name = type(backend).__module__.lower()
    # Fail closed: never fall back to plaintext/null/file/chained unknown storage.
    if not any(x in name for x in ("windows", "macos", "secretservice", "kwallet")):
        raise RuntimeError("secure OS keyring unavailable; unlock/configure the native keyring")
    return backend


def set_secret(name, secret):
    if name not in ALLOWED or not secret or len(secret) > 4096:
        raise ValueError("invalid credential")
    _backend().set_password("jarvis-command-agent", name, secret)


def get_secret(name):
    if name not in ALLOWED:
        raise ValueError("unknown credential reference")

    _load_env_if_needed()

    # 1. Check environment variables (.env or shell)
    for env_var in ENV_MAPPING.get(name, []):
        val = os.environ.get(env_var, "").strip()
        if val and not val.startswith("your_"):
            return val

    # 2. Check native OS keyring
    try:
        value = _backend().get_password("jarvis-command-agent", name)
        if value:
            return value
    except Exception:
        pass

    raise RuntimeError(
        f"credential missing for '{name}'. Set {ENV_MAPPING.get(name, [''])[0]} in .env or run: jarvis credentials set {name}"
    )


def delete_secret(name):
    if name not in ALLOWED:
        raise ValueError("unknown credential reference")
    _backend().delete_password("jarvis-command-agent", name)
