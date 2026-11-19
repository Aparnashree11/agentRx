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

From the project root, activate the AgentRx environment and sign in to Claude
Code. Each generator model gets its own work directory and release line:

| `--model` | Model ID | Release path |
|---|---|---|
| `haiku` | `claude-haiku-5-5` | `<dataset>/step_decoy/haiku/vX.Y.Z` |
| `sonnet` | `claude-sonnet-5-5` | `<dataset>/step_decoy/sonnet/vX.Y.Z` |
| `opus` | `claude-opus-5-5` | `<dataset>/step_decoy/opus/vX.Y.Z` |

```bash
# If `claude` is not on PATH, point at the binary (e.g. the VS Code extension's copy)
export CLAUDE_BIN=~/.vscode/extensions/anthropic.claude-code-<version>/resources/native-binary/claude
base=data/benchmark_versions/tau_retail/baseline/v1.0.0
for m in haiku sonnet opus; do
  python -m agentrx.rewordings.step_decoy generate --domain tau \
    --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
    --model "$m" --effort medium --work "runs/decoy/tau/$m-medium" &
done; wait
```

For Magentic-One use `--domain magentic`, the
`magentic_one/baseline/v1.0.0/trajectories` folder and its ground truth; only
labeled trajectories are attempted. A domain without a default policy needs
`--policy`. Add `--ids 4` for a single-trajectory pilot. `--effort` is optional.
An interrupted batch resumes with the same command.

Each labeled trajectory takes one tool-free Claude Code call (`--safe-mode`, no
tools, no MCP, no CLAUDE.md, empty working directory) whose answer is checked
against a JSON schema. The [prompt](../../agentrx/rewordings/step_decoy_prompt.txt)
follows the invariant prompts: generic instructions with `<<PLACEHOLDER>>` slots
for the domain policy, tool descriptions, task instruction, root failure,
numbered events, the role transitions seen in the dataset, and short error
responses from the dataset as style examples. These inputs are sent to
Anthropic. A work directory is locked to its domain, model, effort, prompt,
policy and input checksums; each case's `generation.json` records the model that
answered, the Claude Code version, cost and generator code hash.

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
python -m agentrx.rewordings.step_decoy release --work runs/decoy/tau/sonnet-medium \
  --reviews runs/decoy/tau/sonnet-medium/reviews.json --version v0.1.0

release_dir=data/benchmark_versions/tau_retail/step_decoy/sonnet/v0.1.0
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
hashes, Claude Code versions, total generation cost and artifact checksums.

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
