# Multi-Agent StayBooking Execution Plan (Research + Productization)

Last updated: 2026-02-25
Plan owner: Project execution baseline agreed with user.

## Rules (Strict)

1. This file is the single source of truth for schedule and milestones.
2. All future progress updates must map to one week item below.
3. No timeline or scope change is allowed without explicit user approval.
4. Every progress report must include: date, week number, completed tasks, evidence files/outputs.

## Scope Extension Approval (2026-02-25)

- User-approved extension: integrate productization landing work into the existing week plan.
- Constraint: keep Week 1-9 methodology milestones unchanged; add productization tasks to Week 10-14.
- Resulting plan mode: dual-track execution (Research track + Productization track).

## Functional Scope Baseline (Ground-Truth Anchored, 2026-02-25)

- Backend baseline source: `ground_truth/staybooking-project` @ `81b85eab7d2d14076eb9b32234522b2f42c66382`.
- Frontend baseline source: `ground_truth/stayboookingfe` @ `4a7a9551a37d6210c40760b30218b20cb03f8394`.
- Ground-truth benchmark: `ground_truth/benchmark/staybooking_ground_truth.json`.
- MVP reproduction scope lock (user-approved): `auth`, `listing`, `search`, `booking`.
- Explicitly out of current MVP scope: `payment`, `review`.
- Scope lock applies to Week 10-14 productization work and does not change Week 1-9 methodology milestones.

## Methodology Sync Check (2026-02-24)

- Source document: `C:/Users/29019/Downloads/Multi_Agent_Methodology.docx`
- Extract snapshot: methodology paragraph dump (616 paragraphs, local temp artifact)
- Result: no section-level or requirement-level text differences from prior extracted version.
- Decision: keep 14-week schedule unchanged.
- Clarification updates applied:
- Week 2 explicitly includes schema and prompt scaffolding.
- Week 3 explicitly includes minimal tool wrappers needed for Sequential runnable flow.
- Week 8 explicitly uses methodology metric weights and composite score formula.

## Fixed Timeline (14 Weeks)

### Week 1 (2026-02-23 ~ 2026-03-01)
- Lock backend/frontend baseline repos and commits.
- Build ground truth extraction pipeline and initial benchmark snapshot.
- Initialize project skeleton and core folder structure.
- Deliverable: reproducible baseline + benchmark artifacts.

### Week 2 (2026-03-02 ~ 2026-03-08)
- Implement `BaseAgent`, `ProjectState`, artifact store, message log/version tracing.
- Add schema/prompt scaffolding: `schemas/*.json`, `configs/prompts/*`.
- Deliverable: core runtime data model and traceable artifact lifecycle.

### Week 3 (2026-03-09 ~ 2026-03-15)
- Implement Orchestrator and Topology A (Sequential).
- Add minimal tool wrapper integration required for runnable loop (`file`, `executor`, `test/lint` entrypoints).
- Run minimal end-to-end flow on Auth module.
- Deliverable: first runnable multi-agent pipeline.

### Week 4 (2026-03-16 ~ 2026-03-22)
- Implement Topology B (Hub-and-Spoke).
- Deliverable: coordinator-mediated routing workflow.

### Week 5 (2026-03-23 ~ 2026-03-29)
- Implement Topology C (Peer Review).
- Deliverable: review/approval loops with bounded revisions.

### Week 6 (2026-03-30 ~ 2026-04-05)
- Implement Topology D (Iterative Feedback).
- Add iteration cap and anti-loop controls.
- Deliverable: QA-driven feedback routing workflow.

### Week 7 (2026-04-06 ~ 2026-04-12)
- Add 3 task granularities: Layer / Module / Feature.
- Deliverable: config-driven granularity switch.

