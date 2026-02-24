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
from core import ProjectState
from core.orchestrator import Orchestrator
from topologies.sequential import DEFAULT_SEQUENTIAL_ROLES, SequentialTopology


class FailOnceProductManagerAgent(ProductManagerAgent):
    """Fail the first call to simulate transient runtime errors."""

    def __init__(self, role: str, system_prompt: str, tools: list[str]) -> None:
        super().__init__(role, system_prompt, tools)
        self._failures_left = 1

    def act(self, context: ProjectState) -> dict[str, object]:
        if self._failures_left > 0:
            self._failures_left -= 1
            raise RuntimeError("simulated transient failure")
        return super().act(context)


class AlwaysFailProductManagerAgent(ProductManagerAgent):
    """Always raise to exercise fail-fast controls."""

    def act(self, context: ProjectState) -> dict[str, object]:
        raise RuntimeError("simulated persistent failure")


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

    def test_retry_per_role_recovers_from_transient_failure(self) -> None:
        orchestrator = Orchestrator()
        orchestrator.register_agent(FailOnceProductManagerAgent("pm", "pm", []))
        topology = SequentialTopology(
            orchestrator,
            roles=["pm"],
            max_retries_per_role=1,
        )

        turn_results = topology.run("retry-once")
        state = orchestrator.state

        self.assertEqual(2, len(turn_results))
        self.assertFalse(turn_results[0].success)
        self.assertTrue(turn_results[1].success)
        self.assertIsNotNone(state.requirements)

    def test_skip_roles_moves_kickoff_to_first_runnable_role(self) -> None:
        orchestrator = Orchestrator()
        orchestrator.register_agent(ProductManagerAgent("pm", "pm", []))
        orchestrator.register_agent(ArchitectAgent("architect", "arch", []))
        topology = SequentialTopology(
            orchestrator,
            roles=["pm", "architect"],
            skipped_roles={"pm"},
        )

        turn_results = topology.run("skip-pm")
        state = orchestrator.state

        self.assertEqual(1, len(turn_results))
        self.assertEqual("architect", turn_results[0].agent_role)
        self.assertIsNone(state.requirements)
        self.assertIsNotNone(state.architecture)
        self.assertEqual("architect", state.message_log.messages[0].receiver)

    def test_fail_fast_false_continues_after_role_failure(self) -> None:
        orchestrator = Orchestrator()
        orchestrator.register_agent(AlwaysFailProductManagerAgent("pm", "pm", []))
        orchestrator.register_agent(ArchitectAgent("architect", "arch", []))
        topology = SequentialTopology(
            orchestrator,
            roles=["pm", "architect"],
            fail_fast=False,
        )

        turn_results = topology.run("continue-on-failure")
        state = orchestrator.state

        self.assertEqual(2, len(turn_results))
        self.assertEqual("pm", turn_results[0].agent_role)
        self.assertFalse(turn_results[0].success)
        self.assertEqual("architect", turn_results[1].agent_role)
        self.assertTrue(turn_results[1].success)
        self.assertIsNotNone(state.architecture)


if __name__ == "__main__":
    unittest.main()
