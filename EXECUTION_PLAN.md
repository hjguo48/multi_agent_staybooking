# Multi-Agent StayBooking Execution Plan (Baseline)

Last updated: 2026-02-25
Plan owner: Project execution baseline agreed with user.

## Rules (Strict)

1. This file is the single source of truth for schedule and milestones.
2. All future progress updates must map to one week item below.
3. No timeline or scope change is allowed without explicit user approval.
4. Every progress report must include: date, week number, completed tasks, evidence files/outputs.

## Methodology Sync Check (2026-02-24)

- Source document: `C:/Users/29019/Downloads/Multi_Agent_Methodology.docx`
- Extract snapshot: `.tmp_doc_extract_latest.txt` (616 paragraphs)
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
- Run primary matrix (Level 1/2 first batch).
- Deliverable: raw experiment results batch 1.

### Week 11 (2026-05-04 ~ 2026-05-10)
- Complete primary matrix runs and aggregate results.
- Deliverable: full matrix dataset (automated metrics).

### Week 12 (2026-05-11 ~ 2026-05-17)
- Run ablations (A1-A6) and Level 3 incremental feature tests.
- Deliverable: ablation + regression result set.

### Week 13 (2026-05-18 ~ 2026-05-24)
- Conduct architecture human evaluation and statistical analysis.
- Deliverable: inter-rater and significance outputs.

### Week 14 (2026-05-25 ~ 2026-05-31)
- Finalize paper-ready tables, figures, and reproducibility docs.
- Deliverable: submission-ready package.

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
- Next phase: Week 7 granularity switch implementation.

