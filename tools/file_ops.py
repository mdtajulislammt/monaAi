"""File and directory management operations."""
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from core.safety import SecurityException, get_safety_validator

logger = logging.getLogger(__name__)


def create_project_structure(
    base_path: str,
    structure: Union[Dict[str, Any], List[str]],
) -> Dict[str, Any]:
    """Recursively create directories and initial files for a project scaffold.

    Args:
        base_path: Base directory to scaffold in.
        structure: Dictionary of nested paths and contents, or list of relative file/dir paths.
                   Example dict: {"src": {"main.py": "print('hello')", "models": {}}, "README.md": "# Title"}
                   Example list: ["src/main.py", "src/models/", "README.md"]

    Returns:
        Dictionary detailing created files and directories.
    """
    validator = get_safety_validator()
    try:
        root = validator.validate_path(base_path, must_exist=False)
        root.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return {"status": "error", "message": f"Failed to initialize base directory: {str(e)}"}

    created_dirs: List[str] = [str(root)]
    created_files: List[str] = []

    def _scaffold_dict(current_dir: Path, subtree: Dict[str, Any]):
        for key, value in subtree.items():
            item_path = current_dir / key
            if isinstance(value, dict):
                item_path.mkdir(parents=True, exist_ok=True)
                created_dirs.append(str(item_path))
                _scaffold_dict(item_path, value)
            elif isinstance(value, str):
                item_path.parent.mkdir(parents=True, exist_ok=True)
                with open(item_path, "w", encoding="utf-8") as f:
                    f.write(value)
                created_files.append(str(item_path))
            elif value is None:
                # Interpret as empty directory if ends with / or has no extension, else empty file
                if key.endswith("/") or "." not in key:
                    item_path.mkdir(parents=True, exist_ok=True)
                    created_dirs.append(str(item_path))
                else:
                    item_path.parent.mkdir(parents=True, exist_ok=True)
                    item_path.touch(exist_ok=True)
                    created_files.append(str(item_path))

    def _scaffold_list(current_dir: Path, items: List[str]):
        for item in items:
            item_path = current_dir / item
            if item.endswith("/") or "." not in item_path.name:
                item_path.mkdir(parents=True, exist_ok=True)
                created_dirs.append(str(item_path))
            else:
                item_path.parent.mkdir(parents=True, exist_ok=True)
                item_path.touch(exist_ok=True)
                created_files.append(str(item_path))

    try:
        if isinstance(structure, dict):
            _scaffold_dict(root, structure)
        elif isinstance(structure, list):
            _scaffold_list(root, structure)
        else:
            return {"status": "error", "message": "Structure must be a dictionary or list."}

        return {
            "status": "success",
            "message": f"Scaffolded structure in '{root}'. Created {len(created_dirs)} directories and {len(created_files)} files.",
            "base_path": str(root),
            "directories_count": len(created_dirs),
            "files_count": len(created_files),
        }
    except Exception as e:
        logger.error(f"Error while scaffolding: {e}")
        return {"status": "error", "message": f"Scaffolding error: {str(e)}"}


def read_file(file_path: str, offset: int = 0, limit: int = 300) -> Dict[str, Any]:
    """Read contents of a file safely with line range limits.

    Args:
        file_path: Path to the target file.
        offset: Starting line index (0-based).
        limit: Maximum number of lines to return.

    Returns:
        Dictionary containing file contents, total lines, and line metadata.
    """
    validator = get_safety_validator()
    try:
        resolved = validator.validate_path(file_path, must_exist=True)
        if not resolved.is_file():
            return {"status": "error", "message": f"Target '{resolved}' is not a regular file."}

        with open(resolved, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        total_lines = len(all_lines)
        sliced_lines = all_lines[offset : offset + limit]
        content = "".join(sliced_lines)

        return {
            "status": "success",
            "file_path": str(resolved),
            "total_lines": total_lines,
            "offset": offset,
            "limit": limit,
            "lines_returned": len(sliced_lines),
            "content": content,
        }
    except SecurityException as se:
        return {"status": "security_denied", "message": str(se)}
    except FileNotFoundError:
        return {"status": "not_found", "message": f"File '{file_path}' does not exist."}
    except Exception as e:
        logger.error(f"Error reading file '{file_path}': {e}")
        return {"status": "error", "message": f"Error reading file: {str(e)}"}


def write_file(file_path: str, content: str, overwrite: bool = False) -> Dict[str, Any]:
    """Write text content to a target file.

    Args:
        file_path: Path to the file to create or overwrite.
        content: String content to write.
        overwrite: If True, replaces existing file. If False, fails if file exists.

    Returns:
        Dictionary with status and bytes written.
    """
    validator = get_safety_validator()
    try:
        resolved = validator.validate_path(file_path, must_exist=False)

        if resolved.exists() and not overwrite:
            return {
                "status": "exists",
                "message": f"File '{resolved}' already exists and overwrite is set to False.",
            }

        resolved.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved, "w", encoding="utf-8") as f:
            bytes_written = f.write(content)

        return {
            "status": "success",
            "message": f"Successfully written {bytes_written} characters to '{resolved}'.",
            "file_path": str(resolved),
            "bytes": bytes_written,
        }
    except SecurityException as se:
        return {"status": "security_denied", "message": str(se)}
    except Exception as e:
        logger.error(f"Error writing file '{file_path}': {e}")
        return {"status": "error", "message": f"Error writing file: {str(e)}"}


def list_dir(
    dir_path: str = ".",
    recursive: bool = False,
    max_items: int = 100,
) -> Dict[str, Any]:
    """List entries inside a directory with metadata.

    Args:
        dir_path: Directory path to inspect (defaults to current directory).
        recursive: If True, lists nested subdirectories.
        max_items: Limit of items to prevent massive directory dumps.

    Returns:
        Dictionary with item details (name, path, is_dir, size_bytes, modified).
    """
    validator = get_safety_validator()
    try:
        resolved = validator.validate_path(dir_path, must_exist=True)
        if not resolved.is_dir():
            return {"status": "error", "message": f"'{resolved}' is not a directory."}

        items: List[Dict[str, Any]] = []

        if recursive:
            for root, dirs, files in os.walk(resolved):
                for d in dirs:
                    p = Path(root) / d
                    items.append({
                        "name": d,
                        "path": str(p.relative_to(resolved)),
                        "is_dir": True,
                    })
                    if len(items) >= max_items:
                        break
                for f in files:
                    p = Path(root) / f
                    try:
                        stat = p.stat()
                        items.append({
                            "name": f,
                            "path": str(p.relative_to(resolved)),
                            "is_dir": False,
                            "size_bytes": stat.st_size,
                            "modified": time.ctime(stat.st_mtime),
                        })
                    except Exception:
                        pass
                    if len(items) >= max_items:
                        break
                if len(items) >= max_items:
                    break
        else:
            for entry in sorted(resolved.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                try:
                    stat = entry.stat()
                    items.append({
                        "name": entry.name,
                        "is_dir": entry.is_dir(),
                        "size_bytes": stat.st_size if entry.is_file() else None,
                        "modified": time.ctime(stat.st_mtime),
                    })
                except Exception:
                    continue
                if len(items) >= max_items:
                    break

        return {
            "status": "success",
            "directory": str(resolved),
            "count": len(items),
            "items": items,
            "truncated": len(items) >= max_items,
        }
    except SecurityException as se:
        return {"status": "security_denied", "message": str(se)}
    except Exception as e:
        logger.error(f"Error listing directory '{dir_path}': {e}")
        return {"status": "error", "message": f"Error listing directory: {str(e)}"}
