# RELEASE_PLAN.md — Fooling the Flight Recorder

**Team:** Uzma Fatima, Pranudeep Metuku, Aparna Shree Govindarajan · CS6170 AI Capstone, Fall 2026
**Version:** v0 · November 24, 2026
**Supersedes:** the earlier `RELEASE_PLAN.md` on `step-decoy` and `step-decomposition`, whose §3 gate ("require all 29 Tau cases per transformation") no rewording meets. The new gate is in Section 3.

## Release candidate

**The rewording framework:** a single tool that takes failed agent trajectories in any layout AgentRx reads, produces three label-preserving rewordings, stores each as a versioned dataset release, re-judges each release with AgentRx, and writes a report.

| Rewording | Generator (frozen) | What changes |
|---|---|---|
| Step decomposition | `claude-haiku-5-5` | The root-cause step is split into 2–4 smaller steps by the same actor |
| Step decoy | `claude-sonnet-5-5` | Noise replays and failed-attempt red herrings are inserted before the root cause |
| Presentation change | `claude-opus-5-5` | Wording, emphasis or JSON layout changes; nothing moves |

- **Commit:** the merge of `step-decomposition`, `presentation-change-v2` (which already contains `step-decoy`) and `baseline-results`, tagged `week11-release` once the branches are merged (tag not yet created). The tag must also contain the judge outputs behind every reported number, including the reference baseline run. None of the three rewording branches contains judge outputs yet.
- **Artifact:** there is no trained model file. The candidate is the framework code (`agentrx/rewordings/`) plus the frozen data releases under `data/benchmark_versions/`.
- **Fallback:** the Week 8 baseline (Section 4).

**Generator choice rule.** For each rewording, we chose the generator whose variants cause the largest drop in step accuracy against the baseline on the same task IDs, counted in trajectories, with ties broken by the lowest category accuracy:

- Presentation change: Opus (0), against Haiku (+2) and Sonnet (+4).
- Step decoy: Sonnet and Haiku tie at −3; Sonnet has the lower category accuracy (5/28 vs. 6/28).
- Step decomposition: Haiku and Opus tie at −1; Haiku has the lower category accuracy (3/16 vs. 3/15). This tie-break is decided by the denominator, not the count: both have 3 correct, and Haiku kept one more case (task 59).

This rule was written **after** the τ-bench results were seen. The choices rest on single runs and differences of 0–3 trajectories.

## 1. Serving pattern

**Published as data.** The framework runs offline as a command-line tool, operated by the team. Its outputs are versioned datasets and reports, not a live service.

**Frozen versions:**

| Component | Frozen version |
|---|---|
| AgentRx judge | gpt-6.1-sol via the GitHub Copilot API, one-shot (`--dynamic-mode oneshot`), single judge, all-at-once, full pipeline. The exact model version string is recorded in each run's logged artifacts. |
| Generators | `claude-haiku-5-5` (decomposition), `claude-sonnet-5-5` (decoy), `claude-opus-5-5` (presentation change); full IDs, not aliases; medium effort; via Claude Code (2.1.327 for step decoy; the version for each generator is recorded in its generation log). A run is refused if `modelUsage` reports a different model. |
| AgentRx | the upstream commit is recorded in each release manifest |
| Baseline data | `data/benchmark_versions/tau_retail/baseline/v1.0.0/`, pinned by SHA-256 |
| Releases | `data/benchmark_versions/<domain>/<rewording>/<model>/vX.Y.Z/`, each with a manifest of SHA-256 values, generator code hash, prompt hash and cost |

**The freezing problem.** "gpt-6.1-sol" is the name Copilot exposes, not a pinned model version. The provider can update the model behind that name without notice, and a silent update between the τ-bench runs and the Magentic-One run would look like a rewording effect. The same applies to Claude Code versions. To freeze:

1. Record the exact version string the judge reports in the run logs, and the Claude Code version for each generator, in the table above before the Magentic-One run.
2. Log the version on every run, and compare it with the frozen one before scoring.
3. If the version changed, stop, record it in the changelog, and rerun the τ-bench reference baseline on the new version before comparing anything.

Generator calls run isolated: `--safe-mode --tools "" --strict-mcp-config --disable-slash-commands --no-session-persistence`, an empty working directory, and structured JSON output.

## 2. Stages

| Stage | Who sees the outputs | How long | Expected cases |
|---|---|---|---|
| **0. τ-bench development, team only** (done) | The three of us | Done by Nov 24 | 29 trajectories × 3 rewordings × 3 generators, each judged once. Released with the chosen generators: decomposition 16, decoy 28, presentation change 29 |
| **0a. Results presentation** (Nov 24) | Instructor and class | One session | Aggregate τ-bench rates from single runs, labeled preliminary. No trajectories, prompts or generator code. |
| **1. Merge and freeze, team only** | The three of us | Nov 24 to Nov 30 | Merge the three rewording branches into one framework; freeze the judge and generator versions (Section 1) |
| **2. Magentic-One held-out run, team only** | The three of us | Dec 1 to Dec 3 | Up to 44 labeled traces per rewording, chosen generators only, run once. Decomposition will likely keep about half. Then produce the report. |
| **3. Disclosure** | AgentRx maintainers at Microsoft Research, with instructor approval | From Dec 3, 2026, for 90 days | Aggregate report, plus gated access to variants on request |
| **4. Class showcase** | Instructor and class | Dec 8 | Aggregate rates only. No trajectories, prompts or generator code. |
| **5. Public write-up** | Anyone | No earlier than about March 3, 2027 | Aggregate findings only |

