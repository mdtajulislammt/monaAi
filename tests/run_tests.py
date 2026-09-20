"""Standalone test runner using Python standard library unittest."""
import shutil
import tempfile
import unittest
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.safety import SafetyValidator, SecurityException, get_safety_validator
from tools.file_ops import create_project_structure, list_dir, read_file, write_file
from tools.os_ops import get_system_stats
from tools.terminal_ops import execute_command


class StandaloneAgentToolsTest(unittest.TestCase):
    """Test suite runnable without third-party test runners."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="mona_standalone_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_block_forbidden_commands(self):
        validator = get_safety_validator()
        for cmd in ["rm -rf /", "rm -rf /*", ":(){ :|:& };:", "mkfs.ext4 /dev/sda1"]:
            allowed, reason = validator.validate_command(cmd)
            self.assertFalse(allowed, f"Expected '{cmd}' to be blocked!")
            self.assertIn("forbidden", reason.lower())

    def test_block_dangerous_patterns(self):
        validator = get_safety_validator()
        for cmd in ["rm -rf ~", "rm -rf $HOME/data", "dd if=/dev/zero of=/dev/sda"]:
            allowed, reason = validator.validate_command(cmd)
            self.assertFalse(allowed, f"Expected '{cmd}' to be blocked!")

    def test_allow_safe_commands(self):
        validator = get_safety_validator()
        for cmd in ["ls -la", "echo 123", "python3 --version"]:
            allowed, reason = validator.validate_command(cmd)
            self.assertTrue(allowed, f"Expected '{cmd}' to be allowed!")
            self.assertIsNone(reason)

    def test_block_protected_paths(self):
        validator = get_safety_validator()
        with self.assertRaises(SecurityException):
            validator.validate_path("/etc/passwd")

    def test_file_write_and_read(self):
        file_path = self.test_dir / "sample.txt"
        content = "Row 1\nRow 2\nRow 3\n"
        w_res = write_file(str(file_path), content)
        self.assertEqual(w_res["status"], "success")

        r_res = read_file(str(file_path), offset=0, limit=2)
        self.assertEqual(r_res["status"], "success")
        self.assertEqual(r_res["lines_returned"], 2)
        self.assertIn("Row 1", r_res["content"])

    def test_create_project_structure(self):
        structure = {
            "app": {
                "main.py": "print('ok')",
                "routers": {
                    "items.py": "# router"
                }
            },
            "README.md": "# Readme"
        }
        res = create_project_structure(str(self.test_dir), structure)
        self.assertEqual(res["status"], "success")
        self.assertTrue((self.test_dir / "app" / "main.py").exists())
        self.assertTrue((self.test_dir / "app" / "routers" / "items.py").exists())
        self.assertTrue((self.test_dir / "README.md").exists())

    def test_list_dir(self):
        (self.test_dir / "a.txt").write_text("a")
        (self.test_dir / "b.txt").write_text("b")
        res = list_dir(str(self.test_dir))
        self.assertEqual(res["status"], "success")
        self.assertGreaterEqual(res["count"], 2)

    def test_execute_safe_command(self):
        res = execute_command("echo 'Agent Verification Passed'")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("Agent Verification Passed", res["stdout"])

    def test_execute_blocked_command(self):
        res = execute_command("rm -rf /")
        self.assertEqual(res["status"], "security_denied")
        self.assertIn("SECURITY POLICY VIOLATION", res["stderr"])

    def test_execute_timeout(self):
        res = execute_command("sleep 3", timeout=1)
        self.assertEqual(res["status"], "timeout")
        self.assertEqual(res["exit_code"], -1)

    def test_system_stats(self):
        stats = get_system_stats()
        self.assertEqual(stats["status"], "success")
        self.assertIn("cpu_percent", stats)
        self.assertIn("memory", stats)
        self.assertIn("disk", stats)


if __name__ == "__main__":
    unittest.main()
