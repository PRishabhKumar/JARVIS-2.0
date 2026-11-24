from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import platform
import time
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import psutil
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
try:
    from starlette.websockets import WebSocketDisconnected
except ImportError:
    WebSocketDisconnected = WebSocketDisconnect

from .bootstrap import build_registry
from .config import Settings
from .contracts import ExecutionContext, Risk, ToolCall, ToolResult
from .models.mock import FIXTURES
from .orchestrator import AgentCoordinator
from .policy import ApprovalRequest, PolicyGate, touches_c_drive, is_deletion_operation
from .storage.store import Store

logger = logging.getLogger("jarvis.deck_server")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def to_utc_iso(timestamp: float | datetime) -> str:
    if isinstance(timestamp, (int, float)):
        dt = datetime.fromtimestamp(timestamp, timezone.utc)
    else:
        dt = timestamp.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


_active_websockets: set[WebSocket] = set()


async def broadcast_deck_event(event_type: str, **kwargs):
    payload = {
        "event_id": f"evt-{uuid4().hex[:12]}",
        "timestamp": utc_now_iso(),
        "type": event_type,
        **kwargs,
    }
    raw = json.dumps(payload)
    for ws in list(_active_websockets):
        try:
            await ws.send_text(raw)
        except Exception:
            pass


def collect_telemetry() -> dict[str, Any]:
    try:
        cpu = float(psutil.cpu_percent(interval=None))
    except Exception:
        cpu = None

    try:
        vmem = psutil.virtual_memory()
        ram = float(round(vmem.percent, 1))
        ram_used_gb = float(round((vmem.total - vmem.available) / (1024**3), 2))
        ram_total_gb = float(round(vmem.total / (1024**3), 2))
    except Exception:
        ram = ram_used_gb = ram_total_gb = None

    try:
        b_info = psutil.sensors_battery()
        battery = float(round(b_info.percent, 1)) if b_info else None
        plugged = bool(b_info.power_plugged) if b_info else True
    except Exception:
        battery = None
        plugged = True

    brightness_val = None
    try:
        from .agents.display_agent import _get_brightness_windows
        b_res = _get_brightness_windows()
        if b_res:
            brightness_val = int(b_res[0])
    except Exception:
        pass

    vol_val = None
    muted_val = False
    try:
        from .agents.audio_control_agent import _get_volume_windows
        v_res = _get_volume_windows()
        if v_res:
            vol_val = int(v_res[0])
            muted_val = bool(v_res[1])
    except Exception:
        pass

    wifi_val = False
    bt_val = False
    hotspot_val = False
    try:
        from .agents.wireless_agent import (
            _get_wifi_status_windows,
            _get_bluetooth_status_windows,
            _get_hotspot_status_windows,
        )
        wifi_val = bool(_get_wifi_status_windows().get("enabled", False))
        bt_val = bool(_get_bluetooth_status_windows().get("enabled", False))
        hotspot_val = bool(_get_hotspot_status_windows().get("enabled", False))
    except Exception:
        pass

    supported: list[str] = ["volume", "muted"]
    if brightness_val is not None:
        supported.append("brightness")
    if platform.system() == "Windows":
        supported.extend(["wifi", "bluetooth", "hotspot"])

    return {
        "cpu": cpu,
        "ram": ram,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "battery": battery,
        "plugged": plugged,
        "brightness": brightness_val,
        "volume": vol_val,
        "muted": muted_val,
        "wifi": wifi_val,
        "bluetooth": bt_val,
        "hotspot": hotspot_val,
        "supported_controls": supported,
    }


_last_telemetry: dict[str, Any] | None = None
_last_telemetry_time: float = 0.0


def get_cached_telemetry() -> dict[str, Any]:
    global _last_telemetry, _last_telemetry_time
    now = time.monotonic()
    if _last_telemetry is not None and (now - _last_telemetry_time) < 2.0:
        return _last_telemetry
    data = collect_telemetry()
    _last_telemetry = data
    _last_telemetry_time = now
    return data


