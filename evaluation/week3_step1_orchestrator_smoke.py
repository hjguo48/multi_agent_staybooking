#!/usr/bin/env python3
"""Week 3 Step 1 smoke run for minimal orchestrator runtime."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week3"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.base_agent import BaseAgent
from core.models import AgentMessage, Artifact, MessageType
from core.orchestrator import Orchestrator


class DummyPMAgent(BaseAgent):
    """Minimal PM agent for orchestrator wiring validation."""

    def act(self, context) -> dict[str, Any]:  # type: ignore[override]
        requirements_payload = {
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
        return {
            "state_updates": {"requirements": {"artifact_ref": "requirements:v1"}},
            "artifacts": [
                {
                    "store_key": "requirements",
                    "artifact": Artifact(
                        artifact_id="requirements-doc",
                        artifact_type="requirements",
                        producer=self.role,
                        content=requirements_payload,
                    ),
                }
            ],
            "messages": [
                AgentMessage(
                    sender=self.role,
                    receiver="architect",
                    content="Requirements ready.",
                    msg_type=MessageType.TASK,
                    artifacts=["requirements-doc:v1"],
                )
            ],
            "usage": {"tokens": 320, "api_calls": 1},
        }


class DummyArchitectAgent(BaseAgent):
    """Minimal Architect agent for orchestrator wiring validation."""

    def act(self, context) -> dict[str, Any]:  # type: ignore[override]
        architecture_payload = {
            "tech_stack": {
                "backend": {"language": "Java 17", "framework": "Spring Boot 3.x"},
                "frontend": {"framework": "React 18"},
            },
            "modules": [
                {"name": "auth-module", "responsibility": "Login and registration"}
            ],
            "database_schema": {"tables": ["users"]},
            "openapi_spec": {"paths": {"/auth/login": {"post": {}}}},
            "deployment": {"target": "docker-compose"},
        }
        return {
            "state_updates": {"architecture": {"artifact_ref": "architecture:v1"}},
            "artifacts": [
                {
                    "store_key": "architecture",
                    "artifact": Artifact(
                        artifact_id="architecture-doc",
                        artifact_type="architecture",
                        producer=self.role,
                        content=architecture_payload,
                    ),
                }
            ],
            "messages": [
                {
                    "sender": self.role,
                    "receiver": "orchestrator",
                    "content": "Architecture draft completed.",
                    "msg_type": "STATUS",
                    "artifacts": ["architecture-doc:v1"],
                }
            ],
            "usage": {"tokens": 410, "api_calls": 1},
        }


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def run_smoke() -> tuple[int, list[CheckResult], Path, Path]:
    orchestrator = Orchestrator()
    pm = DummyPMAgent(role="pm", system_prompt="PM prompt", tools=[])
    architect = DummyArchitectAgent(role="architect", system_prompt="Architect prompt", tools=[])
    orchestrator.register_agent(pm)
    orchestrator.register_agent(architect)

    orchestrator.kickoff("pm", "Start sequential workflow on auth module.")
    turn_results = orchestrator.run_sequence(["pm", "architect"])
    state = orchestrator.state

    state_snapshot_path = OUTPUT_DIR / "week3_step1_state.json"
    report_path = OUTPUT_DIR / "week3_step1_orchestrator_report.json"
    state.save_json(state_snapshot_path)

    requirements_latest = state.get_latest_artifact("requirements")
    architecture_latest = state.get_latest_artifact("architecture")

    checks = [
        CheckResult(
            name="turn_count",
            passed=len(turn_results) == 2,
            details=f"turn_count={len(turn_results)}",
        ),
        CheckResult(
            name="all_turns_success",
            passed=all(result.success for result in turn_results),
            details="all results success expected True",
        ),
        CheckResult(
            name="requirements_state_updated",
            passed=state.requirements is not None,
            details=f"requirements={state.requirements}",
        ),
        CheckResult(
            name="architecture_state_updated",
            passed=state.architecture is not None,
            details=f"architecture={state.architecture}",
        ),
        CheckResult(
            name="artifact_versions_recorded",
            passed=(
                requirements_latest is not None
                and requirements_latest.version == 1
                and architecture_latest is not None
                and architecture_latest.version == 1
            ),
            details=(
                "requirements_v="
                f"{requirements_latest.version if requirements_latest else 'None'}, "
                "architecture_v="
                f"{architecture_latest.version if architecture_latest else 'None'}"
            ),
        ),
        CheckResult(
            name="message_log_recorded",
            passed=len(state.message_log.messages) >= 3,
            details=f"message_count={len(state.message_log.messages)}",
        ),
        CheckResult(
            name="usage_counters_updated",
            passed=state.total_tokens == 730 and state.total_api_calls == 2,
            details=f"tokens={state.total_tokens}, api_calls={state.total_api_calls}",
        ),
    ]

    status = "success" if all(item.passed for item in checks) else "failed"
    write_json(
        report_path,
        {
            "status": status,
            "checks": [asdict(item) for item in checks],
            "turn_results": [asdict(item) for item in turn_results],
            "state_snapshot": str(state_snapshot_path),
        },
    )
    return (0 if status == "success" else 1), checks, state_snapshot_path, report_path


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
