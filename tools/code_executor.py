"""Command execution wrapper for controlled build/test steps."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


class CodeExecutor:
    """Execute shell commands with a fixed working directory."""

    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir.resolve()

    def run(self, command: list[str]) -> CommandResult:
        completed = subprocess.run(
            command,
            cwd=self.workdir,
            text=True,
            capture_output=True,
        )
        return CommandResult(
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )
