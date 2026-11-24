# RELEASE_PLAN.md — Fooling the Flight Recorder

**Team:** Uzma Fatima, Pranudeep Metuku, Aparna Shree Govindarajan · CS6170 AI Capstone, Fall 2026
**Version:** v0 · November 24, 2026
**Supersedes:** the earlier `RELEASE_PLAN.md` on `step-decoy` and `step-decomposition`, whose §3 gate ("require all 29 Tau cases per transformation") no rewording meets. The new gate is in Section 3.

## Release candidate

**The rewording framework:** a single tool that takes failed agent trajectories in any layout AgentRx reads, produces three label-preserving rewordings, stores each as a versioned dataset release, re-judges each release with AgentRx, and writes a comparison report.

| Rewording | Generator | What changes | Paired metric (`compare()`) |
|---|---|---|---|
| Step decomposition | Claude Haiku 5.5 | The root-cause step is split into 2–4 smaller steps by the same actor | `decomposition_evasion_rate` |
| Step decoy | Claude Sonnet 5.5 | Noise replays and failed-attempt red herrings are inserted before the root cause | `decoy_attraction_rate` |
| Presentation change | Claude Opus 5.5 | Wording, emphasis or JSON layout changes; nothing moves | `verdict_flip_rate` |

- **Commit:** the merge of `step-decomposition`, `presentation-change-v2` (which already contains `step-decoy`) and `baseline-results`, tagged `week11-release` once the branches are merged (tag not yet created). The tag must also contain the judge outputs behind every reported number, including the clean baseline run the rewordings were compared against. None of the three rewording branches contains judge outputs yet.
- **Artifact:** there is no trained model file. The candidate is the framework code (`agentrx/rewordings/`) plus the frozen data releases under `data/benchmark_versions/`.
- **Fallback:** the Week 8 baseline (Section 4).

**Generator choice rule.** For each rewording, we choose the generator whose variants cause the largest drop in step accuracy (±2) against the baseline, counted in trajectories, and break ties by the lowest category accuracy (decoy: Sonnet 5/28 vs. Haiku 6/28; decomposition: Haiku 3/16 vs. Opus 3/15). The decomposition tie-break is decided by the denominator, not the count: both have 3 correct, and Haiku has one more accepted case (task 59, which Sonnet and Opus failed review on). This rule was written **after** the τ-bench results were seen. The choices rest on single runs and differences of 0–3 trajectories. They will be re-checked against the committed baseline (Section 3) before the Magentic-One stage.

## 1. Serving pattern

**Published as data.** The framework runs offline as a command-line tool, operated by the team. Its outputs are versioned datasets and reports, not a live service.

**Pinned versions:**

| Component | Pinned version |
|---|---|
| Judge | gpt-6.1-sol via the GitHub Copilot API, one-shot (`--dynamic-mode oneshot`), single judge, all-at-once. The exact model version string is recorded in each run's logged artifacts. |
| Generators | `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5` (full IDs, not aliases), medium effort, via Claude Code (version recorded in each generation log). The run is refused if `modelUsage` reports a different model. |
| AgentRx | the upstream commit is recorded in each release manifest |
| Baseline data | `data/benchmark_versions/tau_retail/baseline/v1.0.0/`, pinned by SHA-256 |
| Releases | `data/benchmark_versions/tau_retail/<rewording>/<model>/v0.1.0/`, each with a manifest of SHA-256 values, generator code hash, prompt hash and cost |

Generator calls run isolated: `--safe-mode --tools "" --strict-mcp-config --disable-slash-commands --no-session-persistence`, an empty working directory, and structured JSON output.

## 2. Stages

