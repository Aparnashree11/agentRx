# AgentRx benchmark releases

This folder contains immutable releases of the benchmark data already used by
the project. The baseline files are byte-for-byte copies of the existing local
inputs and labels. They have not been cleaned, normalized, filtered, or
converted. The manifests preserve the original source paths for provenance, but
the frozen release artifacts are self-contained and do not depend on those
original folders being present.

## Baseline releases

- `tau_retail/baseline/v1.0.0/manifest.json`

Each manifest records the original project paths, the copied artifact paths,
trajectory IDs, row counts, and SHA-256 checksums. Tau Retail freezes the 29
failed trajectories and their 29 labels. The Tau release is scoped to the 29
failed trajectories and does not include the broader 100-row Tau pool.

## Adding reworded datasets

Create a new release directory rather than editing a released version. For
example:

```text
data/benchmark_versions/tau_retail/step_decoy/v1.0.0/
  trajectories.jsonl
  manifest.json
```

Copy the corresponding baseline artifacts into the new release, change only
the trajectory text needed for that rewording, and leave the source baseline
untouched. The new manifest should identify its parent baseline release and
checksum, store a checksum for every artifact, and record the generation model,
prompt version or hash, settings, and seed. Record the label-preservation check
and its result. Reuse the baseline annotations when labels are unchanged. Keep
each domain and rewording type in its own release path. Never overwrite an
existing release; changes to model-visible trajectory content create a new
version.

### Generate step decoys

Step decoys are new trajectories for AgentRx to test: a few events inserted
before the annotated failure that should draw a root-cause judge away from the
real cause without changing it. The model chooses up to three of each kind:

- **Noise** replays an earlier exchange (one to three consecutive events)
  unchanged at a later point.
- **Red herring** inserts a failed attempt directly before an exchange: a copy
  with one value slipped in the request (a value that appears nowhere in the
  trace) and the response replaced by the error that system would return. The
  original exchange then reads as the corrected retry.

The generator is domain-general. `--domain` selects the policy and tool or
agent descriptions from AgentRx's domain registry, as in `run.py`. The input is
any trajectory file or folder `run.py` reads (a wrapper object, a list of events,
a list of wrappers, or JSONL of either; markdown is not supported) plus its
ground truth. The model decides which exchanges are safe to replay or fail;
Python only copies and edits events. No IR conversion is involved.

From the project root, activate the AgentRx environment and sign in to the
GitHub Copilot CLI (`copilot login`), the same CLI AgentRx's judge uses. Each
rewording has its own finalized generator model and effort. They are read from
the environment (`.env`, see `.env.example`) like the judge's
`AGENT_VERIFY_COPILOT_MODEL`; there is no command-line override:

| Rewording | Model variable (default) | Effort variable (default) |
|---|---|---|
| Step decomposition | `STEP_DECOMPOSITION_COPILOT_MODEL` (`claude-haiku-5.5`) | `STEP_DECOMPOSITION_COPILOT_REASONING_EFFORT` (`medium`) |
| Step decoy | `STEP_DECOY_COPILOT_MODEL` (`claude-sonnet-5.5`) | `STEP_DECOY_COPILOT_REASONING_EFFORT` (`medium`) |
| Presentation change | `PRESENTATION_CHANGE_COPILOT_MODEL` (`claude-opus-5.5`) | `PRESENTATION_CHANGE_COPILOT_REASONING_EFFORT` (`medium`) |

The model must be enabled for your Copilot account. The CLI is found as for
AgentRx (`AGENT_VERIFY_COPILOT_BIN`, then the usual npm locations, then `PATH`),
and each call times out after `AGENT_VERIFY_COPILOT_TIMEOUT` seconds (600). A
release is written to `<dataset>/<rewording>/vX.Y.Z`, and its manifest records
the model and effort. The existing `haiku/`, `sonnet/` and `opus/` v0.1.0
releases come from the earlier model-comparison study (Claude Code) and are kept
unchanged; start new releases at v0.2.0.

