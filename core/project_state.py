"""Global project state shared by orchestrator and agents."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from .artifact_store import ArtifactStore
from .message_log import MessageLog
from .models import AgentMessage, Artifact, utc_now


@dataclass
class ProjectState:
    """Serializable orchestration state across the whole run."""

    run_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    requirements: dict[str, Any] | None = None
    architecture: dict[str, Any] | None = None
    backend_code: dict[str, Any] | None = None
    frontend_code: dict[str, Any] | None = None
    qa_report: dict[str, Any] | None = None
    deployment: dict[str, Any] | None = None

    iteration: int = 0
    total_tokens: int = 0
    total_api_calls: int = 0

    artifact_store: ArtifactStore = field(default_factory=ArtifactStore)
    message_log: MessageLog = field(default_factory=MessageLog)

    def touch(self) -> None:
        self.updated_at = utc_now()

    def add_message(self, message: AgentMessage) -> None:
        self.message_log.append(message)
        self.touch()

    def register_artifact(self, key: str, artifact: Artifact) -> Artifact:
        stored = self.artifact_store.register(key, artifact)
        self.touch()
        return stored

    def get_latest_artifact(self, key: str) -> Artifact | None:
        return self.artifact_store.get_latest(key)

    def increment_iteration(self) -> None:
        self.iteration += 1
        self.touch()

    def update_usage(self, token_delta: int = 0, api_call_delta: int = 0) -> None:
        self.total_tokens += token_delta
        self.total_api_calls += api_call_delta
        self.touch()

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "requirements": self.requirements,
            "architecture": self.architecture,
            "backend_code": self.backend_code,
            "frontend_code": self.frontend_code,
            "qa_report": self.qa_report,
            "deployment": self.deployment,
            "iteration": self.iteration,
            "total_tokens": self.total_tokens,
            "total_api_calls": self.total_api_calls,
            "artifact_store": self.artifact_store.to_dict(),
            "message_log": self.message_log.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        state = cls(
            run_id=data.get("run_id", uuid4().hex),
            created_at=data.get("created_at", utc_now()),
            updated_at=data.get("updated_at", utc_now()),
            requirements=data.get("requirements"),
            architecture=data.get("architecture"),
            backend_code=data.get("backend_code"),
            frontend_code=data.get("frontend_code"),
            qa_report=data.get("qa_report"),
            deployment=data.get("deployment"),
            iteration=int(data.get("iteration", 0)),
            total_tokens=int(data.get("total_tokens", 0)),
            total_api_calls=int(data.get("total_api_calls", 0)),
        )
        state.artifact_store = ArtifactStore.from_dict(data.get("artifact_store", {}))
        state.message_log = MessageLog.from_dict(data.get("message_log", []))
        return state

    def save_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load_json(cls, path: Path) -> "ProjectState":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(data)
