"""Materialize generated code artifacts into runnable workspaces."""

from __future__ import annotations

import os
import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _latest_artifact_content(state_payload: dict[str, Any], key: str) -> dict[str, Any]:
    artifact_store = state_payload.get("artifact_store", {})
    versions = artifact_store.get(key, [])
    if not isinstance(versions, list) or not versions:
        return {}
    latest = versions[-1]
    if not isinstance(latest, dict):
        return {}
    content = latest.get("content", {})
    if isinstance(content, dict):
        return content
    return {}


def _safe_write(root: Path, relative_path: str, content: str) -> Path:
    target = (root / relative_path).resolve()
    if root.resolve() not in target.parents and target != root.resolve():
        raise ValueError(f"artifact path escapes workspace root: {relative_path}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


@dataclass
class MaterializationResult:
    run_name: str
    workspace_root: str
    backend_root: str
    frontend_root: str
    backend_files_written: list[str] = field(default_factory=list)
    frontend_files_written: list[str] = field(default_factory=list)
    backend_template_used: str | None = None
    frontend_template_used: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_name": self.run_name,
            "workspace_root": self.workspace_root,
            "backend_root": self.backend_root,
            "frontend_root": self.frontend_root,
            "backend_files_written": self.backend_files_written,
            "frontend_files_written": self.frontend_files_written,
            "backend_template_used": self.backend_template_used,
            "frontend_template_used": self.frontend_template_used,
        }


class ArtifactMaterializer:
    """Materialize latest backend/frontend code_bundle into workspace."""

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root.resolve()

    @staticmethod
    def _on_rm_error(func: Any, path: str, _: Any) -> None:
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def _prepare_root(self, path: Path, template: Path | None) -> str | None:
        if path.exists():
            shutil.rmtree(path, onerror=self._on_rm_error)
        path.parent.mkdir(parents=True, exist_ok=True)

        if template is None:
            path.mkdir(parents=True, exist_ok=True)
            return None

        shutil.copytree(
            template,
            path,
            dirs_exist_ok=False,
            ignore=shutil.ignore_patterns(
                ".git",
                ".gradle",
                "node_modules",
                "build",
                "target",
                ".idea",
                "__pycache__",
            ),
        )
        return template.as_posix()

    def materialize(
        self,
        *,
        run_name: str,
        state_payload: dict[str, Any],
        backend_template: Path | None = None,
        frontend_template: Path | None = None,
    ) -> MaterializationResult:
        workspace_root = (self.output_root / run_name).resolve()
        backend_root = workspace_root / "backend"
        frontend_root = workspace_root / "frontend"

        backend_template_used = self._prepare_root(backend_root, backend_template)
        frontend_template_used = self._prepare_root(frontend_root, frontend_template)

        backend_content = _latest_artifact_content(state_payload, "backend_code")
        frontend_content = _latest_artifact_content(state_payload, "frontend_code")

        backend_bundle = backend_content.get("code_bundle", {})
        frontend_bundle = frontend_content.get("code_bundle", {})
        if not isinstance(backend_bundle, dict):
            backend_bundle = {}
        if not isinstance(frontend_bundle, dict):
            frontend_bundle = {}

        backend_files_written: list[str] = []
        for relative_path, content in backend_bundle.items():
            if not isinstance(content, str):
                continue
            written = _safe_write(backend_root, str(relative_path), content)
            backend_files_written.append(written.as_posix())

        frontend_files_written: list[str] = []
        for relative_path, content in frontend_bundle.items():
            if not isinstance(content, str):
                continue
            written = _safe_write(frontend_root, str(relative_path), content)
            frontend_files_written.append(written.as_posix())

        return MaterializationResult(
            run_name=run_name,
            workspace_root=workspace_root.as_posix(),
            backend_root=backend_root.as_posix(),
            frontend_root=frontend_root.as_posix(),
            backend_files_written=backend_files_written,
            frontend_files_written=frontend_files_written,
            backend_template_used=backend_template_used,
            frontend_template_used=frontend_template_used,
        )