```bash
base=data/benchmark_versions/tau_retail/baseline/v1.0.0
python -m agentrx.rewordings.step_decoy generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
  --work runs/decoy/tau
```

For Magentic-One use `--domain magentic`, the
`magentic_one/baseline/v1.0.0/trajectories` folder and its ground truth; only
labeled trajectories are attempted. A domain without a default policy needs
`--policy`. Add `--ids 4` for a single-trajectory pilot. An interrupted batch
resumes with the same command.

Each labeled trajectory takes one isolated Copilot CLI call: no tools
(`--available-tools` with an empty list), no built-in or user MCP servers, no
custom instructions, and an empty working directory. The output schema is
appended to the prompt, and the JSON answer is checked against it; the call is
refused unless the session used the requested model and effort. The [prompt](../../agentrx/rewordings/step_decoy_prompt.txt)
follows the invariant prompts: generic instructions with `<<PLACEHOLDER>>` slots
for the domain policy, tool descriptions, task instruction, root failure,
numbered events, the role transitions seen in the dataset, and short error
responses from the dataset as style examples. These inputs are sent to GitHub
Copilot and its model provider. A work directory is locked to its domain, model,
effort, prompt, policy and input checksums; each case's `generation.json`
records the model and effort, the Copilot CLI version, premium requests, and
the generator and helper code hashes.

Python enforces what it can learn from the input itself:

- every role boundary an insertion creates must already occur in the dataset
  (so a tool call is never separated from its result);
- no decoy may copy the annotated failure step or land after it;
- call IDs in copies are replaced with fresh IDs of the same shape;
- integer fields that count events in order (such as Tau's `index`) are
  renumbered across the variant;
- original events are otherwise unchanged.

A proposal that breaks a rule is kept as `invalid.json` for review rather than
stopping the batch. Steps are 1-based event positions, as in the baselines.

Open each case's `proposal.json`, `insertions.json`, `events.json` and
`step_map.json`. Check that each replay is read-only and still current at its new
position, that each failed attempt is a harmless lookup with a realistic error,
and that the original failure remains the real root cause. Reject a case whose
decoys create a new mistake beyond a self-corrected slip. Then write a review for
**each proposed insertion**:

```json
{
  "4": {"decision": "accept", "reviewer": "<your name>", "reason": "<what in the trace supports your decision>"}
}
```

Release each model's reviewed work directory with a fresh version:

```bash
python -m agentrx.rewordings.step_decoy release --work runs/decoy/tau \
  --reviews runs/decoy/tau/reviews.json --version v0.2.0

release_dir=data/benchmark_versions/tau_retail/step_decoy/v0.2.0
python run.py "$release_dir/trajectories" --domain tau \
  --ground-truth "$release_dir/ground_truth.json" --run-name tau_decoy_sonnet
```

`trajectories/` mirrors the input files in their own layout, keeping only
accepted trajectories. Release checks that the inputs are unchanged and rebuilds
every accepted case, refusing one that changed since generation. The derived
ground truth renumbers every structured `step_number` and keeps the old value as
`original_step_number`, because free-text reasons keep the annotators'
numbering. `audit.json` records proposals, generation metadata, reviews, skips,
invalid proposals, inserted positions and the original-to-variant map. The
manifest records the parent inputs and checksums, generator configuration, code
hashes, Copilot CLI versions, total premium requests and artifact checksums.

To measure localization shifts, use clean and variant reports from the same
judge configuration, each containing a single decision per case.

```bash
python -m agentrx.rewordings.step_decoy compare --audit "$release_dir/audit.json" \
  --clean runs/tau_baseline_v1/judge_output/runs/run1.json \
  --variant runs/tau_decoy_sonnet/judge_output/runs/run1.json
```

The decoy attraction rate is the fraction of paired, originally correct
localizations that move onto an inserted event; `attracted_by_kind` splits those
between noise and red herrings. The output also counts predictions on other
original events, missing predictions and clean misses.

### Generate presentation changes

Presentation changes are new trajectories for AgentRx to test: the same events,
in the same order, with only their presentation changed, so a robust root-cause
judge should give the same verdict on the variant as on the original. The model
proposes edits of three kinds:

- **Wording** paraphrases an assistant message with the same meaning. Every
  token containing a digit (IDs, prices, counts, zip codes) must survive
  verbatim, so "10" can never become "ten".
- **Emphasis** adds or removes markdown in an assistant message (bold, italics,
  headings, bullets, code marks) without changing its words.
- **Formatting** re-lays-out a JSON payload, either a tool response or a tool
  call's arguments. The model only chooses a layout (`compact`, `spaced`,
  `indented`) and a key order (`original`, `sorted`, `reverse`); Python writes
  the JSON, so every key and value stays identical.

