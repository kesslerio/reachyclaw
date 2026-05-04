"""Realtime voice provider selection."""

import logging
from typing import Any

from fastrtc import AsyncStreamHandler

from reachy_mini_openclaw.config import config
from reachy_mini_openclaw.tools.core_tools import ToolDependencies

logger = logging.getLogger(__name__)


def create_realtime_handler(
    deps: ToolDependencies,
    openclaw_bridge: Any | None = None,
    gradio_mode: bool = False,
) -> AsyncStreamHandler:
    """Create the configured realtime voice handler."""
    provider = config.REALTIME_PROVIDER

    if provider == "openai":
        from reachy_mini_openclaw.openai_realtime import OpenAIRealtimeHandler

        logger.info("Using OpenAI realtime provider with model: %s", config.OPENAI_MODEL)
        return OpenAIRealtimeHandler(deps, openclaw_bridge, gradio_mode)

    if provider == "gemini":
        from reachy_mini_openclaw.gemini_live import GeminiLiveHandler

        logger.info("Using Gemini Live provider with model: %s", config.GEMINI_MODEL)
        return GeminiLiveHandler(deps, openclaw_bridge, gradio_mode)

    valid = "gemini, openai"
    raise ValueError(f"Unsupported realtime provider {provider!r}; expected one of: {valid}")
