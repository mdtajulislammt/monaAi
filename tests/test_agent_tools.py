"""Unit and integration test suite for monaAi Desktop Agent tools and safety guards."""
import os
import shutil
import tempfile
import sys
from pathlib import Path
import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.safety import SafetyValidator, SecurityException, get_safety_validator
from tools.file_ops import create_project_structure, list_dir, read_file, write_file
from tools.os_ops import get_system_stats
from tools.terminal_ops import execute_command


@pytest.fixture
def temp_dir():
    """Create a temporary directory for safe filesystem test operations."""
    d = tempfile.mkdtemp(prefix="mona_test_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


class TestSafetyValidator:
    """Test security filter against malicious commands and paths."""

    def test_block_forbidden_commands(self):
        validator = get_safety_validator()

        # Exact match or substring forbidden commands
        allowed, reason = validator.validate_command("rm -rf /")
        assert not allowed
        assert "forbidden" in reason.lower()

        allowed, reason = validator.validate_command("rm -rf /*")
        assert not allowed

        allowed, reason = validator.validate_command(":(){ :|:& };:")
        assert not allowed

        allowed, reason = validator.validate_command("mkfs.ext4 /dev/sda1")
        assert not allowed

    def test_block_dangerous_patterns(self):
        validator = get_safety_validator()

        # Regex patterns
        allowed, reason = validator.validate_command("rm -rf ~")
        assert not allowed

        allowed, reason = validator.validate_command("rm -rf $HOME/something")
        assert not allowed

        allowed, reason = validator.validate_command("dd if=/dev/zero of=/dev/sda bs=1M")
        assert not allowed

    def test_allow_safe_commands(self):
        validator = get_safety_validator()

        allowed, reason = validator.validate_command("ls -la")
        assert allowed
        assert reason is None

        allowed, reason = validator.validate_command("python3 --version")
        assert allowed

    def test_block_protected_paths(self):
        validator = get_safety_validator()

        with pytest.raises(SecurityException):
            validator.validate_path("/etc/shadow")

        with pytest.raises(SecurityException):
            validator.validate_path("/boot/vmlinuz")


class TestFileOperations:
    """Test safe file scaffolding, reading, writing, and listing."""

    def test_write_and_read_file(self, temp_dir):
        test_file = temp_dir / "sample.txt"
        test_content = "Line 1: Hello\nLine 2: World\nLine 3: Gemini"

        write_res = write_file(str(test_file), test_content)
        assert write_res["status"] == "success"
        assert test_file.exists()

        read_res = read_file(str(test_file), offset=0, limit=2)
        assert read_res["status"] == "success"
        assert read_res["lines_returned"] == 2
        assert "Hello" in read_res["content"]

    def test_create_project_structure(self, temp_dir):
        structure = {
            "src": {
                "main.py": "print('hello world')",
                "submodule": {
                    "module.py": "# module code"
                }
            },
            "README.md": "# Test Project"
        }

        result = create_project_structure(str(temp_dir), structure)
        assert result["status"] == "success"
        assert (temp_dir / "src" / "main.py").exists()
        assert (temp_dir / "src" / "submodule" / "module.py").exists()
        assert (temp_dir / "README.md").exists()

    def test_list_dir(self, temp_dir):
        (temp_dir / "file1.txt").write_text("1")
        (temp_dir / "file2.txt").write_text("2")
        (temp_dir / "subfolder").mkdir()

        result = list_dir(str(temp_dir))
        assert result["status"] == "success"
        assert result["count"] >= 3


class TestTerminalOperations:
    """Test shell command execution, timeouts, and safety gating."""

    def test_execute_safe_command(self):
        res = execute_command("echo 'Hello from monaAi'")
        assert res["status"] == "success"
        assert res["exit_code"] == 0
        assert "Hello from monaAi" in res["stdout"]

    def test_execute_blocked_command(self):
        res = execute_command("rm -rf /")
        assert res["status"] == "security_denied"
        assert "SECURITY POLICY VIOLATION" in res["stderr"]

    def test_execute_timeout(self):
        # Command sleeps 5s with 1s timeout
        res = execute_command("sleep 5", timeout=1)
        assert res["status"] == "timeout"
        assert res["exit_code"] == -1


class TestOSOperations:
    """Test system statistics retrieval."""

    def test_system_stats(self):
        stats = get_system_stats()
        assert stats["status"] == "success"
        assert "cpu_percent" in stats
        assert "memory" in stats
        assert "disk" in stats


class TestMemoryManager:
    """Test persistent memory storage, time context, and recall."""

    def test_memory_persistence(self, temp_dir):
        from core.memory import MemoryManager, get_bengali_time_context
        mem_file = temp_dir / "test_memory.json"
        mem = MemoryManager(memory_file=mem_file)

        # Test facts
        assert mem.add_fact("ইউজারের নাম তাজুল ইসলাম।")
        assert not mem.add_fact("ইউজারের নাম তাজুল ইসলাম।")  # Duplicate not added
        assert "ইউজারের নাম তাজুল ইসলাম।" in mem.get_facts()

        # Test history turn recording
        mem.save_turn("user", "মোনা কেমন আছো?")
        mem.save_turn("model", "হ্যাঁ জান, আমি ভালো আছি!")

        # Verify disk persistence by loading in new instance
        mem2 = MemoryManager(memory_file=mem_file)
        assert "ইউজারের নাম তাজুল ইসলাম।" in mem2.get_facts()
        gemini_hist = mem2.get_history_for_gemini()
        assert len(gemini_hist) == 2
        assert gemini_hist[0]["role"] == "user"
        assert gemini_hist[1]["role"] == "model"

        # Test time context
        ctx = get_bengali_time_context()
        assert "day" in ctx
        assert "time" in ctx
        assert "full" in ctx

