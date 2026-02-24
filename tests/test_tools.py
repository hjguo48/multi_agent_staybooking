from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys

from tools import CodeExecutor, FileSystemTool, TestRunner


class ToolWrapperTests(unittest.TestCase):
    def test_file_system_read_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            fs = FileSystemTool(root)
            fs.write_text("a/b/test.txt", "hello")
            self.assertTrue(fs.exists("a/b/test.txt"))
            self.assertEqual("hello", fs.read_text("a/b/test.txt"))

    def test_code_executor_runs_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            executor = CodeExecutor(root)
            result = executor.run([sys.executable, "-c", "print('ok')"])
            self.assertEqual(0, result.returncode)
            self.assertIn("ok", result.stdout)

    def test_test_runner_command_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            runner = TestRunner(Path(tmpdir))
            result = runner.run_python_unittests()
            self.assertIsNotNone(result.returncode)


if __name__ == "__main__":
    unittest.main()
