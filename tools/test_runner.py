"""Minimal test-runner wrapper built on top of CodeExecutor."""

from __future__ import annotations

import sys
from pathlib import Path

from .code_executor import CodeExecutor, CommandResult


class TestRunner:
    """Run project tests in a repeatable way."""

    def __init__(self, project_root: Path) -> None:
        self.executor = CodeExecutor(project_root)

    def run_python_unittests(self) -> CommandResult:
        return self.executor.run(
            [
                sys.executable,
                "-m",
                "unittest",
                "discover",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            ]
        )
