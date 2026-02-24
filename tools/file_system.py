"""Minimal file-system wrapper for agent tool calls."""

from __future__ import annotations

from pathlib import Path


class FileSystemTool:
    """Simple read/write helpers constrained to project-root-relative paths."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root.resolve()

    def resolve(self, relative_path: str) -> Path:
        target = (self.project_root / relative_path).resolve()
        if self.project_root not in target.parents and target != self.project_root:
            raise ValueError(f"Path escapes project root: {relative_path}")
        return target

    def read_text(self, relative_path: str, encoding: str = "utf-8") -> str:
        return self.resolve(relative_path).read_text(encoding=encoding)

    def write_text(self, relative_path: str, content: str, encoding: str = "utf-8") -> None:
        path = self.resolve(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)

    def exists(self, relative_path: str) -> bool:
        return self.resolve(relative_path).exists()
