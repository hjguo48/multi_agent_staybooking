#!/usr/bin/env python3
"""Week 12 primary experiment — 4 topologies × 3 granularities = 32 cases.

Answers RQ1 (topology effect on code quality) and RQ2 (granularity interaction).
Adds composite Q score calculation per case and best-config selection.
"""

from __future__ import annotations

import copy
import json
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "week12"
PILOT_CONFIG = PROJECT_ROOT / "configs" / "pilot" / "week12_experiment_matrix.json"
GROUND_TRUTH_PATH = PROJECT_ROOT / "ground_truth" / "benchmark" / "staybooking_ground_truth.json"
GRANULARITY_CONFIG = PROJECT_ROOT / "configs" / "granularity_profiles.json"
PROMPTS_DIR = PROJECT_ROOT / "configs" / "prompts"


def _load_prompt(name: str) -> str:
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
from core.evaluation_metrics import RunMetrics, apply_composite_scores, evaluate_run
from core.orchestrator import Orchestrator, TurnResult
from llm import BaseLLMClient, LLMProfile, create_llm_client, load_llm_registry
from topologies.hub_spoke import HubAndSpokeTopology
from topologies.iterative_feedback import IterativeFeedbackTopology
from topologies.peer_review import PeerReviewTopology
from topologies.sequential import SequentialTopology
from tools import ArtifactMaterializer, BuildDeployValidator

GENERATED_WORKSPACES_DIR = OUTPUT_DIR / "generated_workspaces"
VALIDATION_TIMEOUT_SECONDS = 240.0
VALIDATOR_RUN_BACKEND_TESTS = False
VALIDATOR_RUN_FRONTEND_CHECKS = True
VALIDATOR_RUN_FRONTEND_TESTS = False
VALIDATOR_RUN_FRONTEND_LINT = True
REQUIRE_LLM_CODE_OUTPUTS = True
ENFORCE_BUILD_TEST_GATE = True

# QA-driven rework loop (sequential topology)
QA_FEEDBACK_ENABLED = True
QA_FEEDBACK_MAX_ROUNDS = 3
QA_FEEDBACK_PASS_THRESHOLD = 0.85
_QA_REWORK_ROLES = ["backend_dev", "frontend_dev", "qa"]


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
    q_metrics: dict[str, Any] = field(default_factory=dict)


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
        fp for fp, fc in code_bundle.items()
        if isinstance(fc, str) and fc.strip()
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
    return passed, {"passed": passed, "backend": backend_details, "frontend": frontend_details}


def _step_status(checks: list[dict[str, Any]], step_name: str) -> dict[str, Any]:
    for check in checks:
        if str(check.get("name", "")).strip() == step_name:
            return {
                "present": True,
                "executed": bool(check.get("executed", False)),
                "passed": bool(check.get("passed", False)),
                "skipped_reason": check.get("skipped_reason"),
            }
    return {"present": False, "executed": False, "passed": False, "skipped_reason": "missing_step"}


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
        frontend_quality_ok = all(s["passed"] for s in frontend_quality_steps)
    else:
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
        "backend": {"backend_build": backend_build, "backend_test": backend_test, "gate_ok": backend_gate_ok},
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


def _qa_passes_gate(state: ProjectState) -> bool:
    """Return True when QA report meets the passing threshold."""
    qa_art = state.get_latest_artifact("qa_report")
    if qa_art is None or not isinstance(qa_art.content, dict):
        return False
    summary = qa_art.content.get("summary", {})
    if not isinstance(summary, dict):
        return False
    pass_rate = float(summary.get("test_pass_rate", 0.0))
    critical = int(summary.get("critical_bugs", 1))
    return pass_rate >= QA_FEEDBACK_PASS_THRESHOLD and critical == 0


def _qa_state_signature(state: ProjectState) -> str:
    """Return a stable fingerprint of the current QA report for anti-loop detection."""
    qa_art = state.get_latest_artifact("qa_report")
    if qa_art is None or not isinstance(qa_art.content, dict):
        return "qa:none"
    summary = qa_art.content.get("summary", {})
    pass_rate = summary.get("test_pass_rate", "na")
    critical = summary.get("critical_bugs", "na")
    major = summary.get("major_bugs", "na")
    bug_reports = qa_art.content.get("bug_reports", [])
    bug_ids = sorted(
        str(b.get("bug_id", "")).strip()
        for b in (bug_reports if isinstance(bug_reports, list) else [])
        if isinstance(b, dict) and b.get("bug_id")
    )
    return f"pass_rate={pass_rate}|critical={critical}|major={major}|bugs={','.join(bug_ids)}"


