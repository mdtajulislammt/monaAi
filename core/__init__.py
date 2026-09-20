"""Core package for Desktop AI Agent."""
from core.safety import SafetyValidator, SecurityException, get_safety_validator


def __getattr__(name: str):
    """Lazy import to prevent circular dependency with tool modules."""
    if name == "DesktopAgent":
        from core.agent import DesktopAgent
        return DesktopAgent
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = ["SafetyValidator", "SecurityException", "get_safety_validator", "DesktopAgent"]