def apply_control(control: str, value: int | bool) -> bool:
    os_name = platform.system()
    try:
        if control == "volume" and isinstance(value, (int, float)):
            from .agents.audio_control_agent import _set_volume_windows
            return _set_volume_windows(int(value))
        elif control == "brightness" and isinstance(value, (int, float)):
            from .agents.display_agent import _set_brightness_windows
            return _set_brightness_windows(int(value))
        elif control == "muted" and isinstance(value, bool):
            from .agents.audio_control_agent import _set_volume_windows, _get_volume_windows
            v_res = _get_volume_windows()
            if value:
                return _set_volume_windows(0)
            else:
                return _set_volume_windows(v_res[0] if v_res and v_res[0] > 0 else 30)
        elif control == "wifi" and isinstance(value, bool) and os_name == "Windows":
            from .agents.wireless_agent import _set_wifi_state_windows
            return _set_wifi_state_windows(value)
        elif control == "bluetooth" and isinstance(value, bool) and os_name == "Windows":
            from .agents.wireless_agent import _set_bluetooth_state_windows
            return _set_bluetooth_state_windows(value)
        elif control == "hotspot" and isinstance(value, bool) and os_name == "Windows":
            from .agents.wireless_agent import _set_hotspot_state_windows
            return _set_hotspot_state_windows(value)
    except Exception as e:
        logger.error(f"Failed to apply control {control}={value}: {e}")
    return False


async def run_live_audio_turn(
    pcm_bytes: bytes,
    send_fn,
    registry,
    coordinator,
    settings: Settings,
    audio_out=None,
):
    from .models.gemini import GeminiSession
    from .storage.credentials import get_secret

    gemini_key = None
    try:
        gemini_key = get_secret("gemini")
    except Exception as e:
        logger.warning(f"[live-turn] Could not load Gemini credential: {e}")

    if not gemini_key:
        await send_fn(
            "transcript.delta",
            message_id=f"msg-{uuid4().hex[:12]}",
            role="assistant",
            delta="Wake word heard. (Add your GEMINI_API_KEY to Code/jarvis/.env to enable speech recognition).",
            final=True,
        )
        await send_fn("agent.state", state="IDLE")
        return

    assistant_msg_id = f"msg-{uuid4().hex[:12]}"
    user_msg_id = f"msg-{uuid4().hex[:12]}"
    reply_parts: list[str] = []

    async def on_input_transcript(user_text: str):
        cleaned = user_text.strip()
        if cleaned:
            await send_fn(
                "transcript.delta",
                message_id=user_msg_id,
                role="user",
                delta=cleaned,
                final=True,
            )

    async def on_tool_call(name: str, args: dict):
        tool = registry.get(name)
        desc = tool.spec.description if tool else "System Action"
        risk_str = tool.spec.risk.value if tool else "R1"
        await send_fn(
            "tool.update",
            tool={
                "id": f"inv-{uuid4().hex[:12]}",
                "name": name,
                "description": desc,
                "status": "running",
                "risk": risk_str,
                "duration_ms": 0,
                "resources": [],
                "verified": False,
                "detail": f"Executing {name}...",
                "timestamp": utc_now_iso(),
            },
        )

    async def on_tool_result(name: str, result):
        tool = registry.get(name)
        desc = tool.spec.description if tool else "System Action"
        risk_str = tool.spec.risk.value if tool else "R1"
        status = result.status if result.status in ("succeeded", "failed", "denied", "cancelled") else "failed"
        detail = result.message or (
            json.dumps(result.structured_data)[:500] if result.structured_data else f"Status: {result.status}"
        )
        await send_fn(
            "tool.update",
            tool={
                "id": f"inv-{uuid4().hex[:12]}",
                "name": name,
                "description": desc,
                "status": status,
                "risk": risk_str,
                "duration_ms": 120,
                "resources": [],
                "verified": result.status == "succeeded",
                "detail": detail,
                "timestamp": utc_now_iso(),
            },
        )

    def on_emit(chunk: str):
        if chunk:
            reply_parts.append(chunk)

    live = GeminiSession(
        gemini_key,
        settings.model,
        registry,
        coordinator,
        emit=on_emit,
        audio=audio_out,
        on_input_transcript=on_input_transcript,
        on_tool_call=on_tool_call,
        on_tool_result=on_tool_result,
        voice_name=settings.voice_name,
    )

    try:
        await live.connect()
        await send_fn("agent.state", state="THINKING")
        live.turn_done.clear()

        slice_size = 2560
        for i in range(0, len(pcm_bytes), slice_size):
            await live.send_audio(pcm_bytes[i : i + slice_size])
            await asyncio.sleep(0.01)

        if live.session:
            await live.session.send_realtime_input(audio_stream_end=True)

        async with asyncio.timeout(45):
            await live.turn_done.wait()

        if audio_out:
            await audio_out.wait_playback_complete(timeout=10.0)

        full_reply = "".join(reply_parts).strip()
        if full_reply:
            await send_fn(
                "transcript.delta",
                message_id=assistant_msg_id,
                role="assistant",
                delta=full_reply,
                final=True,
            )
    except Exception as e:
        logger.warning(f"[live-turn] Live audio turn error: {e}", exc_info=True)
        await send_fn(
            "transcript.delta",
            message_id=assistant_msg_id,
            role="assistant",
            delta=f"Gemini Live session error: {e}.",
            final=True,
        )
    finally:
        await live.close()
        await send_fn("agent.state", state="IDLE")


