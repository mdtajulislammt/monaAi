"""Tools package exporting OS, File, Terminal, and Browser automation capabilities."""
from tools.os_ops import open_application, launch_ide, get_system_stats, kill_process
from tools.file_ops import create_project_structure, read_file, write_file, list_dir
from tools.terminal_ops import execute_command
from tools.browser_ops import open_url, take_screenshot, extract_page_content, search_web

__all__ = [
    # OS
    "open_application",
    "launch_ide",
    "get_system_stats",
    "kill_process",
    # File
    "create_project_structure",
    "read_file",
    "write_file",
    "list_dir",
    # Terminal
    "execute_command",
    # Browser
    "open_url",
    "take_screenshot",
    "extract_page_content",
    "search_web",
]
