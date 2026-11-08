from __future__ import annotations

from datetime import datetime
from pathlib import Path
import platform
import subprocess
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema, PATH


def register(registry, settings, scope):
    async def capture_screen(args):
        os_name = platform.system()
        state = Path(settings.state_dir)
        captures_dir = state / "captures"
        captures_dir.mkdir(parents=True, exist_ok=True)

        if "path" in args:
            out_path = scope.resolve(args["path"], exists=False)
            out_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = captures_dir / f"screenshot_{stamp}.png"

        success = False
        width, height = 0, 0

        if os_name == "Windows":
            ps_script = f"""
            Add-Type -AssemblyName System.Windows.Forms
            Add-Type -AssemblyName System.Drawing
            $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
            $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
            $g = [System.Drawing.Graphics]::FromImage($bmp)
            $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
            $bmp.Save('{str(out_path).replace("'", "''")}', [System.Drawing.Imaging.ImageFormat]::Png)
            $g.Dispose()
            $bmp.Dispose()
            Write-Output "$($b.Width)x$($b.Height)"
            """
            try:
                proc = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-Command", ps_script],
                    capture_output=True,
                    text=True,
                    timeout=8,
                )
                if proc.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 0:
                    success = True
                    dims = proc.stdout.strip().split("x")
                    if len(dims) == 2:
                        try:
                            width, height = int(dims[0]), int(dims[1])
                        except ValueError:
                            pass
            except Exception:
                success = False

        elif os_name == "Darwin":
            try:
                proc = subprocess.run(["screencapture", "-x", str(out_path)], timeout=5)
                success = proc.returncode == 0 and out_path.is_file()
            except Exception:
                success = False

        elif os_name == "Linux":
            for tool, argv in [
                ("grim", ["grim", str(out_path)]),
                ("scrot", ["scrot", str(out_path)]),
                ("import", ["import", "-window", "root", str(out_path)]),
            ]:
                try:
                    proc = subprocess.run(argv, timeout=5)
                    if proc.returncode == 0 and out_path.is_file():
                        success = True
                        break
                except Exception:
                    continue

        if not success:
            return ToolResult.error("SCREEN_CAPTURE_FAILED", "failed", message="Could not capture screen on this platform")

        file_bytes = out_path.stat().st_size
        return ToolResult.ok(
            path=str(out_path),
            size_bytes=file_bytes,
            width=width if width > 0 else None,
            height=height if height > 0 else None,
            format="png",
        )

    async def verify_capture(args, result):
        if result.status != "succeeded":
            return True
        p = Path(result.structured_data.get("path", ""))
        return p.is_file() and p.stat().st_size > 0

    registry.register(
        ToolSpec(
            tool_id="screen.capture",
            domain="addition_03",
            module=__name__,
            description="Capture full desktop screenshot to a PNG file within allowed roots or state folder",
            input_schema=schema({"path": PATH}),
            risk=Risk.R1,
            effect="local_write",
            rollback="delete captured file if requested",
            verification="Confirm screenshot file exists on disk with non-zero size",
        ),
        capture_screen,
        preview=lambda a: f"Capture primary screen to {a.get('path', 'default captures directory')!r}",
        verifier=verify_capture,
    )