Generator prompts, reworded trajectories and judge outputs on reworded data stay inside the team at every stage, except for gated maintainer access in Stage 3.

## 3. Freeze and run gate

The framework is run on Magentic-One only when every condition below holds, and nothing in it changes after that run.

**Frozen**
- The three branches are merged and tagged; the generator code, prompt and config hashes are recorded.
- The judge and generator versions are recorded as in Section 1.
- Known limits are written down before the run (below). They are disclosed in the report, not fixed afterwards, because changing the framework after seeing held-out results would undo the hold-out.

**Validity**
- Every automated check passes: structural checks, and for presentation change the independent `check_preserved()` re-check.
- Every released case has a signed review. The review sheets and the step-decoy suggestion script are committed.

**Same conditions**
- A clean Magentic-One baseline is run with the same command as every release, and every release is compared with it on the same task IDs.
- Judge outputs for every run are committed, so the report can be reproduced from the tag.

**Minimum cases**
- At least 15 kept variants per rewording. A rewording below that is reported as preliminary.

**Metrics**
- **Step accuracy:** the predicted step is within 2 steps of the label.
- **Category accuracy:** the predicted category matches the label (9 classes).
- **Matched change:** each release against the baseline on the same task IDs, in trajectories.
- **Variants kept** after checks and review, out of the traces attempted.
- **Threshold:** none. The project measures robustness rather than optimizing a model.

**Spread**
- Each release is judged once. On τ-bench, four baseline runs with the same command gave step accuracy 41.4% ± 0.0 and category accuracy 29.3% ± 4.5. A change is read as larger than run-to-run variation only if it exceeds that spread. Magentic-One's own spread is unknown; the report states this.

**Per group**
- Report every rate separately for user-attributed failures (Underspecified User Intent) and agent-attributed failures, and for traces whose root failure is a bare tool call vs. the rest.
- Mark any group under 10 cases as too small to support a conclusion.

**Known limits, disclosed rather than fixed**
- **Decoy:** 100 of 122 τ-bench red herrings use error strings that never appear in the real data. Most swap the last two characters of an ID. Some replays sit directly after the call they copy.
- **Presentation change:** 16–27% of formatting edits are erased by AgentRx's IR converter before the judge sees them. Some emphasis edits bold the mistake itself.
- **Decomposition:** no check flags IDs the original step didn't contain (task 32 passed review with an added clue). Consecutive messages from the same actor never occur in the original data. Bare-tool-call roots can't be decomposed.
- **Step accuracy within ±2** can count a judge that lands on an adjacent decoy or split step as correct.

**Magentic-One setup (required)**
- Decide which agents count as "prose" roles for presentation change.
- Redact the 188 phone-like strings and 10 email addresses before any trace goes to a generator or the judge.

## 4. Rollback

**Owner:** Pranudeep Metuku, data steward

**Triggers.** Roll back when any of these happens:
- a released variant turns out to change the true failure (a validity failure found after release);
- a manifest or input SHA-256 doesn't match;
- the judge or a generator answers with a model version other than the frozen one;
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
- the frozen judge and generator versions, and the commit and data versions used;
- each rate with its count and interval, how many runs it rests on, and which groups are too small to read;
- that verdicts are leads to verify, not findings, and that a category label is not evidence of whether the user or the agent was at fault;
- the known limits (Section 3), which were not fixed in this release.

**Changes (G18):** each new release version is listed in a changelog in `data/benchmark_versions/README.md`. The entry says what changed and why, and gives the new SHA-256 values. A model version change is logged there too. Maintainers who have access get a note when a release they use is replaced or withdrawn.

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
| Modest compute | Spending is capped per the team's compute budget per rewording per domain. τ-bench cost, generation + judging: decomposition with Haiku $0.16 + $3.88; decoy with Sonnet $2.30 + $2.56; presentation change with Opus $5.10 + $3.16; baseline judging $7.52. |
| Findings written for the maintainers | The first audience outside the team is the AgentRx maintainers (Stage 3). Nothing is shown publicly before Dec 3, and nothing is published before the window closes. |

**Confidentiality:** the generators, their prompts and the reworded trajectories are confidential and gated. The repository holding them, and the gated τ-bench data, stays private; `Aparnashree11/agentRx` is a private repository. They are deleted when the disclosure window closes (about March 3, 2027), unless the maintainers ask in writing to keep them.