def _register_standard_agents(
    orchestrator: Orchestrator,
    *,
    llm_client: BaseLLMClient | None,
    llm_profile: LLMProfile | None,
    topology: str,
) -> None:
    orchestrator.register_agent(ProductManagerAgent("pm", _load_prompt("pm_agent"), [], llm_client=llm_client, llm_profile=llm_profile))
    orchestrator.register_agent(ArchitectAgent("architect", _load_prompt("architect_agent"), [], llm_client=llm_client, llm_profile=llm_profile))
    orchestrator.register_agent(BackendDeveloperAgent("backend_dev", _load_prompt("backend_dev_agent"), [], llm_client=llm_client, llm_profile=llm_profile))
    orchestrator.register_agent(FrontendDeveloperAgent("frontend_dev", _load_prompt("frontend_dev_agent"), [], llm_client=llm_client, llm_profile=llm_profile))
    orchestrator.register_agent(QAAgent("qa", _load_prompt("qa_agent"), [], llm_client=llm_client, llm_profile=llm_profile))
    orchestrator.register_agent(DevOpsAgent("devops", _load_prompt("devops_agent"), [], llm_client=llm_client, llm_profile=llm_profile))
    if topology == "hub_spoke":
        orchestrator.register_agent(CoordinatorAgent("coordinator", "Coordinator prompt", []))
    if topology == "peer_review":
        orchestrator.register_agent(PeerReviewerAgent("reviewer", "Reviewer prompt", []))


def _run_sequential_with_granularity(
    orchestrator: Orchestrator,
    granularity: str,
    *,
    work_item_module_map: dict[str, dict[str, Any]] | None = None,
) -> list[TurnResult]:
    registry = load_granularity_registry(GRANULARITY_CONFIG)
    profile = registry.get_profile(granularity)
    all_results: list[TurnResult] = []
    if profile.prelude_roles:
        all_results.extend(
            SequentialTopology(orchestrator=orchestrator, roles=profile.prelude_roles).run(
                f"[w12] prelude for {granularity}"
            )
        )
    if work_item_module_map:
        items_to_run = [wi for wi in profile.work_items if wi in work_item_module_map]
        if not items_to_run:
            items_to_run = profile.work_items[:1]
    else:
        items_to_run = profile.work_items[:1]
    for work_item in items_to_run:
        if work_item_module_map and work_item in work_item_module_map:
            item_cfg = work_item_module_map[work_item]
            orchestrator.state.module_config = item_cfg
            orchestrator.state.current_module_id = item_cfg.get("module_id")
        all_results.extend(
            SequentialTopology(orchestrator=orchestrator, roles=profile.per_item_roles).run(
                f"[w12] {granularity} item: {work_item}"
            )
        )

        # QA-driven rework loop: only when QA ran in per_item_roles
        if QA_FEEDBACK_ENABLED and "qa" in profile.per_item_roles:
            prev_signature: str | None = None
            stagnant_rounds = 0
            qa_loop_passed = _qa_passes_gate(orchestrator.state)
            for rework_round in range(1, QA_FEEDBACK_MAX_ROUNDS + 1):
                if _qa_passes_gate(orchestrator.state):
                    qa_loop_passed = True
                    break
                current_sig = _qa_state_signature(orchestrator.state)
                if prev_signature is not None and current_sig == prev_signature:
                    stagnant_rounds += 1
                else:
                    stagnant_rounds = 0
                if stagnant_rounds >= 1:
                    break  # Anti-loop guard
                prev_signature = current_sig
                orchestrator.state.increment_iteration()
                all_results.extend(
                    SequentialTopology(
                        orchestrator=orchestrator, roles=_QA_REWORK_ROLES
                    ).run(
                        f"[w12] qa-rework round {rework_round} for {work_item}"
                    )
                )
            # PM verdict when rework ends without QA passing
            if not qa_loop_passed and not _qa_passes_gate(orchestrator.state):
                pm_agent = orchestrator.agents.get("pm")
                if pm_agent is not None:
                    try:
                        pm_verdict_output = pm_agent.act_qa_verdict(orchestrator.state)  # type: ignore[attr-defined]
                        verdict_usage = pm_verdict_output.get("usage", {})
                        orchestrator.state.update_usage(
                            token_delta=int(verdict_usage.get("tokens", 0)),
                            api_call_delta=int(verdict_usage.get("api_calls", 0)),
                        )
                        all_results.append(
                            TurnResult(
                                agent_role="pm",
                                success=True,
                                artifacts_registered=["pm_qa_verdict:v1"],
                                messages_emitted=1,
                                usage_tokens=int(verdict_usage.get("tokens", 0)),
                                usage_api_calls=int(verdict_usage.get("api_calls", 0)),
                                updated_fields=[],
                            )
                        )
                    except Exception as exc:
                        all_results.append(
                            TurnResult(
                                agent_role="pm",
                                success=False,
                                error=f"pm_qa_verdict_error:{exc}",
                            )
                        )

    if profile.final_roles:
        all_results.extend(
            SequentialTopology(orchestrator=orchestrator, roles=profile.final_roles).run(
                f"[w12] finalization for {granularity}"
            )
        )
    return all_results


