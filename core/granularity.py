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
    decomposition_unit: str
    topology: str
    work_items: list[str]
    prelude_roles: list[str]
    per_item_roles: list[str]
    final_roles: list[str]
    expected_state_fields: list[str]
    forbidden_state_fields: list[str]
    expected_artifact_versions: dict[str, int]

    @property
    def expected_turn_count(self) -> int:
        return (
            len(self.prelude_roles)
            + len(self.work_items) * len(self.per_item_roles)
            + len(self.final_roles)
        )

    @property
    def expected_role_order(self) -> list[str]:
        roles: list[str] = []
        roles.extend(self.prelude_roles)
        for _ in self.work_items:
            roles.extend(self.per_item_roles)
        roles.extend(self.final_roles)
        return roles


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


def _coerce_str_int_map(value: object, field_name: str) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be an object mapping str->int")
    normalized: dict[str, int] = {}
    for raw_key, raw_val in value.items():
        key = str(raw_key).strip()
        if not key:
            raise ValueError(f"{field_name} contains empty key")
        try:
            int_val = int(raw_val)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name}.{key} must be int") from exc
        if int_val < 0:
            raise ValueError(f"{field_name}.{key} must be >= 0")
        normalized[key] = int_val
    return normalized


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
            decomposition_unit=str(item.get("decomposition_unit", key)).strip().lower(),
            topology=topology,
            work_items=_coerce_str_list(item.get("work_items", []), f"{key}.work_items"),
            prelude_roles=_coerce_str_list(
                item.get("prelude_roles", []),
                f"{key}.prelude_roles",
            ),
            per_item_roles=_coerce_str_list(
                item.get("per_item_roles", []),
                f"{key}.per_item_roles",
            ),
            final_roles=_coerce_str_list(
                item.get("final_roles", []),
                f"{key}.final_roles",
            ),
            expected_state_fields=_coerce_str_list(
                item.get("expected_state_fields", []),
                f"{key}.expected_state_fields",
            ),
            forbidden_state_fields=_coerce_str_list(
                item.get("forbidden_state_fields", []),
                f"{key}.forbidden_state_fields",
            ),
            expected_artifact_versions=_coerce_str_int_map(
                item.get("expected_artifact_versions", {}),
                f"{key}.expected_artifact_versions",
            ),
        )
        if not profile.work_items:
            raise ValueError(f"profile '{key}' must define at least one work_item")
        if not profile.per_item_roles:
            raise ValueError(f"profile '{key}' must define per_item_roles")
        if not profile.expected_artifact_versions:
            raise ValueError(f"profile '{key}' must define expected_artifact_versions")

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
