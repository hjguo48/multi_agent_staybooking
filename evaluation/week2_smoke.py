#!/usr/bin/env python3
"""Week 2 smoke run for core runtime structures."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week2"

import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.base_agent import BaseAgent
from core import AgentMessage, Artifact, MessageType, ProjectState


class DummyPMAgent(BaseAgent):
    """Minimal PM agent used to exercise BaseAgent + ProjectState integration."""

    def act(self, context: ProjectState) -> dict[str, Any]:
        requirements = {
            "project_name": "StayBooking",
            "functional_requirements": [
                {
                    "id": "FR-001",
                    "user_story": "As a guest, I want to login so I can book stays",
                    "acceptance_criteria": ["Given valid creds, when login, then JWT returned"],
                    "priority": "Must",
                    "complexity": "Low",
                }
            ],
            "non_functional_requirements": [{"id": "NFR-001", "description": "JWT auth"}],
            "api_contracts": [{"endpoint": "/auth/login", "method": "POST"}],
            "data_model": {"entities": ["User"], "relationships": []},
        }
        context.update_usage(token_delta=256, api_call_delta=1)
        return requirements


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_smoke() -> tuple[int, list[CheckResult], Path, Path]:
    state = ProjectState()
    pm_agent = DummyPMAgent(
        role="pm",
        system_prompt="Generate structured requirement JSON.",
        tools=[],
    )

    kickoff_message = AgentMessage(
        sender="orchestrator",
        receiver="pm",
        content="Generate requirements for StayBooking auth module.",
        msg_type=MessageType.TASK,
    )
    pm_agent.receive(kickoff_message)
    state.add_message(kickoff_message)

    requirements_payload = pm_agent.act(state)
    requirements_v1 = Artifact(
        artifact_id="requirements-doc",
        artifact_type="requirements",
        producer="pm",
        content=requirements_payload,
    )
    state.register_artifact("requirements", requirements_v1)
    state.requirements = {"artifact_ref": "requirements:v1"}

    # Simulate one revision round to validate version tracking.
    requirements_payload_v2 = dict(requirements_payload)
    requirements_payload_v2["revision_note"] = "Added non-functional clarification."
    requirements_v2 = Artifact(
        artifact_id="requirements-doc",
        artifact_type="requirements",
        producer="pm",
        content=requirements_payload_v2,
    )
    state.register_artifact("requirements", requirements_v2)
    state.requirements = {"artifact_ref": "requirements:v2"}

    handoff_message = AgentMessage(
        sender="pm",
        receiver="architect",
        content="Requirements ready for architecture design.",
        msg_type=MessageType.APPROVAL,
        artifacts=["requirements-doc:v2"],
    )
    state.add_message(handoff_message)

    state.increment_iteration()

    state_snapshot_path = OUTPUT_DIR / "week2_smoke_state.json"
    report_path = OUTPUT_DIR / "week2_smoke_report.json"
    state.save_json(state_snapshot_path)

    latest_requirements = state.get_latest_artifact("requirements")
    checks = [
        CheckResult(
            name="project_state_created",
            passed=bool(state.run_id),
            details=f"run_id={state.run_id}",
        ),
        CheckResult(
            name="artifact_versioning",
            passed=latest_requirements is not None and latest_requirements.version == 2,
            details=(
                "requirements latest version="
                f"{latest_requirements.version if latest_requirements else 'None'}"
            ),
        ),
        CheckResult(
            name="message_log_tracking",
            passed=len(state.message_log.messages) >= 2,
            details=f"message_count={len(state.message_log.messages)}",
        ),
        CheckResult(
            name="usage_counters",
            passed=state.total_tokens > 0 and state.total_api_calls > 0,
            details=f"tokens={state.total_tokens}, api_calls={state.total_api_calls}",
        ),
    ]

    status = "success" if all(item.passed for item in checks) else "failed"
    write_json(
        report_path,
        {
            "status": status,
            "checks": [asdict(item) for item in checks],
            "state_snapshot": str(state_snapshot_path),
            "artifacts": {
                "requirements_versions": state.artifact_store.list_versions("requirements")
            },
        },
    )
    code = 0 if status == "success" else 1
    return code, checks, state_snapshot_path, report_path


def main() -> int:
    code, checks, state_snapshot_path, report_path = run_smoke()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.details}")
    print(f"State snapshot: {state_snapshot_path}")
    print(f"Report: {report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
