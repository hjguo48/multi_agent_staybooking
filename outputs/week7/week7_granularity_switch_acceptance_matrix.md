# Week 7 Acceptance Matrix

Date: 2026-02-25
Week: 7
Focus: Config-driven granularity switch (Layer / Module / Feature)

## Scope

- Granularity profile configuration and loader
- Runtime granularity switching via config
- Scenario validation for layer/module/feature scopes
- Pipeline and unit-test validation

## Checklist

1. Granularity profiles are defined in one config source.
- Status: PASS
- Evidence: `configs/granularity_profiles.json`

2. Loader validates and exposes profiles programmatically.
- Status: PASS
- Evidence: `core/granularity.py`

3. Smoke run executes all three granularities with profile-driven role switch.
- Status: PASS
- Evidence: `evaluation/week7_granularity_switch_smoke.py`, `outputs/week7/week7_granularity_switch_report.json`

4. Layer/module/feature state shapes are validated against profile constraints.
- Status: PASS
- Evidence: `outputs/week7/week7_layer_report.json`, `outputs/week7/week7_module_report.json`, `outputs/week7/week7_feature_report.json`

5. Week7 pipeline runs end-to-end with baseline checks and full test suite.
- Status: PASS
- Evidence: `outputs/week7/week7_granularity_switch_pipeline_report.json`

6. Granularity switch behavior is covered by unit tests.
- Status: PASS
- Evidence: `tests/test_granularity_switch.py`

## Result

- Week 7: COMPLETE
- Next: Week 8 (evaluation pipeline v1 and weighted composite scoring)
