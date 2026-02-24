from __future__ import annotations

import unittest

from agents import (
    ArchitectAgent,
    BackendDeveloperAgent,
    DevOpsAgent,
    FrontendDeveloperAgent,
    ProductManagerAgent,
    QAAgent,
)
from core.orchestrator import Orchestrator
from topologies.sequential import DEFAULT_SEQUENTIAL_ROLES, SequentialTopology


class SequentialTopologyTests(unittest.TestCase):
    def test_sequential_flow_populates_all_phase_states(self) -> None:
        orchestrator = Orchestrator()
        orchestrator.register_agent(ProductManagerAgent("pm", "pm", []))
        orchestrator.register_agent(ArchitectAgent("architect", "arch", []))
        orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend", []))
        orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend", []))
        orchestrator.register_agent(QAAgent("qa", "qa", []))
        orchestrator.register_agent(DevOpsAgent("devops", "devops", []))

        topology = SequentialTopology(orchestrator)
        turn_results = topology.run("run-auth-flow")
        state = orchestrator.state

        self.assertEqual(len(DEFAULT_SEQUENTIAL_ROLES), len(turn_results))
        self.assertTrue(all(result.success for result in turn_results))
        self.assertIsNotNone(state.requirements)
        self.assertIsNotNone(state.architecture)
        self.assertIsNotNone(state.backend_code)
        self.assertIsNotNone(state.frontend_code)
        self.assertIsNotNone(state.qa_report)
        self.assertIsNotNone(state.deployment)
        self.assertEqual(3090, state.total_tokens)
        self.assertEqual(6, state.total_api_calls)
        self.assertEqual(1, state.get_latest_artifact("deployment").version)


if __name__ == "__main__":
    unittest.main()
