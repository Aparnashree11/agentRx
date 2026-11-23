# AgentRx: Step-Decomposition Trajectories

This branch (`step-decomposition`) adds a benchmark variant for [AgentRx](https://arxiv.org/abs/2602.02475): failed agent trajectories whose single annotated **root-cause step is split into several smaller steps**. The smaller steps are what the same actor would naturally do to carry out that one step, spread move by move. They test whether AgentRx's judge still finds the annotated root-cause step once the one guilty step is no longer a single line.

The decompositions were generated for the 29 Tau Retail baseline trajectories by three Claude models (Haiku 5.5, Sonnet 5.5 and Opus 5.5), reviewed, and released as versioned datasets ready to run through AgentRx.

For the full AgentRx pipeline documentation, see the README on the `main` branch.

---

## What a step decomposition is

The generating model takes the one annotated root-cause step and rewrites it as **two to four smaller consecutive steps by the same actor** that together say exactly what it did, with the same mistake left unfixed. Nothing before or after the step changes; only the step's position moves, and the ground truth is renumbered so the root failure points at the smaller step that still carries the mistake.

Example from Tau task 2, where the agent miscounts available T-shirts at step 7:

```
5   assistant  get_product_details {"product_id":"9523456873"}     ← unchanged
6   tool       {"name":"T-Shirt","variants":{...}}                 ← unchanged
7   assistant  "Let me go through the T-shirt variants..."         ← smaller step 1
8   assistant  "Currently, there are 11 available T-shirt options" ← smaller step 2  (root failure, was step 7)
9   assistant  "Each option varies by color, size, material..."    ← smaller step 3
10  user       "Got it, thank you! ..."                            ← unchanged
```

The generator is domain-general. `--domain` selects the policy and tool descriptions as in `run.py`, the input can be any trajectory layout AgentRx reads, and the model proposes only the text of the smaller steps; Python replaces the step, keeps the actor, and renumbers. It does not use AgentRx's IR converter.

A step whose only content is a tool call — a silent `cancel_pending_order` or `calculate` whose mistake *is* the call — cannot be split without inventing a narration the agent never spoke, so those are **rejected in review** rather than released. In Tau, 12 of the 29 root steps are such silent calls. (The generator can still decline a step with `NO_VALID_DECOMPOSITION`; with the current prompt none of the 29 were declined.)

---

## What was generated

All three runs used medium effort, one Claude Code call per trajectory, and the same prompt and generator code. With a prompt that states plainly that splitting one turn produces consecutive same-actor messages, **every model proposes a split for all 29 trajectories**; review keeps the ones whose root step is the agent's own text and rejects the 12 silent tool-call steps, where the narration would be fabricated.

| Generator | Release | Accepted | Rejected | Avg. smaller steps | Avg. steps added | Cost |
|---|---|---|---|---|---|---|
| Haiku 5.5 | [`haiku/v0.1.0`](data/benchmark_versions/tau_retail/step_decomposition/haiku/v0.1.0/manifest.json) | 16 | 13 | 2.8 | 1.8 | $0.16 |
| Sonnet 5.5 | [`sonnet/v0.1.0`](data/benchmark_versions/tau_retail/step_decomposition/sonnet/v0.1.0/manifest.json) | 15 | 14 | 2.6 | 1.6 | $2.21 |
| Opus 5.5 | [`opus/v0.1.0`](data/benchmark_versions/tau_retail/step_decomposition/opus/v0.1.0/manifest.json) | 15 | 14 | 2.2 | 1.2 | $4.49 |

The [findings report](agentrx/rewordings/reports/step_decomposition/tau/findings.md) compares the three generators: what each decomposed and declined, where they agreed, the errors each made, and cost.

---

## Where everything is stored

```
agentrx/rewordings/
├── step_decomposition.py                 # generator CLI: generate, release, compare
├── step_decomposition_prompt.txt         # domain-general prompt with <<PLACEHOLDER>> slots
└── reports/step_decomposition/tau/
    ├── README.md
    ├── findings.md                        # cross-model analysis
    ├── review_sheets/<model>-medium.md    # per-trajectory review notes
    └── reviews/<model>-medium.json        # signed review decisions used for release

data/benchmark_versions/
├── README.md                             # versioning rules and the full step-decomposition workflow
└── tau_retail/
    ├── baseline/v1.0.0/                   # parent: 29 original trajectories + labels
    └── step_decomposition/<haiku|sonnet|opus>/v0.1.0/
        ├── trajectories/tau_dataset_failed.json   # accepted trajectories, same layout as the baseline
        ├── ground_truth.json             # labels renumbered to the new step positions
        ├── audit.json                     # proposals, reviews, step maps, decomposed/error steps, skips
        └── manifest.json                  # parent checksums, generator settings, cost, artifact checksums

tests/test_step_decomposition.py          # layouts, generation, release, compare, Magentic-One

runs/decomp/tau/<model>-medium/           # generation work folders (git-ignored, local only)
```

Releases are immutable. A change produces a new version (`v0.2.0`, …) and never overwrites an existing one.

---

## Setup

You need Python 3.10 or newer and Node.js/npm for the GitHub Copilot CLI, which AgentRx uses by default.

```bash
git clone https://github.com/aparnashree11/agentRx.git
cd agentRx
git switch step-decomposition
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

Running the released trajectories needs only this setup. Generating new decompositions also needs [Claude Code](#regenerate-or-extend).

---

## Run AgentRx on the step-decomposition trajectories

Each release is a drop-in replacement for the baseline input. Run one generator's release:

```bash
release_dir=data/benchmark_versions/tau_retail/step_decomposition/sonnet/v0.1.0
python run.py "$release_dir/trajectories/tau_dataset_failed.json" \
  --domain tau \
  --ground-truth "$release_dir/ground_truth.json" \
  --run-name tau_decomp_sonnet
```

Run all three:

```bash
for m in haiku sonnet opus; do
  release_dir=data/benchmark_versions/tau_retail/step_decomposition/$m/v0.1.0
  python run.py "$release_dir/trajectories/tau_dataset_failed.json" --domain tau \
    --ground-truth "$release_dir/ground_truth.json" --run-name "tau_decomp_$m"
done
```

Outputs go to `runs/tau_decomp_<model>/`, the same as any AgentRx run (`trajectory_ir.json`, invariants, `checker_results/`, `judge_output/`, `plots/`).

### Measure whether the decomposition moved the judge

You need a clean run on the original trajectories with **the same judge configuration**:

```bash
python run.py data/benchmark_versions/tau_retail/baseline/v1.0.0/tau_dataset_failed.json \
  --domain tau \
  --ground-truth data/benchmark_versions/tau_retail/baseline/v1.0.0/tau_ground_truth.json \
  --run-name tau_baseline_v1
```

Then compare the two judge reports:

```bash
python -m agentrx.rewordings.step_decomposition compare \
  --audit data/benchmark_versions/tau_retail/step_decomposition/sonnet/v0.1.0/audit.json \
  --clean runs/tau_baseline_v1/judge_output/runs/run1.json \
  --variant runs/tau_decomp_sonnet/judge_output/runs/run1.json
```

The output classifies every trajectory the clean run localized correctly:

- `found_error_substep`: the judge still found the mistake, on the smaller step that carries it.
- `drifted_within_decomposition`: the judge picked a sibling smaller step instead.
- `other_original_event`: the judge picked another original step.

The **decomposition evasion rate** is the share whose prediction no longer lands on the mistake-carrying step.

---

## Regenerate or extend

Generating decompositions needs [Claude Code](https://claude.com/claude-code), signed in. If `claude` is not on your PATH, set `CLAUDE_BIN` to its executable.

```bash
base=data/benchmark_versions/tau_retail/baseline/v1.0.0
python -m agentrx.rewordings.step_decomposition generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
  --model sonnet --effort medium --work runs/decomp/tau/sonnet-medium

# review each case, write reviews.json, then:
python -m agentrx.rewordings.step_decomposition release --work runs/decomp/tau/sonnet-medium \
  --reviews runs/decomp/tau/sonnet-medium/reviews.json --version v0.2.0
```

Generation sends the policy and trajectories to Anthropic. For Magentic-One, use `--domain magentic` with the `magentic_one/baseline/v1.0.0/trajectories` folder and its ground truth. The review checklist, the generator's rules and every output file are described in [the dataset versioning notes](data/benchmark_versions/README.md#generate-step-decompositions).

Run the tests with `python -m pytest tests/test_step_decomposition.py`.

---

## Caveats

- **Every accepted trajectory now has two messages in a row from the same actor** (assistant then assistant, or user then user), which never happens in the original Tau data. This is inherent to splitting one turn, and the generator only enforces the dataset's role transitions at the outer boundaries of a split. A judge could in principle pick up on the unseen repetition; it is deliberately allowed here, unlike in the step-decoy variant, which rejects any sequence not seen in the data.
- **Silent tool-call steps are rejected, not released.** A root cause that is a bare `cancel_pending_order`, `calculate` or `exchange_delivered_order_items` with no agent text can only be "split" by inventing narration, so review rejects all 12 such steps. That is why the accept counts are about 15–16, not 29.
- **The generator model is a small lever here, once the prompt is clear.** An earlier prompt wording made Opus refuse most splits (it accepted only 4), which looked like model conservatism; with the prompt fixed, all three decompose all 29 and accept nearly the same set (Sonnet and Opus accept the identical 15; Haiku adds task 59). Do not read the earlier "Opus is conservative" result as a model property.
- **Tasks 2, 3 and 4 are related** — same user, same T-shirt miscount — so their decompositions look alike. Treat them as one group when computing rates.
- **One sample per model.** Each trajectory was generated once per model, without seed control.
- **How the reviews were done.** A reviewer read every candidate and confirmed each accepted case keeps the same actor and the same unfixed mistake and invents nothing. Rejections are fabrications or lost mistakes: the 12 silent tool calls, task 80 (the `###STOP` failure marker is dropped), and task 59 for Sonnet and Opus (an invented "5 days" rationale). Per-case decisions and reasons are in each release's `audit.json` and in [the review sheets](agentrx/rewordings/reports/step_decomposition/tau/review_sheets/).

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
