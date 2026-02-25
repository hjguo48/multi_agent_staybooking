"""Run build/test/deploy checks on materialized workspaces."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .code_executor import CodeExecutor


def _tail(text: str | None, max_chars: int = 1200) -> str:
    if text is None:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


@dataclass
class StepCheck:
    name: str
    executed: bool
    passed: bool
    command: list[str]
    returncode: int | None
    timed_out: bool
    skipped_reason: str | None
    stdout_tail: str
    stderr_tail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "executed": self.executed,
            "passed": self.passed,
            "command": self.command,
            "returncode": self.returncode,
            "timed_out": self.timed_out,
            "skipped_reason": self.skipped_reason,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


def _skipped(name: str, reason: str) -> StepCheck:
    return StepCheck(
        name=name,
        executed=False,
        passed=False,
        command=[],
        returncode=None,
        timed_out=False,
        skipped_reason=reason,
        stdout_tail="",
        stderr_tail="",
    )


def _run_step(
    *,
    name: str,
    executor: CodeExecutor,
    command: list[str],
    timeout_seconds: float,
) -> StepCheck:
    result = executor.run(command, timeout_seconds=timeout_seconds)
    return StepCheck(
        name=name,
        executed=True,
        passed=result.returncode == 0 and not result.timed_out,
        command=command,
        returncode=result.returncode,
        timed_out=result.timed_out,
        skipped_reason=None,
        stdout_tail=_tail(result.stdout),
        stderr_tail=_tail(result.stderr),
    )


def _compute_pass_rate(checks: list[StepCheck]) -> tuple[float, int]:
    executed = [check for check in checks if check.executed]
    if not executed:
        return 0.0, 0
    passed = sum(1 for check in executed if check.passed)
    return passed / len(executed), len(executed)


def _compute_real_pass_rate(checks: list[StepCheck]) -> tuple[float, int]:
    executed_real = [check for check in checks if check.executed and bool(check.command)]
    if not executed_real:
        return 0.0, 0
    passed = sum(1 for check in executed_real if check.passed)
    return passed / len(executed_real), len(executed_real)


class BuildDeployValidator:
    """Validate build/test/deploy signals for a workspace."""

    def __init__(
        self,
        *,
        backend_root: Path,
        frontend_root: Path,
        timeout_seconds: float = 600.0,
        run_backend_tests: bool = True,
        run_frontend_checks: bool = True,
        run_frontend_tests: bool = False,
    ) -> None:
        self.backend_root = backend_root.resolve()
        self.frontend_root = frontend_root.resolve()
        self.timeout_seconds = timeout_seconds
        self.run_backend_tests = run_backend_tests
        self.run_frontend_checks = run_frontend_checks
        self.run_frontend_tests = run_frontend_tests

    def _backend_checks(self) -> list[StepCheck]:
        checks: list[StepCheck] = []
        if not self.backend_root.exists():
            return [_skipped("backend_root", "backend workspace missing")]

        gradlew_bat = self.backend_root / "gradlew.bat"
        gradlew = self.backend_root / "gradlew"
        executor = CodeExecutor(self.backend_root)

        if gradlew_bat.exists():
            checks.append(
                _run_step(
                    name="backend_build",
                    executor=executor,
                    command=["cmd", "/c", "gradlew.bat", "build", "-x", "test", "--no-daemon"],
                    timeout_seconds=self.timeout_seconds,
                )
            )
            if self.run_backend_tests:
                checks.append(
                    _run_step(
                        name="backend_test",
                        executor=executor,
                        command=["cmd", "/c", "gradlew.bat", "test", "--no-daemon"],
                        timeout_seconds=self.timeout_seconds,
                    )
                )
            else:
                checks.append(_skipped("backend_test", "disabled by validator config"))
            return checks

        if gradlew.exists():
            checks.append(
                _run_step(
                    name="backend_build",
                    executor=executor,
                    command=["./gradlew", "build", "-x", "test", "--no-daemon"],
                    timeout_seconds=self.timeout_seconds,
                )
            )
            if self.run_backend_tests:
                checks.append(
                    _run_step(
                        name="backend_test",
                        executor=executor,
                        command=["./gradlew", "test", "--no-daemon"],
                        timeout_seconds=self.timeout_seconds,
                    )
                )
            else:
                checks.append(_skipped("backend_test", "disabled by validator config"))
            return checks

        return [_skipped("backend_build", "no gradle wrapper found")]

    def _frontend_checks(self) -> list[StepCheck]:
        checks: list[StepCheck] = []
        if not self.run_frontend_checks:
            return [_skipped("frontend_build", "disabled by validator config")]
        if not self.frontend_root.exists():
            return [_skipped("frontend_root", "frontend workspace missing")]

        package_json_path = self.frontend_root / "package.json"
        if not package_json_path.exists():
            return [_skipped("frontend_build", "package.json missing")]

        npm_bin = shutil.which("npm.cmd") or shutil.which("npm")
        if not npm_bin:
            return [_skipped("frontend_build", "npm not found in PATH")]

        package_payload = json.loads(package_json_path.read_text(encoding="utf-8"))
        scripts = package_payload.get("scripts", {})
        if not isinstance(scripts, dict):
            scripts = {}

        executor = CodeExecutor(self.frontend_root)
        node_modules_dir = self.frontend_root / "node_modules"
        if not node_modules_dir.exists():
            checks.append(
                _run_step(
                    name="frontend_install",
                    executor=executor,
                    command=[npm_bin, "ci", "--no-audit", "--no-fund"],
                    timeout_seconds=self.timeout_seconds,
                )
            )
            if not checks[-1].passed:
                return checks
        else:
            checks.append(
                StepCheck(
                    name="frontend_install",
                    executed=False,
                    passed=True,
                    command=[],
                    returncode=None,
                    timed_out=False,
                    skipped_reason="node_modules already exists",
                    stdout_tail="",
                    stderr_tail="",
                )
            )

        if "build" in scripts:
            checks.append(
                _run_step(
                    name="frontend_build",
                    executor=executor,
                    command=[npm_bin, "run", "build"],
                    timeout_seconds=self.timeout_seconds,
                )
            )
        else:
            checks.append(_skipped("frontend_build", "npm build script missing"))

        if "test" in scripts and self.run_frontend_tests:
            checks.append(
                _run_step(
                    name="frontend_test",
                    executor=executor,
                    command=[npm_bin, "run", "test", "--", "--watch=false", "--passWithNoTests"],
                    timeout_seconds=self.timeout_seconds,
                )
            )
        elif "test" in scripts and not self.run_frontend_tests:
            checks.append(_skipped("frontend_test", "disabled by validator config"))
        else:
            checks.append(_skipped("frontend_test", "npm test script missing"))

        return checks

    def _deploy_checks(self, state_payload: dict[str, Any]) -> list[StepCheck]:
        checks: list[StepCheck] = []

        docker_bin = shutil.which("docker")
        compose_file = self.backend_root / "docker-compose.yml"
        if docker_bin and compose_file.exists():
            executor = CodeExecutor(self.backend_root)
            checks.append(
                _run_step(
                    name="deploy_docker_compose_config",
                    executor=executor,
                    command=[docker_bin, "compose", "-f", compose_file.as_posix(), "config"],
                    timeout_seconds=min(self.timeout_seconds, 120.0),
                )
            )
        else:
            reason = "docker missing" if not docker_bin else "docker-compose.yml missing"
            checks.append(_skipped("deploy_docker_compose_config", reason))

        deployment_versions = state_payload.get("artifact_store", {}).get("deployment", [])
        deployment_content: dict[str, Any] = {}
        if isinstance(deployment_versions, list) and deployment_versions:
            latest = deployment_versions[-1]
            if isinstance(latest, dict) and isinstance(latest.get("content"), dict):
                deployment_content = latest["content"]

        status_ok = str(deployment_content.get("status", "")).strip().lower() == "success"
        health_checks = deployment_content.get("health_checks", {})
        health_ok = False
        if isinstance(health_checks, dict) and health_checks:
            health_ok = all(int(code) == 200 for code in health_checks.values())

        checks.append(
            StepCheck(
                name="deploy_artifact_health",
                executed=True,
                passed=status_ok and health_ok,
                command=[],
                returncode=0 if (status_ok and health_ok) else 1,
                timed_out=False,
                skipped_reason=None,
                stdout_tail=f"status={deployment_content.get('status')}, health={health_checks}",
                stderr_tail="",
            )
        )
        return checks

    def run(self, state_payload: dict[str, Any]) -> dict[str, Any]:
        backend_checks = self._backend_checks()
        frontend_checks = self._frontend_checks()
        deploy_checks = self._deploy_checks(state_payload)

        build_checks = backend_checks + frontend_checks
        build_pass_rate, build_executed_count = _compute_pass_rate(build_checks)
        build_real_pass_rate, build_real_executed_count = _compute_real_pass_rate(build_checks)
        deploy_pass_rate, deploy_executed_count = _compute_pass_rate(deploy_checks)
        deploy_real_pass_rate, deploy_real_executed_count = _compute_real_pass_rate(deploy_checks)

        return {
            "backend": [item.to_dict() for item in backend_checks],
            "frontend": [item.to_dict() for item in frontend_checks],
            "deploy": [item.to_dict() for item in deploy_checks],
            "scores": {
                "build_test_pass_rate": build_pass_rate,
                "build_test_executed_steps": build_executed_count,
                "build_real_pass_rate": build_real_pass_rate,
                "build_real_executed_steps": build_real_executed_count,
                "deploy_pass_rate": deploy_pass_rate,
                "deploy_executed_steps": deploy_executed_count,
                "deploy_real_pass_rate": deploy_real_pass_rate,
                "deploy_real_executed_steps": deploy_real_executed_count,
            },
        }
