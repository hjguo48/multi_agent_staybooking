from __future__ import annotations

import unittest
from pathlib import Path

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

    def test_profiles_drive_role_switch_and_state_shape(self) -> None:
        registry = load_granularity_registry(GRANULARITY_CONFIG)
        for granularity in ["layer", "module", "feature"]:
            profile = registry.get_profile(granularity)
            orchestrator = Orchestrator()
            register_default_agents(orchestrator)

            topology = SequentialTopology(orchestrator=orchestrator, roles=profile.roles)
            turn_results = topology.run(profile.kickoff_content)
            state = orchestrator.state

            self.assertEqual(len(profile.roles), len(turn_results))
            self.assertEqual(profile.roles, [result.agent_role for result in turn_results])
            self.assertTrue(all(result.success for result in turn_results))
            self.assertEqual(len(profile.roles), state.total_api_calls)

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


if __name__ == "__main__":
    unittest.main()
