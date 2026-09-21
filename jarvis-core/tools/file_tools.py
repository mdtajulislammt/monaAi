"""File system automation tools for JARVIS: atomic read/write, tree inspection, and search."""
import fnmatch
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)

DEFAULT_EXCLUDES = [
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    ".app_profile",
    "*.pyc",
    "*.lock",
]


def _resolve_safe_path(target_path: str, must_exist: bool = False) -> Path:
    """Resolve and validate path against workspace directory boundaries."""
    settings = get_settings()
    root = settings.workspace_root.resolve()
    resolved = Path(target_path).expanduser().resolve()

    # If relative, anchor to workspace_root
    if not Path(target_path).is_absolute():
        resolved = (root / target_path).resolve()

    if must_exist and not resolved.exists():
        raise FileNotFoundError(f"Path does not exist: {resolved}")

    # Check protected system paths in strict mode
    if settings.safety_mode == "STRICT":
        system_roots = [Path("/"), Path("/bin"), Path("/etc"), Path("/sys"), Path("/dev"), Path("/boot")]
        if resolved in system_roots:
            raise PermissionError(f"Access to protected system root '{resolved}' is restricted.")

    return resolved


def inspect_directory_tree(
    path: str = ".",
    max_depth: int = 3,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Inspect and generate a visual recursive directory tree.

    Args:
        path: Root directory to inspect.
        max_depth: Maximum recursion depth (1-5).
        exclude_patterns: Glob patterns to ignore.
    """
    try:
        root_dir = _resolve_safe_path(path, must_exist=True)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    excludes = list(DEFAULT_EXCLUDES)
    if exclude_patterns:
        excludes.extend(exclude_patterns)

    tree_lines: List[str] = [f"📂 {root_dir.name}/"]
    total_files = 0
    total_dirs = 0

    def _should_exclude(entry_name: str) -> bool:
        for pat in excludes:
            if fnmatch.fnmatch(entry_name, pat):
                return True
        return False

    def _build_tree(current_dir: Path, prefix: str, depth: int):
        nonlocal total_files, total_dirs
        if depth > max_depth:
            return

        try:
            entries = sorted(
                [e for e in current_dir.iterdir() if not _should_exclude(e.name)],
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )
        except (PermissionError, OSError) as pe:
            tree_lines.append(f"{prefix}└── [Access Denied: {pe}]")
            return

        count = len(entries)
        for idx, entry in enumerate(entries):
            is_last = (idx == count - 1)
            connector = "└── " if is_last else "├── "
            child_prefix = prefix + ("    " if is_last else "│   ")

            if entry.is_dir():
                total_dirs += 1
                tree_lines.append(f"{prefix}{connector}📁 {entry.name}/")
                _build_tree(entry, child_prefix, depth + 1)
            else:
                total_files += 1
                try:
                    size_kb = round(entry.stat().st_size / 1024, 1)
                    tree_lines.append(f"{prefix}{connector}📄 {entry.name} ({size_kb} KB)")
                except OSError:
                    tree_lines.append(f"{prefix}{connector}📄 {entry.name}")

    _build_tree(root_dir, "", 1)

    return {
        "status": "success",
        "root_path": str(root_dir),
        "total_dirs": total_dirs,
        "total_files": total_files,
        "tree_view": "\n".join(tree_lines),
    }


def read_workspace_file(
    file_path: str,
    start_line: int = 1,
    end_line: int = 500,
) -> Dict[str, Any]:
    """Read contents of a workspace file within specified line ranges safely.

    Args:
        file_path: Path to the target file.
        start_line: 1-indexed starting line number.
        end_line: 1-indexed ending line number.
    """
    try:
        resolved = _resolve_safe_path(file_path, must_exist=True)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    if not resolved.is_file():
        return {"status": "error", "message": f"Path is not a file: {resolved}"}

    # Safety check file size (max 5 MB for text read)
    file_size = resolved.stat().st_size
    if file_size > 5 * 1024 * 1024:
        return {
            "status": "error",
            "message": f"File is too large to read safely ({round(file_size/(1024*1024), 2)} MB). Max limit is 5 MB.",
        }

    # Read lines with robust encoding fallback
    lines: List[str] = []
    for enc in ["utf-8", "latin-1", "cp1252"]:
        try:
            with open(resolved, "r", encoding=enc, errors="replace") as f:
                lines = f.readlines()
            break
        except Exception:
            continue

    total_lines = len(lines)
    s_idx = max(0, start_line - 1)
    e_idx = min(total_lines, end_line)

    sliced = lines[s_idx:e_idx]
    content = "".join(sliced)

    return {
        "status": "success",
        "file_path": str(resolved),
        "total_lines": total_lines,
        "start_line": s_idx + 1,
        "end_line": e_idx,
        "content": content,
    }


def write_workspace_file(
    file_path: str,
    content: str,
    atomic: bool = True,
) -> Dict[str, Any]:
    """Write text content to a workspace file atomically to avoid partial writes or race conditions.

    Args:
        file_path: Path to target file.
        content: String content to write.
        atomic: If True, uses temporary file and atomic replace.
    """
    try:
        resolved = _resolve_safe_path(file_path, must_exist=False)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # Ensure parent directory exists
    resolved.parent.mkdir(parents=True, exist_ok=True)

    try:
        if atomic:
            # Write to temporary file in the same directory to guarantee atomic rename
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=str(resolved.parent),
                delete=False,
            ) as tmp:
                tmp.write(content)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_name = tmp.name

            # Atomic rename / replace
            os.replace(temp_name, str(resolved))
        else:
            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)

        bytes_written = len(content.encode("utf-8"))
        return {
            "status": "success",
            "file_path": str(resolved),
            "bytes_written": bytes_written,
            "message": f"Successfully wrote {bytes_written} bytes to '{resolved.name}'.",
        }
    except Exception as e:
        logger.error(f"Error writing to file {resolved}: {e}")
        return {"status": "error", "message": f"Failed to write file: {str(e)}"}


def search_workspace_files(
    query: str,
    root_dir: str = ".",
    is_regex: bool = False,
    file_extension: Optional[str] = None,
    max_results: int = 20,
) -> Dict[str, Any]:
    """Search for string or regex patterns in workspace files."""
    try:
        base_dir = _resolve_safe_path(root_dir, must_exist=True)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    pattern = re.compile(query, re.IGNORECASE) if is_regex else None
    matches: List[Dict[str, Any]] = []

    for root, dirs, files in os.walk(base_dir):
        # Exclude directories in-place
        dirs[:] = [d for d in dirs if not any(fnmatch.fnmatch(d, p) for p in DEFAULT_EXCLUDES)]

        for f in files:
            if any(fnmatch.fnmatch(f, p) for p in DEFAULT_EXCLUDES):
                continue
            if file_extension and not f.endswith(file_extension):
                continue

            full_path = Path(root) / f
            try:
                # Check filename match
                if (pattern and pattern.search(f)) or (not pattern and query.lower() in f.lower()):
                    matches.append({
                        "file": str(full_path.relative_to(base_dir)),
                        "type": "filename_match",
                        "line": None,
                        "snippet": f,
                    })

                # Search content in text files (< 2 MB)
                if full_path.stat().st_size < 2 * 1024 * 1024:
                    with open(full_path, "r", encoding="utf-8", errors="ignore") as file_obj:
                        for line_num, line in enumerate(file_obj, 1):
                            if (pattern and pattern.search(line)) or (not pattern and query.lower() in line.lower()):
                                matches.append({
                                    "file": str(full_path.relative_to(base_dir)),
                                    "type": "content_match",
                                    "line": line_num,
                                    "snippet": line.strip()[:160],
                                })
                                if len(matches) >= max_results:
                                    break
            except Exception:
                continue

            if len(matches) >= max_results:
                break
        if len(matches) >= max_results:
            break

    return {
        "status": "success",
        "query": query,
        "count": len(matches),
        "results": matches,
    }
