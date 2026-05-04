from types import SimpleNamespace

import pytest

from reachy_mini_openclaw import realtime
from reachy_mini_openclaw.openai_realtime import OpenAIRealtimeHandler


def test_create_realtime_handler_uses_openai_by_default(monkeypatch):
    monkeypatch.setattr(realtime.config, "REALTIME_PROVIDER", "openai")

    handler = realtime.create_realtime_handler(SimpleNamespace(), None)

    assert isinstance(handler, OpenAIRealtimeHandler)


def test_create_realtime_handler_uses_gemini(monkeypatch):
    from reachy_mini_openclaw.gemini_live import GeminiLiveHandler

    monkeypatch.setattr(realtime.config, "REALTIME_PROVIDER", "gemini")

    handler = realtime.create_realtime_handler(SimpleNamespace(), None)

    assert isinstance(handler, GeminiLiveHandler)


def test_create_realtime_handler_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(realtime.config, "REALTIME_PROVIDER", "bogus")

    with pytest.raises(ValueError, match="Unsupported realtime provider"):
        realtime.create_realtime_handler(SimpleNamespace(), None)
