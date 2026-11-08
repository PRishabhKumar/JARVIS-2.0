from __future__ import annotations

import json
import platform
import subprocess
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema

WINRT_HELPER = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { 
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' 
})[0]

function AwaitOp($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(8000) | Out-Null
    return $netTask.Result
}
"""


def _run_ps(script: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


# --- Wi-Fi ---

def _get_wifi_status_windows() -> dict:
    state = "unknown"
    ssid = None
    signal = None

    # Check netsh wlan show interfaces
    try:
        proc = _run_ps("netsh wlan show interfaces", timeout=4)
        if proc.returncode == 0:
            for line in proc.stdout.splitlines():
                line = line.strip()
                if line.startswith("State") and ":" in line:
                    state = line.split(":", 1)[1].strip()
                elif line.startswith("SSID") and not line.startswith("BSSID") and ":" in line:
                    ssid = line.split(":", 1)[1].strip()
                elif line.startswith("Signal") and ":" in line:
                    sig_str = line.split(":", 1)[1].strip().replace("%", "")
                    try:
                        signal = int(sig_str)
                    except ValueError:
                        pass
    except Exception:
        pass

    # Check Radio state
    radio_on = None
    try:
        ps_code = WINRT_HELPER + """
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = AwaitOp ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
        $w = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::WiFi }
        if ($w) { $w.State.ToString() }
        """
        proc = _run_ps(ps_code, timeout=6)
        if proc.returncode == 0 and proc.stdout.strip():
            radio_on = proc.stdout.strip().lower() == "on"
    except Exception:
        pass

    return {
        "enabled": radio_on if radio_on is not None else (state == "connected"),
        "state": state,
        "ssid": ssid,
        "signal_pct": signal,
    }


def _set_wifi_state_windows(enable: bool) -> bool:
    try:
        target = "On" if enable else "Off"
        ps_code = WINRT_HELPER + f"""
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = AwaitOp ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
        $w = $radios | Where-Object {{ $_.Kind -eq [Windows.Devices.Radios.RadioKind]::WiFi }}
        if ($w) {{
            $targetState = [Windows.Devices.Radios.RadioState]::{target}
            $res = AwaitOp ($w.SetStateAsync($targetState)) ([Windows.Devices.Radios.RadioAccessStatus])
            if ($res.ToString() -eq "Allowed") {{ exit 0 }} else {{ exit 1 }}
        }} else {{ exit 2 }}
        """
        proc = _run_ps(ps_code, timeout=8)
        if proc.returncode == 0:
            return True
    except Exception:
        pass

    # Fallback to netsh interface
    try:
        action = "ENABLED" if enable else "DISABLED"
        proc = _run_ps(f'netsh interface set interface name="Wi-Fi" admin={action}', timeout=5)
        return proc.returncode == 0
    except Exception:
        return False


# --- Bluetooth ---

def _get_bluetooth_status_windows() -> dict:
    radio_on = False
    try:
        ps_code = WINRT_HELPER + """
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = AwaitOp ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
        $b = $radios | Where-Object { $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth }
        if ($b) { $b.State.ToString() }
        """
        proc = _run_ps(ps_code, timeout=6)
        if proc.returncode == 0 and proc.stdout.strip():
            radio_on = proc.stdout.strip().lower() == "on"
    except Exception:
        pass

    devices = []
    try:
        proc = _run_ps(
            "Get-PnpDevice -Class Bluetooth -Status OK | Select-Object -ExpandProperty FriendlyName",
            timeout=4,
        )
        if proc.returncode == 0:
            devices = [d.strip() for d in proc.stdout.splitlines() if d.strip()][:10]
    except Exception:
        pass

    return {
        "enabled": radio_on,
        "connected_devices": devices,
        "device_count": len(devices),
    }


def _set_bluetooth_state_windows(enable: bool) -> bool:
    target = "On" if enable else "Off"
    try:
        ps_code = WINRT_HELPER + f"""
        [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime] | Out-Null
        $radios = AwaitOp ([Windows.Devices.Radios.Radio]::GetRadiosAsync()) ([System.Collections.Generic.IReadOnlyList[Windows.Devices.Radios.Radio]])
        $b = $radios | Where-Object {{ $_.Kind -eq [Windows.Devices.Radios.RadioKind]::Bluetooth }}
        if ($b) {{
            $targetState = [Windows.Devices.Radios.RadioState]::{target}
            $res = AwaitOp ($b.SetStateAsync($targetState)) ([Windows.Devices.Radios.RadioAccessStatus])
            if ($res.ToString() -eq "Allowed") {{ exit 0 }} else {{ exit 1 }}
        }} else {{ exit 2 }}
        """
        proc = _run_ps(ps_code, timeout=8)
        return proc.returncode == 0
    except Exception:
        return False


# --- Mobile Hotspot ---

def _get_hotspot_status_windows() -> dict:
    try:
        ps_code = """
        [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime] | Out-Null
        [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null
        $p = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
        if ($p) {
            $m = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($p)
            [PSCustomObject]@{
                state = $m.TetheringOperationalState.ToString()
                clients = $m.ClientCount
                max_clients = $m.MaxClientCount
            } | ConvertTo-Json -Compress
        } else {
            '{"state": "NoProfile", "clients": 0, "max_clients": 0}'
        }
        """
        proc = _run_ps(ps_code, timeout=6)
        if proc.returncode == 0 and proc.stdout.strip():
            data = json.loads(proc.stdout.strip())
            return {
                "enabled": data.get("state") == "On",
                "state": data.get("state", "Unknown"),
                "clients": data.get("clients", 0),
                "max_clients": data.get("max_clients", 8),
            }
    except Exception:
        pass
    return {"enabled": False, "state": "Unavailable", "clients": 0, "max_clients": 8}


def _set_hotspot_state_windows(enable: bool) -> bool:
    try:
        method = "StartTetheringAsync" if enable else "StopTetheringAsync"
        ps_code = WINRT_HELPER + f"""
        [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime] | Out-Null
        [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null
        $p = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
        if ($p) {{
            $m = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($p)
            $res = AwaitOp ($m.{method}()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
            if ($res.Status.ToString() -eq "Success") {{ exit 0 }} else {{ exit 1 }}
        }} else {{ exit 2 }}
        """
        proc = _run_ps(ps_code, timeout=12)
        return proc.returncode == 0
    except Exception:
        return False


def register(registry, settings, scope):
    # 1. Wi-Fi
    async def get_wifi(args):
        if platform.system() == "Windows":
            return ToolResult.ok(**_get_wifi_status_windows(), provider="Windows Netsh/WinRT")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    async def set_wifi(args):
        enabled = args["enabled"]
        if platform.system() == "Windows":
            ok = _set_wifi_state_windows(enabled)
            if ok:
                return ToolResult.ok(enabled=enabled, provider="Windows WinRT Radio")
            return ToolResult.error("WIFI_TOGGLE_FAILED", "failed")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    # 2. Bluetooth
    async def get_bluetooth(args):
        if platform.system() == "Windows":
            return ToolResult.ok(**_get_bluetooth_status_windows(), provider="Windows WinRT/PnP")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    async def set_bluetooth(args):
        enabled = args["enabled"]
        if platform.system() == "Windows":
            ok = _set_bluetooth_state_windows(enabled)
            if ok:
                return ToolResult.ok(enabled=enabled, provider="Windows WinRT Radio")
            return ToolResult.error("BLUETOOTH_TOGGLE_FAILED", "failed")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    # 3. Mobile Hotspot
    async def get_hotspot(args):
        if platform.system() == "Windows":
            return ToolResult.ok(**_get_hotspot_status_windows(), provider="Windows WinRT Tethering")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    async def set_hotspot(args):
        enabled = args["enabled"]
        if platform.system() == "Windows":
            ok = _set_hotspot_state_windows(enabled)
            if ok:
                return ToolResult.ok(enabled=enabled, provider="Windows WinRT Tethering")
            return ToolResult.error("HOTSPOT_TOGGLE_FAILED", "failed")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    # Register specs
    registry.register(
        ToolSpec(
            tool_id="wifi.get_status",
            domain="source_17",
            module=__name__,
            description="Get Wi-Fi radio status, connection state, SSID and signal strength",
            input_schema=schema(),
            risk=Risk.R0,
            effect="read",
        ),
        get_wifi,
        preview=lambda a: "Inspect Wi-Fi connection and radio state",
    )

    registry.register(
        ToolSpec(
            tool_id="wifi.set_state",
            domain="source_17",
            module=__name__,
            description="Turn Wi-Fi radio on or off",
            input_schema=schema({"enabled": {"type": "boolean"}}, ["enabled"]),
            risk=Risk.R1,
            effect="local_write",
            rollback="toggle wifi back to previous state",
            verification="Confirm Wi-Fi state updated",
        ),
        set_wifi,
        preview=lambda a: f"Turn Wi-Fi {'on' if a['enabled'] else 'off'}",
    )

    registry.register(
        ToolSpec(
            tool_id="bluetooth.get_status",
            domain="addition_06",
            module=__name__,
            description="Get Bluetooth radio state and connected devices",
            input_schema=schema(),
            risk=Risk.R0,
            effect="read",
        ),
        get_bluetooth,
        preview=lambda a: "Inspect Bluetooth radio and paired devices",
    )

    registry.register(
        ToolSpec(
            tool_id="bluetooth.set_state",
            domain="addition_06",
            module=__name__,
            description="Turn Bluetooth radio on or off",
            input_schema=schema({"enabled": {"type": "boolean"}}, ["enabled"]),
            risk=Risk.R1,
            effect="local_write",
            rollback="toggle bluetooth back to previous state",
            verification="Confirm Bluetooth state updated",
        ),
        set_bluetooth,
        preview=lambda a: f"Turn Bluetooth {'on' if a['enabled'] else 'off'}",
    )

    registry.register(
        ToolSpec(
            tool_id="hotspot.get_status",
            domain="source_17",
            module=__name__,
            description="Get Windows Mobile Hotspot state and client count",
            input_schema=schema(),
            risk=Risk.R0,
            effect="read",
        ),
        get_hotspot,
        preview=lambda a: "Inspect Mobile Hotspot state",
    )

    registry.register(
        ToolSpec(
            tool_id="hotspot.set_state",
            domain="source_17",
            module=__name__,
            description="Turn Windows Mobile Hotspot on or off",
            input_schema=schema({"enabled": {"type": "boolean"}}, ["enabled"]),
            risk=Risk.R1,
            effect="local_write",
            rollback="toggle mobile hotspot back to previous state",
            verification="Confirm Mobile Hotspot state updated",
        ),
        set_hotspot,
        preview=lambda a: f"Turn Mobile Hotspot {'on' if a['enabled'] else 'off'}",
    )

