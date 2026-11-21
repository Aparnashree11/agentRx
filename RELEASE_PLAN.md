# AgentRx Release Plan v0

**Status:** Draft research release plan. The thresholds below are proposed gates for this project, not previously measured results.

## 1. Serving pattern and model versions

AgentRx is run as a local Python CLI (`python run.py`). It is not an AgentRx-hosted production service. The CLI runs the pipeline locally and calls a separately operated LLM provider through Copilot CLI, Azure OpenAI, or the internal TRAPI endpoint. Benchmark snapshots and run artifacts are stored as files; selected aggregate results may be published with the project.

The baseline experiment compares judge-model diagnoses on the same frozen trajectory, IR, invariant, and checker inputs. Planned judge candidates are `gpt-6.1-sol`, `gpt-6-luna`, and a third model selected before the run is frozen. For every release run, record the provider, exact model/deployment and version, API version if applicable, Copilot CLI version and Fusion tier if used, endpoint, run date, and relevant decoding settings. Keep the generated invariant and checker artifacts fixed while changing only the judge model.

The current Copilot setting `fusion` selects a provider-managed model and may not identify an immutable underlying model version. Such runs are exploratory unless the resolved model/version is recorded. Do not describe them as pinned-model results. Do not promote a release run if its model identity cannot be established. Only send benchmark traces to provider accounts whose data-use and retention terms permit this research.

To isolate judge-model effects, generate IR, static invariants, dynamic invariants, and checker results once, then reuse those artifacts for each judge. The current CLI uses the configured endpoint across stages; create a separate run directory per judge and resume each from the judge stage so the pre-judge inputs stay fixed. Record hashes of those shared inputs in the experiment record.

## 2. Pipeline stages, audience, retention, and expected cases

The current baseline has **29 Tau Retail trajectories with 29 labels**. Magentic-One has **58 trajectories, of which 44 have labels**. Baseline runs use the full available trajectory set; labeled accuracy metrics use only cases with matching ground truth.

| Stage | Output and who can see it | Expected cases / calls | Retention |
|---|---|---|---|
| **IR** | Normalized trajectories in `trajectory_ir.json`. Project researchers see the files. Conversion is normally local; if the domain converter falls back to the LLM converter, the configured provider also receives the input trace. | 29 Tau or 58 Magentic-One trajectories per run. | Keep with the restricted run artifacts for 12 months after the final project report; retain the released source snapshot and manifest with the research release. |
| **Static invariants** | Domain-level invariants. Researchers see prompts and results. The selected provider receives the policy, tool information, and sample trajectory used in the prompt. | Current runner generates one static-invariant set per input dataset, using its first trajectory as the sample. | Same as run artifacts; restrict prompt dumps to the project team. |
| **Dynamic invariants** | Per-trajectory assertions. Researchers see prompts and results; the provider sees the trajectory context and static invariants included in each prompt. | 29 or 58 trajectories. Step-by-step mode calls once per step; one-shot calls once per trajectory. | Same as run artifacts; restrict prompt dumps to the project team. |
| **Checker** | Violation and telemetry JSON. Python checks run locally. If NL checks are enabled, the configured provider also sees the evidence sent to that check. | All 29 or 58 trajectories. | Same as run artifacts. |
| **Judge** | Root-cause step and failure category. Researchers see outputs; the judge provider receives the trajectory and checker context required by the selected prompt mode. | One result per trajectory per judge model: 29 Tau; up to 58 Magentic-One. Evaluate labeled accuracy on 29 Tau and 44 Magentic-One cases. | Same as run artifacts. Keep model identity and prompt/config metadata with every result. |
| **Report** | Aggregate accuracy, localization, and model-agreement results for the project team, course reviewers, and research readers. Do not publish case-level traces or prompts unless their release is permitted. | Report every completed case and show the denominator for each metric. | Keep the final report and aggregate tables with the research release. |

