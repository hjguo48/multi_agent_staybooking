#!/usr/bin/env python3
"""Week 3 Step 2 smoke run for sequential topology flow."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week3"

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
from core.orchestrator import Orchestrator
from topologies.sequential import DEFAULT_SEQUENTIAL_ROLES, SequentialTopology


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
    orchestrator.register_agent(QAAgent("qa", "qa prompt", []))
    orchestrator.register_agent(DevOpsAgent("devops", "devops prompt", []))

    topology = SequentialTopology(orchestrator=orchestrator)
    turn_results = topology.run("Build auth module end-to-end for StayBooking.")
    state = orchestrator.state

    state_path = OUTPUT_DIR / "week3_step2_state.json"
    report_path = OUTPUT_DIR / "week3_step2_sequential_report.json"
    state.save_json(state_path)

    qa_artifact = state.get_latest_artifact("qa_report")
    deployment_artifact = state.get_latest_artifact("deployment")

    checks = [
        CheckResult(
            name="turn_count",
            passed=len(turn_results) == len(DEFAULT_SEQUENTIAL_ROLES),
            details=f"turn_count={len(turn_results)}",
        ),
        CheckResult(
            name="all_turns_success",
            passed=all(result.success for result in turn_results),
            details="all turn results should be success",
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
            details=(
                "requirements/architecture/backend_code/frontend_code/"
                "qa_report/deployment populated"
            ),
        ),
        CheckResult(
            name="artifact_keys_present",
            passed=state.artifact_store.keys()
            == [
                "architecture",
                "backend_code",
                "deployment",
                "frontend_code",
                "qa_report",
                "requirements",
            ],
            details=f"artifact_keys={state.artifact_store.keys()}",
        ),
        CheckResult(
            name="qa_quality_gate",
            passed=(
                qa_artifact is not None
                and qa_artifact.content["summary"]["test_pass_rate"] >= 0.85
                and qa_artifact.content["summary"]["critical_bugs"] == 0
            ),
            details=(
                f"qa_summary={qa_artifact.content['summary'] if qa_artifact else 'None'}"
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
            name="message_flow_recorded",
            passed=len(state.message_log.messages) >= 6,
            details=f"message_count={len(state.message_log.messages)}",
        ),
        CheckResult(
            name="usage_counters_accumulated",
            passed=state.total_tokens == 3090 and state.total_api_calls == 6,
            details=f"tokens={state.total_tokens}, api_calls={state.total_api_calls}",
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
