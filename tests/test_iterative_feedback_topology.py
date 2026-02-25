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
from core import AgentMessage, Artifact, MessageType, ProjectState
from core.orchestrator import Orchestrator
from topologies.iterative_feedback import IterativeFeedbackTopology


class FailThenPassQAAgent(QAAgent):
    """Emit one failing QA report then pass."""

    def __init__(self, role: str, system_prompt: str, tools: list[str]) -> None:
        super().__init__(role, system_prompt, tools)
        self._failed_once = False

    def act(self, context: ProjectState) -> dict[str, object]:
        if self._failed_once:
            return super().act(context)

        self._failed_once = True
        report = {
            "summary": {
                "test_pass_rate": 0.4,
                "critical_bugs": 1,
                "major_bugs": 1,
            },
            "bug_reports": [
                {
                    "bug_id": "BUG-IF-001",
                    "severity": "Critical",
                    "category": "Backend",
                    "file": "src/main/java/com/example/auth/AuthService.java",
                    "description": "Auth failure",
                    "related_requirement": "FR-001",
                }
            ],
            "coverage_map": {"FR-001": ["testAuthFailure"]},
        }
        return {
            "state_updates": {"qa_report": {"artifact_ref": "qa_report:v1"}},
            "artifacts": [
                {
                    "store_key": "qa_report",
                    "artifact": Artifact(
                        artifact_id="qa-report-fail-then-pass",
                        artifact_type="qa_report",
                        producer=self.role,
                        content=report,
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="backend_dev",
                    content="backend fix needed",
                    msg_type=MessageType.FEEDBACK,
                )
            ],
            "usage": {"tokens": 470, "api_calls": 1},
        }


class AlwaysFailQAAgent(QAAgent):
    """Always emit the same failing QA report."""

    def act(self, context: ProjectState) -> dict[str, object]:
        report = {
            "summary": {
                "test_pass_rate": 0.5,
                "critical_bugs": 1,
                "major_bugs": 1,
            },
            "bug_reports": [
                {
                    "bug_id": "BUG-IF-ALWAYS",
                    "severity": "Critical",
                    "category": "Backend",
                    "file": "src/main/java/com/example/auth/AuthService.java",
                    "description": "Persistent auth failure",
                    "related_requirement": "FR-001",
                }
            ],
            "coverage_map": {"FR-001": ["testPersistentAuthFailure"]},
        }
        return {
            "state_updates": {"qa_report": {"artifact_ref": "qa_report:v1"}},
            "artifacts": [
                {
                    "store_key": "qa_report",
                    "artifact": Artifact(
                        artifact_id="qa-report-fail-always",
                        artifact_type="qa_report",
                        producer=self.role,
                        content=report,
                    ),
                }
            ],
            "messages": [],
            "usage": {"tokens": 470, "api_calls": 1},
        }


class NoOpBackendAgent(BackendDeveloperAgent):
    """Simulate rework with no code change."""

    def act(self, context: ProjectState) -> dict[str, object]:
        return {"usage": {"tokens": 100, "api_calls": 1}}


class IterativeFeedbackTopologyTests(unittest.TestCase):
    def test_iterative_feedback_reworks_then_deploys(self) -> None:
        orchestrator = Orchestrator()
        orchestrator.register_agent(ProductManagerAgent("pm", "pm", []))
        orchestrator.register_agent(ArchitectAgent("architect", "arch", []))
        orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend", []))
        orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend", []))
        orchestrator.register_agent(FailThenPassQAAgent("qa", "qa", []))
        orchestrator.register_agent(DevOpsAgent("devops", "devops", []))

        topology = IterativeFeedbackTopology(
            orchestrator=orchestrator,
            max_feedback_iterations=2,
            max_stagnant_rounds=1,
        )
        turn_results = topology.run("iterative-feedback-success")
        state = orchestrator.state

        self.assertEqual(
            ["pm", "architect", "backend_dev", "frontend_dev", "qa", "backend_dev", "qa", "devops"],
            [result.agent_role for result in turn_results],
        )
        self.assertTrue(all(result.success for result in turn_results))
        self.assertEqual(2, state.get_latest_artifact("backend_code").version)
        self.assertEqual(2, state.get_latest_artifact("qa_report").version)
        self.assertIsNotNone(state.deployment)
        self.assertEqual(4240, state.total_tokens)
        self.assertEqual(8, state.total_api_calls)
        self.assertEqual(1, state.iteration)

    def test_iterative_feedback_stops_when_iteration_cap_reached(self) -> None:
        orchestrator = Orchestrator()
        orchestrator.register_agent(ProductManagerAgent("pm", "pm", []))
        orchestrator.register_agent(ArchitectAgent("architect", "arch", []))
        orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend", []))
        orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend", []))
        orchestrator.register_agent(AlwaysFailQAAgent("qa", "qa", []))
        orchestrator.register_agent(DevOpsAgent("devops", "devops", []))

        topology = IterativeFeedbackTopology(
            orchestrator=orchestrator,
            max_feedback_iterations=1,
            max_stagnant_rounds=2,
        )
        turn_results = topology.run("iterative-feedback-cap-stop")
        state = orchestrator.state

        self.assertEqual("qa", turn_results[-1].agent_role)
        self.assertTrue(turn_results[-1].stop)
        self.assertIn("feedback iteration cap reached", turn_results[-1].error or "")
        self.assertFalse(any(result.agent_role == "devops" for result in turn_results))
        self.assertIsNone(state.deployment)

    def test_iterative_feedback_anti_loop_stops_on_stagnation(self) -> None:
        orchestrator = Orchestrator()
        orchestrator.register_agent(ProductManagerAgent("pm", "pm", []))
        orchestrator.register_agent(ArchitectAgent("architect", "arch", []))
        orchestrator.register_agent(NoOpBackendAgent("backend_dev", "backend", []))
        orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend", []))
        orchestrator.register_agent(AlwaysFailQAAgent("qa", "qa", []))
        orchestrator.register_agent(DevOpsAgent("devops", "devops", []))

        topology = IterativeFeedbackTopology(
            orchestrator=orchestrator,
            max_feedback_iterations=3,
            max_stagnant_rounds=0,
        )
        turn_results = topology.run("iterative-feedback-anti-loop-stop")
        state = orchestrator.state

        self.assertEqual("qa", turn_results[-1].agent_role)
        self.assertTrue(turn_results[-1].stop)
        self.assertIn("anti-loop triggered", turn_results[-1].error or "")
        self.assertFalse(any(result.agent_role == "devops" for result in turn_results))
        self.assertIsNone(state.deployment)


if __name__ == "__main__":
    unittest.main()