**Retention proposal:** restrict per-case prompts, traces, and intermediate outputs to the project team and retain them for 12 months after the final report. Then delete them unless a course, institutional, publication, or provider requirement calls for a different period. Keep version manifests, code revision, model/config metadata, and aggregate results with the released study. Provider-side retention is governed by the provider and must be checked separately.

## 3. Promotion gate

Promotion means accepting a run as a reproducible research result; it does not mean deploying AgentRx for operational decisions.

**Gate metric:** complete, valid case coverage. **Threshold: 100%.** Before promotion, the dataset checksums must match the baseline manifests, every expected trajectory must have a parseable pipeline result for each judge model, and each result must contain a root-cause step and category. Minimum sample sizes are 29 Tau trajectories per judge model and 58 Magentic-One trajectories per model. Magentic-One accuracy claims require at least 44 ground-truth-matched cases; report the remaining 14 as unlabeled rather than counting them as correct or incorrect.

Report root-cause category accuracy and step-localization accuracy against ground truth, plus pairwise model agreement. Report each metric with its case count and uncertainty, grouped at minimum by domain, judge model, and rewording condition; include failure category where sample size permits. Include every subgroup flagged as a gap in the Week 9 review. The exact Week 9 subgroup list is not in this repository, so the project lead must add that list to the experiment record before sign-off. Do not use model agreement itself as a promotion threshold: disagreement between judges is a research outcome.

For a rewording release, require all 29 Tau cases per transformation, unchanged trajectory IDs and labels, and a documented label-preservation review before promoting the variant. Magentic-One transfer results are reported separately and must state the 58-trajectory / 44-labeled coverage.

## 4. Rollback

**Owner:** the project lead owns release decisions; the experiment owner stops a run and checks artifacts; the data owner restores the baseline snapshot and verifies checksums.

**Triggers:** a checksum mismatch; an unrecorded or changed model version; missing or invalid per-case output; a prompt, invariant, checker, or dataset change during a model comparison; or a data-handling/provider-policy issue.

**Steps:** stop promotion and mark the run as invalid or exploratory; preserve its logs for diagnosis; restore the Week 8 baseline if that snapshot is available, otherwise restore the last accepted frozen baseline and pipeline configuration; rerun the integrity and coverage gate. Roll back the model to the previous pinned version. If no model version can be pinned or the provider cannot be used under approved terms, switch off model calls and do not issue an AgentRx diagnosis. For comparison work, rollback is an integrity and reproducibility action, not an automatic decision to accept whichever model agrees more often.

## 5. User notice and recourse

For demos and reports, tell users that AgentRx is a research prototype, that its diagnosis is model-generated and can be wrong, which dataset release and model configuration produced the result, and that it must not be used as the sole basis for a real-world decision. Do not present an invariant violation as proof of root cause.

If a result appears wrong, users should be able to flag the run or trajectory ID to the project team. A researcher will review the source trace, IR, invariant, checker evidence, and judge output; correct the analysis if needed; and publish a new versioned result rather than silently overwriting a released artifact. Provide a manual review path, and allow the result to be excluded from an aggregate after documenting the reason.

## 6. Risk scope and release rules

**Medium-risk scope for v0:** offline academic experiments, code review, and supervised classroom demos using the versioned benchmark data. Outputs are advisory research artifacts for the project team. A person reviews any interpretation; the pipeline does not take actions on users, accounts, or external systems.

**High-risk uses are out of scope:** production monitoring or remediation, safety-critical workflows, or decisions affecting access to healthcare, finance, employment, education, legal outcomes, or other consequential services. Do not release AgentRx for those uses under v0. Any proposed high-risk use requires a separate risk, privacy, security, and domain review; representative validation data; named operational ownership; human oversight; incident handling; and an approved rollback path before a pilot.

For all releases, use immutable dataset and code versions, record model and prompt configuration, preserve audit evidence, and publish limitations and subgroup results. Never silently replace a released dataset, model configuration, or result.
