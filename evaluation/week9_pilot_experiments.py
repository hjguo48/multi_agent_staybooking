#!/usr/bin/env python3
"""Week 9 pilot experiments and stability checks."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week9"
PILOT_CONFIG = PROJECT_ROOT / "configs" / "pilot" / "week9_pilot_matrix.json"
GRANULARITY_CONFIG = PROJECT_ROOT / "configs" / "granularity_profiles.json"
PROMPTS_DIR = PROJECT_ROOT / "configs" / "prompts"


def _load_prompt(name: str) -> str:
    """Load agent system prompt from configs/prompts/<name>.md, fallback to placeholder."""
    prompt_file = PROMPTS_DIR / f"{name}.md"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    return f"{name} system prompt"

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
from tools import ArtifactMaterializer, BuildDeployValidator

GENERATED_WORKSPACES_DIR = OUTPUT_DIR / "generated_workspaces"
VALIDATION_TIMEOUT_SECONDS = 240.0
VALIDATOR_RUN_BACKEND_TESTS = False  # @SpringBootTest requires live PostgreSQL; disabled until DB infra is ready
VALIDATOR_RUN_FRONTEND_CHECKS = True
VALIDATOR_RUN_FRONTEND_TESTS = False  # CRA test runner requires CI env; disabled for local runs
VALIDATOR_RUN_FRONTEND_LINT = True
REQUIRE_LLM_CODE_OUTPUTS = True
ENFORCE_BUILD_TEST_GATE = True


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
    llm_output_gate_passed: bool
    llm_output_gate: dict[str, Any]
    materialization: dict[str, Any] | None
    build_test_gate_passed: bool
    build_test_gate: dict[str, Any] | None


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


def _resolve_optional_path(path_text: Any) -> Path | None:
    text = str(path_text or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved = candidate.resolve()
    if resolved.exists():
        return resolved
    return None


def _latest_artifact(state_payload: dict[str, Any], key: str) -> dict[str, Any] | None:
    artifact_store = state_payload.get("artifact_store", {})
    if not isinstance(artifact_store, dict):
        return None
    versions = artifact_store.get(key, [])
    if not isinstance(versions, list) or not versions:
        return None
    latest = versions[-1]
    if not isinstance(latest, dict):
        return None
    return latest


def _llm_code_output_check(state_payload: dict[str, Any], key: str) -> tuple[bool, dict[str, Any]]:
    latest = _latest_artifact(state_payload, key)
    if latest is None:
        return False, {
            "artifact_key": key,
            "artifact_present": False,
            "passed": False,
            "reason": "artifact_missing",
        }

    metadata = latest.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    generation = metadata.get("generation", {})
    if not isinstance(generation, dict):
        generation = {}
    source = str(generation.get("source", "")).strip()
    reason = str(generation.get("reason", "")).strip()

    content = latest.get("content", {})
    if not isinstance(content, dict):
        content = {}
    code_bundle = content.get("code_bundle", {})
    if not isinstance(code_bundle, dict):
        code_bundle = {}

    non_empty_files = [
        file_path
        for file_path, file_content in code_bundle.items()
        if isinstance(file_content, str) and file_content.strip()
    ]

    passed = source == "llm" and len(non_empty_files) > 0
    fail_reason = ""
    if source != "llm":
        fail_reason = f"generation_source={source or 'unknown'}"
    elif not non_empty_files:
        fail_reason = "empty_code_bundle"

    return passed, {
        "artifact_key": key,
        "artifact_present": True,
        "generation_source": source,
        "generation_reason": reason,
        "code_bundle_file_count": len(code_bundle),
        "code_bundle_non_empty_file_count": len(non_empty_files),
        "passed": passed,
        "reason": fail_reason,
    }


def _evaluate_llm_output_gate(state_payload: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    backend_ok, backend_details = _llm_code_output_check(state_payload, "backend_code")
    frontend_ok, frontend_details = _llm_code_output_check(state_payload, "frontend_code")
    passed = backend_ok and frontend_ok
    return passed, {
        "passed": passed,
        "backend": backend_details,
        "frontend": frontend_details,
    }


def _step_status(checks: list[dict[str, Any]], step_name: str) -> dict[str, Any]:
    for check in checks:
        if str(check.get("name", "")).strip() == step_name:
            return {
                "present": True,
                "executed": bool(check.get("executed", False)),
                "passed": bool(check.get("passed", False)),
                "skipped_reason": check.get("skipped_reason"),
            }
    return {
        "present": False,
        "executed": False,
        "passed": False,
        "skipped_reason": "missing_step",
    }


def _evaluate_build_test_gate(validation: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    backend_checks = validation.get("backend", [])
    frontend_checks = validation.get("frontend", [])
    if not isinstance(backend_checks, list):
        backend_checks = []
    if not isinstance(frontend_checks, list):
        frontend_checks = []

    backend_build = _step_status(backend_checks, "backend_build")
    backend_test = _step_status(backend_checks, "backend_test")
    frontend_build = _step_status(frontend_checks, "frontend_build")
    frontend_test = _step_status(frontend_checks, "frontend_test")
    frontend_lint = _step_status(frontend_checks, "frontend_lint")

    backend_gate_ok = backend_build["executed"] and backend_build["passed"]
    if VALIDATOR_RUN_BACKEND_TESTS:
        backend_gate_ok = backend_gate_ok and backend_test["executed"] and backend_test["passed"]

    frontend_gate_ok = frontend_build["executed"] and frontend_build["passed"]
    all_quality_candidates = [frontend_test, frontend_lint]
    frontend_quality_steps = [s for s in all_quality_candidates if s["executed"]]
    if frontend_quality_steps:
        # At least one quality step ran: all must pass.
        frontend_quality_ok = all(s["passed"] for s in frontend_quality_steps)
    else:
        # No quality step ran: OK only if every non-executed step has a valid skip reason
        # (e.g. "disabled by validator config" or "npm lint script missing").
        # If skipped_reason is None/empty the step mysteriously did not run → gate fail.
        frontend_quality_ok = all(
            bool(s.get("skipped_reason")) for s in all_quality_candidates if not s["executed"]
        )
    if VALIDATOR_RUN_FRONTEND_CHECKS:
        frontend_gate_ok = frontend_gate_ok and frontend_quality_ok

    passed = backend_gate_ok and frontend_gate_ok
    scores = validation.get("scores", {})
    if not isinstance(scores, dict):
        scores = {}

    return passed, {
        "passed": passed,
        "backend": {
            "backend_build": backend_build,
            "backend_test": backend_test,
            "gate_ok": backend_gate_ok,
        },
        "frontend": {
            "frontend_build": frontend_build,
            "frontend_test": frontend_test,
            "frontend_lint": frontend_lint,
            "quality_steps_executed": len(frontend_quality_steps),
            "quality_gate_ok": frontend_quality_ok,
            "gate_ok": frontend_gate_ok,
        },
        "scores": scores,
        "validation": validation,
    }


def _register_standard_agents(
    orchestrator: Orchestrator,
    *,
    llm_client: BaseLLMClient | None,
    llm_profile: LLMProfile | None,
    topology: str,
) -> None:
    orchestrator.register_agent(
        ProductManagerAgent("pm", _load_prompt("pm_agent"), [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        ArchitectAgent("architect", _load_prompt("architect_agent"), [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        BackendDeveloperAgent("backend_dev", _load_prompt("backend_dev_agent"), [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        FrontendDeveloperAgent("frontend_dev", _load_prompt("frontend_dev_agent"), [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        QAAgent("qa", _load_prompt("qa_agent"), [], llm_client=llm_client, llm_profile=llm_profile)
    )
    orchestrator.register_agent(
        DevOpsAgent("devops", _load_prompt("devops_agent"), [], llm_client=llm_client, llm_profile=llm_profile)
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
    disable_llm_on_retry_config = bool(config.get("disable_llm_on_retry", True))
    disable_llm_on_retry = disable_llm_on_retry_config and not REQUIRE_LLM_CODE_OUTPUTS
    cases = config.get("cases", [])
    repo_landing = config.get("repo_landing", {})
    if not isinstance(repo_landing, dict):
        repo_landing = {}
    materialization_mode = str(repo_landing.get("materialization_mode", "pure_generated")).strip().lower()
    backend_template = _resolve_optional_path(repo_landing.get("backend_template"))
    frontend_template = _resolve_optional_path(repo_landing.get("frontend_template"))
    if materialization_mode in ("template_overlay", "scaffold_overlay"):
        if backend_template is None:
            raise FileNotFoundError("repo_landing.backend_template not found")
        if frontend_template is None:
            raise FileNotFoundError("repo_landing.frontend_template not found")
    elif materialization_mode != "pure_generated":
        raise ValueError(
            "repo_landing.materialization_mode must be 'pure_generated', 'template_overlay', or 'scaffold_overlay'"
        )
    materializer = ArtifactMaterializer(GENERATED_WORKSPACES_DIR)

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
    checks.append(
        CheckResult(
            name="week10_step1_hard_gates_config",
            passed=True,
            details=(
                f"require_llm_code_outputs={REQUIRE_LLM_CODE_OUTPUTS}, "
                f"enforce_build_test_gate={ENFORCE_BUILD_TEST_GATE}, "
                f"disable_llm_on_retry_config={disable_llm_on_retry_config}, "
                f"disable_llm_on_retry_effective={disable_llm_on_retry}, "
                f"materialization_mode={materialization_mode}"
            ),
        )
    )

    case_results: list[CaseResult] = []
    failure_buckets: dict[str, int] = {}
    total_attempt_count = 0
    llm_gate_pass_count = 0
    materialization_pass_count = 0
    build_gate_pass_count = 0
    materialization_executed_count = 0

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
            total_attempt_count += 1
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
            state_payload: dict[str, Any] = {}
            run_ok = False
            run_reason = "run_not_executed"
            try:
                turn_results, state = _execute_case(
                    topology=topology,
                    granularity=granularity,
                    llm_client=llm_client,
                    llm_profile=llm_profile,
                )
                run_ok, run_reason = _case_success(turn_results, state)
            except Exception as exc:
                run_ok = False
                run_reason = f"execution_error:{exc}"

            state_payload = state.to_dict()

            llm_gate_passed = True
            llm_gate: dict[str, Any] = {"passed": True, "disabled": True}
            if REQUIRE_LLM_CODE_OUTPUTS:
                llm_gate_passed, llm_gate = _evaluate_llm_output_gate(state_payload)
            if llm_gate_passed:
                llm_gate_pass_count += 1

            materialization_report: dict[str, Any] | None = None
            build_test_gate_passed = not ENFORCE_BUILD_TEST_GATE
            build_test_gate: dict[str, Any] | None = None

            try:
                workspace_suffix = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                workspace_name = f"{case_name}_attempt{attempt}_{workspace_suffix}"
                use_template = materialization_mode in ("template_overlay", "scaffold_overlay")
                materialized = materializer.materialize(
                    run_name=workspace_name,
                    state_payload=state_payload,
                    backend_template=backend_template if use_template else None,
                    frontend_template=frontend_template if use_template else None,
                )
                materialization_executed_count += 1
                backend_files = len(materialized.backend_files_written)
                frontend_files = len(materialized.frontend_files_written)
                materialization_passed = backend_files > 0 and frontend_files > 0
                if materialization_passed:
                    materialization_pass_count += 1

                materialization_report = {
                    "passed": materialization_passed,
                    "workspace_root": _repo_rel(Path(materialized.workspace_root)),
                    "backend_root": _repo_rel(Path(materialized.backend_root)),
                    "frontend_root": _repo_rel(Path(materialized.frontend_root)),
                    "backend_files_written_count": backend_files,
                    "frontend_files_written_count": frontend_files,
                    "materialization_mode": materialization_mode,
                    "backend_template_used": (
                        _repo_rel(backend_template) if backend_template else None
                    ),
                    "frontend_template_used": (
                        _repo_rel(frontend_template) if frontend_template else None
                    ),
                    "backend_files_written": [
                        _repo_rel(Path(path)) for path in materialized.backend_files_written
                    ],
                    "frontend_files_written": [
                        _repo_rel(Path(path)) for path in materialized.frontend_files_written
                    ],
                }

                validation_result: dict[str, Any] = {}
                if ENFORCE_BUILD_TEST_GATE:
                    validator = BuildDeployValidator(
                        backend_root=Path(materialized.backend_root),
                        frontend_root=Path(materialized.frontend_root),
                        timeout_seconds=VALIDATION_TIMEOUT_SECONDS,
                        run_backend_tests=VALIDATOR_RUN_BACKEND_TESTS,
                        run_frontend_checks=VALIDATOR_RUN_FRONTEND_CHECKS,
                        run_frontend_tests=VALIDATOR_RUN_FRONTEND_TESTS,
                        run_frontend_lint=VALIDATOR_RUN_FRONTEND_LINT,
                    )
                    validation_result = validator.run(state_payload)
                    build_test_gate_passed, build_test_gate = _evaluate_build_test_gate(
                        validation_result
                    )
                    if build_test_gate_passed:
                        build_gate_pass_count += 1
                else:
                    build_test_gate = {
                        "passed": True,
                        "disabled": True,
                        "validation": validation_result,
                    }
            except Exception as exc:
                materialization_report = {
                    "passed": False,
                    "error": str(exc),
                }
                build_test_gate_passed = False
                build_test_gate = {
                    "passed": False,
                    "error": f"materialize_or_validate_error:{exc}",
                }

            failure_reasons: list[str] = []
            if not run_ok:
                failure_reasons.append(run_reason)
            if REQUIRE_LLM_CODE_OUTPUTS and not llm_gate_passed:
                failure_reasons.append("llm_output_gate_failed")
            if materialization_report is None or not bool(materialization_report.get("passed", False)):
                failure_reasons.append("materialization_failed")
            if ENFORCE_BUILD_TEST_GATE and not build_test_gate_passed:
                failure_reasons.append("build_test_gate_failed")

            if failure_reasons:
                error_text = "; ".join(failure_reasons)

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
                    llm_output_gate_passed=llm_gate_passed,
                    llm_output_gate=llm_gate,
                    materialization=materialization_report,
                    build_test_gate_passed=build_test_gate_passed,
                    build_test_gate=build_test_gate,
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
    checks.append(
        CheckResult(
            name="week10_step1_materialization_executed",
            passed=materialization_executed_count == total_attempt_count and total_attempt_count > 0,
            details=(
                f"materialization_executed_count={materialization_executed_count}, "
                f"total_attempt_count={total_attempt_count}"
            ),
        )
    )
    checks.append(
        CheckResult(
            name="week10_step1_llm_output_gate_observed",
            passed=llm_gate_pass_count > 0,
            details=(
                f"llm_gate_pass_count={llm_gate_pass_count}, "
                f"total_attempt_count={total_attempt_count}"
            ),
        )
    )
    checks.append(
        CheckResult(
            name="week10_step1_build_test_gate_observed",
            passed=build_gate_pass_count > 0,
            details=(
                f"build_gate_pass_count={build_gate_pass_count}, "
                f"total_attempt_count={total_attempt_count}"
            ),
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
                "disable_llm_on_retry_config": disable_llm_on_retry_config,
                "disable_llm_on_retry_effective": disable_llm_on_retry,
            },
            "week10_step1_hard_gates": {
                "require_llm_code_outputs": REQUIRE_LLM_CODE_OUTPUTS,
                "enforce_build_test_gate": ENFORCE_BUILD_TEST_GATE,
                "generated_workspaces_root": _repo_rel(GENERATED_WORKSPACES_DIR),
                "validation_timeout_seconds": VALIDATION_TIMEOUT_SECONDS,
                "validator_options": {
                    "run_backend_tests": VALIDATOR_RUN_BACKEND_TESTS,
                    "run_frontend_checks": VALIDATOR_RUN_FRONTEND_CHECKS,
                    "run_frontend_tests": VALIDATOR_RUN_FRONTEND_TESTS,
                    "run_frontend_lint": VALIDATOR_RUN_FRONTEND_LINT,
                },
                "materialization_mode": materialization_mode,
                "backend_template": _repo_rel(backend_template) if backend_template else None,
                "frontend_template": _repo_rel(frontend_template) if frontend_template else None,
            },
            "summary": {
                "case_count": len(case_results),
                "success_count": success_count,
                "success_rate": success_rate,
                "retry_count": retry_count,
                "total_attempt_count": total_attempt_count,
                "llm_gate_pass_count": llm_gate_pass_count,
                "materialization_pass_count": materialization_pass_count,
                "build_gate_pass_count": build_gate_pass_count,
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
