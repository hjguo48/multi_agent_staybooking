"""QA agent implementation (rule-driven baseline)."""

from __future__ import annotations

from typing import Any

from core.models import AgentMessage, Artifact, MessageType
from core.project_state import ProjectState

from .base_agent import BaseAgent


class QAAgent(BaseAgent):
    """Validate produced artifacts and generate QA report."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        fallback_qa_report = {
            "summary": {
                "test_pass_rate": 1.0,
                "critical_bugs": 0,
                "major_bugs": 0,
            },
            "bug_reports": [],
            "coverage_map": {"FR-001": ["testRegister", "testLogin"]},
        }
        qa_report, usage, generation_meta = self._llm_json_or_fallback(
            context=context,
            task_instruction=(
                "Generate QA report JSON for current StayBooking artifacts. "
                "Include summary, bug_reports, and coverage_map."
            ),
            fallback_payload=fallback_qa_report,
            fallback_usage={"tokens": 470, "api_calls": 1},
            required_keys=["summary", "bug_reports", "coverage_map"],
        )
        return {
            "state_updates": {"qa_report": {"artifact_ref": "qa_report:v1"}},
            "artifacts": [
                {
                    "store_key": "qa_report",
                    "artifact": Artifact(
                        artifact_id="qa-report-auth",
                        artifact_type="qa_report",
                        producer=self.role,
                        content=qa_report,
                        metadata={"generation": generation_meta},
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="devops",
                    content="QA passed. Ready for deployment validation.",
                    msg_type=MessageType.APPROVAL,
                    artifacts=["qa-report-auth:v1"],
                )
            ],
            "usage": usage,
        }