As with step decoys, the model decides and Python edits. Each edit can touch only
the one field its kind allows. Some steps are always locked: system messages
(the policy), user turns, tool responses that are not JSON, and the arguments
and results of tool calls on annotated failure steps. A failure step may still
be reworded or emphasized, but it must stay exactly as clear and as wrong.
Before anything is saved, a second check compares the result with the original,
independently of the editing code. It confirms that event order and roles are
unchanged, that every locked step is byte-identical, that tool names and call
IDs are unchanged, that JSON values are strictly equal, and that prose keeps
every digit token. A proposal that breaks a rule is kept as `invalid.json` for
review. Steps are 1-based event positions and never move, so labels need no
remapping.

The generator imports this folder's shared helpers from `step_decoy`
unchanged: dataset loading, layouts, hashing and prompt rendering. Its model
call is the same isolated GitHub Copilot CLI call as step_decoy's (no tools, no
MCP servers, no custom instructions, an empty working directory, the answer
checked against a JSON schema, and a check that the requested model and effort
were used), with `PRESENTATION_CHANGE_COPILOT_MODEL` (default `claude-opus-5.5`)
and `PRESENTATION_CHANGE_COPILOT_REASONING_EFFORT` (default `medium`). The
[prompt](../../agentrx/rewordings/presentation_change_prompt.txt) uses the same
`<<PLACEHOLDER>>` style. Its slots are the domain policy, the tool
descriptions, the task instruction, the root failure, the other annotated
failures, the numbered events, and the editable steps with the kinds each one
allows. Roles and text fields are read with step_decoy's helpers, and tool
results are found by call-ID links, so any layout AgentRx reads works. Which
roles may be reworded and which carry the policy are set per domain with
`--prose-roles` and `--policy-roles`. Tau defaults to `assistant` and `system`.
Another domain, such as Magentic-One, passes its own role names as they appear
in its trajectories. Every other role's text stays locked. The prompt names
these roles through its role slots, and the roles are locked in `config.json`
and recorded in the manifest.

```bash
base=data/benchmark_versions/tau_retail/baseline/v1.0.0
python -m agentrx.rewordings.presentation_change generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
  --work runs/presentation_change/tau
```

`--ids 2` runs a single-trajectory pilot, but a pilot work directory can never
be released. An interrupted batch resumes with the same command. As in
step_decoy, a work directory is locked to its settings in `config.json`. Each
case's `generation.json` records the model and effort, the Copilot CLI
version, premium requests, and hashes of this generator and of the shared
step_decoy and copilot code. Each valid case also gets `events.json` and a `validation.json` that lists
every change and the `events_sha256` the review must name.