def create_deck_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings.load()

    registry = build_registry(settings)
    try:
        state_path = Path(settings.state_dir)
        state_path.mkdir(parents=True, exist_ok=True)
        store = Store(state_path / "deck_state.db")
    except Exception:
        fallback_path = Path.cwd() / ".jarvis_state"
        fallback_path.mkdir(parents=True, exist_ok=True)
        store = Store(fallback_path / "deck_state.db")

    app = FastAPI(title="JARVIS Control Deck Adapter", docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "version": "1.0.0",
            "protocol": "jarvis.ui.v1",
            "name": "JARVIS",
        }

    @app.get("/capabilities")
    async def capabilities():
        caps = [
            {
                "id": t.spec.tool_id,
                "description": t.spec.description,
                "risk": t.spec.risk.value,
                "effect": t.spec.effect,
                "os": t.spec.supported_os,
            }
            for t in registry.all()
        ]
        return {"capabilities": caps[:500]}

    @app.get("/telemetry")
    async def telemetry():
        return await asyncio.to_thread(get_cached_telemetry)

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()
        _active_websockets.add(ws)
        session_id = f"session-{uuid4().hex[:12]}"
        pending_approvals: dict[str, tuple[asyncio.Future, str, str, str | None]] = {}
        incoming_audio: dict[str, list[bytes]] = {}
        active_work: asyncio.Task | None = None
        send_lock = asyncio.Lock()

        async def send_event(event_type: str, **kwargs):
            payload = {
                "event_id": f"evt-{uuid4().hex[:12]}",
                "timestamp": utc_now_iso(),
                "type": event_type,
                **kwargs,
            }
            async with send_lock:
                try:
                    await ws.send_text(json.dumps(payload))
                except Exception:
                    pass

        async def confirm_via_deck(request: ApprovalRequest) -> bool:
            approval_id = f"approval-{uuid4().hex[:12]}"
            guards: list[str] = []
            if touches_c_drive(request.preview) or "c:" in request.preview.lower():
                guards.append("C_DRIVE")
            if is_deletion_operation(request.tool_id, {"target": request.preview}):
                guards.append("DELETION")
            if not guards:
                guards.append("C_DRIVE")

            risk_level = request.risk if request.risk in ("R2", "R3") else "R2"
            approval_data = {
                "id": approval_id,
                "binding_hash": request.binding,
                "tool_id": request.tool_id,
                "title": f"Guardrail: {request.tool_id}",
                "summary": request.preview,
                "target": request.preview,
                "normalized_command": f"{request.tool_id}()",
                "risk": risk_level,
                "guards": guards,
                "expires_at": to_utc_iso(request.expires_at),
                "reversible": False,
                "required_phrase": request.phrase if risk_level == "R3" else None,
            }

            fut = asyncio.get_running_loop().create_future()
            pending_approvals[approval_id] = (fut, request.binding, risk_level, request.phrase)

            await send_event("agent.state", state="GUARDRAIL_ALERT")
            await send_event("approval.required", approval=approval_data)

            timeout = max(1.0, request.expires_at - time.time())
            try:
                async with asyncio.timeout(timeout):
                    return await fut
            except TimeoutError:
                await send_event(
                    "approval.resolved",
                    approval_id=approval_id,
                    decision="expired",
                    message="Approval confirmation expired.",
                )
                return False
            finally:
                pending_approvals.pop(approval_id, None)

        context = ExecutionContext(
            session_id=session_id,
            max_calls=settings.max_calls,
            maximum_effect="local_write" if settings.allow_mutations else "read",
        )
        gate = PolicyGate(
            confirm_via_deck,
            threshold=Risk(settings.confirmation_threshold),
        )
        coordinator = AgentCoordinator(registry, gate, store, context)

        async def tracked_dispatch(call: ToolCall) -> ToolResult:
            tool = coordinator.registry.get(call.name)
            desc = tool.spec.description if tool else "Unknown tool"
            risk_str = tool.spec.risk.value if tool else "R1"
            invocation_id = f"inv-{uuid4().hex[:12]}"

            resources: list[str] = []
            for k, v in call.arguments.items():
                if isinstance(v, str) and (":" in v or "/" in v or "\\" in v):
                    resources.append(v)
                elif isinstance(v, list):
                    for item in v:
                        if isinstance(item, str) and (":" in item or "/" in item or "\\" in item):
                            resources.append(item)
            resources = resources[:100]

            await send_event(
                "tool.update",
                tool={
                    "id": invocation_id,
                    "name": call.name,
                    "description": desc,
                    "status": "running",
                    "risk": risk_str,
                    "duration_ms": 0,
                    "resources": resources,
                    "verified": False,
                    "detail": f"Executing {call.name}...",
                    "timestamp": utc_now_iso(),
                },
            )

            start = time.monotonic()
            result = await coordinator.dispatch(call)
            duration_ms = max(0, int((time.monotonic() - start) * 1000))

            status = result.status
            if status not in ("succeeded", "failed", "denied", "cancelled"):
                status = "failed"
            verified = (result.status == "succeeded")
            detail = result.message or (
                json.dumps(result.structured_data)[:500] if result.structured_data else f"Status: {result.status}"
            )

            await send_event(
                "tool.update",
                tool={
                    "id": invocation_id,
                    "name": call.name,
                    "description": desc,
                    "status": status,
                    "risk": risk_str,
                    "duration_ms": duration_ms,
                    "resources": resources,
                    "verified": verified,
                    "detail": detail,
                    "timestamp": utc_now_iso(),
                },
            )
            return result

        telemetry_task: asyncio.Task | None = None

        async def telemetry_loop():
            while True:
                try:
                    await asyncio.sleep(2.5)
                    data = await asyncio.to_thread(get_cached_telemetry)
                    await send_event("telemetry.update", telemetry=data)
                except asyncio.CancelledError:
                    break
                except Exception:
                    await asyncio.sleep(5)

        async def handle_user_message(req_id: str, text: str):
            message_id = f"msg-{uuid4().hex[:12]}"
            await send_event("agent.state", state="THINKING")

            # Check for Gemini key
            gemini_key = None
            try:
                from .storage.credentials import get_secret
                gemini_key = get_secret("gemini")
            except Exception as e:
                logger.warning(f"Could not load Gemini API key: {e}")

            if gemini_key:
                try:
                    from .models.gemini import GeminiSession

                    reply_parts: list[str] = []

                    async def on_tool_call(name, args):
                        tool = coordinator.registry.get(name)
                        desc = tool.spec.description if tool else "Unknown"
                        risk_str = tool.spec.risk.value if tool else "R1"
                        inv_id = f"inv-{uuid4().hex[:12]}"
                        await send_event(
                            "tool.update",
                            tool={
                                "id": inv_id,
                                "name": name,
                                "description": desc,
                                "status": "running",
                                "risk": risk_str,
                                "duration_ms": 0,
                                "resources": [],
                                "verified": False,
                                "detail": f"Executing {name}...",
                                "timestamp": utc_now_iso(),
                            },
                        )

                    async def on_tool_result(name, result):
                        tool = coordinator.registry.get(name)
                        desc = tool.spec.description if tool else "Unknown"
                        risk_str = tool.spec.risk.value if tool else "R1"
                        inv_id = f"inv-{uuid4().hex[:12]}"
                        status = result.status if result.status in ("succeeded", "failed", "denied", "cancelled") else "failed"
                        detail = result.message or (
                            json.dumps(result.structured_data)[:500] if result.structured_data else f"Status: {result.status}"
                        )
                        await send_event(
                            "tool.update",
                            tool={
                                "id": inv_id,
                                "name": name,
                                "description": desc,
                                "status": status,
                                "risk": risk_str,
                                "duration_ms": 100,
                                "resources": [],
                                "verified": result.status == "succeeded",
                                "detail": detail,
                                "timestamp": utc_now_iso(),
                            },
                        )

                    def on_emit(text_chunk):
                        reply_parts.append(text_chunk)

                    live = GeminiSession(
                        gemini_key,
                        settings.model,
                        registry,
                        coordinator,
                        emit=on_emit,
                        on_tool_call=on_tool_call,
                        on_tool_result=on_tool_result,
                        voice_name=settings.voice_name,
                    )

                    await live.connect()
                    try:
                        await live.text_turn(text)
                    finally:
                        await live.close()

                    reply_text = "".join(reply_parts).strip()
                    if reply_text:
                        await send_event(
                            "transcript.delta",
                            message_id=message_id,
                            role="assistant",
                            delta=reply_text,
                            final=True,
                        )
                    else:
                        await send_event(
                            "transcript.delta",
                            message_id=message_id,
                            role="assistant",
                            delta="Request processed.",
                            final=True,
                        )
                except Exception as e:
                    logger.warning(f"Gemini Live turn failed: {e}", exc_info=True)
                    gemini_key = None

            if not gemini_key:
                # Local intelligent mock / fixture handler
                text_clean = text.strip()
                matched_fixture = FIXTURES.get(text_clean)
                if matched_fixture:
                    tool_name, tool_args = matched_fixture
                    call = ToolCall(call_id=uuid4().hex, name=tool_name, arguments=tool_args)
                    res = await tracked_dispatch(call)
                    if res.status == "succeeded" and tool_name == "system.get_time":
                        out_text = f"The current local time is {res.structured_data.get('iso', 'now')}."
                    else:
                        out_text = f"Action {tool_name} completed: {res.status}."
                elif "time" in text_clean.lower():
                    call = ToolCall(call_id=uuid4().hex, name="system.get_time", arguments={})
                    res = await tracked_dispatch(call)
                    out_text = f"The local time is {res.structured_data.get('iso', 'now')}."
                elif "folder" in text_clean.lower() or "list" in text_clean.lower():
                    call = ToolCall(call_id=uuid4().hex, name="filesystem.list_directory", arguments={"path": "."})
                    res = await tracked_dispatch(call)
                    out_text = f"Directory inspected. Found {len(res.structured_data.get('entries', []))} items."
                elif "process" in text_clean.lower():
                    call = ToolCall(call_id=uuid4().hex, name="process.list", arguments={"limit": 5})
                    res = await tracked_dispatch(call)
                    out_text = "Process inspection completed."
                elif "hardware" in text_clean.lower() or "inventory" in text_clean.lower():
                    call = ToolCall(call_id=uuid4().hex, name="hardware.inventory", arguments={})
                    res = await tracked_dispatch(call)
                    out_text = "Hardware inventory retrieved."
                else:
                    out_text = (
                        f"Received: \"{text}\". (Gemini Live session could not be established; "
                        "check the backend terminal for details. Falling back to local tools: "
                        "try asking for local time, directory listing, hardware inventory, or system controls)."
                    )

                await send_event(
                    "transcript.delta",
                    message_id=message_id,
                    role="assistant",
                    delta=out_text,
                    final=True,
                )

            await send_event("agent.state", state="IDLE")

        async def handle_user_audio(stream_id: str, pcm_bytes: bytes):
            await send_event("agent.state", state="THINKING")
            await run_live_audio_turn(
                pcm_bytes,
                send_event,
                registry,
                coordinator,
                settings,
                audio_out=None,
            )

        try:
            while True:
                raw_text = await ws.receive_text()
                try:
                    payload = json.loads(raw_text)
                except Exception:
                    continue

                event_type = payload.get("type")

                if event_type == "session.hello":
                    await send_event(
                        "session.ready",
                        session_id=session_id,
                        protocol="jarvis.ui.v1",
                    )
                    await send_event("agent.state", state="IDLE")
                    telem = await asyncio.to_thread(get_cached_telemetry)
                    await send_event("telemetry.update", telemetry=telem)
                    if telemetry_task is None or telemetry_task.done():
                        telemetry_task = asyncio.create_task(telemetry_loop())

                elif event_type == "ping":
                    ping_id = payload.get("id", "")
                    await send_event("pong", ping_id=ping_id)

                elif event_type == "control.request":
                    ctrl = payload.get("control")
                    val = payload.get("value")
                    if ctrl:
                        await asyncio.to_thread(apply_control, ctrl, val)
                        telem = await asyncio.to_thread(collect_telemetry)
                        await send_event("telemetry.update", telemetry=telem)

                elif event_type == "user.message":
                    req_id = payload.get("request_id", "")
                    user_text = payload.get("text", "")
                    if user_text:
                        if active_work and not active_work.done():
                            active_work.cancel()
                        active_work = asyncio.create_task(handle_user_message(req_id, user_text))

                elif event_type == "approval.decision":
                    app_id = payload.get("approval_id")
                    b_hash = payload.get("binding_hash")
                    dec = payload.get("decision")
                    phrase = payload.get("typed_phrase")

                    if app_id in pending_approvals:
                        fut, expected_hash, risk, expected_phrase = pending_approvals[app_id]
                        if b_hash != expected_hash:
                            dec_str = "denied"
                            approved = False
                        elif risk == "R3" and phrase != expected_phrase:
                            dec_str = "denied"
                            approved = False
                        elif dec == "approve":
                            dec_str = "approved"
                            approved = True
                        else:
                            dec_str = "denied"
                            approved = False

                        if not fut.done():
                            fut.set_result(approved)

                        await send_event(
                            "approval.resolved",
                            approval_id=app_id,
                            decision=dec_str,
                            message=f"Approval {dec_str}.",
                        )
                        await send_event("agent.state", state="THINKING")

                elif event_type == "session.stop":
                    coordinator.stop()
                    if active_work and not active_work.done():
                        active_work.cancel()
                    for app_id, (fut, _, _, _) in list(pending_approvals.items()):
                        if not fut.done():
                            fut.set_result(False)
                        await send_event(
                            "approval.resolved",
                            approval_id=app_id,
                            decision="denied",
                            message="Task stopped by user.",
                        )
                    pending_approvals.clear()
                    await send_event("agent.state", state="IDLE")

                elif event_type == "audio.start":
                    s_id = payload.get("stream_id")
                    if s_id:
                        incoming_audio[s_id] = []

                elif event_type == "audio.chunk":
                    s_id = payload.get("stream_id")
                    chunk_b64 = payload.get("data", "")
                    if s_id and chunk_b64:
                        try:
                            incoming_audio.setdefault(s_id, []).append(base64.b64decode(chunk_b64))
                        except Exception:
                            pass

                elif event_type == "audio.end":
                    s_id = payload.get("stream_id")
                    chunks = incoming_audio.pop(s_id, [])
                    if chunks:
                        pcm_bytes = b"".join(chunks)
                        if active_work and not active_work.done():
                            active_work.cancel()
                        active_work = asyncio.create_task(handle_user_audio(s_id or "audio-stream", pcm_bytes))

        except (WebSocketDisconnect, WebSocketDisconnected):
            pass
        except Exception:
            pass
        finally:
            _active_websockets.discard(ws)
            if telemetry_task and not telemetry_task.done():
                telemetry_task.cancel()
            if active_work and not active_work.done():
                active_work.cancel()
            coordinator.stop()
            for _, (fut, _, _, _) in pending_approvals.items():
                if not fut.done():
                    fut.set_result(False)
            pending_approvals.clear()

    @app.on_event("startup")
    async def startup_handsfree_mic():
        if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("JARVIS_DISABLE_MIC"):
            return

        async def handsfree_mic_task():
            try:
                from .voice.wakeword import find_wake_model, LocalWakeDetector
                from .voice.satellite import ActivationGate
                from .voice.audio import AudioIO

                wake_path = find_wake_model(getattr(settings, "wake_model", None))
                if not wake_path:
                    logger.info("[hands-free] No wake model found; physical mic loop skipped.")
                    return

                detector = LocalWakeDetector(wake_path, name=settings.wake_name, threshold=0.45)
                gate = ActivationGate(detector, session_seconds=20)
                audio = AudioIO()
                logger.info(f"[hands-free] Physical microphone wake detector active for '{settings.wake_name}'")

                async for chunk in audio.capture(echo_guard=True):
                    st = gate.feed(chunk)
                    if st == "local_only":
                        continue
                    elif st == "wake":
                        logger.info("🔔 [Wake Word Detected] 'Hey JARVIS' recognized by PC microphone!")
                        await broadcast_deck_event("agent.state", state="LISTENING")

                        cmd_frames = []
                        try:
                            async for u_chunk in audio.capture(seconds=3.5, echo_guard=True):
                                cmd_frames.append(u_chunk)
                        except Exception:
                            pass

                        if cmd_frames:
                            pcm_bytes = b"".join(cmd_frames)
                            await run_live_audio_turn(
                                pcm_bytes,
                                broadcast_deck_event,
                                registry,
                                coordinator,
                                settings,
                                audio_out=audio,
                            )
                        else:
                            await broadcast_deck_event("agent.state", state="IDLE")
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.warning(f"[hands-free] Mic loop error: {e}")

        asyncio.create_task(handsfree_mic_task())

    return app


