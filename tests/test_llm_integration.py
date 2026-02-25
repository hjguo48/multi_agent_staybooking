from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agents import ProductManagerAgent
from core.project_state import ProjectState
from llm import LLMProfile, MockLLMClient, create_llm_client, load_llm_registry


class LLMIntegrationTests(unittest.TestCase):
    def test_factory_returns_none_when_api_key_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "llm_profiles.json"
            config_path.write_text(
                json.dumps(
                    {
                        "default": "claude_test",
                        "profiles": {
                            "claude_test": {
                                "provider": "anthropic",
                                "model": "claude-sonnet-4-20250514",
                                "enabled": True,
                                "api_key_env": "UNITTEST_MISSING_ANTHROPIC_KEY",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            registry = load_llm_registry(config_path)
            client, profile, reason = create_llm_client(registry)
            self.assertIsNone(client)
            self.assertEqual("claude_test", profile.name)
            self.assertIn("missing env var", reason)

    def test_pm_agent_uses_llm_json_when_valid(self) -> None:
        llm_profile = LLMProfile(
            name="mock_json",
            provider="mock",
            model="mock-json-model",
            enabled=True,
            temperature=0.0,
            max_output_tokens=512,
        )
        llm_client = MockLLMClient(
            response_text=json.dumps(
                {
                    "project_name": "StayBooking",
                    "functional_requirements": [],
                    "non_functional_requirements": [],
                    "api_contracts": [],
                    "data_model": {"entities": [], "relationships": []},
                }
            ),
            input_tokens=12,
            output_tokens=8,
        )
        agent = ProductManagerAgent(
            role="pm",
            system_prompt="pm prompt",
            tools=[],
            llm_client=llm_client,
            llm_profile=llm_profile,
        )

        result = agent.act(ProjectState())
        artifact = result["artifacts"][0]["artifact"]
        generation = artifact.metadata.get("generation", {})

        self.assertEqual({"tokens": 20, "api_calls": 1}, result["usage"])
        self.assertEqual("llm", generation.get("source"))
        self.assertEqual("StayBooking", artifact.content.get("project_name"))

    def test_pm_agent_falls_back_when_llm_returns_invalid_json(self) -> None:
        llm_profile = LLMProfile(
            name="mock_json",
            provider="mock",
            model="mock-json-model",
            enabled=True,
            temperature=0.0,
            max_output_tokens=512,
        )
        llm_client = MockLLMClient(response_text="not a json payload")
        agent = ProductManagerAgent(
            role="pm",
            system_prompt="pm prompt",
            tools=[],
            llm_client=llm_client,
            llm_profile=llm_profile,
        )

        result = agent.act(ProjectState())
        artifact = result["artifacts"][0]["artifact"]
        generation = artifact.metadata.get("generation", {})

        self.assertEqual({"tokens": 130, "api_calls": 1}, result["usage"])
        self.assertEqual("rule_fallback", generation.get("source"))
        self.assertEqual("invalid_json", generation.get("reason"))
        self.assertEqual("StayBooking", artifact.content.get("project_name"))


if __name__ == "__main__":
    unittest.main()
