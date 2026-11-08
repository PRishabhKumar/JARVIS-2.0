from __future__ import annotations

import asyncio
from uuid import uuid4
import pytest
from jarvis.contracts import ToolCall, Risk
from jarvis.policy import PolicyGate


@pytest.fixture
def mutating_core(core):
    core.context = core.context.model_copy(update={"maximum_effect": "local_write"})
    core.gate.confirm = lambda _: asyncio.sleep(0, result=True)
    return core


@pytest.mark.asyncio
async def test_display_brightness_and_resolution(mutating_core):
    res_res = await mutating_core.dispatch(
        ToolCall(call_id="disp_res", name="display.get_resolution", arguments={})
    )
    assert res_res.status in ("succeeded", "unsupported")
    if res_res.status == "succeeded":
        assert "width" in res_res.structured_data
        assert "height" in res_res.structured_data

    res_b = await mutating_core.dispatch(
        ToolCall(call_id="disp_b_get", name="display.get_brightness", arguments={})
    )
    assert res_b.status in ("succeeded", "unsupported")
    if res_b.status == "succeeded":
        assert 0 <= res_b.structured_data["brightness"] <= 100


@pytest.mark.asyncio
async def test_wifi_status(mutating_core):
    res = await mutating_core.dispatch(
        ToolCall(call_id="wifi_stat", name="wifi.get_status", arguments={})
    )
    assert res.status in ("succeeded", "unsupported")
    if res.status == "succeeded":
        assert "enabled" in res.structured_data
        assert "state" in res.structured_data


@pytest.mark.asyncio
async def test_bluetooth_status(mutating_core):
    res = await mutating_core.dispatch(
        ToolCall(call_id="bt_stat", name="bluetooth.get_status", arguments={})
    )
    assert res.status in ("succeeded", "unsupported")
    if res.status == "succeeded":
        assert "enabled" in res.structured_data
        assert "device_count" in res.structured_data


@pytest.mark.asyncio
async def test_hotspot_status(mutating_core):
    res = await mutating_core.dispatch(
        ToolCall(call_id="hs_stat", name="hotspot.get_status", arguments={})
    )
    assert res.status in ("succeeded", "unsupported")
    if res.status == "succeeded":
        assert "enabled" in res.structured_data
        assert "state" in res.structured_data


@pytest.mark.asyncio
async def test_confirmation_threshold_skips_r1_prompts(core):
    # Configure threshold = R2 and allow local_write
    core.context = core.context.model_copy(update={"maximum_effect": "local_write"})
    
    prompted = []
    async def recording_confirm(req):
        prompted.append(req.tool_id)
        return True

    core.gate = PolicyGate(recording_confirm, threshold=Risk.R2)

    # 1. audio.set_volume is Risk.R1 -> should NOT trigger confirm prompt!
    res_r1 = await core.dispatch(
        ToolCall(call_id=uuid4().hex, name="audio.get_volume", arguments={})
    )
    cur_vol = res_r1.structured_data.get("volume", 50) if res_r1.status == "succeeded" else 50

    res_set = await core.dispatch(
        ToolCall(call_id=uuid4().hex, name="audio.set_volume", arguments={"level": cur_vol})
    )
    assert res_set.status in ("succeeded", "failed", "unsupported")
    assert "audio.set_volume" not in prompted, "Risk.R1 tool should not have prompted when threshold is R2"

    # 2. process.terminate is Risk.R2 -> MUST trigger confirm prompt!
    res_r2 = await core.dispatch(
        ToolCall(call_id=uuid4().hex, name="process.terminate", arguments={"pid": 999999})
    )
    assert res_r2 is not None
    # The prompt was recorded!
    assert "process.terminate" in prompted, "Risk.R2 tool must prompt when threshold is R2"

