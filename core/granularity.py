"""Task granularity configuration models and loaders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_GRANULARITIES = ("layer", "module", "feature")
SUPPORTED_TOPOLOGIES = ("sequential",)


@dataclass(frozen=True)
class GranularityProfile:
    """Runtime profile for a specific task granularity."""

    name: str
    description: str
    topology: str
    kickoff_content: str
    roles: list[str]
    expected_state_fields: list[str]
    forbidden_state_fields: list[str]


@dataclass(frozen=True)
class GranularityRegistry:
    """Collection of profiles indexed by granularity key."""

    version: int
    default: str
    profiles: dict[str, GranularityProfile]

    def get_profile(self, granularity: str) -> GranularityProfile:
        key = granularity.strip().lower()
        if key not in self.profiles:
            raise KeyError(f"Unknown granularity profile: {granularity}")
        return self.profiles[key]


def _coerce_str_list(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list[str]")
    if not all(isinstance(item, str) for item in value):
        raise ValueError(f"{field_name} must contain only strings")
    return [item.strip() for item in value if item.strip()]


def load_granularity_registry(path: Path) -> GranularityRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Granularity config root must be an object")

    version = int(payload.get("version", 1))
    default = str(payload.get("default", "module")).strip().lower()

    profiles_raw = payload.get("profiles")
    if not isinstance(profiles_raw, dict):
        raise ValueError("profiles must be an object keyed by granularity")

    profiles: dict[str, GranularityProfile] = {}
    for name, item in profiles_raw.items():
        key = str(name).strip().lower()
        if key not in SUPPORTED_GRANULARITIES:
            raise ValueError(f"Unsupported granularity key: {key}")
        if not isinstance(item, dict):
            raise ValueError(f"profile '{key}' must be an object")

        topology = str(item.get("topology", "")).strip().lower()
        if topology not in SUPPORTED_TOPOLOGIES:
            raise ValueError(
                f"Unsupported topology '{topology}' for profile '{key}'"
            )

        profile = GranularityProfile(
            name=key,
            description=str(item.get("description", "")).strip(),
            topology=topology,
            kickoff_content=str(item.get("kickoff_content", "")).strip(),
            roles=_coerce_str_list(item.get("roles", []), f"{key}.roles"),
            expected_state_fields=_coerce_str_list(
                item.get("expected_state_fields", []),
                f"{key}.expected_state_fields",
            ),
            forbidden_state_fields=_coerce_str_list(
                item.get("forbidden_state_fields", []),
                f"{key}.forbidden_state_fields",
            ),
        )
        if not profile.roles:
            raise ValueError(f"profile '{key}' must define at least one role")
        if not profile.kickoff_content:
            raise ValueError(f"profile '{key}' must define kickoff_content")

        profiles[key] = profile

    if default not in profiles:
        raise ValueError(f"default profile '{default}' not found in profiles")

    missing = [key for key in SUPPORTED_GRANULARITIES if key not in profiles]
    if missing:
        raise ValueError(f"Missing required granularity profiles: {missing}")

    return GranularityRegistry(
        version=version,
        default=default,
        profiles=profiles,
    )