def _execute_case(
    *,
    topology: str,
    granularity: str,
    llm_client: BaseLLMClient | None,
    llm_profile: LLMProfile | None,
    project_config: dict[str, Any] | None = None,
    module_config: dict[str, Any] | None = None,
    work_item_module_map: dict[str, dict[str, Any]] | None = None,
) -> tuple[list[TurnResult], ProjectState]:
    orchestrator = Orchestrator()
    if project_config is not None:
        orchestrator.state.project_config = project_config
    if module_config is not None:
        orchestrator.state.module_config = module_config
        orchestrator.state.current_module_id = module_config.get("module_id")
    _register_standard_agents(orchestrator, llm_client=llm_client, llm_profile=llm_profile, topology=topology)
    if topology == "sequential":
        results = _run_sequential_with_granularity(orchestrator, granularity=granularity, work_item_module_map=work_item_module_map)
        return results, orchestrator.state
    if topology == "hub_spoke":
        return HubAndSpokeTopology(orchestrator=orchestrator, max_cycles=32).run(f"[w12] hub-spoke {granularity}"), orchestrator.state
    if topology == "peer_review":
        return PeerReviewTopology(orchestrator=orchestrator, max_revisions_per_target=1).run(f"[w12] peer-review {granularity}"), orchestrator.state
    if topology == "iterative_feedback":
        return IterativeFeedbackTopology(orchestrator=orchestrator, max_feedback_iterations=2, max_stagnant_rounds=1).run(f"[w12] iterative-feedback {granularity}"), orchestrator.state
    raise ValueError(f"Unsupported topology: {topology}")


def _promote_best_artifacts(state: ProjectState) -> None:
    qa_versions = state.artifact_store.artifact_versions.get("qa_report", [])
    if len(qa_versions) <= 1:
        return
    best_n: int | None = None
    best_score = -1.0
    for art in qa_versions:
        content = art.content if isinstance(art.content, dict) else {}
        summary = content.get("summary", {}) if isinstance(content.get("summary"), dict) else {}
        pass_rate = float(summary.get("test_pass_rate", 0.0))
        critical = int(summary.get("critical_bugs", 1))
        if critical == 0 and pass_rate > best_score:
            best_score = pass_rate
            best_n = art.version
    if best_n is None:
        for art in qa_versions:
            content = art.content if isinstance(art.content, dict) else {}
            summary = content.get("summary", {}) if isinstance(content.get("summary"), dict) else {}
            pass_rate = float(summary.get("test_pass_rate", 0.0))
            if pass_rate > best_score:
                best_score = pass_rate
                best_n = art.version
    latest_n = qa_versions[-1].version
    if best_n is None or best_n == latest_n:
        return
    for key in ("backend_code", "frontend_code"):
        best_art = state.artifact_store.get_version(key, best_n)
        if best_art is None:
            continue
        latest_art = state.artifact_store.get_latest(key)
        if latest_art is not None and latest_art.version == best_n:
            continue
        promoted = copy.deepcopy(best_art)
        promoted.metadata = dict(promoted.metadata or {})
        promoted.metadata["best_of_n_selection"] = True
        promoted.metadata["promoted_from_version"] = best_n
        promoted.metadata["best_qa_pass_rate"] = best_score
        state.artifact_store.register(key, promoted)
        setattr(state, key, copy.deepcopy(best_art.content))


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


def _load_config_file(path_text: Any) -> dict[str, Any] | None:
    text = str(path_text or "").strip()
    if not text:
        return None
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    if not candidate.exists():
        return None
    return _read_json(candidate)


