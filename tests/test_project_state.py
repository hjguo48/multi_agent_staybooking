from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core import AgentMessage, Artifact, MessageType, ProjectState


class ProjectStateTests(unittest.TestCase):
    def test_state_tracks_artifacts_messages_and_usage(self) -> None:
        state = ProjectState()
        state.register_artifact(
            "requirements",
            Artifact(
                artifact_id="requirements-doc",
                artifact_type="requirements",
                producer="pm",
                content={"project_name": "StayBooking"},
            ),
        )
        state.add_message(
            AgentMessage(
                sender="pm",
                receiver="architect",
                content="handoff",
                msg_type=MessageType.APPROVAL,
            )
        )
        state.update_usage(token_delta=100, api_call_delta=2)

        self.assertEqual(1, state.get_latest_artifact("requirements").version)
        self.assertEqual(1, len(state.message_log.messages))
        self.assertEqual(100, state.total_tokens)
        self.assertEqual(2, state.total_api_calls)

    def test_json_roundtrip(self) -> None:
        state = ProjectState()
        state.iteration = 2
        state.register_artifact(
            "architecture",
            Artifact(
                artifact_id="architecture-doc",
                artifact_type="architecture",
                producer="architect",
                content={"modules": ["auth"]},
            ),
        )
        state.add_message(
            AgentMessage(
                sender="architect",
                receiver="backend_dev",
                content="design-ready",
                msg_type=MessageType.TASK,
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "state.json"
            state.save_json(path)
            loaded = ProjectState.load_json(path)

        self.assertEqual(state.run_id, loaded.run_id)
        self.assertEqual(state.iteration, loaded.iteration)
        self.assertEqual(1, loaded.get_latest_artifact("architecture").version)
        self.assertEqual(1, len(loaded.message_log.messages))


if __name__ == "__main__":
    unittest.main()
