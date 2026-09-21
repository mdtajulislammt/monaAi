"""Comprehensive automated test suite for JARVIS Core."""
import asyncio
import os
import shutil
import tempfile
from pathlib import Path

import pytest
from config.settings import Settings, get_settings
from memory.vector_store import ChromaMemoryManager
from memory.reflection_engine import ExecutionReflectionEngine
from tools.system_tools import (
    SafetyGuard,
    execute_terminal_command,
    get_system_telemetry,
    manage_process,
)
from tools.file_tools import (
    inspect_directory_tree,
    read_workspace_file,
    write_workspace_file,
    search_workspace_files,
)
from interfaces.voice_engine import BengaliVoiceEngine
from core.agent import JarvisAgent
import mcp_server


@pytest.fixture
def temp_workspace():
    """Create isolated temporary directory for file and memory tests."""
    temp_dir = tempfile.mkdtemp(prefix="jarvis_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestConfigAndSafety:
    """Test configuration loading and safety boundaries."""

    def test_settings_initialization(self):
        settings = get_settings()
        assert settings.voice_locale == "bn-BD"
        assert settings.voice_name in ["bn-BD-NabanitaNeural", "bn-BD-PradeepNeural"]
        assert settings.safety_mode in ["STRICT", "MODERATE", "PERMISSIVE"]
        assert settings.command_timeout_seconds > 0

    def test_safety_guard_blocks_catastrophic_commands(self):
        guard = SafetyGuard()

        blocked_cmds = [
            "rm -rf /",
            "rm -rf ~",
            ":(){ :|:& };:",
            "mkfs /dev/sda",
            "dd if=/dev/zero of=/dev/sda",
            "rm -rf /etc",
        ]
        for cmd in blocked_cmds:
            is_safe, reason = guard.validate_command(cmd)
            assert not is_safe, f"Expected '{cmd}' to be blocked, but was allowed."
            assert reason is not None

    def test_safety_guard_allows_safe_commands(self):
        guard = SafetyGuard()

        safe_cmds = [
            "ls -la",
            "pwd",
            "echo 'Hello JARVIS'",
            "python --version",
            "git status",
        ]
        for cmd in safe_cmds:
            is_safe, reason = guard.validate_command(cmd)
            assert is_safe, f"Expected '{cmd}' to be safe, but got blocked: {reason}"


class TestMemoryAndReflection:
    """Test ChromaDB persistence and self-learning reflection loop."""

    def test_vector_store_crud(self, temp_workspace):
        mem_dir = temp_workspace / "chroma_test"
        mm = ChromaMemoryManager(persist_dir=mem_dir)

        # Store interaction turn
        turn_id = mm.store_interaction("ইউজার কী বললেন?", "জার্ভিস উত্তর দিলেন।")
        assert turn_id.startswith("chat_")

        # Store fact
        fact_id = mm.store_fact("ইউজারের প্রিয় ভাষা বাংলা", category="language")
        assert fact_id.startswith("fact_")

        # Semantic recall
        recalled = mm.semantic_recall("ভাষা", n_results=2)
        assert "ইউজারের প্রিয় ভাষা বাংলা" in recalled or "FACT" in recalled

    def test_reflection_engine_diagnosis_and_storage(self, temp_workspace):
        mem_dir = temp_workspace / "chroma_ref_test"
        mm = ChromaMemoryManager(persist_dir=mem_dir)
        re = ExecutionReflectionEngine(memory_manager=mm)

        # Log simulated failure
        action = "pytest non_existent_file.py"
        err = "FileNotFoundError: [Errno 2] No such file or directory: 'non_existent_file.py'"
        ref_id = re.log_execution(action=action, success=False, error=err)
        assert ref_id is not None
        assert "ref_" in ref_id

        # Query reflections
        prompt_snippet = re.format_reflection_prompt("non_existent_file.py")
        assert "PAST EXECUTION LESSONS" in prompt_snippet
        assert "FileNotFound" in prompt_snippet

        # Record explicit learned fix
        fix_id = re.record_learned_fix(
            action="pytest non_existent_file.py",
            error_encountered=err,
            working_fix="Create file or specify valid path: pytest tests/test_jarvis_core.py",
        )
        assert fix_id is not None


class TestToolsSuite:
    """Test system and file operations."""

    def test_safe_terminal_execution(self):
        res = execute_terminal_command("echo 'JARVIS Test'")
        assert res["status"] == "success"
        assert res["exit_code"] == 0
        assert "JARVIS Test" in res["stdout"]

    def test_terminal_blocks_unsafe_execution(self):
        res = execute_terminal_command("rm -rf /")
        assert res["status"] == "security_blocked"
        assert res["exit_code"] == -1
        assert "SECURITY_POLICY_VIOLATION" in res["stderr"]

    def test_system_telemetry_structure(self):
        telem = get_system_telemetry()
        assert "cpu" in telem
        assert "ram" in telem
        assert "disk_root" in telem
        assert "cores" in telem["cpu"]
        assert telem["ram"]["total_gb"] > 0

    def test_process_management_protection(self):
        # Protecting PID 1
        res = manage_process(action="terminate", pid=1)
        assert res["status"] == "security_blocked"

    def test_atomic_file_write_and_read(self, temp_workspace):
        test_file = temp_workspace / "sample.txt"
        sample_text = "JARVIS Line 1\nJARVIS Line 2\nJARVIS Line 3\n"

        w_res = write_workspace_file(str(test_file), sample_text, atomic=True)
        assert w_res["status"] == "success"
        assert test_file.exists()

        r_res = read_workspace_file(str(test_file), start_line=1, end_line=2)
        assert r_res["status"] == "success"
        assert "Line 1" in r_res["content"]
        assert "Line 2" in r_res["content"]

    def test_directory_tree_inspection(self, temp_workspace):
        # Create subfolders and files
        (temp_workspace / "sub1").mkdir()
        (temp_workspace / "sub1" / "fileA.txt").write_text("Hello")
        (temp_workspace / "sub2").mkdir()

        tree = inspect_directory_tree(str(temp_workspace), max_depth=2)
        assert tree["status"] == "success"
        assert tree["total_files"] >= 1
        assert "sub1" in tree["tree_view"]


class TestVoiceEngine:
    """Test voice engine sanitization and edge-tts synthesis."""

    def test_text_sanitization(self):
        ve = BengaliVoiceEngine()
        raw = "```python\nprint('code')\n```\nHere is [link](http://test.com) and **bold** text."
        clean = ve._sanitize_text_for_speech(raw)
        assert "```" not in clean
        assert "http" not in clean
        assert "**" not in clean
        assert "bold text" in clean

    @pytest.mark.asyncio
    async def test_edge_tts_bengali_audio_generation(self, temp_workspace):
        ve = BengaliVoiceEngine()
        audio_dest = str(temp_workspace / "bengali_speech.mp3")

        status = await ve._generate_audio_file("সব সিস্টেম প্রস্তুত স্যার।", audio_dest)
        assert status is True
        assert os.path.exists(audio_dest)
        assert os.path.getsize(audio_dest) > 1000


class TestJarvisAgentAndFastMCP:
    """Test agent registration and FastMCP server interface."""

    def test_agent_tool_registry(self):
        agent = JarvisAgent()
        assert len(agent.tools) >= 12
        tool_names = [t.__name__ for t in agent.tools]
        assert "execute_terminal_command" in tool_names
        assert "get_system_telemetry" in tool_names
        assert "inspect_directory_tree" in tool_names
        assert "query_agent_memory" in tool_names
        assert "send_desktop_message" in tool_names
        assert "open_desktop_application" in tool_names
        assert "automate_gui_action" in tool_names
        assert "capture_desktop_screen" in tool_names
        assert "analyze_screen_content" in tool_names

    def test_fastmcp_server_binding(self):
        assert mcp_server.mcp is not None
        assert mcp_server.mcp.name == "jarvis-core"

