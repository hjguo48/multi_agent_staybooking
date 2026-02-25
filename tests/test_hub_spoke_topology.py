from __future__ import annotations

import unittest

from agents import (
    ArchitectAgent,
    BackendDeveloperAgent,
    CoordinatorAgent,
    DevOpsAgent,
    FrontendDeveloperAgent,
    ProductManagerAgent,
    QAAgent,
)
from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState
from core.orchestrator import Orchestrator
from topologies.hub_spoke import DEFAULT_HUB_SPOKE_ROLES, HubAndSpokeTopology


class FailThenPassQAAgent(QAAgent):
    """Emit one failing QA report, then fall back to baseline pass behavior."""

    def __init__(self, role: str, system_prompt: str, tools: list[str]) -> None:
        super().__init__(role, system_prompt, tools)
        self._failed_once = False

    def act(self, context: ProjectState) -> dict[str, object]:
        if self._failed_once:
            return super().act(context)

        self._failed_once = True
        failing_report = {
            "summary": {
                "test_pass_rate": 0.4,
                "critical_bugs": 1,
                "major_bugs": 2,
            },
            "bug_reports": [
                {
                    "bug_id": "BUG-001",
                    "severity": "Critical",
                    "category": "Auth",
                    "file": "src/main/java/com/example/auth/AuthController.java",
                    "description": "Login endpoint returns 500 on invalid payload",
                    "related_requirement": "FR-001",
                }
            ],
            "coverage_map": {"FR-001": ["testLoginInvalidPayload"]},
        }
        return {
            "state_updates": {"qa_report": {"artifact_ref": "qa_report:v1"}},
            "artifacts": [
                {
                    "store_key": "qa_report",
                    "artifact": Artifact(
                        artifact_id="qa-report-auth-fail",
                        artifact_type="qa_report",
                        producer=self.role,
                        content=failing_report,
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="coordinator",
                    content="QA failed, rework required.",
                    msg_type=MessageType.FEEDBACK,
                )
            ],
            "usage": {"tokens": 470, "api_calls": 1},
        }


class AlwaysFailQAAgent(QAAgent):
    """Always emit failing QA report."""

    def act(self, context: ProjectState) -> dict[str, object]:
        failing_report = {
            "summary": {
                "test_pass_rate": 0.5,
                "critical_bugs": 1,
                "major_bugs": 1,
            },
            "bug_reports": [
                {
                    "bug_id": "BUG-002",
                    "severity": "Critical",
                    "category": "Auth",
                    "file": "src/main/java/com/example/auth/AuthService.java",
                    "description": "Token validation bypass vulnerability",
                    "related_requirement": "FR-001",
                }
            ],
            "coverage_map": {"FR-001": ["testTokenValidation"]},
        }
        return {
            "state_updates": {"qa_report": {"artifact_ref": "qa_report:v1"}},
            "artifacts": [
                {
                    "store_key": "qa_report",
                    "artifact": Artifact(
                        artifact_id="qa-report-auth-fail-always",
                        artifact_type="qa_report",
                        producer=self.role,
                        content=failing_report,
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="coordinator",
                    content="QA still failing.",
                    msg_type=MessageType.FEEDBACK,
                )
            ],
            "usage": {"tokens": 470, "api_calls": 1},
        }


class HubAndSpokeTopologyTests(unittest.TestCase):
    def _register_agents(
        self,
        orchestrator: Orchestrator,
        *,
        coordinator: CoordinatorAgent,
        qa_agent: QAAgent,
    ) -> None:
        orchestrator.register_agent(coordinator)
        orchestrator.register_agent(ProductManagerAgent("pm", "pm", []))
        orchestrator.register_agent(ArchitectAgent("architect", "arch", []))
        orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend", []))
        orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend", []))
        orchestrator.register_agent(qa_agent)
        orchestrator.register_agent(DevOpsAgent("devops", "devops", []))

    def test_hub_spoke_flow_completes_with_coordinator_routing(self) -> None:
        orchestrator = Orchestrator()
        coordinator = CoordinatorAgent("coordinator", "coordinator", [])
        self._register_agents(orchestrator, coordinator=coordinator, qa_agent=QAAgent("qa", "qa", []))

        topology = HubAndSpokeTopology(orchestrator=orchestrator)
        turn_results = topology.run("hub-spoke-normal-flow")
        state = orchestrator.state

        coordinator_turns = [result for result in turn_results if result.agent_role == "coordinator"]
        spoke_turns = [result for result in turn_results if result.agent_role != "coordinator"]
        spoke_order = [result.agent_role for result in spoke_turns]
        coordinator_tasks = [
            message
            for message in state.message_log.messages
            if (
                message.sender == "coordinator"
                and message.msg_type == MessageType.TASK
                and message.receiver in DEFAULT_HUB_SPOKE_ROLES
            )
        ]

        self.assertTrue(all(result.success for result in turn_results))
        self.assertEqual(12, len(turn_results))
        self.assertEqual(6, len(coordinator_turns))
        self.assertEqual(DEFAULT_HUB_SPOKE_ROLES, spoke_order)
        self.assertEqual(6, len(coordinator_tasks))
        self.assertIsNotNone(state.deployment)
        self.assertEqual(4170, state.total_tokens)
        self.assertEqual(12, state.total_api_calls)
        self.assertEqual(6, state.iteration)

    def test_hub_spoke_reworks_after_failed_qa_then_recovers(self) -> None:
        orchestrator = Orchestrator()
        coordinator = CoordinatorAgent("coordinator", "coordinator", [], max_qa_retries=1)
        qa_agent = FailThenPassQAAgent("qa", "qa", [])
        self._register_agents(orchestrator, coordinator=coordinator, qa_agent=qa_agent)

        topology = HubAndSpokeTopology(orchestrator=orchestrator)
        turn_results = topology.run("hub-spoke-qa-rework")
        state = orchestrator.state

        spoke_order = [result.agent_role for result in turn_results if result.agent_role != "coordinator"]

        self.assertTrue(all(result.success for result in turn_results))
        self.assertEqual(
            [
                "pm",
                "architect",
                "backend_dev",
                "frontend_dev",
                "qa",
                "backend_dev",
                "qa",
                "devops",
            ],
            spoke_order,
        )
        self.assertEqual(2, state.get_latest_artifact("backend_code").version)
        self.assertEqual(2, state.get_latest_artifact("qa_report").version)
        self.assertIsNotNone(state.deployment)
        self.assertEqual(5680, state.total_tokens)
        self.assertEqual(16, state.total_api_calls)
        self.assertEqual(8, state.iteration)

    def test_hub_spoke_stops_when_qa_fails_without_retry_budget(self) -> None:
        orchestrator = Orchestrator()
        coordinator = CoordinatorAgent("coordinator", "coordinator", [], max_qa_retries=0)
        qa_agent = AlwaysFailQAAgent("qa", "qa", [])
        self._register_agents(orchestrator, coordinator=coordinator, qa_agent=qa_agent)

        topology = HubAndSpokeTopology(orchestrator=orchestrator)
        turn_results = topology.run("hub-spoke-qa-fail-stop")
        state = orchestrator.state

        self.assertEqual("coordinator", turn_results[-1].agent_role)
        self.assertTrue(turn_results[-1].stop)
        self.assertFalse(any(result.agent_role == "devops" for result in turn_results))
        self.assertIsNone(state.deployment)


if __name__ == "__main__":
    unittest.main()
