import asyncio
from types import SimpleNamespace

import pytest

import reachy_mini_openclaw.openclaw_bridge as bridge_module
from reachy_mini_openclaw.openclaw_bridge import OpenClawBridge


@pytest.mark.asyncio
async def test_chat_returns_trace_metadata_from_final_event(monkeypatch):
    bridge = OpenClawBridge(agent_id="agent", timeout=1)
    bridge._connected = True

    async def send_request(method, params, timeout=None):
        return {"ok": True, "payload": {"runId": "run-1"}}

    monkeypatch.setattr(bridge, "_send_request", send_request)

    task = asyncio.create_task(bridge.chat("hello", timeout=1, trace_id="trace-test"))

    for _ in range(20):
        if "run-1" in bridge._run_events:
            break
        await asyncio.sleep(0)

    await bridge._run_events["run-1"].put(
        {
            "event": "chat",
            "payload": {
                "state": "final",
                "message": {
                    "content": [{"type": "text", "text": "hi there"}],
                },
            },
        }
    )

    response = await task

    assert response.content == "hi there"
    assert response.trace_id == "trace-test"
    assert response.run_id == "run-1"
    assert response.idempotency_key
    assert response.elapsed_ms is not None


@pytest.mark.asyncio
async def test_chat_replays_event_that_arrives_before_run_queue(monkeypatch):
    bridge = OpenClawBridge(agent_id="agent", timeout=1)
    bridge._connected = True

    async def send_request(method, params, timeout=None):
        await bridge._dispatch(
            {
                "type": "event",
                "event": "chat",
                "payload": {
                    "runId": "run-early",
                    "state": "final",
                    "message": {
                        "content": [{"type": "text", "text": "early hi"}],
                    },
                },
            }
        )
        return {"ok": True, "payload": {"runId": "run-early"}}

    monkeypatch.setattr(bridge, "_send_request", send_request)

    response = await bridge.chat("hello", timeout=1, trace_id="trace-test")

    assert response.content == "early hi"
    assert response.run_id == "run-early"
    assert bridge._run_event_backlog == {}


@pytest.mark.asyncio
async def test_chat_timeout_includes_trace_metadata(monkeypatch):
    bridge = OpenClawBridge(agent_id="agent", timeout=1)
    bridge._connected = True

    async def send_request(method, params, timeout=None):
        return {"ok": True, "payload": {"runId": "run-1"}}

    monkeypatch.setattr(bridge, "_send_request", send_request)

    response = await bridge.chat("hello", timeout=0.01, trace_id="trace-test")

    assert response.error == "Response timeout"
    assert response.trace_id == "trace-test"
    assert response.run_id == "run-1"
    assert response.idempotency_key
    assert response.elapsed_ms is not None


@pytest.mark.asyncio
async def test_chat_timeout_uses_absolute_deadline_for_intermediate_events(monkeypatch):
    bridge = OpenClawBridge(agent_id="agent", timeout=1)
    bridge._connected = True
    monotonic_time = SimpleNamespace(value=100.0)
    real_wait_for = asyncio.wait_for

    async def send_request(method, params, timeout=None):
        return {"ok": True, "payload": {"runId": "run-1"}}

    async def wait_for_and_advance_clock(awaitable, timeout):
        result = await real_wait_for(awaitable, timeout=0.01)
        monotonic_time.value = 111.0
        return result

    monkeypatch.setattr(bridge, "_send_request", send_request)
    monkeypatch.setattr(bridge_module, "time", SimpleNamespace(monotonic=lambda: monotonic_time.value))
    monkeypatch.setattr(bridge_module.asyncio, "wait_for", wait_for_and_advance_clock)

    task = asyncio.create_task(bridge.chat("hello", timeout=10, trace_id="trace-test"))

    for _ in range(20):
        if "run-1" in bridge._run_events:
            break
        await asyncio.sleep(0)

    await bridge._run_events["run-1"].put(
        {
            "event": "agent",
            "payload": {
                "stream": "lifecycle",
                "data": {"phase": "thinking"},
            },
        }
    )

    response = await task

    assert response.error == "Response timeout"
    assert response.run_id == "run-1"
    assert response.elapsed_ms == 11000


@pytest.mark.asyncio
async def test_chat_absolute_deadline_returns_partial_assistant_text(monkeypatch):
    bridge = OpenClawBridge(agent_id="agent", timeout=1)
    bridge._connected = True

    async def send_request(method, params, timeout=None):
        return {"ok": True, "payload": {"runId": "run-1"}}

    monkeypatch.setattr(bridge, "_send_request", send_request)

    task = asyncio.create_task(bridge.chat("hello", timeout=0.03, trace_id="trace-test"))

    for _ in range(20):
        if "run-1" in bridge._run_events:
            break
        await asyncio.sleep(0)

    await bridge._run_events["run-1"].put(
        {
            "event": "agent",
            "payload": {
                "stream": "assistant",
                "data": {"text": "partial hello"},
            },
        }
    )

    response = await task

    assert response.content == "partial hello"
    assert response.error is None
    assert response.run_id == "run-1"


@pytest.mark.asyncio
async def test_chat_ack_error_includes_trace_metadata(monkeypatch):
    bridge = OpenClawBridge(agent_id="agent", timeout=1)
    bridge._connected = True

    async def send_request(method, params, timeout=None):
        return {
            "ok": False,
            "error": {"code": "BAD", "message": "nope"},
        }

    monkeypatch.setattr(bridge, "_send_request", send_request)

    response = await bridge.chat("hello", trace_id="trace-test")

    assert response.error == "BAD: nope"
    assert response.trace_id == "trace-test"
    assert response.idempotency_key
    assert response.elapsed_ms is not None
