"""Application configuration and environment settings using Pydantic."""
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Optional, Union
from pydantic import Field, field_validator
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings
    SettingsConfigDict = None


class Settings(BaseSettings):
    """Configuration model for the Desktop AI Agent."""

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            extra="ignore",
        )
    else:
        model_config = {"extra": "ignore"}

    # API Keys & LLM settings
    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY",
        description="Google Gemini API key from AI Studio",
    )
    default_model: str = Field(
        default="gemini-3.5-flash-lite",
        alias="DEFAULT_MODEL",
        description="Default Gemini model to use for agent reasoning",
    )

    # Safety Mode
    safety_mode: Literal["STRICT", "MODERATE", "PERMISSIVE"] = Field(
        default="STRICT",
        alias="SAFETY_MODE",
        description="Safety enforcement level for tool operations",
    )

    # Execution limits
    command_timeout_seconds: int = Field(
        default=60,
        alias="COMMAND_TIMEOUT_SECONDS",
        description="Max seconds allowed for terminal command execution",
    )
    max_tool_iterations: int = Field(
        default=15,
        alias="MAX_TOOL_ITERATIONS",
        description="Max autonomous tool loops per user prompt",
    )

    # Paths
    workspace_root: Path = Field(
        default_factory=lambda: Path.cwd(),
        alias="WORKSPACE_ROOT",
        description="Default working directory for project and file operations",
    )
    safety_rules_path: Path = Field(
        default_factory=lambda: Path(__file__).parent / "safety_rules.json",
        alias="SAFETY_RULES_PATH",
        description="Path to JSON file containing safety patterns and blacklist",
    )

    # Browser automation
    browser_headless: bool = Field(
        default=False,
        alias="BROWSER_HEADLESS",
        description="Whether to run Playwright in headless mode",
    )

    # Voice interface
    voice_name: str = Field(
        default="bn-BD-NabanitaNeural",
        alias="VOICE_NAME",
        description="Bangladeshi Neural Voice name",
    )
    voice_rate: str | int = Field(
        default="+0%",
        alias="VOICE_RATE",
        description="TTS speech rate (+0% or WPM)",
    )
    voice_volume: str | float = Field(
        default="+0%",
        alias="VOICE_VOLUME",
        description="TTS audio volume (+0% or 0.0-1.0)",
    )
    voice_language: str = Field(
        default="bn-BD",
        alias="VOICE_LOCALE",
        description="STT language code",
    )

    @field_validator("workspace_root", mode="before")
    @classmethod
    def resolve_workspace_root(cls, v: Optional[str | Path]) -> Path:
        """Resolve workspace root to absolute path, defaulting to current working dir."""
        if not v or str(v).strip() == "":
            return Path.cwd().resolve()
        return Path(v).expanduser().resolve()

    @field_validator("voice_volume", mode="before")
    @classmethod
    def validate_volume(cls, v: Any) -> str | float:
        """Ensure volume format is valid for both edge-tts and legacy engines."""
        if isinstance(v, str) and "%" in v:
            return v
        try:
            val = float(v)
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return "+0%"


@lru_cache
def get_settings() -> Settings:
    """Retrieve cached application settings singleton."""
    return Settings()
