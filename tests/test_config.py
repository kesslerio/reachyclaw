from reachy_mini_openclaw.config import Config


def clear_provider_env(monkeypatch):
    for name in [
        "REALTIME_PROVIDER",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
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
