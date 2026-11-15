# Walkthrough Notes

Baseline code walkthrough for the **Fooling the Flight Recorder** capstone (CS6170, Fall 2026).
Team: Uzma Fatima, Pranudeep Metuku, Aparna Shree Govindarajan.

This file records what was shown and agreed at the walkthrough, and the fixes committed
afterward.

---

## 1. What we showed

- **The system under test.** AgentRx (Microsoft), run unmodified: a 6-stage pipeline
  (IR -> static invariants -> dynamic invariants -> check -> LLM judge -> report) that
  reads a failed AI-agent run and names the critical failure step and category.
- **Live cold run.** Cloned the repo fresh and ran one tau-retail trajectory end to end
  with `python run.py trajectories/tau-retail/agentrx_walkthrough.json --domain tau
  --run-name tau_walkthrough`. All six stages completed; the judge diagnosed
  **Invention of New Information** (the agent stated a cancellation reason and a refund
  destination that were not grounded in the user's words or any tool result).
- **Reproducibility layer (our team's additions):**
  - **Data versioning** — a frozen, immutable baseline release
    (`data/benchmark_versions/tau_retail/baseline/v1.0.0/`) with a manifest recording
    each file's SHA-256 checksum and all 29 trajectory IDs (29 traces, 29 labels).
  - **Scorer** (`baselines/score_runs.py`) — step and category accuracy, the
    confident-misattribution rate, and Wilson 95% confidence intervals.
  - **Non-AI keyword baseline** (`baselines/keyword_baseline.py`) — a no-AI comparison
    that flags the first step containing an error keyword.
- **Baseline result.** Reproduced AgentRx on the 29 tau-bench traces:
  **step accuracy 41.4%**, matching the paper's one-shot config (41.0 ± 2.1).
  Category accuracy is lower; traced entirely to using a newer judge model than the
  paper's GPT-5.

## 2. What we decided last meeting / what the instructor agreed to

- The instructor agreed to our **pivot**: because AgentRx's verdict depends on the judge
  model, the project becomes a **robustness framework** rather than a single-tool attack.
- Agreed plan: reword each failed trace in **three label-preserving ways**
  (step decoy, step decomposition, presentation change) and run each through
  **multiple judge models**, measuring how much the diagnosis shifts and which model is
  most robust. tau-bench is the tuning stage; the best setup is carried to held-out
  Magentic-One.
- Agreed that the category-accuracy gap is a **finding (model-dependence), not a defect**
  in our pipeline.
- Agreed to keep the baseline reproducible: frozen, checksummed data; a credential-free
  path where possible; and results reported with confidence intervals.

## 3. Known, intentional behavior (not defects)

- **"Import of 'decimal' is not allowed in invariant checks."** One LLM-generated
  invariant used a blocked import; the checker safely skips that single check and
  continues. The run completes normally — it fails safe.
- **"few_shot_examples directory does not exist."** Optional helper examples for the
  judge; absent by design, the run continues without them.
- **Step / violation counts vary slightly run-to-run** (e.g. step 3 vs step 4, 1 vs 2
  violations) because the LLM judge is non-deterministic. This instability is part of
  what the project measures.