| Stage | Who sees the outputs | How long | Expected cases |
|---|---|---|---|
| **0. τ-bench, team only** (generation and review done; gate in Section 3 not yet met) | The three of us | Until Nov 30 | 29 trajectories × 3 rewordings. Released: decomposition 16, decoy 28, presentation change 29 |
| **0a. Results presentation** (Nov 24) | Instructor and class | One session | Aggregate τ-bench rates from single runs, labeled preliminary. No trajectories, prompts or generator code. |
| **1. Magentic-One, team only** | The three of us | Dec 1 to Dec 3 | Up to 44 labeled traces per rewording (38 were scored at baseline). Decomposition will likely accept about half. Paired cases are limited to traces the clean run gets right. |
| **2. Disclosure** | AgentRx maintainers at Microsoft Research, with instructor approval | From Dec 3, 2026, for 90 days | Aggregate report, plus gated access to variants on request |
| **3. Class showcase** | Instructor and class | Dec 8 | Aggregate rates only. No trajectories, prompts or generator code. |
| **4. Public write-up** | Anyone | No earlier than about March 3, 2027 | Aggregate findings only |

Generator prompts, reworded trajectories and judge outputs on reworded data stay inside the team at every stage, except for gated maintainer access in Stage 2.

## 3. Promotion gate

A rewording moves from one stage to the next only if every condition below holds.

**Validity**
- Every automated check passes: structural checks, and for presentation change the independent `check_preserved()` re-check.
- Every released case has a signed review whose reason names something specific to that case. Boilerplate reasons don't count.
- The review scripts and review sheets are committed. The step-decoy suggestion script is not committed yet.

**Minimum cases**
- At least 15 accepted variants per rewording.
- At least 8 paired cases. A paired case is one the clean run got right. Tasks 2, 3 and 4 count as one case.
- A rewording that misses either minimum is reported as preliminary and is not promoted. Decomposition is at risk: its 16 accepted τ-bench cases overlap with only the trajectories the clean run localized correctly. The paired-case count per rewording is computed at the Magentic-One stage.

**Same conditions**
- A clean baseline run with the same judge config is committed, and every variant is compared against it.
- Judge outputs for every variant run are committed, so the report can be reproduced from the tag.

**Spread**
- Each release is judged at least 3 times. A rate is reported as mean ± standard deviation, with its n.

**Metrics and thresholds**
- **Primary:** the paired rate for each rewording (table above), with its count and Wilson 95% interval. The gate does not require a minimum effect size, because the project measures robustness rather than optimizing a model. A rewording counts as "moving the verdict" only if its rate is larger than the clean run's own run-to-run flip rate on the same cases, computed from the three committed sol runs.
- **Secondary:** category accuracy, and step accuracy, defined as the predicted step being within 2 steps of the label. Step accuracy alone would count a judge that picks an adjacent decoy or split step as correct; the paired rates above catch that, because `compare()` checks whether the judge landed on the real root, a decoy, or a split step.
- **Metric change disclosure:** the Week 7 card named exact-step accuracy as the headline metric. We changed it to step accuracy (±2) after seeing the results.

**Per group (Week 9 gap)**
- Report every rate separately for user-attributed failures (Underspecified User Intent, n = 8 on τ-bench, 0/8 at baseline) and agent-attributed failures (n = 21).
- Mark any group under 10 cases as too small to support a conclusion.

**Before Stage 1, fix or disclose the known tells**
- **Decoy:** 100 of 122 red herrings use error strings that never appear in the real data. Most swap the last two characters of an ID. Some replays sit directly after the call they copy.
- **Presentation change:** 16–27% of formatting edits are erased by AgentRx's IR converter before the judge sees them. Some emphasis edits bold the mistake itself.
- **Decomposition:** task 32 adds a clue to the mistake. Consecutive messages from the same actor never occur in the original data.
- **Magentic-One setup:** decide which agents count as "prose" roles for presentation change. Redact the 188 phone-like strings and 10 email addresses before any trace goes to a generator or the judge.

## 4. Rollback

**Owner:** Pranudeep Metuku, data steward

**Triggers.** Roll back when any of these happens:
- a released variant turns out to change the true failure (a validity failure found after release);
- a manifest or input SHA-256 doesn't match;
- the judge or a generator answers with a model version other than the pinned one;
- a report's numbers can't be reproduced from the tag;
- a disclosure or confidentiality term is breached. In that case, withdraw the release and notify the instructor.

