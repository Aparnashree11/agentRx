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
9   user       "Got it, thank you! ..."                            ← unchanged
```

The generator is domain-general. `--domain` selects the policy and tool descriptions as in `run.py`, the input can be any trajectory layout AgentRx reads, and the model proposes only the text of the smaller steps; Python replaces the step, keeps the actor, and renumbers. It does not use AgentRx's IR converter.

A step that cannot be split without changing the failure is **declined** (`NO_VALID_DECOMPOSITION`). In Tau that is almost always an atomic tool call — a single `cancel_pending_order` or `calculate` whose mistake *is* the call — which cannot be spread across messages without inventing a step.

---

## What was generated

All three runs used medium effort, one Claude Code call per trajectory, and the same prompt and generator code. Step decomposition applies to **text** root causes (an assistant's claim, a user's request); tool-call root steps are declined.

| Generator | Release | Accepted | Left out (declined / invalid / rejected) | Avg. smaller steps | Avg. steps added | Cost |
|---|---|---|---|---|---|---|
| Haiku 5.5 | [`haiku/v0.1.0`](data/benchmark_versions/tau_retail/step_decomposition/haiku/v0.1.0/manifest.json) | 13 | 16 (13 / 2 / 1) | 2.6 | 1.6 | $0.17 |
| Sonnet 5.5 | [`sonnet/v0.1.0`](data/benchmark_versions/tau_retail/step_decomposition/sonnet/v0.1.0/manifest.json) | 14 | 15 (13 / 1 / 1) | 2.2 | 1.2 | $2.15 |
| Opus 5.5 | [`opus/v0.1.0`](data/benchmark_versions/tau_retail/step_decomposition/opus/v0.1.0/manifest.json) | 4 | 25 (25 / 0 / 0) | 2.5 | 1.5 | $4.37 |

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

- **Decomposition only applies to text steps.** A tool-call root cause (a single `cancel_pending_order`, `calculate`, `exchange_delivered_order_items`) is declined, because splitting it would mean inventing an extra message or call. That is why the accept counts are well under 29.
- **The models differ in how conservative they are.** Haiku and Sonnet split both assistant and user text turns; Opus declined all user turns and most assistant text, accepting only 4. Treat the generator choice as a variable, not a detail.
- **Tasks 2, 3 and 4 are related** — same user, same T-shirt miscount — so their decompositions look alike. Treat them as one group when computing rates.
- **One sample per model.** Each trajectory was generated once per model, without seed control.
- **How the reviews were done.** A reviewer confirmed each accepted case keeps the same actor and the same unfixed mistake. An automatic numeric-token check flags cases for a closer look; it over-flags Tau order IDs (the digits are glued to a `W` prefix), and those were checked by hand.

---

## Upstream AgentRx, license and citation

AgentRx is by Microsoft Research ([paper](https://arxiv.org/abs/2602.02475), [dataset](https://huggingface.co/datasets/microsoft/AgentRx)) and is licensed under the [MIT](LICENSE.txt) license. Copyright (c) Microsoft Corporation. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

```bibtex
@article{barke2026agentrx,
  title={AgentRx: Diagnosing AI Agent Failures from Execution Trajectories},
  author={Barke, Shraddha and others},
  journal={arXiv preprint arXiv:2602.02475},
  year={2026}
}
```
