"""Operating System & Application Automation Tools."""
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from config.settings import get_settings

logger = logging.getLogger(__name__)


def open_application(app_name: str) -> Dict[str, Any]:
    """Open a desktop application by name cross-platform.

    Args:
        app_name: Name of the application (e.g., 'firefox', 'vlc', 'gedit', 'calc', 'notepad').

    Returns:
        Dictionary with status, message, and process details.
    """
    sys_name = platform.system()
    clean_app = app_name.strip()

    try:
        if sys_name == "Linux":
            # Check if command is directly in PATH
            cmd_path = shutil.which(clean_app)
            if cmd_path:
                proc = subprocess.Popen([cmd_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return {"status": "success", "message": f"Launched '{clean_app}' (PID: {proc.pid})", "pid": proc.pid}
            
            # Try gtk-launch or xdg-open
            proc = subprocess.Popen(["gtk-launch", clean_app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "success", "message": f"Invoked gtk-launch for '{clean_app}'"}

        elif sys_name == "Darwin":  # macOS
            proc = subprocess.Popen(["open", "-a", clean_app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"status": "success", "message": f"Launched macOS app '{clean_app}'"}

        elif sys_name == "Windows":
            os.startfile(clean_app)
            return {"status": "success", "message": f"Started Windows application '{clean_app}'"}

        else:
            return {"status": "error", "message": f"Unsupported platform '{sys_name}'"}

    except Exception as e:
        logger.error(f"Failed to open application '{app_name}': {e}")
        return {"status": "error", "message": f"Failed to open '{app_name}': {str(e)}"}


def launch_ide(ide_name: str = "vscode", workspace_path: Optional[str] = None) -> Dict[str, Any]:
    """Launch an IDE workspace (VS Code, Antigravity, Cursor, PyCharm).

    Args:
        ide_name: Name of IDE ('vscode', 'code', 'antigravity', 'agy', 'cursor', 'pycharm').
        workspace_path: Optional path to project directory or file. Defaults to current workspace.

    Returns:
        Dictionary containing execution result.
    """
    settings = get_settings()
    target_path = Path(workspace_path) if workspace_path else settings.workspace_root
    target_path = target_path.expanduser().resolve()

    if not target_path.exists():
        return {
            "status": "error",
            "message": f"Workspace directory does not exist: {target_path}",
        }

    ide_map = {
        "vscode": ["code", target_path.as_posix()],
        "code": ["code", target_path.as_posix()],
        "antigravity": ["antigravity", target_path.as_posix()],
        "agy": ["agy", target_path.as_posix()],
        "cursor": ["cursor", target_path.as_posix()],
        "pycharm": ["pycharm", target_path.as_posix()],
    }

    key = ide_name.lower().strip()
    command_args = ide_map.get(key)
    if not command_args:
        # Fallback to direct executable call
        command_args = [key, target_path.as_posix()]

    executable = command_args[0]
    which_path = shutil.which(executable)

    # Special handling for Antigravity if 'antigravity' binary isn't in PATH directly
    if not which_path and key in ["antigravity", "agy"]:
        # Also check 'agy' alias
        alt_binary = "agy" if executable == "antigravity" else "antigravity"
        if shutil.which(alt_binary):
            executable = alt_binary
            command_args[0] = alt_binary
            which_path = shutil.which(alt_binary)

    if not which_path:
        return {
            "status": "error",
            "message": f"Executable '{executable}' not found in system PATH. Ensure '{ide_name}' is installed and registered in your PATH.",
        }

    try:
        proc = subprocess.Popen(
            command_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {
            "status": "success",
            "message": f"Launched {ide_name} at workspace '{target_path}' (PID: {proc.pid})",
            "workspace": str(target_path),
            "pid": proc.pid,
        }
    except Exception as e:
        logger.error(f"Error launching IDE '{ide_name}': {e}")
        return {"status": "error", "message": f"Failed to launch '{ide_name}': {str(e)}"}


def get_system_stats() -> Dict[str, Any]:
    """Retrieve real-time hardware, memory, and OS statistics.

    Returns:
        Dictionary with CPU, Memory, Disk, and top process stats.
    """
    try:
        cpu_percent = psutil.cpu_percent(interval=0.2)
        virtual_mem = psutil.virtual_memory()
        disk_usage = psutil.disk_usage(Path.cwd().anchor or "/")

        top_processes: List[Dict[str, Any]] = []
        for p in sorted(
            psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
            key=lambda x: x.info.get("memory_percent") or 0.0,
            reverse=True,
        )[:5]:
            top_processes.append(p.info)

        return {
            "status": "success",
            "platform": platform.platform(),
            "cpu_percent": cpu_percent,
            "cpu_count": psutil.cpu_count(logical=True),
            "memory": {
                "total_gb": round(virtual_mem.total / (1024**3), 2),
                "used_gb": round(virtual_mem.used / (1024**3), 2),
                "available_gb": round(virtual_mem.available / (1024**3), 2),
                "percent": virtual_mem.percent,
            },
            "disk": {
                "total_gb": round(disk_usage.total / (1024**3), 2),
                "free_gb": round(disk_usage.free / (1024**3), 2),
                "percent": disk_usage.percent,
            },
            "top_memory_processes": top_processes,
        }
    except Exception as e:
        logger.error(f"Error gathering system stats: {e}")
        return {"status": "error", "message": f"Failed to gather stats: {str(e)}"}


def kill_process(process_name: Optional[str] = None, pid: Optional[int] = None) -> Dict[str, Any]:
    """Terminate a process by name or PID safely.

    Args:
        process_name: Name of process (e.g., 'chrome', 'python').
        pid: Numeric process ID.

    Returns:
        Dictionary with termination outcome.
    """
    terminated = []
    try:
        if pid:
            p = psutil.Process(pid)
            name = p.name()
            p.terminate()
            return {"status": "success", "message": f"Terminated PID {pid} ({name})"}

        if process_name:
            for p in psutil.process_iter(["pid", "name"]):
                if process_name.lower() in p.info["name"].lower():
                    p.terminate()
                    terminated.append({"pid": p.info["pid"], "name": p.info["name"]})

            if terminated:
                return {
                    "status": "success",
                    "message": f"Terminated {len(terminated)} processes matching '{process_name}'",
                    "processes": terminated,
                }
            return {"status": "not_found", "message": f"No processes found matching '{process_name}'"}

        return {"status": "error", "message": "Either 'pid' or 'process_name' must be provided."}
    except Exception as e:
        return {"status": "error", "message": f"Failed to terminate process: {str(e)}"}
