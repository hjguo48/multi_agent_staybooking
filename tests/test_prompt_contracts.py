from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from evaluation.validate_prompt_contracts import run_validation


class PromptContractTests(unittest.TestCase):
    def test_prompt_contracts_pass(self) -> None:
        contract_file = Path("configs/prompt_contracts.json").resolve()
        code, report = run_validation(contract_file)
        self.assertEqual(0, code)
        self.assertEqual("success", report["status"])
        self.assertGreater(report["total_checks"], 0)

    def test_missing_token_should_fail(self) -> None:
        contract_file = Path("configs/prompt_contracts.json").resolve()
        original_text = contract_file.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_contract = Path(tmpdir) / "contract.json"
            temp_contract.write_text(original_text, encoding="utf-8")

            broken = temp_contract.read_text(encoding="utf-8").replace(
                "Output MUST be valid JSON",
                "Output JSON maybe valid",
                1,
            )
            temp_contract.write_text(broken, encoding="utf-8")

            code, report = run_validation(temp_contract)
            self.assertEqual(1, code)
            self.assertEqual("failed", report["status"])
            self.assertGreater(report["failed_checks"], 0)


if __name__ == "__main__":
    unittest.main()
