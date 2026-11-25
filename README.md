# AgentRx Robustness Framework

**Fooling the Flight Recorder:** does AgentRx still find the real root cause when a failed trajectory is reworded without changing what went wrong?

[AgentRx](https://arxiv.org/abs/2602.02475) ([dataset](https://huggingface.co/datasets/microsoft/AgentRx)) reads a failed agent trajectory and names the *critical failure step* and its failure category. This framework takes the frozen Tau Retail failures and rewrites each one in three **label-preserving** ways, so the annotated root cause stays the true root cause. It stores every rewording as a versioned dataset release, re-judges each release with AgentRx, and measures how often the verdict moves.

```
baseline trajectories ─▶ generate (Copilot CLI) ─▶ automatic checks ─▶ human review
        │                                                                  │
        ▼                                                                  ▼
 AgentRx judge (clean) ◀──────────── compare ────────────▶ AgentRx judge (release)
```

| Rewording | What changes | Generator model | `compare` reports |
|---|---|---|---|
| **Step decomposition** | The root-cause step is split into 2–4 smaller steps by the same actor; the mistake stays on one of them | `claude-haiku-5.5` | decomposition evasion rate |
| **Step decoy** | Up to 3 noise replays and 3 failed-attempt red herrings are inserted before the root cause | `claude-sonnet-5.5` | decoy attraction rate |
| **Presentation change** | Wording, markdown emphasis or JSON layout change; no step moves | `claude-opus-5.5` | verdict-flip rate |

The generator models were chosen in an earlier model-comparison study (see [Branches](#branches)). All three run at medium reasoning effort through the GitHub Copilot CLI, the same CLI the AgentRx judge uses. The judge is `gpt-6.1-sol` at medium effort.

---

## Setup

You need Python 3.10 or newer, Git, and Node.js/npm for the GitHub Copilot CLI.

```bash
git clone https://github.com/aparnashree11/agentRx.git
cd agentRx
python3.12 -m venv .venv
source .venv/bin/activate       # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
npm install -g @github/copilot
copilot login
cp .env.example .env
```

`copilot login` signs in with your GitHub account; no API key is needed. **Every model below must be enabled for that account.** Opus 5.5 and GPT-6.1 Sol need Copilot Pro+, Business or Enterprise. To check, start `copilot` and enter `/model`. A disabled model makes a run stop with `Model "…" is not available`.

### Configuration (`.env`)

The defaults in `.env.example` are the finalized framework settings. Change them only to change the framework itself; no command-line flag overrides the generator models.

| Variable | Default | Used by |
|---|---|---|
| `AGENT_VERIFY_ENDPOINT_TYPE` | `copilot` | AgentRx (`run.py`) |
| `AGENT_VERIFY_COPILOT_MODEL` | `gpt-6.1-sol` | AgentRx judge and invariant stages |
| `AGENT_VERIFY_COPILOT_REASONING_EFFORT` | `medium` | AgentRx |
| `STEP_DECOMPOSITION_COPILOT_MODEL` / `…_REASONING_EFFORT` | `claude-haiku-5.5` / `medium` | step-decomposition generator |
| `STEP_DECOY_COPILOT_MODEL` / `…_REASONING_EFFORT` | `claude-sonnet-5.5` / `medium` | step-decoy generator |
| `PRESENTATION_CHANGE_COPILOT_MODEL` / `…_REASONING_EFFORT` | `claude-opus-5.5` / `medium` | presentation-change generator |
| `AGENT_VERIFY_COPILOT_BIN` | found on `PATH` / npm locations | everything that calls Copilot |
| `AGENT_VERIFY_COPILOT_TIMEOUT` | `600` | seconds per Copilot call |

---

## Run the framework

All commands run from the project root with the virtual environment active. The examples use Tau Retail. Each step can be interrupted and resumed with the same command.

```bash
base=data/benchmark_versions/tau_retail/baseline/v1.0.0
```

### 1. Judge the clean baseline

Every release is compared with a clean run made with the **same** judge command. So run the baseline first, and again whenever the judge model or settings change:

```bash
python run.py "$base/tau_dataset_failed.json" --domain tau \
  --ground-truth "$base/tau_ground_truth.json" \
  --dynamic-mode oneshot --run-name tau_clean
```

The judge's verdicts are written to `runs/tau_clean/judge_output/runs/run1.json`.

### 2. Generate the three rewordings

Each command makes one isolated Copilot call per labeled trajectory, with that rewording's own model. The call has no tools, no MCP servers, no custom instructions and an empty working directory. Each case is saved to a work folder for review:

```bash
python -m agentrx.rewordings.step_decomposition generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
  --work runs/decomp/tau

python -m agentrx.rewordings.step_decoy generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
  --work runs/decoy/tau

python -m agentrx.rewordings.presentation_change generate --domain tau \
  --trajectories "$base/tau_dataset_failed.json" --ground-truth "$base/tau_ground_truth.json" \
  --work runs/presentation_change/tau
```

- **Pilot:** add `--ids 4` to try a single trajectory. A presentation-change pilot can't be released.
- **Locked work folder:** each work folder's `config.json` locks the model, effort, prompt, policy and input checksums, so a later run with different settings is refused.
- **What each case folder holds:** `proposal.json` and `generation.json` (model, effort, Copilot CLI version, premium requests, code hashes). A valid case also has the rebuilt `events.json`. A proposal that breaks a rule is kept as `invalid.json`.
- **Presentation change:** each case is generated **once**; there are no retries.

### 3. Review every candidate

Python has already checked the structure: roles, turn order, call IDs and values. The review is about **meaning**: does the annotated failure stay the real root cause, unfixed and no clearer or vaguer than before?

**Step decomposition and step decoy.** For each case, read `proposal.json`, `events.json` and `step_map.json` in the work folder, plus `decomposition.json` or `insertions.json`. Then write `<work>/reviews.json`:

```json
{
  "4": {"decision": "accept", "reviewer": "<your name>", "reason": "<what in the trace supports your decision>"}
}
```

**Presentation change.** Write a review sheet, then fill in the template it creates:

```bash
python -m agentrx.rewordings.presentation_change review-sheet --work runs/presentation_change/tau
```

This writes `review_sheet.md` and `reviews.template.json` in the work folder. Fill in `decision`, `reviewer` and `reason`, keep each case's `events_sha256` as written, and save the file as `reviews.json`. The hash ties your review to the exact events you read.

### 4. Release

```bash
python -m agentrx.rewordings.step_decomposition release --work runs/decomp/tau \
  --reviews runs/decomp/tau/reviews.json --version v0.2.0
python -m agentrx.rewordings.step_decoy release --work runs/decoy/tau \
  --reviews runs/decoy/tau/reviews.json --version v0.2.0
python -m agentrx.rewordings.presentation_change release --work runs/presentation_change/tau \
  --reviews runs/presentation_change/tau/reviews.json --version v0.2.0
```

Each release is written to `data/benchmark_versions/tau_retail/<rewording>/v0.2.0/` and contains:

- `trajectories/` with the accepted cases, in the input's own layout;
- `ground_truth.json`, renumbered when steps moved;
- `audit.json` with every case's proposal, review, step map and any exclusion reason;
- `manifest.json` with the model, effort, Copilot CLI version, code and prompt hashes, parent checksums and an SHA-256 for every file.

Releases are immutable: release refuses an existing version, and before writing it rebuilds every accepted case and refuses any that changed. The `haiku/`, `sonnet/` and `opus/` v0.1.0 folders come from the model-comparison study and are kept as they are.

- **Step decomposition and step decoy:** only accepted cases are released.
- **Presentation change:** the release must account for all 29 Tau trajectories. A case that is invalid, returned no edit or was rejected is excluded, and the reason is recorded in `manifest.json` (`excluded_ids`, `excluded`) and in `audit.json`. A missing case, or a missing or stale review, stops the release.

### 5. Judge each release

Use the same command as the clean run, with the release's trajectories and ground truth:

```bash
for r in step_decomposition step_decoy presentation_change; do
  rel=data/benchmark_versions/tau_retail/$r/v0.2.0
  python run.py "$rel/trajectories" --domain tau --ground-truth "$rel/ground_truth.json" \
    --dynamic-mode oneshot --run-name "tau_$r"
done
```

### 6. Compare with the clean run

```bash
for r in step_decomposition step_decoy presentation_change; do
  python -m agentrx.rewordings.$r compare \
    --audit data/benchmark_versions/tau_retail/$r/v0.2.0/audit.json \
    --clean runs/tau_clean/judge_output/runs/run1.json \
    --variant runs/tau_$r/judge_output/runs/run1.json
done
```

`compare` pairs the trajectories the clean run localized correctly and reports what happened to each one in the reworded run:

- **Step decomposition:** the judge either still lands on the smaller step that carries the mistake, or drifts to a sibling step or another step (**evasion rate**).
- **Step decoy:** the judge either keeps the original root step, or moves to an inserted noise or red-herring step (**attraction rate**, split by kind) or another step.
- **Presentation change:** the judge either keeps both step and category, or changes the step, the category or both (**verdict-flip rate**, also reported on cases whose clean category was correct).

For step and category accuracy with Wilson 95% intervals on any run:

```bash
python baselines/score_runs.py --ground-truth "$rel/ground_truth.json" --out scores.json \
  runs/tau_step_decoy/judge_output/runs/run1.json
```

### Other domains

Each generator takes `--domain` (`tau`, `magentic`, `flash`) and any trajectory layout AgentRx reads. A domain without a default policy needs `--policy`.

For presentation change outside Tau, name the roles that may be reworded with `--prose-roles` (and the policy roles with `--policy-roles`). Before sending Magentic-One traces to a generator or the judge, follow the setup in [RELEASE_PLAN.md](RELEASE_PLAN.md) §3 (prose roles, redaction).

### Reproduce the frozen baseline score

`scripts/reproduce_baseline.sh` checks the frozen inputs against their checksums and re-scores the committed `gpt-6.1-sol` runs. It needs no credentials and prints step accuracy 0.4138 for all three runs:

```bash
bash scripts/reproduce_baseline.sh
```

### Tests

```bash
python -m pytest tests
```

No model is called: the Copilot CLI is replaced by a fake. The Magentic-One tests are skipped when that baseline is not checked out.

---

## Where things are

```
AgentRx/
├── run.py                              # AgentRx pipeline (IR → invariants → check → judge → report)
├── agentrx/
│   ├── rewordings/
│   │   ├── copilot.py                  # shared, isolated Copilot CLI call; per-rewording models
│   │   ├── step_decomposition.py       # generate / release / compare
│   │   ├── step_decoy.py               # generate / release / compare (+ shared dataset helpers)
│   │   ├── presentation_change.py      # generate / review-sheet / release / compare
│   │   ├── *_prompt.txt                # domain-general prompts with <<PLACEHOLDER>> slots
│   │   └── reports/                    # model-comparison findings, review sheets, signed reviews
│   ├── llm_clients/copilot_cli.py      # AgentRx's Copilot client (judge model and effort)
│   ├── ir/ invariants/ judge/ reports/ # AgentRx
│   └── pipeline/globals.py             # AgentRx configuration
├── data/benchmark_versions/            # frozen baseline and every rewording release
│   ├── README.md                       # versioning rules; step decoy and presentation change in detail
│   └── README_step_decomposition.md    # step decomposition in detail
├── baselines/score_runs.py             # step / category accuracy with Wilson intervals
├── results/                            # frozen baseline runs, scores and data checks
├── scripts/reproduce_baseline.sh       # credential-free baseline reproduction
├── RELEASE_PLAN.md                     # frozen versions, run gate, rollback, disclosure
└── tests/
```

---

## AgentRx reference

### Pipeline stages

| # | Stage | Output |
|---|-------|--------|
| 1 | **IR**: normalize raw logs into the canonical trajectory IR | `trajectory_ir.json` |
| 2 | **Static**: policy, tool and structure invariants | `static_invariants.json` |
| 3 | **Dynamic**: per-step, context-aware invariants | `dynamic_invariants/` |
| 4 | **Check**: evaluate the invariants and record violations | `checker_results/` |
| 5 | **Judge**: the LLM names the critical step and failure category | `judge_output/` |
| 6 | **Report**: failure-frequency plots | `plots/` |

Each stage can be run on its own, resuming from an earlier run: `python run.py trajectory.json --stage <ir|static|dynamic|check|judge|report> --run-dir runs/my_run`. A small synthetic example for learning the pipeline is `python run.py trajectories/tau-retail/agentrx_walkthrough.json --domain tau --run-name tau_walkthrough`.

### Failure taxonomy

| # | Category | Description |
|---|----------|-------------|
| 1 | **Instruction/Plan Adherence Failure** | Skips steps or adds unnecessary actions |
| 2 | **Invention of New Information** | Fabricates or omits ungrounded facts |
| 3 | **Invalid Invocation** | Malformed tool call (wrong args/types/schema) |
| 4 | **Misinterpretation of Tool Output** | Incorrect reasoning about tool results |
| 5 | **Intent-Plan Misalignment** | Pursues wrong objective |
| 6 | **Underspecified User Intent** | Missing information to proceed |
| 7 | **Intent Not Supported** | Action can't be performed with available tools |
| 8 | **Guardrails Triggered** | Blocked by safety/RAI/access policies |
| 9 | **System Failure** | Infra errors (timeouts, unreachable endpoints) |
| 10 | **Inconclusive** | Insufficient evidence to classify |

### Other LLM endpoints

The Copilot CLI is the default. For Azure OpenAI, set `AGENT_VERIFY_ENDPOINT_TYPE=azure` (or pass `--endpoint azure`) and configure `AGENT_VERIFY_ENDPOINT`, `AGENT_VERIFY_DEPLOYMENT` and `AGENT_VERIFY_MODEL_NAME`; authentication uses Azure identity credentials such as `az login`. If `DefaultAzureCredential` stalls for 5–10 s on a local machine, set `AZURE_TOKEN_CREDENTIALS=dev` (requires `azure-identity >= 1.23.0`). The rewording generators always use the Copilot CLI.

---

## Contributing, license and citation

AgentRx is by Microsoft Research and licensed under the [MIT](LICENSE.txt) license. Copyright (c) Microsoft Corporation. See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines. Use of Microsoft trademarks or logos must follow [Microsoft's Trademark & Brand Guidelines](https://www.microsoft.com/en-us/legal/intellectualproperty/trademarks/usage/general) and must not imply Microsoft sponsorship.

```bibtex
@article{barke2026agentrx,
  title={AgentRx: Diagnosing AI Agent Failures from Execution Trajectories},
  author={Barke, Shraddha and Goyal, Arnav and Khare, Alind and Singh, Avaljot and Nath, Suman and Bansal, Chetan},
  journal={arXiv preprint arXiv:2602.02475},
  year={2026}
}
```

---

## Branches

Each branch below holds the analysis behind one part of the framework. The rewording branches contain the **model-comparison study** that chose each generator: Haiku, Sonnet and Opus on all 29 Tau trajectories, the review sheets and the `v0.1.0` releases. They use the earlier Claude Code generator, not the Copilot CLI used here.

| Branch | What you can run there | Instructions |
|---|---|---|
| [`step-decomposition`](https://github.com/Aparnashree11/agentRx/tree/step-decomposition) | Step-decomposition study: generate, review and release with each model, then compare against the clean run | the branch's `README.md` |
| [`step-decoy`](https://github.com/Aparnashree11/agentRx/tree/step-decoy) | Step-decoy study: the same workflow for noise and red-herring insertions | the branch's `README.md` |
| [`presentation-change-v2`](https://github.com/Aparnashree11/agentRx/tree/presentation-change-v2) | Presentation-change study, including the review-sheet workflow and the model-performance report | `data/benchmark_versions/README.md` on that branch ("Generate presentation changes") |
| [`baseline-results`](https://github.com/Aparnashree11/agentRx/tree/baseline-results) | The frozen AgentRx baseline on Tau Retail (`gpt-6.1-sol` and `gpt-6-luna` runs, scores, data checks) | `bash scripts/reproduce_baseline.sh` |

The repository is private, so these links need access to `Aparnashree11/agentRx`.