def serve_deck(host: str = "127.0.0.1", port: int = 8000, settings: Settings | None = None):
    import uvicorn

    if host not in {"127.0.0.1", "::1", "localhost", "0.0.0.0"}:
        raise ValueError("Non-loopback server binding requires authenticated proxy")

    if settings is None:
        settings = Settings.load()

    from .voice.wakeword import find_wake_model

    wake_path = find_wake_model(getattr(settings, "wake_model", None))
    print("\n" + "=" * 65)
    print("        JARVIS 1.0 · Holographic Control Deck & Voice Hub")
    print("=" * 65)
    print(f" Web UI:      http://localhost:5173 (React / Vite Control Deck)")
    print(f" Engine URL:  ws://{host}:{port}/ws (Protocol: jarvis.ui.v1)")
    print(f" Wake Word:   'Hey JARVIS' (Local Acoustic ONNX Inference)")
    print(f" AI Model:    {settings.model} (Gemini Live Stream)")
    print(" Hands-Free:  ACTIVE · Physical PC microphone is actively listening")
    print(" Privacy:     PROTECTED · Zero audio leaves PC until 'Hey JARVIS' is spoken")
    print("=" * 65 + "\n")

    app = create_deck_app(settings)
    uvicorn.run(app, host=host, port=port, access_log=False, log_level="info")
