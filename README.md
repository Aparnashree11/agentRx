# AgentRx: Step-Decoy Trajectories

This branch (`step-decoy`) adds a benchmark variant for [AgentRx](https://arxiv.org/abs/2602.02475): failed agent trajectories with **step decoys** inserted. Decoys are a few extra steps that look like trouble or add noise but are not the cause of the failure. They test whether AgentRx's judge still finds the annotated root-cause step when something more eye-catching sits nearby.

The decoys were generated for the 29 Tau Retail baseline trajectories by three Claude models (Haiku 5.5, Sonnet 5.5 and Opus 5.5), reviewed, and released as versioned datasets ready to run through AgentRx.

For the full AgentRx pipeline documentation, see the README on the `main` branch.

---

## What a step decoy is

The generating model chooses up to three decoys of each kind per trajectory, all placed before the annotated failure:

- **Noise** replays an earlier read-only exchange, unchanged, at a later point.
- **Red herring** inserts a failed attempt just before a real lookup. It is a copy of the lookup with one value slipped and the response replaced by the system's own error. The original lookup then reads as the corrected retry.

Example from Tau task 4, where the agent miscounts available T-shirts at step 15:

```
13  assistant  get_product_details {"product_id":"9523456837"}   ← red herring (transposed digits)
14  tool       Error: product not found                           ← red herring
15  assistant  get_product_details {"product_id":"9523456873"}   ← original step 13 (the retry)
16  tool       {"name": "T-Shirt", "variants": {...}}             ← original step 14
17  assistant  list_all_product_types {}                          ← noise (replay of step 11)
18  tool       {"Action Camera": ..., "T-Shirt": ...}             ← noise
19  assistant  "Currently, there are 11 available T-shirt options" ← root failure (was step 15)
```

The root cause is unchanged. The ground truth is renumbered to the new positions, and each label keeps its `original_step_number`.

The generator is domain-general. `--domain` selects the policy and tool descriptions as in `run.py`, the input can be any trajectory layout AgentRx reads, and the model decides which steps are safe to replay or fail. It does not use AgentRx's IR converter.

---

## What was generated

All three runs used medium effort, one Claude Code call per trajectory, and the same prompt and generator code.

| Generator | Release | Trajectories | Left out | Decoys (red herring / noise) | Avg. events added | Generation cost |
|---|---|---|---|---|---|---|
| Haiku 5.5 | [`haiku/v0.1.0`](data/benchmark_versions/tau_retail/step_decoy/haiku/v0.1.0/manifest.json) | 28 | 28 (stale replay) | 31 / 31 | 4.3 | $0.19 |
| Sonnet 5.5 | [`sonnet/v0.1.0`](data/benchmark_versions/tau_retail/step_decoy/sonnet/v0.1.0/manifest.json) | 28 | 31 (decoy after the failure) | 37 / 36 | 5.2 | $2.30 |
| Opus 5.5 | [`opus/v0.1.0`](data/benchmark_versions/tau_retail/step_decoy/opus/v0.1.0/manifest.json) | 27 | 31 (stale replay), 47 (no actual slip) | 57 / 46 | 7.4 | $4.79 |

The [findings report](agentrx/rewordings/reports/step_decoy/tau/findings.md) compares the three generators: where they agreed, how they differed, the errors each made, and cost.

---

## Where everything is stored

```
agentrx/rewordings/
├── step_decoy.py                    # generator CLI: generate, release, compare
├── step_decoy_prompt.txt            # domain-general prompt with <<PLACEHOLDER>> slots
└── reports/step_decoy/tau/
    ├── README.md
    ├── findings.md                  # cross-model analysis
    ├── review_sheets/<model>-medium.md   # per-trajectory review notes
    └── reviews/<model>-medium.json       # signed review decisions used for release

data/benchmark_versions/
├── README.md                        # versioning rules and the full step-decoy workflow
└── tau_retail/
    ├── baseline/v1.0.0/             # parent: 29 original trajectories + labels
    └── step_decoy/<haiku|sonnet|opus>/v0.1.0/
        ├── trajectories/tau_dataset_failed.json   # accepted trajectories, same layout as the baseline
        ├── ground_truth.json        # labels renumbered to the new step positions
        ├── audit.json               # proposals, reviews, step maps, inserted steps, skipped cases
        └── manifest.json            # parent checksums, generator settings, cost, artifact checksums

tests/test_step_decoy.py             # layouts, generation, release, compare, Magentic-One

runs/decoy/tau/<model>-medium/       # generation work folders (git-ignored, local only)
```

Releases are immutable. A change produces a new version (`v0.2.0`, …) and never overwrites an existing one.

---

## Setup

You need Python 3.10 or newer and Node.js/npm for the GitHub Copilot CLI, which AgentRx uses by default.

```bash
git clone https://github.com/aparnashree11/agentRx.git
cd agentRx
git switch step-decoy
python3.12 -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -e .
npm install -g @github/copilot
copilot login
cp .env.example .env
```

In `.env`, set the endpoint AgentRx's judge will use:

```env
AGENT_VERIFY_ENDPOINT_TYPE=copilot
AGENT_VERIFY_COPILOT_MODEL=auto
```

Running the released trajectories needs only this setup. Generating new decoys also needs [Claude Code](#regenerate-or-extend).

---

## Run AgentRx on the step-decoy trajectories

Each release is a drop-in replacement for the baseline input. Run one generator's release:

```bash
release_dir=data/benchmark_versions/tau_retail/step_decoy/sonnet/v0.1.0
python run.py "$release_dir/trajectories/tau_dataset_failed.json" \
  --domain tau \
  --ground-truth "$release_dir/ground_truth.json" \
  --run-name tau_decoy_sonnet
```

Run all three:

```bash
for m in haiku sonnet opus; do
  release_dir=data/benchmark_versions/tau_retail/step_decoy/$m/v0.1.0
  python run.py "$release_dir/trajectories/tau_dataset_failed.json" --domain tau \
    --ground-truth "$release_dir/ground_truth.json" --run-name "tau_decoy_$m"
done
```

Outputs go to `runs/tau_decoy_<model>/`, the same as any AgentRx run (`trajectory_ir.json`, invariants, `checker_results/`, `judge_output/`, `plots/`).

### Measure whether the decoys moved the judge

You need a clean run on the original trajectories with **the same judge configuration**:

```bash
python run.py data/benchmark_versions/tau_retail/baseline/v1.0.0/tau_dataset_failed.json \
  --domain tau \
  --ground-truth data/benchmark_versions/tau_retail/baseline/v1.0.0/tau_ground_truth.json \
  --run-name tau_baseline_v1
```

Then compare the two judge reports:

```bash
python -m agentrx.rewordings.step_decoy compare \
  --audit data/benchmark_versions/tau_retail/step_decoy/sonnet/v0.1.0/audit.json \
  --clean runs/tau_baseline_v1/judge_output/runs/run1.json \
  --variant runs/tau_decoy_sonnet/judge_output/runs/run1.json
```

The output classifies every trajectory the clean run localized correctly:

- `same_original_event`: the judge still found the root cause.
- `inserted_decoy`: the judge picked a decoy step. `attracted_by_kind` splits these into noise and red herrings.
- `other_original_event`: the judge picked another original step.

The **decoy attraction rate** is the share of those trajectories whose prediction moved onto a decoy.

---

## Regenerate or extend

Generating decoys needs [Claude Code](https://claude.com/claude-code), signed in. If `claude` is not on your PATH, set `CLAUDE_BIN` to its executable.

```bash
base=data/benchmark_versions/tau_retail/baseline/v1.0.0
python -m agentrx.rewordings.step_decoy generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
  --model sonnet --effort medium --work runs/decoy/tau/sonnet-medium

# review each case, write reviews.json, then:
python -m agentrx.rewordings.step_decoy release --work runs/decoy/tau/sonnet-medium \
  --reviews runs/decoy/tau/sonnet-medium/reviews.json --version v0.2.0
```

Generation sends the policy and trajectories to Anthropic. For Magentic-One, use `--domain magentic` with the `magentic_one/baseline/v1.0.0/trajectories` folder and its ground truth. The review checklist, the generator's rules and every output file are described in [the dataset versioning notes](data/benchmark_versions/README.md#generate-step-decoys).

Run the tests with `python -m pytest tests/test_step_decoy.py`.

---

## Caveats

- **Tasks 2, 3 and 4 are related.** They share a user and an opening question, and the agent makes the same miscount in each, so their decoyed versions are similar. Treat them as one group when computing rates. The baseline labels for tasks 2 and 3 choose the miscount at step 7 as the root, although an earlier identity-verification lapse at step 3 is also labeled.
- **Slips are formulaic.** 91 of 125 red herrings swap the last two characters of an ID, a pattern a detector could learn.
- **One sample per model.** Each trajectory was generated once per model, without seed control.
- **How the reviews were done.** Reviews adopt the suggestions in the review sheets. Those come from automated checks, plus a manual check of every flagged replay.

---

## Upstream AgentRx, license and citation

AgentRx is by Microsoft Research ([paper](https://arxiv.org/abs/2602.02475), [dataset](https://huggingface.co/datasets/microsoft/AgentRx)) and is licensed under the [MIT](LICENSE.txt) license. Copyright (c) Microsoft Corporation. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

```bibtex
@article{barke2026agentrx,
  title={AgentRx: Diagnosing AI Agent Failures from Execution Trajectories},
  author={Barke, Shraddha and Goyal, Arnav and Khare, Alind and Singh, Avaljot and Nath, Suman and Bansal, Chetan},
  journal={arXiv preprint arXiv:2602.02475},
  year={2026}
}
```
