"""Model Context Protocol (FastMCP) Server for JARVIS.

Exposes local autonomous workstation tools, system telemetry, file operations,
headless research, and vector memory retrieval to Google Antigravity IDE and VS Code.
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure jarvis-core directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import FastMCP supporting both MCP 1.x and MCP 2.x (MCPServer)
try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        FastMCP = None

from memory.vector_store import get_memory_manager
from memory.reflection_engine import get_reflection_engine
from tools.system_tools import (
    execute_terminal_command as _execute_terminal_command,
    get_system_telemetry as _get_system_telemetry,
    manage_process as _manage_process,
    launch_developer_ide as _launch_developer_ide,
    open_desktop_application as _open_desktop_application,
    automate_gui_action as _automate_gui_action,
    send_desktop_message as _send_desktop_message,
)
from tools.file_tools import (
    inspect_directory_tree as _inspect_directory_tree,
    read_workspace_file as _read_workspace_file,
    write_workspace_file as _write_workspace_file,
    search_workspace_files as _search_workspace_files,
)
from tools.browser_tools import (
    search_web_research as _search_web_research,
    extract_web_page_content as _extract_web_page_content,
    capture_web_screenshot as _capture_web_screenshot,
)
from tools.screen_tools import (
    capture_desktop_screen as _capture_desktop_screen,
    analyze_screen_content as _analyze_screen_content,
)

if not FastMCP:
    raise ImportError("Neither 'mcp.server.mcpserver' nor 'mcp.server.fastmcp' could be loaded. Install mcp>=1.2.0")

# Initialize FastMCP Server
mcp = FastMCP("jarvis-core")


@mcp.tool()
def execute_terminal_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute a shell command with strict safety validation, timeout limits, and real-time capture."""
    return _execute_terminal_command(command=command, cwd=cwd, timeout=timeout)


@mcp.tool()
def get_system_telemetry() -> Dict[str, Any]:
    """Retrieve comprehensive system telemetry (CPU, RAM, Disk, Swap, and top resource-consuming processes)."""
    return _get_system_telemetry()


