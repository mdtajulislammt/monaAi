"""Interfaces module exporting CLI and Voice handlers."""
from interfaces.cli import CLIInterface
from interfaces.voice import VoiceInterface
from interfaces.web_ui import run_web_ui

__all__ = ["CLIInterface", "VoiceInterface", "run_web_ui"]
