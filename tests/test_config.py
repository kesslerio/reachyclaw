from reachy_mini_openclaw.config import Config


def clear_provider_env(monkeypatch):
    for name in [
        "REALTIME_PROVIDER",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
        "GEMINI_INPUT_SUPPRESSION_TIMEOUT",
        "OPENCLAW_VOICE_TIMEOUT",
        "REACHYCLAW_TRACE_LATENCY",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_default_provider_is_openai_and_requires_openai_key(monkeypatch):
    clear_provider_env(monkeypatch)

    cfg = Config()

    assert cfg.REALTIME_PROVIDER == "openai"
    assert cfg.validate() == ["OPENAI_API_KEY is required"]


def test_openai_provider_accepts_openai_key(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("REALTIME_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")

    cfg = Config()

    assert cfg.validate() == []


def test_gemini_provider_requires_gemini_key(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("REALTIME_PROVIDER", "gemini")

    cfg = Config()

    assert cfg.validate() == ["GEMINI_API_KEY is required"]


def test_gemini_provider_accepts_gemini_key(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("REALTIME_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    cfg = Config()

    assert cfg.GEMINI_MODEL == "gemini-3.1-flash-live-preview"
    assert cfg.validate() == []


def test_unknown_realtime_provider_is_rejected(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("REALTIME_PROVIDER", "bogus")

    cfg = Config()

    assert cfg.validate() == ["REALTIME_PROVIDER must be one of: gemini, openai"]


def test_voice_timeout_defaults_to_25_seconds(monkeypatch):
    clear_provider_env(monkeypatch)

    cfg = Config()

    assert cfg.OPENCLAW_VOICE_TIMEOUT == 25.0
    assert cfg.GEMINI_INPUT_SUPPRESSION_TIMEOUT == 12.0


def test_voice_timeout_is_validated(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("REALTIME_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENCLAW_VOICE_TIMEOUT", "0")

    cfg = Config()

    assert cfg.validate() == ["OPENCLAW_VOICE_TIMEOUT must be greater than 0"]


def test_gemini_input_suppression_timeout_is_validated(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("REALTIME_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("GEMINI_INPUT_SUPPRESSION_TIMEOUT", "0")

    cfg = Config()

    assert cfg.validate() == ["GEMINI_INPUT_SUPPRESSION_TIMEOUT must be greater than 0"]


def test_latency_tracing_accepts_common_true_values(monkeypatch):
    clear_provider_env(monkeypatch)
    monkeypatch.setenv("REACHYCLAW_TRACE_LATENCY", "yes")

    cfg = Config()

    assert cfg.ENABLE_LATENCY_TRACING is True