### Week 8 (2026-04-13 ~ 2026-04-19)
- Implement evaluation pipeline v1:
- Requirement/API/entity coverage, build/test pass, deploy checks, efficiency stats.
- Implement weighted composite score:
- `Q = 0.30 * RCR + 0.20 * CodeQuality + 0.20 * ArchScore + 0.20 * DeployScore + 0.10 * (1 - NormEfficiency)`.
- Deliverable: automated scoring outputs.

### Week 9 (2026-04-20 ~ 2026-04-26)
- Run pilot experiments and fix stability issues.
- Deliverable: stable pre-production experiment workflow.

### Week 10 (2026-04-27 ~ 2026-05-03)
- Research track: run primary matrix (Level 1/2 first batch).
- Productization track:
- Freeze target scope for MVP StayBooking (auth, listing, search, booking).
- Week 10 Step 1 (priority hardening):
- Connect `week9` pipeline to automatic materialization (aligned with `week8` runtime materialization behavior).
- Enforce hard gate: backend/frontend must be valid LLM outputs; fallback-generated code is not allowed to pass.
- Enforce post-landing build/test gate: backend build + unit tests, frontend build + test/lint.
- Week 10 Step 2:
- Define artifact-to-repo landing contract (path map, overwrite policy, branch strategy, commit policy).
- Implement repository materialization pipeline from agent `code_bundle` to backend/frontend working trees.
- Deliverable:
- Research: raw experiment results batch 1.
- Productization: runnable repo-landing pipeline v1 with materialize + LLM-output hard gate + build/test gate.

### Week 11 (2026-05-04 ~ 2026-05-10)
- Research track: complete primary matrix runs and aggregate results.
- Productization track:
- Complete auth slice landing into repos with deterministic file writes.
- Add real build/test gates for landed code (backend build + unit tests, frontend build + test/lint).
- Add CI execution entrypoint for landing validation.
- Deliverable:
- Research: full matrix dataset (automated metrics).
- Productization: MVP auth code landed + CI gates passing.

### Week 12 (2026-05-11 ~ 2026-05-17)
- Research track: run ablations (A1-A6) and Level 3 incremental feature tests.
- Productization track:
- Expand landed modules to listing/search/booking flows.
- Add integration tests (API contract tests + frontend-backend integration smoke).
- Add seeded demo dataset and environment bootstrapping scripts.
- Deliverable:
- Research: ablation + regression result set.
- Productization: end-to-end MVP feature slice runnable locally (`auth + listing + search + booking`).

### Week 13 (2026-05-18 ~ 2026-05-24)
- Research track: conduct architecture human evaluation and statistical analysis.
- Productization track:
- Prepare cloud deployment baseline (container build, service manifests, secret/env contract).
- Add staging deployment pipeline with health checks, rollback script, and smoke tests.
- Run security/config hardening pass (credential handling, CORS/auth settings, basic rate-limit checks).
- Deliverable:
- Research: inter-rater and significance outputs.
- Productization: staging-ready deployment pipeline.

### Week 14 (2026-05-25 ~ 2026-05-31)
- Research track: finalize paper-ready tables, figures, and reproducibility docs.
- Productization track:
- Execute first real cloud deployment run (staging -> production promotion checklist).
- Publish runbook (deploy, rollback, incident triage, cost guardrails).
- Freeze release candidate and handoff package (repo state, configs, validation evidence).
- Deliverable:
- Research: submission-ready package.
- Productization: production-deployable MVP package.

## Week 10-14 Sequencing Optimization (User-Approved, 2026-02-25)

- Optimization objective: maximize reliability of landed code before feature expansion.
- Ordered execution for unfinished work:
1. Week 10 Step 1 hardening first: materialize + valid-LLM-output hard gate + build/test gate.
2. Week 10 Step 2 landing contract and deterministic repo write policy.
3. Week 11 auth slice landing and CI entrypoint on top of Step 1/2 gates.
4. Week 12 listing/search/booking integration after auth slice is stable.
5. Week 13-14 cloud deployment and release packaging only after local E2E stability is proven.
- Gating rule: if any hard gate fails, do not advance to the next step/week deliverable.

