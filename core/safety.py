"""Security and safety validation engine for Desktop AI Agent."""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from config.settings import get_settings

logger = logging.getLogger(__name__)


class SecurityException(Exception):
    """Exception raised when an operation violates security or safety policies."""
    pass


class SafetyValidator:
    """Validates commands, paths, and actions before execution."""

    def __init__(self, rules_path: Optional[Path] = None):
        self.settings = get_settings()
        self.rules_path = rules_path or self.settings.safety_rules_path
        self.rules: Dict[str, Any] = self._load_rules()
        self.compiled_patterns: List[re.Pattern] = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.rules.get("forbidden_patterns", [])
        ]

    def _load_rules(self) -> Dict[str, Any]:
        """Load safety rules from JSON file, falling back to secure defaults."""
        if self.rules_path and self.rules_path.exists():
            try:
                with open(self.rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load safety rules from {self.rules_path}: {e}")

        # Fallback minimal rules if file cannot be read
        return {
            "forbidden_commands": ["rm -rf /", ":(){ :|:& };:", "mkfs", "dd if="],
            "forbidden_patterns": [r"^rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+[/~]"],
            "protected_paths": ["/", "/etc", "/boot", "/sys", "/dev", "C:\\Windows"],
            "require_confirmation": ["git reset --hard", "docker system prune"],
        }

    def validate_command(
        self,
        command: str,
        confirm_callback: Optional[Callable[[str], bool]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """Validate a shell command string against blacklists and patterns.

        Args:
            command: The command line string to validate.
            confirm_callback: Optional callable for user confirmation if required.

        Returns:
            Tuple of (is_allowed, reason_if_blocked)
        """
        stripped_cmd = command.strip()
        if not stripped_cmd:
            return False, "Command is empty."

        # If PERMISSIVE mode, only block catastrophic operations
        if self.settings.safety_mode == "PERMISSIVE":
            catastrophic = [":(){ :|:& };:", "rm -rf /", "mkfs"]
            for bad in catastrophic:
                if bad in stripped_cmd:
                    return False, f"Catastrophic command detected: '{bad}'"
            return True, None

        # 1. Check exact forbidden commands & sub-strings
        for forbidden in self.rules.get("forbidden_commands", []):
            # Special handling for root deletion "rm -rf /" to avoid false positives on "/home/..."
            if forbidden == "rm -rf /":
                if re.search(r'\brm\s+-[^\s]*\s+/(?:\s+|$|\*)', stripped_cmd):
                    msg = f"Command contains forbidden expression: '{forbidden}'"
                    logger.warning(f"[SAFETY VIOLATION] {msg} in '{stripped_cmd}'")
                    return False, msg
                continue

            if forbidden.lower() in stripped_cmd.lower():
                msg = f"Command contains forbidden expression: '{forbidden}'"
                logger.warning(f"[SAFETY VIOLATION] {msg} in '{stripped_cmd}'")
                return False, msg

        # 2. Check regex patterns
        for pattern in self.compiled_patterns:
            if pattern.search(stripped_cmd):
                msg = f"Command matched forbidden security pattern: '{pattern.pattern}'"
                logger.warning(f"[SAFETY VIOLATION] {msg} in '{stripped_cmd}'")
                return False, msg

        # 3. Check patterns requiring confirmation
        for conf_phrase in self.rules.get("require_confirmation", []):
            if conf_phrase.lower() in stripped_cmd.lower():
                if self.settings.safety_mode == "STRICT":
                    if confirm_callback is not None:
                        approved = confirm_callback(
                            f"Command '{stripped_cmd}' requires manual authorization. Proceed?"
                        )
                        if not approved:
                            return False, f"User denied execution of: '{stripped_cmd}'"
                    else:
                        return (
                            False,
                            f"Command '{stripped_cmd}' requires manual confirmation but no interactive prompt is active.",
                        )

        return True, None

    def validate_path(
        self,
        target_path: str | Path,
        must_exist: bool = False,
        restrict_to_workspace: bool = False,
    ) -> Path:
        """Validate that a filesystem path is safe and does not target protected areas.

        Args:
            target_path: Path string or Path object to validate.
            must_exist: Whether the path must already exist.
            restrict_to_workspace: If True, confines path within WORKSPACE_ROOT.

        Returns:
            Resolved absolute Path object.

        Raises:
            SecurityException: If path targets a protected system directory or violates workspace boundaries.
            FileNotFoundError: If must_exist is True and file does not exist.
        """
        raw_path = Path(target_path)
        try:
            resolved = raw_path.expanduser().resolve()
        except Exception as e:
            raise SecurityException(f"Invalid path representation: {e}")

        # Check protected paths
        resolved_str = str(resolved).lower()
        for protected in self.rules.get("protected_paths", []):
            norm_protected = str(Path(protected).expanduser().resolve()).lower()
            # Match exact or root/system directories
            if resolved_str == norm_protected or resolved_str.startswith(norm_protected + os.sep):
                if norm_protected not in ["/", "c:\\"]:  # don't trigger on every subpath of /
                    raise SecurityException(
                        f"Access to protected system path '{target_path}' ({resolved}) is forbidden."
                    )
                elif resolved_str in ["/", "c:\\"]:
                    raise SecurityException("Direct modification of filesystem root is forbidden.")

        # Workspace restriction check
        if restrict_to_workspace:
            workspace = self.settings.workspace_root.resolve()
            if not resolved.is_relative_to(workspace):
                raise SecurityException(
                    f"Path '{resolved}' is outside the authorized workspace root '{workspace}'."
                )

        if must_exist and not resolved.exists():
            raise FileNotFoundError(f"Target path does not exist: '{resolved}'")

        return resolved


# Singleton instance
_validator: Optional[SafetyValidator] = None


def get_safety_validator() -> SafetyValidator:
    """Retrieve singleton SafetyValidator instance."""
    global _validator
    if _validator is None:
        _validator = SafetyValidator()
    return _validator