**Target:** the Week 8 baseline. Merge `baseline-results` without squashing, and keep the branch, so that `ac01913` stays reachable. It is the frozen `tau_retail/baseline/v1.0.0` data with the committed sol runs at [`ac01913`](https://github.com/Aparnashree11/agentRx/commit/ac019130950b52ac99d233b628a5965eef241e44), which AgentRx scores with no rewording. For a single bad rewording release, the target is that rewording's previous version.

**Steps:**
1. Record the current commit, data versions and judge version (the rehearsal table below).
2. `git fetch --tags && git checkout ac01913`
3. `bash scripts/reproduce_baseline.sh`
4. Check the **computed** values against the known output. The script's "HEADLINE … reproduced" line is hard-coded and doesn't count as a check.
   - Step accuracy: 0.4138 for all three runs.
   - Category accuracy: 0.3448, 0.2759 and 0.3103.
5. Mark the withdrawn release as withdrawn in `data/benchmark_versions/README.md`, and add a line to the changelog (Section 5).

### Rollback rehearsal

No rehearsal has been run yet. The known input/output for a future rehearsal: 29 τ-bench trajectories and 3 sol runs reproduce step 0.4138 ×3 and category 0.3448 / 0.2759 / 0.3103, against target `ac01913` / `tau_retail/baseline/v1.0.0`.

## 5. What users are told (G18), and what they can do when the output is wrong (G9)

**Users** are AgentRx maintainers, and engineers or researchers who read the report.

**Every report states:**
- the judge and generator versions, and the commit and data versions used;
- each rate with its count and interval, how many runs it rests on, and which groups are too small to read;
- that verdicts are leads to verify, not findings, and that a category label is not evidence of whether the user or the agent was at fault;
- the known tells (Section 3) and whether they were fixed.

**Changes (G18):** each new release version is listed in a changelog in `data/benchmark_versions/README.md`. The entry says what changed and why, and gives the new SHA-256 values. Maintainers who have access get a note when a release they use is replaced or withdrawn.

**When a variant or rate looks wrong (G9):**
- **Trace it.** Every released case has an `audit.json` entry with the proposal, the review, and the step map from original to variant steps, so a reader can check the exact case.
- **Report it.** Open an issue, or contact Uzma Fatima (validity review and disclosure), naming the release and the case ID.
- **Expect a fix.** A confirmed bad case is removed in a new patch version (for example v0.1.1), the report is regenerated, and the changelog records the case and the reason. Old versions are never overwritten.

## 6. Scoping conditions as release rules (high-risk project)

The binding text is Specification §8, which the Development Contract (§2) makes a term of the contract. As restated in proposal §6:

| Scoping condition | Release rule |
|---|---|
| Text-only attacks | The framework changes only trajectory text and JSON layout. No code execution, no changes to tools or the environment, and no edits outside the trajectory. |
| One auditor (AgentRx) | Results are reported for AgentRx only. A second tool requires a new plan and instructor approval. |
| Three attack classes | The release contains exactly three rewordings: decomposition, decoy and presentation change. A new class needs a plan change. |
| Sandboxed runs | Every generator call uses the isolation flags in Section 1. A run without them is refused. |
| Modest compute | Spending is capped per the team's compute budget per rewording per domain. τ-bench cost: about $0.16 (decomposition with Haiku), $2.30 (decoy with Sonnet) and $5.10 (presentation change with Opus). |
| Findings written for the maintainers | The first audience outside the team is the AgentRx maintainers (Stage 2). Nothing is shown publicly before Dec 3, and nothing is published before the window closes. |

**Confidentiality:** the generators, their prompts and the reworded trajectories are confidential and gated. The repository holding them, and the gated τ-bench data, stays private; `Aparnashree11/agentRx` is a private repository. They are deleted when the disclosure window closes (about March 3, 2027), unless the maintainers ask in writing to keep them.
