#!/usr/bin/env python3
"""Week 6 smoke run for Iterative Feedback topology."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week6"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
    """Emit one failing QA report then pass on next round."""

    def __init__(self, role: str, system_prompt: str, tools: list[str]) -> None:
        super().__init__(role, system_prompt, tools)
        self._failed_once = False

    def act(self, context: ProjectState) -> dict[str, object]:
        if self._failed_once:
            return super().act(context)

        self._failed_once = True
        failing_report = {
            "summary": {
                "test_pass_rate": 0.5,
                "critical_bugs": 1,
                "major_bugs": 1,
            },
            "bug_reports": [
                {
                    "bug_id": "BUG-ITER-001",
                    "severity": "Critical",
                    "category": "Backend",
                    "file": "src/main/java/com/example/auth/AuthService.java",
                    "description": "Null pointer in auth flow",
                    "related_requirement": "FR-001",
                }
            ],
            "coverage_map": {"FR-001": ["testLoginNullCase"]},
        }
        return {
            "state_updates": {"qa_report": {"artifact_ref": "qa_report:v1"}},
            "artifacts": [
                {
                    "store_key": "qa_report",
                    "artifact": Artifact(
                        artifact_id="qa-report-iterative-fail",
                        artifact_type="qa_report",
                        producer=self.role,
                        content=failing_report,
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="backend_dev",
                    content="QA failed. backend fix required.",
                    msg_type=MessageType.FEEDBACK,
                )
            ],
            "usage": {"tokens": 470, "api_calls": 1},
        }


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_smoke() -> tuple[int, list[CheckResult], Path, Path]:
    orchestrator = Orchestrator()
    orchestrator.register_agent(ProductManagerAgent("pm", "pm prompt", []))
    orchestrator.register_agent(ArchitectAgent("architect", "architect prompt", []))
    orchestrator.register_agent(BackendDeveloperAgent("backend_dev", "backend prompt", []))
    orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", "frontend prompt", []))
    orchestrator.register_agent(FailThenPassQAAgent("qa", "qa prompt", []))
    orchestrator.register_agent(DevOpsAgent("devops", "devops prompt", []))

    topology = IterativeFeedbackTopology(
        orchestrator=orchestrator,
        max_feedback_iterations=2,
        max_stagnant_rounds=1,
    )
    turn_results = topology.run("Build auth module with QA iterative feedback.")
    state = orchestrator.state

    state_path = OUTPUT_DIR / "week6_iterative_feedback_state.json"
    report_path = OUTPUT_DIR / "week6_iterative_feedback_report.json"
    state.save_json(state_path)

    qa_artifact = state.get_latest_artifact("qa_report")
    deployment_artifact = state.get_latest_artifact("deployment")
    feedback_messages = [
        message
        for message in state.message_log.messages
        if message.msg_type == MessageType.FEEDBACK and message.sender == "orchestrator"
    ]

    checks = [
        CheckResult(
            name="turn_count",
            passed=len(turn_results) == 8,
            details=f"turn_count={len(turn_results)}",
        ),
        CheckResult(
            name="feedback_loop_executed",
            passed=any(result.agent_role == "backend_dev" for result in turn_results[4:]),
            details=(
                "post-qa roles="
                f"{[result.agent_role for result in turn_results[4:]]}"
            ),
        ),
        CheckResult(
            name="state_fields_populated",
            passed=all(
                [
                    state.requirements is not None,
                    state.architecture is not None,
                    state.backend_code is not None,
                    state.frontend_code is not None,
                    state.qa_report is not None,
                    state.deployment is not None,
                ]
            ),
            details="all lifecycle state fields populated",
        ),
        CheckResult(
            name="artifact_versions_after_rework",
            passed=(
                state.get_latest_artifact("backend_code") is not None
                and state.get_latest_artifact("backend_code").version == 2
                and qa_artifact is not None
                and qa_artifact.version == 2
            ),
            details=(
                "backend_v="
                f"{state.get_latest_artifact('backend_code').version if state.get_latest_artifact('backend_code') else 'None'}, "
                "qa_v="
                f"{qa_artifact.version if qa_artifact else 'None'}"
            ),
        ),
        CheckResult(
            name="deployment_success",
            passed=(
                deployment_artifact is not None
                and deployment_artifact.content.get("status") == "success"
            ),
            details=(
                "deployment_status="
                f"{deployment_artifact.content.get('status') if deployment_artifact else 'None'}"
            ),
        ),
        CheckResult(
            name="feedback_messages_recorded",
            passed=len(feedback_messages) >= 1,
            details=f"feedback_messages={len(feedback_messages)}",
        ),
        CheckResult(
            name="usage_counters_accumulated",
            passed=state.total_tokens == 4240 and state.total_api_calls == 8,
            details=f"tokens={state.total_tokens}, api_calls={state.total_api_calls}",
        ),
        CheckResult(
            name="iteration_counter",
            passed=state.iteration == 1,
            details=f"iteration={state.iteration}",
        ),
    ]

    status = "success" if all(item.passed for item in checks) else "failed"
    write_json(
        report_path,
        {
            "status": status,
            "checks": [asdict(item) for item in checks],
            "turn_results": [asdict(result) for result in turn_results],
            "state_snapshot": str(state_path),
        },
    )
    return (0 if status == "success" else 1), checks, state_path, report_path


def main() -> int:
    code, checks, state_path, report_path = run_smoke()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.details}")
    print(f"State snapshot: {state_path}")
    print(f"Report: {report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
