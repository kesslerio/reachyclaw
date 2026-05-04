"""Configuration management for Reachy Mini OpenClaw.

Handles environment variables and configuration settings for the application.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")

VALID_REALTIME_PROVIDERS = {"openai", "gemini"}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Realtime voice provider
    REALTIME_PROVIDER: str = field(default_factory=lambda: os.getenv("REALTIME_PROVIDER", "openai").strip().lower())

    # OpenAI Configuration
    OPENAI_API_KEY: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))
    OPENAI_MODEL: str = field(default_factory=lambda: os.getenv("OPENAI_MODEL", "gpt-4o-realtime-preview-2024-12-17"))
    OPENAI_VOICE: str = field(default_factory=lambda: os.getenv("OPENAI_VOICE", "cedar"))

    # Gemini Live Configuration
    GEMINI_API_KEY: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", ""))
    GEMINI_MODEL: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview"))
    GEMINI_VOICE: str = field(default_factory=lambda: os.getenv("GEMINI_VOICE", "Kore"))

    # OpenClaw Gateway Configuration
    OPENCLAW_GATEWAY_URL: str = field(default_factory=lambda: os.getenv("OPENCLAW_GATEWAY_URL", "ws://localhost:18789"))
    OPENCLAW_TOKEN: str | None = field(default_factory=lambda: os.getenv("OPENCLAW_TOKEN"))
    OPENCLAW_AGENT_ID: str = field(default_factory=lambda: os.getenv("OPENCLAW_AGENT_ID", "main"))
    # Session key for OpenClaw - uses "main" to share context with WhatsApp and other channels
    # Format: agent:<agent_id>:<session_key>, but we only need the session key part here
    OPENCLAW_SESSION_KEY: str = field(default_factory=lambda: os.getenv("OPENCLAW_SESSION_KEY", "main"))
    OPENCLAW_VOICE_TIMEOUT: float = field(default_factory=lambda: _env_float("OPENCLAW_VOICE_TIMEOUT", 25.0))
    GEMINI_INPUT_SUPPRESSION_TIMEOUT: float = field(default_factory=lambda: _env_float("GEMINI_INPUT_SUPPRESSION_TIMEOUT", 12.0))
    ENABLE_LATENCY_TRACING: bool = field(default_factory=lambda: _env_bool("REACHYCLAW_TRACE_LATENCY", False))

    # Robot Configuration
    ROBOT_NAME: str | None = field(default_factory=lambda: os.getenv("ROBOT_NAME"))

    # Feature Flags
    ENABLE_OPENCLAW_TOOLS: bool = field(default_factory=lambda: os.getenv("ENABLE_OPENCLAW_TOOLS", "true").lower() == "true")
    ENABLE_CAMERA: bool = field(default_factory=lambda: os.getenv("ENABLE_CAMERA", "true").lower() == "true")
    ENABLE_FACE_TRACKING: bool = field(default_factory=lambda: os.getenv("ENABLE_FACE_TRACKING", "true").lower() == "true")

    # Face Tracking Configuration
    # Options: "yolo", "mediapipe", or None for auto-detect
    HEAD_TRACKER_TYPE: str | None = field(default_factory=lambda: os.getenv("HEAD_TRACKER_TYPE", "yolo"))

    # Local Vision Processing
    ENABLE_LOCAL_VISION: bool = field(default_factory=lambda: os.getenv("ENABLE_LOCAL_VISION", "false").lower() == "true")
    LOCAL_VISION_MODEL: str = field(default_factory=lambda: os.getenv("LOCAL_VISION_MODEL", "HuggingFaceTB/SmolVLM2-256M-Video-Instruct"))
    VISION_DEVICE: str = field(default_factory=lambda: os.getenv("VISION_DEVICE", "auto"))  # "auto", "cuda", "mps", "cpu"
    HF_HOME: str = field(default_factory=lambda: os.getenv("HF_HOME", os.path.expanduser("~/.cache/huggingface")))

    # Custom Profile (for personality customization)
    CUSTOM_PROFILE: str | None = field(default_factory=lambda: os.getenv("REACHY_MINI_CUSTOM_PROFILE"))

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []

        if self.REALTIME_PROVIDER not in VALID_REALTIME_PROVIDERS:
            valid = ", ".join(sorted(VALID_REALTIME_PROVIDERS))
            errors.append(f"REALTIME_PROVIDER must be one of: {valid}")

        if self.REALTIME_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY is required")
        if self.REALTIME_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")
        if self.OPENCLAW_VOICE_TIMEOUT <= 0:
            errors.append("OPENCLAW_VOICE_TIMEOUT must be greater than 0")
        if self.GEMINI_INPUT_SUPPRESSION_TIMEOUT <= 0:
            errors.append("GEMINI_INPUT_SUPPRESSION_TIMEOUT must be greater than 0")

        return errors


# Global configuration instance
config = Config()


def set_custom_profile(profile: str | None) -> None:
    """Update the custom profile at runtime."""
    global config
    config.CUSTOM_PROFILE = profile
    os.environ["REACHY_MINI_CUSTOM_PROFILE"] = profile or ""


def set_face_tracking_enabled(enabled: bool) -> None:
    """Enable or disable face tracking at runtime."""
    global config
    config.ENABLE_FACE_TRACKING = enabled


def set_local_vision_enabled(enabled: bool) -> None:
    """Enable or disable local vision processing at runtime."""
    global config
    config.ENABLE_LOCAL_VISION = enabled
