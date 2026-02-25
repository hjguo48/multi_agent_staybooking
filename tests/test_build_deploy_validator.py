from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.build_deploy_validator import BuildDeployValidator


class BuildDeployValidatorTests(unittest.TestCase):
    def test_validator_handles_missing_build_tooling_and_scores_deploy_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            backend_root = root / "backend"
            frontend_root = root / "frontend"
            backend_root.mkdir(parents=True, exist_ok=True)
            frontend_root.mkdir(parents=True, exist_ok=True)

            validator = BuildDeployValidator(
                backend_root=backend_root,
                frontend_root=frontend_root,
                timeout_seconds=5.0,
            )
            state_payload = {
                "artifact_store": {
                    "deployment": [
                        {
                            "content": {
                                "status": "success",
                                "health_checks": {"backend": 200, "frontend": 200},
                            }
                        }
                    ]
                }
            }

            result = validator.run(state_payload)
            self.assertIn("backend", result)
            self.assertIn("frontend", result)
            self.assertIn("deploy", result)
            self.assertEqual(0, result["scores"]["build_test_executed_steps"])
            self.assertEqual(1.0, result["scores"]["deploy_pass_rate"])
            self.assertEqual(0, result["scores"]["deploy_real_executed_steps"])

    def test_validator_marks_deploy_health_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            backend_root = root / "backend"
            frontend_root = root / "frontend"
            backend_root.mkdir(parents=True, exist_ok=True)
            frontend_root.mkdir(parents=True, exist_ok=True)

            validator = BuildDeployValidator(
                backend_root=backend_root,
                frontend_root=frontend_root,
                timeout_seconds=5.0,
            )
            state_payload = {
                "artifact_store": {
                    "deployment": [
                        {
                            "content": {
                                "status": "failed",
                                "health_checks": {"backend": 500},
                            }
                        }
                    ]
                }
            }

            result = validator.run(state_payload)
            self.assertEqual(0.0, result["scores"]["deploy_pass_rate"])


if __name__ == "__main__":
    unittest.main()