**One attempt per case.** Each trajectory is generated once; there is no
regeneration. A release must cover every labeled trajectory (29 for Tau): each
case is either accepted (valid, with a signed accept review of its exact events)
or excluded, because it failed validation, returned no edit, was rejected in
review, or no longer passes the current checks. An excluded case is left out of
`trajectories/` and `ground_truth.json`, as step-decoy releases left out task 31,
and documented with its reason in the manifest's `excluded_ids` and `excluded`
and in the audit. Report it as an outcome. A missing case, a missing or stale
review, or drift still blocks the release.

Write the review sheet, then review **each case**:

```bash
python -m agentrx.rewordings.presentation_change review-sheet --work runs/presentation_change/tau
```

This writes `review_sheet.md` and `reviews.template.json` in the work directory.
For each case the sheet shows its root and other failures,
the model's rationale, and every change with its checks. Prose edits appear in
full, before and after, and edits on annotated failure steps are flagged with ⚠.
The sheet also reports whether each review in an existing `reviews.json` is
current, stale or missing. Unlike the step-decoy sheets, it suggests no
decision. Python has already checked structure and values, so the review is
about meaning: each paraphrase must say exactly what the original said, and
every annotated failure must stay exactly as clear and as wrong. Fill in
`decision`, `reviewer` and `reason` in the template and save it as
`reviews.json`. Keep `events_sha256` as written, because it ties the review to
the exact events you read. A review whose hash no longer matches the events is
stale and is refused. A rejected case is excluded with your reason.

```json
{
  "4": {"decision": "accept", "reviewer": "<your name>", "reason": "<what in the trace supports your decision>",
        "events_sha256": "<copied from the template>"}
}
```

Release each model's reviewed work directory with a fresh version. AgentRx
then runs on it like any other release:

```bash
python -m agentrx.rewordings.presentation_change release --work runs/presentation_change/tau \
  --reviews runs/presentation_change/tau/reviews.json --version v0.2.0

release_dir=data/benchmark_versions/tau_retail/presentation_change/v0.2.0
python run.py "$release_dir/trajectories" --domain tau \
  --ground-truth "$release_dir/ground_truth.json" --run-name tau_pc_opus
```

Release refuses with one message listing every case that needs attention and the
fix for each. It refuses in these cases:

- the work directory does not cover every labeled trajectory;
- a case is missing;
- a review is missing, unsigned or stale;
- the inputs changed since generation;
- a rebuilt case differs from its saved events;
- the version already exists.

`trajectories/` has the baseline's layout and holds the accepted cases, each
record identical to the baseline except its `traj`. `ground_truth.json` is the baseline labels
unchanged, plus `original_step_number`, which always equals `step_number`; it
is there only so the file has the same shape as a step-decoy release.
`audit.json` records each case's proposal, generation metadata, review, applied
changes and root failure, and, for an excluded case, its exclusion reason. The
manifest uses the step-decoy keys, and `attempted_count` counts every case,
excluded ones included. It adds `excluded_ids` and `excluded` (each excluded
case with its reason). The existing `v0.1.0` releases were made with the earlier
Claude Code generator, which allowed up to three attempts per case; their
manifests keep `regenerated` and `total_cost_usd` as recorded.

To measure verdict changes, use clean and variant reports from the same judge
configuration, each containing a single decision per case:

```bash
python -m agentrx.rewordings.presentation_change compare --audit "$release_dir/audit.json" \
  --clean runs/tau_baseline_v1/judge_output/runs/run1.json \
  --variant runs/tau_pc_sonnet/judge_output/runs/run1.json
```

Paired cases are those the clean run localized correctly. For each one, the
variant's verdict is compared with the clean verdict on both step and category,
and classified as `same_step_same_category`, `step_moved`, `category_changed`
(same step) or `step_and_category_changed`. Categories are read from the
judge's integer `failure_case` codes with the judge's own
`convert_to_failure_case`. The verdict-flip rate is the fraction of paired
cases with any change; a category change with the step unchanged counts as a
flip. `verdict_flip_rate_fully_correct` repeats the rate on the cases whose
clean category also matched the annotation. Missing predictions and clean
misses are counted separately, as in step_decoy, and `predictions` lists the
root, clean and variant verdict for every case.

