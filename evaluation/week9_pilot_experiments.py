#!/usr/bin/env python3
"""Week 9 pilot experiments and stability checks."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week9"
PILOT_CONFIG = PROJECT_ROOT / "configs" / "pilot" / "week9_pilot_matrix.json"
GRANULARITY_CONFIG = PROJECT_ROOT / "configs" / "granularity_profiles.json"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents import (
    ArchitectAgent,
    BackendDeveloperAgent,
    CoordinatorAgent,
    DevOpsAgent,
    FrontendDeveloperAgent,
    PeerReviewerAgent,
    ProductManagerAgent,
    QAAgent,
)
from core import ProjectState, load_granularity_registry
from core.orchestrator import Orchestrator, TurnResult
from llm import BaseLLMClient, LLMProfile, create_llm_client, load_llm_registry
from topologies.hub_spoke import HubAndSpokeTopology
from topologies.iterative_feedback import IterativeFeedbackTopology
from topologies.peer_review import PeerReviewTopology
from topologies.sequential import SequentialTopology


@dataclass
class CheckResult:
    name: str
    passed: bool
    details: str


@dataclass
class CaseAttempt:
    attempt: int
    llm_enabled: bool
    success: bool
    turn_count: int
    error: str | None
    duration_seconds: float
    total_tokens: int
    total_api_calls: int
    state_snapshot: str


@dataclass
class CaseResult:
    name: str
    topology: str
    granularity: str
    success: bool
    attempts: list[CaseAttempt]
    final_error: str | None
    final_state_snapshot: str


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _register_standard_agents(
    orchestrator: Orchestrator,
    *,
    llm_client: BaseLLMClient | None,
    llm_profile: LLMProfile | None,
    topology: str,
) -> None:
    orchestrator.register_agent(
        ProductManagerAgent("pm", "PM system prompt", [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        ArchitectAgent("architect", "Architect system prompt", [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        BackendDeveloperAgent("backend_dev", "Backend system prompt", [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        FrontendDeveloperAgent("frontend_dev", "Frontend system prompt", [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        QAAgent("qa", "QA system prompt", [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        DevOpsAgent("devops", "DevOps system prompt", [], llm_client=llm_client, llm_profile=llm_profile)
    )

    if topology == "hub_spoke":
        orchestrator.register_agent(CoordinatorAgent("coordinator", "Coordinator prompt", []))
    if topology == "peer_review":
        orchestrator.register_agent(PeerReviewerAgent("reviewer", "Reviewer prompt", []))


def _run_sequential_with_granularity(
    orchestrator: Orchestrator,
    granularity: str,
) -> list[TurnResult]:
    registry = load_granularity_registry(GRANULARITY_CONFIG)
    profile = registry.get_profile(granularity)

    all_results: list[TurnResult] = []
    if profile.prelude_roles:
        all_results.extend(
            SequentialTopology(orchestrator=orchestrator, roles=profile.prelude_roles).run(
                f"[pilot] prelude for {granularity}"
            )
        )

    for work_item in profile.work_items:
        all_results.extend(
            SequentialTopology(orchestrator=orchestrator, roles=profile.per_item_roles).run(
                f"[pilot] {granularity} item: {work_item}"
            )
        )

    if profile.final_roles:
        all_results.extend(
            SequentialTopology(orchestrator=orchestrator, roles=profile.final_roles).run(
                f"[pilot] finalization for {granularity}"
            )
        )
    return all_results


def _execute_case(
    *,
    topology: str,
    granularity: str,
    llm_client: BaseLLMClient | None,
    llm_profile: LLMProfile | None,
) -> tuple[list[TurnResult], ProjectState]:
    orchestrator = Orchestrator()
    _register_standard_agents(
        orchestrator,
        llm_client=llm_client,
        llm_profile=llm_profile,
        topology=topology,
    )

    if topology == "sequential":
        results = _run_sequential_with_granularity(orchestrator, granularity=granularity)
        return results, orchestrator.state
    if topology == "hub_spoke":
        topology_runtime = HubAndSpokeTopology(orchestrator=orchestrator, max_cycles=32)
        return topology_runtime.run(f"[pilot] hub-spoke {granularity}"), orchestrator.state
    if topology == "peer_review":
        topology_runtime = PeerReviewTopology(
            orchestrator=orchestrator,
            max_revisions_per_target=1,
        )
        return topology_runtime.run(f"[pilot] peer-review {granularity}"), orchestrator.state
    if topology == "iterative_feedback":
        topology_runtime = IterativeFeedbackTopology(
            orchestrator=orchestrator,
            max_feedback_iterations=2,
            max_stagnant_rounds=1,
        )
        return topology_runtime.run(f"[pilot] iterative-feedback {granularity}"), orchestrator.state

    raise ValueError(f"Unsupported topology: {topology}")


def _case_success(turn_results: list[TurnResult], state: ProjectState) -> tuple[bool, str]:
    if not turn_results:
        return False, "empty turn results"
    if state.deployment is None:
        return False, "deployment not produced"
    required = [
        state.requirements is not None,
        state.architecture is not None,
        state.backend_code is not None,
        state.frontend_code is not None,
        state.qa_report is not None,
        state.deployment is not None,
    ]
    if not all(required):
        return False, "lifecycle state incomplete"
    if state.total_api_calls <= 0:
        return False, "api usage counter is zero"
    return True, "stable run"


def run_pilot() -> tuple[int, list[CheckResult], Path]:
    config = _read_json(PILOT_CONFIG)
    llm_profiles_path = PROJECT_ROOT / config["llm_profiles_path"]
    llm_profile_name = str(config.get("llm_profile", "")).strip()
    allow_network_llm = bool(config.get("allow_network_llm", False))
    max_attempts = int(config.get("max_attempts_per_case", 1))
    disable_llm_on_retry = bool(config.get("disable_llm_on_retry", True))
    cases = config.get("cases", [])

    registry = load_llm_registry(llm_profiles_path)
    primary_client, primary_profile, llm_reason = create_llm_client(
        registry,
        profile_name=llm_profile_name,
    )
    if not allow_network_llm and primary_profile.provider != "mock":
        primary_client = None
        llm_reason = (
            f"network llm disabled by pilot config (provider={primary_profile.provider})"
        )

    checks: list[CheckResult] = []
    checks.append(
        CheckResult(
            name="pilot_cases_non_empty",
            passed=isinstance(cases, list) and len(cases) > 0,
            details=f"case_count={len(cases) if isinstance(cases, list) else 'invalid'}",
        )
    )
    checks.append(
        CheckResult(
            name="llm_profile_loaded",
            passed=True,
            details=(
                f"profile={primary_profile.name}, provider={primary_profile.provider}, "
                f"llm_available={primary_client is not None}, reason={llm_reason}"
            ),
        )
    )

    case_results: list[CaseResult] = []
    failure_buckets: dict[str, int] = {}

    if not isinstance(cases, list):
        raise ValueError("cases must be a list")

    for case in cases:
        if not isinstance(case, dict):
            continue

        case_name = str(case.get("name", "")).strip() or "unnamed_case"
        topology = str(case.get("topology", "")).strip().lower()
        granularity = str(case.get("granularity", "module")).strip().lower()

        attempts: list[CaseAttempt] = []
        final_error: str | None = None
        final_state_snapshot = ""

        for attempt in range(1, max_attempts + 1):
            llm_enabled = primary_client is not None
            llm_client = primary_client
            llm_profile = primary_profile
            if attempt > 1 and disable_llm_on_retry:
                llm_enabled = False
                llm_client = None
                llm_profile = None

            started = time.monotonic()
            error_text: str | None = None
            turn_results: list[TurnResult] = []
            state = ProjectState()
            try:
                turn_results, state = _execute_case(
                    topology=topology,
                    granularity=granularity,
                    llm_client=llm_client,
                    llm_profile=llm_profile,
                )
                run_ok, run_reason = _case_success(turn_results, state)
                if not run_ok:
                    error_text = run_reason
            except Exception as exc:
                error_text = str(exc)

            duration = max(time.monotonic() - started, 0.0)
            state_path = OUTPUT_DIR / "cases" / f"{case_name}_attempt{attempt}_state.json"
            state.save_json(state_path)
            final_state_snapshot = _repo_rel(state_path)

            success = error_text is None
            attempts.append(
                CaseAttempt(
                    attempt=attempt,
                    llm_enabled=llm_enabled,
                    success=success,
                    turn_count=len(turn_results),
                    error=error_text,
                    duration_seconds=duration,
                    total_tokens=state.total_tokens,
                    total_api_calls=state.total_api_calls,
                    state_snapshot=_repo_rel(state_path),
                )
            )

            if success:
                final_error = None
                break

            final_error = error_text
            failure_key = error_text or "unknown_error"
            failure_buckets[failure_key] = failure_buckets.get(failure_key, 0) + 1

        case_success = any(attempt.success for attempt in attempts)
        case_results.append(
            CaseResult(
                name=case_name,
                topology=topology,
                granularity=granularity,
                success=case_success,
                attempts=attempts,
                final_error=final_error,
                final_state_snapshot=final_state_snapshot,
            )
        )

    success_count = sum(1 for item in case_results if item.success)
    success_rate = (success_count / len(case_results)) if case_results else 0.0
    retry_count = sum(max(len(item.attempts) - 1, 0) for item in case_results)

    checks.append(
        CheckResult(
            name="pilot_success_rate",
            passed=success_rate >= 0.75,
            details=f"success_count={success_count}, total={len(case_results)}, success_rate={success_rate:.4f}",
        )
    )
    checks.append(
        CheckResult(
            name="pilot_retry_budget",
            passed=all(len(item.attempts) <= max_attempts for item in case_results),
            details=f"max_attempts={max_attempts}, total_retries={retry_count}",
        )
    )
    checks.append(
        CheckResult(
            name="pilot_failure_buckets_recorded",
            passed=True,
            details=f"failure_bucket_count={len(failure_buckets)}",
        )
    )

    status = "success" if all(item.passed for item in checks) else "failed"
    report_path = OUTPUT_DIR / "week9_pilot_report.json"
    write_json(
        report_path,
        {
            "status": status,
            "pilot_config": _repo_rel(PILOT_CONFIG),
            "llm_profile": {
                "name": primary_profile.name,
                "provider": primary_profile.provider,
                "model": primary_profile.model,
                "client_available": primary_client is not None,
                "availability_reason": llm_reason,
                "allow_network_llm": allow_network_llm,
            },
            "summary": {
                "case_count": len(case_results),
                "success_count": success_count,
                "success_rate": success_rate,
                "retry_count": retry_count,
            },
            "failure_buckets": failure_buckets,
            "cases": [
                {
                    "name": case_result.name,
                    "topology": case_result.topology,
                    "granularity": case_result.granularity,
                    "success": case_result.success,
                    "attempts": [asdict(item) for item in case_result.attempts],
                    "final_error": case_result.final_error,
                    "final_state_snapshot": case_result.final_state_snapshot,
                }
                for case_result in case_results
            ],
            "checks": [asdict(check) for check in checks],
        },
    )
    return (0 if status == "success" else 1), checks, report_path


def main() -> int:
    code, checks, report_path = run_pilot()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.details}")
    print(f"Pilot report: {report_path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
