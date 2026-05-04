from types import SimpleNamespace

import numpy as np
import pytest

from reachy_mini_openclaw.gemini_live import GEMINI_OUTPUT_SAMPLE_RATE, GeminiLiveHandler, is_normal_gemini_close
from reachy_mini_openclaw.openclaw_bridge import OpenClawResponse


class DummyMovementManager:
    def __init__(self):
        self.processing_states = []

    def set_processing(self, enabled):
        self.processing_states.append(enabled)

    def set_listening(self, enabled):
        pass


class DummyHeadWobbler:
    def __init__(self):
        self.feed_values = []
        self.reset_count = 0

    def feed(self, value):
        self.feed_values.append(value)

    def reset(self):
        self.reset_count += 1


class DummyBridge:
    is_connected = True

    def __init__(self):
        self.queries = []

    async def chat(
        self,
        query,
        image_b64=None,
        system_context=None,
        timeout=None,
        trace_id=None,
    ):
        self.queries.append((query, image_b64, system_context, timeout, trace_id))
        return OpenClawResponse(content="[EMOTION:happy] hello there")

    async def sync_conversation(self, user_message, assistant_response):
        self.synced = (user_message, assistant_response)


def make_handler():
    deps = SimpleNamespace(
        movement_manager=DummyMovementManager(),
        head_wobbler=DummyHeadWobbler(),
        camera_worker=None,
    )
    bridge = DummyBridge()
    return GeminiLiveHandler(deps, bridge), bridge


def test_normal_gemini_close_detects_google_api_close_code():
    error = Exception("1000 None.")
    error.status_code = 1000

    assert is_normal_gemini_close(error)


def test_live_config_includes_audio_transcription_voice_and_tool():
    handler, _bridge = make_handler()

    live_config = handler._build_live_config("relay instructions")

    assert live_config["response_modalities"] == ["AUDIO"]
    assert live_config["system_instruction"] == "relay instructions"
    assert live_config["input_audio_transcription"] == {}
    assert live_config["output_audio_transcription"] == {}
    assert live_config["speech_config"]["voice_config"]["prebuilt_voice_config"]["voice_name"]
    assert live_config["tools"][0]["function_declarations"][0]["name"] == "ask_openclaw"


@pytest.mark.asyncio
async def test_gemini_tool_call_invokes_openclaw_bridge():
    handler, bridge = make_handler()

    result = await handler._handle_gemini_tool_call(
        "ask_openclaw",
        {"query": "hi"},
        trace_id="trace-test",
    )

    assert result == {"response": "hello there", "trace_id": "trace-test"}
    assert bridge.queries[0][0] == "hi"
    assert bridge.queries[0][3] == 25.0
    assert bridge.queries[0][4] == "trace-test"


@pytest.mark.asyncio
async def test_queue_audio_emits_24khz_pcm_frame():
    handler, _bridge = make_handler()
    audio = np.array([1, -1, 2, -2], dtype=np.int16)

    await handler._queue_audio(audio.tobytes())

    output = await handler.output_queue.get()
    assert output[0] == GEMINI_OUTPUT_SAMPLE_RATE
    assert output[1].shape == (1, 4)


@pytest.mark.asyncio
async def test_output_transcription_is_emitted_and_syncable():
    handler, _bridge = make_handler()
    handler._last_user_message = "hello"

    await handler._handle_output_transcription(SimpleNamespace(text="hi", finished=False))
    await handler._handle_output_transcription(SimpleNamespace(text=" there", finished=True))

    output = await handler.output_queue.get()
    assert output.args[0] == {"role": "assistant", "content": "hi there"}
    assert handler._last_assistant_response == "hi there"
