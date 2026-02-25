from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

from agents import (
    ArchitectAgent,
    BackendDeveloperAgent,
    DevOpsAgent,
    FrontendDeveloperAgent,
    ProductManagerAgent,
    QAAgent,
)
from core import load_granularity_registry
from core.orchestrator import Orchestrator
from topologies.sequential import SequentialTopology


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GRANULARITY_CONFIG = PROJECT_ROOT / "configs" / "granularity_profiles.json"


def register_default_agents(orchestrator: Orchestrator) -> None:
    orchestrator.register_agent(ProductManagerAgent("pm", "pm prompt", []))
    orchestrator.register_agent(ArchitectAgent("architect", "architect prompt", []))
    orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend prompt", []))
    orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend prompt", []))
    orchestrator.register_agent(QAAgent("qa", "qa prompt", []))
    orchestrator.register_agent(DevOpsAgent("devops", "devops prompt", []))


class GranularitySwitchTests(unittest.TestCase):
    def test_granularity_profiles_load_with_required_entries(self) -> None:
        registry = load_granularity_registry(GRANULARITY_CONFIG)
        self.assertEqual("module", registry.default)
        self.assertEqual({"layer", "module", "feature"}, set(registry.profiles.keys()))
        self.assertTrue(all(profile.topology == "sequential" for profile in registry.profiles.values()))
        for profile in registry.profiles.values():
            self.assertTrue(profile.decomposition_unit)
            self.assertTrue(profile.work_items)
            self.assertTrue(profile.per_item_roles)
            self.assertTrue(profile.expected_artifact_versions)

    def _run_profile(self, profile: Any) -> tuple[list[Any], Any]:
        orchestrator = Orchestrator()
        register_default_agents(orchestrator)
        all_results: list[Any] = []

        if profile.prelude_roles:
            all_results.extend(
                SequentialTopology(
                    orchestrator=orchestrator,
                    roles=profile.prelude_roles,
                ).run("week7 prelude")
            )

        for work_item in profile.work_items:
            all_results.extend(
                SequentialTopology(
                    orchestrator=orchestrator,
                    roles=profile.per_item_roles,
                ).run(f"week7 work item: {work_item}")
            )

        if profile.final_roles:
            all_results.extend(
                SequentialTopology(
                    orchestrator=orchestrator,
                    roles=profile.final_roles,
                ).run("week7 finalization")
            )

        return all_results, orchestrator.state

    def test_profiles_drive_decomposition_switch_and_state_shape(self) -> None:
        registry = load_granularity_registry(GRANULARITY_CONFIG)
        for granularity in ["layer", "module", "feature"]:
            profile = registry.get_profile(granularity)
            turn_results, state = self._run_profile(profile)

            self.assertEqual(profile.expected_turn_count, len(turn_results))
            self.assertEqual(profile.expected_role_order, [result.agent_role for result in turn_results])
            self.assertTrue(all(result.success for result in turn_results))
            self.assertEqual(profile.expected_turn_count, state.total_api_calls)

            for field_name in profile.expected_state_fields:
                self.assertIsNotNone(
                    getattr(state, field_name),
                    msg=f"{granularity}: expected field not populated -> {field_name}",
                )

            for field_name in profile.forbidden_state_fields:
                self.assertIsNone(
                    getattr(state, field_name),
                    msg=f"{granularity}: forbidden field unexpectedly populated -> {field_name}",
                )

            actual_versions = {
                key: len(versions)
                for key, versions in state.artifact_store.artifact_versions.items()
            }
            for artifact_key, expected_count in profile.expected_artifact_versions.items():
                self.assertEqual(
                    expected_count,
                    actual_versions.get(artifact_key, 0),
                    msg=(
                        f"{granularity}: artifact version mismatch -> "
                        f"{artifact_key}, expected={expected_count}, "
                        f"actual={actual_versions.get(artifact_key, 0)}"
                    ),
                )


if __name__ == "__main__":
    unittest.main()
