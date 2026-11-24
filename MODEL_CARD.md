# Model Card: AgentRx failure attribution, Track-A baseline

Sections follow Mitchell et al. (2019), Section 4. Evaluation type: exploratory (Barocas et al., 2021). Every rate carries its count. Intervals are Wilson 95%.

> Items in [brackets] must be filled or confirmed before commit.

## 4.1 Model details

- **Team:** Fooling the Flight Recorder (Aparna, Uzma, Pranudeep), CS6170 AI Capstone, Track A. Working group: [A / B / C]
- **Date:** November 24, 2026
- **Version:** v1
- **Baseline commit:** [`ac01913`](https://github.com/Aparnashree11/agentRx/commit/ac019130950b52ac99d233b628a5965eef241e44), "Add Track-A tau-bench baseline results (sol + luna)", branch `baseline-results`, November 19, 2026. [The branch is not yet merged into `main`; confirm the commit the card should cite after merging.]
- **Model type:** AgentRx (Barke et al., 2026, arXiv 2602.02475), used unmodified as a gray-box system. It synthesizes constraints from a failed agent trajectory, then an LLM judge names (1) the critical failure step and (2) one of nine failure categories, or returns "inconclusive." No model is trained by our team.
- **Configuration:** one-shot constraint synthesis (`--dynamic-mode oneshot`), single judge, all-at-once. Command: `run.py --domain tau --endpoint copilot --dynamic-mode oneshot`. This corresponds to the paper's one-shot +Vio setting (Table 4).
- **Judges:** reached through the GitHub Copilot API, not Azure OpenAI as in the paper.
  - gpt-6.1-sol: primary judge, three one-shot runs and one few-shot run.
  - gpt-6-luna: comparison judge, one run.
- **Non-AI baseline:** keyword rule. It picks the first step containing an error keyword.
- **Scorer:** `baselines/score_runs.py` (standard-library Python). It matches category labels by number or keyword and compares root-cause IDs as strings.
- **Reproduction:** `bash scripts/reproduce_baseline.sh` checks the SHA-256 of the five pinned inputs in `results/track_a/baseline/manifest.json`, then re-scores the three sol runs without credentials, network access or LLM calls. Only scoring is reproducible; new judge runs need Copilot credentials and vary between runs.

### How the judge was chosen

gpt-6.1-sol and gpt-6-luna were each run once on the 29 τ-bench trajectories. Sol was chosen because it localized more steps exactly (12/29 vs. 8/29); the two were level on category (10/29 vs. 9/29). Luna was not run again because it was not carried forward. Because the judge is an LLM and its output varies, sol was run two more times on the same trajectories, so the baseline is reported as a mean over three runs rather than a single value.

## 4.2 Intended use

- **Primary use:** a research baseline. It is the clean-trajectory reference against which our reworded trajectories (step decomposition, step decoy, presentation change) are scored.
- **Primary users:** our team; AgentRx's maintainers (recipients of the coordinated disclosure); debugging and security engineers deciding how far to trust an AgentRx verdict.
- **Out-of-scope uses:**
  - Assigning blame to a person, team, vendor, or sub-agent based on a verdict alone. At baseline, the judge commits to a wrong step or category on 20/29 τ-bench trajectories on average (sol, 3 runs).
  - Use of the category label as evidence of whether the user or the agent caused a failure (see 4.7: 0/8 on user-attributed failures).
  - Any claim about multi-agent systems (e.g. Magentic-One), production incidents (Flash, not public), or live traffic. This card covers τ-bench retail only.
- **Scoping conditions from project selection (high-risk):** the binding text is the instructor's wording from the project-selection shortlist, reproduced in Specification §8 and made a term of the Development Contract (§2). As restated in proposal §6, the conditions are:
  - text-only attacks;
  - one auditor (AgentRx), with a second tool only as a stretch goal;
  - three attack classes;
  - sandboxed runs;
  - modest compute;
  - findings written for the maintainers.

  Where this restatement and Specification §8 differ, Specification §8 governs.

## 4.3 Factors

### Stakeholder map

| Stakeholder | Direct / indirect | One harm from a model error |
|---|---|---|
| AgentRx maintainers | Direct | Fix the wrong thing because our results misstate where AgentRx fails |
| Debugging and security engineers acting on verdicts | Direct | Trust a confidently wrong step and close the incident while the real cause stays live |
| Governance leads choosing a tool | Direct | Adopt a tracer on the strength of a "matches the paper" claim the data can't support |
| Incident responders | Indirect | Spend hours on the wrong component |
| Sub-agent owners, component teams, vendors | Indirect | Blamed for a failure they didn't cause |
| End users / customers (incl. the simulated user in τ-bench) | Indirect | Blamed for "underspecified intent" when the agent failed, or the reverse |
| Adversary who wants the trace to mislead | Indirect | Rewords a log so the verdict points elsewhere |

[Check row labels against Appendix A, which has 18 rows.]

### Evaluation factors

Type codes: G = groups of people, I = instrumentation, E = environment.

| Stakeholder | Type | Groups | How identified in the test split | n |
|---|---|---|---|---|
| Governance leads, maintainers | I | Attribution method: sol one-shot, sol few-shot, luna one-shot, keyword rule | Run config | 29 each |
| End users vs. agent (who is blamed) | G | User-attributed (Underspecified User Intent) vs. agent-attributed | Human root-cause label | 8 vs. 21 |
| Sub-agent owners | G | Failed sub-agent | — | not measurable yet (τ-bench has a single agent) |
| Engineers, adversary | E | Clean vs. reworded trajectory | Variant set | preliminary, see 4.7 Part B |
| Incident responders | E | Trajectory length | — | not measurable yet |

## 4.4 Metrics

- **Primary metric for disaggregation:** category accuracy (match to the human category label).
- **Also reported:** exact-step accuracy; both correct; confidently wrong (a committed verdict with the step or category wrong); inconclusive. The scorer also computes step within 1, 3 and 5 steps and mean step distance.
- **Threshold:** none. The paper's judge (GPT-5 on Azure OpenAI) is not available to us, so the paper's figures are not a reproduction target. The baseline results are used directly as the reference for the reworded trajectories.
- **Spread:** sol on τ-bench, mean ± standard deviation over 3 runs. All other configurations were run once.
- **Interval method:** Wilson 95% score interval.

## 4.5 Evaluation data

- **Test split:** 29 failed trajectories, all of them human-labeled, from `microsoft/AgentRx` on Hugging Face (CC BY 4.0, gated), retrieved October 27, 2026. Frozen as `data/benchmark_versions/tau_retail/baseline/v1.0.0/` and pinned by SHA-256. The labeled set is used whole; there is no random split.
- **Preprocessing:** none. Ground-truth labels are used as released. An adapter converts raw messages to sub-steps without loss (1,064 = 1,064).
- **Label audit (`results/track_a/data_checks.json`):** 29 traces and 29 labels, all matched. 39 failure entries, at most 4 per trajectory. In 2 trajectories the labeled root cause is not the earliest failure. Category names are spelled inconsistently in the dataset; the scorer matches categories by number or keyword.
- **Known limit:** τ-bench uses an LLM-simulated customer and a single assistant, so sub-agent misattribution can't be studied on this split.

## 4.6 Training data

No training by our team. AgentRx is used as released. The training data of the judge models is not disclosed by their provider, so contamination with the public benchmark can't be ruled out.

## 4.7 Quantitative analyses

### Part A: baseline (n = 29)

| Method | Runs | Exact step | Category | Both correct | Confidently wrong |
|---|---|---|---|---|---|
| gpt-6.1-sol, one-shot | 3 | 12/29 every run, 41.4% ± 0.0 (25.5–59.3%) | 10, 8, 9 /29, 31.0% ± 3.4 | 8, 7, 8 /29, 26.4% ± 2.0 | 20, 21, 19 /29, 69.0% ± 3.4 |
| gpt-6.1-sol, few-shot | 1 | 11/29, 37.9% (22.7–56.0%) | 10/29, 34.5% (19.9–52.7%) | [ ] | [ ] |
| gpt-6-luna, one-shot | 1 | 8/29, 27.6% (14.7–45.7%) | 9/29, 31.0% (17.3–49.2%) | 5/29, 17.2% (7.6–34.5%) | 23/29, 79.3% (61.6–90.2%) |
| Keyword rule (non-AI) | deterministic | 0/29, 0.0% (0.0–11.7%) | 2/29, 6.9% (1.9–22.0%) | — | — |

The keyword rule localizes 6/29 (20.7%) within ±3 steps. Being deterministic, it has zero spread.

The same judge on the same 29 trajectories moved category accuracy by up to 2 trajectories between runs, while exact step did not move. Category gaps of 2 trajectories or fewer are within that noise.

**Per-group results.** Metric: category accuracy. Interval method: Wilson 95%.

| Factor | Group | n | Category | 95% interval |
|---|---|---|---|---|
| Method | gpt-6.1-sol one-shot (run 1; mean of 3 is 9.0/29) | 29 | 10/29 | 19.9–52.7% |
| Method | gpt-6.1-sol few-shot | 29 | 10/29 | 19.9–52.7% |
| Method | gpt-6-luna one-shot | 29 | 9/29 | 17.3–49.2% |
| Method | Keyword rule | 29 | 2/29 | 1.9–22.0% |

**Intersection (method × user-attributed failures):** gpt-6.1-sol 0/8 in every run, gpt-6-luna 0/8 (0.0–32.4%). Both judges usually relabel these as Instruction Adherence Failure, an agent failure. Every failure the annotators attributed to the user is attributed to the agent instead.

### Part B: reworded trajectories (preliminary)

Rewordings (step decomposition, step decoy, presentation change), each produced by three generator models (Haiku, Sonnet, Opus), were re-judged with sol. These results are reported elsewhere and are not part of this card yet, for two reasons:

- The deck's reworded results were compared against a baseline of 9/29 exact step and 7/29 category. The committed baseline above, on byte-identical inputs (same SHA-256), is 12/29 exact step and 8–10/29 category. Any rewording effect computed against 9/29 needs to be recomputed against this baseline.
- The `eval/` conditions on the baseline branch (A, B, C, clean, deepB, noise) are not documented, and the reworded trajectories behind them are not committed.

### Reading the results

- **Largest gap (category accuracy):** gpt-6.1-sol one-shot 10/29 (34.5%) vs. the keyword rule 2/29 (6.9%). The intervals (19.9–52.7% and 1.9–22.0%) overlap only at their edges. Among the LLM judges and configurations, no gap is larger than 1 trajectory.
- **AI vs. non-AI:** every LLM judge beats the keyword rule by a wide margin (category 8–10/29 vs. 2/29; exact step 8–12/29 vs. 0/29).
- **Judges and configurations:** on category, sol one-shot, sol few-shot and luna are within 1 trajectory of each other. No difference between them can be read from this data.
- **The user-attributed intersection** is the clearest failure pattern: 0 of 8 for both judges in every run.
- **Context only:** the paper reports 41.0 ± 2.1% step and 41.9 ± 2.4% category for one-shot +Vio on τ-bench. Our step result (12/29) is consistent with the step figure, but its interval spans 25.5–59.3%. Our category result is about 10 points lower.

## 4.8 Ethical considerations

- **Misattribution is the harm being measured.** A confidently wrong verdict points at an innocent component, team, or user while the real cause keeps working. At baseline this happens on most trajectories (20/29 on average for sol; 23/29 for luna).
- **Privacy:** the privacy scan found 65 email matches in the τ-bench traces, almost all `example.com` with 2 `gmail.com`, and no phone-like strings. [Confirm whether the 2 `gmail.com` addresses were redacted before the traces went to the judge.]
- **Dual use:** the reworded trajectories show how to misdirect the tracer. The generator, its prompts, and reworded trajectories are confidential and gated. Findings go to the AgentRx maintainers at Microsoft Research under coordinated disclosure on December 3, 2026, with instructor approval. Aggregate findings are published no earlier than 90 days after that notice (about March 3, 2027). Reworded variants and generator prompts are deleted when that window closes.
- **Data:** shared only within the team under the dataset's access terms.
- **Scoping conditions:** see 4.2.

## 4.9 Caveats and recommendations

- **Single runs.** Only sol one-shot has three runs. Luna, few-shot and every reworded set have one run, so their gaps have no spread of their own.
- **Reproducibility gaps on the baseline branch:**
  - The manifest's `git_commit` (`d6d41c6…`) does not exist in this repository.
  - `baselines/gen_manifest.py`, `scripts/run_tau_sol.sh` and `baselines/keyword_baseline.py` are referenced but not committed, so the keyword-baseline and eval results cannot be regenerated.
  - The reproducer hides scorer errors and prints a hard-coded headline, so a failed scorer run could print stale numbers.
  - Duplicate copies of the τ-bench data sit at the old paths beside the frozen `v1.0.0` copy.
- **Not measurable yet:** failed sub-agent (τ-bench is single-agent); trajectory length.
- **No per-category breakdown** beyond the user-attributed subgroup, although `score_runs.py` produces one.
- **The 0/8 result is not model-dependent.** The team decided to report it as a model-dependence finding, but both judges score 0/8. With the same AgentRx prompts and constraints for both, it is equally consistent with a prompt or taxonomy problem, or with a contested label boundary. The τ-bench labels have no agreement statistic.
- **Deviation from the proposal:** the proposal set a reproduction gate (τ-bench within ±5 points of 48.3% step and 39.1% category). It was dropped after the baseline run because the paper's judge model is not available to us. Results in this card are not a reproduction of the paper.
- **Judge selection on single runs:** sol was chosen over luna on one run each. The step gap (12 vs. 8 of 29) has overlapping intervals.
- **Judge-route difference:** Copilot-hosted judges, not the paper's GPT-5 on Azure. A silent model update would look like a rewording effect.
- **Recommendation:** don't use a category verdict to decide whether a user or the agent was at fault. Treat every committed verdict as a lead to verify, not a finding.
- **Cross-team review notes:** [paste from worksheet step 4]

## References

Barke, S., Goyal, A., Khare, A., Singh, A., Nath, S., & Bansal, C. (2026). *AgentRx: Diagnosing AI agent failures from execution trajectories*. arXiv. https://arxiv.org/abs/2602.02475

Barocas, S., et al. (2021). Designing disaggregated evaluations of AI systems: Choices, considerations, and tradeoffs. *AIES '21*, 368–378. https://doi.org/10.1145/3461702.3462610

Mitchell, M., et al. (2019). Model cards for model reporting. *FAT\* '19*, 220–229. https://doi.org/10.1145/3287560.3287596
