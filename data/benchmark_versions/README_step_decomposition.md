# AgentRx benchmark releases

This folder contains immutable releases of the benchmark data already used by
the project. The baseline files are byte-for-byte copies of the existing local
inputs and labels. They have not been cleaned, normalized, filtered, or
converted. The manifests preserve the original source paths for provenance, but
the frozen release artifacts are self-contained and do not depend on those
original folders being present.

## Baseline releases

- `tau_retail/baseline/v1.0.0/manifest.json`
- `magentic_one/baseline/v1.0.0/manifest.json`

Each manifest records the original project paths, the copied artifact paths,
trajectory IDs, row counts, and SHA-256 checksums. Tau Retail freezes the 29
failed trajectories and their 29 labels. Magentic-One freezes all 58 trajectory
files and the existing 44 labels; only those 44 annotated IDs have benchmark
labels. The Tau release is scoped to the 29 failed trajectories and does not
include the broader 100-row Tau pool.

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

### Generate step decompositions

Step decompositions are new trajectories for AgentRx to test: the single
annotated root-cause step is split into two to four smaller consecutive steps by
the same actor that together do exactly what it did, so the one guilty step is
spread across the finer, realistic steps an agent would take. The mistake is
preserved and left unfixed; only its position changes.

The generator is domain-general. `--domain` selects the policy and tool or agent
descriptions from AgentRx's domain registry, as in `run.py`. The input is any
trajectory file or folder `run.py` reads (a wrapper object, a list of events, a
list of wrappers, or JSONL of either; markdown is not supported) plus its ground
truth. The model proposes only the text of the smaller steps; Python replaces the
step, keeps the same actor and renumbers the trajectory. No IR conversion is
involved.

From the project root, activate the AgentRx environment and sign in to the
GitHub Copilot CLI (`copilot login`), the same CLI AgentRx's judge uses. The
generator model is `STEP_DECOMPOSITION_COPILOT_MODEL` (default
`claude-haiku-5.5`) and the effort `STEP_DECOMPOSITION_COPILOT_REASONING_EFFORT`
(default `medium`), the finalized setting, read from the environment (`.env`,
see `.env.example`) like the judge's settings; there is no command-line
override. The model must be enabled for your Copilot account. A release is
written to `<dataset>/step_decomposition/vX.Y.Z`, and its manifest records the
model and effort. The existing `haiku/`, `sonnet/` and `opus/` v0.1.0 releases
come from the earlier model-comparison study (Claude Code) and are kept
unchanged; start new releases at v0.2.0.

```bash
base=data/benchmark_versions/tau_retail/baseline/v1.0.0
python -m agentrx.rewordings.step_decomposition generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
  --work runs/decomp/tau
```

For Magentic-One use `--domain magentic`, the
`magentic_one/baseline/v1.0.0/trajectories` folder and its ground truth; only
labeled trajectories are attempted. A domain without a default policy needs
`--policy`. Add `--ids 4` for a single-trajectory pilot. An interrupted batch
resumes with the same command.

Each labeled trajectory takes one isolated Copilot CLI call: no tools, no
built-in or user MCP servers, no custom instructions, and an empty working
directory. The output schema is appended to the prompt and the JSON answer is
checked against it; the call is refused unless the session used the requested
model and effort. The
[prompt](../../agentrx/rewordings/step_decomposition_prompt.txt) follows the
invariant prompts: generic instructions with `<<PLACEHOLDER>>` slots for the
domain policy, tool descriptions, task instruction, root failure, numbered
events, the exact step to decompose, and the role transitions seen in the
dataset. These inputs are sent to GitHub Copilot and its model provider. A work
directory is locked to its domain, model, effort, prompt, policy and input
checksums; each case's `generation.json` records the model and effort, the
Copilot CLI version, premium requests, and the generator and helper code hashes.

Python enforces what it can learn from the input itself:

- only the entry and exit boundaries the split creates must already occur in the
  dataset (so the step is not detached from the turn before or after it); the
  internal same-actor boundaries are inherent to splitting one turn;
- the smaller steps keep the actor of the original step, and any tool call stays
  on the last of them, so the tool result still follows the call;
- integer fields that count events in order (such as Tau's `index`) are
  renumbered across the variant;
- every event except the decomposed step is unchanged.

A proposal that breaks a rule is kept as `invalid.json` for review rather than
stopping the batch. Steps are 1-based event positions, as in the baselines.

Open each case's `proposal.json`, `events.json`, `step_map.json` and
`decomposition.json`. Check that the smaller steps together say exactly what the
original step did, keep the same actor, and still state the same mistake
unfixed, so a reader could still catch the failure, and that nothing before or
after the step is changed or resolved. Reject a case whose smaller steps fix,
soften or add to the failure. Then write a review for **each candidate**:

```json
{
  "4": {"decision": "accept", "reviewer": "<your name>", "reason": "<what in the trace supports your decision>"}
}
```

Release each model's reviewed work directory with a fresh version:

```bash
python -m agentrx.rewordings.step_decomposition release --work runs/decomp/tau \
  --reviews runs/decomp/tau/reviews.json --version v0.2.0

release_dir=data/benchmark_versions/tau_retail/step_decomposition/v0.2.0
python run.py "$release_dir/trajectories" --domain tau \
  --ground-truth "$release_dir/ground_truth.json" --run-name tau_decomp_haiku
```

`trajectories/` mirrors the input files in their own layout, keeping only
accepted trajectories. Release checks that the inputs are unchanged and rebuilds
every accepted case, refusing one that changed since generation. The derived
ground truth renumbers every structured `step_number` and keeps the old value as
`original_step_number`, and the root failure moves onto the smaller step that
carries the mistake, because free-text reasons keep the annotators' numbering.
`audit.json` records proposals, generation metadata, reviews, skips, invalid
proposals, the decomposed and error step positions, and the original-to-variant
map. The manifest records the parent inputs and checksums, generator
configuration, code hashes, Copilot CLI versions, total premium requests and
artifact checksums.

To measure localization shifts, use clean and variant reports from the same
judge configuration, each containing a single decision per case.

```bash
python -m agentrx.rewordings.step_decomposition compare --audit "$release_dir/audit.json" \
  --clean runs/tau_baseline_v1/judge_output/runs/run1.json \
  --variant runs/tau_decomp_haiku/judge_output/runs/run1.json
```

The decomposition evasion rate is the fraction of paired, originally correct
localizations that no longer land on the smaller step carrying the mistake;
`drift_within_rate` is the share that moved onto a sibling smaller step. The
output also counts predictions on other original events, missing predictions and
clean misses.
