"""System automation tools for JARVIS: safe terminal execution, telemetry, process control, and IDE launcher."""
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psutil
from config.settings import get_settings
from memory.reflection_engine import get_reflection_engine
from tools.input_driver import get_virtual_input, set_system_clipboard

logger = logging.getLogger(__name__)


class SafetyGuard:
    """Validates commands and file paths against safety policies."""

    def __init__(self):
        self.settings = get_settings()
        self.rules = self._load_rules()
        self._compiled_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.rules.get("forbidden_patterns", [])
        ]

    def _load_rules(self) -> Dict[str, Any]:
        rules_path = self.settings.safety_rules_path
        if rules_path.exists():
            try:
                with open(rules_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error reading safety_rules.json: {e}")
        return {
            "forbidden_commands": ["rm -rf /", ":(){ :|:& };:", "mkfs", "dd if="],
            "forbidden_patterns": [r"^rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+[/~]"],
            "protected_paths": ["/", "/bin", "/boot", "/etc", "/dev", "/sys", "/usr"],
            "require_confirmation": ["git reset --hard", "docker system prune"],
        }

    def validate_command(self, command: str) -> Tuple[bool, Optional[str]]:
        """Validate shell command against blacklists and dangerous patterns."""
        cmd_clean = command.strip()
        if not cmd_clean:
            return False, "Command is empty."

        # In permissive mode, only block destructive system deletions
        if self.settings.safety_mode == "PERMISSIVE":
            for bad in [":(){ :|:& };:", "rm -rf /", "mkfs"]:
                if bad in cmd_clean:
                    return False, f"Catastrophic command blocked: {bad}"
            return True, None

        # Check exact forbidden commands
        for forbidden in self.rules.get("forbidden_commands", []):
            if forbidden in cmd_clean:
                return False, f"Forbidden command detected: '{forbidden}'"

        # Check regex patterns
        for pattern in self._compiled_patterns:
            if pattern.search(cmd_clean):
                return False, f"Dangerous command pattern matched: '{pattern.pattern}'"

        # Check protected directory modification
        for protected in self.rules.get("protected_paths", []):
            if f"rm -rf {protected}" in cmd_clean or f"rm -r {protected}" in cmd_clean:
                return False, f"Attempted removal of protected path: '{protected}'"

        return True, None


_safety_guard = SafetyGuard()


def execute_terminal_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute a shell command with strict safety validation, timeout, and reflection feedback.

    Args:
        command: The shell command to execute.
        cwd: Optional working directory. Defaults to workspace root.
        timeout: Execution timeout in seconds (defaults to settings.command_timeout_seconds).

    Returns:
        Dict containing status, exit_code, stdout, stderr, execution_time_sec.
    """
    settings = get_settings()
    effective_timeout = timeout or settings.command_timeout_seconds
    start_time = time.time()

    # 1. Safety Validation
    is_safe, violation_reason = _safety_guard.validate_command(command)
    if not is_safe:
        err_msg = f"SECURITY_POLICY_VIOLATION: {violation_reason}"
        get_reflection_engine().log_execution(
            action=command,
            success=False,
            error=err_msg,
            context="Blocked by safety guard before subprocess execution.",
        )
        return {
            "status": "security_blocked",
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": err_msg,
            "execution_time_sec": 0.0,
        }

    # 2. Resolve Working Directory
    working_dir = Path(cwd).resolve() if cwd else settings.workspace_root
    if not working_dir.exists():
        err_msg = f"Working directory does not exist: {working_dir}"
        get_reflection_engine().log_execution(action=command, success=False, error=err_msg)
        return {
            "status": "error",
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": err_msg,
            "execution_time_sec": 0.0,
        }

    # 3. Execute Subprocess
    try:
        env = os.environ.copy()
        local_bin = str(Path.home() / ".local" / "bin")
        if local_bin not in env.get("PATH", ""):
            env["PATH"] = f"{local_bin}:{env.get('PATH', '')}"

        process = subprocess.run(
            command,
            shell=True,
            cwd=str(working_dir),
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            env=env,
        )
        elapsed = round(time.time() - start_time, 3)
        stdout = process.stdout or ""
        stderr = process.stderr or ""
        exit_code = process.returncode

        success = (exit_code == 0)
        if not success:
            get_reflection_engine().log_execution(
                action=command,
                success=False,
                output=stdout,
                error=stderr or f"Non-zero exit code: {exit_code}",
                context=f"Working dir: {working_dir}",
            )

        return {
            "status": "success" if success else "failed",
            "command": command,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "execution_time_sec": elapsed,
        }

    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - start_time, 3)
        err_msg = f"Command timed out after {effective_timeout} seconds."
        get_reflection_engine().log_execution(
            action=command,
            success=False,
            error=err_msg,
            context="Process timed out.",
        )
        return {
            "status": "timeout",
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": err_msg,
            "execution_time_sec": elapsed,
        }
    except Exception as e:
        elapsed = round(time.time() - start_time, 3)
        err_msg = f"Subprocess execution exception: {str(e)}"
        get_reflection_engine().log_execution(action=command, success=False, error=err_msg)
        return {
            "status": "error",
            "command": command,
            "exit_code": -1,
            "stdout": "",
            "stderr": err_msg,
            "execution_time_sec": elapsed,
        }


def get_system_telemetry() -> Dict[str, Any]:
    """Retrieve comprehensive system telemetry (CPU, RAM, Disk, Network, Top Processes)."""
    try:
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        cpu_pct = psutil.cpu_percent(interval=0.2)
        cpu_cores = psutil.cpu_count(logical=True)
        disk = psutil.disk_usage("/")

        # Top 5 processes by memory
        top_procs = []
        for p in sorted(
            psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]),
            key=lambda x: x.info.get("memory_percent") or 0.0,
            reverse=True,
        )[:5]:
            try:
                top_procs.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "memory_pct": round(p.info.get("memory_percent") or 0.0, 1),
                    "cpu_pct": round(p.info.get("cpu_percent") or 0.0, 1),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu": {
                "usage_percent": cpu_pct,
                "cores": cpu_cores,
            },
            "ram": {
                "total_gb": round(vm.total / (1024**3), 2),
                "used_gb": round(vm.used / (1024**3), 2),
                "free_gb": round(vm.available / (1024**3), 2),
                "usage_percent": vm.percent,
            },
            "swap": {
                "total_gb": round(swap.total / (1024**3), 2),
                "used_gb": round(swap.used / (1024**3), 2),
                "usage_percent": swap.percent,
            },
            "disk_root": {
                "total_gb": round(disk.total / (1024**3), 2),
                "free_gb": round(disk.free / (1024**3), 2),
                "usage_percent": disk.percent,
            },
            "top_processes": top_procs,
        }
    except Exception as e:
        logger.error(f"Error fetching system telemetry: {e}")
        return {"error": str(e)}


def manage_process(
    action: str,
    pid: Optional[int] = None,
    process_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspect or safely terminate processes.

    Args:
        action: 'list', 'find', 'terminate', or 'kill'.
        pid: Process ID for termination or details.
        process_name: Substring or name to search for.
    """
    action_lower = action.lower()

    if action_lower in ["list", "find"]:
        matches = []
        for p in psutil.process_iter(["pid", "name", "username", "status"]):
            try:
                p_name = p.info.get("name") or ""
                if not process_name or process_name.lower() in p_name.lower():
                    matches.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return {"status": "success", "count": len(matches), "processes": matches[:25]}

    elif action_lower in ["terminate", "kill"]:
        if not pid:
            return {"status": "error", "message": "PID must be provided for termination."}

        # Guard system processes
        if pid <= 1:
            return {"status": "security_blocked", "message": "Cannot terminate system initialization process (PID <= 1)."}

        try:
            proc = psutil.Process(pid)
            p_name = proc.name()

            if action_lower == "terminate":
                proc.terminate()
                proc.wait(timeout=3)
                return {"status": "success", "message": f"Process {p_name} (PID {pid}) terminated successfully."}
            else:
                proc.kill()
                proc.wait(timeout=3)
                return {"status": "success", "message": f"Process {p_name} (PID {pid}) killed successfully."}
        except psutil.NoSuchProcess:
            return {"status": "not_found", "message": f"No process found with PID {pid}."}
        except psutil.AccessDenied:
            return {"status": "access_denied", "message": f"Insufficient permissions to terminate PID {pid}."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to terminate PID {pid}: {str(e)}"}

    return {"status": "error", "message": f"Unknown process action: '{action}'"}


def launch_developer_ide(
    ide_name: str,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Launch developer IDE (Google Antigravity, VS Code, Cursor) with an optional workspace path.

    Args:
        ide_name: 'antigravity', 'vscode', 'code', or 'cursor'.
        project_path: Workspace folder or file path to open.
    """
    settings = get_settings()
    target_path = str(Path(project_path).resolve()) if project_path else str(settings.workspace_root)
    ide_lower = ide_name.lower()

    binary_candidates = {
        "antigravity": ["antigravity", "/home/mdtajulislam/.local/bin/antigravity", "google-antigravity"],
        "vscode": ["code", "code-insiders"],
        "code": ["code", "code-insiders"],
        "cursor": ["cursor", "/home/mdtajulislam/.local/bin/cursor"],
    }

    target_binaries = binary_candidates.get(ide_lower, [ide_name])
    found_bin = None
    for b in target_binaries:
        if shutil.which(b) or Path(b).is_file():
            found_bin = b
            break

    if not found_bin:
        # Fallback for Antigravity desktop app or generic launcher
        if "antigravity" in ide_lower:
            found_bin = "antigravity"
        elif "code" in ide_lower:
            found_bin = "code"
        else:
            return {
                "status": "not_found",
                "message": f"IDE binary for '{ide_name}' could not be located in system PATH.",
            }

    try:
        # Launch detached process
        subprocess.Popen(
            [found_bin, target_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {
            "status": "success",
            "message": f"Launched {ide_name} targeting '{target_path}'",
            "binary": found_bin,
            "project_path": target_path,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to launch {ide_name}: {str(e)}"}


def open_desktop_application(app_name: str) -> Dict[str, Any]:
    """Launch or bring to focus a local desktop application (e.g. Telegram, Discord, Chrome, VS Code)."""
    name_clean = app_name.lower().strip()

    known_apps = {
        "telegram": ["/usr/bin/Telegram", "telegram-desktop", "Telegram"],
        "discord": ["discord", "Discord"],
        "chrome": ["google-chrome-stable", "google-chrome", "chromium"],
        "google chrome": ["google-chrome-stable", "google-chrome"],
        "vscode": ["code", "code-insiders"],
        "code": ["code"],
        "antigravity": ["antigravity", "/home/mdtajulislam/.local/bin/antigravity", "google-antigravity"],
        "files": ["nautilus", "dolphin", "thunar", "pcmanfm"],
        "file manager": ["nautilus", "dolphin", "thunar"],
        "terminal": ["konsole", "gnome-terminal", "alacritty", "kitty"],
    }

    candidates = known_apps.get(name_clean, [app_name])
    found_binary = None
    for c in candidates:
        if shutil.which(c) or (Path(c).is_file() and os.access(c, os.X_OK)):
            found_binary = c
            break

    if not found_binary:
        try:
            subprocess.Popen(
                ["xdg-open", app_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return {"status": "success", "message": f"Launched '{app_name}' via xdg-open"}
        except Exception as e:
            return {"status": "not_found", "message": f"Could not locate application binary for '{app_name}': {e}"}

    try:
        subprocess.Popen(
            [found_binary],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {
            "status": "success",
            "app_name": app_name,
            "binary": found_binary,
            "message": f"Successfully launched or brought '{app_name}' to focus!",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to launch '{app_name}': {str(e)}"}


def set_system_clipboard(text: str) -> bool:
    """Set system clipboard contents reliably across KDE Plasma, Wayland, and X11."""
    # 1. Try KDE Plasma qdbus6
    try:
        res = subprocess.run(
            ["qdbus6", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper.setClipboardContents", text],
            capture_output=True,
            timeout=2,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    # 2. Try wl-copy (Wayland clipboard)
    try:
        p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"), timeout=2)
        if p.returncode == 0:
            return True
    except Exception:
        pass

    # 3. Try xclip (X11 clipboard)
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"), timeout=2)
        if p.returncode == 0:
            return True
    except Exception:
        pass

    # 4. Try pyperclip fallback
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    return False


def _get_pyautogui():
    """Load pyautogui with mouseinfo bypass on headless/XWayland environments."""
    import sys
    sys.modules["mouseinfo"] = None
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0.08
    return pyautogui


def automate_gui_action(
    action: str,
    text: Optional[str] = None,
    key: Optional[str] = None,
    hotkey: Optional[List[str]] = None,
    delay_seconds: float = 0.4,
) -> Dict[str, Any]:
    """Perform desktop GUI keyboard or mouse automation using native kernel uinput or PyAutoGUI.

    Args:
        action: 'type', 'paste', 'press', 'hotkey', 'click', 'move', or 'scroll'.
        text: String content to type or paste.
        key: Key name to press (e.g. 'enter', 'esc', 'tab', 'down').
        hotkey: List of key combinations (e.g. ['ctrl', 'f'], ['alt', 'f4']).
        delay_seconds: Pause duration before executing action.
    """
    import time
    try:
        time.sleep(delay_seconds)
        v_input = get_virtual_input()
        action_lower = action.lower()

        if action_lower == "type" and text:
            v_input.type_text(text)
            return {"status": "success", "action": "type", "text": text, "message": f"Typed: '{text}'"}
        elif action_lower == "paste" and text:
            v_input.paste_text(text)
            return {"status": "success", "action": "paste", "text": text, "message": f"Pasted: '{text}'"}
        elif action_lower == "press" and key:
            v_input.press_key(key)
            return {"status": "success", "action": "press", "key": key, "message": f"Pressed: '{key}'"}
        elif action_lower == "hotkey" and hotkey:
            v_input.hotkey(*hotkey)
            return {"status": "success", "action": "hotkey", "keys": hotkey, "message": f"Triggered hotkey: {hotkey}"}
        elif action_lower == "click":
            v_input.mouse_click("left")
            return {"status": "success", "action": "click"}
        elif action_lower == "move":
            v_input.mouse_move(0, 0)
            return {"status": "success", "action": "move"}

        return {"status": "error", "message": f"Invalid GUI action or missing arguments: '{action}'"}
    except Exception as e:
        logger.error(f"GUI automation error: {e}")
        return {"status": "error", "message": f"GUI automation failed: {str(e)}"}


def send_desktop_message(
    app_name: str,
    contact_name: str,
    message: str,
) -> Dict[str, Any]:
    """Automate searching a contact and sending a message in desktop applications like Telegram, Discord, etc.

    Uses native Linux kernel uinput driver and KDE Plasma clipboard integration.

    Args:
        app_name: Target desktop application name ('Telegram', 'Discord', etc.).
        contact_name: Contact or channel name to search for (e.g. 'Fahim').
        message: Message text to type and send.
    """
    import time
    try:
        # 1. Bring application to front
        open_desktop_application(app_name)
        time.sleep(1.2)

        v_input = get_virtual_input()

        # 2. Clear any search/modal and activate search
        v_input.press_key("esc")
        time.sleep(0.3)
        v_input.hotkey("ctrl", "f")
        time.sleep(0.5)

        # 3. Type or paste contact name into search bar
        v_input.paste_text(contact_name)
        time.sleep(0.9)

        # 4. Navigate down and press Enter to select the top matched contact
        v_input.press_key("down")
        time.sleep(0.2)
        v_input.press_key("enter")
        time.sleep(0.7)

        # 5. Insert message via clipboard paste (supports English, Bengali, emojis, etc.)
        v_input.paste_text(message)
        time.sleep(0.3)

        # 6. Press Enter to send
        v_input.press_key("enter")

        return {
            "status": "success",
            "app": app_name,
            "contact": contact_name,
            "message": message,
            "details": f"Successfully searched '{contact_name}' in {app_name}, opened conversation, and sent: '{message}'",
        }
    except Exception as e:
        logger.error(f"send_desktop_message failed: {e}")
        return {"status": "error", "message": f"Failed to send message: {str(e)}"}