## Current Status Snapshot (as of 2026-02-25)

- Week 1 completed items:
- Step 1 (baseline lock) completed:
- Backend commit: `81b85eab7d2d14076eb9b32234522b2f42c66382`
- Frontend commit: `4a7a9551a37d6210c40760b30218b20cb03f8394`
- Lock file: `ground_truth/baseline_lock.json`
- Verification script: `evaluation/verify_baseline_lock.py`
- Verification result: `BASELINE_VERIFY: PASS`
- Ground truth extraction script: `evaluation/extract_ground_truth.py`
- Benchmark outputs:
- `ground_truth/benchmark/staybooking_ground_truth.json`
- `ground_truth/benchmark/staybooking_ground_truth.md`
- Week 1 reproducibility pipeline completed:
- Unified entry: `run_experiment.py`
- Week 1 config: `configs/experiment_configs/week1_baseline.json`
- Week 1 report: `outputs/week1/week1_pipeline_report.json`
- Usage doc: `README.md`
- Week 1 status: COMPLETE
- Week 2 progress update (started ahead of schedule):
- Core runtime package:
- `core/models.py`
- `core/artifact_store.py`
- `core/message_log.py`
- `core/project_state.py`
- Base agent interface:
- `agents/base_agent.py`
- Schema scaffolding:
- `schemas/requirements.json`
- `schemas/architecture.json`
- `schemas/bug_report.json`
- `schemas/project_state.json`
- Prompt scaffolding:
- `configs/prompts/pm_agent.md`
- `configs/prompts/architect_agent.md`
- `configs/prompts/backend_dev_agent.md`
- `configs/prompts/frontend_dev_agent.md`
- `configs/prompts/qa_agent.md`
- `configs/prompts/devops_agent.md`
- `configs/prompts/coordinator_agent.md`
- Week 2 smoke + tests:
- `evaluation/week2_smoke.py`
- `configs/experiment_configs/week2_smoke.json`
- `tests/test_artifact_store.py`
- `tests/test_message_log.py`
- `tests/test_project_state.py`
- Prompt/schema contract validation:
- `configs/prompt_contracts.json`
- `evaluation/validate_prompt_contracts.py`
- `tests/test_prompt_contracts.py`
- Verification evidence:
- `outputs/week2/week2_smoke_state.json`
- `outputs/week2/week2_smoke_report.json`
- `outputs/week2/week2_pipeline_report.json`
- `outputs/week2/prompt_contract_report.json`
- `outputs/week2/week2_acceptance_matrix.md`
- `python run_experiment.py --task week2-smoke` => PASS
- `python run_experiment.py --task validate-prompts` => PASS
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (8 tests)
- Week 2 status: COMPLETE
- Week 3 progress update:
- Orchestrator core implemented:
- `core/orchestrator.py`
- Week 3 Step 1 smoke implemented:
- `evaluation/week3_step1_orchestrator_smoke.py`
- `configs/experiment_configs/week3_step1_orchestrator.json`
- Pipeline entrypoint:
- `python run_experiment.py --task week3-step1` => PASS
- Week 3 Step 1 evidence:
- `outputs/week3/step1/week3_step1_state.json`
- `outputs/week3/step1/week3_step1_orchestrator_report.json`
- `outputs/week3/step1/week3_step1_pipeline_report.json`
- `outputs/week3/step1/week3_step1_acceptance_matrix.md`
- Unit tests expanded:
- `tests/test_orchestrator.py`
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (11 tests)
- Week 3 Step 1 status: COMPLETE
- Week 3 Step 2 implemented:
- Role agents:
- `agents/pm_agent.py`
- `agents/architect_agent.py`
- `agents/backend_dev_agent.py`
- `agents/frontend_dev_agent.py`
- `agents/qa_agent.py`
- `agents/devops_agent.py`
- Sequential topology runtime:
- `topologies/sequential.py`
- `evaluation/week3_step2_sequential_smoke.py`
- `configs/experiment_configs/week3_step2_sequential.json`
- Pipeline entrypoint:
- `python run_experiment.py --task week3-step2` => PASS
- Week 3 Step 2 evidence:
- `outputs/week3/step2/week3_step2_state.json`
- `outputs/week3/step2/week3_step2_sequential_report.json`
- `outputs/week3/step2/week3_step2_pipeline_report.json`
- `outputs/week3/step2/week3_step2_acceptance_matrix.md`
- Tool wrappers (minimal):
- `tools/file_system.py`
- `tools/code_executor.py`
- `tools/test_runner.py`
- Unit tests expanded:
- `tests/test_sequential_topology.py`
- `tests/test_tools.py`
- Ground truth portability fix:
- `evaluation/extract_ground_truth.py` now emits repo-relative/project-relative POSIX paths
- `tests/test_ground_truth_paths.py` prevents absolute-path regressions
- `python evaluation/extract_ground_truth.py` => PASS (portable benchmark regenerated)
- `python run_experiment.py --task week1` => PASS after portability change
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (16 tests)
- Week 3 status: COMPLETE
- Week 4 implemented:
- Coordinator agent:
- `agents/coordinator_agent.py`
- Hub-and-Spoke topology runtime:
- `topologies/hub_spoke.py`
- `topologies/__init__.py` exports updated
- Week 4 smoke and pipeline config:
- `evaluation/week4_hub_spoke_smoke.py`
- `configs/experiment_configs/week4_hub_spoke.json`
- Pipeline entrypoint:
- `python run_experiment.py --task week4-hub` => PASS
- Week 4 evidence:
- `outputs/week4/week4_hub_spoke_state.json`
- `outputs/week4/week4_hub_spoke_report.json`
- `outputs/week4/week4_hub_spoke_pipeline_report.json`
- `outputs/week4/week4_hub_spoke_acceptance_matrix.md`
- Unit tests expanded:
- `tests/test_hub_spoke_topology.py`
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (22 tests)
- Week 4 status: COMPLETE
- Week 5 implemented:
- Peer reviewer agent:
- `agents/reviewer_agent.py`
- Peer Review topology runtime:
- `topologies/peer_review.py`
- `topologies/__init__.py` exports updated
- Week 5 smoke and pipeline config:
- `evaluation/week5_peer_review_smoke.py`
- `configs/experiment_configs/week5_peer_review.json`
- Pipeline entrypoint:
- `python run_experiment.py --task week5-peer-review` => PASS
- Week 5 evidence:
- `outputs/week5/week5_peer_review_state.json`
- `outputs/week5/week5_peer_review_report.json`
- `outputs/week5/week5_peer_review_pipeline_report.json`
- `outputs/week5/week5_peer_review_acceptance_matrix.md`
- Unit tests expanded:
- `tests/test_peer_review_topology.py`
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (25 tests)
- Week 5 status: COMPLETE
- Week 6 implemented:
- Iterative Feedback topology runtime:
- `topologies/iterative_feedback.py`
- `topologies/__init__.py` exports updated
- Week 6 smoke and pipeline config:
- `evaluation/week6_iterative_feedback_smoke.py`
- `configs/experiment_configs/week6_iterative_feedback.json`
- Pipeline entrypoint:
- `python run_experiment.py --task week6-iterative-feedback` => PASS
- Week 6 evidence:
- `outputs/week6/week6_iterative_feedback_state.json`
- `outputs/week6/week6_iterative_feedback_report.json`
- `outputs/week6/week6_iterative_feedback_pipeline_report.json`
- `outputs/week6/week6_iterative_feedback_acceptance_matrix.md`
- Unit tests expanded:
- `tests/test_iterative_feedback_topology.py`
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (28 tests)
- Week 6 status: COMPLETE
- Week 7 implemented:
- Granularity profile config:
- `configs/granularity_profiles.json`
- Granularity loader:
- `core/granularity.py`
- `core/__init__.py` exports updated
- Week 7 smoke and pipeline config:
- `evaluation/week7_granularity_switch_smoke.py`
- `configs/experiment_configs/week7_granularity_switch.json`
- Pipeline entrypoint:
- `python run_experiment.py --task week7-granularity-switch` => PASS
- Week 7 evidence:
- `outputs/week7/week7_granularity_switch_report.json`
- `outputs/week7/week7_granularity_switch_pipeline_report.json`
- `outputs/week7/week7_layer_state.json`
- `outputs/week7/week7_module_state.json`
- `outputs/week7/week7_feature_state.json`
- `outputs/week7/week7_granularity_switch_acceptance_matrix.md`
- Unit tests expanded:
- `tests/test_granularity_switch.py`
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (30 tests)
- Week 7 status: COMPLETE
- Week 8 implemented:
- Metric calculation core:
- `core/evaluation_metrics.py`
- `core/__init__.py` exports updated
- Strict no-leakage evaluation mode:
- `materialization_mode = pure_generated` (no ground-truth template overlay)
- runtime-backed score adjustment uses actual executable checks
- Runtime validation tools:
- `tools/artifact_materializer.py`
- `tools/build_deploy_validator.py`
- `tools/code_executor.py`
- `tools/__init__.py` exports updated
- Evaluation target config:
- `configs/evaluation_targets/week8_v1_targets.json`
- Week 8 smoke and pipeline config:
- `evaluation/week8_evaluation_pipeline_v1.py`
- `configs/experiment_configs/week8_evaluation_v1.json`
- Pipeline entrypoint:
- `python run_experiment.py --task week8-evaluation-v1` => PASS
- Week 8 evidence:
- `outputs/week8/week8_evaluation_report.json`
- `outputs/week8/week8_evaluation_pipeline_report.json`
- `outputs/week8/generated_workspaces/*`
- Unit tests expanded:
- `tests/test_evaluation_metrics.py`
- `tests/test_artifact_materializer.py`
- `tests/test_build_deploy_validator.py`
- `tests/test_tools.py` (timeout path)
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (41 tests)
- Week 8 status: COMPLETE
- Week 9 implemented:
- LLM runtime integration:
- `llm/models.py`
- `llm/client.py`
- `llm/factory.py`
- `llm/__init__.py`
- LLM profiles and pilot matrix config:
- `configs/llm_profiles.json`
- `configs/pilot/week9_pilot_matrix.json`
- Agent runtime upgraded with LLM JSON + fallback behavior:
- `agents/base_agent.py`
- `agents/pm_agent.py`
- `agents/architect_agent.py`
- `agents/backend_dev_agent.py`
- `agents/frontend_dev_agent.py`
- `agents/qa_agent.py`
- `agents/devops_agent.py`
- Week 9 pilot and pipeline config:
- `evaluation/week9_pilot_experiments.py`
- `configs/experiment_configs/week9_pilot.json`
- Pipeline entrypoint:
- `python run_experiment.py --task week9-pilot` => PASS
- Week 9 evidence:
- `outputs/week9/week9_pilot_report.json`
- `outputs/week9/week9_pilot_pipeline_report.json`
- Unit tests expanded:
- `tests/test_llm_integration.py`
- `python -m unittest discover -s tests -p "test_*.py"` => PASS (36 tests)
- Week 9 status: COMPLETE
- Week 10 kickoff gap snapshot (to close in Step 1):
- `week9-pilot` default run saves state but does not materialize backend/frontend workspaces.
- backend/frontend code generation has frequent `rule_fallback: invalid_json`; code artifacts are unstable.
- current "deploy success" is local-simulated artifact validation, not real cloud deployment.
- hard-gated landing (`materialize + no-fallback pass + build/test`) is not yet enforced.
- Next phase: Week 10 dual-track kickoff (research matrix + productization repo-landing pipeline).

