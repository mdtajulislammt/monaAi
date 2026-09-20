"""Model Context Protocol (MCP) server exposing desktop automation tools to Antigravity IDE."""
import json
import logging
import sys
from typing import Any, Dict, List, Optional, Union

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

from tools.browser_ops import (
    extract_page_content as _extract_page_content,
    open_url as _open_url,
    search_web as _search_web,
    take_screenshot as _take_screenshot,
)
from tools.file_ops import (
    create_project_structure as _create_project_structure,
    list_dir as _list_dir,
    read_file as _read_file,
    write_file as _write_file,
)
from tools.os_ops import (
    get_system_stats as _get_system_stats,
    kill_process as _kill_process,
    launch_ide as _launch_ide,
    open_application as _open_application,
)
from tools.terminal_ops import execute_command as _execute_command

# Initialize FastMCP application
mcp = FastMCP("mona-desktop-agent") if FastMCP else None


if mcp:
    @mcp.tool()
    def execute_command(
        command: str,
        cwd: Optional[str] = None,
        timeout: Optional[int] = 60,
    ) -> Dict[str, Any]:
        """Execute a safe shell command with real-time stdout/stderr capture and timeout."""
        return _execute_command(command=command, cwd=cwd, timeout=timeout)

    @mcp.tool()
    def open_application(app_name: str) -> Dict[str, Any]:
        """Open a desktop application cross-platform (e.g. 'firefox', 'vlc', 'gedit')."""
        return _open_application(app_name=app_name)

    @mcp.tool()
    def launch_ide(
        ide_name: str = "vscode",
        workspace_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Launch an IDE workspace (VS Code, Antigravity, Cursor, PyCharm)."""
        return _launch_ide(ide_name=ide_name, workspace_path=workspace_path)

    @mcp.tool()
    def get_system_stats() -> Dict[str, Any]:
        """Get CPU, Memory, Disk usage and top processes using psutil."""
        return _get_system_stats()

    @mcp.tool()
    def kill_process(
        process_name: Optional[str] = None,
        pid: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Safely terminate a desktop process by name or PID."""
        return _kill_process(process_name=process_name, pid=pid)

    @mcp.tool()
    def create_project_structure(
        base_path: str,
        structure: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Recursively scaffold directories and files for a new project."""
        return _create_project_structure(base_path=base_path, structure=structure)

    @mcp.tool()
    def read_file(
        file_path: str,
        offset: int = 0,
        limit: int = 300,
    ) -> Dict[str, Any]:
        """Read a slice of lines from a local file safely."""
        return _read_file(file_path=file_path, offset=offset, limit=limit)

    @mcp.tool()
    def write_file(
        file_path: str,
        content: str,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """Write content to a file with automatic directory creation and safety checks."""
        return _write_file(file_path=file_path, content=content, overwrite=overwrite)

    @mcp.tool()
    def list_dir(
        dir_path: str = ".",
        recursive: bool = False,
        max_items: int = 100,
    ) -> Dict[str, Any]:
        """List contents of a directory with file sizes and timestamps."""
        return _list_dir(dir_path=dir_path, recursive=recursive, max_items=max_items)

    @mcp.tool()
    def open_url(url: str, headless: Optional[bool] = None) -> Dict[str, Any]:
        """Navigate to a website URL with Playwright and return title and status."""
        return _open_url(url=url, headless=headless)

    @mcp.tool()
    def take_screenshot(
        url: str,
        output_path: str,
        full_page: bool = False,
    ) -> Dict[str, Any]:
        """Capture a web page screenshot using Playwright."""
        return _take_screenshot(url=url, output_path=output_path, full_page=full_page)

    @mcp.tool()
    def extract_page_content(
        url: str,
        selector: Optional[str] = None,
        max_chars: int = 4000,
    ) -> Dict[str, Any]:
        """Extract cleaned text content from a web page using Playwright."""
        return _extract_page_content(url=url, selector=selector, max_chars=max_chars)

    @mcp.tool()
    def search_web(query: str, num_results: int = 5) -> Dict[str, Any]:
        """Search the web and return top result titles, snippets, and URLs."""
        return _search_web(query=query, num_results=num_results)


def main():
    """Run FastMCP server over stdio transport."""
    if mcp is None:
        sys.stderr.write(
            "Error: 'mcp' library is not installed. Install with: pip install mcp\n"
        )
        sys.exit(1)
    # FastMCP uses stdio transport by default
    mcp.run()


if __name__ == "__main__":
    main()
