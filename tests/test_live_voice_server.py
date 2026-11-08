from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from jarvis.models.gemini import GeminiSession
from jarvis.voice.satellite import ActivationGate
from jarvis.voice.evaluate import compute_metrics
from jarvis.voice.audio import AudioIO
from jarvis.server import create_app


def event(**kw):
    return NS(tool_call=None, tool_call_cancellation=None, server_content=None, **kw)


async def test_live_config_sdk_contract(core):
    live = GeminiSession("fixture-not-real", "gemini-3.8-live", core.registry, core)
    config = live.config()
    assert config.response_modalities == ["AUDIO"]
    for decl in config.tools[0].function_declarations:
        assert decl.behavior == "BLOCKING"
        assert decl.parameters_json_schema["additionalProperties"] is False
        assert core.registry.get(live.names[decl.name]).spec.effect == "read"
    await live.close()


async def test_live_function_response_correlation(core):
    live = GeminiSession("fixture-not-real", "gemini-3.8-live", core.registry, core)
    transport = NS(send_tool_response=AsyncMock())
    live.session = transport
    await live._call(NS(id="fc-123", name="system__get_time", args={}))
    response = transport.send_tool_response.call_args.kwargs["function_responses"][0]
    assert response.id == "fc-123" and response.name == "system__get_time"
    assert response.response["status"] == "succeeded"
    live.session = None
    await live.close()


async def test_live_unknown_tool_not_resolved_by_filename(core):
    live = GeminiSession("fixture-not-real", "gemini-3.8-live", core.registry, core)
    transport = NS(send_tool_response=AsyncMock())
    live.session = transport
    await live._call(NS(id="fc-123", name="__import__", args={"module": "os"}))
    res = transport.send_tool_response.call_args.kwargs["function_responses"][0]
    assert res.response["error_code"] == "CAPABILITY_NOT_FOUND"
    assert core.calls == 0
    live.session = None
    await live.close()


async def test_live_interrupted_audio_cleared(core):
    audio = AudioIO()
    audio.enqueue(b"stale pcm")
    live = GeminiSession("fixture-not-real", "gemini-3.8-live", core.registry, core, audio=audio)
    content = NS(
        interrupted=True,
        input_transcription=None,
        output_transcription=None,
        model_turn=None,
        turn_complete=False,
    )
    await live.handle_event(NS(tool_call_cancellation=None, tool_call=None, server_content=content))
    assert not audio.buffer
    await live.close()


async def test_live_receiver_disconnect_stops_dispatch(core):
    class Failing:
        async def receive(self):
            raise ConnectionError("private key error must not surface")
            yield

    output = []
    live = GeminiSession("fixture-not-real", "gemini-3.8-live", core.registry, core, emit=output.append)
    live.session = Failing()
    await live._receive()
    assert live.failed and core.gate.stopped
    assert "private key" not in "".join(output)
    live.session = None
    await live.close()


class Detector:
    def __init__(self):
        self.awake = False

    def feed(self, frame):
        return self.awake

    def reset(self):
        self.awake = False


def test_pre_wake_never_cloud_and_followups():
    detector = Detector()
    gate = ActivationGate(detector)
    assert gate.feed(b"ambient", now=10) == "local_only"
    detector.awake = True
    assert gate.feed(b"wake", now=11) == "wake"
    detector.awake = False
    assert gate.feed(b"followup", now=12) == "active"
    assert gate.feed(b"followup", now=60) == "active"
    assert gate.feed(b"ambient", now=72) == "local_only"
    gate.sleep()
    assert gate.feed(b"ambient", now=73) == "local_only"


def test_playback_bounded_and_closed():
    audio = AudioIO()
    audio.enqueue(b"old")
    audio.clear()
    assert not audio.buffer
    audio.enqueue(b"x" * 480001)
    assert not audio.buffer
    audio.close()
    audio.enqueue(b"late event")
    assert not audio.buffer


def test_evaluation_math_not_fake_results():
    metrics = compute_metrics(4, 1, 100, 9, [100] * 94 + [700] * 6)
    assert metrics["false_accepts_per_hour"] == 0.25
    assert metrics["false_reject_rate"] == 0.09
    assert metrics["p95_latency_ms"] == 700
    with pytest.raises(ValueError):
        compute_metrics(0, 0, 0, 0, [])


def test_server_requires_auth_and_has_no_execution():
    from fastapi.testclient import TestClient

    token = "s" * 40
    client = TestClient(create_app(token))
    assert client.get("/v1/health").status_code == 401
    headers = {"Authorization": "Bearer " + token}
    assert client.get("/v1/health", headers=headers).json()["remote_execution"] is False
    assert (
        client.post(
            "/v1/devices/heartbeat", headers=headers, json={"device_id": "fixture", "state": "local_only"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/v1/devices/heartbeat",
            headers=headers,
            json={"device_id": "fixture", "state": "local_only", "token": "not-accepted"},
        ).status_code
        == 422
    )
    assert client.post("/v1/tools/execute", headers=headers).status_code == 404
    assert len(client.get("/v1/devices", headers=headers).json()["devices"]) == 1


async def test_secure_server_url_no_http():
    from jarvis.voice.connection import heartbeat_loop

    with pytest.raises(ValueError):
        await heartbeat_loop("http://example.test", "secret", lambda: "local_only", "test")


async def test_interrupted_event_cannot_requeue_old_audio(core):
    audio = AudioIO()
    live = GeminiSession("fixture", "gemini-3.8-live", core.registry, core, audio=audio)
    content = NS(
        interrupted=True,
        input_transcription=None,
        output_transcription=None,
        model_turn=NS(parts=[NS(inline_data=NS(data=b"stale"))]),
        turn_complete=False,
    )
    await live.handle_event(NS(tool_call_cancellation=None, tool_call=None, server_content=content))
    assert not audio.buffer
    await live.close()
