import asyncio

import pytest

from reachy_mini_openclaw.openclaw_bridge import OpenClawBridge


@pytest.mark.asyncio
async def test_chat_returns_trace_metadata_from_final_event(monkeypatch):
    bridge = OpenClawBridge(agent_id="agent", timeout=1)
    bridge._connected = True

    async def send_request(method, params, timeout=None):
        return {"ok": True, "payload": {"runId": "run-1"}}

    monkeypatch.setattr(bridge, "_send_request", send_request)

    task = asyncio.create_task(
        bridge.chat("hello", timeout=1, trace_id="trace-test")
    )

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
