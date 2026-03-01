from __future__ import annotations

import unittest

from evaluation.week9_pilot_experiments import (
    _evaluate_build_test_gate,
    _evaluate_llm_output_gate,
)


def _artifact(source: str, code_bundle: dict[str, str]) -> dict[str, object]:
    return {
        "content": {
            "code_bundle": code_bundle,
        },
        "metadata": {
            "generation": {
                "source": source,
            }
        },
    }


class Week9PilotHardGateTests(unittest.TestCase):
    def test_llm_output_gate_passes_for_backend_and_frontend_llm_bundles(self) -> None:
        state_payload = {
            "artifact_store": {
                "backend_code": [_artifact("llm", {"src/A.java": "class A {}"})],
                "frontend_code": [_artifact("llm", {"src/A.js": "export const a = 1;"})],
            }
        }

        passed, details = _evaluate_llm_output_gate(state_payload)

        self.assertTrue(passed)
        self.assertTrue(details["backend"]["passed"])
        self.assertTrue(details["frontend"]["passed"])

    def test_llm_output_gate_fails_when_frontend_uses_fallback(self) -> None:
        state_payload = {
            "artifact_store": {
                "backend_code": [_artifact("llm", {"src/A.java": "class A {}"})],
                "frontend_code": [_artifact("rule_fallback", {"src/A.js": "fallback"})],
            }
        }

        passed, details = _evaluate_llm_output_gate(state_payload)

        self.assertFalse(passed)
        self.assertTrue(details["backend"]["passed"])
        self.assertFalse(details["frontend"]["passed"])

    def test_build_test_gate_passes_when_required_steps_pass(self) -> None:
        validation = {
            "backend": [
                {"name": "backend_build", "executed": True, "passed": True},
                {"name": "backend_test", "executed": True, "passed": True},
            ],
            "frontend": [
                {"name": "frontend_build", "executed": True, "passed": True},
                {"name": "frontend_test", "executed": True, "passed": True},
                {
                    "name": "frontend_lint",
                    "executed": False,
                    "passed": False,
                    "skipped_reason": "npm lint script missing",
                },
            ],
            "scores": {"build_test_pass_rate": 1.0},
        }

        passed, details = _evaluate_build_test_gate(validation)

        self.assertTrue(passed)
        self.assertTrue(details["backend"]["gate_ok"])
        self.assertTrue(details["frontend"]["gate_ok"])

    def test_build_test_gate_fails_when_no_frontend_quality_step_executed(self) -> None:
        validation = {
            "backend": [
                {"name": "backend_build", "executed": True, "passed": True},
                {"name": "backend_test", "executed": True, "passed": True},
            ],
            "frontend": [
                {"name": "frontend_build", "executed": True, "passed": True},
                {"name": "frontend_test", "executed": False, "passed": False},
                {"name": "frontend_lint", "executed": False, "passed": False},
            ],
            "scores": {"build_test_pass_rate": 0.5},
        }

        passed, details = _evaluate_build_test_gate(validation)

        self.assertFalse(passed)
        self.assertFalse(details["frontend"]["quality_gate_ok"])


if __name__ == "__main__":
    unittest.main()
