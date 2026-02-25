# Multi-Agent StayBooking Research Workspace

This repository is the execution workspace for the 14-week plan in `EXECUTION_PLAN.md`.

## Week 1 Commands

Run baseline verification only:

```bash
python evaluation/verify_baseline_lock.py
```

Run ground truth extraction only:

```bash
python evaluation/extract_ground_truth.py
```

Run Week 1 pipeline (single command):

```bash
python run_experiment.py --task week1
```

Artifacts generated:

- `ground_truth/baseline_lock.json`
- `ground_truth/benchmark/staybooking_ground_truth.json`
- `ground_truth/benchmark/staybooking_ground_truth.md`
- `outputs/week1/week1_pipeline_report.json`

## Week 2 Commands

Run Week 2 smoke pipeline (core runtime structures + tests):

```bash
python run_experiment.py --task week2-smoke
```

Run Week 2 smoke script only:

```bash
python evaluation/week2_smoke.py
```

Run unit tests only:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

Run prompt-schema contract validation only:

```bash
python run_experiment.py --task validate-prompts
```

Week 2 artifacts generated:

- `outputs/week2/week2_smoke_state.json`
- `outputs/week2/week2_smoke_report.json`
- `outputs/week2/week2_pipeline_report.json`
- `outputs/week2/prompt_contract_report.json`

## Week 3 Step 1 Commands

Run Week 3 Step 1 pipeline (minimal orchestrator runtime):

```bash
python run_experiment.py --task week3-step1
```

Run Week 3 Step 1 smoke only:

```bash
python evaluation/week3_step1_orchestrator_smoke.py
```

Week 3 Step 1 artifacts generated:

- `outputs/week3/step1/week3_step1_state.json`
- `outputs/week3/step1/week3_step1_orchestrator_report.json`
- `outputs/week3/step1/week3_step1_pipeline_report.json`

## Week 3 Step 2 Commands

Run Week 3 Step 2 pipeline (sequential topology flow):

```bash
python run_experiment.py --task week3-step2
```

Run Week 3 Step 2 smoke only:

```bash
python evaluation/week3_step2_sequential_smoke.py
```

Week 3 Step 2 artifacts generated:

- `outputs/week3/step2/week3_step2_state.json`
- `outputs/week3/step2/week3_step2_sequential_report.json`
- `outputs/week3/step2/week3_step2_pipeline_report.json`

## Week 4 Commands

Run Week 4 pipeline (Hub-and-Spoke topology):

```bash
python run_experiment.py --task week4-hub
```

Run Week 4 smoke only:

```bash
python evaluation/week4_hub_spoke_smoke.py
```

Week 4 artifacts generated:

- `outputs/week4/week4_hub_spoke_state.json`
- `outputs/week4/week4_hub_spoke_report.json`
- `outputs/week4/week4_hub_spoke_pipeline_report.json`

## Week 5 Commands

Run Week 5 pipeline (Peer Review topology):

```bash
python run_experiment.py --task week5-peer-review
```

Run Week 5 smoke only:

```bash
python evaluation/week5_peer_review_smoke.py
```

Week 5 artifacts generated:

- `outputs/week5/week5_peer_review_state.json`
- `outputs/week5/week5_peer_review_report.json`
- `outputs/week5/week5_peer_review_pipeline_report.json`
- `outputs/week5/week5_peer_review_acceptance_matrix.md`

## Week 6 Commands

Run Week 6 pipeline (Iterative Feedback topology):

```bash
python run_experiment.py --task week6-iterative-feedback
```

Run Week 6 smoke only:

```bash
python evaluation/week6_iterative_feedback_smoke.py
```

Week 6 artifacts generated:

- `outputs/week6/week6_iterative_feedback_state.json`
- `outputs/week6/week6_iterative_feedback_report.json`
- `outputs/week6/week6_iterative_feedback_pipeline_report.json`
- `outputs/week6/week6_iterative_feedback_acceptance_matrix.md`

## Week 7 Commands

Run Week 7 pipeline (granularity switch: layer/module/feature):

```bash
python run_experiment.py --task week7-granularity-switch
```

Run Week 7 smoke only:

```bash
python evaluation/week7_granularity_switch_smoke.py
```

Week 7 artifacts generated:

- `outputs/week7/week7_granularity_switch_report.json`
- `outputs/week7/week7_granularity_switch_pipeline_report.json`
- `outputs/week7/week7_layer_state.json`
- `outputs/week7/week7_module_state.json`
- `outputs/week7/week7_feature_state.json`
- `outputs/week7/week7_granularity_switch_acceptance_matrix.md`

## Week 8 Commands

Run Week 8 pipeline (evaluation pipeline v1 + weighted composite score):

```bash
python run_experiment.py --task week8-evaluation-v1
```

Run Week 8 evaluation script only:

```bash
python evaluation/week8_evaluation_pipeline_v1.py
```

Week 8 artifacts generated:

- `outputs/week8/week8_evaluation_report.json`
- `outputs/week8/week8_evaluation_pipeline_report.json`

## Week 9 Commands

Run Week 9 pipeline (pilot experiments + stability checks):

```bash
python run_experiment.py --task week9-pilot
```

Run Week 9 pilot script only:

```bash
python evaluation/week9_pilot_experiments.py
```

Week 9 artifacts generated:

- `outputs/week9/week9_pilot_report.json`
- `outputs/week9/week9_pilot_pipeline_report.json`

Week 9 pilot defaults to offline-safe mode (`allow_network_llm=false` in
`configs/pilot/week9_pilot_matrix.json`). Set it to `true` to run real Claude
calls when `ANTHROPIC_API_KEY` is configured.

## Notes

- Ground truth uses repository reality as source of truth.
- Methodology numeric assumptions are treated as reference only.
- Ground truth filesystem paths in JSON are emitted as portable POSIX relative paths
  (no machine-specific absolute paths).
