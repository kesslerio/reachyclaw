"""Gemini Live API handler as voice relay for OpenClaw."""

import asyncio
import base64
import json
import logging
import random
import time
from typing import Any, Final, Literal

import numpy as np
from fastrtc import AdditionalOutputs, wait_for_item
from numpy.typing import NDArray
from websockets.exceptions import ConnectionClosedError

from reachy_mini_openclaw.audio import pcm16_bytes, pcm16_frame
from reachy_mini_openclaw.config import config
from reachy_mini_openclaw.openai_realtime import (
    ROBOT_BODY_INSTRUCTIONS,
    OpenAIRealtimeHandler,
)
from reachy_mini_openclaw.tools.core_tools import ToolDependencies, dispatch_tool_call

logger = logging.getLogger(__name__)

GEMINI_INPUT_SAMPLE_RATE: Final[Literal[16000]] = 16000
GEMINI_OUTPUT_SAMPLE_RATE: Final[Literal[24000]] = 24000


def is_normal_gemini_close(error: Exception) -> bool:
    """Return True when google-genai wraps a clean WebSocket close as an APIError."""
    status_code = getattr(error, "status_code", None) or getattr(error, "code", None)
    return status_code == 1000 or str(error).startswith("1000 ")


class GeminiLiveHandler(OpenAIRealtimeHandler):
    """Voice relay handler backed by Gemini Live.

    This keeps the same FastRTC contract as the OpenAI handler while adapting
    Gemini Live's session protocol, tool responses, and audio input rate.
    """

    def __init__(
        self,
        deps: ToolDependencies,
        openclaw_bridge: Any | None = None,
        gradio_mode: bool = False,
    ):
        super().__init__(deps, openclaw_bridge, gradio_mode)
        self.client: Any = None
        self.connection: Any = None
        self._types: Any = None
        self._assistant_transcript_parts: list[str] = []
        self._input_suppressed_until = 0.0
        self._next_input_trace_at = 0.0
        self._input_sent_frames = 0
        self._input_suppressed_frames = 0
        self._audio_chunks_queued = 0

    def copy(self) -> "GeminiLiveHandler":
        """Create a copy of the handler (required by fastrtc)."""
        return GeminiLiveHandler(self.deps, self.openclaw_bridge, self.gradio_mode)

    def _build_function_declarations(self) -> list[dict[str, Any]]:
        """Build Gemini Live function declarations for the session."""
        if self.openclaw_bridge is None:
            return []

        return [
            {
                "name": "ask_openclaw",
                "description": (
                    "MANDATORY: You MUST call this tool for EVERY user message before responding. "
                    "This is the OpenClaw AI agent - the real brain. Send the user's full message "
                    "as the query. Speak the returned response EXACTLY and VERBATIM. Never answer "
                    "without calling this tool first. Never generate your own text - only speak "
                    "what this tool returns."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The question or request to send to OpenClaw",
                        },
                        "include_image": {
                            "type": "boolean",
                            "description": "Whether to include current camera image for visual queries",
                        },
                    },
                    "required": ["query"],
                },
            }
        ]

    def _build_live_config(self, system_instructions: str) -> dict[str, Any]:
        """Build Gemini Live session configuration."""
        live_config: dict[str, Any] = {
            "response_modalities": ["AUDIO"],
            "system_instruction": system_instructions,
            "input_audio_transcription": {},
            "output_audio_transcription": {},
        }

        declarations = self._build_function_declarations()
        if declarations:
            live_config["tools"] = [{"function_declarations": declarations}]

        if config.GEMINI_VOICE:
            live_config["speech_config"] = {
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": config.GEMINI_VOICE},
                },
            }

        return live_config

    async def start_up(self) -> None:
        """Start the handler and connect to Gemini Live."""
        api_key = config.GEMINI_API_KEY
        if not api_key:
            logger.error("GEMINI_API_KEY not configured")
            raise ValueError("GEMINI_API_KEY required")

        from google import genai
        from google.genai import types

        self.client = genai.Client(api_key=api_key)
        self._types = types
        self.start_time = asyncio.get_event_loop().time()
        self.last_activity_time = self.start_time

        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                await self._run_session()
                return
            except ConnectionClosedError as e:
                logger.warning("Gemini Live WebSocket closed unexpectedly (attempt %d/%d): %s", attempt, max_attempts, e)
                if attempt < max_attempts:
                    delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    logger.info("Retrying Gemini Live in %.1f seconds...", delay)
                    await asyncio.sleep(delay)
                    continue
                raise
            finally:
                self.connection = None
                try:
                    self._connected_event.clear()
                except Exception:
                    pass

    async def _run_session(self) -> None:
        """Run a single Gemini Live session."""
        model = config.GEMINI_MODEL
        logger.info("Connecting to Gemini Live API with model: %s", model)

        system_instructions = await self._build_system_instructions()
        live_config = self._build_live_config(system_instructions)

        async with self.client.aio.live.connect(model=model, config=live_config) as session:
            logger.info("Gemini Live session configured with %d tools", len(live_config.get("tools", [])))

            self.connection = session
            self._connected_event.set()

            try:
                async for response in session.receive():
                    await self._handle_response(response)
            except Exception as e:
                if self._shutdown_requested and is_normal_gemini_close(e):
                    logger.debug("Gemini Live session closed cleanly")
                    return
                raise

    async def _build_system_instructions(self) -> str:
        """Build system instructions for the Gemini voice relay."""
        return ROBOT_BODY_INSTRUCTIONS

    async def _handle_response(self, response: Any) -> None:
        """Handle a Gemini Live server message."""
        audio_data = getattr(response, "data", None)
        audio_queued = False
        if audio_data is not None:
            await self._queue_audio(audio_data)
            audio_queued = True

        text = getattr(response, "text", None)
        if text:
            logger.debug("Gemini text response: %s", text)

        tool_call = getattr(response, "tool_call", None)
        if tool_call is not None:
            await self._handle_tool_call(tool_call)

        server_content = getattr(response, "server_content", None)
        if server_content is not None:
            await self._handle_server_content(server_content, audio_queued)

    async def _handle_server_content(self, server_content: Any, audio_queued: bool) -> None:
        """Handle Gemini server content events."""
        if getattr(server_content, "interrupted", False):
            await self._handle_interrupted()

        input_transcription = getattr(server_content, "input_transcription", None)
        if input_transcription is not None:
            await self._handle_input_transcription(input_transcription)

        output_transcription = getattr(server_content, "output_transcription", None)
        if output_transcription is not None:
            await self._handle_output_transcription(output_transcription)

        model_turn = getattr(server_content, "model_turn", None)
        if model_turn is not None and not audio_queued:
            for part in getattr(model_turn, "parts", []) or []:
                inline_data = getattr(part, "inline_data", None)
                if inline_data is not None:
                    await self._queue_audio(getattr(inline_data, "data", b""))

        if getattr(server_content, "turn_complete", False):
            await self._handle_turn_complete()

    async def _handle_input_transcription(self, transcription: Any) -> None:
        """Handle user audio transcription from Gemini Live."""
        transcript = getattr(transcription, "text", "") or ""
        finished = getattr(transcription, "finished", True)
        if not transcript.strip() or not finished:
            return

        logger.info("User: %s", transcript)
        self._last_user_message = transcript
        await self.output_queue.put(AdditionalOutputs({"role": "user", "content": transcript}))

    async def _handle_output_transcription(self, transcription: Any) -> None:
        """Handle assistant audio transcription from Gemini Live."""
        text = getattr(transcription, "text", "") or ""
        if text:
            self._assistant_transcript_parts.append(text)

        if getattr(transcription, "finished", False):
            await self._emit_assistant_transcript()

    async def _emit_assistant_transcript(self) -> None:
        """Emit accumulated assistant transcript to logs, UI, and OpenClaw sync state."""
        response_text = "".join(self._assistant_transcript_parts).strip()
        self._assistant_transcript_parts = []
        if not response_text:
            return

        logger.info("Assistant: %s", response_text[:100] if len(response_text) > 100 else response_text)
        self._last_assistant_response = response_text
        self._input_suppressed_until = 0.0
        await self.output_queue.put(AdditionalOutputs({"role": "assistant", "content": response_text}))

    async def _handle_turn_complete(self) -> None:
        """Handle completion of a Gemini model turn."""
        self._speaking = False
        self._input_suppressed_until = 0.0
        self.deps.movement_manager.set_processing(False)
        if self.deps.head_wobbler is not None:
            self.deps.head_wobbler.reset()
        await self._emit_assistant_transcript()
        await self._sync_to_openclaw()
        logger.debug("Gemini response completed")

    async def _handle_interrupted(self) -> None:
        """Handle Gemini interruption events by clearing queued audio."""
        self._speaking = False
        self._input_suppressed_until = 0.0
        self.deps.movement_manager.set_processing(False)
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        if self.deps.head_wobbler is not None:
            self.deps.head_wobbler.reset()
        logger.info("Gemini generation interrupted")

    async def _queue_audio(self, data: bytes | str) -> None:
        """Queue Gemini audio output for robot playback."""
        self.deps.movement_manager.set_processing(False)

        if isinstance(data, str):
            audio_bytes = base64.b64decode(data)
        else:
            audio_bytes = data

        if not audio_bytes:
            return

        self._audio_chunks_queued += 1
        if config.ENABLE_LATENCY_TRACING:
            logger.info(
                "Voice trace gemini_audio_queued chunk=%d bytes=%d samples=%d",
                self._audio_chunks_queued,
                len(audio_bytes),
                len(audio_bytes) // 2,
            )

        if self.deps.head_wobbler is not None:
            self.deps.head_wobbler.feed(base64.b64encode(audio_bytes).decode("utf-8"))

        self.last_activity_time = asyncio.get_event_loop().time()
        await self.output_queue.put((GEMINI_OUTPUT_SAMPLE_RATE, pcm16_frame(audio_bytes)))

    async def _handle_tool_call(self, tool_call: Any) -> None:
        """Handle function calls from Gemini Live."""
        function_calls = getattr(tool_call, "function_calls", []) or []
        if not function_calls:
            return

        self._suppress_input_for_response()
        self.deps.movement_manager.set_processing(True)
        function_responses = []

        for function_call in function_calls:
            name = getattr(function_call, "name", "")
            args = getattr(function_call, "args", {}) or {}
            call_id = getattr(function_call, "id", None)
            trace_id = self._new_trace_id("gemini", name)
            started_at = time.monotonic()

            logger.info("Gemini tool call: %s(%s)", name, str(args)[:80])
            if trace_id:
                logger.info("Voice trace tool_start traceId=%s provider=gemini tool=%s", trace_id, name)

            try:
                result = await self._handle_gemini_tool_call(name, args, trace_id=trace_id)
            except Exception as e:
                logger.error("Gemini tool '%s' failed: %s", name, e)
                result = {"error": str(e)}
            finally:
                if trace_id:
                    logger.info(
                        "Voice trace tool_done traceId=%s provider=gemini tool=%s elapsedMs=%d",
                        trace_id,
                        name,
                        int((time.monotonic() - started_at) * 1000),
                    )

            function_responses.append(
                self._types.FunctionResponse(
                    id=call_id,
                    name=name,
                    response=result,
                )
            )

        if self.connection:
            response_started_at = time.monotonic()
            await self.connection.send_tool_response(function_responses=function_responses)
            if config.ENABLE_LATENCY_TRACING:
                logger.info(
                    "Voice trace gemini_tool_responses_sent count=%d elapsedMs=%d",
                    len(function_responses),
                    int((time.monotonic() - response_started_at) * 1000),
                )

    async def _handle_gemini_tool_call(
        self,
        name: str,
        args: dict[str, Any],
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch a Gemini function call."""
        args_json = json.dumps(args)
        if name == "ask_openclaw":
            return await self._handle_openclaw_query(args_json, trace_id=trace_id)
        return await dispatch_tool_call(name, args_json, self.deps)

    async def receive(self, frame: tuple[int, NDArray]) -> None:
        """Receive audio from the robot microphone and send it to Gemini Live."""
        if not self.connection or self._types is None:
            return
        if self._is_input_suppressed():
            self._input_suppressed_frames += 1
            self._trace_input_frames("suppressed")
            return

        input_sr, audio = frame
        try:
            audio_bytes = pcm16_bytes(audio, input_sr, GEMINI_INPUT_SAMPLE_RATE)
            if not audio_bytes:
                return
            await self.connection.send_realtime_input(
                audio=self._types.Blob(
                    data=audio_bytes,
                    mime_type=f"audio/pcm;rate={GEMINI_INPUT_SAMPLE_RATE}",
                )
            )
            self._input_sent_frames += 1
            self._trace_input_frames("sent")
        except Exception as e:
            logger.debug("Failed to send Gemini audio: %s", e)

    def _suppress_input_for_response(self) -> None:
        """Pause mic streaming while Gemini is waiting on or speaking a response."""
        self._input_suppressed_until = time.monotonic() + config.OPENCLAW_VOICE_TIMEOUT + 10.0

    def _is_input_suppressed(self) -> bool:
        if not self._input_suppressed_until:
            return False
        if time.monotonic() < self._input_suppressed_until:
            return True
        self._input_suppressed_until = 0.0
        return False

    def _trace_input_frames(self, state: str) -> None:
        if not config.ENABLE_LATENCY_TRACING:
            return
        now = time.monotonic()
        if now < self._next_input_trace_at:
            return
        self._next_input_trace_at = now + 5.0
        logger.info(
            "Voice trace gemini_mic_frames state=%s sent=%d suppressed=%d suppressionActive=%s",
            state,
            self._input_sent_frames,
            self._input_suppressed_frames,
            bool(self._input_suppressed_until),
        )

    async def emit(self) -> tuple[int, NDArray[np.int16]] | AdditionalOutputs | None:
        """Get the next output (audio or transcript)."""
        return await wait_for_item(self.output_queue)

    async def shutdown(self) -> None:
        """Shutdown the handler."""
        self._shutdown_requested = True

        if self.connection:
            try:
                await self.connection.close()
            except Exception as e:
                logger.debug("Gemini connection close: %s", e)
            self.connection = None

        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