## Changelog

Every release version and every change to the framework's frozen models is listed here, newest first. A release is never edited after it is written; a fix is a new version. The SHA-256 is that of the release's `manifest.json`, which in turn holds the SHA-256 of every file in the release.

### 2026-11-24 — framework settings (no new release)

- The rewording generators now run through the GitHub Copilot CLI, the same route as the AgentRx judge, with one finalized model per rewording: `claude-haiku-5.5` (step decomposition), `claude-sonnet-5.5` (step decoy) and `claude-opus-5.5` (presentation change), all at medium effort. Each is set by its own environment variable, with no command-line override.
- New releases are written to `<dataset>/<rewording>/vX.Y.Z` from v0.2.0. The model is recorded in the manifest instead of the folder name.
- Presentation change generates each case once. A case that fails validation, returns no edit or is rejected in review is excluded with its reason; there is no regeneration.
- The AgentRx judge is `gpt-6.1-sol` at medium reasoning effort. Earlier τ-bench judge runs used the model's default effort.

### 2026-11-18 to 2026-11-23 — model-comparison study, v0.1.0

Generated through Claude Code with `claude-*-5-5` models at medium effort, from `tau_retail/baseline/v1.0.0`. ★ marks the generator chosen for the framework.

| Release | Date | Cases | Manifest SHA-256 |
|---|---|---|---|
| `tau_retail/step_decoy/haiku/v0.1.0` | 2026-11-18 | 28 of 29 | `a1437daac2843950e319d80da5d51e70854bca137b22f26c1f8f36027dfc3428` |
| `tau_retail/step_decoy/sonnet/v0.1.0` ★ | 2026-11-18 | 28 of 29 | `16bbcab8c3aa3fc63c870bae1c1d3b4276832c65cdcb11a60693876476dfd53c` |
| `tau_retail/step_decoy/opus/v0.1.0` | 2026-11-18 | 27 of 29 | `5464ac81fa4e22cd88cfc27175b44d86c538b6db895e49e8373696b562077731` |
| `tau_retail/presentation_change/haiku/v0.1.0` | 2026-11-22 | 29 of 29 | `ca42c8484564869daea7dd3f85acb5b69a259194bea19bbea96a403836215845` |
| `tau_retail/presentation_change/sonnet/v0.1.0` | 2026-11-22 | 28 of 29 (case 28 excluded) | `567bd44b090d2f37b4934df268a9c76d50ebf0f11a03f917b5e91bcec0357ff2` |
| `tau_retail/presentation_change/opus/v0.1.0` ★ | 2026-11-22 | 29 of 29 | `20211b54e550e1206d066989003758e1caf6f0d6b031bf33cc96283d4ae0d195` |
| `tau_retail/step_decomposition/haiku/v0.1.0` ★ | 2026-11-23 | 16 of 29 | `397fc068f12f9f18b39e808452e5dbcb2852ffb18642ecfbc000968301686f38` |
| `tau_retail/step_decomposition/sonnet/v0.1.0` | 2026-11-23 | 15 of 29 | `d51b2e180a213c4d240bba4d5476a9eb70af69c6e74dbb076d26ee905c6b59f9` |
| `tau_retail/step_decomposition/opus/v0.1.0` | 2026-11-23 | 15 of 29 | `f2746edabaa1ffdff20a61f418aa4326d692b0a44e7a19bdb3220aa2fc50a139` |

### 2026-11-12 — baseline v1.0.0

| Release | Date | Cases | Manifest SHA-256 |
|---|---|---|---|
| `tau_retail/baseline/v1.0.0` | 2026-11-12 | 29 trajectories, 29 labels | `1073c71b4c64f1d06a7fd83492b2544694967499a6473a2d3a9aad4a643103c9` |

No release has been withdrawn.