@mcp.tool()
def manage_process(
    action: str,
    pid: Optional[int] = None,
    process_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspect ('list', 'find') or safely terminate ('terminate', 'kill') workstation processes."""
    return _manage_process(action=action, pid=pid, process_name=process_name)


@mcp.tool()
def launch_developer_ide(
    ide_name: str,
    project_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Launch developer IDE ('antigravity', 'vscode', 'cursor') with an optional workspace path."""
    return _launch_developer_ide(ide_name=ide_name, project_path=project_path)


@mcp.tool()
def open_desktop_application(app_name: str) -> Dict[str, Any]:
    """Launch or bring to focus a local desktop application (e.g. Telegram, Discord, Chrome, VS Code)."""
    return _open_desktop_application(app_name=app_name)


@mcp.tool()
def automate_gui_action(
    action: str,
    text: Optional[str] = None,
    key: Optional[str] = None,
    hotkey: Optional[List[str]] = None,
    delay_seconds: float = 0.4,
) -> Dict[str, Any]:
    """Perform desktop GUI keyboard or mouse automation ('type', 'paste', 'press', 'hotkey', 'click')."""
    return _automate_gui_action(
        action=action,
        text=text,
        key=key,
        hotkey=hotkey,
        delay_seconds=delay_seconds,
    )


@mcp.tool()
def send_desktop_message(
    app_name: str,
    contact_name: str,
    message: str,
) -> Dict[str, Any]:
    """Search a contact and send a message directly in desktop applications like Telegram or Discord."""
    return _send_desktop_message(app_name=app_name, contact_name=contact_name, message=message)



@mcp.tool()
def inspect_directory_tree(
    path: str = ".",
    max_depth: int = 3,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Inspect and generate a visual recursive directory tree, filtering out build and dependency caches."""
    return _inspect_directory_tree(path=path, max_depth=max_depth, exclude_patterns=exclude_patterns)


@mcp.tool()
def read_workspace_file(
    file_path: str,
    start_line: int = 1,
    end_line: int = 500,
) -> Dict[str, Any]:
    """Read contents of a workspace file within specified line ranges safely."""
    return _read_workspace_file(file_path=file_path, start_line=start_line, end_line=end_line)


@mcp.tool()
def write_workspace_file(
    file_path: str,
    content: str,
    atomic: bool = True,
) -> Dict[str, Any]:
    """Write text content to a workspace file atomically to avoid partial writes or corruption."""
    return _write_workspace_file(file_path=file_path, content=content, atomic=atomic)


@mcp.tool()
def search_workspace_files(
    query: str,
    root_dir: str = ".",
    is_regex: bool = False,
    file_extension: Optional[str] = None,
    max_results: int = 20,
) -> Dict[str, Any]:
    """Search for string or regex patterns across workspace filenames and file contents."""
    return _search_workspace_files(
        query=query,
        root_dir=root_dir,
        is_regex=is_regex,
        file_extension=file_extension,
        max_results=max_results,
    )


@mcp.tool()
def search_web_research(
    query: str,
    max_results: int = 5,
) -> Dict[str, Any]:
    """Execute external web research search using headless Playwright or fast HTTP fallback."""
    return _search_web_research(query=query, max_results=max_results)


@mcp.tool()
def extract_web_page_content(
    url: str,
    max_chars: int = 4000,
) -> Dict[str, Any]:
    """Navigate to a URL with headless Playwright and extract clean readable text content."""
    return _extract_web_page_content(url=url, max_chars=max_chars)


@mcp.tool()
def capture_web_screenshot(
    url: str,
    output_path: str = "screenshot.png",
) -> Dict[str, Any]:
    """Capture a screenshot of a target webpage using headless Playwright."""
    return _capture_web_screenshot(url=url, output_path=output_path)


@mcp.tool()
def capture_desktop_screen(
    output_path: Optional[str] = None,
    delay_ms: int = 0,
) -> Dict[str, Any]:
    """Capture a screenshot of the entire desktop monitor screen."""
    return _capture_desktop_screen(output_path=output_path, delay_ms=delay_ms)


@mcp.tool()
def analyze_screen_content(
    query: str = "মনিটরে বর্তমানে কী কী অ্যাপ্লিকেশন, উইন্ডো বা কনটেন্ট দৃশ্যমান এবং এর অবস্থা কী?",
) -> Dict[str, Any]:
    """Take a screenshot of the monitor and analyze its visual content using Gemini Multimodal Vision."""
    return _analyze_screen_content(query=query)


@mcp.tool()
def query_agent_memory(query: str) -> Dict[str, Any]:
    """Search JARVIS episodic and semantic ChromaDB vector memory for past context or facts."""
    mm = get_memory_manager()
    recalled = mm.semantic_recall(query, n_results=4)
    return {
        "status": "success",
        "query": query,
        "recalled_context": recalled or "No matching memories found.",
    }


@mcp.tool()
def store_agent_memory(fact_or_preference: str, category: str = "preference") -> Dict[str, Any]:
    """Store an explicit technical fact, rule, or user preference into persistent vector memory."""
    mm = get_memory_manager()
    doc_id = mm.store_fact(fact_or_preference, category=category)
    return {
        "status": "success",
        "doc_id": doc_id,
        "message": f"Successfully stored in vector memory: '{fact_or_preference}'",
    }


@mcp.tool()
def query_reflections(query: str) -> Dict[str, Any]:
    """Query past execution failure reflections and learned fixes to avoid repeating mistakes."""
    re = get_reflection_engine()
    reflections = re.retrieve_relevant_reflections(query, n_results=3)
    return {
        "status": "success",
        "query": query,
        "count": len(reflections),
        "reflections": [r["document"] for r in reflections],
    }


def run_server():
    """Run FastMCP server using standard I/O transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
