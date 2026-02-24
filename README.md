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

## Notes

- Ground truth uses repository reality as source of truth.
- Methodology numeric assumptions are treated as reference only.
