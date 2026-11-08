from __future__ import annotations

import platform
import re
import subprocess
import time
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema

SECRET_PATTERNS = [
    re.compile(r"(?i)(?:api[_-]?key|secret|token|password|bearer|auth|access[_-]?key)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.]{12,})['\"]?"),
    re.compile(r"gh" + r"p_[A-Za-z0-9_]{36}"),
    re.compile(r"sk" + r"-[A-Za-z0-9_-]{32,}"),
    re.compile(r"AI" + r"za[A-Za-z0-9_\-]{35}"),
    re.compile(r"ey" + r"[A-Za-z0-9_-]{10,}\.ey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
]


def mask_sensitive(text: str) -> tuple[str, bool]:
    masked = text
    found = False
    for pat in SECRET_PATTERNS:
        if pat.search(masked):
            found = True
            masked = pat.sub("[REDACTED_SECRET]", masked)
    return masked, found


def _init_windows_clipboard_api():
    import ctypes
    from ctypes import wintypes, c_void_p, c_size_t

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    kernel32.GlobalAlloc.restype = c_void_p
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, c_size_t]
    kernel32.GlobalLock.restype = c_void_p
    kernel32.GlobalLock.argtypes = [c_void_p]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalUnlock.argtypes = [c_void_p]
    kernel32.GlobalFree.restype = c_void_p
    kernel32.GlobalFree.argtypes = [c_void_p]

    user32.OpenClipboard.restype = wintypes.BOOL
    user32.OpenClipboard.argtypes = [c_void_p]
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.argtypes = []
    user32.EmptyClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.argtypes = []
    user32.SetClipboardData.restype = c_void_p
    user32.SetClipboardData.argtypes = [wintypes.UINT, c_void_p]
    user32.GetClipboardData.restype = c_void_p
    user32.GetClipboardData.argtypes = [wintypes.UINT]

    return user32, kernel32


def _open_clipboard_retry(user32, attempts: int = 5, delay: float = 0.03) -> bool:
    for _ in range(attempts):
        if user32.OpenClipboard(None):
            return True
        time.sleep(delay)
    return False


def _read_clipboard_windows() -> str | None:
    try:
        import ctypes
        user32, kernel32 = _init_windows_clipboard_api()
        CF_UNICODETEXT = 13
        if not _open_clipboard_retry(user32):
            raise RuntimeError("Cannot open clipboard")
        try:
            h_clip = user32.GetClipboardData(CF_UNICODETEXT)
            if not h_clip:
                return ""
            ptr = kernel32.GlobalLock(h_clip)
            if not ptr:
                return ""
            try:
                return ctypes.c_wchar_p(ptr).value or ""
            finally:
                kernel32.GlobalUnlock(h_clip)
        finally:
            user32.CloseClipboard()
    except Exception:
        # Fallback to PowerShell
        try:
            proc = subprocess.run(
                ["powershell.exe", "-NoProfile", "-Command", "Get-Clipboard"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            return proc.stdout.rstrip("\r\n") if proc.returncode == 0 else None
        except Exception:
            return None


def _write_clipboard_windows(text: str) -> bool:
    try:
        import ctypes
        user32, kernel32 = _init_windows_clipboard_api()
        GMEM_MOVEABLE = 0x0002
        CF_UNICODETEXT = 13

        encoded = text.encode("utf-16le") + b"\x00\x00"
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(encoded))
        if not h_mem:
            raise RuntimeError("GlobalAlloc failed")

        ptr = kernel32.GlobalLock(h_mem)
        if not ptr:
            kernel32.GlobalFree(h_mem)
            raise RuntimeError("GlobalLock failed")

        ctypes.memmove(ptr, encoded, len(encoded))
        kernel32.GlobalUnlock(h_mem)

        if not _open_clipboard_retry(user32):
            kernel32.GlobalFree(h_mem)
            raise RuntimeError("OpenClipboard failed")

        try:
            user32.EmptyClipboard()
            res = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
            if res:
                return True
        finally:
            user32.CloseClipboard()
    except Exception:
        pass

    # Fallback to PowerShell using base64 decoding to avoid quoting issues
    try:
        import base64
        b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
        ps_cmd = f"[System.Windows.Forms.Clipboard]::SetText([System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{b64}')))"
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", f"Add-Type -AssemblyName System.Windows.Forms; {ps_cmd}"],
            capture_output=True,
            timeout=3,
        )
        return proc.returncode == 0
    except Exception:
        return False


def register(registry, settings, scope):
    async def read_clipboard(args):
        mask = args.get("mask_secrets", True)
        os_name = platform.system()
        content = None

        if os_name == "Windows":
            content = _read_clipboard_windows()
        elif os_name == "Darwin":
            try:
                proc = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=2)
                content = proc.stdout if proc.returncode == 0 else None
            except Exception:
                content = None
        elif os_name == "Linux":
            for cmd in (["wl-paste"], ["xclip", "-selection", "clipboard", "-o"]):
                try:
                    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                    if proc.returncode == 0:
                        content = proc.stdout
                        break
                except Exception:
                    continue

        if content is None:
            return ToolResult.error("CLIPBOARD_UNAVAILABLE", "unsupported", message="Clipboard is empty or unsupported on this OS")

        if len(content) > 100000:
            content = content[:100000] + "... [truncated]"

        masked_content, was_masked = mask_sensitive(content) if mask else (content, False)

        return ToolResult.ok(
            text=masked_content,
            length=len(content),
            masked=was_masked,
            note="Sensitive patterns masked by default; set mask_secrets=false to inspect raw",
        )

    async def write_clipboard(args):
        text = args["text"]
        os_name = platform.system()
        success = False

        if os_name == "Windows":
            success = _write_clipboard_windows(text)
        elif os_name == "Darwin":
            try:
                proc = subprocess.run(["pbcopy"], input=text, text=True, capture_output=True, timeout=2)
                success = proc.returncode == 0
            except Exception:
                success = False
        elif os_name == "Linux":
            for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
                try:
                    proc = subprocess.run(cmd, input=text, text=True, capture_output=True, timeout=2)
                    if proc.returncode == 0:
                        success = True
                        break
                except Exception:
                    continue

        if not success:
            return ToolResult.error("CLIPBOARD_WRITE_FAILED", "failed")

        return ToolResult.ok(
            bytes_written=len(text.encode("utf-8")),
            characters=len(text),
            note="Clipboard content updated successfully",
        )

    registry.register(
        ToolSpec(
            tool_id="clipboard.read",
            domain="addition_02",
            module=__name__,
            description="Read text from the system clipboard with automatic secret masking",
            input_schema=schema({"mask_secrets": {"type": "boolean"}}),
            risk=Risk.R1,
            effect="read",
        ),
        read_clipboard,
        preview=lambda a: "Read current system clipboard content (secrets masked by default)",
    )

    registry.register(
        ToolSpec(
            tool_id="clipboard.write",
            domain="addition_02",
            module=__name__,
            description="Write text to the system clipboard with user confirmation",
            input_schema=schema({"text": {"type": "string", "maxLength": 100000}}, ["text"]),
            risk=Risk.R1,
            effect="local_write",
            rollback="overwrite with previous text if known",
            verification="Confirm clipboard successfully set",
        ),
        write_clipboard,
        preview=lambda a: f"Write {len(a['text'])} characters to system clipboard",
    )
