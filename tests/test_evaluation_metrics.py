from __future__ import annotations

import unittest

from core.evaluation_metrics import (
    RunMetrics,
    ScoreWeights,
    apply_composite_scores,
    compute_composite_score,
    evaluate_run,
    normalize_efficiency,
)


class EvaluationMetricsTests(unittest.TestCase):
    def test_evaluate_run_computes_coverage_and_scores(self) -> None:
        state_payload = {
            "created_at": "2026-02-25T00:00:00+00:00",
            "updated_at": "2026-02-25T00:00:10+00:00",
            "total_tokens": 200,
            "total_api_calls": 5,
            "iteration": 1,
            "artifact_store": {
                "requirements": [
                    {
                        "content": {
                            "functional_requirements": [{"id": "FR-1"}, {"id": "FR-2"}],
                            "api_contracts": [
                                {"endpoint": "/auth/login"},
                                {"endpoint": "/bookings/${bookingId}"},
                            ],
                            "data_model": {
                                "entities": ["User", "Booking"],
                                "relationships": [],
                            },
                        }
                    }
                ],
                "architecture": [
                    {
                        "content": {
                            "tech_stack": {},
                            "modules": [{"name": "auth", "responsibility": "auth flows"}],
                            "database_schema": {
                                "tables": [{"name": "users"}, {"name": "bookings"}]
                            },
                            "openapi_spec": {
                                "paths": {
                                    "/auth/login": {},
                                    "/bookings/{bookingId}": {},
                                }
                            },
                            "deployment": {},
                        }
                    }
                ],
                "backend_code": [{"content": {"build_notes": {"compile_status": "pass"}}}],
                "frontend_code": [{"content": {"build_notes": {"build_status": "success"}}}],
                "qa_report": [
                    {
                        "content": {
                            "summary": {
                                "test_pass_rate": 0.5,
                                "critical_bugs": 1,
                                "major_bugs": 1,
                            },
                            "coverage_map": {"FR-1": ["testA"]},
                        }
                    }
                ],
                "deployment": [
                    {
                        "content": {
                            "status": "success",
                            "health_checks": {"backend": 200, "frontend": 500},
                            "access_urls": {
                                "backend": "http://localhost:8080",
                                "frontend": "http://localhost:3000",
                            },
                        }
                    }
                ],
            },
        }

        ground_truth_payload = {
            "backend": {
                "endpoints": [
                    {"full_path": "/auth/login"},
                    {"full_path": "/bookings/{bookingId}"},
                    {"full_path": "/listings"},
                ],
                "entities": [
                    {"class": "UserEntity"},
                    {"class": "BookingEntity"},
                    {"class": "ListingEntity"},
                ],
            }
        }

        metrics = evaluate_run("sample", state_payload, ground_truth_payload)

        self.assertAlmostEqual(0.5, metrics.requirement_coverage, places=6)
        self.assertAlmostEqual(2.0 / 3.0, metrics.api_coverage, places=6)
        self.assertAlmostEqual(2.0 / 3.0, metrics.entity_coverage, places=6)
        self.assertAlmostEqual((0.5 + (2.0 / 3.0) + (2.0 / 3.0)) / 3.0, metrics.rcr, places=6)
        self.assertAlmostEqual(0.765, metrics.code_quality, places=6)
        self.assertAlmostEqual(0.8, metrics.deploy_score, places=6)
        self.assertAlmostEqual(0.6791666666666667, metrics.arch_score, places=6)
        self.assertEqual(200, metrics.total_tokens)
        self.assertEqual(5, metrics.total_api_calls)
        self.assertEqual(1, metrics.iteration_count)
        self.assertAlmostEqual(10.0, metrics.wall_clock_seconds, places=6)

    def test_normalize_efficiency_uses_token_range(self) -> None:
        metrics = [
            RunMetrics(run_name="a", state_path="a.json", total_tokens=100),
            RunMetrics(run_name="b", state_path="b.json", total_tokens=300),
            RunMetrics(run_name="c", state_path="c.json", total_tokens=500),
        ]
        normalize_efficiency(metrics)
        self.assertAlmostEqual(0.0, metrics[0].norm_efficiency, places=6)
        self.assertAlmostEqual(0.5, metrics[1].norm_efficiency, places=6)
        self.assertAlmostEqual(1.0, metrics[2].norm_efficiency, places=6)

    def test_composite_score_formula_matches_spec(self) -> None:
        metric = RunMetrics(
            run_name="x",
            state_path="x.json",
            rcr=0.6,
            code_quality=0.5,
            arch_score=0.7,
            deploy_score=0.8,
            norm_efficiency=0.25,
        )
        score = compute_composite_score(metric, weights=ScoreWeights())
        self.assertAlmostEqual(0.655, score, places=6)

        apply_composite_scores([metric], weights=ScoreWeights())
        self.assertAlmostEqual(0.68, metric.composite_score, places=6)


if __name__ == "__main__":
    unittest.main()
