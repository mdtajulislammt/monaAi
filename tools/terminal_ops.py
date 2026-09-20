"""Terminal and shell command execution engine with real-time capture and safety gates."""
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import get_settings
from core.safety import get_safety_validator

logger = logging.getLogger(__name__)


def execute_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute a shell command with safety validation, timeout limits, and real-time capture.

    Args:
        command: The command line string to run.
        cwd: Optional working directory for command execution.
        timeout: Execution timeout in seconds. Defaults to setting (60s).

    Returns:
        Dictionary containing exit_code, stdout, stderr, execution_time_sec, and status.
    """
    settings = get_settings()
    validator = get_safety_validator()
    effective_timeout = timeout or settings.command_timeout_seconds

    # 1. Safety Validation
    is_allowed, reason = validator.validate_command(command)
    if not is_allowed:
        logger.warning(f"Command execution blocked: {reason}")
        return {
            "status": "security_denied",
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"SECURITY POLICY VIOLATION: {reason}",
            "execution_time_sec": 0.0,
        }

    # 2. CWD resolution & validation
    resolved_cwd = settings.workspace_root
    if cwd:
        try:
            resolved_cwd = validator.validate_path(cwd, must_exist=True)
        except Exception as e:
            return {
                "status": "error",
                "command": command,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Invalid working directory '{cwd}': {str(e)}",
                "execution_time_sec": 0.0,
            }

    start_time = time.time()
    try:
        logger.info(f"Executing command: '{command}' in '{resolved_cwd}' (timeout={effective_timeout}s)")
        process = subprocess.Popen(
            command,
            shell=True,
            cwd=str(resolved_cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True,
            env=os.environ.copy(),
        )

        try:
            stdout_data, stderr_data = process.communicate(timeout=effective_timeout)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout_data, stderr_data = process.communicate()
            elapsed = round(time.time() - start_time, 3)
            return {
                "status": "timeout",
                "command": command,
                "exit_code": -1,
                "stdout": stdout_data,
                "stderr": f"Command timed out after {effective_timeout} seconds.\n{stderr_data}",
                "execution_time_sec": elapsed,
            }

        elapsed = round(time.time() - start_time, 3)
        return {
            "status": "success" if exit_code == 0 else "failed",
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout_data.strip(),
            "stderr": stderr_data.strip(),
            "execution_time_sec": elapsed,
        }

    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        logger.error(f"Error executing command '{command}': {e}")
        return {
            "status": "error",
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": f"Execution failure: {str(e)}",
            "execution_time_sec": elapsed,
        }
