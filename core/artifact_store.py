"""Artifact store with version tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import Artifact


@dataclass
class ArtifactStore:
    """Maintain versioned artifacts keyed by logical artifact name."""

    artifact_versions: dict[str, list[Artifact]] = field(default_factory=dict)

    def register(self, key: str, artifact: Artifact) -> Artifact:
        versions = self.artifact_versions.setdefault(key, [])
        artifact.version = len(versions) + 1
        versions.append(artifact)
        return artifact

    def get_latest(self, key: str) -> Artifact | None:
        versions = self.artifact_versions.get(key, [])
        if not versions:
            return None
        return versions[-1]

    def get_version(self, key: str, version: int) -> Artifact | None:
        versions = self.artifact_versions.get(key, [])
        if version <= 0 or version > len(versions):
            return None
        return versions[version - 1]

    def list_versions(self, key: str) -> list[int]:
        versions = self.artifact_versions.get(key, [])
        return [artifact.version for artifact in versions]

    def keys(self) -> list[str]:
        return sorted(self.artifact_versions.keys())

    def to_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            key: [artifact.to_dict() for artifact in artifacts]
            for key, artifacts in self.artifact_versions.items()
        }

    @classmethod
    def from_dict(cls, data: dict[str, list[dict[str, Any]]]) -> "ArtifactStore":
        store = cls()
        for key, artifacts in data.items():
            store.artifact_versions[key] = [Artifact.from_dict(item) for item in artifacts]
        return store
