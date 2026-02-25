"""Week 8 evaluation metric calculations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ScoreWeights:
    """Composite score weights from the methodology."""

    rcr: float = 0.30
    code_quality: float = 0.20
    arch_score: float = 0.20
    deploy_score: float = 0.20
    efficiency: float = 0.10


@dataclass
class RunMetrics:
    """Evaluated metrics for one run."""

    run_name: str
    state_path: str
    requirement_coverage: float = 0.0
    api_coverage: float = 0.0
    entity_coverage: float = 0.0
    rcr: float = 0.0
    code_quality: float = 0.0
    arch_score: float = 0.0
    deploy_score: float = 0.0
    total_tokens: int = 0
    total_api_calls: int = 0
    iteration_count: int = 0
    wall_clock_seconds: float = 0.0
    norm_efficiency: float = 0.0
    composite_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_name": self.run_name,
            "state_path": self.state_path,
            "requirement_coverage": self.requirement_coverage,
            "api_coverage": self.api_coverage,
            "entity_coverage": self.entity_coverage,
            "rcr": self.rcr,
            "code_quality": self.code_quality,
            "arch_score": self.arch_score,
            "deploy_score": self.deploy_score,
            "total_tokens": self.total_tokens,
            "total_api_calls": self.total_api_calls,
            "iteration_count": self.iteration_count,
            "wall_clock_seconds": self.wall_clock_seconds,
            "norm_efficiency": self.norm_efficiency,
            "composite_score": self.composite_score,
            "percentages": {
                "rcr": self.rcr * 100.0,
                "code_quality": self.code_quality * 100.0,
                "arch_score": self.arch_score * 100.0,
                "deploy_score": self.deploy_score * 100.0,
                "composite_score": self.composite_score * 100.0,
            },
        }


_PATH_PARAM_RE = re.compile(r"\$\{[^}]+\}|\{[^}]+\}")


def _clamp_01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _normalize_path(path: str) -> str:
    raw = str(path).strip()
    if not raw:
        return ""
    if not raw.startswith("/"):
        raw = "/" + raw
    raw = raw.split("?", 1)[0]

    segments: list[str] = []
    for segment in raw.split("/"):
        segment = segment.strip()
        if not segment:
            continue
        normalized = _PATH_PARAM_RE.sub("{}", segment).lower()
        segments.append(normalized)
    return "/" + "/".join(segments)


def _normalize_entity(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", str(name).lower())
    if normalized.endswith("entity"):
        normalized = normalized[: -len("entity")]
    if normalized.endswith("ies"):
        normalized = normalized[:-3] + "y"
    elif normalized.endswith("s") and not normalized.endswith("ss"):
        normalized = normalized[:-1]
    return normalized


def _latest_artifact_content(state_payload: dict[str, Any], key: str) -> dict[str, Any]:
    artifact_store = state_payload.get("artifact_store", {})
    versions = artifact_store.get(key, [])
    if not versions:
        return {}
    latest = versions[-1]
    content = latest.get("content", {})
    if isinstance(content, dict):
        return content
    return {}


def _status_score(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return _clamp_01(float(value))
    text = str(value).strip().lower()
    if not text:
        return 0.0
    if any(token in text for token in ("pass", "success", "ok", "healthy")):
        return 1.0
    if "pending" in text:
        return 0.5
    if any(token in text for token in ("fail", "error", "critical", "broken")):
        return 0.0
    return 0.0


def _wall_clock_seconds(state_payload: dict[str, Any]) -> float:
    created = state_payload.get("created_at")
    updated = state_payload.get("updated_at")
    if not created or not updated:
        return 0.0
    try:
        delta = datetime.fromisoformat(str(updated)) - datetime.fromisoformat(str(created))
    except ValueError:
        return 0.0
    return max(delta.total_seconds(), 0.0)


def evaluate_run(
    run_name: str,
    state_payload: dict[str, Any],
    ground_truth_payload: dict[str, Any],
    *,
    state_path: str = "",
) -> RunMetrics:
    """Evaluate one run against ground truth and return metrics."""

    requirements = _latest_artifact_content(state_payload, "requirements")
    architecture = _latest_artifact_content(state_payload, "architecture")
    backend_code = _latest_artifact_content(state_payload, "backend_code")
    frontend_code = _latest_artifact_content(state_payload, "frontend_code")
    qa_report = _latest_artifact_content(state_payload, "qa_report")
    deployment = _latest_artifact_content(state_payload, "deployment")

    functional_requirements = requirements.get("functional_requirements", [])
    requirement_ids = {
        str(item.get("id", "")).strip()
        for item in functional_requirements
        if isinstance(item, dict) and str(item.get("id", "")).strip()
    }
    coverage_map = qa_report.get("coverage_map", {})
    covered_requirement_ids = {
        str(key).strip()
        for key in coverage_map.keys()
        if str(key).strip()
    }
    requirement_coverage = (
        len(requirement_ids & covered_requirement_ids) / len(requirement_ids)
        if requirement_ids
        else 0.0
    )

    generated_api_paths: set[str] = set()
    for contract in requirements.get("api_contracts", []):
        if isinstance(contract, dict):
            endpoint = _normalize_path(str(contract.get("endpoint", "")))
            if endpoint:
                generated_api_paths.add(endpoint)
    openapi_paths = architecture.get("openapi_spec", {}).get("paths", {})
    if isinstance(openapi_paths, dict):
        for path in openapi_paths.keys():
            normalized = _normalize_path(str(path))
            if normalized:
                generated_api_paths.add(normalized)

    gt_backend = ground_truth_payload.get("backend", {})
    gt_endpoints = {
        _normalize_path(str(entry.get("full_path", "")))
        for entry in gt_backend.get("endpoints", [])
        if isinstance(entry, dict)
    }
    gt_endpoints.discard("")
    api_coverage = (
        len(generated_api_paths & gt_endpoints) / len(gt_endpoints)
        if gt_endpoints
        else 0.0
    )

    generated_entities: set[str] = set()
    data_entities = requirements.get("data_model", {}).get("entities", [])
    for entity in data_entities:
        normalized = _normalize_entity(str(entity))
        if normalized:
            generated_entities.add(normalized)
    tables = architecture.get("database_schema", {}).get("tables", [])
    for table in tables:
        if isinstance(table, dict):
            normalized = _normalize_entity(str(table.get("name", "")))
            if normalized:
                generated_entities.add(normalized)
    gt_entities = {
        _normalize_entity(str(entry.get("class", "")))
        for entry in gt_backend.get("entities", [])
        if isinstance(entry, dict)
    }
    gt_entities.discard("")
    entity_coverage = (
        len(generated_entities & gt_entities) / len(gt_entities)
        if gt_entities
        else 0.0
    )

    rcr = _mean([requirement_coverage, api_coverage, entity_coverage])

    backend_compile = _status_score(backend_code.get("build_notes", {}).get("compile_status"))
    frontend_build = _status_score(frontend_code.get("build_notes", {}).get("build_status"))
    qa_summary = qa_report.get("summary", {})
    test_pass_rate = _clamp_01(_safe_float(qa_summary.get("test_pass_rate"), default=0.0))
    critical_bugs = _safe_int(qa_summary.get("critical_bugs"), default=0)
    major_bugs = _safe_int(qa_summary.get("major_bugs"), default=0)
    bug_penalty = min(1.0, critical_bugs * 0.40 + major_bugs * 0.15)
    bug_quality = 1.0 - bug_penalty
    code_quality = _clamp_01(
        0.30 * backend_compile
        + 0.25 * frontend_build
        + 0.25 * test_pass_rate
        + 0.20 * bug_quality
    )

    required_arch_sections = [
        "tech_stack",
        "modules",
        "database_schema",
        "openapi_spec",
        "deployment",
    ]
    present_sections = sum(
        1
        for key in required_arch_sections
        if architecture.get(key) is not None
    )
    section_score = present_sections / len(required_arch_sections)
    module_count = len(architecture.get("modules", []))
    module_depth_score = min(module_count / 4.0, 1.0)
    arch_score = _clamp_01(
        0.35 * section_score
        + 0.25 * module_depth_score
        + 0.20 * api_coverage
        + 0.20 * entity_coverage
    )

    deployment_status_score = _status_score(deployment.get("status"))
    health_checks = deployment.get("health_checks", {})
    health_values = list(health_checks.values()) if isinstance(health_checks, dict) else []
    health_score = (
        sum(1 for code in health_values if _safe_int(code, default=0) == 200) / len(health_values)
        if health_values
        else 0.0
    )
    access_urls = deployment.get("access_urls", {})
    access_score = 0.0
    if isinstance(access_urls, dict):
        flags = [
            bool(access_urls.get("backend")),
            bool(access_urls.get("frontend")),
        ]
        access_score = sum(1 for flag in flags if flag) / len(flags)
    build_success_score = _mean([backend_compile, frontend_build])
    deploy_score = _clamp_01(
        _mean(
            [
                build_success_score,
                test_pass_rate,
                deployment_status_score,
                health_score,
                access_score,
            ]
        )
    )

    return RunMetrics(
        run_name=run_name,
        state_path=state_path,
        requirement_coverage=_clamp_01(requirement_coverage),
        api_coverage=_clamp_01(api_coverage),
        entity_coverage=_clamp_01(entity_coverage),
        rcr=_clamp_01(rcr),
        code_quality=code_quality,
        arch_score=arch_score,
        deploy_score=deploy_score,
        total_tokens=_safe_int(state_payload.get("total_tokens"), default=0),
        total_api_calls=_safe_int(state_payload.get("total_api_calls"), default=0),
        iteration_count=_safe_int(state_payload.get("iteration"), default=0),
        wall_clock_seconds=_wall_clock_seconds(state_payload),
    )


def normalize_efficiency(run_metrics: list[RunMetrics]) -> None:
    """Normalize token usage across all runs to [0,1] (lower is better)."""

    if not run_metrics:
        return
    token_values = [max(metric.total_tokens, 0) for metric in run_metrics]
    min_tokens = min(token_values)
    max_tokens = max(token_values)
    if max_tokens == min_tokens:
        for metric in run_metrics:
            metric.norm_efficiency = 0.0
        return

    for metric in run_metrics:
        metric.norm_efficiency = _clamp_01(
            (metric.total_tokens - min_tokens) / (max_tokens - min_tokens)
        )


def compute_composite_score(
    metric: RunMetrics,
    weights: ScoreWeights | None = None,
) -> float:
    """Compute methodology composite score Q for one run."""

    w = weights or ScoreWeights()
    quality_term = (
        w.rcr * metric.rcr
        + w.code_quality * metric.code_quality
        + w.arch_score * metric.arch_score
        + w.deploy_score * metric.deploy_score
    )
    efficiency_term = w.efficiency * (1.0 - _clamp_01(metric.norm_efficiency))
    return _clamp_01(quality_term + efficiency_term)


def apply_composite_scores(
    run_metrics: list[RunMetrics],
    weights: ScoreWeights | None = None,
) -> None:
    """Normalize efficiency and assign composite scores in-place."""

    normalize_efficiency(run_metrics)
    for metric in run_metrics:
        metric.composite_score = compute_composite_score(metric, weights=weights)
