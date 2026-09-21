"""Configuration and settings management for JARVIS Desktop Assistant."""
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_env_files() -> List[str]:
    """Find candidate .env files in jarvis-core and parent directories."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]
    return [str(p) for p in candidates if p.exists()]


class Settings(BaseSettings):
    """Production Pydantic BaseSettings for JARVIS."""

    model_config = SettingsConfigDict(
        env_file=find_env_files() or [".env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core LLM
    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY",
        description="Google Gemini API key",
    )
    default_model: str = Field(
        default="gemini-2.5-flash",
        alias="DEFAULT_MODEL",
        description="Primary Gemini model name",
    )
    fallback_models: List[str] = [
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-3.5-flash-lite",
        "gemini-1.5-pro",
    ]

    # Safety & Execution Rules
    safety_mode: str = Field(
        default="STRICT",
        alias="SAFETY_MODE",
        description="Execution safety level: STRICT, MODERATE, or PERMISSIVE",
    )
    command_timeout_seconds: int = Field(
        default=60,
        alias="COMMAND_TIMEOUT_SECONDS",
        description="Max execution timeout for terminal commands",
    )
    max_tool_iterations: int = Field(
        default=15,
        alias="MAX_TOOL_ITERATIONS",
        description="Max iterations per autonomous tool call loop",
    )

    # Workspace & File Paths
    workspace_root: Path = Field(
        default_factory=lambda: Path(os.getenv("WORKSPACE_ROOT") or Path.cwd()).resolve(),
        alias="WORKSPACE_ROOT",
        description="Active workspace root directory",
    )
    safety_rules_path: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent / "safety_rules.json",
        description="Path to JSON safety rules definition",
    )

    # Memory Settings (ChromaDB)
    chroma_persist_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent / "data" / "chroma_db",
        alias="CHROMA_PERSIST_DIR",
        description="ChromaDB persistent storage directory",
    )

    # Bengali Voice Settings
    voice_locale: str = Field(
        default="bn-BD",
        alias="VOICE_LOCALE",
        description="Locale for Speech Recognition STT",
    )
    voice_name: str = Field(
        default="bn-BD-NabanitaNeural",
        alias="VOICE_NAME",
        description="Neural voice for edge-tts (authentic Bangladeshi Bengali: bn-BD-NabanitaNeural or bn-BD-PradeepNeural)",
    )
    voice_rate: str = Field(
        default="+0%",
        alias="VOICE_RATE",
        description="Speaking rate delta for edge-tts (natural pacing: +0%)",
    )
    voice_volume: str = Field(
        default="+0%",
        alias="VOICE_VOLUME",
        description="Volume delta for edge-tts",
    )

    # ElevenLabs Voice Settings
    tts_provider: str = Field(
        default="elevenlabs",
        alias="TTS_PROVIDER",
        description="Active TTS provider: 'elevenlabs' or 'edge_tts'",
    )
    elevenlabs_api_key: str = Field(
        default="",
        alias="ELEVENLABS_API_KEY",
        description="ElevenLabs API Key",
    )
    elevenlabs_voice_id: str = Field(
        default="EXAVITQu4vr4xnSDxMaL",
        alias="ELEVENLABS_VOICE_ID",
        description="ElevenLabs Voice ID (Sarah, Lily, Jessica, etc.)",
    )
    elevenlabs_model_id: str = Field(
        default="eleven_multilingual_v2",
        alias="ELEVENLABS_MODEL_ID",
        description="ElevenLabs model ID for multilingual speech",
    )

    @classmethod
    def _normalize_edge_tts_param(cls, val: Any, default: str = "+0%") -> str:
        if val is None:
            return default
        val_str = str(val).strip()
        import re
        if re.match(r"^[+-]\d+%$", val_str):
            return val_str
        if val_str.isdigit():
            num = int(val_str)
            delta = num - 100 if num >= 100 else num
            if delta > 30:
                delta = 0  # cap at natural human pacing
            sign = "+" if delta >= 0 else ""
            return f"{sign}{delta}%"
        return default

    def model_post_init(self, __context: Any) -> None:
        """Validate and normalize voice settings after initialization."""
        self.voice_rate = self._normalize_edge_tts_param(self.voice_rate, "+0%")
        self.voice_volume = self._normalize_edge_tts_param(self.voice_volume, "+0%")

    # Browser Automation
    browser_headless: bool = Field(
        default=True,
        alias="BROWSER_HEADLESS",
        description="Run Playwright browser in headless mode",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton getter for application settings."""
    return Settings()