def _select_best_config(case_results: list[CaseResult]) -> dict[str, Any]:
    """Select top topology+granularity combos by average composite Q score."""
    # Group by topology+granularity
    group_scores: dict[str, list[float]] = {}
    for cr in case_results:
        if not cr.success or not cr.q_metrics:
            continue
        key = f"{cr.topology}+{cr.granularity}"
        q = float(cr.q_metrics.get("composite_score", 0.0))
        group_scores.setdefault(key, []).append(q)

    ranking = []
    for combo, scores in group_scores.items():
        avg_q = sum(scores) / len(scores)
        topo, gran = combo.split("+", 1)
        ranking.append({
            "topology": topo,
            "granularity": gran,
            "avg_composite_score": round(avg_q, 4),
            "case_count": len(scores),
            "scores": [round(s, 4) for s in scores],
        })
    ranking.sort(key=lambda x: x["avg_composite_score"], reverse=True)

    best = ranking[0] if ranking else {}
    return {
        "best_config": best,
        "ranking": ranking,
        "note": "Best config selected for Week 14 production deployment.",
    }


def run_experiment() -> tuple[int, list[CheckResult], Path]:
    config = _read_json(PILOT_CONFIG)
    llm_profiles_path = PROJECT_ROOT / config["llm_profiles_path"]
    llm_profile_name = str(config.get("llm_profile", "")).strip()
    allow_network_llm = bool(config.get("allow_network_llm", False))
    max_attempts = int(config.get("max_attempts_per_case", 1))
    disable_llm_on_retry_config = bool(config.get("disable_llm_on_retry", True))
    disable_llm_on_retry = disable_llm_on_retry_config and not REQUIRE_LLM_CODE_OUTPUTS
    cases = config.get("cases", [])

    project_config = _load_config_file(config.get("project_config"))
    default_module_config = _load_config_file(config.get("module_config"))

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

    materializer = ArtifactMaterializer(GENERATED_WORKSPACES_DIR)

    # Load ground truth for Q score calculation
    ground_truth_payload: dict[str, Any] = {}
    if GROUND_TRUTH_PATH.exists():
        ground_truth_payload = _read_json(GROUND_TRUTH_PATH)

    registry = load_llm_registry(llm_profiles_path)
    primary_client, primary_profile, llm_reason = create_llm_client(registry, profile_name=llm_profile_name)
    if not allow_network_llm and primary_profile.provider != "mock":
        primary_client = None
        llm_reason = f"network llm disabled by pilot config (provider={primary_profile.provider})"

    checks: list[CheckResult] = []
    checks.append(CheckResult(name="experiment_cases_non_empty", passed=isinstance(cases, list) and len(cases) > 0, details=f"case_count={len(cases) if isinstance(cases, list) else 'invalid'}"))
    checks.append(CheckResult(name="llm_profile_loaded", passed=True, details=f"profile={primary_profile.name}, provider={primary_profile.provider}, llm_available={primary_client is not None}, reason={llm_reason}"))
    checks.append(CheckResult(name="hard_gates_config", passed=True, details=f"require_llm_code_outputs={REQUIRE_LLM_CODE_OUTPUTS}, enforce_build_test_gate={ENFORCE_BUILD_TEST_GATE}, materialization_mode={materialization_mode}"))

    case_results: list[CaseResult] = []
    failure_buckets: dict[str, int] = {}
    total_attempt_count = 0
    llm_gate_pass_count = 0
    materialization_pass_count = 0
    build_gate_pass_count = 0
    materialization_executed_count = 0
    all_run_metrics: list[RunMetrics] = []

    if not isinstance(cases, list):
        raise ValueError("cases must be a list")

    for case in cases:
        if not isinstance(case, dict):
            continue

        case_name = str(case.get("name", "")).strip() or "unnamed_case"
        topology = str(case.get("topology", "")).strip().lower()
        granularity = str(case.get("granularity", "module")).strip().lower()

        case_module_config = _load_config_file(case.get("module_config")) or default_module_config

        raw_wimc = case.get("work_item_module_configs")
        work_item_module_map: dict[str, dict[str, Any]] | None = None
        if isinstance(raw_wimc, dict):
            work_item_module_map = {}
            for wi, cfg_path in raw_wimc.items():
                cfg = _load_config_file(cfg_path)
                if cfg is not None:
                    work_item_module_map[str(wi)] = cfg

        attempts: list[CaseAttempt] = []
        final_error: str | None = None
        final_state_snapshot = ""
        case_q_metrics: dict[str, Any] = {}

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
                    project_config=project_config,
                    module_config=case_module_config,
                    work_item_module_map=work_item_module_map,
                )
                _promote_best_artifacts(state)
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
                    "backend_template_used": _repo_rel(backend_template) if backend_template else None,
                    "frontend_template_used": _repo_rel(frontend_template) if frontend_template else None,
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
                    build_test_gate_passed, build_test_gate = _evaluate_build_test_gate(validation_result)
                    if build_test_gate_passed:
                        build_gate_pass_count += 1
                else:
                    build_test_gate = {"passed": True, "disabled": True, "validation": validation_result}

                # Delete workspace after validation to free disk space
                # Generated code is preserved in the state JSON snapshot
                shutil.rmtree(materialized.workspace_root, ignore_errors=True)

            except Exception as exc:
                materialization_report = {"passed": False, "error": str(exc)}
                build_test_gate_passed = False
                build_test_gate = {"passed": False, "error": f"materialize_or_validate_error:{exc}"}

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

            # Compute Q score for this attempt
            if run_ok and llm_gate_passed:
                try:
                    run_metrics = evaluate_run(
                        run_name=case_name,
                        state_payload=state_payload,
                        ground_truth_payload=ground_truth_payload,
                        state_path=_repo_rel(state_path),
                    )
                    all_run_metrics.append(run_metrics)
                    case_q_metrics = run_metrics.to_dict()
                except Exception:
                    case_q_metrics = {}

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
                q_metrics=case_q_metrics,
            )
        )

    # Normalize efficiency and apply composite scores across all runs
    if all_run_metrics:
        apply_composite_scores(all_run_metrics)
        # Update q_metrics in case_results with final composite scores
        metrics_by_name = {m.run_name: m for m in all_run_metrics}
        for cr in case_results:
            if cr.name in metrics_by_name:
                cr.q_metrics = metrics_by_name[cr.name].to_dict()

    success_count = sum(1 for item in case_results if item.success)
    success_rate = (success_count / len(case_results)) if case_results else 0.0
    retry_count = sum(max(len(item.attempts) - 1, 0) for item in case_results)

    checks.append(CheckResult(name="experiment_success_rate", passed=success_rate >= 0.75, details=f"success_count={success_count}, total={len(case_results)}, success_rate={success_rate:.4f}"))
    checks.append(CheckResult(name="experiment_retry_budget", passed=all(len(item.attempts) <= max_attempts for item in case_results), details=f"max_attempts={max_attempts}, total_retries={retry_count}"))
    checks.append(CheckResult(name="failure_buckets_recorded", passed=True, details=f"failure_bucket_count={len(failure_buckets)}"))
    checks.append(CheckResult(name="materialization_executed", passed=materialization_executed_count == total_attempt_count and total_attempt_count > 0, details=f"materialization_executed_count={materialization_executed_count}, total_attempt_count={total_attempt_count}"))
    checks.append(CheckResult(name="llm_output_gate_observed", passed=llm_gate_pass_count > 0, details=f"llm_gate_pass_count={llm_gate_pass_count}, total_attempt_count={total_attempt_count}"))
    checks.append(CheckResult(name="build_test_gate_observed", passed=build_gate_pass_count > 0, details=f"build_gate_pass_count={build_gate_pass_count}, total_attempt_count={total_attempt_count}"))
    checks.append(CheckResult(name="q_scores_computed", passed=len(all_run_metrics) > 0, details=f"runs_with_q_score={len(all_run_metrics)}, total_cases={len(case_results)}"))

    best_config_selection = _select_best_config(case_results)

    status = "success" if all(item.passed for item in checks) else "failed"
    report_path = OUTPUT_DIR / "week12_experiment_report.json"
    write_json(
        report_path,
        {
            "status": status,
            "experiment_config": _repo_rel(PILOT_CONFIG),
            "llm_profile": {
                "name": primary_profile.name,
                "provider": primary_profile.provider,
                "model": primary_profile.model,
                "client_available": primary_client is not None,
            },
            "summary": {
                "case_count": len(case_results),
                "success_count": success_count,
                "success_rate": success_rate,
                "retry_count": retry_count,
                "total_attempt_count": total_attempt_count,
                "llm_gate_pass_count": llm_gate_pass_count,
                "build_gate_pass_count": build_gate_pass_count,
                "runs_with_q_score": len(all_run_metrics),
            },
            "best_config_selection": best_config_selection,
            "failure_buckets": failure_buckets,
            "cases": [
                {
                    "name": cr.name,
                    "topology": cr.topology,
                    "granularity": cr.granularity,
                    "success": cr.success,
                    "q_metrics": cr.q_metrics,
                    "attempts": [asdict(att) for att in cr.attempts],
                    "final_error": cr.final_error,
                    "final_state_snapshot": cr.final_state_snapshot,
                }
                for cr in case_results
            ],
            "checks": [asdict(check) for check in checks],
        },
    )
    return (0 if status == "success" else 1), checks, report_path


def main() -> int:
    code, checks, report_path = run_experiment()
    for check in checks:
        marker = "PASS" if check.passed else "FAIL"
        print(f"[{marker}] {check.name}: {check.details}")
    print(f"Experiment report: {report_path}")
    return code


if __name__ == "__main__":
    sys.exit(main())
