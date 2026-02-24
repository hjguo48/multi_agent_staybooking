from __future__ import annotations

import unittest

from agents.base_agent import BaseAgent
from core.models import AgentMessage, Artifact, MessageType
from core.orchestrator import Orchestrator


class PMTestAgent(BaseAgent):
    def act(self, context):  # type: ignore[override]
        return {
            "state_updates": {"requirements": {"artifact_ref": "requirements:v1"}},
            "artifacts": [
                {
                    "store_key": "requirements",
                    "artifact": Artifact(
                        artifact_id="requirements-doc",
                        artifact_type="requirements",
                        producer=self.role,
                        content={"project_name": "StayBooking"},
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="architect",
                    content="requirements-ready",
                    msg_type=MessageType.TASK,
                )
            ],
            "usage": {"tokens": 100, "api_calls": 1},
        }


class PassiveAgent(BaseAgent):
    def act(self, context):  # type: ignore[override]
        return {}


class StopAgent(BaseAgent):
    def act(self, context):  # type: ignore[override]
        return {"stop": True}


class OrchestratorTests(unittest.TestCase):
    def test_run_turn_updates_state_artifacts_and_messages(self) -> None:
        orchestrator = Orchestrator()
        pm = PMTestAgent(role="pm", system_prompt="pm", tools=[])
        architect = PassiveAgent(role="architect", system_prompt="arch", tools=[])
        orchestrator.register_agent(pm)
        orchestrator.register_agent(architect)

        orchestrator.kickoff("pm", "start")
        result = orchestrator.run_turn("pm")

        self.assertTrue(result.success)
        self.assertEqual(["requirements"], result.updated_fields)
        self.assertEqual(["requirements:v1"], result.artifacts_registered)
        self.assertEqual(1, result.messages_emitted)
        self.assertEqual({"artifact_ref": "requirements:v1"}, orchestrator.state.requirements)
        self.assertEqual(1, orchestrator.state.get_latest_artifact("requirements").version)
        self.assertEqual(2, len(orchestrator.state.message_log.messages))
        self.assertEqual(1, len(architect.memory.messages))
        self.assertEqual(100, orchestrator.state.total_tokens)
        self.assertEqual(1, orchestrator.state.total_api_calls)

    def test_broadcast_message_routing(self) -> None:
        orchestrator = Orchestrator()
        pm = PassiveAgent(role="pm", system_prompt="pm", tools=[])
        architect = PassiveAgent(role="architect", system_prompt="arch", tools=[])
        orchestrator.register_agent(pm)
        orchestrator.register_agent(architect)

        orchestrator.route_message(
            AgentMessage(
                sender="orchestrator",
                receiver="broadcast",
                content="status",
                msg_type=MessageType.STATUS,
            )
        )

        self.assertEqual(1, len(pm.memory.messages))
        self.assertEqual(1, len(architect.memory.messages))
        self.assertEqual(1, len(orchestrator.state.message_log.messages))

    def test_run_sequence_stops_when_stop_flag_true(self) -> None:
        orchestrator = Orchestrator()
        stop_agent = StopAgent(role="pm", system_prompt="pm", tools=[])
        next_agent = PassiveAgent(role="architect", system_prompt="arch", tools=[])
        orchestrator.register_agent(stop_agent)
        orchestrator.register_agent(next_agent)

        results = orchestrator.run_sequence(["pm", "architect"])

        self.assertEqual(1, len(results))
        self.assertTrue(results[0].stop)
        self.assertEqual("pm", results[0].agent_role)


if __name__ == "__main__":
    unittest.main()
