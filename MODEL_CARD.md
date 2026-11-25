# Model Card: AgentRx failure attribution under label-preserving rewordings

Sections follow Mitchell et al. (2019), Section 4. Evaluation type: exploratory (Barocas et al., 2021). Every rate carries its count. Intervals are Wilson 95%.

## 4.1 Model details

- **Team:** Fooling the Flight Recorder (Aparna, Uzma, Pranudeep), CS6170 AI Capstone, Track A.
- **Date:** November 24, 2026
- **Version:** v1
- **Commits:**
  - Stability runs: [`ac01913`](https://github.com/Aparnashree11/agentRx/commit/ac019130950b52ac99d233b628a5965eef241e44), "Add Track-A tau-bench baseline results (sol + luna)", branch `baseline-results`, November 19, 2026.
  - Reference run and all reworded releases: `presentation-change-v2@2b7df0c`, November 23–24, 2026.
  - Framework: branch `framework-development`, which merges the three rewording branches and `baseline-results` and runs the chosen generators through the GitHub Copilot CLI. Not yet tagged; the `week11-release` tag will record its commit.
- **Model type:** AgentRx (Barke et al., 2026, arXiv 2602.02475), used unmodified as a gray-box system. It synthesizes constraints from a failed agent trajectory, then an LLM judge names (1) the critical failure step and (2) one of nine failure categories, or returns "inconclusive." No model is trained by our team.
- **Configuration:** one-shot constraint synthesis, single judge, all-at-once, full pipeline. Command, identical for every run in this card: `run.py --domain tau --endpoint copilot --dynamic-mode oneshot`. Every run in this card used the judge model's default reasoning effort. The framework now pins medium effort (`AGENT_VERIFY_COPILOT_REASONING_EFFORT=medium`), so the clean baseline must be rerun with that setting before it is compared with any new release.
- **Judges:** reached through the GitHub Copilot API, not Azure OpenAI as in the paper.
  - gpt-6.1-sol: primary judge. Four one-shot runs on the original trajectories (three stability runs and one reference run) and one run on each reworded release. Every run in this card is one-shot.
  - gpt-6-luna: comparison judge, one run.
- **Rewording generators:**
  - *Model-comparison study (every release in this card):* Claude Haiku 5.5, Sonnet 5.5 and Opus 5.5 (`claude-*-5-5`) through Claude Code, medium effort, isolated (no tools, empty working directory, structured output). All three were run on every rewording.
  - *Framework (from now on):* one finalized model per rewording, through the GitHub Copilot CLI, the same route as the judge: `claude-haiku-5.5` for step decomposition, `claude-sonnet-5.5` for step decoy and `claude-opus-5.5` for presentation change, all at medium effort. Each is set by its own environment variable (`STEP_DECOMPOSITION_COPILOT_MODEL`, `STEP_DECOY_COPILOT_MODEL`, `PRESENTATION_CHANGE_COPILOT_MODEL`), with no command-line override. Calls are isolated (no tools, no MCP servers, no custom instructions, empty working directory), and a call is refused if the session reports a different model or effort.
  - Each variant passes automated structural checks and a signed human review before release.
- **Frozen versions:** "gpt-6.1-sol" is the name Copilot exposes, not a pinned model version, so the provider can change the model behind it without notice. The exact judge version string is recorded in the run logs. Every run logs the version; a change stops the run and the τ-bench baseline is rerun before any comparison (RELEASE_PLAN.md §1).
- **Scorer:** `baselines/score_runs.py` for the stability runs, and the evaluation report generator for the reference run and releases. The evaluation report generator is not committed. Category labels are matched by number or keyword.
- **Reproduction:** `bash scripts/reproduce_baseline.sh` checks the SHA-256 of five pinned inputs and re-scores the three stability runs without credentials, network access or LLM calls. New judge runs need Copilot credentials and vary between runs.

### How the judge was chosen

gpt-6.1-sol and gpt-6-luna were each run once on the 29 τ-bench trajectories. Sol was chosen because it localized more steps (12/29 vs. 8/29); the two were level on category (10/29 vs. 9/29). Luna was not run again because it was not carried forward. Because the judge is an LLM and its output varies, sol was run again on the same trajectories with the same command, so the baseline is reported as a mean over four runs rather than a single value.

## 4.2 Intended use

- **Primary use:** a research measurement of whether AgentRx's verdict stays the same when a failed trajectory is reworded without changing what went wrong.
- **Primary users:** our team; AgentRx's maintainers (recipients of the coordinated disclosure); debugging and security engineers deciding how far to trust an AgentRx verdict.
- **Out-of-scope uses:**
  - Assigning blame to a person, team, vendor, or sub-agent based on a verdict alone. At baseline, the judge commits to a wrong step or category on 20/29 τ-bench trajectories on average (sol, 3 stability runs).
  - Use of the category label as evidence of whether the user or the agent caused a failure (see 4.7: 0/8 on user-attributed failures).
  - Ranking the generator models by quality. They are used only to produce rewordings.
  - Any claim about multi-agent systems, production incidents (Flash, not public), or live traffic. τ-bench is the development set; Magentic-One is the held-out test and has not been run with rewordings.
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
| Validity reviewer | Direct | Accepts a variant that changed the failure, so a corrupted case enters the results |
| Governance leads choosing a tool | Direct | Adopt a tracer whose verdict changes with the wording of the log |
| Incident responders | Indirect | Spend hours on the wrong component |
| Sub-agent owners, component teams, vendors | Indirect | Blamed for a failure they didn't cause |
| End users / customers (incl. the simulated user in τ-bench) | Indirect | Blamed for "underspecified intent" when the agent failed, or the reverse |
| Adversary who wants the trace to mislead | Indirect | Rewords a log so the verdict points elsewhere |

### Evaluation factors

Type codes: G = groups of people, I = instrumentation, E = environment.

| Stakeholder | Type | Groups | How identified in the test split | n |
|---|---|---|---|---|
| Governance leads, maintainers | I | Judge model: sol, luna | Run config | 29 each |
| End users vs. agent (who is blamed) | G | User-attributed (Underspecified User Intent) vs. agent-attributed | Human root-cause label | 8 vs. 21 |
| Validity reviewer, engineers | E | Root failure is a bare tool call (no agent text) vs. a narrated step | Root step in the trajectory | 12 vs. 17 |
| Engineers, adversary | E | Rewording: none, presentation change, step decoy, step decomposition | Release | 29 / 28–29 / 27–28 / 15–16 |
| Maintainers | I | Generator: Haiku, Sonnet, Opus | Release | 15–29 per release |
| Sub-agent owners | G | Failed sub-agent | — | not measurable yet (τ-bench has a single agent) |
| Incident responders | E | Trajectory length | — | not measurable yet |

## 4.4 Metrics

- **Step accuracy:** the predicted critical step is within 2 steps of the labeled step.
- **Category accuracy:** the predicted category matches the human label (9 classes). Primary metric for disaggregation.
- **Also reported:** exact-step match; both correct; confidently wrong (a committed verdict with the step or category wrong); inconclusive; variants kept after review.
- **Matched comparison:** each release is compared with the baseline on the same task IDs. Reported as a change in trajectories.
- **Threshold:** none. The paper's judge (GPT-5 on Azure OpenAI) is not available to us, so the paper's figures are not a reproduction target.
- **Spread:** sol on the original trajectories, mean ± sample standard deviation over 4 runs. Every other configuration and every release was run once.
- **Interval method:** Wilson 95% score interval.

## 4.5 Evaluation data

- **Development set:** 29 failed τ-bench retail trajectories, all of them human-labeled, from `microsoft/AgentRx` on Hugging Face (CC BY 4.0, gated), retrieved October 27, 2026. Frozen as `data/benchmark_versions/tau_retail/baseline/v1.0.0/` and pinned by SHA-256. The labeled set is used whole. Prompts were tuned and generators chosen on it.
- **Held-out test:** Magentic-One (44 labeled traces), to be run once with the frozen framework: the merged code, the three chosen generators and the frozen judge. Not reported in this card.
- **Reworded releases:** `data/benchmark_versions/tau_retail/<rewording>/<model>/v0.1.0/` (the model-comparison study), each with its own remapped labels. Each release keeps only the variants that passed checks and review (15–29 of 29). Framework releases are written to `data/benchmark_versions/<domain>/<rewording>/vX.Y.Z/` from v0.2.0, with the generator model and effort in the manifest.
- **Preprocessing:** none. Ground-truth labels are used as released. An adapter converts raw messages to sub-steps without loss (1,064 = 1,064).
- **Label audit (`results/data_checks.json`):** 29 traces and 29 labels, all matched. 39 failure entries, at most 4 per trajectory. In 2 trajectories the labeled root cause is not the earliest failure. Category names are spelled inconsistently in the dataset; the scorer matches categories by number or keyword.
- **Known limit:** τ-bench uses an LLM-simulated customer and a single assistant, so sub-agent misattribution can't be studied on this split.

## 4.6 Training data

No training by our team. AgentRx and the generators are used as released. The training data of the judge and generator models is not disclosed by their providers, so contamination with the public benchmark can't be ruled out.

## 4.7 Quantitative analyses

### Part A: baseline on the original trajectories (n = 29)

| Method | Runs | Step accuracy | Category | Both correct | Confidently wrong |
|---|---|---|---|---|---|
| gpt-6.1-sol, one-shot, stability runs | 3 | 12/29 every run | 10, 8, 9 /29 | 8, 7, 8 /29 | 20, 21, 19 /29 |
| gpt-6.1-sol, one-shot, reference run | 1 | 12/29 (exact step 9/29) | 7/29 | not recorded | not recorded |
| **gpt-6.1-sol, one-shot, all 4 runs** | 4 | **41.4% ± 0.0** (25.5–59.3%) | **29.3% ± 4.5** | — | — |
| gpt-6-luna, one-shot | 1 | 8/29, 27.6% (14.7–45.7%) | 9/29, 31.0% (17.3–49.2%) | 5/29, 17.2% (7.6–34.5%) | 23/29, 79.3% (61.6–90.2%) |

Across the four sol runs, step accuracy did not move (12/29 each) and category accuracy moved between 7 and 10 of 29.

**Per-group results.** Metric: category accuracy. Interval method: Wilson 95%.

| Factor | Group | n | Category | 95% interval |
|---|---|---|---|---|
| Method | gpt-6.1-sol one-shot (4 runs) | 29 | 29.3% ± 4.5 (10, 8, 9, 7 of 29) | run range 24.1–34.5% |
| Method | gpt-6-luna one-shot | 29 | 9/29 | 17.3–49.2% |
| Who is blamed | User-attributed (sol, 4 runs) | 8 | 0/8 every run | 0.0–32.4% |
| Who is blamed | Agent-attributed (sol, 4 runs) | 21 | 40.5% ± 6.1 (10, 8, 9, 7 of 21) | run range 33.3–47.6% |
| Who is blamed | User-attributed (luna, 1 run) | 8 | 0/8 | 0.0–32.4% |
| Who is blamed | Agent-attributed (luna, 1 run) | 21 | 9/21 | 24.5–63.5% |

**Intersection (method × user-attributed failures):** gpt-6.1-sol 0/8 in all four runs, gpt-6-luna 0/8 (0.0–32.4%). Both judges usually relabel these as Instruction Adherence Failure, an agent failure. Every failure the annotators attributed to the user is attributed to the agent instead.

### Part B: reworded trajectories (gpt-6.1-sol, one run per release)

| Release | Kept /29 | Step accuracy | Δ vs. baseline, same IDs | Category |
|---|---|---|---|---|
| Baseline (reference run) | 29 | 12/29 · 41.4% | — | 7/29 · 24.1% |
| Presentation change · Haiku | 29 | 14/29 · 48.3% | +2 | 8/29 · 27.6% |
| Presentation change · Sonnet | 28 | 16/28 · 57.1% | +4 | 9/28 · 32.1% |
| Presentation change · Opus ★ | 29 | 12/29 · 41.4% | 0 | 7/29 · 24.1% |
| Step decoy · Haiku | 28 | 9/28 · 32.1% | −3 | 6/28 · 21.4% |
| Step decoy · Sonnet ★ | 28 | 8/28 · 28.6% | −3 | 5/28 · 17.9% |
| Step decoy · Opus | 27 | 10/27 · 37.0% | 0 | 6/27 · 22.2% |
| Step decomposition · Haiku ★ | 16 | 5/16 · 31.2% | −1 | 3/16 · 18.8% |
| Step decomposition · Sonnet | 15 | 7/15 · 46.7% | +1 | 4/15 · 26.7% |
| Step decomposition · Opus | 15 | 5/15 · 33.3% | −1 | 3/15 · 20.0% |

★ = generator chosen for the framework: the largest drop in step accuracy against the baseline, ties broken by the lowest category accuracy. This rule was set after the results were seen.

**Per-group results: root failure type.** Variants kept after review, and AgentRx step accuracy on the kept bare-tool-call cases against the baseline on the same cases.

| Release | Kept: bare tool-call root (n = 12) | Kept: other roots (n = 17) | Step accuracy on kept bare-tool-call cases |
|---|---|---|---|
| Baseline (reference run) | 12 | 17 | 6/12 |
| Decomposition · Haiku / Sonnet / Opus | 0 / 0 / 0 (0.0–24.3%) | 16 / 15 / 15 | not measurable (n = 0) |
| Step decoy · Haiku | 11 | 17 | 5/11 (baseline 6/11) |
| Step decoy · Sonnet | 11 | 17 | 4/11 (baseline 5/11) |
| Step decoy · Opus | 10 | 17 | 6/10 (baseline 4/10) |
| Presentation change · Haiku | 12 (3 regenerated) | 17 | 6/12 (baseline 6/12) |
| Presentation change · Sonnet | 11 | 17 | 8/11 (baseline 6/11) |
| Presentation change · Opus | 12 | 17 | 4/12 (baseline 6/12) |

41 of the 46 rejected, invalid or excluded variants across the nine releases come from the 12 bare-tool-call trajectories. A bare tool call has no agent text to split or reword without inventing some.

### Reading the results

- **Largest gap (generator):** decomposition keeps 0 of 12 bare-tool-call trajectories against 15–16 of 17 elsewhere. The intervals do not overlap.
- **Largest gap (AgentRx, category accuracy):** user-attributed 0/8 against agent-attributed 40.5% ± 6.1, in every sol run and in luna. The user-attributed group is small (n = 8).
- **Against spread:** across four baseline runs, step accuracy did not move and category moved by up to 3 trajectories. The step changes of +4 (presentation change, Sonnet) and −3 (step decoy, Haiku and Sonnet) are larger than the baseline's run-to-run variation; no category change is. Each release was judged once, so these need repeat runs to confirm.
- **Direction:** presentation change never lowered step accuracy and step decoy never raised it, for all three generators.
- **Context only:** the paper reports 41.0 ± 2.1% step and 41.9 ± 2.4% category for one-shot +Vio on τ-bench with a different judge. These numbers are not a target for this card.

## 4.8 Ethical considerations

- **Misattribution is the harm being measured.** A confidently wrong verdict points at an innocent component, team, or user while the real cause keeps working. At baseline this happens on most trajectories (20/29 on average for sol; 23/29 for luna).
- **Validity of rewordings.** A variant that changes the true failure would be counted as AgentRx being fooled. Every released variant passed structural checks and a signed review; task 32 in two decomposition releases passed review but adds a clue to the mistake.
- **Privacy:** the privacy scan found 65 email matches in the τ-bench traces, almost all `example.com` with 2 `gmail.com`, and no phone-like strings. The 2 `gmail.com` addresses are flagged for redaction before any trace goes to a model API. Magentic-One traces contain 10 email matches and 188 phone-like strings and must be redacted before the held-out run.
- **Dual use:** the reworded trajectories show how to misdirect the tracer. The generator, its prompts, and reworded trajectories are confidential and gated. Findings go to the AgentRx maintainers at Microsoft Research under coordinated disclosure on December 3, 2026, with instructor approval. Aggregate findings are published no earlier than 90 days after that notice (about March 3, 2027). Reworded variants and generator prompts are deleted when that window closes.
- **Data:** shared only within the team under the dataset's access terms.
- **Scoping conditions:** see 4.2.

## 4.9 Caveats and recommendations

- **Single runs.** Only sol on the original trajectories has repeated runs (4). Luna and every reworded release have one run.
- **Step accuracy definition.** The stability runs' step figure (12/29) is taken as within ±2, as the baseline results report states.
- **Step accuracy can hide decoy and decomposition effects.** A judge that lands on an adjacent decoy or split step counts as correct within ±2. The paired rates from each rewording's `compare()` check the exact step and are not yet reported.
- **Small and uneven releases.** Decomposition keeps 15–16 of 29 trajectories and none of the bare-tool-call ones, so its results cover a narrower set than the baseline. Tasks 2, 3 and 4 are the same mistake.
- **Known tells in the releases:** 100 of 122 decoy red herrings use error strings that never occur in the real data. AgentRx's converter erases 16–27% of all presentation-change edits before the judge reads them: every layout-only reformatting of a JSON tool response, which is 30–47% of the formatting edits (Opus, the chosen generator: 39 of 131). Other tells: consecutive messages from the same actor appear only in decomposition variants; no check flags IDs a decomposed step didn't contain. These are not fixed before the Magentic-One run and will be disclosed in its report, because changing the framework after seeing held-out results would undo the hold-out.
- **Changes made after seeing results:** the generator-choice rule; dropping the proposal's reproduction gate. For the framework, also after the τ-bench results:
  - the generators moved from Claude Code to the GitHub Copilot CLI;
  - presentation change no longer regenerates rejected or invalid cases (one attempt per case; failures are excluded with their reason);
  - the judge's reasoning effort is pinned to medium.

  None of these has been run on τ-bench yet.
- **Reproducibility gaps:**
  - The baseline manifest's `git_commit` (`d6d41c6…`) does not exist in this repository.
  - `baselines/gen_manifest.py` and `scripts/run_tau_sol.sh` are referenced but not committed.
  - Judge outputs for the reference run and the nine releases are local and not committed; only the three stability runs' outputs are (`results/baseline/artifacts/`).
  - The evaluation report generator that scored the reference run and the releases is not committed.
  - The reproducer hides scorer errors and prints a hard-coded headline.
- **Not measurable yet:** failed sub-agent (τ-bench is single-agent); trajectory length.
- **The 0/8 result is not model-dependent.** Both judges score 0/8. With the same AgentRx prompts and constraints for both, it is equally consistent with a prompt or taxonomy problem, or with a contested label boundary. The τ-bench labels have no agreement statistic.
- **Judge selection on single runs:** sol was chosen over luna on one run each. The step gap (12 vs. 8 of 29) has overlapping intervals.
- **Generator-route difference:** every release in this card was generated through Claude Code. Framework releases are generated through the GitHub Copilot CLI with the same model families. Whether Copilot-served models produce the same kind of rewordings is untested.
- **Judge-route difference and model drift:** Copilot-hosted judges, not the paper's GPT-5 on Azure. The model name is not a pinned version; a silent update between the τ-bench and Magentic-One runs would look like a rewording effect. The exact version strings must be recorded before the held-out run.
- **Single judge run on the held-out set.** Each Magentic-One release will be judged once, so its own spread will be unknown; the τ-bench baseline spread (4 runs) is the only reference.
- **Recommendation:** don't use a category verdict to decide whether a user or the agent was at fault, and don't treat a step verdict as stable if the log's format may have changed. Treat every committed verdict as a lead to verify.
- **Cross-team review notes:** none recorded in this version.

## References

Barke, S., Goyal, A., Khare, A., Singh, A., Nath, S., & Bansal, C. (2026). *AgentRx: Diagnosing AI agent failures from execution trajectories*. arXiv. https://arxiv.org/abs/2602.02475

Barocas, S., et al. (2021). Designing disaggregated evaluations of AI systems: Choices, considerations, and tradeoffs. *AIES '21*, 368–378. https://doi.org/10.1145/3461702.3462610

Mitchell, M., et al. (2019). Model cards for model reporting. *FAT\* '19*, 220–229. https://doi.org/10.1145/3287560.3287596
