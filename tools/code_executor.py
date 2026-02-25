"""Command execution wrapper for controlled build/test steps."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


def _to_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


@dataclass
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class CodeExecutor:
    """Execute shell commands with a fixed working directory."""

    def __init__(self, workdir: Path) -> None:
        self.workdir = workdir.resolve()

    def run(self, command: list[str], timeout_seconds: float | None = None) -> CommandResult:
        try:
            completed = subprocess.run(
                command,
                cwd=self.workdir,
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
            )
            return CommandResult(
                command=command,
                returncode=completed.returncode,
                stdout=_to_text(completed.stdout),
                stderr=_to_text(completed.stderr),
                timed_out=False,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                returncode=124,
                stdout=_to_text(exc.stdout),
                stderr=_to_text(exc.stderr) or f"command timed out after {timeout_seconds}s",
                timed_out=True,
            )
