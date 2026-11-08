from __future__ import annotations

import platform
import subprocess
from jarvis.contracts import ToolResult, ToolSpec, Risk
from jarvis.registry import schema


def _get_wasapi_endpoint():
    try:
        import ctypes
        from ctypes import wintypes, POINTER, c_void_p, Structure, c_uint32, c_int, byref

        ole32 = ctypes.oledll.ole32

        class GUID(Structure):
            _fields_ = [
                ("Data1", c_uint32),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]
            def __init__(self, d1, d2, d3, d4_list):
                super().__init__(d1, d2, d3, (wintypes.BYTE * 8)(*d4_list))

        CLSID_MMDeviceEnumerator = GUID(0xBCDE0395, 0xE52F, 0x467C, [0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x91, 0x69, 0x2E])
        IID_IMMDeviceEnumerator = GUID(0xA95664D2, 0x9614, 0x4F35, [0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6])
        IID_IAudioEndpointVolume = GUID(0x5CDF2C82, 0x841E, 0x4546, [0x97, 0x22, 0x0C, 0xF7, 0x40, 0x78, 0x22, 0x9A])

        CLSCTX_ALL = 23
        eRender = 0
        eMultimedia = 1

        ole32.CoInitialize(None)
        pEnum = c_void_p()
        hr = ole32.CoCreateInstance(
            byref(CLSID_MMDeviceEnumerator),
            None,
            CLSCTX_ALL,
            byref(IID_IMMDeviceEnumerator),
            byref(pEnum),
        )
        if hr != 0 or not pEnum:
            return None, None

        vtable_enum = ctypes.cast(pEnum, POINTER(POINTER(c_void_p))).contents
        GetDefaultAudioEndpoint_func = ctypes.WINFUNCTYPE(
            ctypes.c_long, c_void_p, c_int, c_int, POINTER(c_void_p)
        )(vtable_enum[4])

        pDevice = c_void_p()
        hr = GetDefaultAudioEndpoint_func(pEnum, eRender, eMultimedia, byref(pDevice))
        if hr != 0 or not pDevice:
            return None, None

        vtable_dev = ctypes.cast(pDevice, POINTER(POINTER(c_void_p))).contents
        Activate_func = ctypes.WINFUNCTYPE(
            ctypes.c_long, c_void_p, POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p)
        )(vtable_dev[3])

        pVolume = c_void_p()
        hr = Activate_func(pDevice, byref(IID_IAudioEndpointVolume), CLSCTX_ALL, None, byref(pVolume))
        if hr != 0 or not pVolume:
            return None, None

        vtable_vol = ctypes.cast(pVolume, POINTER(POINTER(c_void_p))).contents
        return pVolume, vtable_vol
    except Exception:
        return None, None


def _get_volume_windows() -> tuple[int, bool] | None:
    try:
        import ctypes
        from ctypes import wintypes, c_float, byref

        pVolume, vtable_vol = _get_wasapi_endpoint()
        if pVolume and vtable_vol:
            GetMasterVolumeLevelScalar = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(c_float)
            )(vtable_vol[9])
            GetMute = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)
            )(vtable_vol[15])

            vol = c_float()
            muted = wintypes.BOOL()
            hr_vol = GetMasterVolumeLevelScalar(pVolume, byref(vol))
            hr_mute = GetMute(pVolume, byref(muted))

            if hr_vol == 0:
                level = int(round(vol.value * 100))
                is_muted = bool(muted.value) if hr_mute == 0 else (level == 0)
                return level, is_muted
    except Exception:
        pass

    # Legacy fallback to winmm if CoreAudio unavailable
    try:
        import ctypes
        from ctypes import wintypes

        winmm = ctypes.windll.winmm
        vol = wintypes.DWORD()
        res = winmm.waveOutGetVolume(0, ctypes.byref(vol))
        if res == 0:
            left = (vol.value & 0xFFFF) * 100 // 0xFFFF
            right = ((vol.value >> 16) & 0xFFFF) * 100 // 0xFFFF
            avg = (left + right) // 2
            return avg, (avg == 0)
    except Exception:
        pass
    return None


def _set_volume_windows(level: int) -> bool:
    target_scalar = max(0.0, min(1.0, level / 100.0))
    try:
        import ctypes
        from ctypes import c_float

        pVolume, vtable_vol = _get_wasapi_endpoint()
        if pVolume and vtable_vol:
            SetMasterVolumeLevelScalar = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, c_float, ctypes.c_void_p
            )(vtable_vol[7])
            hr = SetMasterVolumeLevelScalar(pVolume, target_scalar, None)
            if hr == 0:
                if level > 0:
                    try:
                        from ctypes import wintypes

                        SetMute = ctypes.WINFUNCTYPE(
                            ctypes.c_long, ctypes.c_void_p, wintypes.BOOL, ctypes.c_void_p
                        )(vtable_vol[14])
                        SetMute(pVolume, False, None)
                    except Exception:
                        pass
                return True
    except Exception:
        pass

    # Fallback to winmm
    try:
        import ctypes
        from ctypes import wintypes

        winmm = ctypes.windll.winmm
        scalar = int(max(0, min(100, level)) * 0xFFFF / 100)
        dw_vol = wintypes.DWORD(scalar | (scalar << 16))
        res = winmm.waveOutSetVolume(0, dw_vol)
        return res == 0
    except Exception:
        return False


def _toggle_mute_windows() -> tuple[bool, bool | None]:
    try:
        import ctypes
        from ctypes import wintypes, byref

        pVolume, vtable_vol = _get_wasapi_endpoint()
        if pVolume and vtable_vol:
            GetMute = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL)
            )(vtable_vol[15])
            SetMute = ctypes.WINFUNCTYPE(
                ctypes.c_long, ctypes.c_void_p, wintypes.BOOL, ctypes.c_void_p
            )(vtable_vol[14])

            current_mute = wintypes.BOOL()
            hr_get = GetMute(pVolume, byref(current_mute))
            target_mute = not bool(current_mute.value) if hr_get == 0 else True
            hr_set = SetMute(pVolume, target_mute, None)
            if hr_set == 0:
                return True, target_mute
    except Exception:
        pass

    # Fallback to media key
    try:
        import ctypes

        user32 = ctypes.windll.user32
        VK_VOLUME_MUTE = 0xAD
        KEYEVENTF_KEYUP = 0x0002
        user32.keybd_event(VK_VOLUME_MUTE, 0, 0, 0)
        user32.keybd_event(VK_VOLUME_MUTE, 0, KEYEVENTF_KEYUP, 0)
        return True, None
    except Exception:
        return False, None


def register(registry, settings, scope):
    async def get_volume(args):
        os_name = platform.system()
        if os_name == "Windows":
            info = _get_volume_windows()
            if info is not None:
                vol, muted = info
                return ToolResult.ok(volume=vol, muted=muted, provider="Windows CoreAudio WASAPI")
            return ToolResult.error("AUDIO_QUERY_FAILED", "failed")
        elif os_name == "Darwin":
            try:
                proc = subprocess.run(
                    ["osascript", "-e", "output volume of (get volume settings)"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if proc.returncode == 0:
                    vol = int(proc.stdout.strip())
                    return ToolResult.ok(volume=vol, provider="macOS osascript")
            except Exception:
                pass
            return ToolResult.error("AUDIO_QUERY_FAILED", "failed")
        elif os_name == "Linux":
            try:
                proc = subprocess.run(
                    ["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if proc.returncode == 0 and "%" in proc.stdout:
                    pct = proc.stdout.split("%")[0].split("/")[-1].strip()
                    return ToolResult.ok(volume=int(pct), provider="Linux PulseAudio")
            except Exception:
                pass
            return ToolResult.error("AUDIO_QUERY_FAILED", "failed")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    async def set_volume(args):
        level = args["level"]
        os_name = platform.system()
        if os_name == "Windows":
            ok = _set_volume_windows(level)
            if ok:
                return ToolResult.ok(level=level, provider="Windows CoreAudio WASAPI")
            return ToolResult.error("AUDIO_SET_FAILED", "failed")
        elif os_name == "Darwin":
            try:
                proc = subprocess.run(
                    ["osascript", "-e", f"set volume output volume {level}"], timeout=2
                )
                if proc.returncode == 0:
                    return ToolResult.ok(level=level, provider="macOS osascript")
            except Exception:
                pass
            return ToolResult.error("AUDIO_SET_FAILED", "failed")
        elif os_name == "Linux":
            try:
                proc = subprocess.run(
                    ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], timeout=2
                )
                if proc.returncode == 0:
                    return ToolResult.ok(level=level, provider="Linux PulseAudio")
            except Exception:
                pass
            return ToolResult.error("AUDIO_SET_FAILED", "failed")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    async def toggle_mute(args):
        os_name = platform.system()
        if os_name == "Windows":
            ok, new_state = _toggle_mute_windows()
            if ok:
                return ToolResult.ok(
                    toggled=True,
                    muted=new_state,
                    provider="Windows CoreAudio WASAPI",
                )
            return ToolResult.error("AUDIO_MUTE_FAILED", "failed")
        elif os_name == "Darwin":
            try:
                proc = subprocess.run(
                    [
                        "osascript",
                        "-e",
                        "set volume output muted not (output muted of (get volume settings))",
                    ],
                    timeout=2,
                )
                if proc.returncode == 0:
                    return ToolResult.ok(toggled=True, provider="macOS osascript")
            except Exception:
                pass
            return ToolResult.error("AUDIO_MUTE_FAILED", "failed")
        elif os_name == "Linux":
            try:
                proc = subprocess.run(
                    ["pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle"], timeout=2
                )
                if proc.returncode == 0:
                    return ToolResult.ok(toggled=True, provider="Linux PulseAudio")
            except Exception:
                pass
            return ToolResult.error("AUDIO_MUTE_FAILED", "failed")
        return ToolResult.error("OS_UNSUPPORTED", "unsupported")

    registry.register(
        ToolSpec(
            tool_id="audio.get_volume",
            domain="addition_05",
            module=__name__,
            description="Get system master audio volume level (0-100) and mute status",
            input_schema=schema(),
            risk=Risk.R0,
            effect="read",
        ),
        get_volume,
        preview=lambda a: "Inspect master audio volume and mute state",
    )

    registry.register(
        ToolSpec(
            tool_id="audio.set_volume",
            domain="addition_05",
            module=__name__,
            description="Set master audio volume to a specified percentage (0 to 100)",
            input_schema=schema({"level": {"type": "integer", "minimum": 0, "maximum": 100}}, ["level"]),
            risk=Risk.R1,
            effect="local_write",
            rollback="restore previous volume level",
            verification="Confirm volume setting applied",
        ),
        set_volume,
        preview=lambda a: f"Set master audio volume to {a['level']}%",
    )

    registry.register(
        ToolSpec(
            tool_id="audio.toggle_mute",
            domain="addition_05",
            module=__name__,
            description="Toggle or set system master audio mute",
            input_schema=schema(),
            risk=Risk.R1,
            effect="local_write",
            rollback="toggle mute again to restore",
            verification="Confirm mute toggle executed",
        ),
        toggle_mute,
        preview=lambda a: "Toggle system master audio mute",
    )
